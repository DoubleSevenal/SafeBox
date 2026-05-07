from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

APP_DIR_NAME = "SafeBox"


@dataclass(frozen=True, slots=True)
class AppSettings:
    vault_path: Path
    auto_lock_seconds: int = 300
    clipboard_clear_seconds: int = 20


def default_vault_path() -> Path:
    base = Path.home() / "AppData" / "Local" / APP_DIR_NAME
    return base / "vaults" / "default" / "vault.db"

