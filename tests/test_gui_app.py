"""Headless startup tests for the functional PySide6 application."""

from __future__ import annotations

import os
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from eas.gui import app as gui_app
from eas.gui.window import CurationWindow


def test_create_application_reuses_existing_qapplication(
    qapp: QApplication,
) -> None:
    """Startup must reuse the one QApplication allowed in the process."""
    application = gui_app.create_application(["eas-curation-gui"])
    assert application is qapp
    assert application.applicationName() == gui_app.APPLICATION_NAME


def test_create_main_window_is_functional(qtbot: Any) -> None:
    """The application must create the functional Stage 3 window."""
    window = gui_app.create_main_window()
    qtbot.addWidget(window)
    assert isinstance(window, CurationWindow)
    assert window.objectName() == "easCurationWindow"
    assert window.windowTitle() == gui_app.WINDOW_TITLE


def test_main_shows_window_and_returns_event_loop_exit_code(
    qapp: QApplication,
    monkeypatch: Any,
    qtbot: Any,
) -> None:
    """The entry point must show one window and return Qt's exit code."""

    class RecordingWindow(QWidget):
        """Record lifecycle calls without entering a real event loop."""

        def __init__(self) -> None:
            super().__init__()
            self.was_shown = False
            self.was_closed = False

        def show(self) -> None:
            self.was_shown = True
            super().show()

        def close(self) -> bool:
            self.was_closed = True
            return super().close()

    window = RecordingWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(gui_app, "create_main_window", lambda: window)
    monkeypatch.setattr(gui_app.QApplication, "exec", lambda _self: 23)

    exit_code = gui_app.main(["eas-curation-gui"])

    assert gui_app.QApplication.instance() is qapp
    assert exit_code == 23
    assert window.was_shown is True
    assert window.was_closed is True
