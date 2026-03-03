from pathlib import Path

import pytest

import build


def write_post(path: Path, *, title: str, slug: str, excerpt: str, date: str, tags: str = "- test") -> None:
    path.write_text(
        (
            "---\n"
            f"title: \"{title}\"\n"
            f"slug: \"{slug}\"\n"
            f"excerpt: \"{excerpt}\"\n"
            f"date: \"{date}\"\n"
            f"tags:\n{tags}\n"
            "---\n\n"
            "Body"
        ),
        encoding="utf-8",
    )


def test_normalize_post_requires_frontmatter(tmp_path: Path) -> None:
    source = tmp_path / "post.md"
    source.write_text("# No frontmatter", encoding="utf-8")

    with pytest.raises(build.BuildError, match="missing valid YAML frontmatter"):
        build.normalize_post(source)


def test_normalize_post_rejects_invalid_slug(tmp_path: Path) -> None:
    source = tmp_path / "post.md"
    write_post(
        source,
        title="Example",
        slug="Invalid/Slug",
        excerpt="Example excerpt",
        date="2026-03-01",
    )

    with pytest.raises(build.BuildError, match="invalid slug"):
        build.normalize_post(source)


def test_load_posts_sorts_by_date_and_detects_duplicates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    monkeypatch.setattr(build, "CONTENT_DIR", content_dir)

    write_post(
        content_dir / "a.md",
        title="Older",
        slug="older-post",
        excerpt="older",
        date="2026-03-01",
    )
    write_post(
        content_dir / "b.md",
        title="Newer",
        slug="newer-post",
        excerpt="newer",
        date="2026-03-02",
    )

    posts = build.load_posts()
    assert [post.slug for post in posts] == ["newer-post", "older-post"]

    write_post(
        content_dir / "c.md",
        title="Duplicate",
        slug="older-post",
        excerpt="dup",
        date="2026-03-03",
    )

    with pytest.raises(build.BuildError, match="Duplicate slug"):
        build.load_posts()
