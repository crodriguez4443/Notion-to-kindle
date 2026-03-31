"""
Convert a list of Notion blocks to an EPUB file.

Flow:
  1. blocks_to_html()  - turn Notion block dicts into an HTML string
  2. build_epub()      - wrap the HTML in an EPUB3 container via ebooklib
"""

import logging
import os
import re
import uuid
from typing import Any

from ebooklib import epub

logger = logging.getLogger(__name__)

# Minimal CSS that renders well on e-ink Kindle screens
_KINDLE_CSS = """
body {
    font-family: Georgia, serif;
    font-size: 1em;
    line-height: 1.6;
    margin: 1em;
    color: #000;
}
h1, h2, h3 { margin-top: 1.4em; margin-bottom: 0.4em; }
h1 { font-size: 1.6em; }
h2 { font-size: 1.35em; }
h3 { font-size: 1.15em; }
p  { margin: 0.6em 0; }
pre, code {
    font-family: "Courier New", monospace;
    font-size: 0.85em;
    background: #f4f4f4;
    border-radius: 3px;
    padding: 0.1em 0.3em;
}
pre { padding: 0.8em; overflow-x: auto; white-space: pre-wrap; }
blockquote {
    border-left: 3px solid #ccc;
    margin-left: 0;
    padding-left: 1em;
    color: #555;
}
img { max-width: 100%; height: auto; }
hr  { border: none; border-top: 1px solid #ccc; margin: 1.5em 0; }
a   { color: #1a0dab; }
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_epub(
    title: str,
    blocks: list[dict[str, Any]],
    page_url: str,
    output_path: str,
) -> str:
    """
    Convert Notion blocks into an EPUB file at output_path.

    Args:
        title:       Article title (used as EPUB title + filename hint).
        blocks:      List of Notion block dicts from notion_fetcher.
        page_url:    Original Notion page URL (added as metadata).
        output_path: Full path where the .epub file should be written.

    Returns:
        The output_path on success.
    """
    html_body = blocks_to_html(blocks)
    _write_epub(title, html_body, page_url, output_path)
    logger.info("EPUB written to %s", output_path)
    return output_path


def blocks_to_html(blocks: list[dict[str, Any]]) -> str:
    """Convert a list of Notion block dicts to an HTML string."""
    parts: list[str] = []
    i = 0
    while i < len(blocks):
        block = blocks[i]
        block_type = block.get("type", "")

        if block_type == "bulleted_list_item":
            items, i = _collect_list_items(blocks, i, "bulleted_list_item")
            parts.append(f"<ul>\n{items}</ul>")
            continue

        if block_type == "numbered_list_item":
            items, i = _collect_list_items(blocks, i, "numbered_list_item")
            parts.append(f"<ol>\n{items}</ol>")
            continue

        parts.append(_block_to_html(block))
        i += 1

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Block rendering
# ---------------------------------------------------------------------------

def _block_to_html(block: dict[str, Any]) -> str:
    t = block.get("type", "")
    data = block.get(t, {})

    if t == "paragraph":
        text = _rich_text_to_html(data.get("rich_text", []))
        return f"<p>{text}</p>" if text.strip() else "<br/>"

    if t in ("heading_1", "heading_2", "heading_3"):
        level = t[-1]
        text = _rich_text_to_html(data.get("rich_text", []))
        return f"<h{level}>{text}</h{level}>"

    if t == "bulleted_list_item":
        text = _rich_text_to_html(data.get("rich_text", []))
        children_html = _render_children(block)
        return f"<li>{text}{children_html}</li>"

    if t == "numbered_list_item":
        text = _rich_text_to_html(data.get("rich_text", []))
        children_html = _render_children(block)
        return f"<li>{text}{children_html}</li>"

    if t == "quote":
        text = _rich_text_to_html(data.get("rich_text", []))
        return f"<blockquote><p>{text}</p></blockquote>"

    if t == "callout":
        text = _rich_text_to_html(data.get("rich_text", []))
        icon = data.get("icon", {})
        emoji = icon.get("emoji", "") if icon.get("type") == "emoji" else ""
        return f"<blockquote><p>{emoji} {text}</p></blockquote>"

    if t == "code":
        text = _plain_text(data.get("rich_text", []))
        lang = data.get("language", "")
        escaped = _escape_html(text)
        return f'<pre><code class="language-{lang}">{escaped}</code></pre>'

    if t == "image":
        url = _image_url(data)
        caption = _rich_text_to_html(data.get("caption", []))
        cap_html = f"<figcaption>{caption}</figcaption>" if caption else ""
        return f"<figure><img src=\"{url}\" alt=\"{_escape_html(caption)}\"/>{cap_html}</figure>"

    if t == "divider":
        return "<hr/>"

    if t == "to_do":
        checked = "checked" if data.get("checked") else ""
        text = _rich_text_to_html(data.get("rich_text", []))
        return f'<p><input type="checkbox" {checked} disabled/> {text}</p>'

    if t == "toggle":
        text = _rich_text_to_html(data.get("rich_text", []))
        children_html = _render_children(block)
        return f"<details><summary>{text}</summary>{children_html}</details>"

    if t == "embed" or t == "bookmark":
        url = data.get("url", "")
        caption = _rich_text_to_html(data.get("caption", []))
        label = caption or url
        return f'<p><a href="{url}">{label}</a></p>'

    if t == "link_preview":
        url = data.get("url", "")
        return f'<p><a href="{url}">{url}</a></p>'

    if t == "video":
        url = _image_url(data)  # same structure as image
        return f'<p>[Video: <a href="{url}">{url}</a>]</p>'

    if t == "file":
        url = _image_url(data)
        return f'<p>[File: <a href="{url}">{url}</a>]</p>'

    if t == "pdf":
        url = _image_url(data)
        return f'<p>[PDF: <a href="{url}">{url}</a>]</p>'

    if t == "table_of_contents":
        return ""  # skip; EPUB has its own TOC

    if t == "column_list":
        columns = block.get("children", [])
        col_html = "".join(
            f'<div style="display:inline-block;vertical-align:top;width:{100 // max(len(columns), 1)}%;">'
            f'{blocks_to_html(col.get("children", []))}</div>'
            for col in columns
        )
        return f'<div style="overflow:hidden;">{col_html}</div>'

    # Fallback for unsupported block types: try to extract any text
    rich_text = data.get("rich_text", [])
    if rich_text:
        return f"<p>{_rich_text_to_html(rich_text)}</p>"

    return ""


def _collect_list_items(
    blocks: list[dict], start: int, list_type: str
) -> tuple[str, int]:
    """Collect consecutive same-type list items and return their HTML + next index."""
    items_html = ""
    i = start
    while i < len(blocks) and blocks[i].get("type") == list_type:
        items_html += _block_to_html(blocks[i]) + "\n"
        i += 1
    return items_html, i


def _render_children(block: dict[str, Any]) -> str:
    children = block.get("children", [])
    if not children:
        return ""
    return f"<ul>{blocks_to_html(children)}</ul>"


# ---------------------------------------------------------------------------
# Rich text helpers
# ---------------------------------------------------------------------------

def _rich_text_to_html(rich_text: list[dict]) -> str:
    parts = []
    for rt in rich_text:
        text = _escape_html(rt.get("plain_text", ""))
        annotations = rt.get("annotations", {})
        href = (rt.get("href") or "")

        if annotations.get("bold"):
            text = f"<strong>{text}</strong>"
        if annotations.get("italic"):
            text = f"<em>{text}</em>"
        if annotations.get("code"):
            text = f"<code>{text}</code>"
        if annotations.get("strikethrough"):
            text = f"<s>{text}</s>"
        if annotations.get("underline"):
            text = f"<u>{text}</u>"
        if href:
            text = f'<a href="{href}">{text}</a>'

        parts.append(text)
    return "".join(parts)


def _plain_text(rich_text: list[dict]) -> str:
    return "".join(rt.get("plain_text", "") for rt in rich_text)


def _image_url(data: dict) -> str:
    if data.get("type") == "external":
        return data.get("external", {}).get("url", "")
    return data.get("file", {}).get("url", "")


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# EPUB packaging
# ---------------------------------------------------------------------------

def _write_epub(title: str, html_body: str, source_url: str, output_path: str) -> None:
    book = epub.EpubBook()
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(title)
    book.set_language("en")
    if source_url:
        book.add_metadata("DC", "source", source_url)

    # CSS
    style = epub.EpubItem(
        uid="style",
        file_name="style.css",
        media_type="text/css",
        content=_KINDLE_CSS,
    )
    book.add_item(style)

    # Main content chapter
    safe_title = re.sub(r"[^\w\s-]", "", title)[:80]
    chapter = epub.EpubHtml(
        title=safe_title,
        file_name="content.xhtml",
        lang="en",
    )
    chapter.content = f"""<html>
<head>
  <title>{_escape_html(title)}</title>
  <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
  <h1>{_escape_html(title)}</h1>
  {html_body}
</body>
</html>""".encode("utf-8")
    chapter.add_item(style)
    book.add_item(chapter)

    # Navigation
    book.toc = [epub.Link("content.xhtml", title, "content")]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    epub.write_epub(output_path, book)
