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
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-r, --reference` | Reference image for style matching (repeatable) | None |
| `-c, --count` | Number of images to generate in parallel | 1 |
| `-a, --aspect` | Aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4, etc.) | 1:1 |
| `-s, --size` | Image size: 1K, 2K, or 4K | 1K |
| `-n, --name` | Filename prefix | sgen |
| `-o, --output` | Output directory | output |

## Example

This repo includes pixel art reference images to demonstrate the workflow:

```bash
sgen "A cute friendly robot with a round head and expressive eyes, sitting at a cozy desk in a recording studio, reading from an open book into a desk microphone. The robot wears headphones. Floating books and music notes surround the scene. Warm lighting, simple clean background. Cartoon illustration style, bold outlines, flat colors, whimsical and playful mood." -r references/pixel1.png -a 3:2
```

<img src="https://github.com/user-attachments/assets/b85ac429-3c88-4605-9945-ddf2af809e6d" width="60%" />

Generated metadata:

```json
{
  "command": "sgen \"A cute friendly robot...\" -r references/pixel1.png -a 3:2",
  "prompt": "A cute friendly robot with a round head and expressive eyes...",
  "aspect_ratio": "3:2",
  "size": "1K",
  "reference": ["references/pixel1.png"],
  "job_timestamp": "2026-01-24T15-54-27",
  "generated_at": "2026-01-24T15:54:41.590988",
  "image_tokens": 1120,
  "cost": 0.1344
}
```

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


## Acknowledgments

Inspired by [gemimg](https://github.com/minimaxir/gemimg) and [imagemage](https://github.com/quinnypig/imagemage). Built for use with coding agents like Claude Code.
