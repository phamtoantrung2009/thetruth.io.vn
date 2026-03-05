# Content Pipeline

## Overview

```
Write → Build → Deploy → CDN
```

## Step 1: Write Content

Create a new markdown file in `content/`:

```bash
content/new-article.md
```

### Frontmatter Format

```yaml
---
title: "Your Article Title"
slug: "your-article-slug"
excerpt: "A brief description (150 chars max)"
date: 2026-03-05
tags: [tag1, tag2, tag3]
---
```

### Content Format

Write in Markdown:

```markdown
## Section Heading

Your content here.

- Bullet point
- Another point

### Subsection

More content.
```

## Step 2: Verify Locally

```bash
# Build the site
python scripts/build.py

# Check for errors
# If successful, _site/ is generated
```

## Step 3: Commit and Push

```bash
git add content/new-article.md
git commit -m "Add: new article title"
git push origin main
```

## Step 4: Automatic Deployment

GitHub Actions will:
1. Run tests
2. Build the site
3. Deploy to Cloudflare Pages
4. CDN updates automatically

## Content Guidelines

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `title` | Yes | Article title |
| `slug` | Yes | URL-friendly identifier |
| `excerpt` | Yes | Brief description |
| `date` | Yes | Publication date |
| `tags` | Yes | Array of tags |

### Writing Style

- Write in Vietnamese or English
- Use clear, direct language
- Focus on systemic analysis
- Avoid motivational content

### Tag Conventions

Use consistent tags:

- `kinh-te-chinh-tri` - Political economy
- `tai-san` - Assets
- `thu-nhap` - Income
- `giao-duc` - Education
- `nam-tinh` - Masculinity
- `viec-lam` - Work

## Content Organization

### Directory Structure

```
content/
├── 2026-03-04-article-slug.md
├── 2026-03-02-article-slug.md
└── ...
```

### Sorting

Posts are sorted by date (newest first) in:
- Homepage
- RSS feed
- Sitemap

## Adding Images

Place images in a public CDN or use absolute URLs:

```markdown
![Description](https://example.com/image.png)
```

Note: Images are not hosted locally in this static system.

## Updating Content

1. Edit the markdown file
2. Rebuild: `python scripts/build.py`
3. Commit and push

## Deleting Content

1. Remove the markdown file
2. Rebuild
3. Commit and push

The old page will be removed from the site.

## Auto-Generated Artifacts

### Search Index

The search index (`search.json`) is auto-generated at build time.

Includes:
- Title
- Slug
- Excerpt
- Tags (lowercase)

No manual updates needed.

### RSS Feed

RSS feed (`rss.xml`) is auto-generated at build time.

Includes latest 20 posts.

### Sitemap

Sitemap (`sitemap.xml`) is auto-generated with:
- All post URLs
- Lastmod dates
- Priority and changefreq

No manual updates needed.

## Content Validation

The build system validates:
- Required frontmatter fields
- Valid date format
- Unique slugs
- Internal link validity
