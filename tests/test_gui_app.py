"""Headless startup tests for the minimal PySide6 application shell."""

from __future__ import annotations

import os
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QWidget

from eas.gui import app as gui_app


def test_create_application_reuses_existing_qapplication(
    qapp: QApplication,
) -> None:
    """Startup must reuse the one QApplication allowed in the process."""
    application = gui_app.create_application(["eas-curation-gui"])

    assert application is qapp
    assert application.applicationName() == gui_app.APPLICATION_NAME


def test_create_startup_window_is_visible_shell(
    qtbot: Any,
) -> None:
    """The Stage 1 shell must create a small visible top-level widget."""
    window = gui_app.create_startup_window()
    qtbot.addWidget(window)

    window.show()
    qtbot.waitExposed(window)

    assert window.isVisible()
    assert window.objectName() == "easStartupWindow"
    assert window.windowTitle() == gui_app.WINDOW_TITLE
    label = window.findChild(QLabel, "startupLabel")
    assert label is not None
    assert label.text() == "EAS Curation desktop shell"


def test_main_shows_shell_and_returns_event_loop_exit_code(
    qapp: QApplication,
    monkeypatch: Any,
    qtbot: Any,
) -> None:
    """The GUI entry point must show one shell and return Qt's exit code."""

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
    monkeypatch.setattr(gui_app, "create_startup_window", lambda: window)
    monkeypatch.setattr(gui_app.QApplication, "exec", lambda _self: 23)

    exit_code = gui_app.main(["eas-curation-gui"])

    assert gui_app.QApplication.instance() is qapp
    assert exit_code == 23
    assert window.was_shown is True
    assert window.was_closed is True
