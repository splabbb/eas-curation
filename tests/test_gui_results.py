"""Focused tests for the factual curation results workspace."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from PySide6.QtCore import QThread, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QImage, QKeySequence, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QPushButton

from eas.application import CurationRunResult
from eas.clustering import ExactDuplicateGroup, ExactDuplicateReport
from eas.gui.results import CurationResultsWidget
from eas.gui.thumbnails import ThumbnailRequest, ThumbnailResult
from eas.integrity import (
    FindingCode,
    IntegrityFinding,
    IntegrityReport,
)
from eas.pipeline import ImageResult
from eas.vision import QualityMetrics


@pytest.fixture
def widget(qtbot: Any) -> CurationResultsWidget:
    """Create a visible results workspace with orderly loader cleanup."""
    created = CurationResultsWidget()
    qtbot.addWidget(created)
    created.show()
    yield created
    thread = created._thumbnail_loader.worker_thread
    if thread.isRunning():
        created.shutdown_thumbnails()

        def thread_stopped_or_deleted() -> bool:
            try:
                return not thread.isRunning()
            except RuntimeError:
                return True

        qtbot.waitUntil(thread_stopped_or_deleted, timeout=3000)


def test_public_states_and_clear(widget: CurationResultsWidget) -> None:
    assert widget.state_label.text() == "No curation result is available."
    widget.set_running_state()
    assert widget.state_label.text() == "Curation is running."
    error = ValueError("invalid source")
    widget.set_failure(error)
    assert widget.state_label.text() == (
        "Curation failed: ValueError: invalid source\n"
        "No result was produced."
    )
    widget.set_empty_state("Nothing to show.")
    assert widget.state_label.text() == "Nothing to show."
    widget.clear()
    assert widget.result is None
    assert widget.contact_sheet.count() == 0


def test_result_identity_order_rank_tooltip_and_first_selection(
    widget: CurationResultsWidget,
    tmp_path: Path,
) -> None:
    first = _image(tmp_path / "zeta.jpg", 0.8764, True, 0.1)
    second = _image(tmp_path / "alpha.jpg", 0.5432, False, 0.2)
    result = _result(tmp_path, selected=(first, second))
    before = result.selected_results

    widget.set_result(result)

    assert widget.result is result
    assert result.selected_results is before
    assert widget.contact_sheet.count() == 2
    assert widget.contact_sheet.item(0).text() == "1. zeta.jpg\n0.876"
    assert widget.contact_sheet.item(1).text() == "2. alpha.jpg\n0.543"
    assert widget.contact_sheet.item(0).toolTip() == first.path
    assert widget.contact_sheet.item(0).data(
        Qt.ItemDataRole.AccessibleDescriptionRole
    ) == first.path
    assert widget.contact_sheet.currentRow() == 0
    assert widget._detail_labels["filename"].text() == "zeta.jpg"
    assert widget._detail_labels["rank"].text() == "1"


def test_selection_transition_displays_every_authoritative_detail(
    widget: CurationResultsWidget,
    tmp_path: Path,
) -> None:
    selected = (
        _image(tmp_path / "one.jpg", 0.111, True, 0.1),
        _image(tmp_path / "two.jpg", 0.9876, False, 0.7),
    )
    widget.set_result(_result(tmp_path, selected=selected))

    widget.contact_sheet.setCurrentRow(1)

    expected = {
        "filename": "two.jpg",
        "path": str(tmp_path / "two.jpg"),
        "rank": "2",
        "score": "0.988",
        "passed": "False",
        "sharpness": "0.700",
        "exposure": "0.710",
        "contrast": "0.720",
        "dynamic_range": "0.730",
        "resolution": "0.740",
        "clipping": "0.750",
        "aesthetic": "0.760",
    }
    assert {
        key: label.text()
        for key, label in widget._detail_labels.items()
    } == expected


def test_zero_selection_and_dry_run_are_distinguished(
    widget: CurationResultsWidget,
    tmp_path: Path,
) -> None:
    widget.set_result(_result(tmp_path, selected=(), dry_run=True))
    assert widget.state_label.text() == (
        "Dry run completed. No images were selected."
    )
    assert widget.contact_sheet.count() == 0


def test_duplicate_report_absent(widget: CurationResultsWidget, tmp_path: Path) -> None:
    widget.set_result(_result(tmp_path, duplicate_report=None))
    assert widget.duplicate_report_label.text() == (
        "Duplicate detection not run."
    )


def test_duplicate_report_counts_groups_and_failures(
    widget: CurationResultsWidget,
    tmp_path: Path,
) -> None:
    group = ExactDuplicateGroup(
        cluster_id=4,
        sha256="a" * 64,
        representative_path="/images/a.jpg",
        member_paths=("/images/a.jpg", "/images/b.jpg"),
        size_bytes=10,
    )
    unique = ExactDuplicateGroup(
        cluster_id=5,
        sha256="b" * 64,
        representative_path="/images/c.jpg",
        member_paths=("/images/c.jpg",),
        size_bytes=20,
    )
    report = ExactDuplicateReport(
        input_count=4,
        fingerprinted_count=3,
        failed_count=1,
        unique_content_count=2,
        duplicate_file_count=1,
        groups=(group, unique),
        failed_paths=("/images/unreadable.jpg",),
    )
    widget.set_result(_result(tmp_path, duplicate_report=report))
    text = widget.duplicate_report_label.text()
    for expected in (
        "Input count: 4",
        "Fingerprinted count: 3",
        "Fingerprint failures: 1",
        "Unique content count: 2",
        "Redundant duplicate count: 1",
        "Duplicate-group count: 1",
        "Cluster ID: 4",
        "Representative path: /images/a.jpg",
        "Member count: 2",
        "/images/a.jpg",
        "/images/b.jpg",
        "/images/unreadable.jpg",
    ):
        assert expected in text


def test_integrity_absent_and_present_without_findings(
    widget: CurationResultsWidget,
    tmp_path: Path,
) -> None:
    widget.set_result(_result(tmp_path, integrity_report=None))
    assert widget.integrity_report_label.text() == "Integrity report absent."
    widget.set_result(
        _result(tmp_path, integrity_report=IntegrityReport(findings=()))
    )
    assert widget.integrity_report_label.text() == (
        "Integrity report present: no findings."
    )


def test_integrity_known_and_future_codes_are_factual(
    widget: CurationResultsWidget,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "eas.integrity._SUPPORTED_FINDING_CODES",
        frozenset(
            {
                FindingCode.EXACT_DUPLICATE,
                FindingCode.FINGERPRINT_FAILED,
                "future_fact",
            }
        ),
    )
    report = IntegrityReport(
        findings=(
            IntegrityFinding(
                code=FindingCode.EXACT_DUPLICATE,
                message="Files have identical content.",
                affected_paths=("/a.jpg", "/b.jpg"),
            ),
            IntegrityFinding(
                code=FindingCode.FINGERPRINT_FAILED,
                message="Fingerprint failed.",
                affected_paths=("/c.jpg",),
            ),
            IntegrityFinding(
                code="future_fact",
                message="Future factual message.",
                affected_paths=("/d.jpg",),
            ),
        )
    )
    widget.set_result(_result(tmp_path, integrity_report=report))
    text = widget.integrity_report_label.text()
    assert "exact_duplicate count: 1" in text
    assert "fingerprint_failed count: 1" in text
    assert "future_fact count: 1" in text
    assert "Future factual message." in text
    assert "/d.jpg" in text
    assert "severity" not in text.casefold()


def test_failed_analysis_paths_preserve_order(
    widget: CurationResultsWidget,
    tmp_path: Path,
) -> None:
    paths = ("/failed/z.jpg", "/failed/a.jpg")
    widget.set_result(_result(tmp_path, failed=paths))
    assert widget.failed_analysis_label.text().splitlines()[1:] == list(paths)


def test_artifact_facts_order_and_missing_action(
    widget: CurationResultsWidget,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "report.json"
    file_path.write_text("{}", encoding="utf-8")
    folder_path = tmp_path / "selected"
    folder_path.mkdir()
    missing_path = tmp_path / "missing.json"
    artifacts = (str(folder_path), str(file_path), str(missing_path))
    widget.set_result(_result(tmp_path, artifacts=artifacts))

    facts = [
        widget.findChild(QLabel, f"artifactFact{index}").text()
        for index in range(3)
    ]
    assert facts == [
        f"selected | Folder | {folder_path}",
        f"report.json | File | {file_path}",
        f"missing.json | Missing | {missing_path}",
    ]
    assert widget._artifact_buttons[0].isEnabled() is True
    assert widget._artifact_buttons[1].isEnabled() is True
    assert widget._artifact_buttons[2].isEnabled() is False


def test_artifact_open_reports_sent_and_failed(
    widget: CurationResultsWidget,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "report.json"
    artifact.write_text("{}", encoding="utf-8")
    calls: list[QUrl] = []

    def open_sent(url: QUrl) -> bool:
        calls.append(url)
        return True

    monkeypatch.setattr(QDesktopServices, "openUrl", open_sent)
    widget.set_result(_result(tmp_path, artifacts=(str(artifact),)))
    widget._artifact_buttons[0].click()
    assert calls[0].toLocalFile() == str(artifact)
    assert widget.open_status_label.text() == (
        f"Open request sent: {artifact}"
    )

    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: False)
    widget._artifact_buttons[0].click()
    assert widget.open_status_label.text() == (
        f"Open request failed: {artifact}"
    )


def test_output_folder_button_and_ctrl_o_follow_filesystem_state(
    widget: CurationResultsWidget,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )
    widget.set_result(_result(tmp_path))
    assert widget.open_output_button.isEnabled() is True
    assert widget.open_output_action.isEnabled() is True
    assert widget.open_output_action.shortcut() == QKeySequence("Ctrl+O")

    widget.setFocus()
    QTest.keyClick(widget, Qt.Key.Key_O, Qt.KeyboardModifier.ControlModifier)
    assert opened == [str(tmp_path)]

    missing = tmp_path / "absent"
    widget.set_result(_result(missing))
    assert widget.open_output_button.isEnabled() is False
    assert widget.open_output_action.isEnabled() is False


def test_keyboard_selection_updates_details(
    widget: CurationResultsWidget,
    tmp_path: Path,
) -> None:
    selected = (
        _image(tmp_path / "one.jpg", 0.1, True, 0.1),
        _image(tmp_path / "two.jpg", 0.2, True, 0.2),
    )
    widget.set_result(_result(tmp_path, selected=selected))
    widget.contact_sheet.setFocus()
    QTest.keyClick(widget.contact_sheet, Qt.Key.Key_Right)
    assert widget.contact_sheet.currentRow() == 1
    assert widget._detail_labels["filename"].text() == "two.jpg"


def test_stable_object_and_accessible_names(
    widget: CurationResultsWidget,
) -> None:
    controls = (
        widget,
        widget.state_label,
        widget.counts_label,
        widget.splitter,
        widget.contact_sheet,
        widget.detail_pane,
        widget.failed_analysis_label,
        widget.duplicate_report_label,
        widget.integrity_report_label,
        widget.open_output_button,
        widget.open_status_label,
    )
    for control in controls:
        assert control.objectName()
        assert control.accessibleName()


def test_invalid_public_inputs_are_rejected(widget: CurationResultsWidget) -> None:
    with pytest.raises(TypeError):
        widget.set_result(object())  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        widget.set_empty_state("   ")
    with pytest.raises(TypeError):
        widget.set_failure("failure")  # type: ignore[arg-type]



def test_exact_primary_counts(
    widget: CurationResultsWidget,
    tmp_path: Path,
) -> None:
    selected = (
        _image(tmp_path / "a.jpg", 0.8, True, 0.1),
        _image(tmp_path / "b.jpg", 0.7, True, 0.2),
    )
    result = CurationRunResult(
        input_dir=str(tmp_path / "input"),
        output_dir=str(tmp_path),
        dry_run=False,
        discovered_paths=("a.jpg", "b.jpg", "c.jpg"),
        analyzed_results=selected,
        selected_results=selected,
        failed_analysis_paths=("failed.jpg",),
        duplicate_report=None,
        integrity_report=None,
        written_artifacts=(),
    )
    widget.set_result(result)
    assert widget.counts_label.text().splitlines() == [
        "Discovered: 3",
        "Analyzed: 2",
        "Failed analysis: 1",
        "Selected: 2",
    ]


@pytest.mark.parametrize(
    ("transition", "expected_state"),
    [
        ("empty", "Nothing to show."),
        ("running", "Curation is running."),
        (
            "failure",
            "Curation failed: ValueError: invalid source\n"
            "No result was produced.",
        ),
    ],
)
def test_non_result_states_clear_previous_content(
    widget: CurationResultsWidget,
    tmp_path: Path,
    transition: str,
    expected_state: str,
) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}", encoding="utf-8")
    widget.set_result(
        _result(tmp_path, artifacts=(str(artifact),), failed=("failed.jpg",))
    )
    widget.open_status_label.setText("previous status")

    if transition == "empty":
        widget.set_empty_state("Nothing to show.")
    elif transition == "running":
        widget.set_running_state()
    else:
        widget.set_failure(ValueError("invalid source"))

    assert widget.result is None
    assert widget.state_label.text() == expected_state
    assert widget.counts_label.text() == ""
    assert widget.contact_sheet.count() == 0
    assert all(
        label.text() == "Not selected"
        for label in widget._detail_labels.values()
    )
    assert widget.failed_analysis_label.text() == "No failed analysis paths."
    assert widget.duplicate_report_label.text() == "Duplicate detection not run."
    assert widget.integrity_report_label.text() == "Integrity report absent."
    assert widget.artifacts_empty_label.isVisible() is True
    assert widget._artifact_buttons == []
    assert widget.open_status_label.text() == ""
    assert widget.open_output_button.isEnabled() is False
    assert widget.open_output_action.isEnabled() is False


def test_dry_run_disables_output_folder_action(
    widget: CurationResultsWidget,
    tmp_path: Path,
) -> None:
    widget.set_result(_result(tmp_path, dry_run=True))
    assert widget.open_output_button.isEnabled() is False
    assert widget.open_output_action.isEnabled() is False


@pytest.mark.parametrize(
    ("accepted", "prefix"),
    [
        (True, "Open request sent: "),
        (False, "Open request failed: "),
    ],
)
def test_output_folder_open_reports_api_result(
    widget: CurationResultsWidget,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    accepted: bool,
    prefix: str,
) -> None:
    calls: list[QUrl] = []

    def open_url(url: QUrl) -> bool:
        calls.append(url)
        return accepted

    monkeypatch.setattr(QDesktopServices, "openUrl", open_url)
    widget.set_result(_result(tmp_path))
    widget.open_output_button.click()

    assert len(calls) == 1
    assert calls[0].toLocalFile() == str(tmp_path)
    assert widget.open_status_label.text() == f"{prefix}{tmp_path}"


def test_thumbnail_placeholder_then_successful_icon_replacement(
    widget: CurationResultsWidget,
    qtbot: Any,
    tmp_path: Path,
) -> None:
    path = tmp_path / "preview.png"
    Image.new("RGB", (80, 40), "red").save(path)
    result = _result(tmp_path, selected=(_image(path, 0.8, True, 0.1),))

    widget.set_result(result)
    initial_cache_key = widget.contact_sheet.item(0).icon().cacheKey()

    qtbot.waitUntil(
        lambda: widget.contact_sheet.item(0).icon().cacheKey() != initial_cache_key,
        timeout=3000,
    )
    assert widget.result is result
    assert widget.contact_sheet.item(0).text() == "1. preview.png\n0.800"


def test_thumbnail_failure_keeps_successful_result_and_order(
    widget: CurationResultsWidget,
    qtbot: Any,
    tmp_path: Path,
) -> None:
    missing = _image(tmp_path / "missing.jpg", 0.8, True, 0.1)
    present_path = tmp_path / "present.png"
    Image.new("RGB", (20, 20), "blue").save(present_path)
    present = _image(present_path, 0.7, True, 0.2)
    result = _result(tmp_path, selected=(missing, present))

    widget.set_result(result)
    qtbot.waitUntil(
        lambda: "Thumbnail unavailable:" in widget.contact_sheet.item(0).toolTip(),
        timeout=3000,
    )
    qtbot.waitUntil(
        lambda: widget._thumbnail_loader.is_busy is False
        and not widget._thumbnail_pending,
        timeout=3000,
    )

    assert widget.result is result
    assert [widget.contact_sheet.item(i).text() for i in range(2)] == [
        "1. missing.jpg\n0.800",
        "2. present.png\n0.700",
    ]
    assert widget.state_label.text() == "Run completed."


def test_thumbnail_queue_dispatches_exactly_one_request(
    widget: CurationResultsWidget,
    tmp_path: Path,
) -> None:
    selected = tuple(
        _image(tmp_path / f"missing-{index}.jpg", 0.8 - index / 10, True, 0.1)
        for index in range(3)
    )
    widget.set_result(_result(tmp_path, selected=selected))
    assert widget._thumbnail_loader.is_busy is True
    assert len(widget._thumbnail_pending) == 2


def test_stale_generation_and_path_results_are_ignored(
    widget: CurationResultsWidget,
    tmp_path: Path,
) -> None:
    current_path = tmp_path / "current.jpg"
    current = _image(current_path, 0.8, True, 0.1)
    widget.set_result(_result(tmp_path, selected=(current,)))
    item = widget.contact_sheet.item(0)
    initial_key = item.icon().cacheKey()
    image = QImage(10, 10, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.red)

    old_request = ThumbnailRequest(
        str(current_path), 160, 120, widget._thumbnail_generation - 1
    )
    widget._on_thumbnail_loaded(ThumbnailResult(old_request, image, None, False))
    assert item.icon().cacheKey() == initial_key

    other_request = ThumbnailRequest(
        str(tmp_path / "other.jpg"), 160, 120, widget._thumbnail_generation
    )
    widget._on_thumbnail_loaded(ThumbnailResult(other_request, image, None, False))
    assert item.icon().cacheKey() == initial_key


def test_thumbnail_completion_preserves_current_detail_selection(
    widget: CurationResultsWidget,
    tmp_path: Path,
) -> None:
    first = _image(tmp_path / "first.jpg", 0.8, True, 0.1)
    second = _image(tmp_path / "second.jpg", 0.7, True, 0.2)
    widget.set_result(_result(tmp_path, selected=(first, second)))
    widget.contact_sheet.setCurrentRow(1)
    image = QImage(10, 10, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.blue)
    request = ThumbnailRequest(
        first.path, 160, 120, widget._thumbnail_generation
    )

    widget._on_thumbnail_loaded(ThumbnailResult(request, image, None, False))

    assert widget.contact_sheet.currentRow() == 1
    assert widget._detail_labels["filename"].text() == "second.jpg"


def test_non_result_state_invalidates_thumbnail_work(
    widget: CurationResultsWidget,
    tmp_path: Path,
) -> None:
    widget.set_result(_result(tmp_path))
    previous_generation = widget._thumbnail_generation
    widget.set_running_state()
    assert widget._thumbnail_generation == previous_generation + 1
    assert not widget._thumbnail_pending
    assert not widget._thumbnail_paths


def test_qpixmap_creation_receiver_runs_on_gui_thread(
    widget: CurationResultsWidget,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "current.jpg"
    widget.set_result(_result(tmp_path, selected=(_image(path, 0.8, True, 0.1),)))
    threads: list[QThread] = []
    original = QPixmap.fromImage

    def from_image(image: QImage, *args: Any, **kwargs: Any) -> QPixmap:
        threads.append(QThread.currentThread())
        return original(image, *args, **kwargs)

    monkeypatch.setattr(QPixmap, "fromImage", from_image)
    image = QImage(10, 10, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.green)
    request = ThumbnailRequest(path.as_posix(), 160, 120, widget._thumbnail_generation)
    widget._on_thumbnail_loaded(ThumbnailResult(request, image, None, False))
    assert threads == [widget.thread()]


def test_thumbnail_shutdown_is_exposed_and_idempotent(
    widget: CurationResultsWidget,
    qtbot: Any,
) -> None:
    with qtbot.waitSignal(widget._thumbnail_loader.stopped, timeout=3000):
        widget.shutdown_thumbnails()
        widget.shutdown_thumbnails()
    assert widget._thumbnail_loader.worker_thread.isFinished() is True

def _image(
    path: Path,
    score: float,
    passed: bool,
    base: float,
) -> ImageResult:
    metrics = QualityMetrics(
        sharpness=base,
        exposure=base + 0.01,
        contrast=base + 0.02,
        dynamic_range=base + 0.03,
        resolution=base + 0.04,
        clipping=base + 0.05,
        aesthetic=base + 0.06,
    )
    return ImageResult(
        path=str(path),
        score=score,
        passed=passed,
        metrics=metrics,
    )


def _result(
    output_dir: Path,
    *,
    selected: tuple[ImageResult, ...] | None = None,
    dry_run: bool = False,
    duplicate_report: ExactDuplicateReport | None = None,
    integrity_report: IntegrityReport | None = None,
    failed: tuple[str, ...] = (),
    artifacts: tuple[str, ...] = (),
) -> CurationRunResult:
    if selected is None:
        selected = (_image(output_dir / "selected.jpg", 0.8, True, 0.1),)
    return CurationRunResult(
        input_dir=str(output_dir / "input"),
        output_dir=str(output_dir),
        dry_run=dry_run,
        discovered_paths=tuple(item.path for item in selected),
        analyzed_results=selected,
        selected_results=selected,
        failed_analysis_paths=failed,
        duplicate_report=duplicate_report,
        integrity_report=integrity_report,
        written_artifacts=artifacts,
    )
