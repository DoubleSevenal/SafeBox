from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from pathlib import Path
from shutil import copy2
from subprocess import Popen
from typing import TYPE_CHECKING
from uuid import uuid4

from PySide6.QtCore import QBuffer, QEvent, QIODevice, QMarginsF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QIcon,
    QImage,
    QKeySequence,
    QPageLayout,
    QPageSize,
    QPdfWriter,
    QPixmap,
    QShortcut,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextListFormat,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from safebox.core.models import Record, RecordSummary, RecordType
from safebox.core.note_imports import (
    build_imported_note,
    note_plain_summary,
    read_import_text,
)
from safebox.core.record_sorting import (
    SORT_MODE_LABELS,
    SortMode,
    sorted_summaries,
)
from safebox.core.remembered_password import protect_password, unprotect_password
from safebox.core.services import try_unlock
from safebox.core.settings import AppSettings
from safebox.core.transfer import (
    TransferConversationStatus,
    TransferMessageKind,
    TransferMessageSender,
)
from safebox.core.vault_profiles import (
    VaultProfileSettings,
    app_data_dir,
    backup_file_for_vault,
    load_profile_settings,
    restore_vault_from_backup,
    save_profile_settings,
    sync_vault_to_backup,
)
from safebox.ui.branding import SAFEBOX_LOGIN_LOGO_PATH, SAFEBOX_NAV_MARK_PATH
from safebox.ui.clipboard import SecureClipboard
from safebox.ui.dialogs import (
    DEFAULT_VAULT_ID,
    NOTE_CATEGORIES,
    AccountDialog,
    ChangePasswordDialog,
    VaultOpenDialog,
    VaultOpenMode,
)
from safebox.ui.theme import THEME_LABELS, normalize_theme_name, stylesheet_for_theme

if TYPE_CHECKING:
    from safebox.net.transfer_server import TransferHttpServer

FORMAT_BRUSH_ICON_PATH = Path(__file__).resolve().parent / "assets" / "format-brush.svg"
ALIGN_LEFT_ICON_PATH = Path(__file__).resolve().parent / "assets" / "align-left.svg"
ALIGN_CENTER_ICON_PATH = Path(__file__).resolve().parent / "assets" / "align-center.svg"
ALIGN_RIGHT_ICON_PATH = Path(__file__).resolve().parent / "assets" / "align-right.svg"
NOTE_EXPORT_FILTERS = (
    "PDF 文件 (*.pdf);;"
    "Markdown 文件 (*.md);;"
    "文本文件 (*.txt)"
)
NOTE_EXPORT_SUFFIX_BY_FILTER = {
    "PDF 文件 (*.pdf)": ".pdf",
    "Markdown 文件 (*.md)": ".md",
    "文本文件 (*.txt)": ".txt",
}
AUTO_LOCK_PRESETS = {
    "5分钟": 5 * 60,
    "20分钟": 20 * 60,
    "从不锁定": 0,
}
NOTE_BODY_FONT_SIZE_PT = 13
NOTE_HEADING_FONT_SIZE_PT = 18
NOTE_IMAGE_MAX_WIDTH = 720


class NoteEditor(QTextEdit):
    formatShortcutRequested = Signal(str)
    imageInserted = Signal()

    def canInsertFromMimeData(self, source) -> bool:
        return self._image_from_mime(source) is not None or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source) -> None:
        image = self._image_from_mime(source)
        if image is not None:
            self._insert_image(image)
            self.imageInserted.emit()
            return
        super().insertFromMimeData(source)

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Bold):
            self.formatShortcutRequested.emit("bold")
            event.accept()
            return
        if event.matches(QKeySequence.StandardKey.Italic):
            self.formatShortcutRequested.emit("italic")
            event.accept()
            return
        if event.matches(QKeySequence.StandardKey.Underline):
            self.formatShortcutRequested.emit("underline")
            event.accept()
            return
        modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            key = event.key()
            shortcuts = {
                Qt.Key.Key_Minus: "clear",
                Qt.Key.Key_L: "align_left",
                Qt.Key.Key_E: "align_center",
                Qt.Key.Key_R: "align_right",
                Qt.Key.Key_7: "ordered_list",
                Qt.Key.Key_8: "bullet_list",
            }
            action = shortcuts.get(key)
            if action:
                self.formatShortcutRequested.emit(action)
                event.accept()
                return
        super().keyPressEvent(event)

    def _insert_image(self, image: QImage) -> None:
        scaled = image
        if image.width() > NOTE_IMAGE_MAX_WIDTH:
            scaled = image.scaledToWidth(
                NOTE_IMAGE_MAX_WIDTH,
                Qt.TransformationMode.SmoothTransformation,
            )
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        scaled.save(buffer, "PNG")
        encoded = bytes(buffer.data().toBase64()).decode("ascii")
        width = scaled.width()
        height = scaled.height()
        html = (
            '<img src="data:image/png;base64,'
            f'{encoded}" width="{width}" height="{height}" '
            'style="max-width:100%;height:auto;" />'
        )
        self.textCursor().insertHtml(html)

    def _image_from_mime(self, source) -> QImage | None:
        if not source.hasImage():
            return None
        image = source.imageData()
        if isinstance(image, QPixmap):
            image = image.toImage()
        if isinstance(image, QImage) and not image.isNull():
            return image
        return None


