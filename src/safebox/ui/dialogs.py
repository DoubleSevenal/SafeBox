from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from safebox.core.models import Record
from safebox.ui.branding import SAFEBOX_LOGIN_LOGO_PATH

CATEGORIES = ["邮箱", "学校", "工作", "游戏", "生活", "软件", "其他"]
NOTE_CATEGORIES = ["收件箱", "MD", "TXT", *CATEGORIES]
DEFAULT_VAULT_ID = "于祥磊"


class VaultOpenMode(StrEnum):
    OPEN = "open"
    REGISTER = "register"


@dataclass(slots=True)
class AccountFormData:
    name: str
    account: str
    password: str
    category: str
    note: str
    entry_hint: str

    def to_payload(self) -> dict[str, str]:
        return {
            "name": self.name,
            "account": self.account,
            "password": self.password,
            "category": self.category,
            "note": self.note,
            "entry_hint": self.entry_hint,
        }


class VaultOpenDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.mode = VaultOpenMode.OPEN
        self.setWindowTitle("SafeBox")
        self.setMinimumWidth(560)

        self.vault_name = QLineEdit()
        self.vault_name.setObjectName("VaultInput")
        self.vault_name.setPlaceholderText("输入保险箱ID")
        self.vault_name.setText(DEFAULT_VAULT_ID)

        self.password = QLineEdit()
        self.password.setObjectName("VaultInput")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("输入保险箱密码")

        self.confirm_password = QLineEdit()
        self.confirm_password.setObjectName("VaultInput")
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password.setPlaceholderText("再次输入保险箱密码")
        self.confirm_password.setVisible(False)

        self.confirm_label = QLabel("确认密码")
        self.confirm_label.setObjectName("VaultFormLabel")
        self.confirm_label.setVisible(False)

        self.open_button = QPushButton("打开保险箱")
        self.open_button.setObjectName("PrimaryButton")
        self.register_button = QPushButton("注册保险箱")
        self.register_button.setObjectName("SubtleButton")

        self.open_button.clicked.connect(self._accept_open)
        self.register_button.clicked.connect(self._accept_register)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(14)

        card = QFrame()
        card.setObjectName("DialogHero")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 18, 22, 18)
        card_layout.setSpacing(8)
        self.brand_mark = QLabel()
        self.brand_mark.setObjectName("BrandMarkLarge")
        self.brand_mark.setFixedSize(124, 124)
        self.brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_mark.setPixmap(
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
        card_layout.addWidget(self.brand_mark, 0, Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(title)
        card_layout.addWidget(hint)

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
        form.addWidget(self.vault_name, 0, 1)
        form.addWidget(password_label, 1, 0)
        form.addWidget(self.password, 1, 1)
        form.addWidget(self.confirm_label, 2, 0)
        form.addWidget(self.confirm_password, 2, 1)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.addWidget(self.open_button, 1)
        action_row.addWidget(self.register_button, 1)

        layout.addWidget(card)
        layout.addLayout(form)
        layout.addLayout(action_row)

    def _toggle_mode(self) -> None:
        if self.mode == VaultOpenMode.OPEN:
            self.mode = VaultOpenMode.REGISTER
            self.open_button.setText("返回打开")
            self.open_button.setObjectName("SubtleButton")
            self.register_button.setObjectName("PrimaryButton")
            self.confirm_label.setVisible(True)
            self.confirm_password.setVisible(True)
            self.vault_name.setPlaceholderText("设置保险箱ID")
            self.password.setPlaceholderText("设置保险箱密码")
        else:
            self.mode = VaultOpenMode.OPEN
            self.open_button.setText("打开保险箱")
            self.open_button.setObjectName("PrimaryButton")
            self.register_button.setObjectName("SubtleButton")
            self.confirm_label.setVisible(False)
            self.confirm_password.setVisible(False)
            self.vault_name.setPlaceholderText("输入保险箱ID")
            self.password.setPlaceholderText("输入保险箱密码")
        _refresh_button_style(self.open_button)
        _refresh_button_style(self.register_button)

    def _accept_open(self) -> None:
        if self.mode == VaultOpenMode.REGISTER:
            self._toggle_mode()
            return
        self.accept()

    def _accept_register(self) -> None:
        if self.mode == VaultOpenMode.OPEN:
            self._toggle_mode()
            return
        self.accept()

    def values(self) -> tuple[str, str, str, str]:
        return (
            self.vault_name.text().strip() or DEFAULT_VAULT_ID,
            self.password.text(),
            self.confirm_password.text(),
            self.mode.value,
        )


class ChangePasswordDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("修改保险箱密码")
        self.setMinimumWidth(460)
        self.old_password = QLineEdit()
        self.old_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.old_password.setPlaceholderText("输入原保险箱密码")
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password.setPlaceholderText("输入新保险箱密码")
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password.setPlaceholderText("再次输入新保险箱密码")
        save = QPushButton("修改")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self.accept)
        cancel = QPushButton("取消")
        cancel.setObjectName("SubtleButton")
        cancel.clicked.connect(self.reject)

        form = QGridLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        form.setColumnMinimumWidth(0, 116)
        form.setColumnStretch(1, 1)
        for row, (label, widget) in enumerate(
            (
                ("原保险箱密码", self.old_password),
                ("新保险箱密码", self.new_password),
                ("确认新密码", self.confirm_password),
            )
        ):
            text = QLabel(label)
            text.setObjectName("VaultFormLabel")
            form.addWidget(text, row, 0)
            form.addWidget(widget, row, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 18)
        title = QLabel("修改保险箱密码")
        title.setObjectName("DialogTitle")
        hint = QLabel("修改后，下次打开这个保险箱需要使用新密码。")
        hint.setObjectName("MutedText")
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(form)
        layout.addLayout(actions)

    def values(self) -> tuple[str, str, str]:
        return (
            self.old_password.text(),
            self.new_password.text(),
            self.confirm_password.text(),
        )


class AccountDialog(QDialog):
    def __init__(self, parent=None, record: Record | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑账号" if record else "新建账号")
        self.setMinimumWidth(560)
        self.name = QLineEdit()
        self.name.setPlaceholderText("例如：学校二课平台")
        self.account = QLineEdit()
        self.account.setPlaceholderText("手机号、邮箱、学号或用户名")
        self.password = QLineEdit()
        self.password.setPlaceholderText("输入已有密码")
        self.category = QComboBox()
        self.category.setObjectName("CategoryCombo")
        self.category.setEditable(True)
        self.category.addItems(CATEGORIES)
        self.entry_hint = QLineEdit()
        self.entry_hint.setPlaceholderText("例如：微信公众号菜单、小程序、网址")
        self.note = QTextEdit()
        self.note.setPlaceholderText("备注可以写入口说明、绑定手机号、注意事项等")

        save = QPushButton("保存")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self.accept)
        cancel = QPushButton("取消")
        cancel.setObjectName("SubtleButton")
        cancel.clicked.connect(self.reject)

        form = QGridLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        form.setColumnMinimumWidth(0, 76)
        form.setColumnStretch(1, 1)
        for row, (label, widget) in enumerate(
            (
                ("名称", self.name),
                ("账号", self.account),
                ("密码", self.password),
                ("分类", self.category),
                ("入口说明", self.entry_hint),
                ("备注", self.note),
            )
        ):
            text = QLabel(label)
            text.setObjectName("VaultFormLabel")
            form.addWidget(text, row, 0)
            form.addWidget(widget, row, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 18)
        header = QFrame()
        header.setObjectName("DialogHero")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_title = QLabel("编辑账号" if record else "新建账号")
        header_title.setObjectName("DialogTitle")
        header_subtitle = QLabel("保存网站、应用、公众号、小程序或校园平台的账号密码。")
        header_subtitle.setObjectName("MutedText")
        header_subtitle.setWordWrap(True)
        header_layout.addWidget(header_title)
        header_layout.addWidget(header_subtitle)
        layout.addWidget(header)
        layout.addLayout(form)
        layout.addLayout(actions)

        if record:
            self.name.setText(record.name)
            self.account.setText(record.account)
            self.password.setText(record.password)
            self.category.setCurrentText(record.category)
            self.entry_hint.setText(record.entry_hint)
            self.note.setPlainText(record.note)
        else:
            self.category.setCurrentText("其他")

    def data(self) -> AccountFormData:
        return AccountFormData(
            name=self.name.text().strip(),
            account=self.account.text().strip(),
            password=self.password.text(),
            category=self.category.currentText().strip(),
            note=self.note.toPlainText().strip(),
            entry_hint=self.entry_hint.text().strip(),
        )


def _refresh_button_style(button: QPushButton) -> None:
    button.style().unpolish(button)
    button.style().polish(button)
