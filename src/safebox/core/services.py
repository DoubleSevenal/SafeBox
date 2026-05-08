from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from safebox.core.crypto import CryptoBox, InvalidPasswordError
from safebox.core.models import Record, RecordSummary, RecordType
from safebox.core.store import VaultStore
from safebox.core.transfer import (
    TransferConversation,
    TransferConversationStatus,
    TransferMessage,
    TransferMessageKind,
    TransferMessageSender,
)


class VaultLockedError(RuntimeError):
    """Raised when an operation needs an unlocked vault."""


@dataclass(frozen=True, slots=True)
class UnlockResult:
    ok: bool
    message: str = ""


class VaultService:
    def __init__(self, vault_path: Path) -> None:
        self.store = VaultStore(vault_path)
        self._box: CryptoBox | None = None

    def vault_exists(self) -> bool:
        return self.store.exists()

    def initialize(self, master_password: str) -> None:
        if self.store.exists():
            raise ValueError("Vault already exists")
        box = CryptoBox.create(master_password)
        self.store.initialize(box)
        self._box = box

    def unlock(self, master_password: str) -> None:
        self._box = self.store.load_crypto_box(master_password)

    def lock(self) -> None:
        self._box = None

    def is_unlocked(self) -> bool:
        return self._box is not None

    def create_account(
        self,
        *,
        name: str,
        account: str,
        password: str,
        category: str = "",
        note: str = "",
        entry_hint: str = "",
    ) -> Record:
        now = _now()
        record = Record(
            id=f"rec_{uuid4().hex}",
            type=RecordType.ACCOUNT,
            name=name.strip(),
            account=account.strip(),
            password=password,
            category=_clean_category(category),
            note=note.strip(),
            entry_hint=entry_hint.strip(),
            created_at=now,
            updated_at=now,
        )
        self._save(record)
        return record

    def create_secure_note(
        self,
        *,
        name: str,
        note: str,
        category: str = "",
    ) -> Record:
        now = _now()
        record = Record(
            id=f"rec_{uuid4().hex}",
            type=RecordType.SECURE_NOTE,
            name=name.strip(),
            category=_clean_category(category),
            note=note.strip(),
            created_at=now,
            updated_at=now,
        )
        self._save(record)
        return record

    def update_account(
        self,
        record_id: str,
        *,
        name: str,
        account: str,
        password: str,
        category: str = "",
        note: str = "",
        entry_hint: str = "",
    ) -> Record:
        existing = self.get_record(record_id)
        if existing.type != RecordType.ACCOUNT:
            raise ValueError("Record is not an account")
        record = Record(
            id=existing.id,
            type=RecordType.ACCOUNT,
            name=name.strip(),
            account=account.strip(),
            password=password,
            category=_clean_category(category),
            note=note.strip(),
            entry_hint=entry_hint.strip(),
            created_at=existing.created_at,
            updated_at=_now(),
            favorite=existing.favorite,
        )
        self._save(record)
        return record

    def update_secure_note(
        self,
        record_id: str,
        *,
        name: str,
        note: str,
        category: str = "",
    ) -> Record:
        existing = self.get_record(record_id)
        if existing.type != RecordType.SECURE_NOTE:
            raise ValueError("Record is not a secure note")
        record = Record(
            id=existing.id,
            type=RecordType.SECURE_NOTE,
            name=name.strip(),
            category=_clean_category(category),
            note=note.strip(),
            created_at=existing.created_at,
            updated_at=_now(),
            favorite=existing.favorite,
        )
        self._save(record)
        return record

    def search(self, query: str = "") -> list[RecordSummary]:
        records = [record for record in self._load_all() if not record.deleted_at]
        term = query.casefold().strip()
        if term:
            records = [
                record
                for record in records
                if term
                in " ".join(
                    [
                        record.name,
                        record.account,
                        record.category,
                        record.note,
                        record.entry_hint,
                    ]
                ).casefold()
            ]
        return [self._summary(record) for record in records]

    def trash(self) -> list[RecordSummary]:
        return [self._summary(record) for record in self._load_all() if record.deleted_at]

    def get_record(self, record_id: str) -> Record:
        for record in self._load_all():
            if record.id == record_id:
                return record
        raise KeyError(record_id)

    def delete_record(self, record_id: str) -> None:
        existing = self.get_record(record_id)
        if existing.deleted_at:
            return
        now = _now()
        existing.deleted_at = now
        existing.updated_at = now
        self._save(existing)

    def restore_record(self, record_id: str) -> Record:
        existing = self.get_record(record_id)
        existing.deleted_at = ""
        existing.updated_at = _now()
        self._save(existing)
        return existing

    def permanently_delete_record(self, record_id: str) -> None:
        self._require_box()
        self.store.delete_record(record_id)

    def clear_trash(self) -> None:
        for record in self._load_all():
            if record.deleted_at:
                self.permanently_delete_record(record.id)

    def change_master_password(self, old_password: str, new_password: str) -> None:
        self.unlock(old_password)
        records = self._load_all()
        conversations = self._load_transfer_conversations()
        messages = self.store.load_all_transfer_messages(self._require_box())
        box = CryptoBox.create(new_password)
        self.store.save_crypto_box(box)
        self._box = box
        for record in records:
            self._save(record)
        for conversation in conversations:
            self._save_transfer_conversation(conversation)
        for message in messages:
            self._save_transfer_message(message)

    def create_transfer_conversation(
        self,
        *,
        title: str,
        device_name: str,
    ) -> TransferConversation:
        now = _now()
        conversation = TransferConversation(
            id=f"tc_{uuid4().hex}",
            title=title.strip() or "未命名传输记录",
            device_name=device_name.strip() or "未知设备",
            created_at=now,
            updated_at=now,
        )
        self._save_transfer_conversation(conversation)
        return conversation

    def list_transfer_conversations(self, query: str = "") -> list[TransferConversation]:
        conversations = [
            conversation
            for conversation in self._load_transfer_conversations()
            if not conversation.deleted_at
        ]
        term = query.casefold().strip()
        if term:
            conversations = [
                conversation
                for conversation in conversations
                if term
                in " ".join(
                    [
                        conversation.title,
                        conversation.device_name,
                        conversation.status.value,
                    ]
                ).casefold()
            ]
        return conversations

    def get_transfer_conversation(self, conversation_id: str) -> TransferConversation:
        for conversation in self._load_transfer_conversations():
            if conversation.id == conversation_id:
                return conversation
        raise KeyError(conversation_id)

    def close_transfer_conversation(self, conversation_id: str) -> TransferConversation:
        existing = self.get_transfer_conversation(conversation_id)
        if existing.status == TransferConversationStatus.CLOSED:
            return existing
        now = _now()
        existing.status = TransferConversationStatus.CLOSED
        existing.closed_at = now
        existing.updated_at = now
        existing.note_sync_active = False
        self._save_transfer_conversation(existing)
        return existing

    def add_transfer_text_message(
        self,
        conversation_id: str,
        *,
        sender: TransferMessageSender,
        text: str,
    ) -> TransferMessage:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Message text is required")
        conversation = self.get_transfer_conversation(conversation_id)
        if conversation.status == TransferConversationStatus.CLOSED:
            raise ValueError("Transfer conversation is closed")
        now = _now()
        message = TransferMessage(
            id=f"tm_{uuid4().hex}",
            conversation_id=conversation.id,
            sender=sender,
            kind=TransferMessageKind.TEXT,
            text=clean_text,
            created_at=now,
            updated_at=now,
        )
        self._save_transfer_message(message)
        conversation.message_count += 1
        conversation.updated_at = now
        self._save_transfer_conversation(conversation)
        return message

    def list_transfer_messages(self, conversation_id: str) -> list[TransferMessage]:
        self.get_transfer_conversation(conversation_id)
        return [
            message
            for message in self.store.load_transfer_messages(
                self._require_box(),
                conversation_id,
            )
            if not message.deleted_at
        ]

    def _save(self, record: Record) -> None:
        self.store.upsert_record(self._require_box(), record)

    def _load_all(self) -> list[Record]:
        return self.store.load_records(self._require_box())

    def _save_transfer_conversation(self, conversation: TransferConversation) -> None:
        self.store.upsert_transfer_conversation(self._require_box(), conversation)

    def _load_transfer_conversations(self) -> list[TransferConversation]:
        return self.store.load_transfer_conversations(self._require_box())

    def _save_transfer_message(self, message: TransferMessage) -> None:
        self.store.upsert_transfer_message(self._require_box(), message)

    def _require_box(self) -> CryptoBox:
        if self._box is None:
            raise VaultLockedError("Vault is locked")
        return self._box

    def _summary(self, record: Record) -> RecordSummary:
        return RecordSummary(
            id=record.id,
            type=record.type,
            name=record.name,
            account=record.account,
            category=record.category,
            favorite=record.favorite,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


def _now() -> str:
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


def _clean_category(category: str) -> str:
    return category.strip() or "其他"


def try_unlock(service: VaultService, master_password: str) -> UnlockResult:
    try:
        service.unlock(master_password)
    except InvalidPasswordError:
        return UnlockResult(ok=False, message="保险箱密码不正确，请重新输入。")
    except KeyError:
        return UnlockResult(ok=False, message="保险箱文件不完整，无法解锁。")
    return UnlockResult(ok=True)

