from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from safebox.core.crypto import CryptoBox, InvalidPasswordError
from safebox.core.models import Record, RecordSummary, RecordType
from safebox.core.store import VaultStore


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
        box = CryptoBox.create(new_password)
        self.store.save_crypto_box(box)
        self._box = box
        for record in records:
            self._save(record)

    def _save(self, record: Record) -> None:
        self.store.upsert_record(self._require_box(), record)

    def _load_all(self) -> list[Record]:
        return self.store.load_records(self._require_box())

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

