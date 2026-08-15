"""Functional PySide6 window for configuring and running curation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from eas.application import CurationRunRequest, CurationRunResult
from eas.gui.controller import CurationController
from eas.gui.results import CurationResultsWidget


class CurationWindow(QMainWindow):
    """Collect curation settings and present factual run outcomes."""

    def __init__(
        self,
        controller: CurationController | None = None,
        *,
        window_title: str = "EAS Curation",
    ) -> None:
        """Create a window connected to one curation controller."""
        super().__init__()
        self.setObjectName("easCurationWindow")
        self.setWindowTitle(window_title)
        self.resize(720, 560)
        self._controller = (
            CurationController(self)
            if controller is None
            else controller
        )
        self._request_controls: list[QWidget] = []
        self._close_after_thumbnail_shutdown = False
        self._build_ui()
        self._connect_controller()

    def _build_ui(self) -> None:
        """Create and arrange all request and result controls."""
        central = QWidget(self)
        layout = QVBoxLayout(central)
        form = QFormLayout()

        self.input_directory = QLineEdit()
        self.input_directory.setObjectName("inputDirectoryField")
        self.input_browse = QPushButton("Browse")
        self.input_browse.setObjectName("inputBrowseButton")
        input_row = self._directory_row(
            self.input_directory,
            self.input_browse,
        )
        form.addRow("Input directory", input_row)

        self.output_directory = QLineEdit()
        self.output_directory.setObjectName("outputDirectoryField")
        self.output_browse = QPushButton("Browse")
        self.output_browse.setObjectName("outputBrowseButton")
        output_row = self._directory_row(
            self.output_directory,
            self.output_browse,
        )
        form.addRow("Output directory", output_row)

        self.top_n = QSpinBox()
        self.top_n.setObjectName("topNControl")
        self.top_n.setRange(1, 1_000_000)
        self.top_n.setValue(10)
        form.addRow("Top N", self.top_n)

        self.threshold = QDoubleSpinBox()
        self.threshold.setObjectName("thresholdControl")
        self.threshold.setRange(0.0, 1.0)
        self.threshold.setDecimals(3)
        self.threshold.setSingleStep(0.05)
        self.threshold.setValue(0.5)
        form.addRow("Threshold", self.threshold)

        self.model_name = QLineEdit("ViT-B/32")
        self.model_name.setObjectName("modelNameField")
        form.addRow("Model name", self.model_name)

        self.deduplicate = QCheckBox("Detect exact duplicates")
        self.deduplicate.setObjectName("deduplicateCheckBox")
        self.deduplicate.setChecked(True)
        form.addRow(self.deduplicate)

        self.dry_run = QCheckBox("Dry run")
        self.dry_run.setObjectName("dryRunCheckBox")
        form.addRow(self.dry_run)
        layout.addLayout(form)

        self.run_button = QPushButton("Run")
        self.run_button.setObjectName("runButton")
        layout.addWidget(self.run_button)

        self.busy_indicator = QProgressBar()
        self.busy_indicator.setObjectName("busyIndicator")
        self.busy_indicator.setRange(0, 0)
        self.busy_indicator.setVisible(False)
        layout.addWidget(self.busy_indicator)

        self.status_text = QLabel("Ready")
        self.status_text.setObjectName("statusText")
        layout.addWidget(self.status_text)

        self.result_summary = QLabel("No run completed.")
        self.result_summary.setObjectName("resultSummary")
        self.result_summary.setWordWrap(True)
        layout.addWidget(self.result_summary)

        self.artifact_paths = QLabel("No artifacts written.")
        self.artifact_paths.setObjectName("artifactPaths")
        self.artifact_paths.setWordWrap(True)
        self.result_summary.setVisible(False)
        self.artifact_paths.setVisible(False)
        self.results_workspace = CurationResultsWidget(self)
        self.results_workspace.setObjectName("windowResultsWorkspace")
        self.results_workspace.setAccessibleName("Curation results workspace")
        layout.addWidget(self.results_workspace, 1)
        self.setCentralWidget(central)

        self._request_controls = [
            self.input_directory,
            self.input_browse,
            self.output_directory,
            self.output_browse,
            self.top_n,
            self.threshold,
            self.model_name,
            self.deduplicate,
            self.dry_run,
            self.run_button,
        ]
        self.input_browse.clicked.connect(self._browse_input)
        self.output_browse.clicked.connect(self._browse_output)
        self.run_button.clicked.connect(self._start_run)
        self.results_workspace._thumbnail_loader.stopped.connect(
            self._on_thumbnail_loader_stopped
        )

    @staticmethod
    def _directory_row(
        field: QLineEdit,
        button: QPushButton,
    ) -> QWidget:
        """Return one directory field with its browse action."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(field)
        layout.addWidget(button)
        return widget

    def _connect_controller(self) -> None:
        """Connect controller lifecycle signals to presentation slots."""
        self._controller.started.connect(self._on_started)
        self._controller.succeeded.connect(self._on_succeeded)
        self._controller.failed.connect(self._on_failed)
        self._controller.finished.connect(self._on_finished)

    @Slot()
    def _browse_input(self) -> None:
        """Prompt for an input directory."""
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select input directory",
            self.input_directory.text(),
        )
        if selected:
            self.input_directory.setText(selected)

    @Slot()
    def _browse_output(self) -> None:
        """Prompt for an output directory."""
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select output directory",
            self.output_directory.text(),
        )
        if selected:
            self.output_directory.setText(selected)

    @Slot()
    def _start_run(self) -> None:
        """Build an immutable request and offer it to the controller."""
        input_directory = self.input_directory.text().strip()
        output_directory = self.output_directory.text().strip()
        model_name = self.model_name.text().strip()
        blank_fields = [
            label
            for label, value in (
                ("input directory", input_directory),
                ("output directory", output_directory),
                ("model name", model_name),
            )
            if not value
        ]
        if blank_fields:
            self.status_text.setText(
                f"Invalid request: {blank_fields[0]} must not be blank"
            )
            return

        try:
            request = CurationRunRequest(
                input_dir=Path(input_directory),
                output_dir=Path(output_directory),
                top_n=self.top_n.value(),
                threshold=self.threshold.value(),
                model_name=model_name,
                deduplicate=self.deduplicate.isChecked(),
                dry_run=self.dry_run.isChecked(),
            )
        except (TypeError, ValueError) as exception:
            self.status_text.setText(f"Invalid request: {exception}")
            return

        if not self._controller.start(request):
            self.status_text.setText("A curation run is already active.")

    @Slot()
    def _on_started(self) -> None:
        """Present the active state and lock request controls."""
        for control in self._request_controls:
            control.setEnabled(False)
        self.busy_indicator.setVisible(True)
        self.status_text.setText("Curation is running.")
        self.result_summary.setText("Awaiting results.")
        self.artifact_paths.setText("No artifacts reported yet.")
        self.results_workspace.set_running_state()

    @Slot(object)
    def _on_succeeded(self, result: object) -> None:
        """Present counts and artifact paths from a successful result."""
        if not isinstance(result, CurationRunResult):
            self.status_text.setText(
                "Curation failed: invalid result type."
            )
            return

        failed_count = len(result.failed_analysis_paths)
        self.status_text.setText("Curation completed.")
        self.result_summary.setText(
            f"Discovered: {result.discovered_count} | "
            f"Analyzed: {result.analyzed_count} | "
            f"Failed analysis: {failed_count} | "
            f"Selected: {result.selected_count}"
        )
        if result.written_artifacts:
            self.artifact_paths.setText(
                "Written artifacts:\n"
                + "\n".join(result.written_artifacts)
            )
        else:
            self.artifact_paths.setText("No artifacts written.")
        self.results_workspace.set_result(result)

    @Slot(object)
    def _on_failed(self, exception: object) -> None:
        """Present concise facts without replacing the original error."""
        if isinstance(exception, Exception):
            detail = str(exception).strip()
            description = type(exception).__name__
            if detail:
                description = f"{description}: {detail}"
        else:
            description = f"Unexpected failure value: {exception!r}"
        self.status_text.setText(f"Curation failed: {description}")
        self.result_summary.setText("No result was produced.")
        self.artifact_paths.setText("No artifacts reported.")
        if isinstance(exception, Exception):
            self.results_workspace.set_failure(exception)

    @Slot()
    def _on_finished(self) -> None:
        """Restore request controls after terminal cleanup completes."""
        for control in self._request_controls:
            control.setEnabled(True)
        self.busy_indicator.setVisible(False)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Reject closing while a run is active; otherwise accept it."""
        if self._controller.is_running:
            self.status_text.setText(
                "Cannot close while curation is running."
            )
            event.ignore()
            return
        thread = self.results_workspace._thumbnail_loader.worker_thread
        try:
            running = thread.isRunning()
        except RuntimeError:
            running = False
        if running:
            self._close_after_thumbnail_shutdown = True
            self.status_text.setText("Closing after thumbnail cleanup.")
            self.results_workspace.shutdown_thumbnails()
            event.ignore()
            return
        event.accept()

    @Slot()
    def _on_thumbnail_loader_stopped(self) -> None:
        """Retry deferred idle close after thumbnail cleanup."""
        if self._close_after_thumbnail_shutdown:
            self._close_after_thumbnail_shutdown = False
            QTimer.singleShot(0, self.close)
