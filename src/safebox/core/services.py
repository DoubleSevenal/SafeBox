from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from shutil import copy2
from uuid import uuid4

from safebox.core.crypto import CryptoBox, InvalidPasswordError
from safebox.core.models import Record, RecordSummary, RecordType
from safebox.core.store import VaultStore
from safebox.core.transfer import (
    DownloadHistoryRecord,
    TransferAttachment,
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
        attachments = self.store.load_all_transfer_attachments(self._require_box())
        download_history = self.store.load_download_history(self._require_box())
        box = CryptoBox.create(new_password)
        self.store.save_crypto_box(box)
        self._box = box
        for record in records:
            self._save(record)
        for conversation in conversations:
            self._save_transfer_conversation(conversation)
        for message in messages:
            self._save_transfer_message(message)
        for attachment in attachments:
            self._save_transfer_attachment(attachment)
        for download_record in download_history:
            self._save_download_history_record(download_record)

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
        if existing.status == TransferConversationStatus.CLOSED or existing.closed_at:
            return existing
        now = _now()
        if existing.status != TransferConversationStatus.TRANSFERRED:
            existing.status = TransferConversationStatus.CLOSED
        existing.closed_at = now
        existing.updated_at = now
        existing.note_sync_active = False
        self._save_transfer_conversation(existing)
        return existing

    def delete_transfer_conversation(self, conversation_id: str) -> None:
        existing = self.get_transfer_conversation(conversation_id)
        if _transfer_conversation_is_open(existing):
            raise ValueError("Active transfer conversation cannot be deleted")
        if existing.deleted_at:
            return
        now = _now()
        existing.deleted_at = now
        existing.updated_at = now
        self._save_transfer_conversation(existing)

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
        if not _transfer_conversation_is_open(conversation):
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
        if conversation.note_sync_active and conversation.note_id:
            self._append_transfer_messages_to_note(conversation, [message])
        self._save_transfer_conversation(conversation)
        return message

    def add_transfer_attachment_message(
        self,
        conversation_id: str,
        *,
        sender: TransferMessageSender,
        kind: TransferMessageKind,
        filename: str,
        mime_type: str = "",
        size_bytes: int = 0,
        storage_path: str = "",
        sha256: str = "",
        text: str = "",
    ) -> tuple[TransferMessage, TransferAttachment]:
        if kind not in {TransferMessageKind.IMAGE, TransferMessageKind.FILE}:
            raise ValueError("Attachment message kind must be image or file")
        clean_filename = filename.strip()
        if not clean_filename:
            raise ValueError("Attachment filename is required")
        conversation = self.get_transfer_conversation(conversation_id)
        if not _transfer_conversation_is_open(conversation):
            raise ValueError("Transfer conversation is closed")
        now = _now()
        attachment = TransferAttachment(
            id=f"ta_{uuid4().hex}",
            conversation_id=conversation.id,
            message_id="",
            filename=clean_filename,
            mime_type=mime_type.strip(),
            size_bytes=max(0, size_bytes),
            storage_path=storage_path.strip(),
            sha256=sha256.strip(),
            created_at=now,
        )
        message = TransferMessage(
            id=f"tm_{uuid4().hex}",
            conversation_id=conversation.id,
            sender=sender,
            kind=kind,
            text=text.strip(),
            attachment_id=attachment.id,
            created_at=now,
            updated_at=now,
        )
        attachment.message_id = message.id
        self._save_transfer_message(message)
        self._save_transfer_attachment(attachment)
        conversation.message_count += 1
        conversation.attachment_count += 1
        conversation.updated_at = now
        if conversation.note_sync_active and conversation.note_id:
            self._append_transfer_messages_to_note(conversation, [message])
        self._save_transfer_conversation(conversation)
        return message, attachment

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

    def edit_transfer_text_message(
        self,
        conversation_id: str,
        message_id: str,
        *,
        text: str,
    ) -> TransferMessage:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Message text is required")
        conversation = self.get_transfer_conversation(conversation_id)
        if not _transfer_conversation_is_open(conversation):
            raise ValueError("Transfer conversation is closed")
        messages = self.list_transfer_messages(conversation.id)
        message = next((item for item in messages if item.id == message_id), None)
        if message is None:
            raise KeyError(message_id)
        if message.kind != TransferMessageKind.TEXT:
            raise ValueError("Only text messages can be edited")
        now = _now()
        message.text = clean_text
        message.edited_at = now
        message.updated_at = now
        conversation.updated_at = now
        self._save_transfer_message(message)
        if conversation.note_sync_active and conversation.note_id:
            self._refresh_transfer_note(conversation)
        self._save_transfer_conversation(conversation)
        return message

    def list_transfer_attachments(self, conversation_id: str) -> list[TransferAttachment]:
        self.get_transfer_conversation(conversation_id)
        return [
            attachment
            for attachment in self.store.load_transfer_attachments(
                self._require_box(),
                conversation_id,
            )
            if not attachment.deleted_at
        ]

    def download_transfer_attachment(
        self,
        *,
        conversation_id: str,
        attachment_id: str,
        download_dir: Path,
    ) -> DownloadHistoryRecord:
        attachment = self._get_transfer_attachment(conversation_id, attachment_id)
        source = Path(attachment.storage_path)
        if not source.exists():
            raise FileNotFoundError(source)
        target_dir = Path(download_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = _unique_download_path(target_dir / attachment.filename)
        copy2(source, target)
        return self.record_transfer_download(
            conversation_id=conversation_id,
            message_id=attachment.message_id,
            attachment_id=attachment.id,
            filename=attachment.filename,
            saved_path=target,
            size_bytes=target.stat().st_size,
        )

    def record_transfer_download(
        self,
        *,
        conversation_id: str,
        message_id: str,
        attachment_id: str,
        filename: str,
        saved_path: Path,
        size_bytes: int = 0,
    ) -> DownloadHistoryRecord:
        self.get_transfer_conversation(conversation_id)
        now = _now()
        record = DownloadHistoryRecord(
            id=f"dh_{uuid4().hex}",
            conversation_id=conversation_id,
            message_id=message_id,
            attachment_id=attachment_id,
            filename=filename.strip(),
            saved_path=str(saved_path),
            size_bytes=max(0, size_bytes),
            downloaded_at=now,
            exists=Path(saved_path).exists(),
        )
        self._save_download_history_record(record)
        return record

    def list_download_history(self) -> list[DownloadHistoryRecord]:
        records = self.store.load_download_history(self._require_box())
        for record in records:
            record.exists = Path(record.saved_path).exists()
        return records

    def delete_download_history_record(self, record_id: str) -> None:
        for record in self.list_download_history():
            if record.id == record_id:
                record.deleted_at = _now()
                self._save_download_history_record(record)
                return
        raise KeyError(record_id)

    def clear_download_history(self) -> None:
        for record in self.list_download_history():
            record.deleted_at = _now()
            self._save_download_history_record(record)

    def _get_transfer_attachment(
        self,
        conversation_id: str,
        attachment_id: str,
    ) -> TransferAttachment:
        for attachment in self.list_transfer_attachments(conversation_id):
            if attachment.id == attachment_id:
                return attachment
        raise KeyError(attachment_id)

    def export_transfer_conversation_to_note(self, conversation_id: str) -> Record:
        conversation = self.get_transfer_conversation(conversation_id)
        messages = self.list_transfer_messages(conversation_id)
        if conversation.note_id:
            note = self.get_record(conversation.note_id)
            note.note = self._format_transfer_note(messages)
            note.updated_at = _now()
            note.category = "会话"
            self._save(note)
        else:
            note = self.create_secure_note(
                name=conversation.title,
                note=self._format_transfer_note(messages),
                category="会话",
            )
            conversation.note_id = note.id
        conversation.note_sync_active = _transfer_conversation_is_open(conversation)
        conversation.note_last_appended_message_id = messages[-1].id if messages else ""
        conversation.status = TransferConversationStatus.TRANSFERRED
        conversation.updated_at = _now()
        self._save_transfer_conversation(conversation)
        return note

    def _append_transfer_messages_to_note(
        self,
        conversation: TransferConversation,
        messages: list[TransferMessage],
    ) -> None:
        if not messages:
            return
        note = self.get_record(conversation.note_id)
        addition = self._format_transfer_note(messages)
        if note.note.strip():
            note.note = f"{note.note.rstrip()}\n\n{addition}"
        else:
            note.note = addition
        note.updated_at = _now()
        note.category = "会话"
        self._save(note)
        conversation.note_last_appended_message_id = messages[-1].id

    def _refresh_transfer_note(self, conversation: TransferConversation) -> None:
        note = self.get_record(conversation.note_id)
        messages = self.list_transfer_messages(conversation.id)
        note.note = self._format_transfer_note(messages)
        note.updated_at = _now()
        note.category = "会话"
        self._save(note)
        conversation.note_last_appended_message_id = messages[-1].id if messages else ""

    def _format_transfer_note(self, messages: list[TransferMessage]) -> str:
        blocks: list[str] = []
        for message in messages:
            content = message.text
            if message.kind in {TransferMessageKind.IMAGE, TransferMessageKind.FILE}:
                content = self._attachment_placeholder(message)
            blocks.append(content)
        return "\n\n".join(blocks)

    def _attachment_placeholder(self, message: TransferMessage) -> str:
        attachments = self.list_transfer_attachments(message.conversation_id)
        attachment = next(
            (item for item in attachments if item.id == message.attachment_id),
            None,
        )
        filename = attachment.filename if attachment else "未知附件"
        label = "图片附件" if message.kind == TransferMessageKind.IMAGE else "文件附件"
        return f"[{label}] {filename}"

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

    def _save_transfer_attachment(self, attachment: TransferAttachment) -> None:
        self.store.upsert_transfer_attachment(self._require_box(), attachment)

    def _save_download_history_record(self, record: DownloadHistoryRecord) -> None:
        self.store.upsert_download_history_record(self._require_box(), record)

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


def _unique_download_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 1
    while True:
        candidate = parent / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _transfer_conversation_is_open(conversation: TransferConversation) -> bool:
    return (
        conversation.status
        in {TransferConversationStatus.ACTIVE, TransferConversationStatus.TRANSFERRED}
        and not conversation.closed_at
    )


def try_unlock(service: VaultService, master_password: str) -> UnlockResult:
    try:
        service.unlock(master_password)
    except InvalidPasswordError:
        return UnlockResult(ok=False, message="保险箱密码不正确，请重新输入。")
    except KeyError:
        return UnlockResult(ok=False, message="保险箱文件不完整，无法解锁。")
    return UnlockResult(ok=True)

