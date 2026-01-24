# stylegen

A CLI for generating images with Google's Gemini API, designed around one idea: **your AI-generated images should look like *yours*, not like everyone else's.**

## The Problem

AI image generation is everywhere now, but the outputs all look the same. Generic. You've seen that "Midjourney look" or that "DALL-E vibe" a thousand times. The web interfaces are convenient, but they're designed for one-off generations, not for building a consistent personal aesthetic.

## The Solution

stylegen is built for a different workflow:

1. **Find or create reference images** that represent your style
2. **Use those references consistently** across all your generations
3. **Generate variations in parallel** to find the best output
4. **Keep metadata for reproducibility** so you can recreate or iterate on any image

This is how you build a personal AI art style that's recognizably yours.

## Features

- **Style references** - Pass 1-2 images that define your aesthetic, and every generation matches that style
- **Parallel generation** - Generate multiple variations simultaneously with `-c 5` (true async, not sequential)
- **Rich metadata** - Every image gets a JSON file with the full command, settings, cost, and timestamps
- **Reproducibility** - Re-run any generation exactly from its metadata

## Install

```bash
# With uv (recommended)
uv tool install git+https://github.com/ryanbbrown/stylegen

# Or clone and install locally
git clone https://github.com/ryanbbrown/stylegen
cd stylegen
uv tool install .
```

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

## Output

Images and metadata are saved separately:

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

Each metadata JSON includes:
- Full command to reproduce the generation
- Prompt and all settings
- Reference image paths
- Token usage and cost
- Timestamps

## Design Decisions

**Why separate JSON metadata instead of embedding in PNG?**
Easier to search, parse, and use programmatically. You can `grep` through your metadata, pipe it to `jq`, or let a coding agent read it.

**Why parallel generation?**
AI image generation has natural variation. Generating 3-5 images at once and picking the best is faster than generating one, deciding it's not quite right, and regenerating.

**Why job timestamps?**
Images from the same batch share a timestamp, so they sort together. The individual completion time is in the metadata if you need it.

## Pricing

As of January 2026 (gemini-3-pro-image-preview):
- 1K/2K resolution: ~$0.13/image
- 4K resolution: ~$0.24/image

Cost is tracked per-image in the metadata.

## Acknowledgments

Inspired by [gemimg](https://github.com/minimaxir/gemimg) and [imagemage](https://github.com/quinnypig/imagemage). Built for use with coding agents like Claude Code.

## License

MIT
