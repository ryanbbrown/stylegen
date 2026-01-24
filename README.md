# image-gen

CLI for generating images with Google's Gemini API, with support for style references and parallel batch generation.

## Setup

1. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)
2. Copy `.env.example` to `.env` and add your key:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```
3. Install dependencies:
   ```bash
   uv sync
   ```

## Usage

```bash
# Basic generation
uv run gemini.py "a robot in a forest"

# With style reference (e.g., pixel art)
uv run gemini.py "a robot in a forest" -r references/pixel1.png

# Multiple style references
uv run gemini.py "a robot in a forest" -r references/pixel1.png -r references/pixel2.png

# Custom aspect ratio and size
uv run gemini.py "a robot in a forest" -a 16:9 -s 2K

# Generate 5 variations in parallel
uv run gemini.py "a robot in a forest" -r references/pixel1.png -c 5

# Custom output name
uv run gemini.py "a robot in a forest" -n robot-forest
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-r, --reference` | Reference image(s) for style matching (can use multiple) | None |
| `-a, --aspect` | Aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4, etc. | 1:1 |
| `-s, --size` | Image size: 1K, 2K, or 4K | 1K |
| `-c, --count` | Number of images to generate in parallel | 1 |
| `-n, --name` | Custom name for output file | gemini |
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

The included reference images (`references/pixel1.png`, `references/pixel2.png`) demonstrate style-matched generation for pixel art:

```bash
uv run gemini.py "a cozy tavern with a fireplace" -r references/pixel1.png -r references/pixel2.png -c 3
```
