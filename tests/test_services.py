from inspect import signature

import pytest

from safebox.core.models import Record, RecordType
from safebox.core.services import UnlockResult, VaultService, try_unlock
from safebox.ui.dialogs import AccountFormData


def test_record_round_trip_dict_ignores_legacy_tags() -> None:
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
        favorite=False,
    )
    legacy_payload = record.to_dict() | {"tags": ["legacy"]}

    restored = Record.from_dict(legacy_payload)

    assert restored == record
    assert not hasattr(restored, "tags")


def test_record_round_trip_defaults_deleted_at() -> None:
    record = Record(
        id="rec_legacy",
        type=RecordType.SECURE_NOTE,
        name="Legacy note",
    )
    payload = record.to_dict()
    payload.pop("deleted_at")

    restored = Record.from_dict(payload)

    assert restored.deleted_at == ""


def test_service_create_methods_do_not_expose_tags() -> None:
    assert "tags" not in signature(VaultService.create_account).parameters
    assert "tags" not in signature(VaultService.create_secure_note).parameters


def test_account_form_data_converts_to_service_payload() -> None:
    data = AccountFormData(
        name="School platform",
        account="20240001",
        password="secret",
        category="School",
        note="Open from official account menu",
        entry_hint="Official account entry",
    )

    assert data.to_payload() == {
        "name": "School platform",
        "account": "20240001",
        "password": "secret",
        "category": "School",
        "note": "Open from official account menu",
        "entry_hint": "Official account entry",
    }


def test_service_creates_account_and_searches(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")

    record = service.create_account(
        name="School platform",
        account="20240001",
        password="secret",
        category="School",
        note="Open from official account menu",
        entry_hint="Official account entry",
    )

    results = service.search("School")

    assert results[0].id == record.id
    assert service.get_record(record.id).password == "secret"


def test_service_creates_secure_note(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")

    note = service.create_secure_note(
        name="Inbox note",
        note="Text copied from phone",
        category="Inbox",
    )

    assert note.type == RecordType.SECURE_NOTE
    assert service.search("phone")[0].id == note.id


def test_service_updates_account(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")
    record = service.create_account(
        name="Old name",
        account="old-account",
        password="old-password",
        category="Other",
    )

    updated = service.update_account(
        record.id,
        name="New name",
        account="new-account",
        password="new-password",
        category="School",
        note="new note",
        entry_hint="new entry",
    )

    assert updated.name == "New name"
    assert service.get_record(record.id).password == "new-password"
    assert service.search("new note")[0].id == record.id


def test_service_updates_secure_note(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")
    note = service.create_secure_note(name="Old note", note="old body", category="Inbox")

    updated = service.update_secure_note(
        note.id,
        name="New note",
        note="new body",
        category="Other",
    )

    assert updated.name == "New note"
    assert service.get_record(note.id).note == "new body"


def test_service_moves_deleted_records_to_trash_and_restores(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")
    note = service.create_secure_note(name="Trash me", note="body", category="Inbox")

    service.delete_record(note.id)

    assert service.search("Trash me") == []
    trashed = service.trash()
    assert len(trashed) == 1
    assert trashed[0].id == note.id

    restored = service.restore_record(note.id)

    assert restored.deleted_at == ""
    assert service.search("Trash me")[0].id == note.id


def test_service_permanently_deletes_records(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")
    note = service.create_secure_note(name="Remove me", note="body", category="Inbox")
    service.delete_record(note.id)

    service.permanently_delete_record(note.id)

    assert service.trash() == []


def test_service_initialize_refuses_existing_vault_without_rekeying_records(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("old password")
    record = service.create_account(name="Email", account="me", password="secret")
    service.lock()

    with pytest.raises(ValueError, match="already exists"):
        service.initialize("new password")

    service.unlock("old password")

    assert service.get_record(record.id).password == "secret"


def test_service_changes_master_password(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("old password")
    service.unlock("old password")
    record = service.create_account(name="Email", account="me", password="secret")

    service.change_master_password("old password", "new password")
    service.lock()

    wrong = try_unlock(service, "old password")
    right = try_unlock(service, "new password")

    assert wrong.ok is False
    assert right.ok is True
    assert service.get_record(record.id).password == "secret"


def test_try_unlock_returns_error_for_wrong_password(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("correct master password")
    service.lock()

    result = try_unlock(service, "wrong password")

    assert result == UnlockResult(ok=False, message="保险箱密码不正确，请重新输入。")
    assert service.is_unlocked() is False


def test_try_unlock_returns_success_for_correct_password(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("correct master password")
    service.lock()

    result = try_unlock(service, "correct master password")

    assert result == UnlockResult(ok=True, message="")
    assert service.is_unlocked() is True

