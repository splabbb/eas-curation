"""Minimal PySide6 application startup for EAS Curation."""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)

APPLICATION_NAME = "EAS Curation"
WINDOW_TITLE = "EAS Curation"


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    """Return the process QApplication, creating it when necessary.

    Args:
        argv: Optional application arguments. The process arguments are used
            when this value is omitted.

    Returns:
        The single QApplication instance for the current process.

    Raises:
        RuntimeError: If a non-widget Qt application already exists.
    """
    existing = QApplication.instance()
    if existing is not None:
        if not isinstance(existing, QApplication):
            raise RuntimeError(
                "A non-QApplication Qt application already exists"
            )
        existing.setApplicationName(APPLICATION_NAME)
        return existing

    arguments = list(sys.argv if argv is None else argv)
    application = QApplication(arguments)
    application.setApplicationName(APPLICATION_NAME)
    return application


def create_startup_window() -> QWidget:
    """Create the temporary visible shell used before the main window exists."""
    window = QWidget()
    window.setObjectName("easStartupWindow")
    window.setWindowTitle(WINDOW_TITLE)
    window.resize(480, 160)

    layout = QVBoxLayout(window)
    message = QLabel("EAS Curation desktop shell")
    message.setObjectName("startupLabel")
    layout.addWidget(message)
    return window


def main(argv: Sequence[str] | None = None) -> int:
    """Start the minimal desktop shell and return the Qt exit code."""
    application = create_application(argv)
    window = create_startup_window()
    window.show()
    logger.info("Starting EAS Curation desktop shell")
    exit_code = int(application.exec())
    window.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
