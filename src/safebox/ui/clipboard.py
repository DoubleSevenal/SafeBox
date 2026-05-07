from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication


class SecureClipboard:
    def __init__(self, clear_after_seconds: int = 20) -> None:
        self.clear_after_ms = clear_after_seconds * 1000
        self._last_text = ""

    def copy(self, text: str) -> None:
        self._last_text = text
        QApplication.clipboard().setText(text)
        QTimer.singleShot(self.clear_after_ms, self.clear_if_unchanged)

    def clear_if_unchanged(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard.text() == self._last_text:
            clipboard.clear()
