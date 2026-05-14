import json
from dataclasses import replace
from pathlib import Path
from urllib.request import Request, urlopen

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent, QPixmap, QTextCursor
from PySide6.QtWidgets import QMessageBox

from safebox.core.models import Record, RecordType
from safebox.core.services import VaultService
from safebox.core.transfer import TransferMessageKind, TransferMessageSender
from safebox.core.vault_profiles import load_profile_settings, vault_path_for_name
from safebox.ui import main_window
from safebox.ui.branding import SAFEBOX_NAV_MARK_PATH
from safebox.ui.main_window import (
    NOTE_BODY_FONT_SIZE_PT,
    MainWindow,
    _note_export_suffix_for_choice,
    _safe_export_filename,
)
from safebox.ui.theme import LIGHT_FLUENT_QSS


class FakeVaultOpenDialog:
    def __init__(self, parent=None) -> None:
        pass

    def exec(self) -> bool:
        return True

    def values(self) -> tuple[str, str, str, str]:
        return ("于祥磊", "wojiao321.", "", "open")


def _pair_transfer_phone(window: MainWindow) -> None:
    window.connect_phone_button.click()
    assert window.transfer_server is not None
    with urlopen(
        f"{window.transfer_server.url}/?token={window.transfer_server.connection_token}",
        timeout=5,
    ):
        pass
    request = Request(
        f"{window.transfer_server.url}/api/pair",
        data=json.dumps(
            {
                "token": window.transfer_server.connection_token,
                "code": window.transfer_server.verification_code,
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5):
        pass
    window._check_transfer_pairing()


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


def test_sidebar_navigation_preserves_account_detail_page(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    account = service.create_account(
        name="教务系统",
        account="student-user",
        password="secret",
        category="学校",
    )
    service.create_secure_note(name="课程安排", note="周一数学", category="学习")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()

    account_item = window.account_list.item(0)
    window._open_account_item(account_item)
    assert window.current_account_id == account.id
    assert window.pages.currentWidget() == window.account_detail_page

    window._show_notes_page()
    assert window.pages.currentWidget() == window.notes_page

    window._show_accounts_page()
    assert window.pages.currentWidget() == window.account_detail_page
    assert window.current_account_id == account.id
    assert window.account_title.text() == "教务系统"

    window.close()


def test_sidebar_navigation_preserves_note_detail_page(
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
    note = service.create_secure_note(name="课程安排", note="周一数学", category="学习")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()

    window._show_notes_page()
    note_item = window.note_list.item(0)
    window._open_note_item(note_item)
    assert window.current_note_id == note.id
    assert window.pages.currentWidget() == window.note_detail_page

    window._show_accounts_page()
    assert window.pages.currentWidget() == window.accounts_page

    window._show_notes_page()
    assert window.pages.currentWidget() == window.note_detail_page
    assert window.current_note_id == note.id
    assert window.note_title_input.text() == "课程安排"

    window.close()


def test_transfer_assistant_page_lists_local_conversations(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.create_transfer_conversation(
        title="祥磊的 iPhone 对话",
        device_name="祥磊的 iPhone",
    )
    service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()

    window._show_transfer_page()

    assert window.pages.currentWidget() == window.transfer_page
    assert window.transfer_list.count() == 2
    assert window.transfer_status.text() == ""

    window.transfer_search.setText("报销")

    assert window.transfer_list.count() == 1

    window.close()


def test_transfer_conversation_opens_read_only_detail(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    service.close_transfer_conversation(conversation.id)
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()

    window._open_transfer_item(window.transfer_list.item(0))

    assert window.current_transfer_id == conversation.id
    assert window.pages.currentWidget() == window.transfer_detail_page
    assert window.transfer_detail_title.text() == "报销资料"
    assert "安卓手机" in window.transfer_detail_meta.text()
    assert "只读查看" in window.transfer_detail_notice.text()

    window._show_notes_page()
    window._show_transfer_page()

    assert window.pages.currentWidget() == window.transfer_detail_page

    window.close()


def test_transfer_detail_shows_attachment_list(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.IMAGE,
        filename="invoice.jpg",
        mime_type="image/jpeg",
        size_bytes=2048,
        storage_path="attachments/tc/invoice.jpg",
        sha256="abc123",
    )
    service.close_transfer_conversation(conversation.id)
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()
    window._open_transfer_item(window.transfer_list.item(0))

    window._show_current_transfer_attachments()

    assert "invoice.jpg" in window.transfer_detail_notice.text()
    assert "image/jpeg" in window.transfer_detail_notice.text()
    assert "2.0 KB" in window.transfer_detail_notice.text()

    window.close()


def test_transfer_detail_back_resets_transfer_module_to_list(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.create_transfer_conversation(title="报销资料", device_name="安卓手机")
    service.create_secure_note(name="课程安排", note="周一数学", category="学习")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()

    window._open_transfer_item(window.transfer_list.item(0))
    window._show_transfer_list_page()
    assert window.pages.currentWidget() == window.transfer_page

    window._show_notes_page()
    window._show_transfer_page()

    assert window.pages.currentWidget() == window.transfer_page

    window.close()


def test_connect_phone_waits_for_phone_before_creating_chat(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()

    window.connect_phone_button.click()

    assert window.transfer_server is not None
    assert window.pages.currentWidget() == window.transfer_connect_page
    assert window.current_transfer_id == ""
    assert window.transfer_list.count() == 1
    assert window.transfer_list.item(0).flags() == Qt.ItemFlag.NoItemFlags
    assert window.service.list_transfer_conversations() == []
    assert window.transfer_server.url.startswith("http://")
    assert window.transfer_server.display_url in window.transfer_connect_url_value.text()
    assert "给未信任或首次连接的手机使用" in window.transfer_connect_type_value.text()
    assert "验证码：" in window.transfer_connect_code_value.text()
    assert window.transfer_trusted_link_value.isHidden()

    with urlopen(
        f"{window.transfer_server.url}/?token={window.transfer_server.connection_token}",
        timeout=5,
    ):
        pass
    request = Request(
        f"{window.transfer_server.url}/api/pair",
        data=json.dumps(
            {
                "token": window.transfer_server.connection_token,
                "code": window.transfer_server.verification_code,
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5):
        pass
    window._check_transfer_pairing()

    assert window.pages.currentWidget() == window.transfer_chat_page
    assert window.current_transfer_id
    assert window.transfer_chat_title.text() == "手机对话"
    assert window.transfer_messages_view.toPlainText() == ""
    assert window.transfer_server.conversation_id == window.current_transfer_id

    window.transfer_server.stop()
    window.close()


def test_trusted_device_connection_has_separate_link_feedback(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window.profile_settings.trusted_transfer_devices.append(
        {
            "id": "td_phone",
            "name": "IQOO12",
            "last_connected_at": "2026-05-09T22:46:01+08:00",
        }
    )
    window._show_transfer_page()
    window.connect_phone_button.click()

    window.transfer_trusted_list.setCurrentRow(0)
    window.transfer_trusted_connect_button.click()

    assert window.transfer_server is not None
    assert window.transfer_connect_url_value.text() == "未启动新手机连接"
    assert "可信设备：IQOO12" in window.transfer_trusted_link_title.text()
    assert window.transfer_server.display_url in window.transfer_trusted_link_value.text()
    assert not window.transfer_trusted_link_value.isHidden()
    assert "等待 IQOO12 打开可信设备链接" in window.transfer_trusted_status.text()

    window._copy_transfer_link()
    assert "可信设备链接已复制" in window.transfer_trusted_status.text()

    window.transfer_server.stop()
    window.close()


def test_transfer_chat_sends_text_and_closes_to_history(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()
    _pair_transfer_phone(window)

    window.transfer_message_input.setPlainText("电脑发来的资料说明")
    window.transfer_send_button.click()

    assert "电脑" in window.transfer_messages_view.toPlainText()
    assert "电脑发来的资料说明" in window.transfer_messages_view.toPlainText()
    assert window.transfer_message_input.toPlainText() == ""

    window.transfer_close_button.click()

    conversation = window.service.get_transfer_conversation(window.current_transfer_id)
    assert conversation.message_count == 1
    assert conversation.status.value == "closed"
    assert window.pages.currentWidget() == window.transfer_page
    assert window.transfer_list.count() == 1

    window._open_transfer_item(window.transfer_list.item(0))
    assert "电脑发来的资料说明" in window.transfer_detail_messages_view.toPlainText()
    assert "只读查看" in window.transfer_detail_notice.text()

    window.close()


def test_transfer_chat_does_not_expose_message_editing(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()
    _pair_transfer_phone(window)
    window.transfer_message_input.setPlainText("旧内容")
    window.transfer_send_button.click()

    messages = window.service.list_transfer_messages(window.current_transfer_id)

    assert len(messages) == 1
    assert messages[0].text == "旧内容"
    assert not hasattr(window, "transfer_edit_last_button")
    assert "编辑消息" not in [
        window.transfer_send_button.text(),
        window.transfer_send_file_button.text(),
    ]

    window.transfer_server.stop()
    window.close()


def test_transfer_server_phone_message_appears_in_current_chat(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()
    _pair_transfer_phone(window)

    request = Request(
        f"{window.transfer_server.url}/api/messages",
        data=json.dumps({"text": "手机同步过来的消息"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5):
        pass

    window._show_transfer_chat(window.current_transfer_id)

    assert "手机" in window.transfer_messages_view.toPlainText()
    assert "手机同步过来的消息" in window.transfer_messages_view.toPlainText()

    window.transfer_server.stop()
    window.close()


def test_active_transfer_chat_refreshes_phone_message_without_reopening(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()
    _pair_transfer_phone(window)

    window.service.add_transfer_text_message(
        window.current_transfer_id,
        sender=TransferMessageSender.PHONE,
        text="自动刷新消息",
    )

    assert "自动刷新消息" not in window.transfer_messages_view.toPlainText()

    window._refresh_active_transfer_chat()

    assert "自动刷新消息" in window.transfer_messages_view.toPlainText()
    assert "消息 1" in window.transfer_chat_meta.text()

    window.transfer_server.stop()
    window.close()


def test_active_transfer_chat_returns_to_list_when_phone_closes(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()
    _pair_transfer_phone(window)

    window.service.close_transfer_conversation(window.current_transfer_id)

    window._refresh_active_transfer_chat()

    assert window.pages.currentWidget() == window.transfer_chat_page
    assert not window.transfer_refresh_timer.isActive()
    window._show_transfer_list_page()
    assert window.transfer_list.count() == 1
    conversation = window.service.get_transfer_conversation(window.current_transfer_id)
    assert conversation.status.value == "closed"

    window.transfer_server.stop()
    window.close()


def test_transfer_chat_disables_input_for_closed_conversation(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()
    _pair_transfer_phone(window)

    window.service.close_transfer_conversation(window.current_transfer_id)
    window._show_transfer_chat(window.current_transfer_id)

    assert not window.transfer_message_input.isEnabled()
    assert not window.transfer_send_button.isEnabled()
    assert not hasattr(window, "transfer_edit_last_button")

    window.transfer_server.stop()
    window.close()


def test_active_transfer_chat_refreshes_attachment_summary(
    vault_path: Path,
    monkeypatch,
    tmp_path,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()
    _pair_transfer_phone(window)
    window.service.add_transfer_attachment_message(
        window.current_transfer_id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.FILE,
        filename="invoice.pdf",
        mime_type="application/pdf",
        size_bytes=4096,
        storage_path=str(tmp_path / "invoice.pdf"),
        sha256="abc123",
    )

    window._refresh_active_transfer_chat()

    assert "[附件] invoice.pdf" in window.transfer_messages_view.toPlainText()
    assert "附件 1" in window.transfer_chat_meta.text()

    window.transfer_server.stop()
    window.close()


def test_transfer_refresh_timer_runs_only_on_active_chat(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()

    assert not window.transfer_refresh_timer.isActive()

    _pair_transfer_phone(window)
    assert window.transfer_refresh_timer.isActive()

    window._show_transfer_list_page()
    assert not window.transfer_refresh_timer.isActive()

    window.transfer_server.stop()
    window.close()


def test_sidebar_navigation_preserves_active_transfer_chat(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.create_secure_note(name="课程安排", note="周一数学", category="学习")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()
    _pair_transfer_phone(window)

    window.transfer_message_input.setPlainText("保留这次对话")
    window.transfer_send_button.click()

    window._show_notes_page()
    window._show_transfer_page()

    assert window.pages.currentWidget() == window.transfer_chat_page
    assert "保留这次对话" in window.transfer_messages_view.toPlainText()

    window.close()


def test_transfer_chat_exports_session_note_from_organize_menu(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()
    _pair_transfer_phone(window)
    window.transfer_message_input.setPlainText("发票图片稍后发你")
    window.transfer_send_button.click()

    window._export_current_transfer_to_note()

    conversation = window.service.get_transfer_conversation(window.current_transfer_id)
    note = window.service.get_record(conversation.note_id)
    assert note.category == "会话"
    assert "发票图片稍后发你" in note.note
    assert "已转存为小纸条" in window.transfer_chat_meta.text()

    window.transfer_message_input.setPlainText("后续自动追加")
    window.transfer_send_button.click()
    note = window.service.get_record(conversation.note_id)
    assert "后续自动追加" in note.note

    window._show_notes_page()
    assert window.note_list.count() == 1

    window.close()


def test_transfer_chat_shows_attachment_summary(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.FILE,
        filename="invoice.pdf",
        mime_type="application/pdf",
        size_bytes=4096,
        storage_path="attachments/tc/invoice.pdf",
        sha256="abc123",
    )
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()
    window._open_transfer_item(window.transfer_list.item(0))

    window._show_current_transfer_attachments()

    assert window.pages.currentWidget() == window.transfer_chat_page
    assert "invoice.pdf" in window.transfer_chat_meta.text()
    assert "4.0 KB" in window.transfer_chat_meta.text()

    window.close()


def test_transfer_attachments_download_to_default_dir(
    vault_path: Path,
    monkeypatch,
    tmp_path,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    source = tmp_path / "source" / "invoice.pdf"
    source.parent.mkdir()
    source.write_text("pdf data", encoding="utf-8")
    download_dir = tmp_path / "downloads"
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.FILE,
        filename="invoice.pdf",
        mime_type="application/pdf",
        size_bytes=source.stat().st_size,
        storage_path=str(source),
        sha256="abc123",
    )
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window.settings = replace(window.settings, transfer_download_dir=download_dir)
    window._show_transfer_page()
    window._open_transfer_item(window.transfer_list.item(0))

    window._download_current_transfer_attachments()

    assert (download_dir / "invoice.pdf").read_text(encoding="utf-8") == "pdf data"
    assert "已下载 1 个附件" in window.transfer_chat_meta.text()
    assert window.service.list_download_history()[0].filename == "invoice.pdf"

    window.close()


def test_transfer_detail_downloads_attachments(
    vault_path: Path,
    monkeypatch,
    tmp_path,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    source = tmp_path / "source" / "invoice.pdf"
    source.parent.mkdir()
    source.write_text("pdf data", encoding="utf-8")
    download_dir = tmp_path / "downloads"
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.FILE,
        filename="invoice.pdf",
        mime_type="application/pdf",
        size_bytes=source.stat().st_size,
        storage_path=str(source),
        sha256="abc123",
    )
    service.close_transfer_conversation(conversation.id)
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window.settings = replace(window.settings, transfer_download_dir=download_dir)
    window._show_transfer_page()
    window._open_transfer_item(window.transfer_list.item(0))

    window._download_current_transfer_attachments()

    assert (download_dir / "invoice.pdf").exists()
    assert window.transfer_detail_notice.text() == "已下载 1 个附件"

    window.close()


def test_transfer_image_attachment_opens_preview(
    vault_path: Path,
    monkeypatch,
    tmp_path,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    image_path = tmp_path / "invoice.png"
    pixmap = QPixmap(2, 2)
    pixmap.fill(QColor("#2563eb"))
    assert pixmap.save(str(image_path), "PNG")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.IMAGE,
        filename="invoice.png",
        mime_type="image/png",
        size_bytes=image_path.stat().st_size,
        storage_path=str(image_path),
        sha256="abc123",
    )
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()
    window._open_transfer_item(window.transfer_list.item(0))

    window._preview_first_transfer_image()

    assert window.image_preview_dialog.windowTitle() == "invoice.png"
    assert not window.image_preview_pixmap.isNull()

    window.image_preview_dialog.close()
    window.close()


def test_transfer_image_preview_reports_missing_source(
    vault_path: Path,
    monkeypatch,
    tmp_path,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.IMAGE,
        filename="missing.png",
        mime_type="image/png",
        size_bytes=100,
        storage_path=str(tmp_path / "missing.png"),
        sha256="abc123",
    )
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()
    window._open_transfer_item(window.transfer_list.item(0))

    window._preview_first_transfer_image()

    assert "图片文件不存在" in window.transfer_chat_meta.text()

    window.close()


def test_transfer_image_preview_ignores_non_image_attachment(
    vault_path: Path,
    monkeypatch,
    tmp_path,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    source = tmp_path / "invoice.pdf"
    source.write_text("pdf", encoding="utf-8")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.FILE,
        filename="invoice.pdf",
        mime_type="application/pdf",
        size_bytes=source.stat().st_size,
        storage_path=str(source),
        sha256="abc123",
    )
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_transfer_page()
    window._open_transfer_item(window.transfer_list.item(0))

    window._preview_first_transfer_image()

    assert "当前会话没有图片附件" in window.transfer_chat_meta.text()

    window.close()


def test_settings_show_transfer_download_defaults_and_history(
    vault_path: Path,
    monkeypatch,
    tmp_path,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    message, attachment = service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.FILE,
        filename="invoice.pdf",
        mime_type="application/pdf",
        size_bytes=4096,
        storage_path="attachments/tc/invoice.pdf",
        sha256="abc123",
    )
    saved_path = tmp_path / "invoice.pdf"
    saved_path.write_text("pdf", encoding="utf-8")
    service.record_transfer_download(
        conversation_id=conversation.id,
        message_id=message.id,
        attachment_id=attachment.id,
        filename=attachment.filename,
        saved_path=saved_path,
        size_bytes=attachment.size_bytes,
    )
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_settings_page()

    assert "Downloads" in window.transfer_download_dir_label.text()
    assert "SafeBox" in window.transfer_download_dir_label.text()

    window._show_download_history_page()

    assert window.pages.currentWidget() == window.download_history_page
    assert window.download_history_list.count() == 1
    assert "invoice.pdf" in window.download_history_status.text()
    assert "文件存在" in window.download_history_status.text()

    saved_path.unlink()
    window._refresh_download_history()

    assert "文件不存在" in window.download_history_status.text()

    window._delete_selected_download_history()
    assert window.download_history_list.count() == 1

    window._clear_download_history()
    assert window.download_history_status.text() == "下载历史为空"

    window.close()


def test_settings_can_change_transfer_download_directory(
    vault_path: Path,
    monkeypatch,
    tmp_path,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()
    download_dir = tmp_path / "SafeBoxDownloads"

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    monkeypatch.setattr(
        main_window.QFileDialog,
        "getExistingDirectory",
        lambda *args, **kwargs: str(download_dir),
    )
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()

    window._choose_transfer_download_dir()

    assert window.settings.transfer_download_dir == download_dir
    assert str(download_dir) in window.transfer_download_dir_label.text()
    assert (
        load_profile_settings(base_dir, "于祥磊").transfer_download_dir
        == str(download_dir)
    )

    window.close()


def test_main_window_starts_with_embedded_login_page(qt_app) -> None:
    window = MainWindow(lambda name: VaultService(Path(":memory:")))

    assert window.pages.currentWidget() == window.login_page
    assert window.sidebar.isHidden()
    assert window.login_vault_name.text()
    assert window.login_password.placeholderText() == "输入保险箱密码"
    assert window.login_page.parent() is window.pages
    assert window.login_shell.maximumWidth() >= 700
    assert window.login_form_panel.objectName() == "LoginFormPanel"

    window.close()


def test_sidebar_returns_after_embedded_login_success(vault_path: Path, qt_app) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window.profile_base_dir = base_dir
    window.login_vault_name.setText("于祥磊")
    window.login_password.setText("wojiao321.")

    window._open_vault_from_login()

    assert window.pages.currentWidget() == window.accounts_page
    assert not window.sidebar.isHidden()

    window.close()


def test_embedded_login_error_shows_status(qt_app) -> None:
    window = MainWindow(lambda name: VaultService(Path(":memory:")))

    window.login_password.setText("")
    window._open_vault_from_login()

    assert not window.login_status.isHidden()
    assert window.login_status.text()
    assert window.pages.currentWidget() == window.login_page

    window.close()


def test_embedded_login_wrong_password_shows_toast(vault_path: Path, qt_app) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window.profile_base_dir = base_dir
    window.login_vault_name.setText("于祥磊")
    window.login_password.setText("wrong-password")

    window._open_vault_from_login()

    assert not window.login_status.isHidden()
    assert window.toast_notice is not None
    assert not window.toast_notice.isHidden()
    assert window.toast_notice.text()
    assert window.pages.currentWidget() == window.login_page

    window.close()


def test_remembered_password_prefills_and_opens_vault(vault_path: Path, qt_app) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window.profile_base_dir = base_dir
    window.login_vault_name.setText("于祥磊")
    window.login_password.setText("wojiao321.")
    window.remember_password_check.setChecked(True)

    window._open_vault_from_login()
    window._lock()

    assert window.remember_password_check.isChecked()
    assert window.login_password.text() == "wojiao321."

    window._open_vault_from_login()

    assert window.pages.currentWidget() == window.accounts_page
    assert not window.sidebar.isHidden()

    window.close()


def test_transfer_organize_menu_opens_download_history_dialog(qt_app) -> None:
    window = MainWindow(lambda name: VaultService(Path(":memory:")))
    actions = {
        action.text(): action
        for action in window.transfer_organize_menu.actions()
    }

    assert "查看下载记录" in actions
    assert "下载全部附件" not in actions

    opened = []
    original = window._show_download_history_dialog
    try:
        window._show_download_history_dialog = lambda: opened.append(True)
        actions["查看下载记录"].trigger()
    finally:
        window._show_download_history_dialog = original

    assert opened == [True]
    window.close()


def test_download_history_page_opens_folder_and_deletes_selected_files(
    vault_path: Path,
    monkeypatch,
    tmp_path,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    first_message, first_attachment = service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.FILE,
        filename="invoice.pdf",
        mime_type="application/pdf",
        size_bytes=3,
        storage_path="attachments/tc/invoice.pdf",
        sha256="abc123",
    )
    second_message, second_attachment = service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.FILE,
        filename="receipt.txt",
        mime_type="text/plain",
        size_bytes=4,
        storage_path="attachments/tc/receipt.txt",
        sha256="def456",
    )
    download_dir = tmp_path / "downloads"
    first_path = download_dir / "invoice.pdf"
    second_path = download_dir / "receipt.txt"
    download_dir.mkdir()
    first_path.write_text("pdf", encoding="utf-8")
    second_path.write_text("text", encoding="utf-8")
    service.record_transfer_download(
        conversation_id=conversation.id,
        message_id=first_message.id,
        attachment_id=first_attachment.id,
        filename=first_attachment.filename,
        saved_path=first_path,
        size_bytes=first_attachment.size_bytes,
    )
    service.record_transfer_download(
        conversation_id=conversation.id,
        message_id=second_message.id,
        attachment_id=second_attachment.id,
        filename=second_attachment.filename,
        saved_path=second_path,
        size_bytes=second_attachment.size_bytes,
    )
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window.settings = replace(window.settings, transfer_download_dir=download_dir)
    opened_paths: list[str] = []
    monkeypatch.setattr(
        window,
        "_open_local_path",
        lambda path, status=None: opened_paths.append(str(path)),
    )

    window._show_download_history_page()
    page_buttons = window.download_history_page.findChildren(main_window.QPushButton)
    assert any(button.text() == "删除文件" for button in page_buttons)
    assert any(button.text() == "打开文件夹" for button in page_buttons)

    window._open_transfer_download_folder()
    assert opened_paths[-1] == str(download_dir)

    window._open_download_history_item(window.download_history_list.item(0))
    assert opened_paths[-1] == str(first_path)

    window.batch_modes["download_history"] = True
    window._apply_batch_mode("download_history", window.download_history_list)
    window.download_history_list.item(0).setSelected(True)
    window.download_history_list.item(1).setSelected(True)
    window._delete_selected_download_history_files()

    assert not first_path.exists()
    assert not second_path.exists()
    assert len(window.service.list_download_history()) == 2
    window._refresh_download_history()
    assert "文件不存在" in window.download_history_status.text()

    window.close()


def test_download_history_dialog_supports_multi_select_delete_files_and_open_folder(
    vault_path: Path,
    monkeypatch,
    tmp_path,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    first_message, first_attachment = service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.FILE,
        filename="invoice.pdf",
        mime_type="application/pdf",
        size_bytes=3,
        storage_path="attachments/tc/invoice.pdf",
        sha256="abc123",
    )
    second_message, second_attachment = service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.FILE,
        filename="receipt.txt",
        mime_type="text/plain",
        size_bytes=4,
        storage_path="attachments/tc/receipt.txt",
        sha256="def456",
    )
    download_dir = tmp_path / "downloads"
    first_path = download_dir / "invoice.pdf"
    second_path = download_dir / "receipt.txt"
    download_dir.mkdir()
    first_path.write_text("pdf", encoding="utf-8")
    second_path.write_text("text", encoding="utf-8")
    service.record_transfer_download(
        conversation_id=conversation.id,
        message_id=first_message.id,
        attachment_id=first_attachment.id,
        filename=first_attachment.filename,
        saved_path=first_path,
        size_bytes=first_attachment.size_bytes,
    )
    service.record_transfer_download(
        conversation_id=conversation.id,
        message_id=second_message.id,
        attachment_id=second_attachment.id,
        filename=second_attachment.filename,
        saved_path=second_path,
        size_bytes=second_attachment.size_bytes,
    )
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window.settings = replace(window.settings, transfer_download_dir=download_dir)
    opened_paths: list[str] = []
    monkeypatch.setattr(
        window,
        "_open_local_path",
        lambda path, status=None: opened_paths.append(str(path)),
    )

    window._show_download_history_dialog()
    dialog = window.download_history_dialog
    buttons = {button.text(): button for button in dialog.findChildren(main_window.QPushButton)}
    list_widget = dialog.findChild(main_window.QListWidget)

    assert "多选" in buttons
    assert "删除文件" in buttons
    assert "打开文件夹" in buttons
    assert list_widget is not None

    buttons["打开文件夹"].click()
    assert opened_paths[-1] == str(download_dir)

    list_widget.itemDoubleClicked.emit(list_widget.item(0))
    assert opened_paths[-1] == str(first_path)

    buttons["多选"].click()
    assert list_widget.selectionMode() == main_window.QAbstractItemView.SelectionMode.MultiSelection
    list_widget.item(0).setSelected(True)
    list_widget.item(1).setSelected(True)
    buttons["删除文件"].click()

    assert not first_path.exists()
    assert not second_path.exists()
    assert len(window.service.list_download_history()) == 2

    dialog.close()
    window.close()


def test_explicit_back_resets_account_module_to_list(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.create_account(
        name="教务系统",
        account="student-user",
        password="secret",
        category="学校",
    )
    service.create_secure_note(name="课程安排", note="周一数学", category="学习")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()

    window._open_account_item(window.account_list.item(0))
    window._show_accounts_list_page()
    assert window.pages.currentWidget() == window.accounts_page

    window._show_notes_page()
    window._show_accounts_page()
    assert window.pages.currentWidget() == window.accounts_page

    window.close()


def test_deleting_current_account_resets_accounts_module_to_list(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.create_account(
        name="教务系统",
        account="student-user",
        password="secret",
        category="学校",
    )
    service.create_secure_note(name="课程安排", note="周一数学", category="学习")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    monkeypatch.setattr(
        main_window.QMessageBox,
        "question",
        lambda *args, **kwargs: main_window.QMessageBox.StandardButton.Yes,
    )
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()

    window._open_account_item(window.account_list.item(0))
    window._delete_current_account()
    assert window.pages.currentWidget() == window.accounts_page

    window._show_notes_page()
    window._show_accounts_page()
    assert window.pages.currentWidget() == window.accounts_page

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
    assert window.transfer_nav.text() == "传输助手"
    assert window.trash_nav.parent().objectName() == "ManagementNavGroup"
    assert window.settings_nav.parent().objectName() == "ManagementNavGroup"
    assert window.minimumSizeHint().height() <= 720

    window.resize(1120, 720)
    window.sidebar.setVisible(True)
    window.show()
    qt_app.processEvents()
    transfer_bottom = window.transfer_nav.mapTo(
        window,
        window.transfer_nav.rect().bottomLeft(),
    ).y()
    trash_top = window.trash_nav.mapTo(window, window.trash_nav.rect().topLeft()).y()
    nav_bottom = window.settings_nav.mapTo(window, window.settings_nav.rect().bottomLeft()).y()
    assert trash_top - transfer_bottom >= 120
    assert nav_bottom < window.height()

    window.close()


def test_settings_can_switch_and_persist_ui_theme(vault_path: Path, monkeypatch, qt_app) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()

    assert window.theme_combo.currentData() == "classic"

    window.theme_combo.setCurrentText("Linear Dark")

    assert window.active_theme_name == "linear_dark"
    assert "near-black graphite" in qt_app.styleSheet()
    assert load_profile_settings(base_dir, "于祥磊").theme_name == "linear_dark"

    window.theme_combo.setCurrentText("经典")

    assert window.active_theme_name == "classic"
    assert "near-black graphite" not in qt_app.styleSheet()

    window.close()


def test_home_header_uses_project_bundled_brand_mark(qt_app) -> None:
    window = MainWindow(lambda name: VaultService(Path(":memory:")))

    assert SAFEBOX_NAV_MARK_PATH.is_file()
    assert window.header_brand_mark.pixmap() is not None
    assert window.header_brand_mark.layoutDirection().name == "LeftToRight"
    assert window.header_brand_mark.parent() is window.header_brand

    window.close()


def test_settings_can_disable_and_customize_auto_lock(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()

    window.auto_lock_combo.setCurrentText("从不锁定")
    assert not window.idle_timer.isActive()
    assert load_profile_settings(base_dir, "于祥磊").auto_lock_seconds == 0

    window.auto_lock_combo.setCurrentText("自定义")
    window.custom_auto_lock_minutes.setValue(13)
    assert window.idle_timer.interval() == 13 * 60 * 1000
    assert window.idle_timer.isActive()
    assert load_profile_settings(base_dir, "于祥磊").auto_lock_seconds == 13 * 60

    window.auto_lock_combo.setCurrentText("20分钟")
    assert window.idle_timer.interval() == 20 * 60 * 1000
    assert load_profile_settings(base_dir, "于祥磊").auto_lock_seconds == 20 * 60

    window.close()


def test_new_note_defaults_to_body_font_size(vault_path: Path, monkeypatch, qt_app) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()

    window._new_note()
    record = window.service.get_record(window.current_note_id)

    assert f"font-size:{NOTE_BODY_FONT_SIZE_PT}pt" in record.note
    assert window.note_font_size.currentText() == str(NOTE_BODY_FONT_SIZE_PT)

    window.close()


def test_note_toolbar_keeps_format_brush_and_font_size_compact(qt_app) -> None:
    window = MainWindow(lambda name: VaultService(Path(":memory:")))

    assert window.note_export_button.objectName() == "SubtleButton"
    assert window.note_export_menu.actions()[0].text() == "导出 TXT"
    assert window.note_export_menu.actions()[1].text() == "导出 Markdown"
    assert window.note_export_menu.actions()[2].text() == "导出 PDF"
    assert window.note_format_brush_button.objectName() == "FormatButton"
    assert not window.note_format_brush_button.text()
    assert not window.note_format_brush_button.icon().isNull()
    assert window.note_format_buttons[0] is window.note_format_brush_button
    assert not window.note_align_left_button.icon().isNull()
    assert not window.note_align_center_button.icon().isNull()
    assert not window.note_align_right_button.icon().isNull()
    assert window.note_color_red_button.objectName() == "ColorButtonRed"
    assert window.note_font_size.objectName() == "FontSizeCombo"
    assert window.note_font_size.currentText() == str(NOTE_BODY_FONT_SIZE_PT)
    assert window.note_font_size.minimumWidth() <= 70

    window.close()


def test_note_detail_edits_directly_tracks_dirty_and_prompts_on_back(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.create_secure_note(name="课程安排", note="周一数学", category="学习")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_notes_page()
    window._open_note_item(window.note_list.item(0))

    assert not window.note_body.isReadOnly()
    assert not window.note_title_input.isReadOnly()
    assert not window.note_dirty

    window.note_body.setPlainText("周一数学\n周二英语")

    assert window.note_dirty
    assert "*" in window.note_save_button.text()
    assert window.pages.currentWidget() == window.note_detail_page

    monkeypatch.setattr(
        main_window.QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.No,
    )
    window._show_notes_list_page()
    assert window.pages.currentWidget() == window.note_detail_page

    monkeypatch.setattr(
        main_window.QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )
    window._show_notes_list_page()
    assert window.pages.currentWidget() == window.notes_page

    saved = window.service.get_record(window.current_note_id)
    assert "周二英语" not in saved.note

    window.close()


def test_note_ctrl_s_saves_dirty_content(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.create_secure_note(name="课程安排", note="周一数学", category="学习")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_notes_page()
    window._open_note_item(window.note_list.item(0))
    window.note_body.setPlainText("周一数学\n周二英语")

    window.note_save_shortcut.activated.emit()

    saved = window.service.get_record(window.current_note_id)
    assert "周二英语" in saved.note
    assert not window.note_dirty
    window._show_notes_list_page()
    assert window.pages.currentWidget() == window.notes_page

    window.close()


def test_note_export_writes_txt_md_and_pdf_files(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    note = window.service.create_secure_note(
        name='课程/安排:第1版',
        note="<h1>课程安排</h1><p><strong>周一数学</strong><br>周二英语</p>",
        category="学习",
    )
    window.current_note_id = note.id
    window._render_note_detail(note)

    txt_path = vault_path.with_name("note.txt")
    md_path = vault_path.with_name("note.md")
    pdf_path = vault_path.with_name("note.pdf")

    window._write_note_export(note, txt_path)
    window._write_note_export(note, md_path)
    window._write_note_export(note, pdf_path)

    assert "课程安排" in txt_path.read_text(encoding="utf-8")
    assert "周一数学" in txt_path.read_text(encoding="utf-8")
    markdown = md_path.read_text(encoding="utf-8")
    assert "课程安排" in markdown
    assert "周一数学" in markdown
    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert _safe_export_filename(note.name, ".pdf") == "课程_安排_第1版.pdf"

    window.close()


def test_account_export_writes_txt_md_and_pdf_files(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.create_account(
        name="校园账号",
        account="student",
        password="secret",
        category="学校",
        entry_hint="官网入口",
        note="期末前检查",
    )
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._show_accounts_page()
    window._open_account_item(window.account_list.item(0))
    record = window.service.get_record(window.current_account_id)

    assert window.account_export_button.objectName() == "SubtleButton"
    assert window.account_export_menu.actions()[0].text() == "导出 TXT"
    assert window.account_export_menu.actions()[1].text() == "导出 Markdown"
    assert window.account_export_menu.actions()[2].text() == "导出 PDF"

    txt_path = vault_path.with_name("account.txt")
    md_path = vault_path.with_name("account.md")
    pdf_path = vault_path.with_name("account.pdf")

    window._write_record_export(record, txt_path)
    window._write_record_export(record, md_path)
    window._write_record_export(record, pdf_path)

    txt = txt_path.read_text(encoding="utf-8")
    assert "校园账号" in txt
    assert "student" in txt
    assert "secret" in txt
    markdown = md_path.read_text(encoding="utf-8")
    assert "校园账号" in markdown
    assert "期末前检查" in markdown
    assert pdf_path.read_bytes().startswith(b"%PDF")

    window.close()


def test_account_detail_refresh_clears_previous_export_notice(
    qt_app,
) -> None:
    window = MainWindow(lambda name: VaultService(Path(":memory:")))
    record = Record(
        id="account-1",
        type=RecordType.ACCOUNT,
        name="邮箱一",
        account="first@example.com",
        password="secret1",
        category="邮箱",
    )

    window.account_save_notice.setText("已导出 邮箱一.pdf")
    window.account_save_notice.setVisible(True)
    assert not window.account_save_notice.isHidden()

    window._render_account_detail(record)

    assert window.account_save_notice.isHidden()
    assert window.account_save_notice.text() == "保存成功"

    window.close()


def test_note_export_action_saves_dirty_editor_before_export(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._new_note()
    window.note_title_input.setText("导出前保存")
    window.note_body.setPlainText("还没点保存的内容")

    export_path = vault_path.with_name("autosaved.txt")
    monkeypatch.setattr(window, "_choose_note_export_path", lambda record, suffix: export_path)

    window._export_current_note_as(".txt")

    saved = window.service.get_record(window.current_note_id)
    assert saved.name == "导出前保存"
    assert "还没点保存的内容" in saved.note
    assert export_path.read_text(encoding="utf-8").strip() == "还没点保存的内容"

    window.close()


def test_note_export_action_stops_when_dirty_note_title_is_empty(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "于祥磊")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    monkeypatch.setattr(main_window, "VaultOpenDialog", FakeVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    monkeypatch.setattr(main_window.QMessageBox, "warning", lambda *args: None)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._new_note()
    window.note_title_input.setText("")
    chosen = []
    monkeypatch.setattr(
        window,
        "_choose_note_export_path",
        lambda record, suffix: chosen.append((record, suffix)),
    )

    window._export_current_note_as(".txt")

    assert chosen == []

    window.close()


def test_note_export_uses_dialog_filter_suffix() -> None:
    assert _note_export_suffix_for_choice("", "Markdown 文件 (*.md)", ".pdf") == ".md"
    assert _note_export_suffix_for_choice(".TXT", "PDF 文件 (*.pdf)", ".pdf") == ".txt"
    assert _note_export_suffix_for_choice("", "文本文件 (*.txt)", ".pdf") == ".txt"


def test_close_window_can_remember_hide_to_tray_choice(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    class CloseEvent:
        def __init__(self) -> None:
            self.accepted = False
            self.ignored = False

        def accept(self) -> None:
            self.accepted = True

        def ignore(self) -> None:
            self.ignored = True

    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "test-vault")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    class TestVaultOpenDialog:
        def __init__(self, parent=None) -> None:
            pass

        def exec(self) -> bool:
            return True

        def values(self) -> tuple[str, str, str, str]:
            return ("test-vault", "wojiao321.", "", "open")

    monkeypatch.setattr(main_window, "VaultOpenDialog", TestVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    monkeypatch.setattr(window, "_prompt_window_close_action", lambda: ("tray", True))
    hidden = []
    monkeypatch.setattr(window, "_hide_to_tray", lambda: hidden.append(True))

    event = CloseEvent()
    window.closeEvent(event)

    assert hidden == [True]
    assert event.ignored
    assert not event.accepted
    assert load_profile_settings(base_dir, "test-vault").window_close_action == "tray"

    window._close_action_override = "exit"
    window.close()


def test_named_buttons_have_hover_and_pressed_feedback() -> None:
    required_selectors = [
        "QPushButton#SubtleButton:hover",
        "QPushButton#SubtleButton:pressed",
        "QPushButton#PrimaryButton:pressed",
        "QPushButton#DangerButton:pressed",
        "QPushButton#FormatButton:pressed",
        "QPushButton#FormatButtonWide:pressed",
    ]

    for selector in required_selectors:
        assert selector in LIGHT_FLUENT_QSS


def test_note_font_size_control_applies_selected_size(qt_app) -> None:
    window = MainWindow(lambda name: VaultService(Path(":memory:")))
    window.note_body.setPlainText("hello")
    cursor = window.note_body.textCursor()
    cursor.select(cursor.SelectionType.Document)
    window.note_body.setTextCursor(cursor)

    window.note_font_size.setCurrentText("16")

    assert window.note_body.textCursor().charFormat().fontPointSize() == 16

    window.close()


def test_note_format_brush_copies_current_text_format(qt_app) -> None:
    window = MainWindow(lambda name: VaultService(Path(":memory:")))
    window.note_body.setPlainText("source target")
    cursor = window.note_body.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(6, cursor.MoveMode.KeepAnchor)
    window.note_body.setTextCursor(cursor)
    window._set_text_size(18)
    window._set_text_color("#2563eb")

    window._capture_note_format()
    cursor = window.note_body.textCursor()
    cursor.setPosition(7)
    cursor.setPosition(13, cursor.MoveMode.KeepAnchor)
    window.note_body.setTextCursor(cursor)
    window._apply_note_format_brush()

    applied = window.note_body.textCursor().charFormat()
    assert applied.fontPointSize() == 18
    assert applied.foreground().color().name() == "#2563eb"
    assert window.note_format_brush is None

    window.close()


def test_note_editor_keyboard_shortcuts_apply_word_like_formatting(qt_app) -> None:
    window = MainWindow(lambda name: VaultService(Path(":memory:")))
    window.note_body.setPlainText("hello")
    cursor = window.note_body.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    window.note_body.setTextCursor(cursor)

    window.note_body.keyPressEvent(
        QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_B,
            Qt.KeyboardModifier.ControlModifier,
        )
    )

    assert window.note_body.textCursor().charFormat().fontWeight() > 400

    window.close()


def test_note_editor_inserts_clipboard_image_as_embedded_html(qt_app) -> None:
    window = MainWindow(lambda name: VaultService(Path(":memory:")))
    image = QImage(8, 6, QImage.Format.Format_RGB32)
    image.fill(QColor("#2563eb"))
    mime_data = QMimeData()
    mime_data.setImageData(image)

    assert window.note_body.canInsertFromMimeData(mime_data)
    window.note_body.insertFromMimeData(mime_data)

    html = window.note_body.toHtml()
    assert "data:image/png;base64," in html
    assert "max-width:100%" in html

    window.close()


def test_save_current_note_keeps_rich_text_and_embedded_images(
    vault_path: Path,
    monkeypatch,
    qt_app,
) -> None:
    base_dir = vault_path.with_suffix("") / "SafeBoxData"
    vault_path = vault_path_for_name(base_dir, "test-vault")
    service = VaultService(vault_path)
    service.initialize("wojiao321.")
    service.lock()

    class TestVaultOpenDialog:
        def __init__(self, parent=None) -> None:
            pass

        def exec(self) -> bool:
            return True

        def values(self) -> tuple[str, str, str, str]:
            return ("test-vault", "wojiao321.", "", "open")

    monkeypatch.setattr(main_window, "VaultOpenDialog", TestVaultOpenDialog)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: base_dir)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(base_dir, name)))
    window._open_vault()
    window._new_note()
    window.note_title_input.setText("rich note")
    window.note_body.setHtml(
        '<p><strong>bold</strong></p><p><img src="data:image/png;base64,AA=="></p>'
    )

    window._save_current_note()

    saved = window.service.get_record(window.current_note_id)
    assert "font-weight" in saved.note or "<strong" in saved.note
    assert "data:image/png;base64,AA==" in saved.note

    window.close()
