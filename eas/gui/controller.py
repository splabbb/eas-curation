from __future__ import annotations

from typing import Literal, TypeAlias, cast

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot

from eas.application import CurationRunRequest, CurationRunResult, run_curation

_OutcomeKind: TypeAlias = Literal["success", "failure"]


class _CurationWorker(QObject):
    """Execute one curation request in its owning worker thread."""

    completed = Signal(str, object)

    def __init__(self, request: CurationRunRequest) -> None:
        """Store the immutable request without copying or transforming it."""
        super().__init__()
        self._request = request

    @Slot()
    def execute(self) -> None:
        """Execute curation exactly once and report its unmodified outcome."""
        try:
            result: CurationRunResult = run_curation(self._request)
        except Exception as exception:
            self.completed.emit("failure", exception)
        else:
            self.completed.emit("success", result)


class CurationController(QObject):
    """Own and coordinate one asynchronous curation execution at a time."""

    started = Signal()
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        """Create an idle controller owned by the current Qt thread."""
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _CurationWorker | None = None
        self._outcome_kind: _OutcomeKind | None = None
        self._outcome: CurationRunResult | Exception | None = None

    @property
    def is_running(self) -> bool:
        """Return whether a run is active or awaiting terminal delivery."""
        return self._thread is not None

    def start(self, request: CurationRunRequest) -> bool:
        """Start one run, returning ``False`` when another run is active."""
        if self.is_running:
            return False

        thread = QThread(self)
        worker = _CurationWorker(request)
        worker.moveToThread(thread)

        worker.completed.connect(
            self._capture_outcome,
            Qt.ConnectionType.QueuedConnection,
        )
        thread.started.connect(
            self._emit_started,
            Qt.ConnectionType.QueuedConnection,
        )
        thread.started.connect(
            worker.execute,
            Qt.ConnectionType.QueuedConnection,
        )
        thread.finished.connect(
            self._deliver_terminal,
            Qt.ConnectionType.QueuedConnection,
        )
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        self._outcome_kind = None
        self._outcome = None

        thread.start()
        return True

    @Slot()
    def _emit_started(self) -> None:
        """Announce an accepted run after Qt reports its thread started."""
        self.started.emit()

    @Slot(str, object)
    def _capture_outcome(self, kind: str, outcome: object) -> None:
        """Retain the worker outcome and request orderly thread shutdown."""
        if kind == "success":
            self._outcome_kind = "success"
            self._outcome = cast(CurationRunResult, outcome)
        elif kind == "failure":
            self._outcome_kind = "failure"
            self._outcome = cast(Exception, outcome)
        else:
            raise ValueError(f"Unknown worker outcome kind: {kind!r}")

        thread = self._thread
        if thread is not None:
            thread.quit()

    @Slot()
    def _deliver_terminal(self) -> None:
        """Deliver one terminal outcome after the worker thread terminates."""
        kind = self._outcome_kind
        outcome = self._outcome

        self._worker = None
        self._thread = None
        self._outcome_kind = None
        self._outcome = None

        if kind == "success":
            self.succeeded.emit(outcome)
        elif kind == "failure":
            self.failed.emit(outcome)
        else:
            raise RuntimeError("Worker thread ended without an outcome")

        self.finished.emit()
