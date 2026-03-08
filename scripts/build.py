#!/usr/bin/env python3
"""Static site build pipeline with strict content validation."""

from __future__ import annotations

import math
import os
import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import markdown
import yaml
from jinja2 import Environment, StrictUndefined, select_autoescape
from markupsafe import Markup

BASE_DIR = Path(__file__).parent.parent.resolve()
CONTENT_DIR = BASE_DIR / "content"
LAYOUTS_DIR = BASE_DIR / "layouts"
OUTPUT_DIR = BASE_DIR / "_site"
STATIC_DIR = BASE_DIR / "static"
SITE_URL = os.getenv("SITE_URL", "https://thetruth.io.vn").rstrip("/")

REQUIRED_FIELDS = ("title", "slug", "excerpt", "date")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)
UNRESOLVED_TEMPLATE_TOKEN_RE = re.compile(r"\{\{\s*[^{}]+\s*\}\}")
POSTS_PER_PAGE = 12

# Tension data (Vietnamese)
TENSIONS = [
    {"id": "thu-nhap-vs-tai-san", "name": "Thu Nhập vs. Nghèo Tài Sản", "mechanism": "Lương không tạo tài sản", "tags": ["thu-nhap", "tai-san", "cuong-luong"]},
    {"id": "luong-vs-lam-phat", "name": "Tăng Lương vs. Lạm Phát", "mechanism": "Lương không theo kịp lạm phát tài sản", "tags": ["thu-nhap", "lam-phat"]},
    {"id": "lam-viec-cap-von", "name": "Làm Việc Chăm Chỉ vs. Yêu Cầu Vốn", "mechanism": "Quan hệ > nỗ lực", "tags": ["cong-viec", "co-hoi"]},
    {"id": "nghia-vu-gia-dinh", "name": "Nghĩa Vụ Gia Đình vs. Tự Chủ", "mechanism": "Kinh tế hiếu nghĩa", "tags": ["gia-dinh", "nghia-vu"]},
    {"id": "hien-menh-cha-me", "name": "Hi Sinh Của Cha Mẹ vs. Đền Đáp", "mechanism": "Nợ liên thế hệ", "tags": ["gia-dinh", "hien-menh"]},
    {"id": "so-sanh-ban-be", "name": "So Sánh Bạn Bè vs. Đình Trệ", "mechanism": "Méo mó mạng xã hội", "tags": ["xa-hoi", "so-sanh"]},
    {"id": "vi-tri-c-dinh", "name": "Cơ Hội Đô Thị vs. Kẹt Gia Đình", "mechanism": "Tập trung đô thị", "tags": ["vi-tri", "di-cu"]},
    {"id": "on-dinh-ry", "name": "Ổn Định vs. Rủi Ro", "mechanism": "Tư duy sinh tồn", "tags": ["rui-ro", "an-toan"]},
    {"id": "so-huu-thue", "name": "Sở Hữu vs. Thuê Trọ", "mechanism": "Lạm phát bất động sản", "tags": ["nha-dat", "so-huu"]},
    {"id": "danh-du-chu-thuc", "name": "Danh Dự vs. Chân Thực", "mechanism": "Vốn xã hội", "tags": ["ban-sac", "danh-du"]},
    {"id": "tre-trong-kinh-nghiem", "name": "Tôn Thờ Tuổi Trẻ vs. Trí Tuệ", "mechanism": "Phân biệt tuổi tác", "tags": ["tuoi", "kinh-nghiem"]},
    {"id": "thong-tin-qua-tai", "name": "Thông Tin Quá Tải vs. Rõ Ràng", "mechanism": "Quá tải lời khuyên", "tags": ["thong-tin", "loi-khuyen"]},
]


class BuildError(RuntimeError):
    """Raised when content/template/output validation fails."""


@dataclass(frozen=True)
class Post:
    title: str
    slug: str
    excerpt: str
    published_on: date
    tags: tuple[str, ...]
    body_markdown: str
    source_path: Path

    @property
    def output_filename(self) -> str:
        return f"{self.slug}.html"

    @property
    def route(self) -> str:
        return f"/{self.output_filename}"

    @property
    def url(self) -> str:
        return f"{SITE_URL}{self.route}"


