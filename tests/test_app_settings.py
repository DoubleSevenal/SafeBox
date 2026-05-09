from pathlib import Path

from safebox.core.settings import AppSettings


def test_app_settings_default_transfer_download_dir(vault_path) -> None:
    settings = AppSettings(vault_path=vault_path)

    assert settings.transfer_download_dir == Path.home() / "Downloads" / "SafeBox"
