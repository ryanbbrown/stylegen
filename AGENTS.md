# stylegen

Generate images using Google's Gemini API with style reference support.

## Usage

```bash
sgen "<prompt>" [options]
sgen edit <image> "<instruction>" [options]
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-r, --reference` | Reference image for style matching (repeatable) | None |
| `-a, --aspect` | Aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4, etc.) | 1:1 (auto-detect in edit) |
| `-s, --size` | Image size: 1K, 2K, or 4K (pro only) | 1K |
| `-m, --model` | Model: pro or flash | pro |
| `-t, --temperature` | Temperature 0.0-2.0 | 1.0 |
| `-c, --count` | Number of images to generate in parallel | 1 |
| `-n, --name` | Filename prefix | sgen |
| `-o, --output` | Output directory | output |

## Examples

```bash
# Basic
sgen "a castle on a hill"

# With style reference
sgen "a castle on a hill" -r references/pixel1.png

# Multiple references, custom aspect ratio
sgen "a castle on a hill" -r references/pixel1.png -r references/pixel2.png -a 16:9

# Generate 5 variations
sgen "a castle on a hill" -c 5

# Use flash model (cheaper)
sgen "a castle on a hill" -m flash

# Prompt from file
sgen prompts/castle.md -r style.png

# Edit an existing image
sgen edit photo.png "make the sky more dramatic"
```

Prompts can be text or file paths. If path exists, contents are used as prompt.

## Output Structure

```
output/
├── images/      # Generated images
│   └── {timestamp}-{name}[-{n}].{ext}
└── metadata/    # JSON with prompt, settings, cost
    └── {timestamp}-{name}[-{n}].json
```

## Requirements

- `GEMINI_API_KEY` in `.env` or environment
- Python 3.10+
