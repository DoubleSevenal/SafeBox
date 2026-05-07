import os
from pathlib import Path
from time import time

from safebox.core.vault_profiles import (
    VaultProfileSettings,
    backup_file_for_vault,
    load_profile_settings,
    safe_vault_slug,
    save_profile_settings,
    sync_vault_to_backup,
    vault_path_for_name,
)


def test_safe_vault_slug_filters_windows_unsafe_characters() -> None:
    assert safe_vault_slug("学校/工作:2026") == "学校_工作_2026"
    assert safe_vault_slug("  ") == "default"


def test_vault_path_uses_slugged_vault_name() -> None:
    path = vault_path_for_name(Path("root"), "school")

    assert path == Path("root") / "vaults" / "school" / "vault.db"


def test_backup_file_is_one_file_per_vault() -> None:
    path = backup_file_for_vault(Path("backup"), "school")

    assert path == Path("backup") / "SafeBox-school.pmbackup"


def test_profile_settings_persist_auto_lock_seconds(tmp_path: Path) -> None:
    settings = VaultProfileSettings(
        backup_dir="D:\\SafeBoxBackup",
        auto_sync_on_close=False,
        auto_lock_seconds=1200,
    )

    save_profile_settings(tmp_path, "school", settings)
    loaded = load_profile_settings(tmp_path, "school")

    assert loaded.backup_dir == "D:\\SafeBoxBackup"
    assert not loaded.auto_sync_on_close
    assert loaded.auto_lock_seconds == 1200


def test_sync_vault_to_backup_uses_sync_time_for_backup_mtime(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault.db"
    vault_path.write_text("safe data", encoding="utf-8")
    old_time = time() - 3600
    os.utime(vault_path, (old_time, old_time))

    before_sync = time()
    target = sync_vault_to_backup(vault_path, tmp_path / "backup", "school")

    assert target.read_text(encoding="utf-8") == "safe data"
    assert target.stat().st_mtime >= before_sync
    assert target.stat().st_mtime > vault_path.stat().st_mtime
