#!/usr/bin/env python3
"""Static site build pipeline for knowledge base architecture.

Content model:
- type: post | pillar | framework | letter
- status: draft | publish
- Only files with status=publish are generated

URL structure:
- /post/{slug}
- /pillar/{slug}
- /framework/{slug}
- /letter/{slug}
"""

from __future__ import annotations

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

BASE_DIR = Path(__file__).parent.resolve()
POSTS_DIR = BASE_DIR / "posts"
LAYOUTS_DIR = BASE_DIR / "layouts"
OUTPUT_DIR = BASE_DIR / "_site"
STATIC_DIR = BASE_DIR / "static"
SITE_URL = os.getenv("SITE_URL", "https://thetruth.io.vn").rstrip("/")

# Valid content types
VALID_TYPES = ("post", "pillar", "framework", "letter")
VALID_STATUS = ("draft", "publish")

# Required front matter fields
REQUIRED_FIELDS = ("title", "slug", "type", "status", "excerpt", "date")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)
UNRESOLVED_TEMPLATE_TOKEN_RE = re.compile(r"\{\{\s*[^{}]+\s*\}\}")


class BuildError(RuntimeError):
    """Raised when content/template/output validation fails."""


@dataclass(frozen=True)
class Post:
    title: str
    slug: str
    content_type: str
    status: str
    excerpt: str
    published_on: date
    tags: tuple[str, ...]
    body_markdown: str
    source_path: Path

    @property
    def url_path(self) -> str:
        return f"/{self.content_type}/{self.slug}"

    @property
    def output_filename(self) -> str:
        return f"{self.content_type}/{self.slug}/index.html"

    @property
    def url(self) -> str:
        return f"{SITE_URL}{self.url_path}"


def parse_frontmatter(raw_content: str, source_path: Path) -> tuple[dict[str, Any], str]:
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


def validate_type(content_type: str, source_path: Path) -> str:
    normalized = content_type.lower().strip()
    if normalized not in VALID_TYPES:
        raise BuildError(
            f"{source_path}: invalid type '{content_type}'. Must be one of: {', '.join(VALID_TYPES)}"
        )
    return normalized


def validate_status(status: str, source_path: Path) -> str:
    normalized = status.lower().strip()
    if normalized not in VALID_STATUS:
        raise BuildError(
            f"{source_path}: invalid status '{status}'. Must be one of: {', '.join(VALID_STATUS)}"
        )
    return normalized


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
    content_type = validate_type(frontmatter["type"], source_path)
    status = validate_status(frontmatter["status"], source_path)
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
        content_type=content_type,
        status=status,
        excerpt=excerpt,
        published_on=published_on,
        tags=tags,
        body_markdown=body,
        source_path=source_path,
    )


def load_posts() -> list[Post]:
    if not POSTS_DIR.exists():
        raise BuildError(f"Missing posts directory: {POSTS_DIR}")

    markdown_files = sorted(POSTS_DIR.glob("*.md"))
    if not markdown_files:
        raise BuildError(f"No markdown posts found in {POSTS_DIR}")

    errors: list[str] = []
    posts: list[Post] = []

    for source_path in markdown_files:
        try:
            post = normalize_post(source_path)
            if post.status == "publish":
                posts.append(post)
        except BuildError as exc:
            errors.append(str(exc))

    if errors:
        raise BuildError("\n".join(errors))

    slug_to_path: dict[tuple[str, str], Path] = {}
    for post in posts:
        key = (post.content_type, post.slug)
        if key in slug_to_path:
            raise BuildError(
                f"Duplicate slug '{post.slug}' for type '{post.content_type}' in {slug_to_path[key]} and {post.source_path}"
            )
        slug_to_path[key] = post.source_path

    posts.sort(key=lambda item: (item.published_on, item.slug), reverse=True)
    return posts


def filter_by_type(posts: list[Post], content_type: str) -> list[Post]:
    return [p for p in posts if p.content_type == content_type]


def markdown_to_html(markdown_text: str) -> str:
    markdown_text = normalize_internal_links(markdown_text)
    return markdown.markdown(
        markdown_text,
        extensions=["extra", "sane_lists", "smarty"],
        output_format="html5",
    )


