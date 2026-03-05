# THE TRUTH

Static socio-economic blog system for thetruth.io.vn

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Build the site
python scripts/build.py

# Preview
python -m http.server 8000 --directory _site
```

## Project Structure

```
content/          # Markdown blog posts
layouts/          # HTML templates
scripts/          # Build system
workers/          # Cloudflare Worker
docs/             # Documentation
tests/            # Unit tests
_site/            # Generated output (do not edit)
```

## Publishing

1. Add markdown to `content/`
2. Commit and push to GitHub
3. Cloudflare Pages auto-deploys

## Documentation

- [Architecture](docs/architecture.md)
- [Content Pipeline](docs/content-pipeline.md)
- [Build System](docs/build-system.md)
- [Deployment](docs/deployment.md)
- [Workers](docs/workers.md)
- [AI System Instruction](docs/ai-system-instruction.md)

## Tech Stack

- Python static generator
- Jinja2 templates
- Markdown content
- Cloudflare Pages + Worker + D1 + KV
- GitHub Actions CI/CD
- Playwright (OG images)
