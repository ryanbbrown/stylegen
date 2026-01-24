"""stylegen - Gemini image generation CLI with style references.

Pricing (as of 2026-01-20):
  Pro (gemini-3-pro-image-preview):
    - 1K/2K: ~$0.134/image (1,120 tokens @ $120/1M)
    - 4K: ~$0.24/image (2,000 tokens)
  Flash (gemini-2.5-flash-image):
    - ~$0.019/image (1,120 tokens @ $17/1M) - fixed 1K output
"""

import argparse
import asyncio
import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()

VALID_ASPECTS = ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "21:9", "5:4", "4:5"]
VALID_SIZES = ["1K", "2K", "4K"]
MODELS = {
    "pro": "gemini-3-pro-image-preview",
    "flash": "gemini-2.5-flash-image",
}

# Pricing per 1M tokens (as of 2026-01-20)
PRICE_PER_M_IMAGE_TOKENS = {"pro": 120.0, "flash": 17.0}  # Pro: $120, Flash: $17
PRICE_PER_M_TEXT_TOKENS = 2.0  # $2 per 1M text input tokens

def load_image_base64(path: str | Path) -> dict[str, str]:
    """Load image file as base64 string with mime type."""
    ext = Path(path).suffix.lower()
    mime_types = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}
    with open(path, "rb") as f:
        return {"mime_type": mime_types.get(ext, 'image/png'), "data": base64.b64encode(f.read()).decode("utf-8")}

def detect_aspect_ratio(path: str | Path) -> str:
    """Detect closest supported aspect ratio from image dimensions."""
    with Image.open(path) as img:
        width, height = img.size
    ratio = width / height
    return min(VALID_ASPECTS, key=lambda ar: abs(ratio - int(ar.split(":")[0]) / int(ar.split(":")[1])))

def save_image(image_data: Any, output_dir: str | Path, name: str = "gemini", metadata: dict | None = None, job_timestamp: str | None = None, index: int | None = None) -> Path:
    """Save image and metadata to separate subdirectories."""
    output_dir = Path(output_dir)
    images_dir = output_dir / "images"
    metadata_dir = output_dir / "metadata"
    images_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    ext = 'png' if 'png' in image_data.mime_type else 'jpg'
    timestamp = job_timestamp or datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    basename = f"{timestamp}-{name}" if index is None else f"{timestamp}-{name}-{index}"

    image_path = images_dir / f"{basename}.{ext}"
    metadata_path = metadata_dir / f"{basename}.json"

    # Save image
    data = image_data.data
    if isinstance(data, str):
        data = base64.b64decode(data)
    with open(image_path, "wb") as f:
        f.write(data)

    # Save metadata
    if metadata:
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

    print(f"✓ Saved: {image_path}")
    return image_path

