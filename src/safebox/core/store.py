from __future__ import annotations

import sqlite3
from pathlib import Path

from safebox.core.crypto import CryptoBox
from safebox.core.models import Record

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

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

