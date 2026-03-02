# Cloudflare Pages Deployment

## Quick Deploy

### Option 1: GitHub Integration (Recommended)

1. **Push to GitHub**
   ```bash
   cd site
   git init
   git add .
   git commit -m "Initial site"
   # Create repo on GitHub, then:
   git remote add origin https://github.com/yourusername/sable-site.git
   git push -u origin main
   ```

2. **Connect to Cloudflare Pages**
   - Go to Cloudflare Dashboard → Pages
   - Connect GitHub repository
   - Settings:
     - Build command: `python3 build.py`
     - Build output directory: `_site`
     - Python version: 3.11

3. **Deploy**
   - Cloudflare auto-deploys on push
   - Custom domain: Add in Settings → Custom domains

---

### Option 2: Wrangler CLI

```bash
# Install wrangler
npm install -g wrangler

# Login
wrangler login

# Deploy
wrangler pages deploy site/_site \
  --project-name=sable-site \
  --branch=main
```

---

## Project Structure

```
site/
├── content/              # Markdown articles
│   └── income-vs-assets.md
├── layouts/              # HTML templates
│   ├── index.html
│   └── post.html
├── static/               # Static assets (favicon, etc.)
├── _site/                # Built output (gitignore this)
├── build.py             # Static site generator
└── requirements.txt     # Python dependencies
```

---

## Adding New Articles

1. **Create markdown file** in `content/`
   ```markdown
   ---
   title: "Article Title"
   slug: "article-slug"
   excerpt: "Short description"
   tags: ["tag1", "tag2"]
   date: "2026-03-01"
   ---
   
   Your content here...
   ```

2. **Build site**
   ```bash
   python3 build.py
   ```

3. **Deploy** (auto on GitHub push)

---

## Custom Domain

1. Go to Cloudflare Pages → Your project → Custom domains
2. Add domain (e.g., `sable.example.com`)
3. Update DNS at your registrar

---

## Environment Variables

If needed for future features:
- Cloudflare Pages → Settings → Environment variables

---

## Troubleshooting

**Build fails?**
- Check Python version: `python3 --version` (need 3.11+)
- Test locally: `python3 build.py`

**Missing styles?**
- Check `_site/` was generated
- Verify static files copied

**404 on articles?**
- Check slug matches filename
- Verify Cloudflare build output: `_site`
