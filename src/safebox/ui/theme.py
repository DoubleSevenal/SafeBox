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
QLabel#SettingsLabel {
    color: #475569;
    background: transparent;
    font-size: 13px;
    font-weight: 700;
    min-width: 80px;
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
    border: 1px solid #0f172a;
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
QListWidget {
    border: 0;
    background: transparent;
}
QListWidget#RecordList {
    border-radius: 16px;
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