async def generate(prompt: str, reference: list[str] | None = None, input_image: str | None = None, aspect_ratio: str = "1:1", image_size: str = "1K", model: str = "pro", temperature: float = 1.0) -> tuple[Any, Any]:
    """Generate or edit image via Gemini API."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    if aspect_ratio not in VALID_ASPECTS:
        raise ValueError(f"Invalid aspect ratio. Must be one of: {VALID_ASPECTS}")
    if image_size not in VALID_SIZES:
        raise ValueError(f"Invalid size. Must be one of: {VALID_SIZES}")
    if model not in MODELS:
        raise ValueError(f"Invalid model. Must be one of: {list(MODELS.keys())}")

    client = genai.Client(api_key=api_key)
    model_name = MODELS[model]

    parts = []

    # Edit mode: input image without style prefix
    if input_image:
        img_data = load_image_base64(input_image)
        parts.append({"inline_data": img_data})
        print(f"Editing: {input_image}")
    # Generate mode: optional style references with prefix
    elif reference:
        refs = reference if isinstance(reference, list) else [reference]
        for i, ref in enumerate(refs):
            ref_data = load_image_base64(ref)
            parts.append({"inline_data": ref_data})
            print(f"Using reference {i+1}: {ref}")
        parts.append({"text": "Match the visual style of these reference images exactly."})

    parts.append({"text": prompt})

    mode = "Editing" if input_image else "Generating"
    print(f"{mode} ({model}, {aspect_ratio}, {image_size}, temp={temperature}): {prompt[:50]}{'...' if len(prompt) > 50 else ''}")

    # Build config - Flash model doesn't support image_size
    image_config = types.ImageConfig(aspect_ratio=aspect_ratio)
    if model == "pro":
        image_config = types.ImageConfig(aspect_ratio=aspect_ratio, image_size=image_size)

    response = await client.aio.models.generate_content(
        model=model_name,
        contents=[{"role": "user", "parts": parts}],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            temperature=temperature,
            image_config=image_config
        )
    )

    # Extract image from response
    if response.candidates and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            inline = getattr(part, 'inline_data', None)
            if inline and inline.mime_type and inline.mime_type.startswith('image/'):
                return inline, response

    raise ValueError("No image generated - check your prompt or try again")

def print_usage(response: Any, model: str = "pro") -> None:
    """Print token usage and estimated cost."""
    usage = response.usage_metadata
    if not usage:
        return

    # Get token counts
    prompt_tokens = usage.prompt_token_count or 0
    image_tokens = 0
    for detail in (usage.candidates_tokens_details or []):
        if detail.modality.value == 'IMAGE':
            image_tokens = detail.token_count

    # Calculate cost using model-specific pricing
    text_cost = (prompt_tokens / 1_000_000) * PRICE_PER_M_TEXT_TOKENS
    image_cost = (image_tokens / 1_000_000) * PRICE_PER_M_IMAGE_TOKENS[model]
    total_cost = text_cost + image_cost

    print(f"Tokens: {prompt_tokens} input, {image_tokens} image output")
    print(f"Est. cost: ${total_cost:.4f}")

async def generate_single(args: argparse.Namespace, job_timestamp: str, index: int | None = None) -> Path:
    """Generate a single image and save it."""
    image_data, response = await generate(
        prompt=args.prompt,
        reference=args.reference,
        aspect_ratio=args.aspect,
        image_size=args.size.upper(),
        model=args.model,
        temperature=args.temperature
    )

    # Build metadata for reproducibility
    cmd_parts = ["sgen", args.prompt]
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
    if args.temperature != 1.0:
        cmd_parts.extend(["-t", str(args.temperature)])
    if args.count > 1:
        cmd_parts.extend(["-c", str(args.count)])

    usage = response.usage_metadata
    image_tokens = 0
    if usage:
        for detail in (usage.candidates_tokens_details or []):
            if detail.modality.value == 'IMAGE':
                image_tokens = detail.token_count

    metadata = {
        "command": " ".join(f'"{p}"' if " " in p else p for p in cmd_parts),
        "prompt": args.prompt,
        "name": args.name,
        "aspect_ratio": args.aspect,
        "size": args.size.upper(),
        "model": args.model,
        "temperature": args.temperature,
        "reference": args.reference,
        "job_timestamp": job_timestamp,
        "generated_at": datetime.now().isoformat(),
        "index": index,
        "image_tokens": image_tokens,
        "cost": round((image_tokens / 1_000_000) * PRICE_PER_M_IMAGE_TOKENS[args.model], 4)
    }

    print_usage(response, args.model)
    return save_image(image_data, args.output, name=args.name, metadata=metadata, job_timestamp=job_timestamp, index=index)


async def edit_single(args: argparse.Namespace, job_timestamp: str) -> Path:
    """Edit a single image and save it."""
    # Auto-detect aspect ratio if not specified
    aspect = args.aspect if args.aspect else detect_aspect_ratio(args.image)
    if not args.aspect:
        print(f"Auto-detected aspect ratio: {aspect}")

    image_data, response = await generate(
        prompt=args.instruction,
        input_image=args.image,
        aspect_ratio=aspect,
        image_size=args.size.upper(),
        model=args.model,
        temperature=args.temperature
    )

    # Build metadata for reproducibility
    cmd_parts = ["sgen", "edit", args.image, args.instruction]
    if args.name != "sgen":
        cmd_parts.extend(["-n", args.name])
    if args.aspect:
        cmd_parts.extend(["-a", args.aspect])
    if args.size.upper() != "1K":
        cmd_parts.extend(["-s", args.size.upper()])
    if args.model != "pro":
        cmd_parts.extend(["-m", args.model])
    if args.temperature != 1.0:
        cmd_parts.extend(["-t", str(args.temperature)])

    usage = response.usage_metadata
    image_tokens = 0
    if usage:
        for detail in (usage.candidates_tokens_details or []):
            if detail.modality.value == 'IMAGE':
                image_tokens = detail.token_count

    metadata = {
        "command": " ".join(f'"{p}"' if " " in p else p for p in cmd_parts),
        "mode": "edit",
        "instruction": args.instruction,
        "input_image": args.image,
        "name": args.name,
        "aspect_ratio": aspect,
        "aspect_auto_detected": not args.aspect,
        "size": args.size.upper(),
        "model": args.model,
        "temperature": args.temperature,
        "job_timestamp": job_timestamp,
        "generated_at": datetime.now().isoformat(),
        "image_tokens": image_tokens,
        "cost": round((image_tokens / 1_000_000) * PRICE_PER_M_IMAGE_TOKENS[args.model], 4)
    }

    print_usage(response, args.model)
    return save_image(image_data, args.output, name=args.name, metadata=metadata, job_timestamp=job_timestamp)


async def async_main() -> None:
    # Check if first arg is "edit" subcommand
    if len(sys.argv) > 1 and sys.argv[1] == "edit":
        parser = argparse.ArgumentParser(
            prog="sgen edit",
            description="Edit an existing image with natural language",
            epilog="Pricing: pro ~$0.13/image (1K/2K), ~$0.24 (4K) | flash ~$0.02/image"
        )
        parser.add_argument("_edit", help=argparse.SUPPRESS)  # consume "edit"
        parser.add_argument("image", help="Image to edit")
        parser.add_argument("instruction", help="Edit instruction")
        parser.add_argument("-n", "--name", default="sgen", help="Filename prefix (default: sgen)")
        parser.add_argument("-a", "--aspect", default=None, help=f"Aspect ratio (default: auto-detect). Options: {', '.join(VALID_ASPECTS)}")
        parser.add_argument("-s", "--size", default="1K", help="Image size: 1K, 2K, or 4K (default: 1K, pro model only)")
        parser.add_argument("-m", "--model", default="pro", choices=["pro", "flash"], help="Model to use: pro or flash (default: pro)")
        parser.add_argument("-t", "--temperature", type=float, default=1.0, help="Temperature 0.0-2.0 (default: 1.0, lower=more consistent)")
        parser.add_argument("-o", "--output", default="output", help="Output directory")

        args = parser.parse_args()
        if not Path(args.image).exists():
            print(f"Error: Image not found: {args.image}")
            sys.exit(1)

        job_timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        await edit_single(args, job_timestamp)
    else:
        # Generate mode (default)
        parser = argparse.ArgumentParser(
            prog="sgen",
            description="Generate style-matched images via Gemini",
            epilog="Pricing: pro ~$0.13/image (1K/2K), ~$0.24 (4K) | flash ~$0.02/image"
        )
        parser.add_argument("prompt", help="Image description")
        parser.add_argument("-n", "--name", default="sgen", help="Filename prefix (default: sgen)")
        parser.add_argument("-r", "--reference", action="append", help="Reference image(s) for style matching (can use multiple times)")
        parser.add_argument("-a", "--aspect", default="1:1", help=f"Aspect ratio (default: 1:1). Options: {', '.join(VALID_ASPECTS)}")
        parser.add_argument("-s", "--size", default="1K", help="Image size: 1K, 2K, or 4K (default: 1K, pro model only)")
        parser.add_argument("-m", "--model", default="pro", choices=["pro", "flash"], help="Model to use: pro or flash (default: pro)")
        parser.add_argument("-t", "--temperature", type=float, default=1.0, help="Temperature 0.0-2.0 (default: 1.0, lower=more consistent)")
        parser.add_argument("-o", "--output", default="output", help="Output directory")
        parser.add_argument("-c", "--count", type=int, default=1, help="Number of images to generate in parallel (default: 1)")

        args = parser.parse_args()
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
