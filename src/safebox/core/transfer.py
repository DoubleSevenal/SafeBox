from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class TransferConversationStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"
    PENDING_REVIEW = "pending_review"
    TRANSFERRED = "transferred"


@dataclass(slots=True)
class TransferConversation:
    id: str
    title: str
    device_name: str
    status: TransferConversationStatus = TransferConversationStatus.ACTIVE
    created_at: str = ""
    updated_at: str = ""
    closed_at: str = ""
    message_count: int = 0
    attachment_count: int = 0
    note_id: str = ""
    note_sync_active: bool = False
    note_last_appended_message_id: str = ""
    deleted_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransferConversation:
        clean = dict(data)
        clean["status"] = TransferConversationStatus(clean["status"])
        clean.setdefault("message_count", 0)
        clean.setdefault("attachment_count", 0)
        clean.setdefault("note_id", "")
        clean.setdefault("note_sync_active", False)
        clean.setdefault("note_last_appended_message_id", "")
        clean.setdefault("deleted_at", "")
        return cls(**clean)
