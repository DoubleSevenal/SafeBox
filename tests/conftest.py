import os
from pathlib import Path
from time import sleep
from uuid import uuid4

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def vault_path() -> Path:
    root = Path.cwd() / ".test-output"
    root.mkdir(exist_ok=True)
    path = root / f"{uuid4().hex}.db"
    yield path
    if path.exists():
        for _ in range(5):
            try:
                path.unlink()
                break
            except PermissionError:
                sleep(0.1)


@pytest.fixture(scope="session")
def qt_app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
