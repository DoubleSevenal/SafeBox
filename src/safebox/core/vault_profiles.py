from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from safebox.core.settings import APP_DIR_NAME


@dataclass(slots=True)
class VaultProfileSettings:
    backup_dir: str = ""
    auto_sync_on_close: bool = True
    auto_lock_seconds: int = 300
    transfer_download_dir: str = ""
    theme_name: str = "classic"
    window_close_action: str = ""
    remember_password: bool = False
    remembered_password: str = ""
    trusted_transfer_devices: list[dict[str, str]] = field(default_factory=list)


def app_data_dir() -> Path:
    return Path.home() / "AppData" / "Local" / APP_DIR_NAME


def safe_vault_slug(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name.strip())
    cleaned = re.sub(r"\s+", "_", cleaned).strip(" ._")
    return cleaned or "default"


def vault_path_for_name(base_dir: Path, name: str) -> Path:
    return base_dir / "vaults" / safe_vault_slug(name) / "vault.db"


def backup_file_for_vault(backup_dir: Path, name: str) -> Path:
    return backup_dir / f"SafeBox-{safe_vault_slug(name)}.pmbackup"


def profile_settings_path(base_dir: Path, name: str) -> Path:
    return base_dir / "vaults" / safe_vault_slug(name) / "settings.json"


def load_profile_settings(base_dir: Path, name: str) -> VaultProfileSettings:
    path = profile_settings_path(base_dir, name)
    if not path.exists():
        return VaultProfileSettings()
    data = json.loads(path.read_text(encoding="utf-8"))
    return VaultProfileSettings(
        backup_dir=str(data.get("backup_dir", "")),
        auto_sync_on_close=bool(data.get("auto_sync_on_close", True)),
        auto_lock_seconds=int(data.get("auto_lock_seconds", 300)),
        transfer_download_dir=str(data.get("transfer_download_dir", "")),
        theme_name=str(data.get("theme_name", "classic") or "classic"),
        window_close_action=str(data.get("window_close_action", "")),
        remember_password=bool(data.get("remember_password", False)),
        remembered_password=str(data.get("remembered_password", "")),
        trusted_transfer_devices=[
            {
                "id": str(item.get("id", "")),
                "name": str(item.get("name", "")),
                "last_connected_at": str(item.get("last_connected_at", "")),
            }
            for item in data.get("trusted_transfer_devices", [])
            if isinstance(item, dict) and item.get("id") and item.get("name")
        ],
    )


def save_profile_settings(base_dir: Path, name: str, settings: VaultProfileSettings) -> None:
    path = profile_settings_path(base_dir, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "backup_dir": settings.backup_dir,
                "auto_sync_on_close": settings.auto_sync_on_close,
                "auto_lock_seconds": settings.auto_lock_seconds,
                "transfer_download_dir": settings.transfer_download_dir,
                "theme_name": settings.theme_name,
                "window_close_action": settings.window_close_action,
                "remember_password": settings.remember_password,
                "remembered_password": settings.remembered_password,
                "trusted_transfer_devices": settings.trusted_transfer_devices,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def sync_vault_to_backup(vault_path: Path, backup_dir: Path, name: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_file_for_vault(backup_dir, name)
    shutil.copyfile(vault_path, target)
    return target


def restore_vault_from_backup(backup_file: Path, vault_path: Path) -> None:
    vault_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_file, vault_path)

