from safebox.core.crypto import CryptoBox
from safebox.core.models import Record, RecordType
from safebox.core.store import VaultStore


def test_store_initializes_and_reopens(vault_path) -> None:
    store = VaultStore(vault_path)
    assert not store.exists()

    box = CryptoBox.create("master password")
    store.initialize(box)

    assert store.exists()
    loaded = store.load_crypto_box("master password")
    assert loaded.salt == box.salt


def test_store_saves_and_loads_encrypted_records(vault_path) -> None:
    store = VaultStore(vault_path)
    box = CryptoBox.create("master password")
    store.initialize(box)
    record = Record(
        id="rec_1",
        type=RecordType.ACCOUNT,
        name="School platform",
        account="20240001",
        password="secret",
        category="School",
        note="Open from official account menu",
        entry_hint="Official account entry",
        created_at="2026-05-06T19:00:00+08:00",
        updated_at="2026-05-06T19:00:00+08:00",
    )

    store.upsert_record(box, record)
    rows = store.load_records(box)

    assert rows == [record]
    assert b"secret" not in vault_path.read_bytes()

