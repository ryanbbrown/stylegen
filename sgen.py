"""stylegen - Gemini and OpenAI image generation CLI with style references.

Pricing (as of 2026-07-27):
  Pro (gemini-3-pro-image-preview):
    - 1K/2K: ~$0.134/image (1,120 tokens @ $120/1M)
    - 4K: ~$0.24/image (2,000 tokens)
  Flash (gemini-2.5-flash-image):
    - ~$0.019/image (1,120 tokens @ $17/1M) - fixed 1K output
  GPT (gpt-image-2):
    - 1K: ~$0.12-0.21/image (3,900-7,000 tokens @ $30/1M, varies with dimensions)
    - Scales up with resolution; 2K/4K are flagged experimental by OpenAI
"""

import argparse
import asyncio
import base64
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from openai import AsyncOpenAI
from PIL import Image

load_dotenv()

VALID_ASPECTS = ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "21:9", "5:4", "4:5"]
VALID_SIZES = ["1K", "2K", "4K"]
MODELS = {
    "pro": "gemini-3-pro-image-preview",
    "flash": "gemini-2.5-flash-image",
    "gpt": "gpt-image-2",
}
PROVIDERS = {"pro": "gemini", "flash": "gemini", "gpt": "openai"}
API_KEY_VARS = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}

MIME_TYPES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}
STYLE_PREFIX = "Match the visual style of these reference images exactly."

# Pricing per 1M tokens (as of 2026-07-27)
PRICE_PER_M_IMAGE_TOKENS = {"pro": 120.0, "flash": 17.0, "gpt": 30.0}
PRICE_PER_M_TEXT_TOKENS = {"pro": 2.0, "flash": 2.0, "gpt": 5.0}
OPENAI_PRICE_PER_M_IMAGE_INPUT = 8.0  # gpt-image-2 bills input images separately; Gemini folds them into prompt tokens

# gpt-image-2 takes a literal WIDTHxHEIGHT instead of an aspect ratio, capped at 3840px per edge
OPENAI_PIXEL_TARGETS = {"1K": 1_048_576, "2K": 4_194_304, "4K": 8_294_400}
OPENAI_MAX_EDGE = 3840
OPENAI_MAX_REFERENCES = 16
OPENAI_QUALITY = "high"  # pinned: 'auto' can silently pick 'low', which defeats style matching


@dataclass
class ImageResult:
    """A generated image plus usage, normalized across providers."""
    data: bytes
    mime_type: str
    input_tokens: int
    image_tokens: int
    input_cost: float
    image_cost: float


def load_image_base64(path: str | Path) -> dict[str, str]:
    """Load image file as base64 string with mime type."""
    with open(path, "rb") as f:
        return {"mime_type": MIME_TYPES.get(Path(path).suffix.lower(), 'image/png'), "data": base64.b64encode(f.read()).decode("utf-8")}

def load_image_upload(path: str | Path) -> tuple[str, bytes, str]:
    """Load image file as an OpenAI (filename, bytes, mime type) upload tuple.

    Bytes rather than a file handle so the same reference can be sent by concurrent requests.
    """
    path = Path(path)
    with open(path, "rb") as f:
        return (path.name, f.read(), MIME_TYPES.get(path.suffix.lower(), 'image/png'))

def aspect_to_size(aspect_ratio: str, image_size: str) -> str:
    """Map an aspect ratio and size tier to a gpt-image-2 WIDTHxHEIGHT string.

    Edges must be multiples of 16 and at most 3840px, and total pixels must not exceed the
    4K target, so the scale is capped on the long edge and both edges are rounded down.
    """
    w, h = (int(n) for n in aspect_ratio.split(":"))
    scale = min(math.sqrt(OPENAI_PIXEL_TARGETS[image_size] / (w * h)), OPENAI_MAX_EDGE / max(w, h))
    return f"{math.floor(w * scale / 16) * 16}x{math.floor(h * scale / 16) * 16}"

