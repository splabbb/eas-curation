from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import pytest
from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot

from eas.application import CurationRunRequest, CurationRunResult
from eas.gui.controller import CurationController


class _ReceiverProbe(QObject):
    """Record signal delivery and the receiving Qt thread."""

    received = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.value: object | None = None
        self.thread: QThread | None = None
        self.count = 0

    @Slot(object)
    def receive(self, value: object) -> None:
        """Record one signal delivery."""
        self.value = value
        self.thread = QThread.currentThread()
        self.count += 1
        self.received.emit()

    @Slot()
    def receive_without_value(self) -> None:
        """Record one argument-free signal delivery."""
        self.receive(None)


def _request() -> CurationRunRequest:
    return object()  # type: ignore[return-value]


def _result() -> CurationRunResult:
    return object()  # type: ignore[return-value]


def test_started_once_on_controller_thread(
    monkeypatch: pytest.MonkeyPatch,
    qtbot: Any,
) -> None:
    controller = CurationController()
    receiver = _ReceiverProbe()
    controller.started.connect(receiver.receive_without_value)
    monkeypatch.setattr("eas.gui.controller.run_curation", lambda request: _result())

    with qtbot.waitSignal(controller.finished):
        assert controller.start(_request()) is True

    assert receiver.count == 1
    assert receiver.thread == controller.thread()


def test_rejected_start_does_not_emit_started(
    monkeypatch: pytest.MonkeyPatch,
    qtbot: Any,
) -> None:
    controller = CurationController()
    entered = threading.Event()
    release = threading.Event()
    started_count: list[int] = []
    controller.started.connect(lambda: started_count.append(1))

    def fake_run(request: CurationRunRequest) -> CurationRunResult:
        entered.set()
        release.wait()
        return _result()

    monkeypatch.setattr("eas.gui.controller.run_curation", fake_run)

    assert controller.start(_request()) is True
    qtbot.waitUntil(entered.is_set)
    assert started_count == [1]
    assert controller.start(_request()) is False
    assert started_count == [1]

    release.set()
    with qtbot.waitSignal(controller.finished):
        pass


def test_success_invokes_once_and_preserves_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    qtbot: Any,
) -> None:
    controller = CurationController()
    request = _request()
    result = _result()
    calls: list[CurationRunRequest] = []
    execution_threads: list[QThread] = []
    receiver = _ReceiverProbe()
    controller.succeeded.connect(receiver.receive)

    def fake_run(actual: CurationRunRequest) -> CurationRunResult:
        calls.append(actual)
        execution_threads.append(QThread.currentThread())
        return result

    monkeypatch.setattr("eas.gui.controller.run_curation", fake_run)

    with qtbot.waitSignal(receiver.received):
        assert controller.start(request) is True

    assert calls == [request]
    assert calls[0] is request
    assert execution_threads[0] != controller.thread()
    assert receiver.thread == controller.thread()
    assert receiver.value is result


def test_failure_preserves_exception_and_receiver_thread(
    monkeypatch: pytest.MonkeyPatch,
    qtbot: Any,
) -> None:
    controller = CurationController()
    exception = ValueError("curation failed")
    execution_threads: list[QThread] = []
    receiver = _ReceiverProbe()
    controller.failed.connect(receiver.receive)

    def fake_run(request: CurationRunRequest) -> CurationRunResult:
        execution_threads.append(QThread.currentThread())
        raise exception

    monkeypatch.setattr("eas.gui.controller.run_curation", fake_run)

    with qtbot.waitSignal(receiver.received):
        assert controller.start(_request()) is True

    assert execution_threads[0] != controller.thread()
    assert receiver.thread == controller.thread()
    assert receiver.value is exception
    assert type(receiver.value) is ValueError
    assert str(receiver.value) == "curation failed"


@pytest.mark.parametrize("fails", [False, True])
def test_terminal_delivery_occurs_after_controller_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    qtbot: Any,
    fails: bool,
) -> None:
    controller = CurationController()
    observed: list[str] = []
    terminal_threads: list[QThread] = []

    def fake_run(request: CurationRunRequest) -> CurationRunResult:
        if fails:
            raise RuntimeError("failure")
        return _result()

    def receive_terminal(outcome: object) -> None:
        assert controller.is_running is False
        assert controller._thread is None
        assert controller._worker is None
        terminal_threads.append(QThread.currentThread())
        observed.append("terminal")

    monkeypatch.setattr("eas.gui.controller.run_curation", fake_run)
    controller.succeeded.connect(receive_terminal)
    controller.failed.connect(receive_terminal)
    controller.finished.connect(lambda: observed.append("finished"))

    with qtbot.waitSignal(controller.finished):
        assert controller.start(_request()) is True

    assert terminal_threads == [controller.thread()]
    assert observed == ["terminal", "finished"]


def test_busy_state_rejects_second_run_without_blocking_gui(
    monkeypatch: pytest.MonkeyPatch,
    qtbot: Any,
) -> None:
    controller = CurationController()
    entered = threading.Event()
    release = threading.Event()
    calls: list[CurationRunRequest] = []

    def fake_run(request: CurationRunRequest) -> CurationRunResult:
        calls.append(request)
        entered.set()
        release.wait()
        return _result()

    monkeypatch.setattr("eas.gui.controller.run_curation", fake_run)

    assert controller.is_running is False
    assert controller.start(_request()) is True
    assert controller.is_running is True
    qtbot.waitUntil(entered.is_set)
    assert controller.start(_request()) is False
    assert controller.is_running is True

    release.set()
    with qtbot.waitSignal(controller.finished):
        pass

    assert controller.is_running is False
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("implementation", "expected_terminal"),
    [
        (lambda request: _result(), "succeeded"),
        (lambda request: (_ for _ in ()).throw(RuntimeError("failure")), "failed"),
    ],
)
def test_terminal_signals_are_exclusive_and_finished_once(
    monkeypatch: pytest.MonkeyPatch,
    qtbot: Any,
    implementation: Callable[[CurationRunRequest], CurationRunResult],
    expected_terminal: str,
) -> None:
    controller = CurationController()
    observed: list[str] = []
    controller.succeeded.connect(lambda outcome: observed.append("succeeded"))
    controller.failed.connect(lambda exception: observed.append("failed"))
    controller.finished.connect(lambda: observed.append("finished"))
    monkeypatch.setattr("eas.gui.controller.run_curation", implementation)

    with qtbot.waitSignal(controller.finished):
        controller.start(_request())

    assert observed == [expected_terminal, "finished"]


def test_controller_runs_again_after_terminal_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    qtbot: Any,
) -> None:
    controller = CurationController()
    first = _request()
    second = _request()
    calls: list[CurationRunRequest] = []

    def fake_run(request: CurationRunRequest) -> CurationRunResult:
        calls.append(request)
        return _result()

    monkeypatch.setattr("eas.gui.controller.run_curation", fake_run)

    with qtbot.waitSignal(controller.finished):
        assert controller.start(first) is True
    assert controller.is_running is False

    with qtbot.waitSignal(controller.finished):
        assert controller.start(second) is True

    assert calls == [first, second]
    assert controller.is_running is False