def parse_frontmatter(raw_content: str, source_path: Path) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter and markdown body."""
    match = FRONTMATTER_RE.match(raw_content)
    if not match:
        raise BuildError(f"{source_path}: missing valid YAML frontmatter block")

    frontmatter_raw, body = match.group(1), match.group(2)
    try:
        parsed = yaml.safe_load(frontmatter_raw) or {}
    except yaml.YAMLError as exc:
        raise BuildError(f"{source_path}: invalid YAML frontmatter: {exc}") from exc

    if not isinstance(parsed, dict):
        raise BuildError(f"{source_path}: frontmatter must parse to a key/value mapping")

    return parsed, body.strip()


def normalize_tags(raw_tags: Any, source_path: Path) -> tuple[str, ...]:
    if raw_tags is None:
        return tuple()

    if isinstance(raw_tags, str):
        candidate_tags = [part.strip() for part in raw_tags.split(",") if part.strip()]
    elif isinstance(raw_tags, list):
        candidate_tags = []
        for item in raw_tags:
            if not isinstance(item, str):
                raise BuildError(f"{source_path}: each tag must be a string")
            cleaned = item.strip()
            if cleaned:
                candidate_tags.append(cleaned)
    else:
        raise BuildError(f"{source_path}: tags must be a string or list of strings")

    return tuple(candidate_tags)


def parse_iso_date(raw_date: Any, source_path: Path) -> date:
    if isinstance(raw_date, date):
        return raw_date

    if not isinstance(raw_date, str):
        raise BuildError(f"{source_path}: date must be a string in YYYY-MM-DD format")

    candidate = raw_date.strip()
    try:
        return date.fromisoformat(candidate)
    except ValueError as exc:
        raise BuildError(f"{source_path}: invalid date '{raw_date}', expected YYYY-MM-DD") from exc


def normalize_post(source_path: Path) -> Post:
    raw_content = source_path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(raw_content, source_path)

    missing = [field for field in REQUIRED_FIELDS if field not in frontmatter]
    if missing:
        raise BuildError(f"{source_path}: missing required frontmatter fields: {', '.join(missing)}")

    title = str(frontmatter["title"]).strip()
    slug = str(frontmatter["slug"]).strip().strip("\"'")
    excerpt = str(frontmatter["excerpt"]).strip()

    if not title:
        raise BuildError(f"{source_path}: title cannot be empty")
    if not excerpt:
        raise BuildError(f"{source_path}: excerpt cannot be empty")

    if not SLUG_PATTERN.fullmatch(slug):
        raise BuildError(
            f"{source_path}: invalid slug '{slug}'. Use lowercase letters, numbers, and hyphens only"
        )

    published_on = parse_iso_date(frontmatter["date"], source_path)
    tags = normalize_tags(frontmatter.get("tags"), source_path)

    return Post(
        title=title,
        slug=slug,
        excerpt=excerpt,
        published_on=published_on,
        tags=tags,
        body_markdown=body,
        source_path=source_path,
    )


def load_posts() -> list[Post]:
    if not CONTENT_DIR.exists():
        raise BuildError(f"Missing content directory: {CONTENT_DIR}")

    markdown_files = sorted(CONTENT_DIR.glob("*.md"))
    if not markdown_files:
        raise BuildError(f"No markdown posts found in {CONTENT_DIR}")

    errors: list[str] = []
    posts: list[Post] = []

    for source_path in markdown_files:
        try:
            posts.append(normalize_post(source_path))
        except BuildError as exc:
            errors.append(str(exc))

    if errors:
        raise BuildError("\n".join(errors))

    slug_to_path: dict[str, Path] = {}
    for post in posts:
        if post.slug in slug_to_path:
            raise BuildError(
                f"Duplicate slug '{post.slug}' in {slug_to_path[post.slug]} and {post.source_path}"
            )
        slug_to_path[post.slug] = post.source_path

    posts.sort(key=lambda item: (item.published_on, item.slug), reverse=True)
    return posts


def markdown_to_html(markdown_text: str) -> str:
    markdown_text = normalize_internal_links(markdown_text)
    return markdown.markdown(
        markdown_text,
        extensions=["extra", "sane_lists", "smarty"],
        output_format="html5",
    )


def normalize_internal_links(markdown_text: str) -> str:
    """Rewrite legacy internal routes to current paths before markdown rendering."""
    replacements = {
        "/tensions#": "/ten-xo#",
        "/tensions)": "/ten-xo)",
        "/articles#": "/phan-tich#",
        "/articles)": "/phan-tich)",
    }
    normalized = markdown_text
    for legacy, current in replacements.items():
        normalized = normalized.replace(legacy, current)
    return normalized


def build_tag_index(posts: list[Post]) -> dict[str, list[Post]]:
    tag_index: dict[str, list[Post]] = {}
    for post in posts:
        for tag in post.tags:
            tag_index.setdefault(tag, []).append(post)

    for tag_posts in tag_index.values():
        tag_posts.sort(key=lambda item: (item.published_on, item.slug), reverse=True)

    return tag_index


def get_all_tension_tags() -> set[str]:
    tags: set[str] = set()
    for tension in TENSIONS:
        tags.update(tension["tags"])
    return tags


def get_tensions_preview() -> list[dict[str, Any]]:
    return TENSIONS[:6]


def paginate_posts(posts: list[Post], per_page: int = POSTS_PER_PAGE):
    """Yield (page_number, page_posts, total_pages) tuples (1-indexed)."""
    total_pages = max(1, math.ceil(len(posts) / per_page))
    for page_num in range(1, total_pages + 1):
        start = (page_num - 1) * per_page
        yield page_num, posts[start:start + per_page], total_pages

def get_related_tensions(tags: tuple[str, ...]) -> list[dict[str, str]]:
    if not tags:
        return []

    related: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    for tension in TENSIONS:
        if tension["id"] in seen_ids:
            continue

        if any(tag in tension["tags"] for tag in tags):
            related.append({"name": tension["name"], "href": f"/ten-xo#{tension['id']}"})
            seen_ids.add(tension["id"])

        if len(related) == 3:
            break

    return related


def get_related_articles(current_post: Post, all_posts: list[Post], limit: int = 3) -> list[Post]:
    if not current_post.tags:
        return []

    scored: list[tuple[int, Post]] = []
    current_tags = set(current_post.tags)

    for candidate in all_posts:
        if candidate.slug == current_post.slug:
            continue

        shared = len(current_tags.intersection(candidate.tags))
        if shared > 0:
            scored.append((shared, candidate))

    scored.sort(key=lambda item: (item[0], item[1].published_on, item[1].slug), reverse=True)
    return [post for _, post in scored[:limit]]


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def copy_static_assets() -> None:
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, OUTPUT_DIR, dirs_exist_ok=True)


def render_template(env: Environment, template_name: str, context: dict[str, Any]) -> str:
    template_path = LAYOUTS_DIR / template_name
    if not template_path.exists():
        raise BuildError(f"Missing template: {template_path}")

    template_source = template_path.read_text(encoding="utf-8")
    template = env.from_string(template_source)
    rendered = template.render(**context)

    unresolved = UNRESOLVED_TEMPLATE_TOKEN_RE.findall(rendered)
    if unresolved:
        raise BuildError(
            f"Template '{template_name}' rendered with unresolved tokens: {', '.join(sorted(set(unresolved)))}"
        )

    return rendered


def write_output(relative_path: str, html_text: str) -> None:
    output_path = OUTPUT_DIR / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")


def validate_generated_links() -> None:
    html_files = list(OUTPUT_DIR.rglob("*.html"))
    existing_paths: set[str] = set()
    aliases: set[str] = set()

    for file_path in OUTPUT_DIR.rglob("*"):
        if not file_path.is_file():
            continue

        rel_path = "/" + file_path.relative_to(OUTPUT_DIR).as_posix()
        existing_paths.add(rel_path)

        if rel_path.endswith(".html"):
            aliases.add(rel_path)
            if rel_path == "/index.html":
                aliases.add("/")
            else:
                aliases.add(rel_path[:-5])

    broken_links: list[str] = []
    href_re = re.compile(r'href\s*=\s*"([^"]+)"')

    for html_file in html_files:
        text = html_file.read_text(encoding="utf-8")
        # Remove script tag contents to avoid false positives from JS
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        
        for href in href_re.findall(text):
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc:
                continue
            if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue

            path = parsed.path or "/"
            if path not in aliases and path not in existing_paths:
                broken_links.append(f"{html_file.relative_to(OUTPUT_DIR)} -> {href}")

    if broken_links:
        details = "\n".join(sorted(set(broken_links)))
        raise BuildError(f"Broken internal links detected:\n{details}")


def calculate_reading_time(markdown_text: str) -> int:
    """Calculate reading time in minutes (approx 200 words/min)."""
    word_count = len(markdown_text.split())
    return max(1, round(word_count / 200))


def generate_sitemap(posts: list[Post]) -> str:
    """Generate sitemap.xml with lastmod dates."""
    urls = []
    for p in posts:
        urls.append(f"""<url>
    <loc>{p.url}</loc>
    <lastmod>{p.published_on.isoformat()}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
