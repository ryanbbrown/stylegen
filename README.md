# stylegen

Minimal CLI for generating images with Google's Gemini API, with style reference support and parallel batch generation.

Built to help maintain a consistent personal style for AI-generated images, so that you don't end up with the same generic style as everyone else.

## Install

```bash
# Install as a global CLI tool
uv tool install git+https://github.com/ryanbbrown/stylegen
```

Or clone the repo if you want the included reference images as a starting point:

```bash
git clone https://github.com/ryanbbrown/stylegen
cd stylegen
uv tool install .
```

Output directories are created automatically wherever you run `sgen`.

## Setup

1. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)
2. Set the environment variable:
   ```bash
   export GEMINI_API_KEY=your_api_key_here
   ```
   Or create a `.env` file in your working directory.

## Usage

```bash
# Basic generation
sgen "a cozy cabin in the woods"

# With your style reference
sgen "a cozy cabin in the woods" -r my-style.png

# Multiple references for stronger style matching
sgen "a cozy cabin in the woods" -r style1.png -r style2.png

# Generate 5 variations to pick the best one
sgen "a cozy cabin in the woods" -r my-style.png -c 5

# Different aspect ratios and sizes
sgen "a cozy cabin in the woods" -a 16:9 -s 2K

# Use flash model (7x cheaper, lower quality)
sgen "a cozy cabin in the woods" -m flash

# Lower temperature for more consistent results
sgen "a cozy cabin in the woods" -t 0.5

# Prompt from file (for longer/reusable prompts)
sgen prompts/my-style.md -r style.png
```

### Edit Mode

```bash
# Edit an image (aspect ratio auto-detected)
sgen edit photo.png "make the sky more dramatic"

# Override aspect ratio
sgen edit photo.png "add a rainbow" -a 16:9
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-r, --reference` | Reference image for style matching (repeatable) | None |
| `-c, --count` | Number of images to generate in parallel | 1 |
| `-a, --aspect` | Aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4, etc.) | 1:1 (auto-detect in edit mode) |
| `-s, --size` | Image size: 1K, 2K, or 4K (pro model only) | 1K |
| `-m, --model` | Model: pro or flash | pro |
| `-t, --temperature` | Temperature 0.0-2.0 (lower = more consistent) | 1.0 |
| `-n, --name` | Filename prefix | sgen |
| `-o, --output` | Output directory | output |

**Pricing:** pro ~$0.13/image (1K/2K), ~$0.24 (4K) \| flash ~$0.02/image

## Example

This repo includes pixel art reference images to demonstrate the workflow:

```bash
sgen "A cute friendly robot with a round head and expressive eyes, sitting at a cozy desk in a recording studio, reading from an open book into a desk microphone. The robot wears headphones. Floating books and music notes surround the scene. Warm lighting, simple clean background. Cartoon illustration style, bold outlines, flat colors, whimsical and playful mood." -r references/pixel1.png -a 3:2
```


<p align="center">
  <img src="https://github-production-user-asset-6210df.s3.amazonaws.com/56168848/540163721-b85ac429-3c88-4605-9945-ddf2af809e6d.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAVCODYLSA53PQK4ZA%2F20260224%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260224T005713Z&X-Amz-Expires=300&X-Amz-Signature=a3f860111733e6bb3eb81b6e43d2b38d3d98253efd7cd1d79a0455e147d8c60e&X-Amz-SignedHeaders=host" width="60%" />
</p>

Generated metadata:

```json
{
  "command": "sgen \"A cute friendly robot...\" -r references/pixel1.png -a 3:2",
  "prompt": "A cute friendly robot with a round head and expressive eyes...",
  "aspect_ratio": "3:2",
  "size": "1K",
  "model": "pro",
  "temperature": 1.0,
  "reference": ["references/pixel1.png"],
  "job_timestamp": "2026-01-24T15-54-27",
  "generated_at": "2026-01-24T15:54:41.590988",
  "image_tokens": 1120,
  "cost": 0.1344
}
```

A few more examples using the same style reference:

<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/e5cddf4d-2f62-49e4-860a-b0cf035e8c41" width="100%" /></td>
    <td><img src="https://github.com/user-attachments/assets/a5119f3a-7731-49cc-9e68-e0134a66677f" width="100%" /></td>
  </tr>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/d17539d9-0438-4774-a9dc-f0a3454818b4" width="100%" /></td>
    <td><img src="https://github.com/user-attachments/assets/224dda80-7d6e-4d6c-b914-1a2b46fa595b" width="100%" /></td>
  </tr>
</table>

## Output

Images and rich metadata are saved separately:

```
output/
├── images/
│   ├── 2026-01-24T15-30-00-sgen-1.png
│   ├── 2026-01-24T15-30-00-sgen-2.png
│   └── ...
└── metadata/
    ├── 2026-01-24T15-30-00-sgen-1.json
    ├── 2026-01-24T15-30-00-sgen-2.json
    └── ...
```

## Design Decisions

**Why separate JSON metadata instead of embedding in PNG?**

Easier to search, parse, and use programmatically. You can `grep` through your metadata, pipe it to `jq`, or let a coding agent read it and re-run the command.

**Why parallel generation?**

AI image generation has natural variation. Generating 3-5 images at once and picking the best is faster than generating one, deciding it's not quite right, and regenerating.

**Why no built-in prompt management?**

Prompts can be passed as text or as a file path (if the path exists, its contents are used). Beyond that, prompt management is left to you and your tools. Store prompts in version-controlled files, use templates, or let a coding agent manage them—whatever fits your workflow.


## Acknowledgments

Inspired by [gemimg](https://github.com/minimaxir/gemimg) and [imagemage](https://github.com/quinnypig/imagemage). Built for use with coding agents like Claude Code.