def detect_aspect_ratio(path: str | Path) -> str:
    """Detect closest supported aspect ratio from image dimensions."""
    with Image.open(path) as img:
        width, height = img.size
    ratio = width / height
    return min(VALID_ASPECTS, key=lambda ar: abs(ratio - int(ar.split(":")[0]) / int(ar.split(":")[1])))

def load_prompt(prompt_or_path: str) -> tuple[str, str | None]:
    """Load prompt from file if path exists, otherwise return as-is. Returns (prompt, source_file)."""
    path = Path(prompt_or_path)
    if path.exists() and path.is_file():
        return path.read_text().strip(), str(path)
    return prompt_or_path, None

def save_image(result: ImageResult, output_dir: str | Path, name: str = "gemini", metadata: dict | None = None, job_timestamp: str | None = None, index: int | None = None) -> Path:
    """Save image and metadata to separate subdirectories."""
    output_dir = Path(output_dir)
    images_dir = output_dir / "images"
    metadata_dir = output_dir / "metadata"
    images_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    ext = 'png' if 'png' in result.mime_type else 'jpg'
    timestamp = job_timestamp or datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    basename = f"{timestamp}-{name}" if index is None else f"{timestamp}-{name}-{index}"

    image_path = images_dir / f"{basename}.{ext}"
    metadata_path = metadata_dir / f"{basename}.json"

    # Save image
    with open(image_path, "wb") as f:
        f.write(result.data)

    # Save metadata
    if metadata:
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

    print(f"✓ Saved: {image_path}")
    return image_path

async def generate(prompt: str, reference: list[str] | None = None, input_image: str | None = None, aspect_ratio: str = "1:1", image_size: str = "1K", model: str = "pro", temperature: float = 1.0) -> ImageResult:
    """Generate or edit image via the provider backing the selected model."""
    if aspect_ratio not in VALID_ASPECTS:
        raise ValueError(f"Invalid aspect ratio. Must be one of: {VALID_ASPECTS}")
    if image_size not in VALID_SIZES:
        raise ValueError(f"Invalid size. Must be one of: {VALID_SIZES}")
    if model not in MODELS:
        raise ValueError(f"Invalid model. Must be one of: {list(MODELS.keys())}")

    # Only the selected provider's key is required, so one key is enough to use its models
    api_key = os.getenv(API_KEY_VARS[PROVIDERS[model]])
    if not api_key:
        raise ValueError(f"{API_KEY_VARS[PROVIDERS[model]]} not set in environment")

    refs = reference if isinstance(reference, list) else ([reference] if reference else [])
    if PROVIDERS[model] == "openai" and len(refs) > OPENAI_MAX_REFERENCES:
        raise ValueError(f"gpt-image-2 accepts at most {OPENAI_MAX_REFERENCES} reference images")

    if input_image:
        print(f"Editing: {input_image}")
    for i, ref in enumerate(refs):
        print(f"Using reference {i+1}: {ref}")

    mode = "Editing" if input_image else "Generating"
    # gpt-image-2 has no temperature knob, so don't imply one was applied
    settings = f"{model}, {aspect_ratio}, {image_size}" + (f", temp={temperature}" if PROVIDERS[model] == "gemini" else "")
    print(f"{mode} ({settings}): {prompt[:50]}{'...' if len(prompt) > 50 else ''}")

    if PROVIDERS[model] == "openai":
        return await generate_openai(prompt, refs, input_image, aspect_ratio, image_size, model, api_key)
    return await generate_gemini(prompt, refs, input_image, aspect_ratio, image_size, model, temperature, api_key)