</url>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""


def generate_robots_txt() -> str:
    """Generate robots.txt."""
    return f"""User-agent: *
Allow: /
Sitemap: {SITE_URL}/sitemap.xml
"""


def generate_posts_json(posts: list[Post]) -> str:
    """Generate posts.json for AI pipeline."""
    import json
    from datetime import datetime
    return json.dumps({
        "posts": [
            {
                "title": p.title,
                "slug": p.slug,
                "excerpt": p.excerpt,
                "date": p.published_on.isoformat(),
                "url": p.url,
                "tags": list(p.tags),
                "reading_time": calculate_reading_time(p.body_markdown),
            }
            for p in posts
        ],
        "generated_at": datetime.now().isoformat()
    }, indent=2, ensure_ascii=False)


def generate_site_manifest(posts: list[Post]) -> str:
    """Generate site-manifest.json."""
    import json
    from datetime import datetime
    all_tags = sorted(set(tag for p in posts for tag in p.tags))
    return json.dumps({
        "site": SITE_URL.replace("https://", ""),
        "generated_at": datetime.now().isoformat(),
        "posts_count": len(posts),
        "tags": list(all_tags),
        "latest_posts": [
            {"slug": p.slug, "date": p.published_on.isoformat(), "title": p.title}
            for p in sorted(posts, key=lambda x: x.published_on, reverse=True)[:5]
        ],
        "tensions": [{"id": t["id"], "name": t["name"]} for t in TENSIONS]
    }, indent=2, ensure_ascii=False)