def normalize_internal_links(markdown_text: str) -> str:
    replacements = {
        "/tensions#": "/post#",
        "/tensions)": "/post)",
        "/articles#": "/post#",
        "/articles)": "/post)",
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


def get_related_posts(current_post: Post, all_posts: list[Post], limit: int = 3) -> list[Post]:
    if not current_post.tags:
        return []

    scored: list[tuple[int, Post]] = []
    current_tags = set(current_post.tags)

    for candidate in all_posts:
        if candidate.slug == current_post.slug and candidate.content_type == current_post.content_type:
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

    for file_path in OUTPUT_DIR.rglob("*"):
        if not file_path.is_file():
            continue

        rel_path = "/" + file_path.relative_to(OUTPUT_DIR).as_posix()
        existing_paths.add(rel_path)

        if rel_path.endswith("/index.html"):
            clean_path = rel_path[:-10]
            existing_paths.add(clean_path)

    broken_links: list[str] = []
    href_re = re.compile(r'href\s*=\s*"([^"]+)"')

    for html_file in html_files:
        text = html_file.read_text(encoding="utf-8")
        for href in href_re.findall(text):
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc:
                continue
            if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue

            path = parsed.path or "/"
            clean_path = path if not path.endswith(".html") else path[:-5]
            if clean_path not in existing_paths and path not in existing_paths:
                broken_links.append(f"{html_file.relative_to(OUTPUT_DIR)} -> {href}")

    if broken_links:
        details = "\n".join(sorted(set(broken_links)))
        raise BuildError(f"Broken internal links detected:\n{details}")


def build_site() -> None:
    posts = load_posts()
    tag_index = build_tag_index(posts)
    clean_output_dir()

    pillar_posts = filter_by_type(posts, "pillar")
    framework_posts = filter_by_type(posts, "framework")
    letter_posts = filter_by_type(posts, "letter")
    blog_posts = filter_by_type(posts, "post")

    latest_posts = blog_posts[:10]

    env = Environment(
        autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Render individual posts
    for post in posts:
        rendered_content = Markup(markdown_to_html(post.body_markdown))
        related_posts = get_related_posts(post, posts)

        html_text = render_template(
            env,
            "post.html",
            {
                "title": post.title,
                "excerpt": post.excerpt,
                "date": post.published_on.isoformat(),
                "tags": post.tags,
                "content": rendered_content,
                "url": post.url,
                "content_type": post.content_type,
                "related_posts": related_posts,
            },
        )
        write_output(post.output_filename, html_text)

    # Homepage
    write_output(
        "index.html",
        render_template(
            env,
            "index.html",
            {
                "pillars": pillar_posts,
                "frameworks": framework_posts,
                "letters": letter_posts,
                "latest_posts": latest_posts,
                "site_url": SITE_URL,
            },
        ),
    )

    # Archive pages
    if blog_posts:
        write_output(
            "post/index.html",
            render_template(
                env,
                "archive.html",
                {
                    "posts": blog_posts,
                    "content_type": "post",
                    "type_label": "Bai Phan Tich",
                    "site_url": SITE_URL,
                },
            ),
        )
        write_output(
            "post.html",
            render_template(env, "redirect.html", {"redirect_url": "/post/"}),
        )

    if pillar_posts:
        write_output(
            "pillar/index.html",
            render_template(
                env,
                "archive.html",
                {
                    "posts": pillar_posts,
                    "content_type": "pillar",
                    "type_label": "Tru Cot",
                    "site_url": SITE_URL,
                },
            ),
        )
        write_output(
            "pillar.html",
            render_template(env, "redirect.html", {"redirect_url": "/pillar/"}),
        )

    if framework_posts:
        write_output(
            "framework/index.html",
            render_template(
                env,
                "archive.html",
                {
                    "posts": framework_posts,
                    "content_type": "framework",
                    "type_label": "Khung",
                    "site_url": SITE_URL,
                },
            ),
        )
        write_output(
            "framework.html",
            render_template(env, "redirect.html", {"redirect_url": "/framework/"}),
        )

    if letter_posts:
        write_output(
            "letter/index.html",
            render_template(
                env,
                "archive.html",
                {
                    "posts": letter_posts,
                    "content_type": "letter",
                    "type_label": "Thu",
                    "site_url": SITE_URL,
                },
            ),
        )
        write_output(
            "letter.html",
            render_template(env, "redirect.html", {"redirect_url": "/letter/"}),
        )

    # Tag pages
    all_tags = sorted(set(tag_index.keys()))
    for tag in all_tags:
        tag_posts = tag_index.get(tag, [])
        write_output(
            f"tag/{tag}/index.html",
            render_template(
                env,
                "archive.html",
                {
                    "posts": tag_posts,
                    "content_type": "post",
                    "page_title": f"Tag: {tag}",
                    "type_label": "Bai viet",
                    "site_url": SITE_URL,
                },
            ),
        )

    copy_static_assets()

    # Legacy redirects
    legacy_redirects = [
        ("ten-xo.html", "/post"),
        ("phan-tich.html", "/post"),
        ("ve-he-thong.html", "/post"),
    ]
    for old_file, new_url in legacy_redirects:
        write_output(old_file, render_template(env, "redirect.html", {"redirect_url": new_url}))

    # validate_generated_links()

    print(f"Built {len(posts)} posts to {OUTPUT_DIR}")
    print(f"  - {len(pillar_posts)} pillars")
    print(f"  - {len(framework_posts)} frameworks")
    print(f"  - {len(letter_posts)} letters")
    print(f"  - {len(blog_posts)} posts")


if __name__ == "__main__":
    try:
        build_site()
    except BuildError as exc:
        raise SystemExit(f"Build failed:\n{exc}")
