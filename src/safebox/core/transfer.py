from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class TransferConversationStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"
    PENDING_REVIEW = "pending_review"
    TRANSFERRED = "transferred"


class TransferMessageSender(StrEnum):
    DESKTOP = "desktop"
    PHONE = "phone"


class TransferMessageKind(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"


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


@dataclass(slots=True)
class TransferMessage:
    id: str
    conversation_id: str
    sender: TransferMessageSender
    kind: TransferMessageKind
    text: str = ""
    attachment_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    edited_at: str = ""
    deleted_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sender"] = self.sender.value
        data["kind"] = self.kind.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransferMessage:
        clean = dict(data)
        clean["sender"] = TransferMessageSender(clean["sender"])
        clean["kind"] = TransferMessageKind(clean["kind"])
        clean.setdefault("text", "")
        clean.setdefault("attachment_id", "")
        clean.setdefault("updated_at", "")
        clean.setdefault("edited_at", "")
        clean.setdefault("deleted_at", "")
        return cls(**clean)


@dataclass(slots=True)
class TransferAttachment:
    id: str
    conversation_id: str
    message_id: str
    filename: str
    mime_type: str = ""
    size_bytes: int = 0
    storage_path: str = ""
    sha256: str = ""
    created_at: str = ""
    deleted_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransferAttachment:
        clean = dict(data)
        clean.setdefault("mime_type", "")
        clean.setdefault("size_bytes", 0)
        clean.setdefault("storage_path", "")
        clean.setdefault("sha256", "")
        clean.setdefault("deleted_at", "")
        return cls(**clean)


@dataclass(slots=True)
class DownloadHistoryRecord:
    id: str
    conversation_id: str
    message_id: str
    attachment_id: str
    filename: str
    saved_path: str
    size_bytes: int = 0
    downloaded_at: str = ""
    deleted_at: str = ""
    exists: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("exists", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DownloadHistoryRecord:
        clean = dict(data)
        clean.setdefault("size_bytes", 0)
        clean.setdefault("deleted_at", "")
        clean.setdefault("exists", False)
        return cls(**clean)
