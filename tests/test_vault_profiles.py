from pathlib import Path

from safebox.core.vault_profiles import (
    backup_file_for_vault,
    safe_vault_slug,
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