async def generate_gemini(prompt: str, refs: list[str], input_image: str | None, aspect_ratio: str, image_size: str, model: str, temperature: float, api_key: str) -> ImageResult:
    """Generate or edit image via Gemini API."""
    client = genai.Client(api_key=api_key)

    parts = []

    # Edit mode: input image without style prefix
    if input_image:
        parts.append({"inline_data": load_image_base64(input_image)})
    # Generate mode: optional style references with prefix
    elif refs:
        for ref in refs:
            parts.append({"inline_data": load_image_base64(ref)})
        parts.append({"text": STYLE_PREFIX})

    parts.append({"text": prompt})

    # Build config - Flash model doesn't support image_size
    image_config = types.ImageConfig(aspect_ratio=aspect_ratio)
    if model == "pro":
        image_config = types.ImageConfig(aspect_ratio=aspect_ratio, image_size=image_size)

    response = await client.aio.models.generate_content(
        model=MODELS[model],
        contents=[{"role": "user", "parts": parts}],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            temperature=temperature,
            image_config=image_config
        )
    )

    # Gemini reports one input total; reference images are billed inside it as prompt tokens
    usage = response.usage_metadata
    input_tokens = (usage.prompt_token_count or 0) if usage else 0
    image_tokens = 0
    if usage:
        for detail in (usage.candidates_tokens_details or []):
            if detail.modality.value == 'IMAGE':
                image_tokens = detail.token_count

    # Extract image from response
    if response.candidates and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            inline = getattr(part, 'inline_data', None)
            if inline and inline.mime_type and inline.mime_type.startswith('image/'):
                data = inline.data
                if isinstance(data, str):
                    data = base64.b64decode(data)
                return ImageResult(
                    data=data,
                    mime_type=inline.mime_type,
                    input_tokens=input_tokens,
                    image_tokens=image_tokens,
                    input_cost=(input_tokens / 1_000_000) * PRICE_PER_M_TEXT_TOKENS[model],
                    image_cost=(image_tokens / 1_000_000) * PRICE_PER_M_IMAGE_TOKENS[model],
                )

    raise ValueError("No image generated - check your prompt or try again")


async def generate_openai(prompt: str, refs: list[str], input_image: str | None, aspect_ratio: str, image_size: str, model: str, api_key: str) -> ImageResult:
    """Generate or edit image via OpenAI Images API."""
    client = AsyncOpenAI(api_key=api_key)
    params = {
        "model": MODELS[model],
        "size": aspect_to_size(aspect_ratio, image_size),
        "quality": OPENAI_QUALITY,
    }

    # Only the edits endpoint accepts images, so both edit mode and style references route through it
    if input_image:
        response = await client.images.edit(image=load_image_upload(input_image), prompt=prompt, **params)
    elif refs:
        response = await client.images.edit(image=[load_image_upload(r) for r in refs], prompt=f"{STYLE_PREFIX}\n\n{prompt}", **params)
    else:
        response = await client.images.generate(prompt=prompt, **params)

    if not response.data or not response.data[0].b64_json:
        raise ValueError("No image generated - check your prompt or try again")

    usage = response.usage
    details = usage.input_tokens_details if usage else None
    text_input_tokens = (details.text_tokens or 0) if details else 0
    image_input_tokens = (details.image_tokens or 0) if details else 0
    image_tokens = (usage.output_tokens or 0) if usage else 0

    return ImageResult(
        data=base64.b64decode(response.data[0].b64_json),
        mime_type="image/png",  # the API returns PNG unless output_format says otherwise
        input_tokens=(usage.input_tokens or 0) if usage else 0,
        image_tokens=image_tokens,
        input_cost=(text_input_tokens / 1_000_000) * PRICE_PER_M_TEXT_TOKENS[model]
        + (image_input_tokens / 1_000_000) * OPENAI_PRICE_PER_M_IMAGE_INPUT,
        image_cost=(image_tokens / 1_000_000) * PRICE_PER_M_IMAGE_TOKENS[model],
    )


def print_usage(result: ImageResult) -> None:
    """Print token usage and estimated cost."""
    if not result.input_tokens and not result.image_tokens:
        return

    print(f"Tokens: {result.input_tokens} input, {result.image_tokens} image output")
    print(f"Est. cost: ${result.input_cost + result.image_cost:.4f}")

