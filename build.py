#!/usr/bin/env python3
"""
Minimal static site generator v2.
Supports multi-page generation: index, articles, tensions, about.
"""

import os
import re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.resolve()
CONTENT_DIR = BASE_DIR / "content"
LAYOUTS_DIR = BASE_DIR / "layouts"
OUTPUT_DIR = BASE_DIR / "_site"

OUTPUT_DIR.mkdir(exist_ok=True)

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

def md_to_html(text):
    """Simple markdown to HTML converter."""
    # Headers
    text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
    
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    
    # Links
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
    
    # Blockquotes
    text = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', text, flags=re.MULTILINE)
    
    # Horizontal rules
    text = re.sub(r'^---$', r'<hr>', text, flags=re.MULTILINE)
    
    # Lists
    text = re.sub(r'^- (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    text = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', text)
    
    # Paragraphs
    paragraphs = []
    for para in text.split('\n\n'):
        para = para.strip()
        if para and not para.startswith('<') and not para.startswith('#'):
            paragraphs.append(f'<p>{para}</p>')
        elif para:
            paragraphs.append(para)
    text = '\n'.join(paragraphs)
    
    return text

def parse_frontmatter(content):
    """Parse YAML frontmatter."""
    if not content.startswith('---'):
        return {}, content
    
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content
    
    frontmatter = parts[1]
    body = parts[2].strip()
    
    data = {}
    for line in frontmatter.split('\n'):
        if ': ' in line:
            key, value = line.split(': ', 1)
            data[key.strip()] = value.strip()
    
    return data, body

def get_tensions_html():
    """Generate tensions list for homepage."""
    items = []
    for t in TENSIONS[:6]:  # Top 6 for preview
        items.append(f'''<a href="/ten-xo#{t['id']}" class="tension-card">
            <h3>{t['name']}</h3>
            <p>{t['mechanism']}</p>
        </a>''')
    return '\n'.join(items)

def get_tensions_full_html():
    """Generate full tensions page."""
    items = []
    for t in TENSIONS:
        items.append(f'''<div class="tension" id="{t['id']}">
            <h2>{t['name']}</h2>
            <p class="mechanism"><strong>Cơ chế:</strong> {t['mechanism']}</p>
            <div class="tags">{" ".join([f'<span class="tag">{tag}</span>' for tag in t['tags']])}</div>
            <a href="/phan-tich?tag={t['tags'][0]}" class="related-link">Xem bài phân tích →</a>
        </div>''')
    return '\n'.join(items)

def get_related_links(tags):
    """Generate related links based on tags."""
    # Simple tag-based matching
    if not tags:
        return '<a href="/thu-nhap-vs-tai-san-vietnam">Thu Nhập vs Tài Sản — Ảo Tưởng</a>'
    
    # Find matching tensions
    matches = []
    for t in TENSIONS:
        if any(tag in t['tags'] for tag in tags):
            matches.append(f'<a href="/ten-xo#{t["id"]}">{t["name"]}</a>')
    
    if matches:
        return '\n'.join(matches[:3])
    return '<a href="/thu-nhap-vs-tai-san-vietnam">Thu Nhập vs Tài Sản — Ảo Tưởng</a>'

def build_site():
    """Build the static site."""
    print("Building site...")
    
    # Load templates
    post_template = (LAYOUTS_DIR / "post.html").read_text()
    index_template = (LAYOUTS_DIR / "index.html").read_text()
    tensions_template = (LAYOUTS_DIR / "tensions.html").read_text() if (LAYOUTS_DIR / "tensions.html").exists() else index_template
    about_template = (LAYOUTS_DIR / "about.html").read_text() if (LAYOUTS_DIR / "about.html").exists() else index_template
    articles_template = (LAYOUTS_DIR / "articles.html").read_text() if (LAYOUTS_DIR / "articles.html").exists() else index_template
    
    # Build articles index
    posts_html = []
    articles_list = []
    
    for md_file in sorted(CONTENT_DIR.glob("*.md")):
        print(f"  Processing: {md_file.name}")
        
        content = md_file.read_text(encoding='utf-8')
        data, body = parse_frontmatter(content)
        
        html_content = md_to_html(body)
        
        title = data.get('title', md_file.stem)
        date = data.get('date', '')
        excerpt = data.get('excerpt', '')
        slug = data.get('slug', md_file.stem)
        
        # Clean slug: strip quotes, backslashes, and whitespace
        slug = slug.strip().strip('"').strip("'").replace('\\', '')
        
        # Validate slug is safe for filesystem
        if not slug or slug.startswith('.'):
            slug = md_file.stem
        
        tags_raw = data.get('tags', '')
        
        # Process tags
        tags = []
        if tags_raw:
            if '[' in tags_raw:
                tags = re.findall(r'"([^"]+)"', tags_raw)
            else:
                tags = [tags_raw]
        
        tags_html = ''.join([f'<span class="tag">{t}</span>' for t in tags])
        
        # Build post HTML
        post_html = post_template
        post_html = post_html.replace('{{title}}', title)
        post_html = post_html.replace('{{excerpt}}', excerpt)
        post_html = post_html.replace('{{date}}', date)
        post_html = post_html.replace('{{tags}}', tags_html)
        post_html = post_html.replace('{{content}}', html_content)
        post_html = post_html.replace('{{url}}', f'/{slug}')
        post_html = post_html.replace('{{related}}', get_related_links(tags))
        
        (OUTPUT_DIR / f"{slug}.html").write_text(post_html, encoding='utf-8')
        
        # Add to index
        posts_html.append(f'''<li>
            <a href="/{slug}">
                <h2>{title}</h2>
                <p class="excerpt">{excerpt}</p>
                <div class="meta"><time>{date}</time> {tags_html}</div>
            </a>
        </li>''')
        
        # Add to articles list
        articles_list.append(f'''<li>
            <a href="/{slug}">
                <h2>{title}</h2>
                <p class="excerpt">{excerpt}</p>
                <div class="meta"><time>{date}</time> {tags_html}</div>
            </a>
        </li>''')
    
    # Build homepage
    index_html = index_template
    index_html = index_html.replace('{{posts}}', '\n'.join(posts_html))
    index_html = index_html.replace('{{tensions}}', get_tensions_html())
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding='utf-8')
    
    # Build articles index page
    articles_html = articles_template
    articles_html = articles_html.replace('{{articles}}', '\n'.join(articles_list))
    (OUTPUT_DIR / "articles.html").write_text(articles_html, encoding='utf-8')
    
    # Build tensions page
    tensions_html = tensions_template
    tensions_html = tensions_html.replace('{{tensions_list}}', get_tensions_full_html())
    (OUTPUT_DIR / "tensions.html").write_text(tensions_html, encoding='utf-8')
    
    # Build about page
    about_html = about_template
    (OUTPUT_DIR / "about.html").write_text(about_html, encoding='utf-8')
    
    # Copy static files
    static_dir = BASE_DIR / "static"
    if static_dir.exists():
        for f in static_dir.glob("*"):
            if f.is_file():
                import shutil
                shutil.copy(f, OUTPUT_DIR / f.name)
    
    print(f"✓ Built to {OUTPUT_DIR}")
    print(f"  {len(posts_html)} articles")

if __name__ == "__main__":
    build_site()
