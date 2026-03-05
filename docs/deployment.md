# Deployment Guide

## Pipeline Overview

```
Developer → GitHub → CI/CD Build → Cloudflare Pages → CDN
```

## Deployment Pipeline

```
git push
    ↓
GitHub Actions
    ↓
Build (python scripts/build.py)
    ↓
Cloudflare Pages
    ↓
CDN (global)
```

## GitHub Actions Workflow

Location: `.github/workflows/build.yml`

```yaml
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -r requirements.txt
      - run: pytest -q
      - run: python scripts/build.py
      - uses: cloudflare/pages-action@v1
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          projectName: thetruth-io-vn
          directory: _site
```

## Cloudflare Setup

### 1. Pages Project

- Name: `thetruth-io-vn`
- Build output: `_site/`
- Build command: (none - pre-built)

### 2. Required Secrets

Set in GitHub repository settings:

| Secret | Purpose |
|--------|---------|
| `CLOUDFLARE_API_TOKEN` | Deploy to Pages |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account |

### 3. Domain

- Add custom domain: `thetruth.io.vn`
- Enable HTTPS (automatic via Cloudflare)

## Worker Deployment

### Prerequisites

```bash
# Install wrangler
npm install -g wrangler
```

### 1. Create D1 Database

```bash
wrangler d1 create thetruth-subscribers
```

Update `wrangler.toml` with returned `database_id`.

### 2. Create KV Namespace

```bash
wrangler kv:namespace create SUBSCRIBERS_KV
```

Update `wrangler.toml` with returned `id`.

### 3. Add Secrets

```bash
wrangler secret put RESEND_API_KEY
# Enter your Resend API key

wrangler secret put OWNER_EMAIL
# Enter your email address
```

### 4. Deploy Worker

```bash
cd workers/subscribe
wrangler deploy
```

## Local Development

### Build Site

```bash
pip install -r requirements.txt
python scripts/build.py
```

### Preview

```bash
# Serve _site/ locally
python -m http.server 8000 --directory _site
```

### Test Worker Locally

```bash
wrangler dev workers/subscribe/index.js
```

## Troubleshooting

### Build Fails

```bash
# Check Python version
python --version  # Should be 3.11+

# Reinstall dependencies
pip install -r requirements.txt

# Run tests
pytest
```

### Worker Not Responding

```bash
# Check worker logs
wrangler tail

# Check deployment
wrangler deployments list
```

### Cloudflare Pages Not Updating

1. Check GitHub Actions ran successfully
2. Verify `_site/` was generated
3. Check Cloudflare dashboard for errors

## Rollback

```
Cloudflare Dashboard → Pages → thetruth-io-vn → Deployments
Click "Roll back" on previous deployment
```

## Environment Variables

| Variable | Where Set | Purpose |
|----------|-----------|---------|
| `SITE_URL` | wrangler.toml | Site URL |
| `RESEND_API_KEY` | wrangler secrets | Email sending |
| `OWNER_EMAIL` | wrangler secrets | Notification recipient |

## CI/CD Secrets

Set in GitHub: Settings → Secrets and variables → Actions

| Secret | Required | Description |
|--------|----------|-------------|
| `CLOUDFLARE_API_TOKEN` | Yes | Pages deployment |
| `CLOUDFLARE_ACCOUNT_ID` | Yes | Account ID |

## Quick Deploy Options

### Option 1: GitHub Integration (Recommended)

1. Push to GitHub
2. Connect repository in Cloudflare Pages
3. Deploys automatically on push

### Option 2: Wrangler CLI

```bash
wrangler pages deploy _site \
  --project-name=thetruth-io-vn \
  --branch=main
```

## Custom Domain

1. Go to Cloudflare Pages → Custom domains
2. Add domain (e.g., `thetruth.io.vn`)
3. DNS updates automatic via Cloudflare