async def generate_single(args: argparse.Namespace, job_timestamp: str, index: int | None = None) -> Path:
    """Generate a single image and save it."""
    prompt, prompt_file = load_prompt(args.prompt)
    if prompt_file:
        print(f"Using prompt from: {prompt_file}")

    result = await generate(
        prompt=prompt,
        reference=args.reference,
        aspect_ratio=args.aspect,
        image_size=args.size.upper(),
        model=args.model,
        temperature=args.temperature
    )

    provider = PROVIDERS[args.model]

    # Build metadata for reproducibility
    cmd_parts = ["sgen", args.prompt]  # Use original arg (file path or text)
    if args.name != "sgen":
        cmd_parts.extend(["-n", args.name])
    if args.reference:
        for ref in args.reference:
            cmd_parts.extend(["-r", ref])
    if args.aspect != "1:1":
        cmd_parts.extend(["-a", args.aspect])
    if args.size.upper() != "1K":
        cmd_parts.extend(["-s", args.size.upper()])
    if args.model != "pro":
        cmd_parts.extend(["-m", args.model])
    if args.temperature != 1.0 and provider == "gemini":  # -t is ignored on providers without it
        cmd_parts.extend(["-t", str(args.temperature)])
    if args.count > 1:
        cmd_parts.extend(["-c", str(args.count)])

    metadata = {
        "command": " ".join(f'"{p}"' if " " in p else p for p in cmd_parts),
        "prompt": prompt,
        "prompt_file": prompt_file,
        "name": args.name,
        "aspect_ratio": args.aspect,
        "size": args.size.upper(),
        "model": args.model,
        "provider": provider,
        "temperature": args.temperature if provider == "gemini" else None,
        "quality": OPENAI_QUALITY if provider == "openai" else None,
        "reference": args.reference,
        "job_timestamp": job_timestamp,
        "generated_at": datetime.now().isoformat(),
        "index": index,
        "image_tokens": result.image_tokens,
        "cost": round(result.image_cost, 4)
    }

    print_usage(result)
    return save_image(result, args.output, name=args.name, metadata=metadata, job_timestamp=job_timestamp, index=index)


async def edit_single(args: argparse.Namespace, job_timestamp: str) -> Path:
    """Edit a single image and save it."""
    instruction, instruction_file = load_prompt(args.instruction)
    if instruction_file:
        print(f"Using instruction from: {instruction_file}")

    # Auto-detect aspect ratio if not specified
    aspect = args.aspect if args.aspect else detect_aspect_ratio(args.image)
    if not args.aspect:
        print(f"Auto-detected aspect ratio: {aspect}")

    result = await generate(
        prompt=instruction,
        input_image=args.image,
        aspect_ratio=aspect,
        image_size=args.size.upper(),
        model=args.model,
        temperature=args.temperature
    )

    provider = PROVIDERS[args.model]

    # Build metadata for reproducibility
    cmd_parts = ["sgen", "edit", args.image, args.instruction]  # Use original arg
    if args.name != "sgen":
        cmd_parts.extend(["-n", args.name])
    if args.aspect:
        cmd_parts.extend(["-a", args.aspect])
    if args.size.upper() != "1K":
        cmd_parts.extend(["-s", args.size.upper()])
    if args.model != "pro":
        cmd_parts.extend(["-m", args.model])
    if args.temperature != 1.0 and provider == "gemini":  # -t is ignored on providers without it
        cmd_parts.extend(["-t", str(args.temperature)])

    metadata = {
        "command": " ".join(f'"{p}"' if " " in p else p for p in cmd_parts),
        "mode": "edit",
        "instruction": instruction,
        "instruction_file": instruction_file,
        "input_image": args.image,
        "name": args.name,
        "aspect_ratio": aspect,
        "aspect_auto_detected": not args.aspect,
        "size": args.size.upper(),
        "model": args.model,
        "provider": provider,
        "temperature": args.temperature if provider == "gemini" else None,
        "quality": OPENAI_QUALITY if provider == "openai" else None,
        "job_timestamp": job_timestamp,
        "generated_at": datetime.now().isoformat(),
        "image_tokens": result.image_tokens,
        "cost": round(result.image_cost, 4)
    }

    print_usage(result)
    return save_image(result, args.output, name=args.name, metadata=metadata, job_timestamp=job_timestamp)


