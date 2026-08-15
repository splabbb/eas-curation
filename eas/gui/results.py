"""Factual presentation of completed curation results."""

from __future__ import annotations

from collections import Counter, deque
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Slot
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from eas.application import CurationRunResult
from eas.clustering import ExactDuplicateGroup, ExactDuplicateReport
from eas.integrity import IntegrityReport
from eas.pipeline import ImageResult
from eas.gui.thumbnails import ThumbnailLoader, ThumbnailRequest, ThumbnailResult

_PATH_ROLE = Qt.ItemDataRole.UserRole
_RANK_ROLE = int(Qt.ItemDataRole.UserRole) + 1
THUMBNAIL_WIDTH = 160
THUMBNAIL_HEIGHT = 120


class CurationResultsWidget(QWidget):
    """Display one immutable curation result without interpreting its facts."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create an empty results workspace."""
        super().__init__(parent)
        self.setObjectName("curationResultsWidget")
        self.setAccessibleName("Curation results")
        self._result: CurationRunResult | None = None
        self._artifact_buttons: list[QPushButton] = []
        self._thumbnail_generation = 0
        self._thumbnail_pending: deque[ThumbnailRequest] = deque()
        self._thumbnail_paths: set[str] = set()
        self._thumbnail_loader = ThumbnailLoader(self)
        self._thumbnail_loader.loaded.connect(self._on_thumbnail_loaded)
        self._build_ui()
        self.clear()

    @property
    def result(self) -> CurationRunResult | None:
        """Return the exact result object currently presented."""
        return self._result

    def _build_ui(self) -> None:
        """Build the contact sheet and factual detail pane."""
        layout = QVBoxLayout(self)
        self.state_label = QLabel()
        self.state_label.setObjectName("resultsStateLabel")
        self.state_label.setAccessibleName("Results state")
        self.state_label.setWordWrap(True)
        layout.addWidget(self.state_label)
        self.counts_label = QLabel()
        self.counts_label.setObjectName("resultsCountsLabel")
        self.counts_label.setAccessibleName("Results counts")
        self.counts_label.setWordWrap(True)
        layout.addWidget(self.counts_label)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("resultsSplitter")
        self.splitter.setAccessibleName("Results workspace")
        layout.addWidget(self.splitter, 1)

        self.contact_sheet = QListWidget()
        self.contact_sheet.setObjectName("resultsContactSheet")
        self.contact_sheet.setAccessibleName("Selected images")
        self.contact_sheet.setViewMode(QListWidget.ViewMode.IconMode)
        self.contact_sheet.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.contact_sheet.setMovement(QListWidget.Movement.Static)
        self.contact_sheet.currentRowChanged.connect(
            self._show_selected_details
        )
        self.splitter.addWidget(self.contact_sheet)

        detail_scroll = QScrollArea()
        detail_scroll.setObjectName("resultsDetailScrollArea")
        detail_scroll.setAccessibleName("Selected image details")
        detail_scroll.setWidgetResizable(True)
        self.detail_pane = QWidget()
        self.detail_pane.setObjectName("resultsDetailPane")
        self.detail_pane.setAccessibleName("Selected image details")
        detail_layout = QVBoxLayout(self.detail_pane)

        details_group = QGroupBox("Selected image")
        details_group.setObjectName("selectedImageGroup")
        details_group.setAccessibleName("Selected image facts")
        details_form = QFormLayout(details_group)
        self._detail_labels: dict[str, QLabel] = {}
        for key, caption in (
            ("filename", "Filename"),
            ("path", "Complete path"),
            ("rank", "Rank"),
            ("score", "Score"),
            ("passed", "Pass state"),
            ("sharpness", "Sharpness"),
            ("exposure", "Exposure"),
            ("contrast", "Contrast"),
            ("dynamic_range", "Dynamic range"),
            ("resolution", "Resolution"),
            ("clipping", "Clipping"),
            ("aesthetic", "Aesthetic"),
        ):
            label = QLabel("Not selected")
            label.setObjectName(f"detail{key.title().replace('_', '')}")
            label.setAccessibleName(caption)
            label.setWordWrap(True)
            details_form.addRow(caption, label)
            self._detail_labels[key] = label
        detail_layout.addWidget(details_group)

        self.failed_analysis_label = QLabel()
        self.failed_analysis_label.setObjectName("failedAnalysisPaths")
        self.failed_analysis_label.setAccessibleName("Failed analysis paths")
        self.failed_analysis_label.setWordWrap(True)
        detail_layout.addWidget(self.failed_analysis_label)

        self.duplicate_report_label = QLabel()
        self.duplicate_report_label.setObjectName("duplicateReport")
        self.duplicate_report_label.setAccessibleName("Duplicate report")
        self.duplicate_report_label.setWordWrap(True)
        detail_layout.addWidget(self.duplicate_report_label)

        self.integrity_report_label = QLabel()
        self.integrity_report_label.setObjectName("integrityReport")
        self.integrity_report_label.setAccessibleName("Integrity report")
        self.integrity_report_label.setWordWrap(True)
        detail_layout.addWidget(self.integrity_report_label)

        artifacts_group = QGroupBox("Written artifacts")
        artifacts_group.setObjectName("artifactsGroup")
        artifacts_group.setAccessibleName("Written artifacts")
        self.artifacts_layout = QVBoxLayout(artifacts_group)
        self.artifacts_empty_label = QLabel("No artifacts were written.")
        self.artifacts_empty_label.setObjectName("artifactsEmptyLabel")
        self.artifacts_empty_label.setAccessibleName("Artifact state")
        self.artifacts_layout.addWidget(self.artifacts_empty_label)
        detail_layout.addWidget(artifacts_group)

        self.open_output_button = QPushButton("Open Output Folder")
        self.open_output_button.setObjectName("openOutputFolderButton")
        self.open_output_button.setAccessibleName("Open output folder")
        self.open_output_button.clicked.connect(self._open_output_folder)
        detail_layout.addWidget(self.open_output_button)

        self.open_output_action = QAction("Open Output Folder", self)
        self.open_output_action.setObjectName("openOutputFolderAction")
        self.open_output_action.setShortcut(QKeySequence("Ctrl+O"))
        self.open_output_action.setShortcutContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self.open_output_action.triggered.connect(self._open_output_folder)
        self.addAction(self.open_output_action)

        self.open_status_label = QLabel()
        self.open_status_label.setObjectName("openRequestStatus")
        self.open_status_label.setAccessibleName("Open request status")
        self.open_status_label.setWordWrap(True)
        detail_layout.addWidget(self.open_status_label)
        detail_layout.addStretch()

        detail_scroll.setWidget(self.detail_pane)
        self.splitter.addWidget(detail_scroll)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)

    def set_result(self, result: CurationRunResult) -> None:
        """Present an existing result while preserving its identity and order."""
        if not isinstance(result, CurationRunResult):
            raise TypeError("result must be a CurationRunResult")
        self._result = result
        self._reset_content()
        mode = "Dry run completed." if result.dry_run else "Run completed."
        self.state_label.setText(mode)
        self._populate_contact_sheet(result.selected_results)
        self._show_failed_analysis(result.failed_analysis_paths)
        self._show_duplicate_report(result.duplicate_report)
        self._show_integrity_report(result.integrity_report)
        self._show_artifacts(result.written_artifacts)
        self.counts_label.setText(
            f"Discovered: {result.discovered_count}\n"
            f"Analyzed: {result.analyzed_count}\n"
            f"Failed analysis: {len(result.failed_analysis_paths)}\n"
            f"Selected: {result.selected_count}"
        )
        self._configure_output_action(result.output_dir, result.dry_run)
        self._queue_thumbnails(result.selected_results)

    def set_empty_state(self, message: str) -> None:
        """Show a caller-supplied empty-state message."""
        if not isinstance(message, str) or not message.strip():
            raise ValueError("empty-state message must be a non-empty string")
        self._result = None
        self._reset_content()
        self.state_label.setText(message)

    def set_running_state(self) -> None:
        """Show that curation is currently running."""
        self._result = None
        self._reset_content()
        self.state_label.setText("Curation is running.")

    def set_failure(self, exception: Exception) -> None:
        """Show the type and message of the original failure object."""
        if not isinstance(exception, Exception):
            raise TypeError("exception must be an Exception")
        self._result = None
        self._reset_content()
        detail = str(exception).strip()
        description = type(exception).__name__
        if detail:
            description = f"{description}: {detail}"
        self.state_label.setText(
            f"Curation failed: {description}\nNo result was produced."
        )

    def clear(self) -> None:
        """Return the component to its initial empty state."""
        self.set_empty_state("No curation result is available.")

    def _reset_content(self) -> None:
        """Clear result-derived controls without touching source objects."""
        self._invalidate_thumbnails()
        self.counts_label.clear()
        self.contact_sheet.clear()
        for label in self._detail_labels.values():
            label.setText("Not selected")
        self.failed_analysis_label.setText("No failed analysis paths.")
        self.duplicate_report_label.setText("Duplicate detection not run.")
        self.integrity_report_label.setText("Integrity report absent.")
        self._clear_artifacts()
        self.open_status_label.clear()
        self._set_output_enabled(False)

    def _populate_contact_sheet(
        self,
        selected_results: tuple[ImageResult, ...],
    ) -> None:
        """Populate stable neutral-icon items in authoritative tuple order."""
        if not selected_results:
            self.state_label.setText(
                f"{self.state_label.text()} No images were selected."
            )
            return
        neutral_icon = self.style().standardIcon(
            QStyle.StandardPixmap.SP_FileIcon
        )
        for rank, image_result in enumerate(selected_results, start=1):
            path = str(image_result.path)
            item = QListWidgetItem(
                neutral_icon,
                f"{rank}. {Path(path).name}\n{image_result.score:.3f}",
            )
            item.setToolTip(path)
            item.setData(_PATH_ROLE, path)
            item.setData(
                Qt.ItemDataRole.AccessibleDescriptionRole,
                path,
            )
            item.setData(_RANK_ROLE, rank)
            self.contact_sheet.addItem(item)
        self.contact_sheet.setCurrentRow(0)

    def _invalidate_thumbnails(self) -> None:
        """Invalidate queued and cached presentation for the previous state."""
        self._thumbnail_generation += 1
        self._thumbnail_pending.clear()
        self._thumbnail_paths.clear()
        self._thumbnail_loader.clear_cache()

    def _queue_thumbnails(
        self,
        selected_results: tuple[ImageResult, ...],
    ) -> None:
        """Queue thumbnail requests in authoritative result order."""
        self._thumbnail_paths = {
            self._normalized_path(str(result.path))
            for result in selected_results
        }
        self._thumbnail_pending.extend(
            ThumbnailRequest(
                path=str(result.path),
                width=THUMBNAIL_WIDTH,
                height=THUMBNAIL_HEIGHT,
                generation=self._thumbnail_generation,
            )
            for result in selected_results
        )
        self._dispatch_next_thumbnail()

    def _dispatch_next_thumbnail(self) -> None:
        """Dispatch the next request only while the loader is idle."""
        if self._thumbnail_loader.is_busy or self._thumbnail_loader.is_stopping:
            return
        while self._thumbnail_pending:
            request = self._thumbnail_pending.popleft()
            if request.generation != self._thumbnail_generation:
                continue
            if self._thumbnail_loader.load(request):
                return

    @Slot(object)
    def _on_thumbnail_loaded(self, value: object) -> None:
        """Apply one current thumbnail result on the GUI thread."""
        if not isinstance(value, ThumbnailResult):
            return
        request = value.request
        normalized = self._normalized_path(request.path)
        is_current = (
            request.generation == self._thumbnail_generation
            and normalized in self._thumbnail_paths
        )
        if is_current:
            item = self._item_for_path(normalized)
            if item is not None:
                if value.image is not None:
                    item.setIcon(QPixmap.fromImage(value.image))
                else:
                    item.setIcon(
                        self.style().standardIcon(
                            QStyle.StandardPixmap.SP_MessageBoxWarning
                        )
                    )
                    message = value.error or "Thumbnail unavailable."
                    item.setToolTip(f"{request.path}\nThumbnail unavailable: {message}")
        else:
            self._thumbnail_loader.clear_cache()
        self._dispatch_next_thumbnail()

    def _item_for_path(self, normalized_path: str) -> QListWidgetItem | None:
        """Return the current contact-sheet item for a normalized path."""
        for index in range(self.contact_sheet.count()):
            item = self.contact_sheet.item(index)
            path = item.data(_PATH_ROLE)
            if isinstance(path, str) and self._normalized_path(path) == normalized_path:
                return item
        return None

    @staticmethod
    def _normalized_path(path: str) -> str:
        """Return a stable absolute path for thumbnail identity checks."""
        return str(Path(path).expanduser().resolve(strict=False))

    def shutdown_thumbnails(self) -> None:
        """Begin orderly, idempotent thumbnail-loader shutdown."""
        self._thumbnail_generation += 1
        self._thumbnail_pending.clear()
        self._thumbnail_paths.clear()
        self._thumbnail_loader.shutdown()

    @Slot(int)
    def _show_selected_details(self, row: int) -> None:
        """Display authoritative fields for the current selected image."""
        if self._result is None or row < 0:
            return
        if row >= len(self._result.selected_results):
            return
        image_result = self._result.selected_results[row]
        metrics = image_result.metrics
        values = {
            "filename": Path(image_result.path).name,
            "path": str(image_result.path),
            "rank": str(row + 1),
            "score": f"{image_result.score:.3f}",
            "passed": str(image_result.passed),
            "sharpness": f"{metrics.sharpness:.3f}",
            "exposure": f"{metrics.exposure:.3f}",
            "contrast": f"{metrics.contrast:.3f}",
            "dynamic_range": f"{metrics.dynamic_range:.3f}",
            "resolution": f"{metrics.resolution:.3f}",
            "clipping": f"{metrics.clipping:.3f}",
            "aesthetic": f"{metrics.aesthetic:.3f}",
        }
        for key, value in values.items():
            self._detail_labels[key].setText(value)

    def _show_failed_analysis(self, paths: tuple[str, ...]) -> None:
        """Display failed-analysis paths in their supplied order."""
        if paths:
            self.failed_analysis_label.setText(
                "Failed analysis paths:\n" + "\n".join(paths)
            )
        else:
            self.failed_analysis_label.setText("No failed analysis paths.")

    def _show_duplicate_report(
        self,
        report: ExactDuplicateReport | None,
    ) -> None:
        """Display duplicate counts and factual group membership."""
        if report is None:
            self.duplicate_report_label.setText(
                "Duplicate detection not run."
            )
            return
        lines = [
            "Duplicate report:",
            f"Input count: {report.input_count}",
            f"Fingerprinted count: {report.fingerprinted_count}",
            f"Fingerprint failures: {report.failed_count}",
            f"Unique content count: {report.unique_content_count}",
            f"Redundant duplicate count: {report.duplicate_file_count}",
            f"Duplicate-group count: {len(report.duplicate_groups)}",
        ]
        for group in report.duplicate_groups:
            lines.extend(self._duplicate_group_lines(group))
        if report.failed_paths:
            lines.append("Fingerprint failure paths:")
            lines.extend(report.failed_paths)
        self.duplicate_report_label.setText("\n".join(lines))

    @staticmethod
    def _duplicate_group_lines(group: ExactDuplicateGroup) -> list[str]:
        """Return factual text for one authoritative duplicate group."""
        return [
            f"Cluster ID: {group.cluster_id}",
            f"Representative path: {group.representative_path}",
            f"Member count: {len(group.member_paths)}",
            "Member paths:",
            *group.member_paths,
        ]

    def _show_integrity_report(
        self,
        report: IntegrityReport | None,
    ) -> None:
        """Display known and future finding codes without severity inference."""
        if report is None:
            self.integrity_report_label.setText("Integrity report absent.")
            return
        if not report.findings:
            self.integrity_report_label.setText(
                "Integrity report present: no findings."
            )
            return
        counts = Counter(finding.code for finding in report.findings)
        lines = ["Integrity report:"]
        for code in sorted(counts):
            lines.append(f"{code} count: {counts[code]}")
        for finding in report.findings:
            lines.append(f"{finding.code}: {finding.message}")
            lines.extend(finding.affected_paths)
        self.integrity_report_label.setText("\n".join(lines))

    def _clear_artifacts(self) -> None:
        """Remove artifact rows created for the previous result."""
        while self.artifacts_layout.count() > 1:
            item = self.artifacts_layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._artifact_buttons.clear()
        self.artifacts_empty_label.setVisible(True)
        self.artifacts_empty_label.setText("No artifacts were written.")

    def _show_artifacts(self, paths: tuple[str, ...]) -> None:
        """Show artifact facts and open actions in tuple order."""
        if not paths:
            return
        self.artifacts_empty_label.setVisible(False)
        for index, path_text in enumerate(paths):
            path = Path(path_text)
            kind = self._path_kind(path)
            row = QWidget()
            row.setObjectName(f"artifactRow{index}")
            row.setAccessibleName(f"Artifact {index + 1}")
            row_layout = QHBoxLayout(row)
            fact = QLabel(f"{path.name} | {kind} | {path_text}")
            fact.setObjectName(f"artifactFact{index}")
            fact.setAccessibleName(f"Artifact {index + 1} facts")
            fact.setWordWrap(True)
            button = QPushButton("Open")
            button.setObjectName(f"artifactOpenButton{index}")
            button.setAccessibleName(f"Open artifact {path.name}")
            button.setEnabled(kind != "Missing")
            button.clicked.connect(
                lambda checked=False, value=path_text: self._open_path(value)
            )
            row_layout.addWidget(fact, 1)
            row_layout.addWidget(button)
            self.artifacts_layout.addWidget(row)
            self._artifact_buttons.append(button)

    @staticmethod
    def _path_kind(path: Path) -> str:
        """Return the current filesystem kind without creating anything."""
        if path.is_file():
            return "File"
        if path.is_dir():
            return "Folder"
        return "Missing"

    def _configure_output_action(
        self,
        output_dir: str,
        dry_run: bool,
    ) -> None:
        """Enable output opening only for a written existing directory."""
        enabled = not dry_run and Path(output_dir).is_dir()
        self.open_output_button.setProperty("outputPath", output_dir)
        self.open_output_action.setProperty("outputPath", output_dir)
        self._set_output_enabled(enabled)

    def _set_output_enabled(self, enabled: bool) -> None:
        """Keep the button and Ctrl+O action enabled together."""
        self.open_output_button.setEnabled(enabled)
        self.open_output_action.setEnabled(enabled)

    @Slot()
    def _open_output_folder(self) -> None:
        """Request opening the current output directory."""
        path = self.open_output_button.property("outputPath")
        if isinstance(path, str) and Path(path).is_dir():
            self._open_path(path)

    def _open_path(self, path: str) -> None:
        """Request a local path open and report only the API result."""
        sent = QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        if sent:
            self.open_status_label.setText(
                f"Open request sent: {path}"
            )
        else:
            self.open_status_label.setText(
                f"Open request failed: {path}"
            )


__all__ = ["CurationResultsWidget", "THUMBNAIL_HEIGHT", "THUMBNAIL_WIDTH"]
