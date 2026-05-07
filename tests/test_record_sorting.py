from safebox.core.models import RecordSummary, RecordType
from safebox.core.record_sorting import (
    SortMode,
    imported_note_category_from_suffix,
    sorted_summaries,
)


def _summary(
    name: str,
    category: str,
    updated_at: str,
    created_at: str,
    record_type: RecordType = RecordType.SECURE_NOTE,
) -> RecordSummary:
    return RecordSummary(
        id=name,
        type=record_type,
        name=name,
        account="",
        category=category,
        favorite=False,
        created_at=created_at,
        updated_at=updated_at,
    )


def test_imported_note_category_uses_file_type() -> None:
    assert imported_note_category_from_suffix(".md") == "MD"
    assert imported_note_category_from_suffix(".markdown") == "MD"
    assert imported_note_category_from_suffix(".txt") == "TXT"
    assert imported_note_category_from_suffix(".unknown") == "文档"


def test_sorted_summaries_by_updated_time_descending() -> None:
    old = _summary("Old", "TXT", "2026-05-05T10:00:00+08:00", "2026-05-05T09:00:00+08:00")
    new = _summary("New", "MD", "2026-05-06T10:00:00+08:00", "2026-05-06T09:00:00+08:00")

    assert [item.name for item in sorted_summaries([old, new], SortMode.UPDATED_DESC)] == [
        "New",
        "Old",
    ]


def test_sorted_summaries_by_category_then_name() -> None:
    md = _summary("Beta", "MD", "2026-05-06T10:00:00+08:00", "2026-05-06T09:00:00+08:00")
    txt = _summary("Alpha", "TXT", "2026-05-06T11:00:00+08:00", "2026-05-06T08:00:00+08:00")
    other = _summary("Other", "其他", "2026-05-06T12:00:00+08:00", "2026-05-06T07:00:00+08:00")

    assert [item.name for item in sorted_summaries([txt, other, md], SortMode.CATEGORY_ASC)] == [
        "Beta",
        "Alpha",
        "Other",
    ]