def generate_search_index(posts: list[Post]) -> str:
    """Generate search.json with lowercase tags."""
    import json
    return json.dumps({
        "posts": [
            {"t": p.title, "s": p.slug, "e": p.excerpt, "g": [t.lower() for t in p.tags]}
            for p in posts
        ]
    }, ensure_ascii=False)


def generate_rss_feed(posts: list[Post]) -> str:
    """Generate RSS 2.0 feed."""
    from datetime import datetime
    items = []
    for p in posts[:20]:  # Latest 20 posts
        items.append(f"""<item>
    <title><![CDATA[{p.title}]]></title>
    <link>{p.url}</link>
    <description><![CDATA[{p.excerpt}]]></description>
    <pubDate>{p.published_on.isoformat()}</pubDate>
    <guid>{p.url}</guid>
</item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
    <title>THE TRUTH</title>
    <link>{SITE_URL}</link>
    <description>Sự thật về thực tại Việt Nam</description>
    <language>vi</language>
    <atom:link href="{SITE_URL}/rss.xml" rel="self" type="application/rss+xml"/>
    <lastBuildDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')}</lastBuildDate>
{chr(10).join(items)}
</channel>
</rss>"""


OG_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <style>
    body {{
      background: #0d0d0d;
      color: #e5e5e5;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 80px;
      width: 1200px;
      height: 630px;
      margin: 0;
      box-sizing: border-box;
    }}
    h1 {{
      font-size: 52px;
      line-height: 1.2;
      margin: 0;
      max-width: 1000px;
    }}
    .brand {{
      color: #e63946;
      font-size: 28px;
      font-weight: 700;
      letter-spacing: 0.1em;
    }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="brand">THE TRUTH</div>
</body>
</html>"""


async def generate_og_images(posts: list[Post]) -> None:
    """Generate OG images using Playwright (single browser session)."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Playwright not installed. Skipping OG image generation.")
        return

    og_dir = OUTPUT_DIR / "og"
    og_dir.mkdir(parents=True, exist_ok=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            
            for post in posts:
                html = OG_TEMPLATE.format(title=post.title[:80])  # Truncate for safety
                
                page = await browser.new_page(viewport={"width": 1200, "height": 630})
                await page.set_content(html)
                await page.wait_for_timeout(50)  # Wait for render
                await page.screenshot(path=str(og_dir / f"{post.slug}.png"), type="png")
                await page.close()
            
            await browser.close()
            print(f"Generated {len(posts)} OG images")
    except Exception as e:
        print(f"OG image generation skipped: {e}")
        print("To enable OG images, run: playwright install chromium")


def build_site() -> None:
    posts = load_posts()
    tag_index = build_tag_index(posts)
    all_tension_tags = get_all_tension_tags()
    clean_output_dir()

    env = Environment(
        autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Render individual posts
    for post in posts:
        rendered_content = Markup(markdown_to_html(post.body_markdown))
        related_tensions = get_related_tensions(post.tags)
        related_articles = get_related_articles(post, posts)
        reading_time = calculate_reading_time(post.body_markdown)

        html_text = render_template(
            env,
            "post.html",
            {
                "title": post.title,
                "slug": post.slug,
                "excerpt": post.excerpt,
                "date": post.published_on.isoformat(),
                "tags": post.tags,
                "content": rendered_content,
                "url": post.url,
                "related_tensions": related_tensions,
                "related_articles": related_articles,
                "reading_time": reading_time,
            },
        )
        write_output(post.output_filename, html_text)

    # Core pages
    write_output(
        "index.html",
        render_template(
            env,
            "index.html",
            {
                "posts": posts[:6],  # Show latest 6 on homepage
                "tensions": get_tensions_preview(),
                "site_url": SITE_URL,
            },
        ),
    )

    # Paginated articles archive
    for page_num, page_posts, total_pages in paginate_posts(posts):
        out_path = "phan-tich.html" if page_num == 1 else f"phan-tich/page/{page_num}.html"
        canonical = f"{SITE_URL}/phan-tich" if page_num == 1 else f"{SITE_URL}/phan-tich/page/{page_num}"
        prev_url = None
        if page_num > 1:
            prev_url = f"{SITE_URL}/phan-tich" if page_num == 2 else f"{SITE_URL}/phan-tich/page/{page_num - 1}"
        next_url = f"{SITE_URL}/phan-tich/page/{page_num + 1}" if page_num < total_pages else None
        write_output(
            out_path,
            render_template(env, "articles.html", {
                "articles": page_posts,
                "site_url": SITE_URL,
                "current_page": page_num,
                "total_pages": total_pages,
                "base_path": "/phan-tich",
                "canonical": canonical,
                "prev_url": prev_url,
                "next_url": next_url,
            }),
        )

    write_output(
        "ten-xo.html",
        render_template(env, "tensions.html", {"tensions_list": TENSIONS, "site_url": SITE_URL}),
    )

    write_output("ve-he-thong.html", render_template(env, "about.html", {"site_url": SITE_URL}))

    # Tag pages
    all_tags = sorted(set(tag_index.keys()).union(all_tension_tags))
    for tag in all_tags:
        tag_posts = tag_index.get(tag, [])
        write_output(
            f"tags/{tag}.html",
            render_template(
                env,
                "articles.html",
                {
                    "articles": tag_posts,
                    "site_url": SITE_URL,
                    "page_title": f"Tag: {tag}",
                    "page_subtitle": f"Bai phan tich co tag '{tag}'",
                },
            ),
        )

    # Generate sitemap, manifest, search index, RSS
    write_output("sitemap.xml", generate_sitemap(posts))
    write_output("robots.txt", generate_robots_txt())
    write_output("posts.json", generate_posts_json(posts))
    write_output("site-manifest.json", generate_site_manifest(posts))
    write_output("search.json", generate_search_index(posts))
    write_output("rss.xml", generate_rss_feed(posts))

    # Generate OG images
    import asyncio
    asyncio.run(generate_og_images(posts))

    copy_static_assets()
    validate_generated_links()

    print(f"Built {len(posts)} posts to {OUTPUT_DIR}")


if __name__ == "__main__":
    try:
        build_site()
    except BuildError as exc:
        raise SystemExit(f"Build failed:\n{exc}")
