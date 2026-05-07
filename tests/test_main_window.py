from pathlib import Path

from safebox.core.services import VaultService
from safebox.core.vault_profiles import vault_path_for_name
from safebox.ui import main_window
from safebox.ui.branding import SAFEBOX_NAV_MARK_PATH
from safebox.ui.main_window import MainWindow


class FakeVaultOpenDialog:
    def __init__(self, parent=None) -> None:
        pass

    def exec(self) -> bool:
        return True

    def values(self) -> tuple[str, str, str, str]:
        return ("于祥磊", "wojiao321.", "", "open")


def test_open_existing_vault_refreshes_account_and_note_lists(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.create_account(
        name="微信",
        account="wechat-user",
        password="secret",
        category="软件",
    )
    service.create_secure_note(name="二课平台说明", note="公众号入口", category="收件箱")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))

    window._open_vault()

    assert window.service.store.path == vault_path
    assert window.vault_subtitle.text() == "保险箱ID：于祥磊 / 账号1 / 小纸条1"
    assert window.account_list.count() == 1
    assert window.account_status.text() == ""
    assert "总记录 2 / 账号 1 / 小纸条 1" in window.settings_data_overview.text()

    window._show_notes_page()

    assert window.note_list.count() == 1
    assert window.note_status.text() == ""
    assert "数据文件：" in window.settings_data_overview.text()

    window.close()


def test_record_context_menu_actions_view_and_delete(vault_path: Path, monkeypatch, qt_app) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    account = service.create_account(
        name="微信",
        account="wechat-user",
        password="secret",
        category="软件",
    )
    service.create_secure_note(name="说明", note="正文", category="收件箱")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()

    account_item = window.account_list.item(0)
    window._handle_record_context_action("accounts", account_item, "view")
    assert window.current_account_id == account.id
    assert window.pages.currentWidget() == window.account_detail_page

    monkeypatch.setattr(
        main_window.QMessageBox,
        "question",
        lambda *args, **kwargs: main_window.QMessageBox.StandardButton.Yes,
    )
    window._show_notes_page()
    note_item = window.note_list.item(0)
    window._handle_record_context_action("notes", note_item, "delete")
    assert window.service.search("说明") == []
    assert len(window.service.trash()) == 1

    assert window.account_list.contextMenuPolicy().name == "CustomContextMenu"
    assert window.note_list.contextMenuPolicy().name == "CustomContextMenu"
    window.close()


def test_copy_account_fields_shows_non_modal_notice(vault_path: Path, monkeypatch, qt_app) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    record = service.create_account(
        name="微信",
        account="wechat-user",
        password="secret",
        category="软件",
    )
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window.current_account_id = record.id

    window._copy_current_account_field("account")
    assert window.account_save_notice.text() == "账号已复制"
    assert not window.account_save_notice.isHidden()

    window._copy_current_account_field("password")
    assert window.account_save_notice.text() == "密码已复制"
    assert not window.account_save_notice.isHidden()

    window.close()


def test_sidebar_separates_management_nav_and_wraps_vault_summary(qt_app) -> None:
    window = MainWindow(lambda name: VaultService(Path(":memory:")))

    assert window.vault_subtitle.isHidden()
    assert window.trash_nav.parent().objectName() == "ManagementNavGroup"
    assert window.settings_nav.parent().objectName() == "ManagementNavGroup"

    window.close()


def test_home_header_uses_project_bundled_brand_mark(qt_app) -> None:
    window = MainWindow(lambda name: VaultService(Path(":memory:")))

    assert SAFEBOX_NAV_MARK_PATH.is_file()
    assert window.header_brand_mark.pixmap() is not None
    assert window.header_brand_mark.layoutDirection().name == "LeftToRight"
    assert window.header_brand_mark.parent() is window.header_brand

    window.close()
