# Image Generation CLI

Generate images using Google's Gemini API with style reference support.

## Usage

```bash
uv run gemini.py "<prompt>" [options]
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-r, --reference` | Reference image for style matching (repeatable) | None |
| `-a, --aspect` | Aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4, etc.) | 1:1 |
| `-s, --size` | Image size: 1K, 2K, or 4K | 1K |
| `-c, --count` | Number of images to generate in parallel | 1 |
| `-n, --name` | Filename prefix | gemini |
| `-o, --output` | Output directory | output |

## Examples

```bash
# Basic
uv run gemini.py "a castle on a hill"

# With style reference
uv run gemini.py "a castle on a hill" -r references/pixel1.png

# Multiple references, custom aspect ratio
uv run gemini.py "a castle on a hill" -r references/pixel1.png -r references/pixel2.png -a 16:9

# Generate 5 variations
uv run gemini.py "a castle on a hill" -c 5
```

## Output Structure

```
output/
├── images/      # Generated images
│   └── {timestamp}-{name}[-{n}].{ext}
└── metadata/    # JSON with prompt, settings, cost
    └── {timestamp}-{name}[-{n}].json
```

## Requirements

- `GEMINI_API_KEY` in `.env`
- Python 3.10+
- Dependencies installed via `uv sync`
