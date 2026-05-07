from __future__ import annotations

from enum import StrEnum

from safebox.core.models import RecordSummary


class SortMode(StrEnum):
    UPDATED_DESC = "updated_desc"
    CREATED_DESC = "created_desc"
    NAME_ASC = "name_asc"
    CATEGORY_ASC = "category_asc"


SORT_MODE_LABELS = {
    SortMode.UPDATED_DESC: "按修改时间",
    SortMode.CREATED_DESC: "按创建时间",
    SortMode.NAME_ASC: "按名称",
    SortMode.CATEGORY_ASC: "按类型 / 分类",
}


def sorted_summaries(records: list[RecordSummary], mode: SortMode) -> list[RecordSummary]:
    if mode == SortMode.CREATED_DESC:
        return sorted(
            records,
            key=lambda item: (item.created_at, item.name.casefold()),
            reverse=True,
        )
    if mode == SortMode.NAME_ASC:
        return sorted(records, key=lambda item: item.name.casefold())
    if mode == SortMode.CATEGORY_ASC:
        return sorted(
            records,
            key=lambda item: (_category_rank(item.category), item.name.casefold()),
        )
    return sorted(records, key=lambda item: (item.updated_at, item.name.casefold()), reverse=True)


def imported_note_category_from_suffix(suffix: str) -> str:
    normalized = suffix.casefold()
    if normalized in {".md", ".markdown"}:
        return "MD"
    if normalized == ".txt":
        return "TXT"
    return "文档"


def _category_rank(category: str) -> tuple[int, str]:
    normalized = category.casefold()
    preferred = {
        "md": 0,
        "txt": 1,
        "学校": 2,
        "工作": 3,
        "游戏": 4,
        "生活": 5,
        "软件": 6,
        "收件箱": 7,
        "其他": 99,
    }
    return (preferred.get(normalized, 50), normalized)

