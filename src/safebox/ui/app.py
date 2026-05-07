from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from safebox.core.services import VaultService
from safebox.core.vault_profiles import app_data_dir, vault_path_for_name
from safebox.ui.branding import SAFEBOX_APP_ICON_PATH
from safebox.ui.main_window import MainWindow
from safebox.ui.theme import LIGHT_FLUENT_QSS


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SafeBox")
    app.setWindowIcon(QIcon(str(SAFEBOX_APP_ICON_PATH)))
    app.setStyleSheet(LIGHT_FLUENT_QSS)
    window = MainWindow(lambda name: VaultService(vault_path_for_name(app_data_dir(), name)))
    window.setWindowIcon(QIcon(str(SAFEBOX_APP_ICON_PATH)))
    window.resize(1120, 720)
    window.show()
    return app.exec()

