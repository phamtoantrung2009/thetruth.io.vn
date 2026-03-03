#!/usr/bin/env python3
"""Static site build pipeline with strict content validation."""

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
CONTENT_DIR = BASE_DIR / "content"
LAYOUTS_DIR = BASE_DIR / "layouts"
OUTPUT_DIR = BASE_DIR / "_site"
STATIC_DIR = BASE_DIR / "static"
SITE_URL = os.getenv("SITE_URL", "https://thetruth.io.vn").rstrip("/")

REQUIRED_FIELDS = ("title", "slug", "excerpt", "date")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)
UNRESOLVED_TEMPLATE_TOKEN_RE = re.compile(r"\{\{\s*[^{}]+\s*\}\}")

# Tension data (Vietnamese)
TENSIONS = [
    {"id": "thu-nhap-vs-tai-san", "name": "Thu Nháº­p vs. NghÃ¨o TÃ i Sáº£n", "mechanism": "LÆ°Æ¡ng khÃ´ng táº¡o tÃ i sáº£n", "tags": ["thu-nhap", "tai-san", "cuong-luong"]},
    {"id": "luong-vs-lam-phat", "name": "TÄƒng LÆ°Æ¡ng vs. Láº¡m PhÃ¡t", "mechanism": "LÆ°Æ¡ng khÃ´ng theo ká»‹p láº¡m phÃ¡t tÃ i sáº£n", "tags": ["thu-nhap", "lam-phat"]},
    {"id": "lam-viec-cap-von", "name": "LÃ m Viá»‡c ChÄƒm Chá»‰ vs. YÃªu Cáº§u Vá»‘n", "mechanism": "Quan há»‡ > ná»— lá»±c", "tags": ["cong-viec", "co-hoi"]},
    {"id": "nghia-vu-gia-dinh", "name": "NghÄ©a Vá»¥ Gia ÄÃ¬nh vs. Tá»± Chá»§", "mechanism": "Kinh táº¿ hiáº¿u nghÄ©a", "tags": ["gia-dinh", "nghia-vu"]},
    {"id": "hien-menh-cha-me", "name": "Hi Sinh Cá»§a Cha Máº¹ vs. Äá»n ÄÃ¡p", "mechanism": "Ná»£ liÃªn tháº¿ há»‡", "tags": ["gia-dinh", "hien-menh"]},
    {"id": "so-sanh-ban-be", "name": "So SÃ¡nh Báº¡n BÃ¨ vs. ÄÃ¬nh Trá»‡", "mechanism": "MÃ©o mÃ³ máº¡ng xÃ£ há»™i", "tags": ["xa-hoi", "so-sanh"]},
    {"id": "vi-tri-c-dinh", "name": "CÆ¡ Há»™i ÄÃ´ Thá»‹ vs. Káº¹t Gia ÄÃ¬nh", "mechanism": "Táº­p trung Ä‘Ã´ thá»‹", "tags": ["vi-tri", "di-cu"]},
    {"id": "on-dinh-ry", "name": "á»”n Äá»‹nh vs. Rá»§i Ro", "mechanism": "TÆ° duy sinh tá»“n", "tags": ["rui-ro", "an-toan"]},
    {"id": "so-huu-thue", "name": "Sá»Ÿ Há»¯u vs. ThuÃª Trá»", "mechanism": "Láº¡m phÃ¡t báº¥t Ä‘á»™ng sáº£n", "tags": ["nha-dat", "so-huu"]},
    {"id": "danh-du-chu-thuc", "name": "Danh Dá»± vs. ChÃ¢n Thá»±c", "mechanism": "Vá»‘n xÃ£ há»™i", "tags": ["ban-sac", "danh-du"]},
    {"id": "tre-trong-kinh-nghiem", "name": "TÃ´n Thá» Tuá»•i Tráº» vs. TrÃ­ Tuá»‡", "mechanism": "PhÃ¢n biá»‡t tuá»•i tÃ¡c", "tags": ["tuoi", "kinh-nghiem"]},
    {"id": "thong-tin-qua-tai", "name": "ThÃ´ng Tin QuÃ¡ Táº£i vs. RÃµ RÃ ng", "mechanism": "QuÃ¡ táº£i lá»i khuyÃªn", "tags": ["thong-tin", "loi-khuyen"]},
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
    return markdown.markdown(
        markdown_text,
        extensions=["extra", "sane_lists", "smarty"],
        output_format="html5",
    )


def build_tag_index(posts: list[Post]) -> dict[str, list[Post]]:
    tag_index: dict[str, list[Post]] = {}
    for post in posts:
        for tag in post.tags:
            tag_index.setdefault(tag, []).append(post)

    for tag_posts in tag_index.values():
        tag_posts.sort(key=lambda item: (item.published_on, item.slug), reverse=True)

    return tag_index


def get_tensions_preview() -> list[dict[str, Any]]:
    return TENSIONS[:6]


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


def build_site() -> None:
    posts = load_posts()
    tag_index = build_tag_index(posts)
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
                "related_tensions": related_tensions,
                "related_articles": related_articles,
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
                "posts": posts,
                "tensions": get_tensions_preview(),
                "site_url": SITE_URL,
            },
        ),
    )

    write_output(
        "phan-tich.html",
        render_template(env, "articles.html", {"articles": posts, "site_url": SITE_URL}),
    )

    write_output(
        "ten-xo.html",
        render_template(env, "tensions.html", {"tensions_list": TENSIONS, "site_url": SITE_URL}),
    )

    write_output("ve-he-thong.html", render_template(env, "about.html", {"site_url": SITE_URL}))

    # Tag pages
    for tag, tag_posts in tag_index.items():
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

    copy_static_assets()
    validate_generated_links()

    print(f"Built {len(posts)} posts to {OUTPUT_DIR}")


if __name__ == "__main__":
    try:
        build_site()
    except BuildError as exc:
        raise SystemExit(f"Build failed:\n{exc}")
