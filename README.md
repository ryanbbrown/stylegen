# stylegen

CLI for generating images with Google's Gemini API, with support for style references and parallel batch generation.

## Install

```bash
# Install globally with uv
uv tool install git+https://github.com/ryanbbrown/stylegen

# Or clone and install locally
git clone https://github.com/ryanbbrown/stylegen
cd stylegen
uv tool install .
```

## Setup

1. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)
2. Create a `.env` file (or export the variable):
   ```
   GEMINI_API_KEY=your_api_key_here
   ```

## Usage

```bash
# Basic generation
sgen "a robot in a forest"

# With style reference (e.g., pixel art)
sgen "a robot in a forest" -r references/pixel1.png

# Multiple style references
sgen "a robot in a forest" -r references/pixel1.png -r references/pixel2.png

# Custom aspect ratio and size
sgen "a robot in a forest" -a 16:9 -s 2K

# Generate 5 variations in parallel
sgen "a robot in a forest" -r references/pixel1.png -c 5

# Custom output name
sgen "a robot in a forest" -n robot-forest
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-r, --reference` | Reference image(s) for style matching (can use multiple) | None |
| `-a, --aspect` | Aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4, etc. | 1:1 |
| `-s, --size` | Image size: 1K, 2K, or 4K | 1K |
| `-c, --count` | Number of images to generate in parallel | 1 |
| `-n, --name` | Filename prefix | sgen |
| `-o, --output` | Output directory | output |

## Output

Images are saved to `output/images/` with metadata in `output/metadata/`.

Filename format:
- Single: `{timestamp}-{name}.{ext}`
- Batch: `{timestamp}-{name}-{n}.{ext}`

Metadata JSON includes the full command for reproducibility.

## Pricing

As of January 2026 (gemini-3-pro-image-preview):
- 1K/2K resolution: ~$0.13/image
- 4K resolution: ~$0.24/image

## Example: Pixel Art Style

The included reference images (`references/pixel1.png`, `references/pixel2.png`) demonstrate style-matched generation:

```bash
sgen "a cozy tavern with a fireplace" -r references/pixel1.png -r references/pixel2.png -c 3
```
