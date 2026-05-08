from __future__ import annotations

from pathlib import Path

CHEVRON_DOWN_ICON = (Path(__file__).resolve().parent / "assets" / "chevron-down.svg").as_posix()


LIGHT_FLUENT_QSS = """
QWidget {
    font-family: "Segoe UI", "Microsoft YaHei";
    color: #172033;
    background: #f3f6fb;
}
QMainWindow {
    background: #f3f6fb;
}
QDialog {
    background: #f8fbff;
}
QToolTip {
    color: #334155;
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 13px;
}
QFrame#Sidebar {
    background: #ffffff;
    border-right: 1px solid #d6e0ed;
}
QFrame#ManagementNavGroup {
    background: transparent;
    border-top: 1px solid #edf2f7;
    padding-top: 12px;
}
QFrame#HeaderBrand {
    background: transparent;
}
QLabel#AppTitle {
    font-size: 18px;
    font-weight: 700;
}
QLabel#PageTitle {
    font-size: 28px;
    font-weight: 700;
    color: #0f172a;
}
QLabel#HeroTitle {
    font-size: 30px;
    font-weight: 750;
    color: #0f172a;
    background: transparent;
}
QLabel#HeroMeta {
    font-size: 15px;
    color: #1d4ed8;
    background: transparent;
}
QLabel#MutedText {
    color: #64748b;
    background: transparent;
}
QLabel#SuccessNotice {
    color: #047857;
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    border-radius: 12px;
    padding: 9px 14px;
    font-size: 14px;
    font-weight: 700;
}
QLabel#ToastNotice {
    color: #065f46;
    background: #ecfdf5;
    border: 1px solid #86efac;
    border-radius: 16px;
    padding: 10px 18px;
    font-size: 15px;
    font-weight: 750;
}
QLabel#TransferConnectStatus {
    color: #475569;
    background: #ffffff;
    border: 1px solid #dbe5f3;
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 14px;
    font-weight: 650;
}
QLabel#DataStatus {
    color: #475569;
    background: #ffffff;
    border: 1px solid #dbe5f3;
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 13px;
}
QLabel#EmptyTitle {
    color: #64748b;
    background: transparent;
    font-size: 16px;
    font-weight: 700;
}
QLabel#SectionLabel {
    color: #334155;
    font-size: 15px;
    font-weight: 700;
    background: transparent;
}
QLabel#RecordTitle {
    font-size: 18px;
    font-weight: 700;
    color: #0f172a;
    background: transparent;
}
QLabel#RecordSubtitle {
    font-size: 13px;
    color: #64748b;
    background: transparent;
}
QLabel#SourceNotice {
    color: #475569;
    background: #f8fbff;
    border: 1px solid #dbe5f3;
    border-radius: 12px;
    padding: 8px 12px;
    font-size: 13px;
    font-weight: 650;
}
QFrame#SettingsCard {
    background: #ffffff;
    border: 1px solid #dbe5f3;
    border-radius: 16px;
}
QFrame#SettingsCard:hover {
    border: 1px solid #bfdbfe;
    background: #fbfdff;
}
QLabel#SettingsCardTitle {
    color: #0f172a;
    background: transparent;
    font-size: 18px;
    font-weight: 750;
}
QLabel#SettingsCardHint {
    color: #64748b;
    background: transparent;
    font-size: 13px;
}
QFrame#SettingsRow {
    background: #f8fbff;
    border: 1px solid #edf2f7;
    border-radius: 12px;
}
QFrame#TransferConnectInfoRow {
    background: #f8fbff;
    border: 1px solid #edf2f7;
    border-radius: 12px;
    min-height: 92px;
}
QFrame#AttachmentCard {
    background: #ffffff;
    border: 1px solid #dbe5f3;
    border-radius: 14px;
}
QFrame#AttachmentCard:hover {
    border-color: #93c5fd;
    background: #fbfdff;
}
QLabel#AttachmentThumb {
    min-width: 140px;
    max-width: 140px;
    min-height: 92px;
    border-radius: 10px;
    background: #f1f5f9;
    color: #64748b;
    font-weight: 700;
}
QLabel#AttachmentFileIcon {
    min-width: 92px;
    max-width: 92px;
    min-height: 72px;
    border-radius: 10px;
    background: #eef2ff;
    color: #3730a3;
    font-weight: 750;
}
QLabel#AttachmentInfo {
    color: #0f172a;
    background: transparent;
    font-size: 14px;
    font-weight: 650;
}
QScrollArea#AttachmentScroll {
    border: 0;
    background: transparent;
}
QWidget#AttachmentScrollContent {
    background: transparent;
}
QScrollArea#PageScroll {
    border: 0;
    background: transparent;
}
QScrollArea#PageScroll > QWidget {
    background: transparent;
}
QLabel#SettingsLabel {
    color: #475569;
    background: transparent;
    font-size: 13px;
    font-weight: 700;
    min-width: 80px;
}
QLabel#TransferConnectInfoLabel {
    color: #475569;
    background: transparent;
    font-size: 14px;
    font-weight: 750;
    min-width: 104px;
}
QLabel#SettingsValue {
    color: #172033;
    background: transparent;
    font-size: 14px;
    font-weight: 600;
}
QFrame#DetailHero {
    background: #eaf2ff;
    border: 1px solid #bfdbfe;
    border-radius: 18px;
}
QFrame#FieldPanel {
    background: transparent;
}
QFrame#FieldCard {
    background: #ffffff;
    border: 1px solid #dbe5f3;
    border-radius: 16px;
}
QFrame#FieldCard:hover {
    border: 1px solid #93c5fd;
    background: #f8fbff;
}
QLabel#FieldLabel {
    color: #64748b;
    font-size: 13px;
    font-weight: 700;
    background: transparent;
}
QLabel#FieldContent {
    font-size: 19px;
    font-weight: 650;
    color: #0f172a;
    background: #ffffff;
    border: 1px solid #d7e2f0;
    border-radius: 12px;
    padding: 0 14px;
    min-height: 64px;
}
QLabel#CategoryBadge_Blue,
QLabel#CategoryBadge_Pink,
QLabel#CategoryBadge_Cyan,
QLabel#CategoryBadge_Mint,
QLabel#CategoryBadge_Lavender,
QLabel#CategoryBadge_Peach,
QLabel#CategoryBadge_Sky {
    min-height: 30px;
    padding-left: 12px;
    padding-right: 12px;
    border-radius: 15px;
    font-size: 13px;
    font-weight: 750;
}
QLabel#CategoryBadge_Blue {
    color: #1d4ed8;
    background: #dbeafe;
}
QLabel#CategoryBadge_Pink {
    color: #be185d;
    background: #fce7f3;
}
QLabel#CategoryBadge_Cyan {
    color: #0e7490;
    background: #cffafe;
}
QLabel#CategoryBadge_Mint {
    color: #047857;
    background: #d1fae5;
}
QLabel#CategoryBadge_Lavender {
    color: #6d28d9;
    background: #ede9fe;
}
QLabel#CategoryBadge_Peach {
    color: #c2410c;
    background: #ffedd5;
}
QLabel#CategoryBadge_Sky {
    color: #0369a1;
    background: #e0f2fe;
}
QPushButton {
    min-height: 36px;
    padding: 0 15px;
    border-radius: 10px;
    border: 1px solid #d4deeb;
    background: #ffffff;
}
QPushButton:hover {
    background: #eaf2ff;
    border-color: #93c5fd;
}
QPushButton:pressed {
    background: #dbeafe;
    padding-top: 1px;
}
QPushButton#PrimaryButton {
    color: white;
    background: #2563eb;
    border: 1px solid #2563eb;
    font-weight: 700;
}
QPushButton#PrimaryButton:hover {
    background: #1d4ed8;
    border-color: #1d4ed8;
}
QPushButton#PrimaryButton:pressed {
    background: #1e40af;
    border-color: #1e40af;
    padding-top: 1px;
}
QPushButton#PrimaryButton:focus {
    color: white;
    border: 1px solid #0f172a;
}
QPushButton#PrimaryButton:disabled {
    color: #334155;
    background: #e2e8f0;
    border-color: #cbd5e1;
}
QPushButton#SyncNowButton {
    color: #ffffff;
    background: #2563eb;
    border: 1px solid #2563eb;
    font-weight: 750;
    min-height: 36px;
    padding: 0 16px;
    border-radius: 10px;
}
QPushButton#SyncNowButton:hover {
    color: #ffffff;
    background: #1d4ed8;
    border-color: #1d4ed8;
}
QPushButton#SyncNowButton:pressed {
    color: #ffffff;
    background: #1e40af;
    border-color: #1e40af;
    padding-top: 1px;
}
QPushButton#SyncNowButton:focus {
    color: #ffffff;
    border: 1px solid #0f172a;
}
QPushButton#SyncNowButton:disabled {
    color: #334155;
    background: #e2e8f0;
    border-color: #cbd5e1;
}
QPushButton#NavButton, QPushButton#NavButtonActive {
    min-height: 42px;
    text-align: left;
    padding-left: 14px;
    border-radius: 11px;
    border: 1px solid transparent;
    background: transparent;
    color: #334155;
}
QPushButton#NavButton:hover {
    background: #edf4ff;
    border-color: #dbeafe;
}
QPushButton#NavButtonActive {
    color: #1d4ed8;
    background: #dbeafe;
    border: 1px solid #93c5fd;
    font-weight: 700;
}
QPushButton#SubtleButton {
    color: #334155;
    background: #ffffff;
    border: 1px solid #d4deeb;
}
QPushButton#SubtleButton:hover {
    color: #1d4ed8;
    background: #eaf2ff;
    border-color: #93c5fd;
}
QPushButton#SubtleButton:pressed {
    color: #1e40af;
    background: #dbeafe;
    border-color: #60a5fa;
    padding-top: 1px;
}
QPushButton#SubtleButton:focus {
    border: 1px solid #3b82f6;
}
QPushButton#DangerButton {
    color: white;
    background: #dc2626;
    border: 1px solid #dc2626;
    font-weight: 700;
}
QPushButton#DangerButton:hover {
    background: #b91c1c;
    border-color: #b91c1c;
}
QPushButton#DangerButton:pressed {
    background: #991b1b;
    border-color: #991b1b;
    padding-top: 1px;
}
QPushButton#DangerButton:focus {
    color: white;
    border: 1px solid #7f1d1d;
}
QPushButton#DangerButton:disabled {
    color: #fee2e2;
    background: #fca5a5;
    border-color: #fca5a5;
}
QPushButton#FormatButton,
QPushButton#FormatButtonWide {
    min-height: 32px;
    border-radius: 8px;
    background: #ffffff;
    border: 1px solid #d4deeb;
    font-weight: 700;
}
QPushButton#FormatButton {
    min-width: 36px;
    padding: 0;
}
QPushButton#FormatButtonWide {
    min-width: 54px;
    padding: 0 8px;
}
QPushButton#FormatButton:hover,
QPushButton#FormatButtonWide:hover {
    background: #eaf2ff;
    border-color: #93c5fd;
}
QPushButton#FormatButton:pressed,
QPushButton#FormatButtonWide:pressed {
    background: #dbeafe;
    border-color: #60a5fa;
    padding-top: 1px;
}
QPushButton#FormatButton:focus,
QPushButton#FormatButtonWide:focus {
    border: 1px solid #3b82f6;
}
QPushButton#ColorButtonBlack,
QPushButton#ColorButtonBlue,
QPushButton#ColorButtonPink,
QPushButton#ColorButtonGreen,
QPushButton#ColorButtonOrange {
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    border-radius: 13px;
    padding: 0;
    border: 2px solid #ffffff;
}
QPushButton#ColorButtonBlack:hover,
QPushButton#ColorButtonBlue:hover,
QPushButton#ColorButtonPink:hover,
QPushButton#ColorButtonGreen:hover,
QPushButton#ColorButtonOrange:hover {
    border: 2px solid #93c5fd;
}
QPushButton#ColorButtonBlack {
    background: #111827;
}
QPushButton#ColorButtonBlue {
    background: #2563eb;
}
QPushButton#ColorButtonPink {
    background: #db2777;
}
QPushButton#ColorButtonGreen {
    background: #059669;
}
QPushButton#ColorButtonOrange {
    background: #ea580c;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    min-height: 36px;
    border-radius: 10px;
    border: 1px solid #d4deeb;
    background: #ffffff;
    padding: 7px 11px;
    font-size: 14px;
}
QSpinBox#MinuteSpinBox {
    min-height: 36px;
    border-radius: 10px;
    border: 1px solid #d4deeb;
    background: #ffffff;
    padding: 7px 11px;
    font-size: 14px;
}
QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QComboBox:focus,
QSpinBox#MinuteSpinBox:focus {
    border: 1px solid #3b82f6;
}
QLabel#VaultFormLabel {
    color: #172033;
    background: transparent;
    font-size: 15px;
    font-weight: 650;
    min-height: 54px;
    qproperty-alignment: AlignVCenter;
}
QLineEdit#VaultInput {
    min-height: 54px;
    border-radius: 14px;
    padding: 0 16px;
    font-size: 17px;
    border: 1px solid #c9d8ec;
    background: #ffffff;
}
QLineEdit#VaultInput:focus {
    border: 1px solid #3b82f6;
}
QLineEdit#InlineEditor, QComboBox#InlineCombo, QComboBox#CategoryCombo {
    min-height: 64px;
    font-size: 17px;
    font-weight: 650;
    border-radius: 12px;
    background: #ffffff;
    border: 1px solid #d7e2f0;
    padding: 0 42px 0 14px;
}
QLineEdit#InlineEditor:hover, QComboBox#InlineCombo:hover, QComboBox#CategoryCombo:hover {
    background: #fbfdff;
    border: 1px solid #a9c8f8;
}
QLineEdit#InlineEditor:focus, QComboBox#InlineCombo:focus, QComboBox#CategoryCombo:focus {
    background: #ffffff;
    border: 1px solid #60a5fa;
}
QComboBox#InlineCombo::drop-down, QComboBox#CategoryCombo::drop-down {
    width: 36px;
    border: 0;
    border-left: 1px solid #e2e8f0;
    border-top-right-radius: 12px;
    border-bottom-right-radius: 12px;
    background: #f6f9fe;
}
QComboBox#InlineCombo::drop-down:hover, QComboBox#CategoryCombo::drop-down:hover {
    background: #edf5ff;
}
QComboBox#InlineCombo::down-arrow, QComboBox#CategoryCombo::down-arrow {
    image: url(__CHEVRON_DOWN_ICON__);
    width: 14px;
    height: 14px;
    margin-right: 11px;
}
QComboBox#SortCombo {
    min-width: 150px;
    min-height: 34px;
    border-radius: 10px;
    background: #ffffff;
    border: 1px solid #d7e2f0;
    padding: 5px 36px 5px 11px;
}
QComboBox#SortCombo:hover {
    border: 1px solid #a9c8f8;
    background: #fbfdff;
}
QComboBox#SortCombo::drop-down {
    width: 30px;
    border: 0;
    border-left: 1px solid #e2e8f0;
    border-top-right-radius: 10px;
    border-bottom-right-radius: 10px;
    background: #f6f9fe;
}
QComboBox#SortCombo::down-arrow {
    image: url(__CHEVRON_DOWN_ICON__);
    width: 14px;
    height: 14px;
    margin-right: 8px;
}
QTextEdit#DetailNote {
    background: #ffffff;
    border: 1px solid #dbe5f3;
    border-radius: 16px;
    font-size: 20px;
    line-height: 1.55;
    padding: 12px;
}
QTextEdit#TransferMessageInput {
    background: #ffffff;
    border: 1px solid #dbe5f3;
    border-radius: 14px;
    font-size: 15px;
    line-height: 1.45;
    padding: 10px;
}
QTextEdit#TransferMessageInput:focus {
    border: 1px solid #3b82f6;
}
QTextEdit#NoteBody {
    font-size: 16px;
    line-height: 1.55;
    padding: 12px;
}
QComboBox#FontSizeCombo {
    min-width: 58px;
    min-height: 32px;
    max-height: 32px;
    border-radius: 8px;
    background: #ffffff;
    border: 1px solid #d4deeb;
    padding: 4px 28px 4px 10px;
    font-size: 13px;
    font-weight: 700;
}
QComboBox#FontSizeCombo:hover {
    background: #eaf2ff;
    border-color: #93c5fd;
}
QComboBox#FontSizeCombo::drop-down {
    width: 24px;
    border: 0;
    border-left: 1px solid #e2e8f0;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    background: #f6f9fe;
}
QComboBox#FontSizeCombo::down-arrow {
    image: url(__CHEVRON_DOWN_ICON__);
    width: 12px;
    height: 12px;
    margin-right: 6px;
}
QComboBox#CategoryPillCombo_Blue,
QComboBox#CategoryPillCombo_Pink,
QComboBox#CategoryPillCombo_Cyan,
QComboBox#CategoryPillCombo_Mint,
QComboBox#CategoryPillCombo_Lavender,
QComboBox#CategoryPillCombo_Peach,
QComboBox#CategoryPillCombo_Sky {
    min-width: 118px;
    max-width: 150px;
    min-height: 36px;
    border-radius: 18px;
    font-size: 14px;
    font-weight: 750;
    padding: 5px 34px 5px 14px;
}
QComboBox#CategoryPillCombo_Blue {
    color: #1d4ed8;
    background: #dbeafe;
    border: 1px solid #bfdbfe;
}
QComboBox#CategoryPillCombo_Pink {
    color: #be185d;
    background: #fce7f3;
    border: 1px solid #fbcfe8;
}
QComboBox#CategoryPillCombo_Cyan {
    color: #0e7490;
    background: #cffafe;
    border: 1px solid #a5f3fc;
}
QComboBox#CategoryPillCombo_Mint {
    color: #047857;
    background: #d1fae5;
    border: 1px solid #a7f3d0;
}
QComboBox#CategoryPillCombo_Lavender {
    color: #6d28d9;
    background: #ede9fe;
    border: 1px solid #ddd6fe;
}
QComboBox#CategoryPillCombo_Peach {
    color: #c2410c;
    background: #ffedd5;
    border: 1px solid #fed7aa;
}
QComboBox#CategoryPillCombo_Sky {
    color: #0369a1;
    background: #e0f2fe;
    border: 1px solid #bae6fd;
}
QComboBox#CategoryPillCombo_Blue:hover,
QComboBox#CategoryPillCombo_Pink:hover,
QComboBox#CategoryPillCombo_Cyan:hover,
QComboBox#CategoryPillCombo_Mint:hover,
QComboBox#CategoryPillCombo_Lavender:hover,
QComboBox#CategoryPillCombo_Peach:hover,
QComboBox#CategoryPillCombo_Sky:hover {
    border-color: #60a5fa;
}
QComboBox#CategoryPillCombo_Blue:focus,
QComboBox#CategoryPillCombo_Pink:focus,
QComboBox#CategoryPillCombo_Cyan:focus,
QComboBox#CategoryPillCombo_Mint:focus,
QComboBox#CategoryPillCombo_Lavender:focus,
QComboBox#CategoryPillCombo_Peach:focus,
QComboBox#CategoryPillCombo_Sky:focus {
    border-color: #2563eb;
}
QComboBox#CategoryPillCombo_Blue::drop-down,
QComboBox#CategoryPillCombo_Pink::drop-down,
QComboBox#CategoryPillCombo_Cyan::drop-down,
QComboBox#CategoryPillCombo_Mint::drop-down,
QComboBox#CategoryPillCombo_Lavender::drop-down,
QComboBox#CategoryPillCombo_Peach::drop-down,
QComboBox#CategoryPillCombo_Sky::drop-down {
    width: 28px;
    border: 0;
    border-top-right-radius: 18px;
    border-bottom-right-radius: 18px;
    background: rgba(255,255,255,.28);
}
QComboBox#CategoryPillCombo_Blue::drop-down:hover,
QComboBox#CategoryPillCombo_Pink::drop-down:hover,
QComboBox#CategoryPillCombo_Cyan::drop-down:hover,
QComboBox#CategoryPillCombo_Mint::drop-down:hover,
QComboBox#CategoryPillCombo_Lavender::drop-down:hover,
QComboBox#CategoryPillCombo_Peach::drop-down:hover,
QComboBox#CategoryPillCombo_Sky::drop-down:hover {
    background: rgba(255,255,255,.5);
}
QComboBox#CategoryPillCombo_Blue::down-arrow,
QComboBox#CategoryPillCombo_Pink::down-arrow,
QComboBox#CategoryPillCombo_Cyan::down-arrow,
QComboBox#CategoryPillCombo_Mint::down-arrow,
QComboBox#CategoryPillCombo_Lavender::down-arrow,
QComboBox#CategoryPillCombo_Peach::down-arrow,
QComboBox#CategoryPillCombo_Sky::down-arrow {
    image: url(__CHEVRON_DOWN_ICON__);
    width: 13px;
    height: 13px;
    margin-right: 8px;
}
QComboBox {
    padding-right: 38px;
}
QComboBox::drop-down {
    width: 32px;
    border: 0;
    border-left: 1px solid #e2e8f0;
    border-top-right-radius: 10px;
    border-bottom-right-radius: 10px;
    background: #f6f9fe;
}
QComboBox::drop-down:hover {
    background: #edf5ff;
}
QComboBox::down-arrow {
    image: url(__CHEVRON_DOWN_ICON__);
    width: 14px;
    height: 14px;
    margin-right: 9px;
}
QComboBox QAbstractItemView {
    outline: 0;
    border: 1px solid #d4deeb;
    border-radius: 12px;
    background: #ffffff;
    selection-background-color: #dbeafe;
    selection-color: #0f172a;
    padding: 6px;
    font-size: 15px;
}
QMenu {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    padding: 5px;
}
QMenu::item {
    min-height: 30px;
    padding: 6px 34px 6px 28px;
    border-radius: 7px;
    color: #172033;
}
QMenu::item:selected {
    background: #dbeafe;
    color: #0f172a;
}
QMenu::item:pressed {
    background: #bfdbfe;
    color: #0f172a;
}
QMenu::item:disabled {
    color: #94a3b8;
    background: transparent;
}
QMenu::separator {
    height: 1px;
    background: #e2e8f0;
    margin: 5px 8px;
}
QListWidget {
    border: 0;
    background: transparent;
}
QListWidget#RecordList {
    border-radius: 16px;
}
QListWidget#TransferMessageList {
    background: #f6f9fe;
    border: 1px solid #dbe5f3;
    border-radius: 16px;
    padding: 8px;
}
QListWidget#TransferMessageList::item:hover {
    background: transparent;
    border: 0;
}
QListWidget#TransferMessageList::item:selected {
    background: #e0edff;
    border: 1px solid #93c5fd;
}
QFrame#TransferBubbleDesktop {
    background: #dcf8c6;
    border: 1px solid #b7e59c;
    border-radius: 14px;
}
QFrame#TransferBubblePhone {
    background: #ffffff;
    border: 1px solid #dbe5f3;
    border-radius: 14px;
}
QLabel#TransferBubbleMeta {
    color: #64748b;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}
QLabel#TransferBubbleText {
    color: #0f172a;
    font-size: 15px;
    line-height: 1.45;
    background: transparent;
}
QLabel#TransferImagePreview {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 6px;
}
QListWidget::item {
    min-height: 62px;
    padding: 0;
    border-radius: 16px;
}
QListWidget::item:hover {
    background: #dbeafe;
    border: 1px solid #93c5fd;
}
QListWidget::item:selected {
    background: #bfdbfe;
    border: 1px solid #60a5fa;
    color: #0f172a;
}
QFrame#DialogHero {
    background: #eaf2ff;
    border: 1px solid #bfdbfe;
    border-radius: 18px;
}
QLabel#DialogTitle {
    font-size: 24px;
    font-weight: 750;
    color: #0f172a;
    background: transparent;
}
QLabel#BrandMarkLarge {
    background: transparent;
    border: 0;
}
QLabel#BrandMarkSmall {
    background: transparent;
    border: 0;
}
""".replace("__CHEVRON_DOWN_ICON__", CHEVRON_DOWN_ICON)
