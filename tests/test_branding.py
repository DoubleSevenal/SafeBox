from pathlib import Path

from safebox.ui.branding import (
    SAFEBOX_APP_ICON_PATH,
    SAFEBOX_LOGIN_LOGO_PATH,
    SAFEBOX_NAV_MARK_PATH,
)


def test_project_bundles_all_branding_assets() -> None:
    for path in (SAFEBOX_APP_ICON_PATH, SAFEBOX_LOGIN_LOGO_PATH, SAFEBOX_NAV_MARK_PATH):
        assert path.is_file()
        assert "Downloads" not in str(path)


def test_desktop_launcher_entrypoint_is_project_local() -> None:
    launcher = Path(__file__).resolve().parents[1] / "SafeBox.pyw"

    assert launcher.is_file()
    assert "safebox.ui.app" in launcher.read_text(encoding="utf-8")
