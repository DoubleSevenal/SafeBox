from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QTextDocument

from safebox.core.record_sorting import imported_note_category_from_suffix


@dataclass(frozen=True, slots=True)
class ImportedNote:
    title: str
    html: str
    category: str
    source: str


def note_html_from_imported_text(text: str, suffix: str) -> str:
    document = QTextDocument()
    normalized_suffix = suffix.casefold()
    if normalized_suffix in {".md", ".markdown"}:
        document.setMarkdown(text)
    else:
        document.setHtml(_plain_text_to_html(text))
    return _with_body_font_size(document.toHtml())


def build_imported_note(path: Path, text: str) -> ImportedNote:
    suffix = path.suffix
    category = imported_note_category_from_suffix(suffix)
    title = _markdown_title(text) if category == "MD" else ""
    title = title or path.stem or "导入的小纸条"
    return ImportedNote(
        title=title,
        html=note_html_from_imported_text(text, suffix),
        category=category,
        source=f"来源：{path.name}",
    )


def read_import_text(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def note_plain_summary(note_html: str, limit: int = 44) -> str:
    document = QTextDocument()
    document.setHtml(note_html)
    text = " ".join(document.toPlainText().split())
    if len(text) <= limit:
        return text
    snippet = text[:limit].rstrip()
    if " " in snippet:
        snippet = snippet.rsplit(" ", 1)[0]
    return snippet + "..."


def _plain_text_to_html(text: str) -> str:
    escaped = html.escape(text).replace("\n", "<br>")
    return f'<p style="font-size:13pt;">{escaped}</p>'


def _with_body_font_size(note_html: str) -> str:
    for tag in ("p", "li", "code"):
        note_html = _with_tag_font_size(note_html, tag)
    note_html = re.sub(
        r'(<span style=")(?![^"]*font-size:)([^"]*font-family:[^"]*")',
        r"\1font-size:13pt; \2",
        note_html,
    )
    return note_html


def _with_tag_font_size(note_html: str, tag: str) -> str:
    pattern = re.compile(rf"<{tag}([^>]*)>")

    def replace(match: re.Match[str]) -> str:
        attrs = match.group(1)
        style_match = re.search(r'style="([^"]*)"', attrs)
        if style_match:
            style = style_match.group(1)
            if "font-size:" in style:
                return match.group(0)
            updated_style = f'font-size:13pt; {style}'
            updated_attrs = (
                attrs[: style_match.start(1)]
                + updated_style
                + attrs[style_match.end(1) :]
            )
            return f"<{tag}{updated_attrs}>"
        return f'<{tag}{attrs} style="font-size:13pt;">'

    return pattern.sub(replace, note_html)


def _markdown_title(text: str) -> str:
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}#\s+(.+?)\s*#*\s*$", line)
        if match:
            return match.group(1).strip()
    return ""