def warn_unsupported_temperature(args: argparse.Namespace) -> None:
    """Warn once when -t was set on a model that has no temperature control."""
    if args.temperature != 1.0 and PROVIDERS[args.model] != "gemini":
        print(f"Warning: --temperature is not supported by {MODELS[args.model]} and will be ignored")


async def async_main() -> None:
    # Check if first arg is "edit" subcommand
    if len(sys.argv) > 1 and sys.argv[1] == "edit":
        parser = argparse.ArgumentParser(
            prog="sgen edit",
            description="Edit an existing image with natural language",
            epilog="Pricing: pro ~$0.13/image (1K/2K), ~$0.24 (4K) | flash ~$0.02/image | gpt ~$0.12-0.21/image (1K)"
        )
        parser.add_argument("_edit", help=argparse.SUPPRESS)  # consume "edit"
        parser.add_argument("image", help="Image to edit")
        parser.add_argument("instruction", help="Edit instruction")
        parser.add_argument("-n", "--name", default="sgen", help="Filename prefix (default: sgen)")
        parser.add_argument("-a", "--aspect", default=None, help=f"Aspect ratio (default: auto-detect). Options: {', '.join(VALID_ASPECTS)}")
        parser.add_argument("-s", "--size", default="1K", help="Image size: 1K, 2K, or 4K (default: 1K; ignored by flash, 2K/4K experimental on gpt)")
        parser.add_argument("-m", "--model", default="pro", choices=list(MODELS), help="Model to use: pro, flash, or gpt (default: pro)")
        parser.add_argument("-t", "--temperature", type=float, default=1.0, help="Temperature 0.0-2.0 (default: 1.0, lower=more consistent, gemini models only)")
        parser.add_argument("-o", "--output", default="output", help="Output directory")

        args = parser.parse_args()
        if not Path(args.image).exists():
            print(f"Error: Image not found: {args.image}")
            sys.exit(1)
        warn_unsupported_temperature(args)

        job_timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        await edit_single(args, job_timestamp)
    else:
        # Generate mode (default)
        parser = argparse.ArgumentParser(
            prog="sgen",
            description="Generate style-matched images via Gemini or OpenAI",
            epilog="Pricing: pro ~$0.13/image (1K/2K), ~$0.24 (4K) | flash ~$0.02/image | gpt ~$0.12-0.21/image (1K)"
        )
        parser.add_argument("prompt", help="Image description")
        parser.add_argument("-n", "--name", default="sgen", help="Filename prefix (default: sgen)")
        parser.add_argument("-r", "--reference", action="append", help="Reference image(s) for style matching (can use multiple times)")
        parser.add_argument("-a", "--aspect", default="1:1", help=f"Aspect ratio (default: 1:1). Options: {', '.join(VALID_ASPECTS)}")
        parser.add_argument("-s", "--size", default="1K", help="Image size: 1K, 2K, or 4K (default: 1K; ignored by flash, 2K/4K experimental on gpt)")
        parser.add_argument("-m", "--model", default="pro", choices=list(MODELS), help="Model to use: pro, flash, or gpt (default: pro)")
        parser.add_argument("-t", "--temperature", type=float, default=1.0, help="Temperature 0.0-2.0 (default: 1.0, lower=more consistent, gemini models only)")
        parser.add_argument("-o", "--output", default="output", help="Output directory")
        parser.add_argument("-c", "--count", type=int, default=1, help="Number of images to generate in parallel (default: 1)")

        args = parser.parse_args()
        warn_unsupported_temperature(args)
        job_timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

        if args.count == 1:
            await generate_single(args, job_timestamp, index=None)
        else:
            print(f"Generating {args.count} images in parallel...")
            tasks = [generate_single(args, job_timestamp, i + 1) for i in range(args.count)]
            await asyncio.gather(*tasks)
            print(f"\n✓ Generated {args.count} images")


def main() -> None:
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
