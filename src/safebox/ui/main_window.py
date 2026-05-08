from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
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
from safebox.core.services import try_unlock
from safebox.core.settings import AppSettings
from safebox.core.transfer import TransferConversationStatus, TransferMessageSender
from safebox.core.vault_profiles import (
    VaultProfileSettings,
    app_data_dir,
    backup_file_for_vault,
    load_profile_settings,
    restore_vault_from_backup,
    save_profile_settings,
    sync_vault_to_backup,
)
from safebox.ui.branding import SAFEBOX_NAV_MARK_PATH
from safebox.ui.clipboard import SecureClipboard
from safebox.ui.dialogs import (
    DEFAULT_VAULT_ID,
    NOTE_CATEGORIES,
    AccountDialog,
    ChangePasswordDialog,
    VaultOpenDialog,
    VaultOpenMode,
)

FORMAT_BRUSH_ICON_PATH = Path(__file__).resolve().parent / "assets" / "format-brush.svg"
AUTO_LOCK_PRESETS = {
    "5分钟": 5 * 60,
    "20分钟": 20 * 60,
    "从不锁定": 0,
}
NOTE_BODY_FONT_SIZE_PT = 13
NOTE_HEADING_FONT_SIZE_PT = 18


class MainWindow(QMainWindow):
    def __init__(self, service_factory) -> None:
        super().__init__()
        self.service_factory = service_factory
        self.vault_name = DEFAULT_VAULT_ID
        self.profile_base_dir = app_data_dir()
        self.profile_settings = VaultProfileSettings()
        self.service = self.service_factory(self.vault_name)
        self.settings = AppSettings(vault_path=self.service.store.path)
        self.clipboard = SecureClipboard(self.settings.clipboard_clear_seconds)
        self.current_account_id = ""
        self.current_note_id = ""
        self.current_transfer_id = ""
        self.account_editing = False
        self.note_editing = False
        self.account_edit_widgets: dict[str, QLineEdit | QTextEdit | QComboBox] = {}
        self.note_format_buttons: list[QPushButton | QComboBox] = []
        self.note_format_brush: QTextCharFormat | None = None
        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(self.profile_settings.auto_lock_seconds * 1000)
        self.idle_timer.timeout.connect(self._lock)
        self.setWindowTitle("SafeBox")
        self._build_ui()
        self.installEventFilter(self)
        QTimer.singleShot(0, self._open_vault)

    def _build_ui(self) -> None:
        root = QWidget()
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        side_layout = QVBoxLayout(sidebar)
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
        self.accounts_page = self._build_accounts_page()
        self.account_detail_page = self._build_account_detail_page()
        self.notes_page = self._build_notes_page()
        self.note_detail_page = self._build_note_detail_page()
        self.transfer_page = self._build_transfer_page()
        self.transfer_detail_page = self._build_transfer_detail_page()
        self.transfer_chat_page = self._build_transfer_chat_page()
        self.trash_page = self._build_trash_page()
        self.settings_page = self._build_settings_page()
        self.download_history_page = self._build_download_history_page()
        for page in (
            self.accounts_page,
            self.account_detail_page,
            self.notes_page,
            self.note_detail_page,
            self.transfer_page,
            self.transfer_detail_page,
            self.transfer_chat_page,
            self.trash_page,
            self.settings_page,
            self.download_history_page,
        ):
            self.pages.addWidget(page)
        self._reset_module_pages()

        shell.addWidget(sidebar)
        shell.addWidget(self.pages, 1)
        self.setCentralWidget(root)

        self.accounts_nav.clicked.connect(self._show_accounts_page)
        self.notes_nav.clicked.connect(self._show_notes_page)
        self.transfer_nav.clicked.connect(self._show_transfer_page)
        self.trash_nav.clicked.connect(self._show_trash_page)
        self.settings_nav.clicked.connect(self._show_settings_page)
        lock.clicked.connect(self._lock)

    def _build_accounts_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        header = QHBoxLayout()
        title = QLabel("账号密码")
        title.setObjectName("PageTitle")
        add = QPushButton("+ 新建账号")
        add.setObjectName("PrimaryButton")
        self.account_status = QLabel("")
        self.account_status.setObjectName("DataStatus")
        self.account_status.setWordWrap(True)
        self.account_status.setVisible(False)
        self.account_search = QLineEdit()
        self.account_search.setPlaceholderText("搜索名称、账号、分类、备注")
        account_tools = QHBoxLayout()
        self.account_sort = QComboBox()
        self.account_sort.setObjectName("SortCombo")
        self._populate_sort_combo(self.account_sort)
        account_tools.addStretch()
        account_tools.addWidget(QLabel("排序"))
        account_tools.addWidget(self.account_sort)
        self.account_list = QListWidget()
        self.account_list.setObjectName("RecordList")
        self.account_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.account_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(add)
        layout.addLayout(header)
        layout.addWidget(self.account_status)
        layout.addLayout(account_tools)
        layout.addWidget(self.account_search)
        layout.addWidget(self.account_list, 1)

        add.clicked.connect(self._add_account)
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
        delete = QPushButton("删除")
        delete.setObjectName("DangerButton")
        top.addWidget(back)
        top.addStretch()
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
        delete.clicked.connect(self._delete_current_account)
        copy_account.clicked.connect(lambda: self._copy_current_account_field("account"))
        copy_password.clicked.connect(lambda: self._copy_current_account_field("password"))
        return page

    def _build_notes_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        header = QHBoxLayout()
        title = QLabel("小纸条")
        title.setObjectName("PageTitle")
        add = QPushButton("+ 新建小纸条")
        add.setObjectName("PrimaryButton")
        import_file = QPushButton("导入文档")
        import_file.setObjectName("SubtleButton")
        import_file.setToolTip("仅支持 .txt、.md、.markdown 格式")
        self.note_status = QLabel("")
        self.note_status.setObjectName("DataStatus")
        self.note_status.setWordWrap(True)
        self.note_status.setVisible(False)
        self.note_search = QLineEdit()
        self.note_search.setPlaceholderText("搜索标题、分类、内容")
        note_tools = QHBoxLayout()
        self.note_sort = QComboBox()
        self.note_sort.setObjectName("SortCombo")
        self._populate_sort_combo(self.note_sort)
        note_tools.addStretch()
        note_tools.addWidget(QLabel("排序"))
        note_tools.addWidget(self.note_sort)
        self.note_list = QListWidget()
        self.note_list.setObjectName("RecordList")
        self.note_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.note_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(import_file)
        header.addWidget(add)
        layout.addLayout(header)
        layout.addWidget(self.note_status)
        layout.addLayout(note_tools)
        layout.addWidget(self.note_search)
        layout.addWidget(self.note_list, 1)

        add.clicked.connect(self._new_note)
        import_file.clicked.connect(self._import_note_file)
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
        self.connect_phone_button.setToolTip("后续阶段将支持手机扫码连接")
        self.transfer_status = QLabel("")
        self.transfer_status.setObjectName("DataStatus")
        self.transfer_status.setWordWrap(True)
        self.transfer_status.setVisible(False)
        self.transfer_search = QLineEdit()
        self.transfer_search.setPlaceholderText("搜索传输记录、设备、状态")
        self.transfer_device_notice = QLabel("当前可连接设备：后续阶段支持扫码配对和信任设备")
        self.transfer_device_notice.setObjectName("DataStatus")
        self.transfer_list = QListWidget()
        self.transfer_list.setObjectName("RecordList")
        self.transfer_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.connect_phone_button)
        layout.addLayout(header)
        layout.addWidget(self.transfer_status)
        layout.addWidget(self.transfer_device_notice)
        layout.addWidget(self.transfer_search)
        layout.addWidget(self.transfer_list, 1)

        self.transfer_search.textChanged.connect(self._refresh_transfer_conversations)
        self.transfer_list.itemClicked.connect(self._open_transfer_item)
        self.connect_phone_button.clicked.connect(self._show_connect_phone_placeholder)
        return page

    def _build_transfer_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        top = QHBoxLayout()
        back = QPushButton("返回列表")
        back.setObjectName("SubtleButton")
        self.transfer_detail_attachments_button = QPushButton("查看附件")
        self.transfer_detail_attachments_button.setObjectName("SubtleButton")
        self.transfer_detail_title = QLabel("传输记录")
        self.transfer_detail_title.setObjectName("HeroTitle")
        self.transfer_detail_meta = QLabel("")
        self.transfer_detail_meta.setObjectName("HeroMeta")
        self.transfer_detail_notice = QLabel("只读查看：后续阶段将显示完整聊天内容和附件列表")
        self.transfer_detail_notice.setObjectName("DataStatus")
        self.transfer_detail_notice.setWordWrap(True)
        self.transfer_detail_body = QTextEdit()
        self.transfer_detail_body.setObjectName("DetailNote")
        self.transfer_detail_body.setReadOnly(True)
        top.addWidget(back)
        top.addStretch()
        top.addWidget(self.transfer_detail_attachments_button)
        hero = QFrame()
        hero.setObjectName("DetailHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 16, 20, 16)
        hero_layout.addWidget(self.transfer_detail_title)
        hero_layout.addWidget(self.transfer_detail_meta)
        layout.addLayout(top)
        layout.addWidget(hero)
        layout.addWidget(self.transfer_detail_notice)
        layout.addWidget(self.transfer_detail_body, 1)

        back.clicked.connect(self._show_transfer_list_page)
        self.transfer_detail_attachments_button.clicked.connect(
            self._show_current_transfer_attachments
        )
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
        download_attachments_action = self.transfer_organize_menu.addAction("下载全部附件")
        close_chat_action = self.transfer_organize_menu.addAction("关闭此次对话")
        self.transfer_organize_button.setMenu(self.transfer_organize_menu)
        self.transfer_close_button = QPushButton("关闭此次对话")
        self.transfer_close_button.setObjectName("SubtleButton")
        self.transfer_close_button.setVisible(False)
        self.transfer_chat_title = QLabel("手机对话")
        self.transfer_chat_title.setObjectName("HeroTitle")
        self.transfer_chat_meta = QLabel("")
        self.transfer_chat_meta.setObjectName("HeroMeta")
        self.transfer_messages_view = QTextEdit()
        self.transfer_messages_view.setObjectName("DetailNote")
        self.transfer_messages_view.setReadOnly(True)
        self.transfer_message_input = QTextEdit()
        self.transfer_message_input.setObjectName("TransferMessageInput")
        self.transfer_message_input.setPlaceholderText("输入要发送给手机的文字")
        self.transfer_message_input.setFixedHeight(92)
        self.transfer_send_button = QPushButton("发送")
        self.transfer_send_button.setObjectName("PrimaryButton")
        hero = QFrame()
        hero.setObjectName("DetailHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 16, 20, 16)
        hero_layout.addWidget(self.transfer_chat_title)
        hero_layout.addWidget(self.transfer_chat_meta)
        input_row = QHBoxLayout()
        input_row.addWidget(self.transfer_message_input, 1)
        input_row.addWidget(self.transfer_send_button)
        top.addWidget(back)
        top.addStretch()
        top.addWidget(self.transfer_organize_button)
        top.addWidget(self.transfer_close_button)
        layout.addLayout(top)
        layout.addWidget(hero)
        layout.addWidget(self.transfer_messages_view, 1)
        layout.addLayout(input_row)

        back.clicked.connect(self._show_transfer_list_page)
        export_note_action.triggered.connect(self._export_current_transfer_to_note)
        show_attachments_action.triggered.connect(self._show_current_transfer_attachments)
        preview_image_action.triggered.connect(self._preview_first_transfer_image)
        download_attachments_action.triggered.connect(self._download_current_transfer_attachments)
        close_chat_action.triggered.connect(self._close_current_transfer_chat)
        self.transfer_close_button.clicked.connect(self._close_current_transfer_chat)
        self.transfer_send_button.clicked.connect(self._send_current_transfer_text)
        return page

    def _build_note_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        top = QHBoxLayout()
        back = QPushButton("返回")
        back.setObjectName("SubtleButton")
        self.note_edit_button = QPushButton("编辑")
        self.note_edit_button.setObjectName("SubtleButton")
        self.note_save_button = QPushButton("保存")
        self.note_save_button.setObjectName("PrimaryButton")
        delete = QPushButton("删除")
        delete.setObjectName("DangerButton")
        top.addWidget(back)
        top.addStretch()
        top.addWidget(self.note_edit_button)
        top.addWidget(self.note_save_button)
        top.addWidget(delete)
        self.note_title_input = QLineEdit()
        self.note_title_input.setPlaceholderText("标题")
        self.note_category = QComboBox()
        self.note_category.setEditable(True)
        self.note_category.addItems(NOTE_CATEGORIES)
        self.note_source_info = QLabel("")
        self.note_source_info.setObjectName("SourceNotice")
        self.note_source_info.setVisible(False)
        self.note_save_notice = QLabel("保存成功")
        self.note_save_notice.setObjectName("SuccessNotice")
        self.note_save_notice.setVisible(False)
        toolbar = QHBoxLayout()
        bold = QPushButton("B")
        bold.setObjectName("FormatButton")
        italic = QPushButton("I")
        italic.setObjectName("FormatButton")
        underline = QPushButton("U")
        underline.setObjectName("FormatButton")
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
            bold,
            italic,
            underline,
            bullet,
            self.note_format_brush_button,
            heading,
            body,
            clear_format,
            copy_all,
        ):
            toolbar.addWidget(button)
        toolbar.addWidget(self.note_font_size)
        toolbar.addSpacing(8)
        for button in (color_black, color_blue, color_pink, color_green, color_orange):
            toolbar.addWidget(button)
        toolbar.addStretch()
        self.note_body = QTextEdit()
        self.note_body.setObjectName("NoteBody")
        self.note_body.setPlaceholderText("在这里写小纸条内容")
        self.note_format_buttons = [
            bold,
            italic,
            underline,
            bullet,
            self.note_format_brush_button,
            heading,
            body,
            clear_format,
            self.note_font_size,
            color_black,
            color_blue,
            color_pink,
            color_green,
            color_orange,
        ]
        layout.addLayout(top)
        layout.addWidget(self.note_title_input)
        layout.addWidget(self.note_category)
        layout.addWidget(self.note_source_info)
        layout.addWidget(self.note_save_notice)
        layout.addLayout(toolbar)
        layout.addWidget(self.note_body, 1)

        back.clicked.connect(self._show_notes_list_page)
        self.note_edit_button.clicked.connect(self._enter_note_edit_mode)
        self.note_save_button.clicked.connect(self._save_current_note)
        delete.clicked.connect(self._delete_current_note)
        bold.clicked.connect(lambda: self._toggle_text_property("bold"))
        italic.clicked.connect(lambda: self._toggle_text_property("italic"))
        underline.clicked.connect(lambda: self._toggle_text_property("underline"))
        bullet.clicked.connect(self._insert_bullet)
        heading.clicked.connect(lambda: self._set_text_size(NOTE_HEADING_FONT_SIZE_PT))
        body.clicked.connect(lambda: self._set_text_size(NOTE_BODY_FONT_SIZE_PT))
        self.note_format_brush_button.clicked.connect(self._use_note_format_brush)
        clear_format.clicked.connect(self._clear_note_format)
        copy_all.clicked.connect(self._copy_note_plain_text)
        self.note_font_size.currentTextChanged.connect(self._set_text_size_from_text)
        color_black.clicked.connect(lambda: self._set_text_color("#111827"))
        color_blue.clicked.connect(lambda: self._set_text_color("#2563eb"))
        color_pink.clicked.connect(lambda: self._set_text_color("#db2777"))
        color_green.clicked.connect(lambda: self._set_text_color("#059669"))
        color_orange.clicked.connect(lambda: self._set_text_color("#ea580c"))
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
        header.addWidget(clear)
        layout.addLayout(header)
        layout.addWidget(self.trash_list, 1)
        layout.addLayout(action_row)

        restore.clicked.connect(self._restore_selected_trash)
        remove.clicked.connect(self._delete_selected_trash_permanently)
        clear.clicked.connect(self._clear_trash)
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
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
        sync_now.setObjectName("PrimaryButton")
        restore_backup = QPushButton("从备份恢复")
        restore_backup.setObjectName("SubtleButton")
        show_download_history = QPushButton("查看下载历史")
        show_download_history.setObjectName("SubtleButton")
        self.auto_sync_check = QCheckBox("关闭软件时自动同步当前保险箱")
        self.auto_sync_check.setChecked(True)
        self.auto_lock_combo = QComboBox()
        self.auto_lock_combo.addItems(("5分钟", "20分钟", "自定义", "从不锁定"))
        self.auto_lock_combo.setObjectName("SortCombo")
        self.custom_auto_lock_minutes = QSpinBox()
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
        transfer_actions.addWidget(show_download_history)
        transfer_actions.addStretch()
        transfer_card.layout().addLayout(transfer_actions)
        layout.addWidget(transfer_card)
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
        sync_now.clicked.connect(self._sync_current_vault)
        restore_backup.clicked.connect(self._restore_current_vault_from_backup)
        show_download_history.clicked.connect(self._show_download_history_page)
        self.auto_sync_check.toggled.connect(self._set_auto_sync_on_close)
        self.auto_lock_combo.currentTextChanged.connect(self._set_auto_lock_mode)
        self.custom_auto_lock_minutes.valueChanged.connect(self._set_custom_auto_lock_minutes)
        change_password.clicked.connect(self._change_master_password)
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
        clear = QPushButton("清空下载列表")
        clear.setObjectName("DangerButton")
        self.download_history_status = QLabel("下载历史为空")
        self.download_history_status.setObjectName("DataStatus")
        self.download_history_status.setWordWrap(True)
        self.download_history_list = QListWidget()
        self.download_history_list.setObjectName("RecordList")
        self.download_history_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        action_row = QHBoxLayout()
        delete_record = QPushButton("清除选中记录")
        delete_record.setObjectName("SubtleButton")
        action_row.addStretch()
        action_row.addWidget(delete_record)
        header.addWidget(back)
        header.addStretch()
        header.addWidget(clear)
        layout.addLayout(header)
        layout.addWidget(title)
        layout.addWidget(self.download_history_status)
        layout.addWidget(self.download_history_list, 1)
        layout.addLayout(action_row)

        back.clicked.connect(self._show_settings_page)
        clear.clicked.connect(self._clear_download_history)
        delete_record.clicked.connect(self._delete_selected_download_history)
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

    def _open_vault(self) -> None:
        dialog = VaultOpenDialog(self)
        if not dialog.exec():
            self.close()
            return
        vault_name, password, confirm_password, mode = dialog.values()
        self.vault_name = vault_name
        self.service = self.service_factory(vault_name)
        self.settings = AppSettings(vault_path=self.service.store.path)
        self.profile_settings = load_profile_settings(self.profile_base_dir, vault_name)
        self._apply_auto_lock_settings()
        if not password:
            QMessageBox.warning(self, "信息不完整", "保险箱密码需要填写。")
            QTimer.singleShot(0, self._open_vault)
            return
        if mode == VaultOpenMode.REGISTER.value:
            if self.service.vault_exists():
                QMessageBox.warning(self, "保险箱已存在", "这个保险箱ID已经注册，请直接打开。")
                QTimer.singleShot(0, self._open_vault)
                return
            if password != confirm_password:
                QMessageBox.warning(self, "两次密码不一致", "请重新确认保险箱密码。")
                QTimer.singleShot(0, self._open_vault)
                return
            self.service.initialize(password)
        elif self.service.vault_exists():
            result = try_unlock(self.service, password)
            if not result.ok:
                QMessageBox.warning(self, "无法打开保险箱", result.message)
                QTimer.singleShot(0, self._open_vault)
                return
        else:
            QMessageBox.warning(self, "保险箱不存在", "这个保险箱ID还没有注册，请先注册保险箱。")
            QTimer.singleShot(0, self._open_vault)
            return
        self._apply_auto_lock_settings()
        self.vault_subtitle.setText(f"保险箱ID：{self.vault_name}")
        self._refresh_settings_view()
        self._reset_module_pages()
        self._show_accounts_list_page()

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

    def _set_nav(self, active: str) -> None:
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
        self._refresh_accounts()

    def _show_accounts_list_page(self) -> None:
        self._remember_module_page("accounts", self.accounts_page)
        self._set_nav("accounts")
        self.pages.setCurrentWidget(self.accounts_page)
        self._refresh_accounts()

    def _show_notes_page(self) -> None:
        self._show_module_page("notes", self.notes_page)
        self._refresh_notes()

    def _show_notes_list_page(self) -> None:
        self._remember_module_page("notes", self.notes_page)
        self._set_nav("notes")
        self.pages.setCurrentWidget(self.notes_page)
        self._refresh_notes()

    def _show_transfer_page(self) -> None:
        self._show_module_page("transfer", self.transfer_page)
        self._refresh_transfer_conversations()

    def _show_transfer_list_page(self) -> None:
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
        self._sync_auto_lock_controls()

    def _choose_backup_dir(self) -> None:
        start_dir = self.profile_settings.backup_dir or "E:\\BaiduSyncdisk"
        directory = QFileDialog.getExistingDirectory(self, "选择备份位置", start_dir)
        if not directory:
            return
        self.profile_settings.backup_dir = directory
        save_profile_settings(self.profile_base_dir, self.vault_name, self.profile_settings)
        self._refresh_settings_view()

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
        self.account_list.clear()
        all_summaries = self.service.search("")
        summaries = [
            summary for summary in self.service.search(query) if summary.type == RecordType.ACCOUNT
        ]
        sorted_accounts = sorted_summaries(summaries, self._selected_sort_mode(self.account_sort))
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

    def _refresh_notes(self) -> None:
        query = self.note_search.text().strip()
        self.note_list.clear()
        all_summaries = self.service.search("")
        summaries = [
            summary
            for summary in self.service.search(query)
            if summary.type == RecordType.SECURE_NOTE
        ]
        sorted_notes = sorted_summaries(summaries, self._selected_sort_mode(self.note_sort))
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
            record = self.service.get_record(summary.id)
            self.note_list.setItemWidget(
                item,
                RecordListItem(summary, note_plain_summary(record.note)),
            )

    def _refresh_transfer_conversations(self) -> None:
        query = self.transfer_search.text().strip()
        self.transfer_list.clear()
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
                category=_transfer_status_label(conversation.status.value),
                favorite=False,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
            )
            subtitle = (
                f"{conversation.device_name} · "
                f"消息 {conversation.message_count} · 附件 {conversation.attachment_count}"
            )
            self.transfer_list.setItemWidget(item, RecordListItem(summary, subtitle))

    def _open_transfer_item(self, item: QListWidgetItem) -> None:
        self.current_transfer_id = item.data(Qt.ItemDataRole.UserRole)
        conversation = self.service.get_transfer_conversation(self.current_transfer_id)
        if conversation.status == TransferConversationStatus.ACTIVE:
            self._show_transfer_chat(conversation.id)
            return
        self.transfer_detail_title.setText(conversation.title)
        self.transfer_detail_meta.setText(
            f"{conversation.device_name} · {_transfer_status_label(conversation.status.value)}"
        )
        self.transfer_detail_body.setPlainText(self._format_transfer_messages(conversation.id))
        self._remember_module_page("transfer", self.transfer_detail_page)
        self.pages.setCurrentWidget(self.transfer_detail_page)

    def _show_connect_phone_placeholder(self) -> None:
        conversation = self.service.create_transfer_conversation(
            title="手机对话",
            device_name="手机浏览器",
        )
        self._show_transfer_chat(conversation.id)

    def _show_transfer_chat(self, conversation_id: str) -> None:
        self.current_transfer_id = conversation_id
        conversation = self.service.get_transfer_conversation(conversation_id)
        self.transfer_chat_title.setText(conversation.title)
        self.transfer_chat_meta.setText(self._transfer_chat_meta(conversation.id))
        self.transfer_messages_view.setPlainText(self._format_transfer_messages(conversation_id))
        self._remember_module_page("transfer", self.transfer_chat_page)
        self._set_nav("transfer")
        self.pages.setCurrentWidget(self.transfer_chat_page)

    def _send_current_transfer_text(self) -> None:
        text = self.transfer_message_input.toPlainText()
        self.service.add_transfer_text_message(
            self.current_transfer_id,
            sender=TransferMessageSender.DESKTOP,
            text=text,
        )
        self.transfer_message_input.clear()
        self._show_transfer_chat(self.current_transfer_id)

    def _close_current_transfer_chat(self) -> None:
        if not self.current_transfer_id:
            return
        self.service.close_transfer_conversation(self.current_transfer_id)
        self._show_transfer_list_page()

    def _export_current_transfer_to_note(self) -> None:
        if not self.current_transfer_id:
            return
        self.service.export_transfer_conversation_to_note(self.current_transfer_id)
        self.transfer_chat_meta.setText(self._transfer_chat_meta(self.current_transfer_id))
        self._refresh_notes()

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

    def _show_current_transfer_attachments(self) -> None:
        if not self.current_transfer_id:
            return
        summary = self._format_transfer_attachments(self.current_transfer_id)
        if self.pages.currentWidget() == self.transfer_chat_page:
            self.transfer_chat_meta.setText(
                f"{self._transfer_chat_meta(self.current_transfer_id)} · {summary}"
            )
        else:
            self.transfer_detail_notice.setText(summary)

    def _download_current_transfer_attachments(self) -> None:
        if not self.current_transfer_id:
            return
        attachments = self.service.list_transfer_attachments(self.current_transfer_id)
        downloaded = 0
        for attachment in attachments:
            self.service.download_transfer_attachment(
                conversation_id=self.current_transfer_id,
                attachment_id=attachment.id,
                download_dir=self.settings.transfer_download_dir,
            )
            downloaded += 1
        message = f"已下载 {downloaded} 个附件"
        if self.pages.currentWidget() == self.transfer_chat_page:
            self.transfer_chat_meta.setText(
                f"{self._transfer_chat_meta(self.current_transfer_id)} · {message}"
            )
        else:
            self.transfer_detail_notice.setText(message)

    def _preview_first_transfer_image(self) -> None:
        if not self.current_transfer_id:
            return
        attachment = self._first_transfer_image_attachment(self.current_transfer_id)
        if attachment is None:
            self._set_transfer_attachment_status("当前会话没有图片附件")
            return
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

    def _first_transfer_image_attachment(self, conversation_id: str):
        for attachment in self.service.list_transfer_attachments(conversation_id):
            if attachment.mime_type.startswith("image/"):
                return attachment
            suffix = Path(attachment.filename).suffix.casefold()
            if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                return attachment
        return None

    def _set_transfer_attachment_status(self, message: str) -> None:
        if self.pages.currentWidget() == self.transfer_chat_page:
            self.transfer_chat_meta.setText(
                f"{self._transfer_chat_meta(self.current_transfer_id)} · {message}"
            )
        else:
            self.transfer_detail_notice.setText(message)

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
        meta = f"{conversation.device_name} · {_transfer_status_label(conversation.status.value)}"
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
        for summary in sorted_summaries(self.service.trash(), SortMode.UPDATED_DESC):
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 74))
            item.setData(Qt.ItemDataRole.UserRole, summary.id)
            self.trash_list.addItem(item)
            self.trash_list.setItemWidget(item, RecordListItem(summary, "已移入回收站"))

    def _refresh_download_history(self) -> None:
        self.download_history_list.clear()
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
        item = self.download_history_list.currentItem()
        if item is None and self.download_history_list.count() == 1:
            item = self.download_history_list.item(0)
        if item is None or item.flags() == Qt.ItemFlag.NoItemFlags:
            return
        self.service.delete_download_history_record(item.data(Qt.ItemDataRole.UserRole))
        self._refresh_download_history()

    def _clear_download_history(self) -> None:
        self.service.clear_download_history()
        self._refresh_download_history()

    def _open_account_item(self, item: QListWidgetItem) -> None:
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
        self.account_title.setText(record.name)
        self.account_meta.setText(f"{record.category} · {record.account}")
        self._clear_account_fields()
        self._add_field_card(0, 0, "账号", "account", record.account)
        self._add_field_card(0, 1, "密码", "password", record.password)
        self._add_field_card(1, 0, "分类", "category", record.category)
        self._add_field_card(1, 1, "入口说明", "entry_hint", record.entry_hint or "未填写")
        self.account_note.setPlainText(record.note or "没有备注。")

    def _open_note_item(self, item: QListWidgetItem) -> None:
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
        self.note_title_input.setText(record.name)
        self.note_category.setCurrentText(record.category)
        self.note_body.setHtml(record.note)
        self._show_note_source_info(record.note)
        self._set_note_edit_mode(False)

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
        QTimer.singleShot(2000, lambda: self.account_save_notice.setVisible(False))

    def _new_note(self) -> None:
        note = self.service.create_secure_note(
            name="未命名小纸条",
            note=f'<p style="font-size:{NOTE_BODY_FONT_SIZE_PT}pt;"></p>',
            category="收件箱",
        )
        self.current_note_id = note.id
        self._render_note_detail(note)
        self._enter_note_edit_mode()
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

    def _save_current_note(self) -> None:
        if not self.current_note_id:
            return
        name = self.note_title_input.text().strip()
        note = self.note_body.toHtml().strip()
        category = self.note_category.currentText().strip()
        if not name:
            QMessageBox.warning(self, "信息不完整", "标题需要填写。")
            return
        updated = self.service.update_secure_note(
            self.current_note_id,
            name=name,
            note=note,
            category=category,
        )
        self._render_note_detail(updated)
        self._refresh_notes()
        self._show_note_save_notice("保存成功")

    def _enter_note_edit_mode(self) -> None:
        self._set_note_edit_mode(True)

    def _set_note_edit_mode(self, editing: bool) -> None:
        self.note_editing = editing
        if not editing:
            self.note_format_brush = None
        self.note_title_input.setReadOnly(not editing)
        self.note_category.setEnabled(editing)
        self.note_body.setReadOnly(not editing)
        self.note_save_button.setVisible(editing)
        self.note_edit_button.setVisible(not editing)
        for button in self.note_format_buttons:
            button.setEnabled(editing)

    def _show_note_save_notice(self, text: str = "保存成功") -> None:
        self.note_save_notice.setText(text)
        self.note_save_notice.setVisible(True)
        QTimer.singleShot(2000, lambda: self.note_save_notice.setVisible(False))

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
        self.idle_timer.stop()
        self.service.lock()
        self.account_list.clear()
        self.note_list.clear()
        self._clear_account_fields()
        self.current_account_id = ""
        self.current_note_id = ""
        self.current_transfer_id = ""
        self._reset_module_pages()
        self._open_vault()

    def closeEvent(self, event) -> None:
        self._auto_sync_current_vault()
        super().closeEvent(event)

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


def _category_color_key(category: str) -> str:
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


def _with_note_source(note_html: str, source: str) -> str:
    return f"<!-- safebox-source:{source} -->\n{note_html}"


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

