from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class RecordType(StrEnum):
    ACCOUNT = "account"
    SECURE_NOTE = "secure_note"


@dataclass(slots=True)
class Record:
    id: str
    type: RecordType
    name: str
    account: str = ""
    password: str = ""
    category: str = ""
    note: str = ""
    entry_hint: str = ""
    created_at: str = ""
    updated_at: str = ""
    deleted_at: str = ""
    favorite: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Record:
        clean = dict(data)
        clean["type"] = RecordType(clean["type"])
        clean.pop("tags", None)
        clean.setdefault("deleted_at", "")
        return cls(**clean)


@dataclass(slots=True)
class RecordSummary:
    id: str
    type: RecordType
    name: str
    account: str
    category: str
    favorite: bool
    created_at: str
    updated_at: str
