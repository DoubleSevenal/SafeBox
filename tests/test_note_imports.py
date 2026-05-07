from pathlib import Path

from safebox.core.note_imports import (
    build_imported_note,
    note_html_from_imported_text,
    note_plain_summary,
    read_import_text,
)


def test_markdown_import_keeps_rich_content() -> None:
    html = note_html_from_imported_text(
        '# 标题\n\n<font color="#2563eb">蓝色文字</font>',
        ".md",
    )

    assert "标题" in html
    assert "蓝色文字" in html
    assert "#2563eb" in html


def test_text_import_escapes_plain_text() -> None:
    html = note_html_from_imported_text("账号 <admin>\n第二行", ".txt")

    assert "账号 &lt;admin&gt;" in html
    assert "第二行" in html
    assert "font-size:13pt" in html


def test_markdown_import_uses_body_font_size_for_plain_paragraphs() -> None:
    html = note_html_from_imported_text("# 标题\n\n普通正文", ".md")

    assert "普通正文" in html
    assert "font-size:13pt" in html
    assert 'style="' in html
    assert '" style="' not in html


def test_markdown_import_uses_body_font_size_for_lists_and_inline_code() -> None:
    html = note_html_from_imported_text(
        "Mapper 负责和数据库交互。\n\n- `selectById`\n- selectList",
        ".md",
    )

    assert "selectById" in html
    assert "selectList" in html
    assert html.count("font-size:13pt") >= 3
    assert '" style="' not in html


def test_markdown_import_uses_first_heading_as_title() -> None:
    imported = build_imported_note(
        path=Path("school-note.md"),
        text="# School Note\n\n- Open official account\n- Tap entry",
    )

    assert imported.title == "School Note"
    assert imported.category == "MD"
    assert "school-note.md" in imported.source


def test_plain_summary_removes_html_formatting() -> None:
    summary = note_plain_summary("<h1>Title</h1><p>First line<br>Second line</p>", limit=18)

    assert summary == "Title First line..."


def test_read_import_text_supports_utf16() -> None:
    path = Path(".test-output") / "utf16-structure.txt"
    path.parent.mkdir(exist_ok=True)
    path.write_text("项目目录结构", encoding="utf-16")

    try:
        assert read_import_text(path) == "项目目录结构"
    finally:
        path.unlink(missing_ok=True)
