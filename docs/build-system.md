# Build System

## Overview

Location: `scripts/build.py`

The build system transforms markdown content into static HTML.

## Responsibilities

### 1. Markdown Parsing

- Reads `content/*.md` files
- Parses YAML frontmatter
- Converts markdown to HTML

### 2. Template Rendering

- Uses Jinja2 templates from `layouts/`
- Passes context: title, content, tags, date, etc.

### 3. Post Generation

- Generates individual blog post pages
- Adds related articles
- Adds tension cards

### 4. Index Generation

- Homepage (`index.html`)
- Articles list (`phan-tich.html`)
- Tags pages

### 5. Artifact Generation

| Artifact | Purpose |
|----------|---------|
| `sitemap.xml` | Search engine indexing |
| `robots.txt` | Crawler instructions |
| `rss.xml` | RSS feed |
| `search.json` | Client-side search |
| `posts.json` | AI pipeline content index |
| `site-manifest.json` | Site metadata |

### 6. OG Image Generation

- Uses Playwright to screenshot HTML templates
- Outputs to `_site/og/{slug}.png`

## Build Output

Generated to `_site/`:

```
_site/
├── index.html              # Homepage
├── phan-tich.html          # Articles list
├── ve-he-thong.html        # About
├── ten-xo.html             # Tensions
├── sitemap.xml             # Sitemap
├── robots.txt              # Robots
├── rss.xml                 # RSS
├── search.json             # Search index
├── posts.json              # Content index
├── site-manifest.json      # Site manifest
├── og/                     # OG images
│   └── *.png
├── tags/                   # Tag pages
│   └── *.html
└── *.html                  # Blog posts
```

## Running the Build

### Local Build

```bash
pip install -r requirements.txt
python scripts/build.py
```

### Output

```
Built 7 posts to _site/
Generated 7 OG images
```

## Dependencies

See `requirements.txt`:

```
Jinja2==3.1.6        # Template engine
Markdown==3.8.2      # Markdown parser
PyYAML==6.0.3       # YAML parsing
pytest==8.4.2        # Testing
playwright>=1.40.0  # OG images
```

## Build Configuration

### Site URL

Set in `scripts/build.py`:

```python
SITE_URL = "https://thetruth.io.vn"
```

### Template Directory

```python
LAYOUTS_DIR = Path("layouts")
```

### Output Directory

```python
OUTPUT_DIR = Path("_site")
```

## Customization

### Adding New Templates

1. Create template in `layouts/`
2. Add render call in `scripts/build.py`

### Adding New Artifacts

1. Add generation function in `scripts/build.py`
2. Call from `build_site()` function

## Validation

The build system validates:
- All internal links exist
- Required frontmatter present
- No broken references

## Troubleshooting

### Build Fails

```bash
# Check Python version
python --version  # Should be 3.11+

# Reinstall dependencies
pip install -r requirements.txt

# Run with verbose output
python -v scripts/build.py
```

### OG Images Not Generated

```bash
# Install Playwright
pip install playwright
playwright install chromium

# Test manually
python -c "from playwright.async_api import async_playwright"
```

### Template Errors

Check Jinja2 syntax in `layouts/`. Common issues:
- Missing endif
- Unclosed tags
- Invalid variable names
