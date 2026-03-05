# AI System Instruction

**This file contains instructions for AI agents maintaining this project.**

---

## Repository Overview

**Project:** THE TRUTH - Static Socio-Economic Blog
**Domain:** thetruth.io.vn
**Stack:** Python static generator + Cloudflare Pages + Cloudflare Worker

---

## CRITICAL RULES

### NEVER EDIT

```
❌ NEVER edit _site/
❌ NEVER commit _site/
❌ NEVER edit generated files directly
```

### ALWAYS EDIT

```
✅ Edit source files in:
   - content/ (markdown)
   - layouts/ (HTML templates)
   - scripts/build.py (Python)
   - workers/ (Cloudflare Worker)
```

---

## Repository Structure

```
thetruth-io-vn/
├── content/              # MARKDOWN BLOG POSTS (edit here)
├── layouts/              # HTML TEMPLATES (edit here)
├── scripts/
│   └── build.py        # BUILD SYSTEM (edit here)
├── workers/
│   └── subscribe/       # CLOUDFLARE WORKER (edit here)
├── docs/                # DOCUMENTATION
├── tests/               # UNIT TESTS
├── .github/
│   └── workflows/       # CI/CD
├── _site/               # GENERATED OUTPUT (never edit)
├── wrangler.toml        # CLOUDFLARE CONFIG
└── requirements.txt     # PYTHON DEPENDENCIES
```

---

## Content Pipeline

```
content/*.md (markdown)
        ↓
scripts/build.py
        ↓
_site/ (static HTML)
        ↓
GitHub Actions
        ↓
Cloudflare Pages
        ↓
CDN
```

### To Add Content

1. Create `content/your-article.md`:
```yaml
---
title: "Your Title"
slug: "your-slug"
excerpt: "Brief description"
date: 2026-03-05
tags: [tag1, tag2]
---
Your content here...
```

2. Run `python scripts/build.py`
3. Commit and push

---

## Build System

**Location:** `scripts/build.py`

**Responsibilities:**
- Parse markdown → HTML
- Render Jinja2 templates
- Generate sitemap, RSS, search index
- Generate OG images via Playwright

**Run locally:**
```bash
pip install -r requirements.txt
python scripts/build.py
```

---

## Deployment Pipeline

```
git push
    ↓
GitHub Actions (runs tests + build)
    ↓
Cloudflare Pages (deploys _site/)
    ↓
CDN (global delivery)
```

**No manual deployment needed.**

---

## Email Subscription Worker

**Location:** `workers/subscribe/`

**Endpoints:**
- `POST /subscribe` - Submit email
- `GET /subscribe/confirm?token=xxx` - Confirm
- `GET /subscribe/unsubscribe?token=xxx` - Unsubscribe

**Database:** Cloudflare D1
**Rate Limit:** Cloudflare KV

---

## Safe Modification Rules

### ✅ ALLOWED

- Add/edit markdown in `content/`
- Edit HTML templates in `layouts/`
- Modify build.py in `scripts/`
- Update worker in `workers/subscribe/`
- Add tests in `tests/`
- Update docs in `docs/`

### ❌ FORBIDDEN

- Edit files in `_site/` directly
- Commit generated files
- Add tracking scripts
- Introduce server-side rendering
- Add unnecessary frameworks

---

## Common Tasks

### Add New Blog Post

```bash
# 1. Create markdown
vim content/new-post.md

# 2. Build locally
python scripts/build.py

# 3. Test locally
python -m http.server 8000 --directory _site

# 4. Commit and push
git add content/new-post.md
git commit -m "Add: new post"
git push
```

### Modify Template

1. Edit `layouts/post.html` (or other)
2. Run `python scripts/build.py`
3. Check `_site/` output
4. Commit and push

### Update Worker

```bash
cd workers/subscribe
wrangler deploy
```

### Add Test

1. Edit `tests/test_build.py`
2. Run `pytest`
3. Commit and push

---

## Troubleshooting

### Build Fails

```bash
# Check dependencies
pip install -r requirements.txt

# Run tests
pytest

# Verbose build
python -v scripts/build.py
```

### Worker Errors

```bash
# View logs
wrangler tail

# Test locally
wrangler dev workers/subscribe/index.js
```

---

## Documentation

All documentation in `docs/`:

| File | Purpose |
|------|---------|
| `docs/architecture.md` | System overview |
| `docs/content-pipeline.md` | How to add content |
| `docs/build-system.md` | Build system details |
| `docs/deployment.md` | Deployment guide |
| `docs/workers.md` | Worker documentation |

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `content/*.md` | Blog posts |
| `layouts/*.html` | HTML templates |
| `scripts/build.py` | Static generator |
| `workers/subscribe/index.js` | Email worker |
| `wrangler.toml` | Cloudflare config |
| `.github/workflows/build.yml` | CI/CD |

---

## CI/CD Secrets

Set in GitHub: Settings → Secrets and variables → Actions

| Secret | Purpose |
|--------|---------|
| `CLOUDFLARE_API_TOKEN` | Deploy to Pages |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account |

Worker secrets (via `wrangler secret put`):
- `RESEND_API_KEY`
- `OWNER_EMAIL`

---

## Summary

1. **Content** goes in `content/`
2. **Templates** go in `layouts/`
3. **Build** runs via `scripts/build.py`
4. **Output** is in `_site/` (never edit)
5. **Push** triggers deployment automatically

**When in doubt, check `docs/`.**
