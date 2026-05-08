from __future__ import annotations

import sqlite3
from pathlib import Path

from safebox.core.crypto import CryptoBox
from safebox.core.models import Record
from safebox.core.transfer import (
    DownloadHistoryRecord,
    TransferAttachment,
    TransferConversation,
    TransferMessage,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS vault_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name_index TEXT NOT NULL,
    category_index TEXT NOT NULL,
    favorite INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    encrypted_payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transfer_conversations (
    id TEXT PRIMARY KEY,
    title_index TEXT NOT NULL,
    device_index TEXT NOT NULL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    encrypted_payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transfer_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    sender TEXT NOT NULL,
    created_at TEXT NOT NULL,
    encrypted_payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transfer_attachments (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    filename_index TEXT NOT NULL,
    created_at TEXT NOT NULL,
    encrypted_payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS download_history (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    attachment_id TEXT NOT NULL,
    filename_index TEXT NOT NULL,
    downloaded_at TEXT NOT NULL,
    deleted_at TEXT NOT NULL DEFAULT '',
    encrypted_payload TEXT NOT NULL
);
"""


class VaultStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists() and self.path.stat().st_size > 0

    def initialize(self, box: CryptoBox) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(SCHEMA)
            con.execute(
                "INSERT OR REPLACE INTO vault_meta(key, value) VALUES(?, ?)",
                ("salt", box.salt),
            )
            con.execute(
                "INSERT OR REPLACE INTO vault_meta(key, value) VALUES(?, ?)",
                ("verify_token", box.verify_token),
            )

    def save_crypto_box(self, box: CryptoBox) -> None:
        with self._connect() as con:
            con.executescript(SCHEMA)
            con.execute(
                "INSERT OR REPLACE INTO vault_meta(key, value) VALUES(?, ?)",
                ("salt", box.salt),
            )
            con.execute(
                "INSERT OR REPLACE INTO vault_meta(key, value) VALUES(?, ?)",
                ("verify_token", box.verify_token),
            )

    def load_crypto_box(self, master_password: str) -> CryptoBox:
        with self._connect() as con:
            con.executescript(SCHEMA)
            rows = dict(con.execute("SELECT key, value FROM vault_meta").fetchall())
        return CryptoBox.from_existing(master_password, rows["salt"], rows["verify_token"])

    def upsert_record(self, box: CryptoBox, record: Record) -> None:
        encrypted = box.encrypt_json(record.to_dict())
        with self._connect() as con:
            con.executescript(SCHEMA)
            con.execute(
                """
                INSERT INTO records(
                    id, type, name_index, category_index, favorite, updated_at, encrypted_payload
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    type = excluded.type,
                    name_index = excluded.name_index,
                    category_index = excluded.category_index,
                    favorite = excluded.favorite,
                    updated_at = excluded.updated_at,
                    encrypted_payload = excluded.encrypted_payload
                """,
                (
                    record.id,
                    record.type.value,
                    record.name.casefold(),
                    record.category.casefold(),
                    int(record.favorite),
                    record.updated_at,
                    encrypted,
                ),
            )

    def load_records(self, box: CryptoBox) -> list[Record]:
        with self._connect() as con:
            con.executescript(SCHEMA)
            rows = con.execute(
                "SELECT encrypted_payload FROM records ORDER BY updated_at DESC"
            ).fetchall()
        return [Record.from_dict(box.decrypt_json(row[0])) for row in rows]

    def delete_record(self, record_id: str) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM records WHERE id = ?", (record_id,))

    def upsert_transfer_conversation(
        self,
        box: CryptoBox,
        conversation: TransferConversation,
    ) -> None:
        encrypted = box.encrypt_json(conversation.to_dict())
        with self._connect() as con:
            con.executescript(SCHEMA)
            con.execute(
                """
                INSERT INTO transfer_conversations(
                    id, title_index, device_index, status, updated_at, encrypted_payload
                )
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title_index = excluded.title_index,
                    device_index = excluded.device_index,
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    encrypted_payload = excluded.encrypted_payload
                """,
                (
                    conversation.id,
                    conversation.title.casefold(),
                    conversation.device_name.casefold(),
                    conversation.status.value,
                    conversation.updated_at,
                    encrypted,
                ),
            )

    def load_transfer_conversations(self, box: CryptoBox) -> list[TransferConversation]:
        with self._connect() as con:
            con.executescript(SCHEMA)
            rows = con.execute(
                "SELECT encrypted_payload FROM transfer_conversations ORDER BY updated_at DESC"
            ).fetchall()
        return [TransferConversation.from_dict(box.decrypt_json(row[0])) for row in rows]

    def upsert_transfer_message(self, box: CryptoBox, message: TransferMessage) -> None:
        encrypted = box.encrypt_json(message.to_dict())
        with self._connect() as con:
            con.executescript(SCHEMA)
            con.execute(
                """
                INSERT INTO transfer_messages(
                    id, conversation_id, kind, sender, created_at, encrypted_payload
                )
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    conversation_id = excluded.conversation_id,
                    kind = excluded.kind,
                    sender = excluded.sender,
                    created_at = excluded.created_at,
                    encrypted_payload = excluded.encrypted_payload
                """,
                (
                    message.id,
                    message.conversation_id,
                    message.kind.value,
                    message.sender.value,
                    message.created_at,
                    encrypted,
                ),
            )

    def load_transfer_messages(
        self,
        box: CryptoBox,
        conversation_id: str,
    ) -> list[TransferMessage]:
        rows = self._load_transfer_message_rows(conversation_id)
        return [TransferMessage.from_dict(box.decrypt_json(row[0])) for row in rows]

    def load_all_transfer_messages(self, box: CryptoBox) -> list[TransferMessage]:
        rows = self._load_transfer_message_rows()
        return [TransferMessage.from_dict(box.decrypt_json(row[0])) for row in rows]

    def upsert_transfer_attachment(
        self,
        box: CryptoBox,
        attachment: TransferAttachment,
    ) -> None:
        encrypted = box.encrypt_json(attachment.to_dict())
        with self._connect() as con:
            con.executescript(SCHEMA)
            con.execute(
                """
                INSERT INTO transfer_attachments(
                    id, conversation_id, message_id, filename_index, created_at, encrypted_payload
                )
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    conversation_id = excluded.conversation_id,
                    message_id = excluded.message_id,
                    filename_index = excluded.filename_index,
                    created_at = excluded.created_at,
                    encrypted_payload = excluded.encrypted_payload
                """,
                (
                    attachment.id,
                    attachment.conversation_id,
                    attachment.message_id,
                    attachment.filename.casefold(),
                    attachment.created_at,
                    encrypted,
                ),
            )

    def load_transfer_attachments(
        self,
        box: CryptoBox,
        conversation_id: str,
    ) -> list[TransferAttachment]:
        rows = self._load_transfer_attachment_rows(conversation_id)
        return [TransferAttachment.from_dict(box.decrypt_json(row[0])) for row in rows]

    def load_all_transfer_attachments(self, box: CryptoBox) -> list[TransferAttachment]:
        rows = self._load_transfer_attachment_rows()
        return [TransferAttachment.from_dict(box.decrypt_json(row[0])) for row in rows]

    def upsert_download_history_record(
        self,
        box: CryptoBox,
        record: DownloadHistoryRecord,
    ) -> None:
        encrypted = box.encrypt_json(record.to_dict())
        with self._connect() as con:
            con.executescript(SCHEMA)
            con.execute(
                """
                INSERT INTO download_history(
                    id, conversation_id, attachment_id, filename_index, downloaded_at,
                    deleted_at, encrypted_payload
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    conversation_id = excluded.conversation_id,
                    attachment_id = excluded.attachment_id,
                    filename_index = excluded.filename_index,
                    downloaded_at = excluded.downloaded_at,
                    deleted_at = excluded.deleted_at,
                    encrypted_payload = excluded.encrypted_payload
                """,
                (
                    record.id,
                    record.conversation_id,
                    record.attachment_id,
                    record.filename.casefold(),
                    record.downloaded_at,
                    record.deleted_at,
                    encrypted,
                ),
            )

    def load_download_history(self, box: CryptoBox) -> list[DownloadHistoryRecord]:
        with self._connect() as con:
            con.executescript(SCHEMA)
            rows = con.execute(
                """
                SELECT encrypted_payload
                FROM download_history
                WHERE deleted_at = ''
                ORDER BY downloaded_at DESC
                """
            ).fetchall()
        return [DownloadHistoryRecord.from_dict(box.decrypt_json(row[0])) for row in rows]

    def _load_transfer_message_rows(
        self,
        conversation_id: str = "",
    ) -> list[sqlite3.Row]:
        with self._connect() as con:
            con.executescript(SCHEMA)
            if conversation_id:
                return con.execute(
                    """
                    SELECT encrypted_payload
                    FROM transfer_messages
                    WHERE conversation_id = ?
                    ORDER BY created_at ASC
                    """,
                    (conversation_id,),
                ).fetchall()
            return con.execute(
                "SELECT encrypted_payload FROM transfer_messages ORDER BY created_at ASC"
            ).fetchall()

    def _load_transfer_attachment_rows(
        self,
        conversation_id: str = "",
    ) -> list[sqlite3.Row]:
        with self._connect() as con:
            con.executescript(SCHEMA)
            if conversation_id:
                return con.execute(
                    """
                    SELECT encrypted_payload
                    FROM transfer_attachments
                    WHERE conversation_id = ?
                    ORDER BY created_at ASC
                    """,
                    (conversation_id,),
                ).fetchall()
            return con.execute(
                "SELECT encrypted_payload FROM transfer_attachments ORDER BY created_at ASC"
            ).fetchall()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

