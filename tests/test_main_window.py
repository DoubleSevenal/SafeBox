import json
from dataclasses import replace
from pathlib import Path
from urllib.request import Request, urlopen

from PySide6.QtGui import QColor, QPixmap

from safebox.core.services import VaultService
from safebox.core.transfer import TransferMessageKind, TransferMessageSender
from safebox.core.vault_profiles import load_profile_settings, vault_path_for_name
from safebox.ui import main_window
from safebox.ui.branding import SAFEBOX_NAV_MARK_PATH
from safebox.ui.main_window import NOTE_BODY_FONT_SIZE_PT, MainWindow
from safebox.ui.theme import LIGHT_FLUENT_QSS


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


def test_connect_phone_starts_current_transfer_chat(
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

    assert window.pages.currentWidget() == window.transfer_chat_page
    assert window.current_transfer_id
    assert window.transfer_chat_title.text() == "手机对话"
    assert window.transfer_messages_view.toPlainText() == ""
    assert window.transfer_server is not None
    assert window.transfer_server.url.startswith("http://")
    assert window.transfer_server.display_url in window.transfer_status.text()
    assert window.transfer_server.verification_code in window.transfer_status.text()

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
    window.connect_phone_button.click()

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
    assert "电脑发来的资料说明" in window.transfer_detail_body.toPlainText()
    assert "只读查看" in window.transfer_detail_notice.text()

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
    window.connect_phone_button.click()

    pair_request = Request(
        f"{window.transfer_server.url}/api/pair",
        data=json.dumps({"code": window.transfer_server.verification_code}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(pair_request, timeout=5):
        pass

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
    window.connect_phone_button.click()

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
    window.connect_phone_button.click()
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

    window.connect_phone_button.click()
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
    window.connect_phone_button.click()

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
    window.connect_phone_button.click()
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

    assert window.note_format_brush_button.objectName() == "FormatButton"
    assert not window.note_format_brush_button.text()
    assert not window.note_format_brush_button.icon().isNull()
    assert window.note_font_size.objectName() == "FontSizeCombo"
    assert window.note_font_size.currentText() == str(NOTE_BODY_FONT_SIZE_PT)
    assert window.note_font_size.minimumWidth() <= 70

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
