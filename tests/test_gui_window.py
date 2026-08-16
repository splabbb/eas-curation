"""Focused tests for the functional curation window."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog

from eas.application import CurationRunRequest, CurationRunResult
from eas.gui.controller import CurationController
from eas.gui.window import CurationWindow
from eas.pipeline import ImageResult
from eas.vision import QualityMetrics


class FakeController(QObject):
    """Provide deterministic controller behavior without running curation."""

    started = Signal()
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.is_running = False
        self.reject_start = False
        self.requests: list[CurationRunRequest] = []

    def start(self, request: CurationRunRequest) -> bool:
        """Record one accepted request or reject it deterministically."""
        if self.is_running or self.reject_start:
            return False
        self.is_running = True
        self.requests.append(request)
        self.started.emit()
        return True

    def succeed(self, result: CurationRunResult) -> None:
        """Deliver success while leaving cleanup to finish()."""
        self.succeeded.emit(result)

    def fail(self, exception: Exception) -> None:
        """Deliver the original exception while leaving cleanup to finish()."""
        self.failed.emit(exception)

    def finish(self) -> None:
        """Complete cleanup and emit the lifecycle terminal signal."""
        self.is_running = False
        self.finished.emit()


@pytest.fixture
def window(
    qtbot: Any,
) -> tuple[CurationWindow, FakeController]:
    """Create a visible window backed by a fake controller."""
    controller = FakeController()
    created = CurationWindow(
        controller=cast(CurationController, controller)
    )
    created.input_directory.setText("/input")
    created.output_directory.setText("/output")
    created.model_name.setText("ViT-B/32")
    qtbot.addWidget(created)
    created.show()
    yield created, controller
    thread = created.results_workspace._thumbnail_loader.worker_thread
    try:
        running = thread.isRunning()
    except RuntimeError:
        running = False
    if running:
        created.results_workspace.shutdown_thumbnails()
        def stopped() -> bool:
            try:
                return not thread.isRunning()
            except RuntimeError:
                return True
        qtbot.waitUntil(stopped, timeout=3000)


def test_run_constructs_authoritative_request(
    window: tuple[CurationWindow, FakeController],
) -> None:
    created, controller = window
    created.input_directory.setText("  /input  ")
    created.output_directory.setText("  /output  ")
    created.top_n.setValue(7)
    created.threshold.setValue(0.75)
    created.model_name.setText("  model-x  ")
    created.deduplicate.setChecked(False)
    created.dry_run.setChecked(True)

    created.run_button.click()

    expected = CurationRunRequest(
        input_dir=Path("/input"),
        output_dir=Path("/output"),
        top_n=7,
        threshold=0.75,
        model_name="model-x",
        deduplicate=False,
        dry_run=True,
    )
    assert controller.requests == [expected]


@pytest.mark.parametrize(
    ("field_name", "expected_label"),
    [
        ("input_directory", "input directory"),
        ("output_directory", "output directory"),
        ("model_name", "model name"),
    ],
)
def test_blank_request_fields_are_rejected_without_controller_execution(
    field_name: str,
    expected_label: str,
    window: tuple[CurationWindow, FakeController],
) -> None:
    created, controller = window
    field = getattr(created, field_name)
    field.setText("   ")

    created.run_button.click()

    assert controller.requests == []
    assert created.status_text.text() == (
        f"Invalid request: {expected_label} must not be blank"
    )
    assert created.run_button.isEnabled() is True


def test_busy_indicator_tracks_active_lifecycle(
    window: tuple[CurationWindow, FakeController],
) -> None:
    created, controller = window
    assert created.busy_indicator.isVisible() is False

    created.run_button.click()

    assert created.busy_indicator.isVisible() is True
    assert created.run_button.isEnabled() is False

    controller.finish()

    assert created.busy_indicator.isVisible() is False
    assert created.run_button.isEnabled() is True


def test_legacy_result_widgets_are_removed(
    window: tuple[CurationWindow, FakeController],
) -> None:
    created, _ = window

    assert not hasattr(created, "result_summary")
    assert not hasattr(created, "artifact_paths")


def test_starting_new_run_clears_previous_result(
    window: tuple[CurationWindow, FakeController],
) -> None:
    created, controller = window

    created.run_button.click()
    controller.succeed(_result(dry_run=False))
    controller.finish()
    assert created.results_workspace.result is not None

    created.run_button.click()

    assert created.results_workspace.result is None
    assert created.status_text.text() == "Curation is running."
    controller.finish()


def test_controls_restore_only_after_finished(
    window: tuple[CurationWindow, FakeController],
) -> None:
    created, controller = window
    created.run_button.click()

    controller.succeed(_result(dry_run=False))

    assert created.run_button.isEnabled() is False
    assert created.input_directory.isEnabled() is False

    controller.finish()

    assert created.run_button.isEnabled() is True
    assert created.input_directory.isEnabled() is True


def test_success_with_written_artifacts_is_presented(
    window: tuple[CurationWindow, FakeController],
) -> None:
    created, controller = window
    created.run_button.click()

    controller.succeed(_result(dry_run=False))
    controller.finish()

    assert created.status_text.text() == "Curation completed."
    assert created.results_workspace.result is not None
    assert "Discovered: 3" in created.results_workspace.counts_label.text()
    assert "Analyzed: 2" in created.results_workspace.counts_label.text()
    assert "Failed analysis: 1" in created.results_workspace.counts_label.text()
    assert "Selected: 1" in created.results_workspace.counts_label.text()


def test_successful_dry_run_reports_no_artifacts(
    window: tuple[CurationWindow, FakeController],
) -> None:
    created, controller = window
    created.run_button.click()

    controller.succeed(_result(dry_run=True))
    controller.finish()

    assert created.status_text.text() == "Curation completed."
    assert created.results_workspace.artifacts_empty_label.text() == "No artifacts were written."


def test_failure_presentation_is_factual(
    window: tuple[CurationWindow, FakeController],
) -> None:
    created, controller = window
    error = ValueError("bad threshold")
    created.run_button.click()

    controller.fail(error)

    assert created.status_text.text() == (
        "Curation failed: ValueError: bad threshold"
    )
    assert "No result was produced." in created.results_workspace.state_label.text()
    assert created.run_button.isEnabled() is False

    controller.finish()
    assert created.run_button.isEnabled() is True


def test_controller_start_rejection_is_presented(
    window: tuple[CurationWindow, FakeController],
) -> None:
    created, controller = window
    controller.reject_start = True

    created.run_button.click()

    assert controller.requests == []
    assert created.status_text.text() == (
        "A curation run is already active."
    )
    assert created.run_button.isEnabled() is True


def test_browse_actions_set_input_and_output(
    monkeypatch: pytest.MonkeyPatch,
    window: tuple[CurationWindow, FakeController],
) -> None:
    created, _ = window
    choices = iter(["/chosen/input", "/chosen/output"])
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *args: next(choices),
    )

    created.input_browse.click()
    created.output_browse.click()

    assert created.input_directory.text() == "/chosen/input"
    assert created.output_directory.text() == "/chosen/output"


def test_close_is_rejected_while_run_is_active(
    window: tuple[CurationWindow, FakeController],
) -> None:
    created, _ = window
    created.run_button.click()

    assert created.close() is False
    assert created.isVisible() is True
    assert created.status_text.text() == (
        "Cannot close while curation is running."
    )


def test_close_is_deferred_until_thumbnail_shutdown(
    window: tuple[CurationWindow, FakeController],
    qtbot: Any,
) -> None:
    created, _ = window
    assert created.close() is False
    qtbot.waitUntil(lambda: not created.isVisible(), timeout=3000)

def _result(*, dry_run: bool) -> CurationRunResult:
    """Return a minimal factual result without loading OpenCLIP."""
    metrics = QualityMetrics(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7)
    analyzed = (
        ImageResult("/input/a.jpg", 0.8, True, metrics),
        ImageResult("/input/b.jpg", 0.7, False, metrics),
    )
    selected = (analyzed[0],)
    artifacts = () if dry_run else (
        str(Path("/output/results.json")),
        str(Path("/output/run_manifest.json")),
    )
    return CurationRunResult(
        input_dir=str(Path("/input")),
        output_dir=str(Path("/output")),
        dry_run=dry_run,
        discovered_paths=tuple(
            str(Path(name))
            for name in ("a.jpg", "b.jpg", "c.jpg")
        ),
        analyzed_results=analyzed,
        selected_results=selected,
        failed_analysis_paths=(str(Path("c.jpg")),),
        duplicate_report=None,
        integrity_report=None,
        written_artifacts=artifacts,
    )