class WindowClosePrompt(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("关闭 SafeBox")
        self._choice: str = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(12)
        title = QLabel("关闭 SafeBox")
        title.setObjectName("DialogTitle")
        message = QLabel("你想退出程序，还是隐藏到电脑右下角？")
        message.setWordWrap(True)
        self.remember_choice = QCheckBox("记住我的选择")
        row = QHBoxLayout()
        self.exit_button = QPushButton("退出")
        self.exit_button.setObjectName("PrimaryButton")
        self.hide_button = QPushButton("隐藏到右下角")
        self.hide_button.setObjectName("SubtleButton")
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setObjectName("SubtleButton")
        row.addWidget(self.exit_button)
        row.addWidget(self.hide_button)
        row.addWidget(self.cancel_button)
        layout.addWidget(title)
        layout.addWidget(message)
        layout.addWidget(self.remember_choice)
        layout.addLayout(row)
        self.exit_button.clicked.connect(lambda: self._finish("exit"))
        self.hide_button.clicked.connect(lambda: self._finish("tray"))
        self.cancel_button.clicked.connect(self.reject)

    def choice(self) -> tuple[str, bool]:
        return self._choice, self.remember_choice.isChecked()

    def _finish(self, choice: str) -> None:
        self._choice = choice
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, service_factory) -> None:
        super().__init__()
        self.service_factory = service_factory
        self.vault_name = DEFAULT_VAULT_ID
        self.profile_base_dir = app_data_dir()
        self.profile_settings = VaultProfileSettings()
        self.active_theme_name = "classic"
        self.service = self.service_factory(self.vault_name)
        self.settings = AppSettings(vault_path=self.service.store.path)
        self.clipboard = SecureClipboard(self.settings.clipboard_clear_seconds)
        self.current_account_id = ""
        self.current_note_id = ""
        self.current_transfer_id = ""
        self.transfer_connect_mode = ""
        self.transfer_trusted_device_name = ""
        self.transfer_server: TransferHttpServer | None = None
        self.transfer_messages_signature = ""
        self.transfer_connect_info_rows: list[QFrame] = []
        self.active_nav_key = ""
        self._close_action_override: str = ""
        self.tray_icon: QSystemTrayIcon | None = None
        self._tray_available = False
        self.account_editing = False
        self.note_editing = False
        self.note_dirty = False
        self._saved_note_snapshot: tuple[str, str, str] = ("", "", "")
        self._loading_note_detail = False
        self.batch_modes: dict[str, bool] = {
            "accounts": False,
            "notes": False,
            "transfer": False,
            "download_history": False,
            "trash": False,
        }
        self.account_edit_widgets: dict[str, QLineEdit | QTextEdit | QComboBox] = {}
        self.note_format_buttons: list[QPushButton | QComboBox] = []
        self.note_format_brush: QTextCharFormat | None = None
        self.toast_notice: QLabel | None = None
        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(self.profile_settings.auto_lock_seconds * 1000)
        self.idle_timer.timeout.connect(self._lock)
        self.transfer_refresh_timer = QTimer(self)
        self.transfer_refresh_timer.setInterval(1000)
        self.transfer_refresh_timer.timeout.connect(self._refresh_active_transfer_chat)
        self.transfer_pair_timer = QTimer(self)
        self.transfer_pair_timer.setInterval(800)
        self.transfer_pair_timer.timeout.connect(self._check_transfer_pairing)
        self.setWindowTitle("SafeBox")
        self._build_ui()
        self.installEventFilter(self)
        QTimer.singleShot(0, self._show_login_page)

    def _build_ui(self) -> None:
        root = QWidget()
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(220)
        self.sidebar.setVisible(False)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(16, 18, 16, 16)
        self.header_brand = QFrame()
        self.header_brand.setObjectName("HeaderBrand")
        title_row = QHBoxLayout(self.header_brand)
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        title = QLabel("SafeBox")
        title.setObjectName("AppTitle")
        self.header_brand_mark = QLabel()
        self.header_brand_mark.setObjectName("BrandMarkSmall")
        self.header_brand_mark.setFixedSize(32, 32)
        self.header_brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_brand_mark.setPixmap(
            QPixmap(str(SAFEBOX_NAV_MARK_PATH)).scaled(
                32,
                32,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        title_row.addWidget(self.header_brand_mark)
        title_row.addWidget(title)
        title_row.addStretch()
        self.vault_subtitle = QLabel("保险箱ID：未打开")
        self.vault_subtitle.setObjectName("MutedText")
        self.vault_subtitle.setVisible(False)
        self.accounts_nav = QPushButton("账号密码")
        self.accounts_nav.setObjectName("NavButtonActive")
        self.notes_nav = QPushButton("小纸条")
        self.notes_nav.setObjectName("NavButton")
        self.transfer_nav = QPushButton("传输助手")
        self.transfer_nav.setObjectName("NavButton")
        self.trash_nav = QPushButton("回收站")
        self.trash_nav.setObjectName("NavButton")
        self.settings_nav = QPushButton("设置")
        self.settings_nav.setObjectName("NavButton")
        lock = QPushButton("锁定")
        lock.setObjectName("SubtleButton")
        management_nav = QFrame()
        management_nav.setObjectName("ManagementNavGroup")
        management_layout = QVBoxLayout(management_nav)
        management_layout.setContentsMargins(0, 0, 0, 0)
        management_layout.setSpacing(8)
        management_layout.addWidget(self.trash_nav)
        management_layout.addWidget(self.settings_nav)
        side_layout.addWidget(self.header_brand)
        side_layout.addSpacing(26)
        side_layout.addWidget(self.accounts_nav)
        side_layout.addWidget(self.notes_nav)
        side_layout.addWidget(self.transfer_nav)
        side_layout.addStretch()
        side_layout.addWidget(management_nav)
        side_layout.addSpacing(12)
        side_layout.addWidget(lock)

        self.pages = QStackedWidget()
        self.login_page = self._build_login_page()
        self.accounts_page = self._build_accounts_page()
        self.account_detail_page = self._build_account_detail_page()
        self.notes_page = self._build_notes_page()
        self.note_detail_page = self._build_note_detail_page()
        self.transfer_page = self._build_transfer_page()
        self.transfer_connect_page = self._build_transfer_connect_page()
        self.transfer_detail_page = self._build_transfer_detail_page()
        self.transfer_chat_page = self._build_transfer_chat_page()
        self.trash_page = self._build_trash_page()
        self.settings_page = self._build_settings_page()
        self.download_history_page = self._build_download_history_page()
        for page in (
            self.login_page,
            self.accounts_page,
            self.account_detail_page,
            self.notes_page,
            self.note_detail_page,
            self.transfer_page,
            self.transfer_connect_page,
            self.transfer_detail_page,
            self.transfer_chat_page,
            self.trash_page,
            self.settings_page,
            self.download_history_page,
        ):
            self.pages.addWidget(page)
        self._reset_module_pages()

        shell.addWidget(self.sidebar)
        shell.addWidget(self.pages, 1)
        self.setCentralWidget(root)

        self.accounts_nav.clicked.connect(self._show_accounts_page)
        self.notes_nav.clicked.connect(self._show_notes_page)
        self.transfer_nav.clicked.connect(self._show_transfer_page)
        self.trash_nav.clicked.connect(self._show_trash_page)
        self.settings_nav.clicked.connect(self._show_settings_page)
        lock.clicked.connect(self._lock)

    def _build_login_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(28, 28, 28, 28)
        outer.addStretch()
        shell = QFrame()
        self.login_shell = shell
        self.login_form_panel = shell
        shell.setObjectName("LoginFormPanel")
        shell.setMaximumWidth(760)
        shell.setMinimumWidth(640)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(16)
        self.login_brand_mark = QLabel()
        self.login_brand_mark.setObjectName("BrandMarkLarge")
        self.login_brand_mark.setFixedSize(124, 124)
        self.login_brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.login_brand_mark.setPixmap(
            QPixmap(str(SAFEBOX_LOGIN_LOGO_PATH)).scaled(
                124,
                124,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        title = QLabel("SafeBox")
        title.setObjectName("DialogTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel("私人保险箱。用保险箱ID和保险箱密码打开对应的数据空间。")
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.login_vault_name = QLineEdit()
        self.login_vault_name.setObjectName("VaultInput")
        self.login_vault_name.setPlaceholderText("输入保险箱ID")
        self.login_vault_name.setText(DEFAULT_VAULT_ID)
        self.login_password = QLineEdit()
        self.login_password.setObjectName("VaultInput")
        self.login_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_password.setPlaceholderText("输入保险箱密码")
        self.login_confirm_password = QLineEdit()
        self.login_confirm_password.setObjectName("VaultInput")
        self.login_confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_confirm_password.setPlaceholderText("再次输入保险箱密码")
        self.login_confirm_password.setVisible(False)
        self.login_confirm_label = QLabel("确认密码")
        self.login_confirm_label.setObjectName("VaultFormLabel")
        self.login_confirm_label.setVisible(False)
        self.remember_password_check = QCheckBox("记住密码")
        self.remember_password_check.setObjectName("RememberPasswordCheck")
        self.login_status = QLabel("")
        self.login_status.setObjectName("DataStatus")
        self.login_status.setWordWrap(True)
        self.login_status.setVisible(False)
        self.login_mode = VaultOpenMode.OPEN
        self.login_open_button = QPushButton("打开保险箱")
        self.login_open_button.setObjectName("LoginPrimaryButton")
        self.login_register_button = QPushButton("注册保险箱")
        self.login_register_button.setObjectName("LoginSubtleButton")

        form = QGridLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(14)
        form.setColumnMinimumWidth(0, 86)
        form.setColumnStretch(1, 1)
        id_label = QLabel("保险箱ID")
        id_label.setObjectName("VaultFormLabel")
        password_label = QLabel("保险箱密码")
        password_label.setObjectName("VaultFormLabel")
        form.addWidget(id_label, 0, 0)
        form.addWidget(self.login_vault_name, 0, 1)
        form.addWidget(password_label, 1, 0)
        form.addWidget(self.login_password, 1, 1)
        form.addWidget(self.login_confirm_label, 2, 0)
        form.addWidget(self.login_confirm_password, 2, 1)
        form.addWidget(self.remember_password_check, 3, 1)
        actions = QHBoxLayout()
        actions.setContentsMargins(104, 2, 0, 0)
        actions.setSpacing(12)
        self.login_open_button.setMinimumWidth(230)
        self.login_register_button.setMinimumWidth(150)
        actions.addWidget(self.login_open_button, 3)
        actions.addWidget(self.login_register_button, 2)

        layout.addWidget(self.login_brand_mark, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(form)
        layout.addWidget(self.login_status)
        layout.addLayout(actions)
        outer.addWidget(shell, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch()

        self.login_open_button.clicked.connect(self._open_vault_from_login)
        self.login_register_button.clicked.connect(self._register_vault_from_login)
        self.login_password.returnPressed.connect(self._open_vault_from_login)
        self.login_confirm_password.returnPressed.connect(self._register_vault_from_login)
        self.login_vault_name.editingFinished.connect(self._load_remembered_password_for_login)
        return page

    def _build_accounts_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        header = QHBoxLayout()
        header.setSpacing(10)
        title = QLabel("账号密码")
        title.setObjectName("PageTitle")
        add = QPushButton("+ 新建账号")
        add.setObjectName("PrimaryButton")
        self.account_multi_button = QPushButton("多选")
        self.account_multi_button.setObjectName("SubtleButton")
        self.account_delete_selected_button = QPushButton("删除选中")
        self.account_delete_selected_button.setObjectName("DangerButton")
        self.account_delete_selected_button.setVisible(False)
        self.account_status = QLabel("")
        self.account_status.setObjectName("DataStatus")
        self.account_status.setWordWrap(True)
        self.account_status.setVisible(False)
        self.account_search = QLineEdit()
        self.account_search.setPlaceholderText("搜索名称、账号、分类、备注")
        self.account_sort = QComboBox()
        self.account_sort.setObjectName("SortCombo")
        self._populate_sort_combo(self.account_sort)
        account_sort_group = self._sort_control_group(self.account_sort)
        self.account_list = QListWidget()
        self.account_list.setObjectName("RecordList")
        self.account_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.account_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.account_multi_button)
        header.addWidget(self.account_delete_selected_button)
        header.addWidget(account_sort_group)
        header.addWidget(add)
        layout.addLayout(header)
        layout.addWidget(self.account_status)
        layout.addWidget(self.account_search)
        layout.addWidget(self.account_list, 1)

        add.clicked.connect(self._add_account)
        self.account_multi_button.clicked.connect(
            lambda: self._toggle_batch_mode("accounts", self.account_list)
        )
        self.account_delete_selected_button.clicked.connect(self._delete_selected_accounts)
        self.account_sort.currentIndexChanged.connect(self._refresh_accounts)
        self.account_search.textChanged.connect(self._refresh_accounts)
        self.account_list.itemClicked.connect(self._open_account_item)
        self.account_list.customContextMenuRequested.connect(self._show_account_context_menu)
        return page

    def _build_account_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        top = QHBoxLayout()
        back = QPushButton("返回")
        back.setObjectName("SubtleButton")
        self.account_edit_button = QPushButton("编辑")
        self.account_edit_button.setObjectName("SubtleButton")
        self.account_export_button = QPushButton("导出")
        self.account_export_button.setObjectName("SubtleButton")
        self.account_export_menu = QMenu(self)
        self.account_export_txt_action = self.account_export_menu.addAction("导出 TXT")
        self.account_export_md_action = self.account_export_menu.addAction("导出 Markdown")
        self.account_export_pdf_action = self.account_export_menu.addAction("导出 PDF")
        self.account_export_button.setMenu(self.account_export_menu)
        delete = QPushButton("删除")
        delete.setObjectName("DangerButton")
        top.addWidget(back)
        top.addStretch()
        top.addWidget(self.account_export_button)
        top.addWidget(self.account_edit_button)
        top.addWidget(delete)
        account_header = QFrame()
        account_header.setObjectName("DetailHero")
        account_header_layout = QVBoxLayout(account_header)
        account_header_layout.setContentsMargins(20, 16, 20, 16)
        self.account_title = QLabel("账号详情")
        self.account_title.setObjectName("HeroTitle")
        self.account_meta = QLabel("")
        self.account_meta.setObjectName("HeroMeta")
        account_header_layout.addWidget(self.account_title)
        account_header_layout.addWidget(self.account_meta)
        self.account_save_notice = QLabel("保存成功")
        self.account_save_notice.setObjectName("SuccessNotice")
        self.account_save_notice.setVisible(False)
        self.account_fields = QFrame()
        self.account_fields.setObjectName("FieldPanel")
        self.account_fields_layout = QGridLayout(self.account_fields)
        self.account_fields_layout.setContentsMargins(0, 0, 0, 0)
        self.account_fields_layout.setSpacing(12)
        note_label = QLabel("备注")
        note_label.setObjectName("SectionLabel")
        self.account_note = QTextEdit()
        self.account_note.setObjectName("DetailNote")
        self.account_note.setReadOnly(True)
        copy_row = QHBoxLayout()
        copy_account = QPushButton("复制账号")
        copy_account.setObjectName("PrimaryButton")
        copy_password = QPushButton("复制密码")
        copy_password.setObjectName("PrimaryButton")
        copy_row.addWidget(copy_account)
        copy_row.addWidget(copy_password)
        layout.addLayout(top)
        layout.addWidget(self.account_save_notice)
        layout.addWidget(account_header)
        layout.addWidget(self.account_fields)
        layout.addWidget(note_label)
        layout.addWidget(self.account_note, 1)
        layout.addLayout(copy_row)

        back.clicked.connect(self._show_accounts_list_page)
        self.account_edit_button.clicked.connect(self._toggle_account_edit)
        self.account_export_txt_action.triggered.connect(
            lambda: self._export_current_account_as(".txt")
        )
        self.account_export_md_action.triggered.connect(
            lambda: self._export_current_account_as(".md")
        )
        self.account_export_pdf_action.triggered.connect(
            lambda: self._export_current_account_as(".pdf")
        )
        delete.clicked.connect(self._delete_current_account)
        copy_account.clicked.connect(lambda: self._copy_current_account_field("account"))
        copy_password.clicked.connect(lambda: self._copy_current_account_field("password"))
        return page

    def _build_notes_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        header = QHBoxLayout()
        header.setSpacing(10)
        title = QLabel("小纸条")
        title.setObjectName("PageTitle")
        add = QPushButton("+ 新建小纸条")
        add.setObjectName("PrimaryButton")
        import_file = QPushButton("导入文档")
        import_file.setObjectName("SubtleButton")
        self.note_multi_button = QPushButton("多选")
        self.note_multi_button.setObjectName("SubtleButton")
        self.note_delete_selected_button = QPushButton("删除选中")
        self.note_delete_selected_button.setObjectName("DangerButton")
        self.note_delete_selected_button.setVisible(False)
        import_file.setToolTip("仅支持 .txt、.md、.markdown 格式")
        self.note_status = QLabel("")
        self.note_status.setObjectName("DataStatus")
        self.note_status.setWordWrap(True)
        self.note_status.setVisible(False)
        self.note_search = QLineEdit()
        self.note_search.setPlaceholderText("搜索标题、分类、内容")
        self.note_sort = QComboBox()
        self.note_sort.setObjectName("SortCombo")
        self._populate_sort_combo(self.note_sort)
        note_sort_group = self._sort_control_group(self.note_sort)
        self.note_list = QListWidget()
        self.note_list.setObjectName("RecordList")
        self.note_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.note_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.note_multi_button)
        header.addWidget(self.note_delete_selected_button)
        header.addWidget(note_sort_group)
        header.addWidget(import_file)
        header.addWidget(add)
        layout.addLayout(header)
        layout.addWidget(self.note_status)
        layout.addWidget(self.note_search)
        layout.addWidget(self.note_list, 1)

        add.clicked.connect(self._new_note)
        import_file.clicked.connect(self._import_note_file)
        self.note_multi_button.clicked.connect(
            lambda: self._toggle_batch_mode("notes", self.note_list)
        )
        self.note_delete_selected_button.clicked.connect(self._delete_selected_notes)
        self.note_sort.currentIndexChanged.connect(self._refresh_notes)
        self.note_search.textChanged.connect(self._refresh_notes)
        self.note_list.itemClicked.connect(self._open_note_item)
        self.note_list.customContextMenuRequested.connect(self._show_note_context_menu)
        return page

    def _build_transfer_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        header = QHBoxLayout()
        title = QLabel("传输助手")
        title.setObjectName("PageTitle")
        self.connect_phone_button = QPushButton("连接手机")
        self.connect_phone_button.setObjectName("PrimaryButton")
        self.connect_phone_button.setToolTip("打开连接页，手机无需输入验证码")
        self.transfer_multi_button = QPushButton("多选")
        self.transfer_multi_button.setObjectName("SubtleButton")
        self.transfer_delete_selected_button = QPushButton("删除选中")
        self.transfer_delete_selected_button.setObjectName("DangerButton")
        self.transfer_delete_selected_button.setVisible(False)
        self.transfer_status = QLabel("")
        self.transfer_status.setObjectName("DataStatus")
        self.transfer_status.setWordWrap(True)
        self.transfer_status.setVisible(False)
        self.transfer_search = QLineEdit()
        self.transfer_search.setPlaceholderText("搜索传输记录、设备、状态")
        self.transfer_device_notice = QLabel("手机打开连接链接后即可直接对话，无需验证码。")
        self.transfer_device_notice.setObjectName("DataStatus")
        self.transfer_list = QListWidget()
        self.transfer_list.setObjectName("RecordList")
        self.transfer_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.transfer_multi_button)
        header.addWidget(self.transfer_delete_selected_button)
        header.addWidget(self.connect_phone_button)
        layout.addLayout(header)
        layout.addWidget(self.transfer_status)
        layout.addWidget(self.transfer_device_notice)
        layout.addWidget(self.transfer_search)
        layout.addWidget(self.transfer_list, 1)

        self.transfer_search.textChanged.connect(self._refresh_transfer_conversations)
        self.transfer_list.itemClicked.connect(self._open_transfer_item)
        self.connect_phone_button.clicked.connect(self._show_connect_phone_placeholder)
        self.transfer_multi_button.clicked.connect(
            lambda: self._toggle_batch_mode("transfer", self.transfer_list)
        )
        self.transfer_delete_selected_button.clicked.connect(
            self._delete_selected_transfer_conversations
        )
        return page

    def _build_transfer_connect_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        top = QHBoxLayout()
        back = QPushButton("返回列表")
        back.setObjectName("SubtleButton")
        self.transfer_connect_title = QLabel("连接手机")
        self.transfer_connect_title.setObjectName("HeroTitle")
        self.transfer_connect_meta = QLabel("手机和电脑在同一个 WiFi，或手机给电脑开热点。")
        self.transfer_connect_meta.setObjectName("HeroMeta")
        self.transfer_connect_type_value = QLabel("")
        self.transfer_connect_type_value.setObjectName("SettingsValue")
        self.transfer_connect_url_value = QLabel("")
        self.transfer_connect_url_value.setObjectName("SettingsValue")
        self.transfer_connect_url_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.transfer_connect_code_value = QLabel("")
        self.transfer_connect_code_value.setObjectName("SettingsValue")
        self.transfer_connect_code_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        for value in (
            self.transfer_connect_type_value,
            self.transfer_connect_url_value,
            self.transfer_connect_code_value,
        ):
            value.setMinimumHeight(34)
            value.setWordWrap(True)
        self.transfer_connect_copy_button = QPushButton("复制新手机链接")
        self.transfer_connect_copy_button.setObjectName("PrimaryButton")
        self.transfer_connect_status = QLabel("等待手机打开连接链接。")
        self.transfer_connect_status.setObjectName("TransferConnectStatus")
        self.transfer_connect_status.setMinimumHeight(48)
        self.transfer_connect_status.setWordWrap(True)
        self.transfer_trusted_list = QListWidget()
        self.transfer_trusted_list.setObjectName("RecordList")
        self.transfer_trusted_list.setFixedHeight(176)
        self.transfer_trusted_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.transfer_trusted_connect_button = QPushButton("连接选中设备")
        self.transfer_trusted_connect_button.setObjectName("PrimaryButton")
        self.transfer_trusted_copy_button = QPushButton("复制可信设备链接")
        self.transfer_trusted_copy_button.setObjectName("PrimaryButton")
        self.transfer_trusted_copy_button.setVisible(False)
        self.transfer_trusted_link_title = QLabel("可信设备链接")
        self.transfer_trusted_link_title.setObjectName("TransferConnectInfoLabel")
        self.transfer_trusted_link_title.setVisible(False)
        self.transfer_trusted_link_value = QLabel("")
        self.transfer_trusted_link_value.setObjectName("SettingsValue")
        self.transfer_trusted_link_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.transfer_trusted_link_value.setMinimumHeight(34)
        self.transfer_trusted_link_value.setWordWrap(True)
        self.transfer_trusted_link_value.setVisible(False)
        self.transfer_trusted_status = QLabel("选择可信设备后，会在这里显示专用连接链接。")
        self.transfer_trusted_status.setObjectName("TransferConnectStatus")
        self.transfer_trusted_status.setMinimumHeight(42)
        self.transfer_trusted_status.setWordWrap(True)
        hero = QFrame()
        hero.setObjectName("DetailHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 16, 20, 16)
        hero_layout.addWidget(self.transfer_connect_title)
        hero_layout.addWidget(self.transfer_connect_meta)
        connect_card = QFrame()
        connect_card.setObjectName("SettingsCard")
        connect_layout = QVBoxLayout(connect_card)
        connect_layout.setContentsMargins(18, 16, 18, 16)
        connect_layout.setSpacing(14)
        connect_title = QLabel("手机浏览器连接")
        connect_title.setObjectName("SettingsCardTitle")
        connect_hint = QLabel(
            "第一次连接或未信任的手机使用这里。复制链接到手机浏览器打开，"
            "手机进入后电脑才会创建对话。"
        )
        connect_hint.setObjectName("SettingsCardHint")
        connect_hint.setWordWrap(True)
        connect_layout.addWidget(connect_title)
        connect_layout.addWidget(connect_hint)
        connect_layout.addWidget(
            self._transfer_connect_info_row("连接用途", self.transfer_connect_type_value)
        )
        connect_layout.addWidget(
            self._transfer_connect_info_row("访问地址", self.transfer_connect_url_value)
        )
        connect_layout.addWidget(
            self._transfer_connect_info_row("连接状态", self.transfer_connect_code_value)
        )
        connect_layout.addWidget(self.transfer_connect_status)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(self.transfer_connect_copy_button)
        connect_layout.addLayout(actions)
        trusted_card = QFrame()
        trusted_card.setObjectName("SettingsCard")
        trusted_layout = QVBoxLayout(trusted_card)
        trusted_layout.setContentsMargins(18, 16, 18, 16)
        trusted_layout.setSpacing(10)
        trusted_title = QLabel("可信设备")
        trusted_title.setObjectName("SettingsCardTitle")
        trusted_hint = QLabel(
            "已经信任过的手机从这里连接。选择设备后会生成专用链接，"
            "复制给这台手机打开，连接后再进入对话。"
        )
        trusted_hint.setObjectName("SettingsCardHint")
        trusted_hint.setWordWrap(True)
        trusted_actions = QHBoxLayout()
        trusted_actions.addStretch()
        trusted_actions.addWidget(self.transfer_trusted_copy_button)
        trusted_actions.addWidget(self.transfer_trusted_connect_button)
        trusted_layout.addWidget(trusted_title)
        trusted_layout.addWidget(trusted_hint)
        trusted_layout.addWidget(self.transfer_trusted_list)
        trusted_layout.addWidget(self.transfer_trusted_link_title)
        trusted_layout.addWidget(self.transfer_trusted_link_value)
        trusted_layout.addWidget(self.transfer_trusted_status)
        trusted_layout.addLayout(trusted_actions)
        steps = QFrame()
        steps.setObjectName("SettingsCard")
        steps_layout = QVBoxLayout(steps)
        steps_layout.setContentsMargins(18, 16, 18, 16)
        steps_layout.setSpacing(8)
        steps_title = QLabel("连接步骤")
        steps_title.setObjectName("SettingsCardTitle")
        steps_layout.addWidget(steps_title)
        for text in (
            "1. 确认手机和电脑在同一个 WiFi，或手机给电脑开热点。",
            "2. 新手机用“手机浏览器连接”，可信手机用“可信设备”里的专用链接。",
            "3. 手机打开链接进入聊天页后，电脑端会自动进入本次对话。",
            "4. 第一次连接成功后，可在对话页点击“信任此设备”方便下次连接。",
        ):
            row = QLabel(text)
            row.setObjectName("SettingsValue")
            row.setWordWrap(True)
            steps_layout.addWidget(row)
        top.addWidget(back)
        top.addStretch()
        scroll = QScrollArea()
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        content_layout.addWidget(hero)
        content_layout.addWidget(connect_card)
        content_layout.addWidget(trusted_card)
        content_layout.addWidget(steps)
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addLayout(top)
        layout.addWidget(scroll, 1)

        back.clicked.connect(self._show_transfer_list_page)
        self.transfer_connect_copy_button.clicked.connect(self._copy_transfer_link)
        self.transfer_trusted_copy_button.clicked.connect(self._copy_transfer_link)
        self.transfer_trusted_connect_button.clicked.connect(self._connect_selected_trusted_device)
        return page

    def _transfer_connect_info_row(self, label: str, value: QLabel) -> QFrame:
        row = QFrame()
        row.setObjectName("TransferConnectInfoRow")
        row.setMinimumHeight(92)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(4)
        title = QLabel(label)
        title.setObjectName("TransferConnectInfoLabel")
        title.setMinimumHeight(22)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        value.setWordWrap(True)
        value.setMinimumHeight(28)
        value.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)
        layout.addWidget(value)
        self.transfer_connect_info_rows.append(row)
        return row

    def _build_transfer_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        top = QHBoxLayout()
        back = QPushButton("返回列表")
        back.setObjectName("SubtleButton")
        self.transfer_detail_attachments_button = QPushButton("查看附件")
        self.transfer_detail_attachments_button.setObjectName("SubtleButton")
        self.transfer_detail_delete_button = QPushButton("删除记录")
        self.transfer_detail_delete_button.setObjectName("DangerButton")
        self.transfer_detail_title = QLabel("传输记录")
        self.transfer_detail_title.setObjectName("HeroTitle")
        self.transfer_detail_meta = QLabel("")
        self.transfer_detail_meta.setObjectName("HeroMeta")
        self.transfer_detail_notice = QLabel("只读查看：可复制消息文本，也可预览或下载附件")
        self.transfer_detail_notice.setObjectName("DataStatus")
        self.transfer_detail_notice.setWordWrap(True)
        self.transfer_detail_messages_view = TransferMessageList()
        self.transfer_detail_messages_view.setObjectName("TransferMessageList")
        self.transfer_detail_messages_view.noticeRequested.connect(self._show_toast)
        top.addWidget(back)
        top.addStretch()
        top.addWidget(self.transfer_detail_attachments_button)
        top.addWidget(self.transfer_detail_delete_button)
        hero = QFrame()
        hero.setObjectName("DetailHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 16, 20, 16)
        hero_layout.addWidget(self.transfer_detail_title)
        hero_layout.addWidget(self.transfer_detail_meta)
        layout.addLayout(top)
        layout.addWidget(hero)
        layout.addWidget(self.transfer_detail_notice)
        layout.addWidget(self.transfer_detail_messages_view, 1)

        back.clicked.connect(self._show_transfer_list_page)
        self.transfer_detail_attachments_button.clicked.connect(
            self._show_current_transfer_attachments
        )
        self.transfer_detail_delete_button.clicked.connect(self._delete_current_transfer_record)
        return page

    def _build_transfer_chat_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        top = QHBoxLayout()
        back = QPushButton("返回列表")
        back.setObjectName("SubtleButton")
        self.transfer_organize_button = QPushButton("整理")
        self.transfer_organize_button.setObjectName("SubtleButton")
        self.transfer_organize_menu = QMenu(self)
        export_note_action = self.transfer_organize_menu.addAction("转存为小纸条")
        show_attachments_action = self.transfer_organize_menu.addAction("查看附件")
        preview_image_action = self.transfer_organize_menu.addAction("预览图片")
        show_download_history_action = self.transfer_organize_menu.addAction("查看下载记录")
        self.transfer_organize_button.setMenu(self.transfer_organize_menu)
        self.transfer_trust_device_button = QPushButton("信任此设备")
        self.transfer_trust_device_button.setObjectName("SubtleButton")
        self.transfer_close_button = QPushButton("关闭此次对话")
        self.transfer_close_button.setObjectName("DangerButton")
        self.transfer_chat_title = QLabel("手机对话")
        self.transfer_chat_title.setObjectName("HeroTitle")
        self.transfer_chat_meta = QLabel("")
        self.transfer_chat_meta.setObjectName("HeroMeta")
        self.transfer_chat_connection = QLabel("")
        self.transfer_chat_connection.setObjectName("DataStatus")
        self.transfer_chat_connection.setWordWrap(True)
        self.transfer_copy_link_button = QPushButton("复制链接")
        self.transfer_copy_link_button.setObjectName("SubtleButton")
        self.transfer_copy_link_button.setVisible(False)
        connection_row = QHBoxLayout()
        connection_row.addWidget(self.transfer_chat_connection, 1)
        connection_row.addWidget(self.transfer_copy_link_button)
        self.transfer_messages_view = TransferMessageList()
        self.transfer_messages_view.setObjectName("TransferMessageList")
        self.transfer_messages_view.noticeRequested.connect(self._show_toast)
        self.transfer_message_input = QTextEdit()
        self.transfer_message_input.setObjectName("TransferMessageInput")
        self.transfer_message_input.setPlaceholderText("输入要发送给手机的文字")
        self.transfer_message_input.setFixedHeight(92)
        self.transfer_send_button = QPushButton("发送到手机")
        self.transfer_send_button.setObjectName("PrimaryButton")
        self.transfer_send_image_button = QPushButton("图片")
        self.transfer_send_image_button.setObjectName("SubtleButton")
        self.transfer_send_file_button = QPushButton("发送文件")
        self.transfer_send_file_button.setObjectName("SubtleButton")
        hero = QFrame()
        hero.setObjectName("DetailHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 16, 20, 16)
        hero_layout.addWidget(self.transfer_chat_title)
        hero_layout.addWidget(self.transfer_chat_meta)
        hero_layout.addLayout(connection_row)
        input_row = QHBoxLayout()
        input_row.addWidget(self.transfer_message_input, 1)
        input_row.addWidget(self.transfer_send_image_button)
        input_row.addWidget(self.transfer_send_file_button)
        input_row.addWidget(self.transfer_send_button)
        top.addWidget(back)
        top.addStretch()
        top.addWidget(self.transfer_trust_device_button)
        top.addWidget(self.transfer_organize_button)
        top.addWidget(self.transfer_close_button)
        layout.addLayout(top)
        layout.addWidget(hero)
        layout.addWidget(self.transfer_messages_view, 1)
        layout.addLayout(input_row)

        back.clicked.connect(self._show_transfer_list_page)
        export_note_action.triggered.connect(self._export_current_transfer_to_note)
        self.transfer_trust_device_button.clicked.connect(self._trust_current_transfer_device)
        show_attachments_action.triggered.connect(self._show_current_transfer_attachments)
        preview_image_action.triggered.connect(self._preview_first_transfer_image)
        show_download_history_action.triggered.connect(
            lambda: self._show_download_history_dialog()
        )
        self.transfer_close_button.clicked.connect(self._close_current_transfer_chat)
        self.transfer_send_button.clicked.connect(self._send_current_transfer_text)
        self.transfer_send_image_button.clicked.connect(self._send_current_transfer_image)
        self.transfer_send_file_button.clicked.connect(self._send_current_transfer_file)
        self.transfer_copy_link_button.clicked.connect(self._copy_transfer_link)
        return page

    def _build_note_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        top = QHBoxLayout()
        back = QPushButton("返回")
        back.setObjectName("SubtleButton")
        self.note_attachments_button = QPushButton("查看附件")
        self.note_attachments_button.setObjectName("SubtleButton")
        self.note_attachments_button.setVisible(False)
        self.note_export_button = QPushButton("导出")
        self.note_export_button.setObjectName("SubtleButton")
        self.note_export_menu = QMenu(self)
        self.note_export_txt_action = self.note_export_menu.addAction("导出 TXT")
        self.note_export_md_action = self.note_export_menu.addAction("导出 Markdown")
        self.note_export_pdf_action = self.note_export_menu.addAction("导出 PDF")
        self.note_export_button.setMenu(self.note_export_menu)
        self.note_save_button = QPushButton("保存")
        self.note_save_button.setObjectName("PrimaryButton")
        delete = QPushButton("删除")
        delete.setObjectName("DangerButton")
        top.addWidget(back)
        top.addStretch()
        top.addWidget(self.note_attachments_button)
        top.addWidget(self.note_export_button)
        top.addWidget(self.note_save_button)
        top.addWidget(delete)
        self.note_title_input = QLineEdit()
        self.note_title_input.setPlaceholderText("标题")
        self.note_category = QComboBox()
        self.note_category.setEditable(True)
        self.note_category.addItems(NOTE_CATEGORIES)
        self.note_category.setFixedWidth(150)
        self.note_source_info = QLabel("")
        self.note_source_info.setObjectName("SourceNotice")
        self.note_source_info.setVisible(False)
        self.note_save_notice = QLabel("保存成功")
        self.note_save_notice.setObjectName("SuccessNotice")
        self.note_save_notice.setVisible(False)
        toolbar = QHBoxLayout()
        undo = QPushButton("↶")
        undo.setObjectName("FormatButton")
        undo.setToolTip("撤销 Ctrl+Z")
        redo = QPushButton("↷")
        redo.setObjectName("FormatButton")
        redo.setToolTip("重做 Ctrl+Y")
        bold = QPushButton("B")
        bold.setObjectName("FormatButton")
        bold.setToolTip("加粗 Ctrl+B")
        italic = QPushButton("I")
        italic.setObjectName("FormatButton")
        italic.setToolTip("斜体 Ctrl+I")
        underline = QPushButton("U")
        underline.setObjectName("FormatButton")
        underline.setToolTip("下划线 Ctrl+U")
        ordered = QPushButton("1.")
        ordered.setObjectName("FormatButton")
        ordered.setToolTip("编号列表 Ctrl+7")
        align_left = QPushButton("L")
        align_left.setObjectName("FormatButton")
        align_left.setToolTip("左对齐 Ctrl+L")
        align_center = QPushButton("C")
        align_center.setObjectName("FormatButton")
        align_center.setToolTip("居中 Ctrl+E")
        align_right = QPushButton("R")
        align_right.setObjectName("FormatButton")
        align_right.setToolTip("右对齐 Ctrl+R")
        insert_image = QPushButton("Img")
        insert_image.setObjectName("FormatButtonWide")
        insert_image.setToolTip("插入图片，也支持 Ctrl+V 粘贴图片")
        bullet = QPushButton("•")
        bullet.setObjectName("FormatButton")
        heading = QPushButton("标题")
        heading.setObjectName("FormatButtonWide")
        body = QPushButton("正文")
        body.setObjectName("FormatButtonWide")
        self.note_format_brush_button = QPushButton("")
        self.note_format_brush_button.setObjectName("FormatButton")
        self.note_format_brush_button.setIcon(QIcon(str(FORMAT_BRUSH_ICON_PATH)))
        self.note_format_brush_button.setIconSize(QSize(18, 18))
        self.note_format_brush_button.setToolTip("格式刷")
        clear_format = QPushButton("清格式")
        clear_format.setObjectName("FormatButtonWide")
        copy_all = QPushButton("复制全文")
        copy_all.setObjectName("FormatButtonWide")
        self.note_font_size = QComboBox()
        self.note_font_size.setObjectName("FontSizeCombo")
        self.note_font_size.addItems(
            ["10", "11", "12", "13", "14", "16", "18", "20", "24", "28", "32"]
        )
        self.note_font_size.setCurrentText(str(NOTE_BODY_FONT_SIZE_PT))
        self.note_font_size.setFixedWidth(64)
        self.note_align_left_button = align_left
        self.note_align_left_button.setText("")
        self.note_align_left_button.setIcon(QIcon(str(ALIGN_LEFT_ICON_PATH)))
        self.note_align_left_button.setIconSize(QSize(18, 18))
        self.note_align_center_button = align_center
        self.note_align_center_button.setText("")
        self.note_align_center_button.setIcon(QIcon(str(ALIGN_CENTER_ICON_PATH)))
        self.note_align_center_button.setIconSize(QSize(18, 18))
        self.note_align_right_button = align_right
        self.note_align_right_button.setText("")
        self.note_align_right_button.setIcon(QIcon(str(ALIGN_RIGHT_ICON_PATH)))
        self.note_align_right_button.setIconSize(QSize(18, 18))
        self.note_color_red_button = QPushButton("")
        self.note_color_red_button.setObjectName("ColorButtonRed")
        color_black = QPushButton("")
        color_black.setObjectName("ColorButtonBlack")
        color_blue = QPushButton("")
        color_blue.setObjectName("ColorButtonBlue")
        color_pink = QPushButton("")
        color_pink.setObjectName("ColorButtonPink")
        color_green = QPushButton("")
        color_green.setObjectName("ColorButtonGreen")
        color_orange = QPushButton("")
        color_orange.setObjectName("ColorButtonOrange")
        for button in (
            self.note_format_brush_button,
            bold,
            italic,
            underline,
            ordered,
            align_left,
            align_center,
            align_right,
            insert_image,
            bullet,
            heading,
            body,
            clear_format,
            copy_all,
        ):
            toolbar.addWidget(button)
        toolbar.addWidget(self.note_font_size)
        toolbar.addSpacing(8)
        for button in (
            self.note_color_red_button,
            color_black,
            color_blue,
            color_pink,
            color_green,
            color_orange,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch()
        self.note_body = NoteEditor()
        self.note_body.setObjectName("NoteBody")
        self.note_body.setPlaceholderText("在这里写小纸条内容")
        self.note_format_buttons = [
            self.note_format_brush_button,
            bold,
            italic,
            underline,
            ordered,
            align_left,
            align_center,
            align_right,
            insert_image,
            bullet,
            heading,
            body,
            clear_format,
            self.note_font_size,
            self.note_color_red_button,
            color_black,
            color_blue,
            color_pink,
            color_green,
            color_orange,
        ]
        note_title_row = QHBoxLayout()
        note_title_row.setSpacing(10)
        note_title_row.addWidget(self.note_title_input, 1)
        note_title_row.addWidget(self.note_category, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)
        layout.addLayout(note_title_row)
        layout.addWidget(self.note_source_info)
        layout.addWidget(self.note_save_notice)
        layout.addLayout(toolbar)
        layout.addWidget(self.note_body, 1)

        back.clicked.connect(self._return_from_note_detail)
        self.note_attachments_button.clicked.connect(self._show_current_note_attachments)
        self.note_export_txt_action.triggered.connect(
            lambda: self._export_current_note_as(".txt")
        )
        self.note_export_md_action.triggered.connect(
            lambda: self._export_current_note_as(".md")
        )
        self.note_export_pdf_action.triggered.connect(
            lambda: self._export_current_note_as(".pdf")
        )
        self.note_save_button.clicked.connect(self._save_current_note)
        self.note_category.currentTextChanged.connect(self._mark_note_dirty_from_editor)
        delete.clicked.connect(self._delete_current_note)
        undo.clicked.connect(self.note_body.undo)
        redo.clicked.connect(self.note_body.redo)
        bold.clicked.connect(lambda: self._toggle_text_property("bold"))
        italic.clicked.connect(lambda: self._toggle_text_property("italic"))
        underline.clicked.connect(lambda: self._toggle_text_property("underline"))
        bullet.clicked.connect(lambda: self._toggle_note_list(QTextListFormat.Style.ListDisc))
        ordered.clicked.connect(
            lambda: self._toggle_note_list(QTextListFormat.Style.ListDecimal)
        )
        align_left.clicked.connect(
            lambda: self._set_note_alignment(Qt.AlignmentFlag.AlignLeft)
        )
        align_center.clicked.connect(
            lambda: self._set_note_alignment(Qt.AlignmentFlag.AlignCenter)
        )
        align_right.clicked.connect(
            lambda: self._set_note_alignment(Qt.AlignmentFlag.AlignRight)
        )
        insert_image.clicked.connect(self._insert_note_image_file)
        heading.clicked.connect(lambda: self._set_text_size(NOTE_HEADING_FONT_SIZE_PT))
        body.clicked.connect(lambda: self._set_text_size(NOTE_BODY_FONT_SIZE_PT))
        self.note_format_brush_button.clicked.connect(self._use_note_format_brush)
        clear_format.clicked.connect(self._clear_note_format)
        copy_all.clicked.connect(self._copy_note_plain_text)
        self.note_font_size.currentTextChanged.connect(self._set_text_size_from_text)
        self.note_color_red_button.clicked.connect(
            lambda: self._set_text_color("#dc2626")
        )
        color_black.clicked.connect(lambda: self._set_text_color("#111827"))
        color_blue.clicked.connect(lambda: self._set_text_color("#2563eb"))
        color_pink.clicked.connect(lambda: self._set_text_color("#db2777"))
        color_green.clicked.connect(lambda: self._set_text_color("#059669"))
        color_orange.clicked.connect(lambda: self._set_text_color("#ea580c"))
        self.note_title_input.textChanged.connect(self._mark_note_dirty_from_editor)
        self.note_body.textChanged.connect(self._mark_note_dirty_from_editor)
        self.note_save_shortcut = QShortcut(QKeySequence.StandardKey.Save, page)
        self.note_save_shortcut.activated.connect(lambda: self._save_current_note())
        self.note_body.formatShortcutRequested.connect(self._handle_note_shortcut)
        self.note_body.imageInserted.connect(lambda: self._show_note_save_notice("已插入图片"))
        return page

    def _build_trash_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        header = QHBoxLayout()
        title = QLabel("回收站")
        title.setObjectName("PageTitle")
        clear = QPushButton("清空回收站")
        clear.setObjectName("DangerButton")
        self.trash_multi_button = QPushButton("多选")
        self.trash_multi_button.setObjectName("SubtleButton")
        self.trash_list = QListWidget()
        self.trash_list.setObjectName("RecordList")
        self.trash_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        action_row = QHBoxLayout()
        restore = QPushButton("恢复")
        restore.setObjectName("PrimaryButton")
        remove = QPushButton("彻底删除")
        remove.setObjectName("DangerButton")
        action_row.addStretch()
        action_row.addWidget(restore)
        action_row.addWidget(remove)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.trash_multi_button)
        header.addWidget(clear)
        layout.addLayout(header)
        layout.addWidget(self.trash_list, 1)
        layout.addLayout(action_row)

        restore.clicked.connect(self._restore_selected_trash)
        remove.clicked.connect(self._delete_selected_trash_permanently)
        self.trash_multi_button.clicked.connect(
            lambda: self._toggle_batch_mode("trash", self.trash_list)
        )
        clear.clicked.connect(self._clear_trash)
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        title = QLabel("设置")
        title.setObjectName("PageTitle")
        subtitle = QLabel("管理当前保险箱、安全策略和备份同步。")
        subtitle.setObjectName("MutedText")
        self.settings_vault_label = QLabel("")
        self.settings_vault_label.setObjectName("SettingsValue")
        self.settings_data_overview = QLabel("打开保险箱后显示数据概览。")
        self.settings_data_overview.setObjectName("SettingsValue")
        self.settings_data_overview.setWordWrap(True)
        self.backup_dir_label = QLabel("")
        self.backup_dir_label.setObjectName("SettingsValue")
        self.backup_dir_label.setWordWrap(True)
        self.transfer_download_dir_label = QLabel("")
        self.transfer_download_dir_label.setObjectName("SettingsValue")
        self.transfer_download_dir_label.setWordWrap(True)
        choose_backup = QPushButton("设置备份位置")
        choose_backup.setObjectName("SubtleButton")
        sync_now = QPushButton("立即同步")
        sync_now.setObjectName("SyncNowButton")
        sync_now.setMinimumWidth(100)
        restore_backup = QPushButton("从备份恢复")
        restore_backup.setObjectName("SubtleButton")
        show_download_history = QPushButton("查看下载历史")
        show_download_history.setObjectName("SubtleButton")
        choose_download_dir = QPushButton("修改下载位置")
        choose_download_dir.setObjectName("SubtleButton")
        self.auto_sync_check = QCheckBox("关闭软件时自动同步当前保险箱")
        self.auto_sync_check.setChecked(True)
        self.auto_lock_combo = QComboBox()
        self.auto_lock_combo.addItems(("5分钟", "20分钟", "自定义", "从不锁定"))
        self.auto_lock_combo.setObjectName("SortCombo")
        self.custom_auto_lock_minutes = QSpinBox()
        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("SortCombo")
        for theme_name, label in THEME_LABELS.items():
            self.theme_combo.addItem(label, theme_name)
        self.custom_auto_lock_minutes.setRange(1, 24 * 60)
        self.custom_auto_lock_minutes.setSuffix(" 分钟")
        self.custom_auto_lock_minutes.setObjectName("MinuteSpinBox")
        self.custom_auto_lock_minutes.setFixedWidth(110)
        self.custom_auto_lock_minutes.setVisible(False)
        change_password = QPushButton("修改保险箱密码")
        change_password.setObjectName("PrimaryButton")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(
            self._settings_card(
                "保险箱概览",
                "当前打开的数据空间和本地存储状态。",
                (("保险箱", self.settings_vault_label), ("数据概览", self.settings_data_overview)),
            )
        )
        backup_card = self._settings_card(
            "备份同步",
            "选择一个固定备份位置，并按需同步或恢复当前保险箱。",
            (("备份位置", self.backup_dir_label),),
        )
        backup_actions = QHBoxLayout()
        backup_actions.setSpacing(10)
        backup_actions.addWidget(choose_backup)
        backup_actions.addWidget(sync_now)
        backup_actions.addWidget(restore_backup)
        backup_actions.addStretch()
        backup_card.layout().addLayout(backup_actions)
        layout.addWidget(backup_card)
        transfer_card = self._settings_card(
            "传输助手",
            "管理附件下载位置和下载历史。",
            (("默认下载位置", self.transfer_download_dir_label),),
        )
        transfer_actions = QHBoxLayout()
        transfer_actions.setSpacing(10)
        transfer_actions.addWidget(choose_download_dir)
        transfer_actions.addWidget(show_download_history)
        transfer_actions.addStretch()
        transfer_card.layout().addLayout(transfer_actions)
        layout.addWidget(transfer_card)
        appearance_card = self._settings_card(
            "界面",
            "经典主题保持现有外观，Linear Dark 按 DESIGN.md 的深色工作台风格重新设计。",
            (),
        )
        theme_row = QFrame()
        theme_row.setObjectName("SettingsRow")
        theme_layout = QHBoxLayout(theme_row)
        theme_layout.setContentsMargins(12, 10, 12, 10)
        theme_layout.setSpacing(12)
        theme_label = QLabel("主题")
        theme_label.setObjectName("SettingsLabel")
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()
        appearance_card.layout().addWidget(theme_row)
        layout.addWidget(appearance_card)
        security_card = self._settings_card(
            "安全",
            "控制自动同步和保险箱密码。",
            (),
        )
        security_actions = QHBoxLayout()
        security_actions.setSpacing(10)
        security_actions.addWidget(self.auto_sync_check)
        security_actions.addStretch()
        security_actions.addWidget(change_password)
        security_card.layout().addLayout(security_actions)
        auto_lock_row = QFrame()
        auto_lock_row.setObjectName("SettingsRow")
        auto_lock_layout = QHBoxLayout(auto_lock_row)
        auto_lock_layout.setContentsMargins(12, 10, 12, 10)
        auto_lock_layout.setSpacing(12)
        auto_lock_label = QLabel("自动锁定")
        auto_lock_label.setObjectName("SettingsLabel")
        auto_lock_layout.addWidget(auto_lock_label)
        auto_lock_layout.addWidget(self.auto_lock_combo)
        auto_lock_layout.addWidget(self.custom_auto_lock_minutes)
        auto_lock_layout.addStretch()
        security_card.layout().addWidget(auto_lock_row)
        layout.addWidget(security_card)
        layout.addStretch()
        choose_backup.clicked.connect(self._choose_backup_dir)
        choose_download_dir.clicked.connect(self._choose_transfer_download_dir)
        sync_now.clicked.connect(self._sync_current_vault)
        restore_backup.clicked.connect(self._restore_current_vault_from_backup)
        show_download_history.clicked.connect(self._show_download_history_page)
        self.auto_sync_check.toggled.connect(self._set_auto_sync_on_close)
        self.auto_lock_combo.currentTextChanged.connect(self._set_auto_lock_mode)
        self.custom_auto_lock_minutes.valueChanged.connect(self._set_custom_auto_lock_minutes)
        self.theme_combo.currentIndexChanged.connect(self._set_theme_from_settings)
        change_password.clicked.connect(self._change_master_password)
        scroll.setWidget(content)
        page_layout.addWidget(scroll)
        return page

    def _build_download_history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        header = QHBoxLayout()
        back = QPushButton("返回设置")
        back.setObjectName("SubtleButton")
        title = QLabel("下载历史")
        title.setObjectName("PageTitle")
        delete_file = QPushButton("删除文件")
        delete_file.setObjectName("DangerButton")
        self.download_history_multi_button = QPushButton("多选")
        self.download_history_multi_button.setObjectName("SubtleButton")
        self.download_history_status = QLabel("下载历史为空")
        self.download_history_status.setObjectName("DataStatus")
        self.download_history_status.setWordWrap(True)
        self.download_history_list = QListWidget()
        self.download_history_list.setObjectName("RecordList")
        self.download_history_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.download_history_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.download_history_list.customContextMenuRequested.connect(
            lambda position: self._show_download_history_context_menu(
                self.download_history_list,
                position,
                self._refresh_download_history,
                self.download_history_status,
            )
        )
        action_row = QHBoxLayout()
        open_folder = QPushButton("打开文件夹")
        open_folder.setObjectName("PrimaryButton")
        delete_record = QPushButton("清除选中记录")
        delete_record.setObjectName("SubtleButton")
        action_row.addStretch()
        action_row.addWidget(open_folder)
        action_row.addWidget(delete_record)
        header.addWidget(back)
        header.addStretch()
        header.addWidget(self.download_history_multi_button)
        header.addWidget(delete_file)
        layout.addLayout(header)
        layout.addWidget(title)
        layout.addWidget(self.download_history_status)
        layout.addWidget(self.download_history_list, 1)
        layout.addLayout(action_row)

        back.clicked.connect(self._show_settings_page)
        delete_file.clicked.connect(self._delete_selected_download_history_files)
        open_folder.clicked.connect(self._open_transfer_download_folder)
        delete_record.clicked.connect(self._delete_selected_download_history)
        self.download_history_list.itemDoubleClicked.connect(
            self._open_download_history_item
        )
        self.download_history_multi_button.clicked.connect(
            lambda: self._toggle_batch_mode(
                "download_history",
                self.download_history_list,
            )
        )
        return page

    def _settings_card(
        self,
        title: str,
        description: str,
        rows: tuple[tuple[str, QLabel], ...],
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("SettingsCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("SettingsCardTitle")
        hint = QLabel(description)
        hint.setObjectName("SettingsCardHint")
        hint.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(hint)
        for label_text, value_label in rows:
            row = QFrame()
            row.setObjectName("SettingsRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 10, 12, 10)
            row_layout.setSpacing(14)
            label = QLabel(label_text)
            label.setObjectName("SettingsLabel")
            row_layout.addWidget(label)
            row_layout.addWidget(value_label, 1)
            layout.addWidget(row)
        return card

    def _sort_control_group(self, combo: QComboBox) -> QWidget:
        group = QWidget()
        group.setObjectName("SortControlGroup")
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        label = QLabel("排序")
        label.setObjectName("SortLabel")
        label.setMinimumWidth(0)
        combo.setMinimumWidth(160)
        layout.addWidget(label)
        layout.addWidget(combo)
        return group

    def _open_vault(self) -> None:
        dialog = VaultOpenDialog(self)
        if not dialog.exec():
            self.close()
            return
        vault_name, password, confirm_password, mode = dialog.values()
        self._handle_vault_open_values(
            vault_name,
            password,
            confirm_password,
            mode,
            retry_on_error=True,
        )

    def _handle_vault_open_values(
        self,
        vault_name: str,
        password: str,
        confirm_password: str,
        mode: str,
        *,
        retry_on_error: bool,
    ) -> None:
        self.vault_name = vault_name
        self.service = self.service_factory(vault_name)
        self.settings = AppSettings(vault_path=self.service.store.path)
        self.profile_settings = load_profile_settings(self.profile_base_dir, vault_name)
        self._apply_theme(normalize_theme_name(self.profile_settings.theme_name))
        self._apply_profile_download_dir()
        self._apply_auto_lock_settings()
        if not password:
            self._show_login_error(
                "信息不完整",
                "保险箱密码需要填写。",
                retry_on_error=retry_on_error,
            )
            return
        if mode == VaultOpenMode.REGISTER.value:
            if self.service.vault_exists():
                self._show_login_error(
                    "保险箱已存在",
                    "这个保险箱ID已经注册，请直接打开。",
                    retry_on_error=retry_on_error,
                )
                return
            if password != confirm_password:
                self._show_login_error(
                    "两次密码不一致",
                    "请重新确认保险箱密码。",
                    retry_on_error=retry_on_error,
                )
                return
            self.service.initialize(password)
        elif self.service.vault_exists():
            result = try_unlock(self.service, password)
            if not result.ok:
                self._show_login_error(
                    "无法打开保险箱",
                    result.message,
                    retry_on_error=retry_on_error,
                )
                return
        else:
            self._show_login_error(
                "保险箱不存在",
                "这个保险箱ID还没有注册，请先注册保险箱。",
                retry_on_error=retry_on_error,
            )
            return
        self._apply_auto_lock_settings()
        self.vault_subtitle.setText(f"保险箱ID：{self.vault_name}")
        self._save_remembered_password(password)
        self.login_password.clear()
        self.login_confirm_password.clear()
        self.login_status.setText("")
        self.login_status.setVisible(False)
        self._set_login_mode(VaultOpenMode.OPEN)
        self._refresh_settings_view()
        self._reset_module_pages()
        self.sidebar.setVisible(True)
        self._show_accounts_list_page()

    def _apply_profile_download_dir(self) -> None:
        if not self.profile_settings.transfer_download_dir:
            return
        self.settings = AppSettings(
            vault_path=self.settings.vault_path,
            auto_lock_seconds=self.settings.auto_lock_seconds,
            clipboard_clear_seconds=self.settings.clipboard_clear_seconds,
            transfer_download_dir=Path(self.profile_settings.transfer_download_dir),
        )

    def _show_unlock_dialog(self) -> None:
        self._open_vault()

    def _reset_module_pages(self) -> None:
        self.module_pages = {
            "accounts": self.accounts_page,
            "notes": self.notes_page,
            "transfer": self.transfer_page,
            "trash": self.trash_page,
            "settings": self.settings_page,
        }

    def _remember_module_page(self, module: str, page: QWidget) -> None:
        self.module_pages[module] = page

    def _show_module_page(self, module: str, default_page: QWidget) -> None:
        self._set_nav(module)
        self.pages.setCurrentWidget(self.module_pages.get(module, default_page))

    def _module_is_showing_list(self, module: str, list_page: QWidget) -> bool:
        return self.module_pages.get(module, list_page) is list_page

    def _set_nav(self, active: str) -> None:
        if self.active_nav_key == active:
            return
        self.active_nav_key = active
        pairs = {
            "accounts": self.accounts_nav,
            "notes": self.notes_nav,
            "transfer": self.transfer_nav,
            "trash": self.trash_nav,
            "settings": self.settings_nav,
        }
        for key, button in pairs.items():
            button.setObjectName("NavButtonActive" if key == active else "NavButton")
            button.style().unpolish(button)
            button.style().polish(button)

    def _show_accounts_page(self) -> None:
        self._show_module_page("accounts", self.accounts_page)
        if self._module_is_showing_list("accounts", self.accounts_page):
            self._refresh_accounts()

    def _show_accounts_list_page(self) -> None:
        self._remember_module_page("accounts", self.accounts_page)
        self._set_nav("accounts")
        self.pages.setCurrentWidget(self.accounts_page)
        self._refresh_accounts()

    def _show_notes_page(self) -> None:
        self._show_module_page("notes", self.notes_page)
        if self._module_is_showing_list("notes", self.notes_page):
            self._refresh_notes()

    def _show_notes_list_page(self) -> None:
        if not self._confirm_discard_dirty_note():
            return
        self._remember_module_page("notes", self.notes_page)
        self._set_nav("notes")
        self.pages.setCurrentWidget(self.notes_page)
        self._refresh_notes()

    def _return_from_note_detail(self) -> None:
        self._show_notes_list_page()

    def _show_transfer_page(self) -> None:
        self._show_module_page("transfer", self.transfer_page)
        if self._module_is_showing_list("transfer", self.transfer_page):
            self._refresh_transfer_conversations()

    def _show_transfer_list_page(self) -> None:
        self.transfer_refresh_timer.stop()
        self.transfer_pair_timer.stop()
        self.transfer_messages_signature = ""
        self._remember_module_page("transfer", self.transfer_page)
        self._set_nav("transfer")
        self.pages.setCurrentWidget(self.transfer_page)
        self._refresh_transfer_conversations()

    def _show_trash_page(self) -> None:
        self._remember_module_page("trash", self.trash_page)
        self._set_nav("trash")
        self.pages.setCurrentWidget(self.trash_page)
        self._refresh_trash()

    def _show_settings_page(self) -> None:
        self._remember_module_page("settings", self.settings_page)
        self._set_nav("settings")
        self._refresh_settings_view()
        self.pages.setCurrentWidget(self.settings_page)

    def _show_download_history_page(self) -> None:
        self._remember_module_page("settings", self.download_history_page)
        self._set_nav("settings")
        self.pages.setCurrentWidget(self.download_history_page)
        self._refresh_download_history()

    def _show_login_page(self) -> None:
        self.sidebar.setVisible(False)
        self._load_remembered_password_for_login()
        self.pages.setCurrentWidget(self.login_page)
        self.active_nav_key = ""

    def _set_login_mode(self, mode: VaultOpenMode) -> None:
        self.login_mode = mode
        registering = mode == VaultOpenMode.REGISTER
        self.login_confirm_label.setVisible(registering)
        self.login_confirm_password.setVisible(registering)
        self.login_open_button.setText("返回打开" if registering else "打开保险箱")
        self.login_open_button.setObjectName(
            "LoginSubtleButton" if registering else "LoginPrimaryButton"
        )
        self.login_register_button.setObjectName(
            "LoginPrimaryButton" if registering else "LoginSubtleButton"
        )
        self.login_vault_name.setPlaceholderText(
            "设置保险箱ID" if registering else "输入保险箱ID"
        )
        self.login_password.setPlaceholderText(
            "设置保险箱密码" if registering else "输入保险箱密码"
        )
        self._refresh_button_style(self.login_open_button)
        self._refresh_button_style(self.login_register_button)
        self.login_status.setText("")
        self.login_status.setVisible(False)
        self.remember_password_check.setVisible(not registering)

    def _open_vault_from_login(self) -> None:
        if self.login_mode == VaultOpenMode.REGISTER:
            self._set_login_mode(VaultOpenMode.OPEN)
            return
        self._handle_vault_open_values(
            self.login_vault_name.text().strip() or DEFAULT_VAULT_ID,
            self.login_password.text(),
            self.login_confirm_password.text(),
            VaultOpenMode.OPEN.value,
            retry_on_error=False,
        )

    def _register_vault_from_login(self) -> None:
        if self.login_mode == VaultOpenMode.OPEN:
            self._set_login_mode(VaultOpenMode.REGISTER)
            return
        self._handle_vault_open_values(
            self.login_vault_name.text().strip() or DEFAULT_VAULT_ID,
            self.login_password.text(),
            self.login_confirm_password.text(),
            VaultOpenMode.REGISTER.value,
            retry_on_error=False,
        )

    def _show_login_error(self, title: str, message: str, *, retry_on_error: bool) -> None:
        if retry_on_error:
            QMessageBox.warning(self, title, message)
            QTimer.singleShot(0, self._open_vault)
            return
        self.login_status.setText(message)
        self.login_status.setVisible(True)
        self._show_toast(message)

    def _load_remembered_password_for_login(self) -> None:
        if self.login_mode == VaultOpenMode.REGISTER:
            return
        vault_name = self.login_vault_name.text().strip() or DEFAULT_VAULT_ID
        settings = load_profile_settings(self.profile_base_dir, vault_name)
        self.remember_password_check.blockSignals(True)
        self.remember_password_check.setChecked(settings.remember_password)
        self.remember_password_check.blockSignals(False)
        if not settings.remember_password or not settings.remembered_password:
            return
        try:
            password = unprotect_password(settings.remembered_password)
        except (OSError, ValueError):
            self.login_password.clear()
            return
        self.login_password.setText(password)

    def _save_remembered_password(self, password: str) -> None:
        if self.login_mode == VaultOpenMode.REGISTER:
            return
        self.profile_settings.remember_password = self.remember_password_check.isChecked()
        if self.profile_settings.remember_password:
            self.profile_settings.remembered_password = protect_password(password)
        else:
            self.profile_settings.remembered_password = ""
        save_profile_settings(self.profile_base_dir, self.vault_name, self.profile_settings)

    def _show_download_history_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("下载历史")
        dialog.resize(720, 520)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(12)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("下载历史")
        title.setObjectName("DialogTitle")
        subtitle = QLabel("最近保存到电脑的附件记录")
        subtitle.setObjectName("MutedText")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        multi_select = QPushButton("多选")
        multi_select.setObjectName("SubtleButton")
        multi_select.setMinimumWidth(76)
        delete_file = QPushButton("删除文件")
        delete_file.setObjectName("DangerButton")
        delete_file.setMinimumWidth(98)
        close = QPushButton("关闭")
        close.setObjectName("SubtleButton")
        header.addLayout(title_box, 1)
        header.addWidget(multi_select)
        header.addWidget(delete_file)
        header.addWidget(close)
        list_widget = QListWidget()
        list_widget.setObjectName("RecordList")
        list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        status = QLabel("")
        status.setObjectName("DataStatus")
        status.setWordWrap(True)
        actions = QHBoxLayout()
        open_folder = QPushButton("打开文件夹")
        open_folder.setObjectName("PrimaryButton")
        open_folder.setMinimumWidth(100)
        remove_record = QPushButton("清除记录")
        remove_record.setObjectName("SubtleButton")
        remove_record.setMinimumWidth(100)
        actions.addStretch()
        actions.addWidget(open_folder)
        actions.addWidget(remove_record)
        layout.addLayout(header)
        layout.addWidget(list_widget, 1)
        layout.addWidget(status)
        layout.addLayout(actions)

        def refresh() -> None:
            list_widget.clear()
            history = self.service.list_download_history()
            if not history:
                status.setText("下载历史为空")
                self._add_empty_record_item(list_widget, "当前没有下载记录")
                return
            status.setText(f"共 {len(history)} 条下载记录")
            for record in history:
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 74))
                item.setData(Qt.ItemDataRole.UserRole, record.id)
                state = "文件存在" if record.exists else "文件已删除"
                summary = RecordSummary(
                    id=record.id,
                    type=RecordType.SECURE_NOTE,
                    name=record.filename,
                    account=record.saved_path,
                    category=state,
                    favorite=False,
                    created_at=record.downloaded_at,
                    updated_at=record.downloaded_at,
                )
                subtitle_text = (
                    f"{_format_size_bytes(record.size_bytes)} · {record.saved_path}"
                )
                list_widget.addItem(item)
                list_widget.setItemWidget(item, RecordListItem(summary, subtitle_text))

        def selected_items() -> list[QListWidgetItem]:
            return self._selected_items(list_widget)

        def selected_records():
            records = []
            for item in selected_items():
                record = self._download_history_record_from_item(item)
                if record is not None:
                    records.append(record)
            return records

        def selected_record():
            item = list_widget.currentItem()
            if item is None or item.flags() == Qt.ItemFlag.NoItemFlags:
                return None
            record_id = item.data(Qt.ItemDataRole.UserRole)
            return next(
                (entry for entry in self.service.list_download_history() if entry.id == record_id),
                None,
            )

        def open_record_item(item: QListWidgetItem) -> None:
            if item is None or item.flags() == Qt.ItemFlag.NoItemFlags:
                return
            record = self._download_history_record_from_item(item)
            if record is None:
                return
            self._open_local_path(record.saved_path, status)

        def toggle_multi_select() -> None:
            multi_enabled = (
                list_widget.selectionMode()
                != QAbstractItemView.SelectionMode.MultiSelection
            )
            list_widget.setSelectionMode(
                QAbstractItemView.SelectionMode.MultiSelection
                if multi_enabled
                else QAbstractItemView.SelectionMode.SingleSelection
            )
            multi_select.setText("取消多选" if multi_enabled else "多选")
            self._refresh_button_style(multi_select)

        def delete_selected_files() -> None:
            records = selected_records()
            if not records:
                status.setText("请先选择下载记录")
                return
            message = self._delete_download_history_files(records)
            self._refresh_download_history()
            refresh()
            status.setText(message)

        def remove_selected() -> None:
            records = selected_records()
            if not records:
                record = selected_record()
                records = [record] if record is not None else []
            if not records:
                return
            for record in records:
                self.service.delete_download_history_record(record.id)
            self._refresh_download_history()
            refresh()

        list_widget.customContextMenuRequested.connect(
            lambda position: self._show_download_history_context_menu(
                list_widget,
                position,
                refresh,
                status,
            )
        )
        list_widget.itemDoubleClicked.connect(open_record_item)
        multi_select.clicked.connect(toggle_multi_select)
        delete_file.clicked.connect(delete_selected_files)
        open_folder.clicked.connect(self._open_transfer_download_folder)
        remove_record.clicked.connect(remove_selected)
        close.clicked.connect(dialog.close)
        refresh()
        self.download_history_dialog = dialog
        dialog.show()

    def _show_toast(self, message: str) -> None:
        if not message:
            return
        if self.toast_notice is None:
            self.toast_notice = QLabel(self)
            self.toast_notice.setObjectName("ToastNotice")
            self.toast_notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast_notice.setText(message)
        self.toast_notice.adjustSize()
        width = min(max(self.toast_notice.width() + 28, 180), 520)
        height = max(self.toast_notice.height() + 10, 42)
        sidebar_width = 220
        x = sidebar_width + max(20, (self.width() - sidebar_width - width) // 2)
        self.toast_notice.setGeometry(x, 32, width, height)
        self.toast_notice.show()
        self.toast_notice.raise_()
        QTimer.singleShot(1800, self.toast_notice.hide)

    def _change_master_password(self) -> None:
        dialog = ChangePasswordDialog(self)
        if not dialog.exec():
            return
        old_password, new_password, confirm_password = dialog.values()
        if not old_password or not new_password:
            QMessageBox.warning(self, "信息不完整", "原保险箱密码和新保险箱密码都需要填写。")
            return
        if new_password != confirm_password:
            QMessageBox.warning(self, "两次密码不一致", "请重新确认新保险箱密码。")
            return
        result = try_unlock(self.service, old_password)
        if not result.ok:
            QMessageBox.warning(self, "无法修改", result.message)
            return
        self.service.change_master_password(old_password, new_password)
        QMessageBox.information(self, "修改成功", "保险箱密码已修改，下次打开请使用新密码。")

    def _refresh_settings_view(self) -> None:
        self.settings_vault_label.setText(f"当前保险箱ID：{self.vault_name}")
        self.transfer_download_dir_label.setText(str(self.settings.transfer_download_dir))
        backup_dir = self.profile_settings.backup_dir or "未设置"
        backup_file = ""
        if backup_dir != "未设置":
            backup_file = backup_file_for_vault(Path(backup_dir), self.vault_name).name
        suffix = f"\n备份文件：{backup_file}" if backup_file else ""
        self.backup_dir_label.setText(f"备份位置：{backup_dir}{suffix}")
        self.auto_sync_check.blockSignals(True)
        self.auto_sync_check.setChecked(self.profile_settings.auto_sync_on_close)
        self.auto_sync_check.blockSignals(False)
        self.theme_combo.blockSignals(True)
        theme_index = self.theme_combo.findData(
            normalize_theme_name(self.profile_settings.theme_name)
        )
        self.theme_combo.setCurrentIndex(max(0, theme_index))
        self.theme_combo.blockSignals(False)
        self._sync_auto_lock_controls()

    def _choose_backup_dir(self) -> None:
        start_dir = self.profile_settings.backup_dir or "E:\\BaiduSyncdisk"
        directory = QFileDialog.getExistingDirectory(self, "选择备份位置", start_dir)
        if not directory:
            return
        self.profile_settings.backup_dir = directory
        save_profile_settings(self.profile_base_dir, self.vault_name, self.profile_settings)
        self._refresh_settings_view()

    def _choose_transfer_download_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择传输助手默认下载位置",
            str(self.settings.transfer_download_dir),
        )
        if not directory:
            return
        self.settings = AppSettings(
            vault_path=self.settings.vault_path,
            auto_lock_seconds=self.settings.auto_lock_seconds,
            clipboard_clear_seconds=self.settings.clipboard_clear_seconds,
            transfer_download_dir=Path(directory),
        )
        self.profile_settings.transfer_download_dir = str(self.settings.transfer_download_dir)
        save_profile_settings(self.profile_base_dir, self.vault_name, self.profile_settings)
        self._refresh_settings_view()
        self._show_toast("已更新默认下载位置")

    def _sync_current_vault(self) -> None:
        if not self.profile_settings.backup_dir:
            QMessageBox.warning(self, "未设置备份位置", "请先在设置里选择备份位置。")
            return
        target = sync_vault_to_backup(
            self.service.store.path,
            Path(self.profile_settings.backup_dir),
            self.vault_name,
        )
        QMessageBox.information(self, "同步完成", f"已更新备份文件：{target.name}")
        self._refresh_settings_view()

    def _restore_current_vault_from_backup(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "选择 SafeBox 备份",
            self.profile_settings.backup_dir,
            "SafeBox 备份 (*.pmbackup)",
        )
        if not file_name:
            return
        reply = QMessageBox.question(
            self,
            "从备份恢复",
            "恢复会覆盖当前保险箱的数据，确定继续吗？",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.service.lock()
        restore_vault_from_backup(Path(file_name), self.service.store.path)
        QMessageBox.information(self, "恢复完成", "请重新输入保险箱密码打开恢复后的数据。")
        QTimer.singleShot(0, self._open_vault)

    def _set_auto_sync_on_close(self, enabled: bool) -> None:
        self.profile_settings.auto_sync_on_close = enabled
        save_profile_settings(self.profile_base_dir, self.vault_name, self.profile_settings)

    def _apply_theme(self, theme_name: str) -> None:
        normalized = normalize_theme_name(theme_name)
        self.active_theme_name = normalized
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(stylesheet_for_theme(normalized))

    def _set_theme_from_settings(self) -> None:
        theme_name = self.theme_combo.currentData()
        if not isinstance(theme_name, str):
            return
        theme_name = normalize_theme_name(theme_name)
        self.profile_settings.theme_name = theme_name
        self._apply_theme(theme_name)
        save_profile_settings(self.profile_base_dir, self.vault_name, self.profile_settings)

    def _sync_auto_lock_controls(self) -> None:
        seconds = self.profile_settings.auto_lock_seconds
        self.auto_lock_combo.blockSignals(True)
        self.custom_auto_lock_minutes.blockSignals(True)
        if seconds == 5 * 60:
            self.auto_lock_combo.setCurrentText("5分钟")
            self.custom_auto_lock_minutes.setVisible(False)
        elif seconds == 20 * 60:
            self.auto_lock_combo.setCurrentText("20分钟")
            self.custom_auto_lock_minutes.setVisible(False)
        elif seconds == 0:
            self.auto_lock_combo.setCurrentText("从不锁定")
            self.custom_auto_lock_minutes.setVisible(False)
        else:
            self.auto_lock_combo.setCurrentText("自定义")
            self.custom_auto_lock_minutes.setValue(max(1, seconds // 60))
            self.custom_auto_lock_minutes.setVisible(True)
        self.custom_auto_lock_minutes.blockSignals(False)
        self.auto_lock_combo.blockSignals(False)

    def _set_auto_lock_mode(self, mode: str) -> None:
        self.custom_auto_lock_minutes.setVisible(mode == "自定义")
        if mode == "自定义":
            seconds = self.custom_auto_lock_minutes.value() * 60
        else:
            seconds = AUTO_LOCK_PRESETS[mode]
        self._save_auto_lock_seconds(seconds)

    def _set_custom_auto_lock_minutes(self, minutes: int) -> None:
        if self.auto_lock_combo.currentText() == "自定义":
            self._save_auto_lock_seconds(minutes * 60)

    def _save_auto_lock_seconds(self, seconds: int) -> None:
        self.profile_settings.auto_lock_seconds = seconds
        save_profile_settings(self.profile_base_dir, self.vault_name, self.profile_settings)
        self._apply_auto_lock_settings()

    def _apply_auto_lock_settings(self) -> None:
        seconds = self.profile_settings.auto_lock_seconds
        if seconds <= 0:
            self.idle_timer.stop()
            return
        self.idle_timer.setInterval(seconds * 1000)
        if self.service.is_unlocked():
            self.idle_timer.start()

    def _auto_sync_current_vault(self) -> None:
        if (
            not self.service.is_unlocked()
            or not self.profile_settings.auto_sync_on_close
            or not self.profile_settings.backup_dir
        ):
            return
        try:
            sync_vault_to_backup(
                self.service.store.path,
                Path(self.profile_settings.backup_dir),
                self.vault_name,
            )
        except OSError:
            pass

    def _populate_sort_combo(self, combo: QComboBox) -> None:
        for mode, label in SORT_MODE_LABELS.items():
            combo.addItem(label, mode.value)

    def _selected_sort_mode(self, combo: QComboBox) -> SortMode:
        value = combo.currentData()
        if isinstance(value, str):
            return SortMode(value)
        return SortMode.UPDATED_DESC

    def _refresh_accounts(self) -> None:
        query = self.account_search.text().strip()
        self.account_list.setUpdatesEnabled(False)
        self.account_list.clear()
        self._apply_batch_mode("accounts", self.account_list)
        try:
            records = self.service.active_records()
            all_summaries = [self.service.summary_for(record) for record in records]
            term = query.casefold()
            summaries = [
                self.service.summary_for(record)
                for record in records
                if record.type == RecordType.ACCOUNT
                and (not term or term in _record_search_text(record))
            ]
            sorted_accounts = sorted_summaries(
                summaries,
                self._selected_sort_mode(self.account_sort),
            )
            self._update_data_status("accounts", all_summaries, len(sorted_accounts))
            if not sorted_accounts:
                self._add_empty_record_item(
                    self.account_list,
                    "当前没有账号记录" if not query else "没有找到匹配的账号记录",
                )
                return
            for summary in sorted_accounts:
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 74))
                item.setData(Qt.ItemDataRole.UserRole, summary.id)
                self.account_list.addItem(item)
                self.account_list.setItemWidget(item, RecordListItem(summary, ""))
        finally:
            self.account_list.setUpdatesEnabled(True)
            self.account_list.viewport().update()

    def _refresh_notes(self) -> None:
        query = self.note_search.text().strip()
        self.note_list.setUpdatesEnabled(False)
        self.note_list.clear()
        self._apply_batch_mode("notes", self.note_list)
        try:
            records = self.service.active_records()
            all_summaries = [self.service.summary_for(record) for record in records]
            term = query.casefold()
            note_records = [
                record
                for record in records
                if record.type == RecordType.SECURE_NOTE
                and (not term or term in _record_search_text(record))
            ]
            sorted_notes = sorted_summaries(
                [self.service.summary_for(record) for record in note_records],
                self._selected_sort_mode(self.note_sort),
            )
            notes_by_id = {record.id: record for record in note_records}
            self._update_data_status("notes", all_summaries, len(sorted_notes))
            if not sorted_notes:
                self._add_empty_record_item(
                    self.note_list,
                    "当前没有小纸条记录" if not query else "没有找到匹配的小纸条记录",
                )
                return
            for summary in sorted_notes:
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 74))
                item.setData(Qt.ItemDataRole.UserRole, summary.id)
                self.note_list.addItem(item)
                record = notes_by_id[summary.id]
                self.note_list.setItemWidget(
                    item,
                    RecordListItem(summary, note_plain_summary(record.note)),
                )
        finally:
            self.note_list.setUpdatesEnabled(True)
            self.note_list.viewport().update()

    def _refresh_transfer_conversations(self) -> None:
        query = self.transfer_search.text().strip()
        self.transfer_list.setUpdatesEnabled(False)
        self.transfer_list.clear()
        self._apply_batch_mode("transfer", self.transfer_list)
        try:
            conversations = self.service.list_transfer_conversations(query)
            self.transfer_status.setText("")
            self.transfer_status.setVisible(False)
            if not conversations:
                self._add_empty_record_item(
                    self.transfer_list,
                    "当前没有传输记录" if not query else "没有找到匹配的传输记录",
                )
                return
            for conversation in conversations:
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 74))
                item.setData(Qt.ItemDataRole.UserRole, conversation.id)
                self.transfer_list.addItem(item)
                summary = RecordSummary(
                    id=conversation.id,
                    type=RecordType.SECURE_NOTE,
                    name=conversation.title,
                    account=conversation.device_name,
                    category=self._transfer_conversation_status_label(conversation),
                    favorite=False,
                    created_at=conversation.created_at,
                    updated_at=conversation.updated_at,
                )
                subtitle = (
                    f"{conversation.device_name} · "
                    f"消息 {conversation.message_count} · 附件 {conversation.attachment_count}"
                )
                self.transfer_list.setItemWidget(item, RecordListItem(summary, subtitle))
        finally:
            self.transfer_list.setUpdatesEnabled(True)
            self.transfer_list.viewport().update()

    def _open_transfer_item(self, item: QListWidgetItem) -> None:
        if self.batch_modes.get("transfer"):
            return
        self.current_transfer_id = item.data(Qt.ItemDataRole.UserRole)
        conversation = self.service.get_transfer_conversation(self.current_transfer_id)
        if self._transfer_conversation_is_open(conversation):
            self._show_transfer_chat(conversation.id)
            return
        self.transfer_detail_title.setText(conversation.title)
        self.transfer_detail_meta.setText(
            f"{conversation.device_name} · {self._transfer_conversation_status_label(conversation)}"
        )
        self._render_transfer_messages(
            conversation.id,
            target_view=self.transfer_detail_messages_view,
        )
        self._remember_module_page("transfer", self.transfer_detail_page)
        self.pages.setCurrentWidget(self.transfer_detail_page)

    def _show_connect_phone_placeholder(self) -> None:
        active_conversation = self._open_transfer_conversation()
        if active_conversation is not None:
            self.current_transfer_id = active_conversation.id
            link_text = self._current_transfer_link_text()
            self.transfer_connect_type_value.setText("当前已有进行中的手机会话")
            self.transfer_connect_url_value.setText(
                link_text or "当前会话已存在，请进入对话继续使用"
            )
            self.transfer_connect_code_value.setText("已有进行中的会话")
            self._clear_trusted_transfer_link()
            status = "已有进行中的手机会话，可进入当前对话"
            if link_text:
                status = f"{status}或复制连接。"
            else:
                status = f"{status}。"
            self.transfer_connect_status.setText(status)
            self._refresh_trusted_transfer_devices()
            self._remember_module_page("transfer", self.transfer_connect_page)
            self._set_nav("transfer")
            self.pages.setCurrentWidget(self.transfer_connect_page)
            self._show_toast("已有进行中的手机会话")
            return
        if self.transfer_server is not None:
            self._stop_transfer_server(close_conversation=True)
        self._start_transfer_server("手机浏览器")
        self.transfer_status.setText("")
        self.transfer_status.setVisible(False)
        self.current_transfer_id = ""
        self.transfer_connect_mode = "browser"
        self.transfer_trusted_device_name = ""
        self.transfer_connect_type_value.setText("给未信任或首次连接的手机使用")
        self.transfer_connect_url_value.setText(self.transfer_server.display_url)
        self.transfer_connect_code_value.setText(
            f"验证码：{self.transfer_server.verification_code}"
        )
        self.transfer_connect_status.setText(
            "复制新手机链接，发到手机浏览器打开；手机输入验证码后才会创建对话。"
        )
        self._clear_trusted_transfer_link()
        self._refresh_trusted_transfer_devices()
        self._remember_module_page("transfer", self.transfer_connect_page)
        self._set_nav("transfer")
        self.pages.setCurrentWidget(self.transfer_connect_page)
        self.transfer_pair_timer.start()

    def _clear_trusted_transfer_link(self) -> None:
        self.transfer_trusted_link_title.setText("可信设备链接")
        self.transfer_trusted_link_title.setVisible(False)
        self.transfer_trusted_link_value.setText("")
        self.transfer_trusted_link_value.setVisible(False)
        self.transfer_trusted_copy_button.setVisible(False)
        self.transfer_trusted_status.setText(
            "选择可信设备后，会在这里显示专用连接链接。"
        )

    def _show_trusted_transfer_link(self, device_name: str, link: str) -> None:
        self.transfer_trusted_link_title.setText(f"可信设备：{device_name}")
        self.transfer_trusted_link_title.setVisible(True)
        self.transfer_trusted_link_value.setText(link)
        self.transfer_trusted_link_value.setVisible(True)
        self.transfer_trusted_copy_button.setVisible(True)
        self.transfer_trusted_status.setText(
            f"等待 {device_name} 打开可信设备链接，连接后才会创建对话。"
        )

    def _start_transfer_server(self, device_name: str) -> None:
        from safebox.net.transfer_server import TransferHttpServer

        self.transfer_server = TransferHttpServer(self.service, device_name=device_name)
        self.transfer_server.start()

    def _open_transfer_conversation(self):
        for conversation in self.service.list_transfer_conversations():
            if self._transfer_conversation_is_open(conversation):
                return conversation
        return None

    def _check_transfer_pairing(self) -> None:
        if self.transfer_server is None:
            self.transfer_pair_timer.stop()
            return
        if not self.transfer_server.paired or not self.transfer_server.conversation_id:
            if self.transfer_connect_mode == "trusted" and self.transfer_trusted_device_name:
                self.transfer_trusted_status.setText(
                    f"等待 {self.transfer_trusted_device_name} 打开可信设备链接。"
                )
            else:
                self.transfer_connect_status.setText("等待手机打开新手机连接链接。")
            return
        try:
            conversation = self.service.get_transfer_conversation(
                self.transfer_server.conversation_id
            )
        except KeyError:
            self.transfer_pair_timer.stop()
            return
        if not self._transfer_conversation_is_open(conversation):
            self.transfer_pair_timer.stop()
            if self.transfer_connect_mode == "trusted":
                self.transfer_trusted_status.setText("此次可信设备连接已关闭。")
            else:
                self.transfer_connect_status.setText("此次连接已关闭。")
            return
        self.transfer_pair_timer.stop()
        self._show_transfer_chat(conversation.id)

    def _show_transfer_chat(self, conversation_id: str) -> None:
        if self.current_transfer_id != conversation_id:
            self.transfer_messages_signature = ""
        self.current_transfer_id = conversation_id
        conversation = self.service.get_transfer_conversation(conversation_id)
        writable = self._transfer_conversation_is_open(conversation)
        self.transfer_chat_title.setText(conversation.title)
        self.transfer_chat_meta.setText(self._transfer_chat_meta(conversation.id))
        self._refresh_transfer_trust_button(conversation.device_name)
        if self.transfer_server is None or conversation.id != self.transfer_server.conversation_id:
            self.transfer_chat_connection.setText("")
            self.transfer_chat_connection.setVisible(False)
            self.transfer_copy_link_button.setVisible(False)
        else:
            self._refresh_transfer_connection_status(conversation)
        self._render_transfer_messages(conversation_id)
        self.transfer_message_input.setEnabled(writable)
        self.transfer_send_button.setEnabled(writable)
        self.transfer_send_image_button.setEnabled(writable)
        self.transfer_send_file_button.setEnabled(writable)
        self.transfer_close_button.setVisible(writable)
        self._remember_module_page("transfer", self.transfer_chat_page)
        self._set_nav("transfer")
        self.pages.setCurrentWidget(self.transfer_chat_page)
        if writable and not self.transfer_refresh_timer.isActive():
            self.transfer_refresh_timer.start()
        if not writable:
            self.transfer_refresh_timer.stop()

    def _refresh_transfer_trust_button(self, device_name: str) -> None:
        trusted = self._trusted_device_by_name(device_name) is not None
        self.transfer_trust_device_button.setText("已信任设备" if trusted else "信任此设备")
        self.transfer_trust_device_button.setEnabled(not trusted)
        self._refresh_button_style(self.transfer_trust_device_button)

    def _refresh_active_transfer_chat(self) -> None:
        if (
            not self.current_transfer_id
            or not self.service.is_unlocked()
            or self.pages.currentWidget() != self.transfer_chat_page
        ):
            return
        try:
            conversation = self.service.get_transfer_conversation(self.current_transfer_id)
            if not self._transfer_conversation_is_open(conversation):
                self.transfer_refresh_timer.stop()
                self._show_transfer_chat(conversation.id)
                return
            self.transfer_chat_meta.setText(self._transfer_chat_meta(self.current_transfer_id))
            self._refresh_transfer_connection_status(conversation)
            self._render_transfer_messages(self.current_transfer_id)
        except KeyError:
            self.transfer_refresh_timer.stop()

    def _send_current_transfer_text(self) -> None:
        if not self.current_transfer_id:
            return
        conversation = self.service.get_transfer_conversation(self.current_transfer_id)
        if not self._transfer_conversation_is_open(conversation):
            return
        text = self.transfer_message_input.toPlainText().strip()
        if not text:
            return
        try:
            self.service.add_transfer_text_message(
                self.current_transfer_id,
                sender=TransferMessageSender.DESKTOP,
                text=text,
            )
        except ValueError as exc:
            self._set_transfer_attachment_status(str(exc))
            return
        self.transfer_message_input.clear()
        self._show_transfer_chat(self.current_transfer_id)

    def _send_current_transfer_file(self) -> None:
        self._send_current_transfer_local_file("选择要发送的文件")

    def _send_current_transfer_image(self) -> None:
        self._send_current_transfer_local_file(
            "选择要发送的图片",
            "图片文件 (*.png *.jpg *.jpeg *.webp *.gif);;所有文件 (*)",
        )

    def _send_current_transfer_local_file(
        self,
        title: str,
        file_filter: str = "",
    ) -> None:
        if not self.current_transfer_id:
            return
        conversation = self.service.get_transfer_conversation(self.current_transfer_id)
        if not self._transfer_conversation_is_open(conversation):
            return
        filename, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
        if not filename:
            return
        source = Path(filename)
        if not source.exists():
            self._set_transfer_attachment_status("文件不存在")
            return
        target_dir = self.service.store.path.parent / "attachments" / conversation.id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = _unique_local_path(target_dir / source.name)
        copy2(source, target)
        mime_type = _guess_mime_type(source)
        kind = (
            TransferMessageKind.IMAGE
            if mime_type.startswith("image/")
            or source.suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}
            else TransferMessageKind.FILE
        )
        self.service.add_transfer_attachment_message(
            self.current_transfer_id,
            sender=TransferMessageSender.DESKTOP,
            kind=kind,
            filename=source.name,
            mime_type=mime_type,
            size_bytes=target.stat().st_size,
            storage_path=str(target),
        )
        self._show_transfer_chat(self.current_transfer_id)

    def _copy_transfer_link(self) -> None:
        text = self._current_transfer_link_text()
        if not text:
            return
        self.clipboard.copy(text)
        self.transfer_chat_connection.setText(f"手机访问：{text}\n链接已复制。")
        if self.pages.currentWidget() == self.transfer_connect_page:
            if self.transfer_connect_mode == "trusted":
                device_name = self.transfer_trusted_device_name or "可信设备"
                self.transfer_trusted_status.setText(
                    f"可信设备链接已复制，请发送给 {device_name} 打开。"
                )
                self._show_toast("可信设备链接已复制")
                return
            self.transfer_connect_status.setText(
                "新手机连接链接已复制，请发送到手机浏览器打开，并输入电脑端验证码。"
            )
        self._show_toast("连接链接已复制")

    def _current_transfer_link_text(self) -> str:
        if self.transfer_server is None:
            return ""
        return self.transfer_server.display_url

    def _refresh_transfer_connection_status(self, conversation) -> None:
        if self.transfer_server is None or conversation.id != self.transfer_server.conversation_id:
            return
        if self.transfer_server.paired:
            self.transfer_chat_connection.setText("")
            self.transfer_chat_connection.setVisible(False)
            self.transfer_copy_link_button.setVisible(False)
            return
        pair_status = "等待手机打开链接"
        self.transfer_chat_connection.setText(
            f"手机访问：{self.transfer_server.display_url}\n"
            f"{pair_status}，打开链接即可连接。{self._transfer_chat_hint(conversation)}"
        )
        self.transfer_chat_connection.setVisible(True)
        self.transfer_copy_link_button.setVisible(True)

    def _transfer_chat_hint(self, conversation) -> str:
        if not self._transfer_conversation_is_open(conversation):
            return "此次对话已关闭，只能查看历史消息"
        if conversation.note_id:
            return "已转存为小纸条，新消息会继续同步到该小纸条"
        return "可互发文字、图片和文件"

    def _transfer_conversation_is_open(self, conversation) -> bool:
        return (
            conversation.status
            in {TransferConversationStatus.ACTIVE, TransferConversationStatus.TRANSFERRED}
            and not conversation.closed_at
        )

    def _transfer_conversation_status_label(self, conversation) -> str:
        if conversation.closed_at:
            return "已关闭 · 已转存" if conversation.note_id else "已关闭"
        return _transfer_status_label(conversation.status.value)

    def _close_current_transfer_chat(self) -> None:
        if not self.current_transfer_id:
            return
        self.transfer_refresh_timer.stop()
        self.service.close_transfer_conversation(self.current_transfer_id)
        self._show_transfer_list_page()

    def _open_current_transfer_chat(self) -> None:
        if self.current_transfer_id:
            self._show_transfer_chat(self.current_transfer_id)

    def _refresh_trusted_transfer_devices(self) -> None:
        self.transfer_trusted_list.clear()
        devices = self.profile_settings.trusted_transfer_devices
        if not devices:
            self._add_empty_record_item(self.transfer_trusted_list, "暂无可信设备")
            return
        for device in devices:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 74))
            item.setData(Qt.ItemDataRole.UserRole, device["id"])
            self.transfer_trusted_list.addItem(item)
            summary = RecordSummary(
                id=device["id"],
                type=RecordType.SECURE_NOTE,
                name=device["name"],
                account="可信手机",
                category="可信设备",
                favorite=False,
                created_at=device.get("last_connected_at", ""),
                updated_at=device.get("last_connected_at", ""),
            )
            subtitle = device.get("last_connected_at", "") or "点击后创建新的手机对话"
            self.transfer_trusted_list.setItemWidget(item, RecordListItem(summary, subtitle))

    def _connect_selected_trusted_device(self) -> None:
        item = self.transfer_trusted_list.currentItem()
        if item is None or item.flags() == Qt.ItemFlag.NoItemFlags:
            self._show_toast("请选择可信设备")
            return
        device = self._trusted_device_by_id(item.data(Qt.ItemDataRole.UserRole))
        if device is None:
            self._show_toast("可信设备不存在")
            self._refresh_trusted_transfer_devices()
            return
        active_conversation = self._open_transfer_conversation()
        if active_conversation is not None:
            self.current_transfer_id = active_conversation.id
            self._show_toast("已有进行中的手机会话")
            return
        if self.transfer_server is not None:
            self._stop_transfer_server(close_conversation=True)
        self._start_transfer_server(device["name"])
        self.current_transfer_id = ""
        self.transfer_connect_mode = "trusted"
        self.transfer_trusted_device_name = device["name"]
        device["last_connected_at"] = _now_local()
        save_profile_settings(self.profile_base_dir, self.vault_name, self.profile_settings)
        self.transfer_connect_type_value.setText("给未信任或首次连接的手机使用")
        self.transfer_connect_url_value.setText("未启动新手机连接")
        self.transfer_connect_code_value.setText("已切换为可信设备连接")
        self.transfer_connect_status.setText(
            "当前正在等待可信设备连接，请使用下方可信设备专用链接。"
        )
        self._show_trusted_transfer_link(device["name"], self.transfer_server.display_url)
        self._refresh_trusted_transfer_devices()
        self.transfer_pair_timer.start()
        self._show_toast("已准备可信设备连接")

    def _trust_current_transfer_device(self) -> None:
        if not self.current_transfer_id:
            return
        conversation = self.service.get_transfer_conversation(self.current_transfer_id)
        default_name = conversation.device_name or "我的手机"
        if self._trusted_device_by_name(default_name) is not None:
            self._refresh_transfer_trust_button(default_name)
            self._show_toast("此设备已信任")
            return
        name, ok = QInputDialog.getText(self, "信任此设备", "设备名称", text=default_name)
        if not ok:
            return
        clean_name = name.strip() or default_name
        existing = self._trusted_device_by_name(clean_name)
        if existing is None:
            self.profile_settings.trusted_transfer_devices.append(
                {
                    "id": f"td_{uuid4().hex}",
                    "name": clean_name,
                    "last_connected_at": _now_local(),
                }
            )
        else:
            existing["last_connected_at"] = _now_local()
        save_profile_settings(self.profile_base_dir, self.vault_name, self.profile_settings)
        self._refresh_transfer_trust_button(clean_name)
        self._show_toast("已信任此设备")

    def _trusted_device_by_id(self, device_id: str) -> dict[str, str] | None:
        return next(
            (
                device
                for device in self.profile_settings.trusted_transfer_devices
                if device["id"] == device_id
            ),
            None,
        )

    def _trusted_device_by_name(self, device_name: str) -> dict[str, str] | None:
        clean_name = device_name.strip()
        return next(
            (
                device
                for device in self.profile_settings.trusted_transfer_devices
                if device["name"] == clean_name
            ),
            None,
        )

    def _delete_current_transfer_record(self) -> None:
        if not self.current_transfer_id:
            return
        conversation = self.service.get_transfer_conversation(self.current_transfer_id)
        if self._transfer_conversation_is_open(conversation):
            self.transfer_detail_notice.setText("进行中的对话不能删除，请先关闭此次对话")
            return
        self.service.delete_transfer_conversation(self.current_transfer_id)
        self.current_transfer_id = ""
        self._show_transfer_list_page()

    def _export_current_transfer_to_note(self) -> None:
        if not self.current_transfer_id:
            return
        self.service.export_transfer_conversation_to_note(self.current_transfer_id)
        self.transfer_chat_meta.setText(self._transfer_chat_meta(self.current_transfer_id))
        self._refresh_notes()
        self._show_toast("已转存为小纸条")

    def _format_transfer_messages(self, conversation_id: str) -> str:
        lines: list[str] = []
        for message in self.service.list_transfer_messages(conversation_id):
            sender = "电脑" if message.sender == TransferMessageSender.DESKTOP else "手机"
            content = message.text or self._transfer_message_attachment_label(
                conversation_id,
                message.attachment_id,
            )
            lines.append(f"{sender} {message.created_at}\n{content}")
        return "\n\n".join(lines)

    def _render_transfer_messages(
        self,
        conversation_id: str,
        *,
        target_view: TransferMessageList | None = None,
    ) -> None:
        view = target_view or self.transfer_messages_view
        messages = self.service.list_transfer_messages(conversation_id)
        attachments = self.service.list_transfer_attachments(conversation_id)
        signature = self._transfer_messages_signature(messages, attachments)
        if target_view is None and signature == self.transfer_messages_signature:
            return
        if target_view is None:
            self.transfer_messages_signature = signature
        view.set_messages(
            messages,
            {attachment.id: attachment for attachment in attachments},
            preview_attachment=self._preview_transfer_attachment_by_id,
            download_attachment=self._download_transfer_attachment_by_id,
        )

    def _transfer_messages_signature(self, messages, attachments) -> str:
        message_parts = [
            f"{message.id}:{message.updated_at}:{message.edited_at}:{message.text}:"
            f"{message.attachment_id}"
            for message in messages
        ]
        attachment_parts = [
            f"{attachment.id}:{attachment.filename}:{attachment.size_bytes}:"
            f"{attachment.storage_path}"
            for attachment in attachments
        ]
        return "|".join([*message_parts, *attachment_parts])

    def _show_current_transfer_attachments(self) -> None:
        if not self.current_transfer_id:
            return
        self._show_transfer_attachments_dialog(self.current_transfer_id)

    def _download_current_transfer_attachments(self, conversation_id: str = "") -> None:
        target_conversation_id = conversation_id or self.current_transfer_id
        if not target_conversation_id:
            return
        attachments = self.service.list_transfer_attachments(target_conversation_id)
        downloaded = 0
        failed = 0
        for attachment in attachments:
            try:
                self.service.download_transfer_attachment(
                    conversation_id=target_conversation_id,
                    attachment_id=attachment.id,
                    download_dir=self.settings.transfer_download_dir,
                )
                downloaded += 1
            except FileNotFoundError:
                failed += 1
        message = f"已下载 {downloaded} 个附件"
        if failed:
            message = f"{message}，{failed} 个源文件不存在"
        self._set_transfer_attachment_status(message)
        self._refresh_download_history()
        self._show_download_history_dialog()

    def _download_transfer_attachment_by_id(self, attachment_id: str) -> None:
        if not self.current_transfer_id:
            return
        attachment = self._download_transfer_attachment(
            self.current_transfer_id,
            attachment_id,
        )
        if attachment is not None:
            self._set_transfer_attachment_status(f"已下载 {attachment.filename}")
            self._show_download_history_dialog()

    def _preview_transfer_attachment_by_id(self, attachment_id: str) -> None:
        if not self.current_transfer_id:
            return
        attachment = next(
            (
                item
                for item in self.service.list_transfer_attachments(self.current_transfer_id)
                if item.id == attachment_id
            ),
            None,
        )
        if attachment is None:
            self._set_transfer_attachment_status("附件不存在")
            return
        self._preview_transfer_image_attachment(attachment)

    def _preview_first_transfer_image(self) -> None:
        if not self.current_transfer_id:
            return
        attachment = self._first_transfer_image_attachment(self.current_transfer_id)
        if attachment is None:
            self._set_transfer_attachment_status("当前会话没有图片附件")
            return
        self._preview_transfer_image_attachment(attachment)

    def _preview_transfer_image_attachment(self, attachment) -> None:
        source = Path(attachment.storage_path)
        if not source.exists():
            self._set_transfer_attachment_status("图片文件不存在")
            return
        pixmap = QPixmap(str(source))
        if pixmap.isNull():
            self._set_transfer_attachment_status("图片无法预览")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(attachment.filename)
        dialog.resize(720, 520)
        layout = QVBoxLayout(dialog)
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setPixmap(
            pixmap.scaled(
                680,
                460,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        layout.addWidget(label)
        self.image_preview_dialog = dialog
        self.image_preview_pixmap = pixmap
        dialog.show()

    def _download_transfer_attachment(self, conversation_id: str, attachment_id: str):
        try:
            return self.service.download_transfer_attachment(
                conversation_id=conversation_id,
                attachment_id=attachment_id,
                download_dir=self.settings.transfer_download_dir,
            )
        except FileNotFoundError:
            self._set_transfer_attachment_status("附件源文件不存在")
            return None

    def _show_transfer_attachments_dialog(self, conversation_id: str) -> None:
        conversation = self.service.get_transfer_conversation(conversation_id)
        attachments = self.service.list_transfer_attachments(conversation_id)
        if not attachments:
            self._set_transfer_attachment_status("当前会话没有附件")
            return
        summary = "；".join(
            f"{attachment.filename} · {attachment.mime_type or '未知类型'} · "
            f"{_format_size_bytes(attachment.size_bytes)}"
            for attachment in attachments
        )
        self._set_transfer_attachment_status(summary)
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{conversation.title} · 会话附件")
        dialog.resize(760, 560)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(12)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("会话附件")
        title.setObjectName("DialogTitle")
        subtitle = QLabel(f"{conversation.title} · 共 {len(attachments)} 个附件")
        subtitle.setObjectName("MutedText")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        download_all = QPushButton("下载全部")
        download_all.setObjectName("PrimaryButton")
        download_all.setMinimumWidth(100)
        close = QPushButton("关闭")
        close.setObjectName("SubtleButton")
        header.addLayout(title_box, 1)
        header.addWidget(download_all)
        header.addWidget(close)
        layout.addLayout(header)
        status = QLabel("")
        status.setObjectName("DataStatus")
        status.setWordWrap(True)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("AttachmentScroll")
        content = QWidget()
        content.setObjectName("AttachmentScrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 2, 2, 2)
        content_layout.setSpacing(10)
        for attachment in attachments:
            row = QFrame()
            row.setObjectName("AttachmentCard")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 12, 14, 12)
            row_layout.setSpacing(12)
            if self._is_transfer_image_attachment(attachment):
                preview_box = QLabel()
                preview_box.setObjectName("AttachmentThumb")
                preview_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
                pixmap = QPixmap(attachment.storage_path)
                if pixmap.isNull():
                    preview_box.setText("图片")
                else:
                    preview_box.setPixmap(
                        pixmap.scaled(
                            128,
                            88,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                row_layout.addWidget(preview_box)
            else:
                file_icon = QLabel("文件")
                file_icon.setObjectName("AttachmentFileIcon")
                file_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                row_layout.addWidget(file_icon)
            info = QLabel(
                f"{attachment.filename}\n"
                f"{attachment.mime_type or '未知类型'} · "
                f"{_format_size_bytes(attachment.size_bytes)}"
            )
            info.setObjectName("AttachmentInfo")
            info.setWordWrap(True)
            row_layout.addWidget(info, 1)
            if self._is_transfer_image_attachment(attachment):
                preview = QPushButton("预览")
                preview.setObjectName("SubtleButton")
                preview.clicked.connect(
                    lambda checked=False, item=attachment: self._preview_transfer_image_attachment(
                        item
                    )
                )
                row_layout.addWidget(preview)
            open_source = QPushButton("打开")
            open_source.setObjectName("SubtleButton")
            open_source.clicked.connect(
                lambda checked=False, path=attachment.storage_path: self._open_local_path(
                    path,
                    status,
                )
            )
            download = QPushButton("下载")
            download.setObjectName("PrimaryButton")
            download.setMinimumWidth(74)
            download.clicked.connect(
                lambda checked=False, item=attachment: self._download_dialog_attachment(
                    conversation_id,
                    item.id,
                    status,
                )
            )
            row_layout.addWidget(open_source)
            row_layout.addWidget(download)
            content_layout.addWidget(row)
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        layout.addWidget(status)
        download_all.clicked.connect(
            lambda: self._download_current_transfer_attachments(conversation_id)
        )
        close.clicked.connect(dialog.close)
        self.transfer_attachments_dialog = dialog
        dialog.show()

    def _download_dialog_attachment(
        self,
        conversation_id: str,
        attachment_id: str,
        status: QLabel,
    ) -> None:
        record = self._download_transfer_attachment(conversation_id, attachment_id)
        if record is None:
            status.setText("下载失败：附件源文件不存在")
            return
        status.setText(f"已下载：{record.saved_path}")
        self._show_toast(f"已下载 {record.filename}")
        self._refresh_download_history()
        self._show_download_history_dialog()

    def _open_local_path(self, path: str, status: QLabel | None = None) -> None:
        source = Path(path)
        if not source.exists():
            if status is not None:
                status.setText("文件不存在，可能已被移动或删除")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(source)))

    def _reveal_local_path(self, path: str, status: QLabel | None = None) -> None:
        source = Path(path)
        target = source if source.exists() else source.parent
        if not target.exists():
            if status is not None:
                status.setText("文件和所在文件夹都不存在")
            return
        if source.exists():
            Popen(["explorer", "/select,", str(source)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _is_transfer_image_attachment(self, attachment) -> bool:
        if attachment.mime_type.startswith("image/"):
            return True
        return Path(attachment.filename).suffix.casefold() in {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".gif",
        }

    def _first_transfer_image_attachment(self, conversation_id: str):
        for attachment in self.service.list_transfer_attachments(conversation_id):
            if self._is_transfer_image_attachment(attachment):
                return attachment
        return None

    def _set_transfer_attachment_status(self, message: str) -> None:
        self._show_toast(message)
        if self.pages.currentWidget() == self.transfer_detail_page:
            self.transfer_detail_notice.setText(message)
            return
        if self.pages.currentWidget() == self.transfer_chat_page:
            self.transfer_chat_meta.setText(message)

    def _format_transfer_attachments(self, conversation_id: str) -> str:
        attachments = self.service.list_transfer_attachments(conversation_id)
        if not attachments:
            return "当前会话没有附件"
        lines = ["附件列表"]
        for attachment in attachments:
            lines.append(
                f"{attachment.filename} · {attachment.mime_type or '未知类型'} · "
                f"{_format_size_bytes(attachment.size_bytes)}"
            )
        return "\n".join(lines)

    def _transfer_message_attachment_label(
        self,
        conversation_id: str,
        attachment_id: str,
    ) -> str:
        for attachment in self.service.list_transfer_attachments(conversation_id):
            if attachment.id == attachment_id:
                return f"[附件] {attachment.filename}"
        return "[附件] 未知附件"

    def _transfer_chat_meta(self, conversation_id: str) -> str:
        conversation = self.service.get_transfer_conversation(conversation_id)
        status_label = self._transfer_conversation_status_label(conversation)
        meta = (
            f"{conversation.device_name} · {status_label} · "
            f"消息 {conversation.message_count} · 附件 {conversation.attachment_count}"
        )
        if conversation.note_id:
            meta = f"{meta} · 已转存为小纸条"
        return meta

    def _update_data_status(
        self,
        page: str,
        all_summaries: list[RecordSummary],
        current_count: int,
    ) -> None:
        account_count = sum(1 for item in all_summaries if item.type == RecordType.ACCOUNT)
        note_count = sum(1 for item in all_summaries if item.type == RecordType.SECURE_NOTE)
        status = (
            f"数据文件：{self.service.store.path}\n"
            f"总记录 {len(all_summaries)} / 账号 {account_count} / 小纸条 {note_count}"
        )
        self.vault_subtitle.setText(
            f"保险箱ID：{self.vault_name} / 账号{account_count} / 小纸条{note_count}"
        )
        self.settings_data_overview.setText(status)
        self.account_status.setText("")
        self.note_status.setText("")
        self.account_status.setVisible(False)
        self.note_status.setVisible(False)
    def _add_empty_record_item(self, list_widget: QListWidget, text: str) -> None:
        item = QListWidgetItem()
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setSizeHint(QSize(0, 72))
        list_widget.addItem(item)
        list_widget.setItemWidget(item, EmptyListItem(text))
    def _refresh_trash(self) -> None:
        self.trash_list.clear()
        self._apply_batch_mode("trash", self.trash_list)
        for summary in sorted_summaries(self.service.trash(), SortMode.UPDATED_DESC):
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 74))
            item.setData(Qt.ItemDataRole.UserRole, summary.id)
            self.trash_list.addItem(item)
            self.trash_list.setItemWidget(item, RecordListItem(summary, "已移入回收站"))

    def _refresh_download_history(self) -> None:
        self.download_history_list.clear()
        self._apply_batch_mode("download_history", self.download_history_list)
        history = self.service.list_download_history()
        if not history:
            self.download_history_status.setText("下载历史为空")
            self._add_empty_record_item(self.download_history_list, "当前没有下载记录")
            return
        status_lines: list[str] = []
        for record in history:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 74))
            item.setData(Qt.ItemDataRole.UserRole, record.id)
            self.download_history_list.addItem(item)
            state = "文件存在" if record.exists else "文件不存在"
            status_lines.append(f"{record.filename} · {state}")
            summary = RecordSummary(
                id=record.id,
                type=RecordType.SECURE_NOTE,
                name=record.filename,
                account=record.saved_path,
                category=state,
                favorite=False,
                created_at=record.downloaded_at,
                updated_at=record.downloaded_at,
            )
            subtitle = f"{_format_size_bytes(record.size_bytes)} · {record.saved_path}"
            self.download_history_list.setItemWidget(item, RecordListItem(summary, subtitle))
        self.download_history_status.setText("\n".join(status_lines))

    def _delete_selected_download_history(self) -> None:
        items = self._selected_items(self.download_history_list)
        if not items:
            return
        for item in items:
            self.service.delete_download_history_record(item.data(Qt.ItemDataRole.UserRole))
        self._exit_batch_mode("download_history", self.download_history_list)
        self._refresh_download_history()
        self._show_toast(f"已清除 {len(items)} 条下载记录")

    def _open_selected_download_history(self) -> None:
        item = self.download_history_list.currentItem()
        if item is None and self.download_history_list.count() == 1:
            item = self.download_history_list.item(0)
        self._open_download_history_item(item)

    def _open_download_history_item(self, item: QListWidgetItem | None) -> None:
        if item is None or item.flags() == Qt.ItemFlag.NoItemFlags:
            return
        record = self._download_history_record_from_item(item)
        if record is None:
            self.download_history_status.setText("下载记录不存在")
            return
        status = QLabel()
        self._open_local_path(record.saved_path, status)
        if status.text():
            self.download_history_status.setText(status.text())

    def _open_transfer_download_folder(self) -> None:
        self.settings.transfer_download_dir.mkdir(parents=True, exist_ok=True)
        status = QLabel()
        self._open_local_path(str(self.settings.transfer_download_dir), status)
        if status.text() and hasattr(self, "download_history_status"):
            self.download_history_status.setText(status.text())

    def _show_download_history_context_menu(
        self,
        list_widget: QListWidget,
        position,
        refresh,
        status: QLabel,
    ) -> None:
        item = list_widget.itemAt(position)
        if item is None or item.flags() == Qt.ItemFlag.NoItemFlags:
            return
        list_widget.setCurrentItem(item)
        record = self._download_history_record_from_item(item)
        if record is None:
            status.setText("下载记录不存在")
            return
        menu = QMenu(list_widget)
        open_file = menu.addAction("打开文件")
        reveal_file = menu.addAction("在资源管理器中打开")
        delete_file = menu.addAction("删除文件")
        remove_record = menu.addAction("清除记录")
        action = menu.exec(list_widget.viewport().mapToGlobal(position))
        if action == open_file:
            self._open_local_path(record.saved_path, status)
        elif action == reveal_file:
            self._reveal_local_path(record.saved_path, status)
        elif action == delete_file:
            status.setText(self._delete_download_history_files([record]))
            self._refresh_download_history()
            refresh()
        elif action == remove_record:
            self.service.delete_download_history_record(record.id)
            self._refresh_download_history()
            refresh()

    def _download_history_record_from_item(self, item: QListWidgetItem):
        record_id = item.data(Qt.ItemDataRole.UserRole)
        return next(
            (entry for entry in self.service.list_download_history() if entry.id == record_id),
            None,
        )

    def _delete_selected_download_history_files(self) -> None:
        items = self._selected_items(self.download_history_list)
        if not items:
            self._show_toast("请先选择下载记录")
            return
        records = [
            record
            for item in items
            if (record := self._download_history_record_from_item(item)) is not None
        ]
        message = self._delete_download_history_files(records)
        self._exit_batch_mode("download_history", self.download_history_list)
        self._refresh_download_history()
        self.download_history_status.setText(message)
        self._show_toast(message)

    def _delete_download_history_files(self, records) -> str:
        deleted = 0
        missing = 0
        failed = 0
        for record in records:
            path = Path(record.saved_path)
            if not path.exists():
                missing += 1
                continue
            try:
                path.unlink()
                deleted += 1
            except OSError:
                failed += 1
        message = f"已删除 {deleted} 个文件"
        details = []
        if missing:
            details.append(f"{missing} 个文件不存在")
        if failed:
            details.append(f"{failed} 个文件删除失败")
        if details:
            message = f"{message}，{', '.join(details)}"
        return message

    def _clear_download_history(self) -> None:
        self.service.clear_download_history()
        self._refresh_download_history()
        self._show_toast("已清空下载列表")

    def _toggle_batch_mode(self, key: str, list_widget: QListWidget) -> None:
        self.batch_modes[key] = not self.batch_modes.get(key, False)
        self._apply_batch_mode(key, list_widget)
        self._refresh_batch_buttons(key)

    def _exit_batch_mode(self, key: str, list_widget: QListWidget) -> None:
        self.batch_modes[key] = False
        list_widget.clearSelection()
        self._apply_batch_mode(key, list_widget)
        self._refresh_batch_buttons(key)

    def _apply_batch_mode(self, key: str, list_widget: QListWidget) -> None:
        mode = (
            QAbstractItemView.SelectionMode.MultiSelection
            if self.batch_modes.get(key, False)
            else QAbstractItemView.SelectionMode.SingleSelection
        )
        list_widget.setSelectionMode(mode)

    def _refresh_batch_buttons(self, key: str) -> None:
        enabled = self.batch_modes.get(key, False)
        mapping = {
            "accounts": (self.account_multi_button, self.account_delete_selected_button),
            "notes": (self.note_multi_button, self.note_delete_selected_button),
            "transfer": (self.transfer_multi_button, self.transfer_delete_selected_button),
            "download_history": (self.download_history_multi_button, None),
            "trash": (self.trash_multi_button, None),
        }
        toggle, delete_button = mapping[key]
        toggle.setText("取消多选" if enabled else "多选")
        if delete_button is not None:
            delete_button.setVisible(enabled)
        self._refresh_button_style(toggle)
        if delete_button is not None:
            self._refresh_button_style(delete_button)

    def _selected_items(self, list_widget: QListWidget) -> list[QListWidgetItem]:
        return [
            item
            for item in list_widget.selectedItems()
            if item is not None and item.flags() != Qt.ItemFlag.NoItemFlags
        ]

    def _delete_selected_accounts(self) -> None:
        items = self._selected_items(self.account_list)
        if not items:
            self._show_toast("请先选择账号记录")
            return
        for item in items:
            record_id = item.data(Qt.ItemDataRole.UserRole)
            self.service.delete_record(record_id)
            if self.current_account_id == record_id:
                self.current_account_id = ""
        self._exit_batch_mode("accounts", self.account_list)
        self._refresh_accounts()
        self._show_toast(f"已删除 {len(items)} 条账号记录")

    def _delete_selected_notes(self) -> None:
        items = self._selected_items(self.note_list)
        if not items:
            self._show_toast("请先选择小纸条")
            return
        for item in items:
            record_id = item.data(Qt.ItemDataRole.UserRole)
            self.service.delete_record(record_id)
            if self.current_note_id == record_id:
                self.current_note_id = ""
        self._exit_batch_mode("notes", self.note_list)
        self._refresh_notes()
        self._show_toast(f"已删除 {len(items)} 条小纸条")

    def _delete_selected_transfer_conversations(self) -> None:
        items = self._selected_items(self.transfer_list)
        if not items:
            self._show_toast("请先选择传输记录")
            return
        deleted = 0
        skipped = 0
        for item in items:
            conversation_id = item.data(Qt.ItemDataRole.UserRole)
            conversation = self.service.get_transfer_conversation(conversation_id)
            if self._transfer_conversation_is_open(conversation):
                skipped += 1
                continue
            self.service.delete_transfer_conversation(conversation_id)
            deleted += 1
            if self.current_transfer_id == conversation_id:
                self.current_transfer_id = ""
        self._exit_batch_mode("transfer", self.transfer_list)
        self._refresh_transfer_conversations()
        message = f"已删除 {deleted} 条传输记录"
        if skipped:
            message = f"{message}，{skipped} 条进行中会话已跳过"
        self._show_toast(message)

    def _delete_selected_trash_records(self) -> bool:
        items = self._selected_items(self.trash_list)
        if not items:
            return False
        reply = QMessageBox.question(
            self,
            "彻底删除",
            f"确定彻底删除选中的 {len(items)} 条记录吗？",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return True
        for item in items:
            self.service.permanently_delete_record(item.data(Qt.ItemDataRole.UserRole))
        self._exit_batch_mode("trash", self.trash_list)
        self._refresh_trash()
        self._show_toast(f"已彻底删除 {len(items)} 条记录")
        return True

    def _open_account_item(self, item: QListWidgetItem) -> None:
        if self.batch_modes.get("accounts"):
            return
        self.current_account_id = item.data(Qt.ItemDataRole.UserRole)
        self._render_account_detail(self.service.get_record(self.current_account_id))
        self._remember_module_page("accounts", self.account_detail_page)
        self.pages.setCurrentWidget(self.account_detail_page)

    def _render_account_detail(self, record: Record) -> None:
        self.account_editing = False
        self.account_edit_widgets = {}
        self.account_edit_button.setText("编辑")
        self.account_edit_button.setObjectName("SubtleButton")
        self._refresh_button_style(self.account_edit_button)
        self.account_export_button.setEnabled(True)
        self.account_save_notice.setText("保存成功")
        self.account_save_notice.setVisible(False)
        self.account_title.setText(record.name)
        self.account_meta.setText(f"{record.category} · {record.account}")
        self._clear_account_fields()
        self._add_field_card(0, 0, "账号", "account", record.account)
        self._add_field_card(0, 1, "密码", "password", record.password)
        self._add_field_card(1, 0, "分类", "category", record.category)
        self._add_field_card(1, 1, "入口说明", "entry_hint", record.entry_hint or "未填写")
        self.account_note.setPlainText(record.note or "没有备注。")

    def _open_note_item(self, item: QListWidgetItem) -> None:
        if self.batch_modes.get("notes"):
            return
        self.current_note_id = item.data(Qt.ItemDataRole.UserRole)
        self._render_note_detail(self.service.get_record(self.current_note_id))
        self._remember_module_page("notes", self.note_detail_page)
        self.pages.setCurrentWidget(self.note_detail_page)

    def _show_account_context_menu(self, position) -> None:
        item = self.account_list.itemAt(position)
        if item:
            self._show_record_context_menu("accounts", self.account_list, item, position)

    def _show_note_context_menu(self, position) -> None:
        item = self.note_list.itemAt(position)
        if item:
            self._show_record_context_menu("notes", self.note_list, item, position)

    def _show_record_context_menu(
        self,
        page: str,
        list_widget: QListWidget,
        item: QListWidgetItem,
        position,
    ) -> None:
        menu = QMenu(self)
        view_action = menu.addAction("查看")
        delete_action = menu.addAction("删除")
        action = menu.exec(list_widget.viewport().mapToGlobal(position))
        if action == view_action:
            self._handle_record_context_action(page, item, "view")
        elif action == delete_action:
            self._handle_record_context_action(page, item, "delete")

    def _handle_record_context_action(
        self,
        page: str,
        item: QListWidgetItem | None,
        action: str,
    ) -> None:
        if item is None:
            return
        record_id = item.data(Qt.ItemDataRole.UserRole)
        if action == "view":
            if page == "accounts":
                self._open_account_item(item)
            else:
                self._open_note_item(item)
            return
        if action != "delete":
            return
        reply = QMessageBox.question(
            self,
            "确认删除",
            "确认删除这条记录吗？删除后会移入回收站。",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.service.delete_record(record_id)
        if page == "accounts":
            if self.current_account_id == record_id:
                self.current_account_id = ""
                self._remember_module_page("accounts", self.accounts_page)
            self._refresh_accounts()
        else:
            if self.current_note_id == record_id:
                self.current_note_id = ""
                self._remember_module_page("notes", self.notes_page)
            self._refresh_notes()

    def _render_note_detail(self, record: Record) -> None:
        self._loading_note_detail = True
        self.note_title_input.setText(record.name)
        self.note_category.setCurrentText(record.category)
        self._apply_note_category_style(record.category)
        self.note_body.setHtml(record.note)
        self._saved_note_snapshot = self._current_note_snapshot()
        self._loading_note_detail = False
        self._set_note_dirty(False)
        self.note_save_notice.setText("已保存")
        self.note_save_notice.setVisible(False)
        self._show_note_source_info(record.note)
        self.note_attachments_button.setVisible(
            bool(self._transfer_conversation_for_note(record.id))
        )
        self._set_note_edit_mode(True)

    def _add_account(self) -> None:
        dialog = AccountDialog(self)
        if dialog.exec():
            data = dialog.data()
            if not data.name or not data.account or not data.password:
                QMessageBox.warning(self, "信息不完整", "名称、账号、密码都需要填写。")
                return
            self.service.create_account(**data.to_payload())
            self._refresh_accounts()

    def _toggle_account_edit(self) -> None:
        if not self.current_account_id:
            return
        if self.account_editing:
            self._save_inline_account()
        else:
            self._enter_account_edit_mode()

    def _enter_account_edit_mode(self) -> None:
        record = self.service.get_record(self.current_account_id)
        self.account_editing = True
        self.account_edit_widgets = {}
        self.account_edit_button.setText("保存")
        self.account_edit_button.setObjectName("PrimaryButton")
        self._refresh_button_style(self.account_edit_button)
        self.account_export_button.setEnabled(False)
        self._clear_account_fields()
        self._add_edit_field_card(0, 0, "账号", "account", record.account)
        self._add_edit_field_card(0, 1, "密码", "password", record.password)
        self._add_edit_field_card(1, 0, "分类", "category", record.category)
        self._add_edit_field_card(1, 1, "入口说明", "entry_hint", record.entry_hint)
        self.account_note.setReadOnly(False)
        self.account_note.setPlainText(record.note)

    def _save_inline_account(self) -> None:
        if not self.current_account_id:
            return
        record = self.service.get_record(self.current_account_id)
        account = self._line_value("account")
        password = self._line_value("password")
        category = self._combo_value("category")
        entry_hint = self._line_value("entry_hint")
        if not account or not password:
            QMessageBox.warning(self, "信息不完整", "账号和密码都需要填写。")
            return
        updated = self.service.update_account(
            self.current_account_id,
            name=record.name,
            account=account,
            password=password,
            category=category,
            note=self.account_note.toPlainText().strip(),
            entry_hint=entry_hint,
        )
        self.account_note.setReadOnly(True)
        self._render_account_detail(updated)
        self._refresh_accounts()
        self._show_account_save_notice()

    def _show_account_save_notice(self, text: str = "保存成功") -> None:
        self.account_save_notice.setText(text)
        self.account_save_notice.setVisible(True)
        self._show_toast(text)

    def _new_note(self) -> None:
        note = self.service.create_secure_note(
            name="未命名小纸条",
            note=f'<p style="font-size:{NOTE_BODY_FONT_SIZE_PT}pt;"></p>',
            category="收件箱",
        )
        self.current_note_id = note.id
        self._render_note_detail(note)
        self._remember_module_page("notes", self.note_detail_page)
        self.pages.setCurrentWidget(self.note_detail_page)

    def _import_note_file(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "导入小纸条文档",
            "",
            "文本和 Markdown (*.txt *.md *.markdown);;"
            "文本文件 (*.txt);;"
            "Markdown 文件 (*.md *.markdown)",
        )
        if not file_name:
            return
        path = Path(file_name)
        try:
            text = read_import_text(path)
        except OSError as exc:
            QMessageBox.warning(self, "导入失败", f"无法读取这个文件：{exc}")
            return
        imported = build_imported_note(path, text)
        note = self.service.create_secure_note(
            name=imported.title,
            note=_with_note_source(imported.html, imported.source),
            category=imported.category,
        )
        self.current_note_id = note.id
        self._render_note_detail(note)
        self._refresh_notes()
        self._remember_module_page("notes", self.note_detail_page)
        self.pages.setCurrentWidget(self.note_detail_page)
        self._show_note_save_notice("导入成功")

    def _save_current_note(self) -> bool:
        if not self.current_note_id:
            return False
        name = self.note_title_input.text().strip()
        note = self.note_body.toHtml().strip()
        category = self.note_category.currentText().strip()
        if not name:
            QMessageBox.warning(self, "信息不完整", "标题需要填写。")
            return False
        updated = self.service.update_secure_note(
            self.current_note_id,
            name=name,
            note=note,
            category=category,
        )
        self._loading_note_detail = True
        self.note_title_input.setText(updated.name)
        self.note_category.setCurrentText(updated.category)
        self._apply_note_category_style(updated.category)
        self.note_body.setHtml(updated.note)
        self._saved_note_snapshot = self._current_note_snapshot()
        self._loading_note_detail = False
        self._set_note_dirty(False)
        self._show_note_source_info(updated.note)
        self.note_attachments_button.setVisible(
            bool(self._transfer_conversation_for_note(updated.id))
        )
        self._refresh_notes()
        self._show_note_save_notice("保存成功")
        return True

    def _apply_note_category_style(self, category: str) -> None:
        self.note_category.setObjectName(f"CategoryPillCombo_{_category_color_key(category)}")
        self._refresh_button_style(self.note_category)

    def _enter_note_edit_mode(self) -> None:
        self._set_note_edit_mode(True)

    def _set_note_edit_mode(self, editing: bool) -> None:
        self.note_editing = bool(editing)
        self.note_title_input.setReadOnly(False)
        self.note_category.setEnabled(True)
        self.note_body.setReadOnly(False)
        self.note_save_button.setVisible(True)
        self.note_export_button.setEnabled(bool(self.current_note_id))
        for button in self.note_format_buttons:
            button.setEnabled(True)

    def _current_note_snapshot(self) -> tuple[str, str, str]:
        return (
            self.note_title_input.text().strip(),
            self.note_category.currentText().strip(),
            self.note_body.toHtml().strip(),
        )

    def _mark_note_dirty_from_editor(self, *args) -> None:
        if self._loading_note_detail or not self.current_note_id:
            return
        self._set_note_dirty(self._current_note_snapshot() != self._saved_note_snapshot)

    def _set_note_dirty(self, dirty: bool) -> None:
        self.note_dirty = dirty
        self.note_title_input.setPlaceholderText("标题 *" if dirty else "标题")
        self.note_save_button.setText("保存 *" if dirty else "保存")
        self.note_save_button.setObjectName("PrimaryButton" if dirty else "SubtleButton")
        self._refresh_button_style(self.note_save_button)
        self.note_save_notice.setText("未保存 *" if dirty else "已保存")
        self.note_save_notice.setVisible(dirty)
        if self.current_note_id and not dirty:
            self._show_note_source_info(self.service.get_record(self.current_note_id).note)

    def _confirm_discard_dirty_note(self) -> bool:
        if not self.current_note_id or not self.note_dirty:
            return True
        reply = QMessageBox.question(
            self,
            "未保存的小纸条",
            "当前小纸条还有未保存的改动，确定不保存就返回吗？",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return False
        self._set_note_dirty(False)
        return True

    def _show_note_save_notice(self, text: str = "保存成功") -> None:
        self.note_save_notice.setText(text)
        self.note_save_notice.setVisible(False)
        self._show_toast(text)

    def _transfer_conversation_for_note(self, note_id: str):
        for conversation in self.service.list_transfer_conversations():
            if conversation.note_id == note_id:
                return conversation
        return None

    def _show_current_note_attachments(self) -> None:
        if not self.current_note_id:
            return
        conversation = self._transfer_conversation_for_note(self.current_note_id)
        if conversation is None:
            self._show_note_save_notice("当前纸条没有会话附件")
            return
        self.current_transfer_id = conversation.id
        if not self.service.list_transfer_attachments(conversation.id):
            self._show_note_save_notice("当前会话没有附件")
            return
        self._show_transfer_attachments_dialog(conversation.id)

    def _export_current_note_as(self, suffix: str = "") -> None:
        if not self.current_note_id:
            return
        if self.note_dirty and not self._save_current_note():
            return
        suffix = suffix if suffix in {".txt", ".md", ".pdf"} else ".pdf"
        record = self.service.get_record(self.current_note_id)
        path = self._choose_note_export_path(record, suffix)
        if path is None:
            return
        try:
            self._write_note_export(record, path)
        except OSError as exc:
            QMessageBox.warning(self, "导出失败", f"无法写入这个文件：{exc}")
            return
        self._show_note_save_notice(f"已导出 {path.name}")

    def _choose_note_export_path(self, record: Record, suffix: str) -> Path | None:
        return self._choose_record_export_path(record, suffix, "导出小纸条")

    def _choose_record_export_path(
        self,
        record: Record,
        suffix: str,
        title: str,
    ) -> Path | None:
        suggested = _safe_export_filename(record.name, suffix)
        file_name, selected_filter = QFileDialog.getSaveFileName(
            self,
            title,
            suggested,
            NOTE_EXPORT_FILTERS,
            _note_export_filter_for_suffix(suffix),
        )
        if not file_name:
            return None
        path = Path(file_name)
        final_suffix = _note_export_suffix_for_choice(path.suffix, selected_filter, suffix)
        return path.with_suffix(final_suffix)

    def _write_note_export(self, record: Record, path: Path) -> None:
        self._write_record_export(record, path)

    def _write_record_export(self, record: Record, path: Path) -> None:
        suffix = path.suffix.lower()
        path.parent.mkdir(parents=True, exist_ok=True)
        html = _record_export_html(record)
        if suffix == ".pdf":
            _export_note_pdf(html, path)
            return
        if suffix == ".md":
            path.write_text(_note_html_to_markdown(html).strip() + "\n", encoding="utf-8")
            return
        path.write_text(_note_html_to_plain_text(html).strip() + "\n", encoding="utf-8")

    def _show_note_source_info(self, note: str) -> None:
        source = _note_source(note)
        self.note_source_info.setText(source)
        self.note_source_info.setVisible(bool(source))

    def _copy_current_account_field(self, field: str) -> None:
        if not self.current_account_id:
            return
        record = self.service.get_record(self.current_account_id)
        text = getattr(record, field)
        if text:
            self.clipboard.copy(text)
            self._show_account_save_notice("账号已复制" if field == "account" else "密码已复制")

    def _export_current_account_as(self, suffix: str = "") -> None:
        if not self.current_account_id:
            return
        if self.account_editing:
            self._save_inline_account()
            if self.account_editing:
                return
        suffix = suffix if suffix in {".txt", ".md", ".pdf"} else ".pdf"
        record = self.service.get_record(self.current_account_id)
        path = self._choose_record_export_path(record, suffix, "导出账号密码")
        if path is None:
            return
        try:
            self._write_record_export(record, path)
        except OSError as exc:
            QMessageBox.warning(self, "导出失败", f"无法写入这个文件：{exc}")
            return
        self._show_account_save_notice(f"已导出 {path.name}")

    def _add_field_card(self, row: int, col: int, label: str, key: str, value: str) -> None:
        card = QFrame()
        card.setObjectName("FieldCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        title = QLabel(label)
        title.setObjectName("FieldLabel")
        content = QLabel(value)
        content.setObjectName("FieldContent")
        content.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        content.setWordWrap(True)
        content.setMinimumHeight(64)
        layout.addWidget(title)
        layout.addWidget(content)
        self.account_fields_layout.addWidget(card, row, col)

    def _add_edit_field_card(
        self,
        row: int,
        col: int,
        label: str,
        key: str,
        value: str,
    ) -> None:
        card = QFrame()
        card.setObjectName("FieldCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        title = QLabel(label)
        title.setObjectName("FieldLabel")
        if key == "category":
            editor = QComboBox()
            editor.setObjectName("InlineCombo")
            editor.setEditable(True)
            editor.addItems(["邮箱", "学校", "工作", "游戏", "生活", "软件", "其他"])
            editor.setCurrentText(value)
        else:
            editor = QLineEdit(value)
            editor.setObjectName("InlineEditor")
        editor.setMinimumHeight(64)
        self.account_edit_widgets[key] = editor
        layout.addWidget(title)
        layout.addWidget(editor)
        self.account_fields_layout.addWidget(card, row, col)

    def _clear_account_fields(self) -> None:
        while self.account_fields_layout.count():
            item = self.account_fields_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _line_value(self, key: str) -> str:
        widget = self.account_edit_widgets[key]
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        return ""

    def _combo_value(self, key: str) -> str:
        widget = self.account_edit_widgets[key]
        if isinstance(widget, QComboBox):
            return widget.currentText().strip()
        return ""

    def _refresh_button_style(self, button: QPushButton) -> None:
        button.style().unpolish(button)
        button.style().polish(button)

    def _merge_note_format(self, text_format: QTextCharFormat) -> None:
        cursor = self.note_body.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        cursor.mergeCharFormat(text_format)
        self.note_body.mergeCurrentCharFormat(text_format)

    def _toggle_text_property(self, prop: str) -> None:
        text_format = QTextCharFormat()
        current = self.note_body.currentCharFormat()
        if prop == "bold":
            text_format.setFontWeight(400 if current.fontWeight() > 400 else 700)
        elif prop == "italic":
            text_format.setFontItalic(not current.fontItalic())
        elif prop == "underline":
            text_format.setFontUnderline(not current.fontUnderline())
        self._merge_note_format(text_format)

    def _set_text_size(self, size: int) -> None:
        if self.note_font_size.currentText() != str(size):
            self.note_font_size.blockSignals(True)
            self.note_font_size.setCurrentText(str(size))
            self.note_font_size.blockSignals(False)
        text_format = QTextCharFormat()
        text_format.setFontPointSize(size)
        self._merge_note_format(text_format)

    def _set_text_size_from_text(self, size_text: str) -> None:
        try:
            size = int(size_text)
        except ValueError:
            return
        self._set_text_size(size)

    def _set_text_color(self, color: str) -> None:
        text_format = QTextCharFormat()
        text_format.setForeground(QColor(color))
        self._merge_note_format(text_format)

    def _set_note_alignment(self, alignment: Qt.AlignmentFlag) -> None:
        cursor = self.note_body.textCursor()
        block_format = cursor.blockFormat()
        block_format.setAlignment(alignment)
        cursor.setBlockFormat(block_format)
        self.note_body.setTextCursor(cursor)
        self._show_note_save_notice("已调整对齐")

    def _toggle_note_list(self, style: QTextListFormat.Style) -> None:
        cursor = self.note_body.textCursor()
        block_format = cursor.blockFormat()
        list_format = QTextListFormat()
        if cursor.currentList() is not None and cursor.currentList().format().style() == style:
            block_format.setObjectIndex(-1)
            cursor.setBlockFormat(block_format)
            self.note_body.setTextCursor(cursor)
            self._show_note_save_notice("已取消列表")
            return
        list_format.setStyle(style)
        cursor.createList(list_format)
        self.note_body.setTextCursor(cursor)
        self._show_note_save_notice("已设置列表")

    def _insert_note_image_file(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "插入图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.gif *.webp)",
        )
        if not file_name:
            return
        image = QImage(file_name)
        if image.isNull():
            QMessageBox.warning(self, "插入失败", "无法读取这张图片")
            return
        self.note_body._insert_image(image)
        self._show_note_save_notice("已插入图片")

    def _handle_note_shortcut(self, action: str) -> None:
        actions = {
            "bold": lambda: self._toggle_text_property("bold"),
            "italic": lambda: self._toggle_text_property("italic"),
            "underline": lambda: self._toggle_text_property("underline"),
            "clear": self._clear_note_format,
            "align_left": lambda: self._set_note_alignment(Qt.AlignmentFlag.AlignLeft),
            "align_center": lambda: self._set_note_alignment(Qt.AlignmentFlag.AlignCenter),
            "align_right": lambda: self._set_note_alignment(Qt.AlignmentFlag.AlignRight),
            "ordered_list": lambda: self._toggle_note_list(QTextListFormat.Style.ListDecimal),
            "bullet_list": lambda: self._toggle_note_list(QTextListFormat.Style.ListDisc),
            "save": self._save_current_note,
        }
        handler = actions.get(action)
        if handler is not None:
            handler()

    def _capture_note_format(self) -> None:
        self.note_format_brush = QTextCharFormat(self.note_body.currentCharFormat())
        self._show_note_save_notice("已吸取格式")

    def _apply_note_format_brush(self) -> None:
        if self.note_format_brush is None:
            return
        self._merge_note_format(self.note_format_brush)
        self.note_format_brush = None
        self._show_note_save_notice("已应用格式")

    def _use_note_format_brush(self) -> None:
        if self.note_format_brush is None:
            self._capture_note_format()
        else:
            self._apply_note_format_brush()

    def _clear_note_format(self) -> None:
        cursor = self.note_body.textCursor()
        if cursor.hasSelection():
            cursor.setCharFormat(QTextCharFormat())
        else:
            self.note_body.selectAll()
            cursor = self.note_body.textCursor()
            cursor.setCharFormat(QTextCharFormat())
            cursor.clearSelection()
            self.note_body.setTextCursor(cursor)
        self._show_note_save_notice("已清除格式")

    def _copy_note_plain_text(self) -> None:
        text = self.note_body.toPlainText().strip()
        if text:
            self.clipboard.copy(text)
            self._show_note_save_notice("已复制全文")

    def _insert_bullet(self) -> None:
        cursor = self.note_body.textCursor()
        cursor.insertText("• ")

    def _delete_current_account(self) -> None:
        if not self.current_account_id:
            return
        reply = QMessageBox.question(self, "移入回收站", "确定把这条账号记录移入回收站吗？")
        if reply == QMessageBox.StandardButton.Yes:
            self.service.delete_record(self.current_account_id)
            self.current_account_id = ""
            self._show_accounts_list_page()

    def _delete_current_note(self) -> None:
        if not self.current_note_id:
            return
        reply = QMessageBox.question(self, "移入回收站", "确定把这条小纸条移入回收站吗？")
        if reply == QMessageBox.StandardButton.Yes:
            self.service.delete_record(self.current_note_id)
            self.current_note_id = ""
            self._show_notes_list_page()

    def _restore_selected_trash(self) -> None:
        item = self.trash_list.currentItem()
        if not item:
            return
        self.service.restore_record(item.data(Qt.ItemDataRole.UserRole))
        self._refresh_trash()

    def _delete_selected_trash_permanently(self) -> None:
        if self.batch_modes.get("trash") and self._delete_selected_trash_records():
            return
        item = self.trash_list.currentItem()
        if not item:
            return
        reply = QMessageBox.question(self, "彻底删除", "彻底删除后不能从回收站恢复，确定继续吗？")
        if reply == QMessageBox.StandardButton.Yes:
            self.service.permanently_delete_record(item.data(Qt.ItemDataRole.UserRole))
            self._refresh_trash()

    def _clear_trash(self) -> None:
        if not self.service.trash():
            return
        reply = QMessageBox.question(self, "清空回收站", "确定彻底删除回收站里的全部记录吗？")
        if reply == QMessageBox.StandardButton.Yes:
            self.service.clear_trash()
            self._refresh_trash()

    def _lock(self) -> None:
        self._auto_sync_current_vault()
        self.transfer_refresh_timer.stop()
        self.transfer_pair_timer.stop()
        self._stop_transfer_server(close_conversation=True)
        self.idle_timer.stop()
        self.service.lock()
        self.account_list.clear()
        self.note_list.clear()
        self._clear_account_fields()
        self.current_account_id = ""
        self.current_note_id = ""
        self.current_transfer_id = ""
        self.transfer_messages_signature = ""
        self._reset_module_pages()
        self._show_login_page()

    def closeEvent(self, event) -> None:
        is_spontaneous = getattr(event, "spontaneous", lambda: True)()
        if (
            not is_spontaneous
            and not self._close_action_override
            and self.profile_settings.window_close_action not in {"exit", "tray"}
        ):
            self._auto_sync_current_vault()
            self._stop_transfer_server(close_conversation=True)
            super().closeEvent(event)
            return
        action = self._resolve_window_close_action()
        if action == "tray":
            self._hide_to_tray()
            event.ignore()
            return
        if action != "exit":
            event.ignore()
            return
        self._auto_sync_current_vault()
        self._stop_transfer_server(close_conversation=True)
        super().closeEvent(event)

    def _setup_tray_icon(self) -> None:
        self._tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.windowIcon())
        self.tray_icon.setToolTip("SafeBox")
        tray_menu = QMenu(self)
        restore_action = tray_menu.addAction("显示 SafeBox")
        quit_action = tray_menu.addAction("退出")
        restore_action.triggered.connect(self._restore_from_tray)
        quit_action.triggered.connect(self._quit_from_tray)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._handle_tray_activated)
        if self._tray_available:
            self.tray_icon.show()

    def _resolve_window_close_action(self) -> str:
        if self._close_action_override:
            action = self._close_action_override
            self._close_action_override = ""
            return action
        if self.profile_settings.window_close_action in {"exit", "tray"}:
            return self.profile_settings.window_close_action
        action, remember = self._prompt_window_close_action()
        if remember and action in {"exit", "tray"}:
            self.profile_settings.window_close_action = action
            save_profile_settings(self.profile_base_dir, self.vault_name, self.profile_settings)
        return action

    def _prompt_window_close_action(self) -> tuple[str, bool]:
        dialog = WindowClosePrompt(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return "cancel", False
        return dialog.choice()

    def _hide_to_tray(self) -> None:
        if self.tray_icon is not None and self._tray_available:
            self.tray_icon.show()
        self.hide()
        self._show_toast("已隐藏到右下角，双击托盘图标可恢复")

    def _restore_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self) -> None:
        self._close_action_override = "exit"
        self.close()

    def _handle_tray_activated(self, reason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self._restore_from_tray()

    def _stop_transfer_server(self, *, close_conversation: bool = False) -> None:
        if self.transfer_server is None:
            return
        self.transfer_pair_timer.stop()
        conversation_id = self.transfer_server.conversation_id
        self.transfer_server.stop()
        if close_conversation and conversation_id and self.service.is_unlocked():
            try:
                self.service.close_transfer_conversation(conversation_id)
            except KeyError:
                pass
        self.transfer_server = None

    def eventFilter(self, watched, event) -> bool:
        if (
            event.type()
            in {
                QEvent.Type.MouseButtonPress,
                QEvent.Type.KeyPress,
                QEvent.Type.MouseMove,
            }
            and self.service.is_unlocked()
            and self.profile_settings.auto_lock_seconds > 0
        ):
            self.idle_timer.start()
        return super().eventFilter(watched, event)


class EmptyListItem(QWidget):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.setFixedHeight(70)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        label = QLabel(text)
        label.setObjectName("EmptyTitle")
        layout.addWidget(label)
        layout.addStretch()


class RecordListItem(QWidget):
    def __init__(self, summary: RecordSummary, subtitle: str = "") -> None:
        super().__init__()
        self.setFixedHeight(70)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)
        title = QLabel(summary.name)
        title.setObjectName("RecordTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        text_layout.addWidget(title)
        if subtitle:
            note_summary = QLabel(subtitle)
            note_summary.setObjectName("RecordSubtitle")
            note_summary.setWordWrap(False)
            text_layout.addWidget(note_summary)
        category = QLabel(summary.category)
        category.setObjectName(f"CategoryBadge_{_category_color_key(summary.category)}")
        category.setAlignment(Qt.AlignmentFlag.AlignCenter)
        category.setFixedSize(90, 30)
        category.setMinimumWidth(72)
        layout.addLayout(text_layout, 1)
        layout.addWidget(category, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)


class TransferMessageList(QListWidget):
    noticeRequested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._plain_text = ""
        self._message_text_by_id: dict[str, str] = {}
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._copy_message_at_position)

    def set_messages(
        self,
        messages,
        attachments_by_id: dict[str, object],
        *,
        preview_attachment,
        download_attachment,
    ) -> None:
        self.clear()
        self._message_text_by_id = {}
        blocks: list[str] = []
        for message in messages:
            sender = "电脑" if message.sender == TransferMessageSender.DESKTOP else "手机"
            content = message.text
            attachment_label = ""
            attachment = attachments_by_id.get(message.attachment_id)
            if message.kind in {TransferMessageKind.IMAGE, TransferMessageKind.FILE}:
                filename = attachment.filename if attachment is not None else "未知附件"
                attachment_label = "图片" if message.kind == TransferMessageKind.IMAGE else "文件"
                content = f"[附件] {filename}"
            blocks.append(f"{sender} {message.created_at}\n{content}")
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, message.id)
            self._message_text_by_id[message.id] = content
            message_item = TransferMessageItem(
                sender=sender,
                created_at=message.created_at,
                text=content,
                edited=False,
                outbound=message.sender == TransferMessageSender.DESKTOP,
                attachment_label=attachment_label,
                attachment_id=message.attachment_id,
                attachment=attachment,
                can_preview=message.kind == TransferMessageKind.IMAGE,
                preview_attachment=preview_attachment,
                download_attachment=download_attachment,
            )
            message_item.noticeRequested.connect(lambda text: self.noticeRequested.emit(text))
            item.setSizeHint(message_item.sizeHint() + QSize(0, 10))
            self.addItem(item)
            self.setItemWidget(item, message_item)
        self._plain_text = "\n\n".join(blocks)

    def setPlainText(self, text: str) -> None:
        self.clear()
        self._message_text_by_id = {}
        self._plain_text = text

    def toPlainText(self) -> str:
        return self._plain_text

    def selected_message_id(self) -> str:
        item = self.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else ""

    def mousePressEvent(self, event) -> None:
        item = self.itemAt(event.position().toPoint())
        if (
            item is not None
            and item == self.currentItem()
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.clearSelection()
            self.setCurrentItem(None)
            event.accept()
            return
        super().mousePressEvent(event)

    def _copy_message_at_position(self, position) -> None:
        item = self.itemAt(position)
        if item is None:
            return
        message_id = item.data(Qt.ItemDataRole.UserRole)
        text = self._message_text_by_id.get(message_id, "").strip()
        if text:
            menu = QMenu(self)
            copy_action = menu.addAction("复制整条消息")
            action = menu.exec(self.viewport().mapToGlobal(position))
            if action == copy_action:
                QApplication.clipboard().setText(text)
                self.noticeRequested.emit("已复制整条消息")


class CopyableMessageLabel(QLabel):
    noticeRequested = Signal(str)

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self._plain_text = text
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_copy_menu)

    def set_plain_text(self, text: str) -> None:
        self._plain_text = text

    def _show_copy_menu(self, position) -> None:
        selected_text = self.selectedText().strip()
        text = selected_text or self._plain_text.strip()
        if not text:
            return
        menu = QMenu(self)
        action = menu.addAction("复制选中文字" if selected_text else "复制整条消息")
        chosen = menu.exec(self.mapToGlobal(position))
        if chosen == action:
            QApplication.clipboard().setText(text)
            self.noticeRequested.emit("已复制选中文字" if selected_text else "已复制整条消息")


class TransferMessageItem(QWidget):
    noticeRequested = Signal(str)

    def __init__(
        self,
        *,
        sender: str,
        created_at: str,
        text: str,
        edited: bool,
        outbound: bool,
        attachment_label: str = "",
        attachment_id: str = "",
        attachment=None,
        can_preview: bool = False,
        preview_attachment=None,
        download_attachment=None,
    ) -> None:
        super().__init__()
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(10)
        bubble = QFrame()
        bubble.setObjectName("TransferBubbleDesktop" if outbound else "TransferBubblePhone")
        bubble.setMaximumWidth(520)
        layout = QVBoxLayout(bubble)
        layout.setContentsMargins(14, 9, 14, 10)
        layout.setSpacing(5)
        meta = QLabel(f"{sender} {created_at}")
        meta.setObjectName("TransferBubbleMeta")
        meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        meta.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        attachment_name = text.removeprefix("[附件] ").strip()
        body_text = attachment_name if attachment_label else text
        body = CopyableMessageLabel(body_text)
        body.setObjectName("TransferBubbleText")
        body.setWordWrap(True)
        body.set_plain_text(text)
        body.noticeRequested.connect(lambda text: self.noticeRequested.emit(text))
        layout.addWidget(meta)
        if attachment_label and attachment is not None and can_preview:
            source = Path(attachment.storage_path)
            pixmap = QPixmap(str(source)) if source.exists() else QPixmap()
            if not pixmap.isNull():
                image = QLabel()
                image.setObjectName("TransferImagePreview")
                image.setAlignment(Qt.AlignmentFlag.AlignCenter)
                image.setPixmap(
                    pixmap.scaled(
                        240,
                        180,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                image.setCursor(Qt.CursorShape.PointingHandCursor)
                image.mousePressEvent = (
                    lambda event, aid=attachment_id: preview_attachment
                    and preview_attachment(aid)
                )
                layout.addWidget(image)
        layout.addWidget(body)
        if attachment_label and attachment_id:
            actions = QHBoxLayout()
            actions.setContentsMargins(0, 4, 0, 0)
            actions.setSpacing(8)
            if can_preview:
                preview = QPushButton("预览")
                preview.setObjectName("SubtleButton")
                preview.setMinimumHeight(32)
                preview.setMinimumWidth(70)
                preview.clicked.connect(
                    lambda: preview_attachment and preview_attachment(attachment_id)
                )
                actions.addWidget(preview)
            download = QPushButton("下载")
            download.setObjectName("SubtleButton")
            download.setMinimumHeight(32)
            download.setMinimumWidth(70)
            download.clicked.connect(
                lambda: download_attachment and download_attachment(attachment_id)
            )
            actions.addWidget(download)
            actions.addStretch()
            layout.addLayout(actions)
        if outbound:
            outer.addStretch(1)
            outer.addWidget(bubble, 0, Qt.AlignmentFlag.AlignRight)
        else:
            outer.addWidget(bubble, 0, Qt.AlignmentFlag.AlignLeft)
            outer.addStretch(1)


def _category_color_key(category: str) -> str:
    fixed_colors = {
        "邮箱": "Blue",
        "学校": "Mint",
        "工作": "Sky",
        "游戏": "Lavender",
        "生活": "Pink",
        "软件": "Cyan",
        "收件箱": "Blue",
        "会话": "Lavender",
        "MD": "Mint",
        "TXT": "Cyan",
        "其他": "Peach",
        "进行中": "Mint",
        "待整理": "Sky",
        "已转存": "Lavender",
        "已关闭": "Peach",
        "已关闭 · 已转存": "Lavender",
    }
    if category in fixed_colors:
        return fixed_colors[category]
    palette = ["Blue", "Pink", "Cyan", "Mint", "Lavender", "Peach", "Sky"]
    index = sum(ord(ch) for ch in category) % len(palette)
    return palette[index]


def _transfer_status_label(status: str) -> str:
    labels = {
        "active": "进行中",
        "closed": "已关闭",
        "pending_review": "待整理",
        "transferred": "已转存",
    }
    return labels.get(status, status)


def _format_size_bytes(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / 1024 / 1024:.1f} MB"


def _unique_local_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 1
    while True:
        candidate = parent / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _guess_mime_type(path: Path) -> str:
    suffix = path.suffix.casefold()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".json": "application/json",
        ".zip": "application/zip",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".ppt": "application/vnd.ms-powerpoint",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }.get(suffix, "application/octet-stream")


def _record_search_text(record: Record) -> str:
    return " ".join(
        [
            record.name,
            record.account,
            record.category,
            record.note,
            record.entry_hint,
        ]
    ).casefold()


def _with_note_source(note_html: str, source: str) -> str:
    return f"<!-- safebox-source:{source} -->\n{note_html}"


def _note_document(note_html: str) -> QTextDocument:
    document = QTextDocument()
    document.setHtml(note_html)
    return document


def _note_html_to_plain_text(note_html: str) -> str:
    return _note_document(note_html).toPlainText()


def _note_html_to_markdown(note_html: str) -> str:
    document = _note_document(note_html)
    return document.toMarkdown()


def _record_export_html(record: Record) -> str:
    if record.type == RecordType.SECURE_NOTE:
        return record.note
    rows = [
        ("账号", record.account),
        ("密码", record.password),
        ("分类", record.category),
        ("入口说明", record.entry_hint),
        ("备注", record.note),
    ]
    items = "\n".join(
        f"<p><strong>{escape(label)}：</strong>{escape(value or '未填写')}</p>"
        for label, value in rows
    )
    return f"<h1>{escape(record.name)}</h1>\n{items}"


def _export_note_pdf(note_html: str, path: Path) -> None:
    document = _note_document(note_html)
    writer = QPdfWriter(str(path))
    writer.setResolution(300)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(14, 14, 14, 14), QPageLayout.Unit.Millimeter)
    document.print_(writer)


def _safe_export_filename(title: str, suffix: str) -> str:
    cleaned = "".join(
        "_" if char in '<>:"/\\|?*' or ord(char) < 32 else char
        for char in title.strip()
    ).strip(" .")
    return f"{cleaned or '未命名小纸条'}{suffix}"


def _note_export_filter_for_suffix(suffix: str) -> str:
    for label, label_suffix in NOTE_EXPORT_SUFFIX_BY_FILTER.items():
        if label_suffix == suffix:
            return label
    return "PDF 文件 (*.pdf)"


def _note_export_suffix_for_choice(
    path_suffix: str,
    selected_filter: str,
    fallback_suffix: str,
) -> str:
    suffix = path_suffix.casefold()
    if suffix in {".txt", ".md", ".pdf"}:
        return suffix
    return NOTE_EXPORT_SUFFIX_BY_FILTER.get(selected_filter, fallback_suffix)


def _note_source(note_html: str) -> str:
    marker = "<!-- safebox-source:"
    start = note_html.find(marker)
    if start < 0:
        return ""
    source_start = start + len(marker)
    source_end = note_html.find("-->", source_start)
    if source_end < 0:
        return ""
    return note_html[source_start:source_end].strip()


def _now_local() -> str:
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")

