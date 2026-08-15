"""Focused tests for asynchronous thumbnail decoding."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from PySide6.QtCore import QThread
from PySide6.QtGui import QImage, QPixmap

from eas.gui.thumbnails import ThumbnailLoader, ThumbnailRequest, ThumbnailResult


@pytest.fixture
def loader(qtbot: Any) -> ThumbnailLoader:
    created = ThumbnailLoader()
    yield created
    if created.worker_thread.isRunning():
        with qtbot.waitSignal(created.stopped, timeout=3000):
            created.shutdown()


def test_request_and_result_are_frozen() -> None:
    request = ThumbnailRequest("image.jpg", 10, 20, 0)
    result = ThumbnailResult(request, None, "failed", False)
    with pytest.raises(FrozenInstanceError):
        request.width = 30  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.error = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    "values",
    [
        ("", 10, 10, 0),
        ("image.jpg", 0, 10, 0),
        ("image.jpg", 10, -1, 0),
        ("image.jpg", 10, 10, -1),
    ],
)
def test_request_validation(values: tuple[str, int, int, int]) -> None:
    with pytest.raises(ValueError):
        ThumbnailRequest(*values)


def test_successful_decode_and_request_identity(
    loader: ThumbnailLoader,
    qtbot: Any,
    sample_image: Path,
) -> None:
    request = ThumbnailRequest(str(sample_image), 100, 80, 7)
    with qtbot.waitSignal(loader.loaded, timeout=3000) as blocker:
        assert loader.load(request) is True
    result = blocker.args[0]
    assert result.request is request
    assert result.request.generation == 7
    assert result.image is not None
    assert result.image.isNull() is False
    assert result.error is None
    assert result.from_cache is False


@pytest.mark.parametrize("kind", ["missing", "corrupt"])
def test_invalid_source_emits_one_factual_failure(
    loader: ThumbnailLoader,
    qtbot: Any,
    tmp_path: Path,
    corrupt_image: Path,
    kind: str,
) -> None:
    path = tmp_path / "missing.jpg" if kind == "missing" else corrupt_image
    request = ThumbnailRequest(str(path), 80, 80, 0)
    emissions: list[ThumbnailResult] = []
    loader.loaded.connect(emissions.append)
    with qtbot.waitSignal(loader.loaded, timeout=3000):
        assert loader.load(request) is True
    assert len(emissions) == 1
    assert emissions[0].image is None
    assert emissions[0].error


def test_aspect_ratio_is_preserved(
    loader: ThumbnailLoader,
    qtbot: Any,
    tmp_path: Path,
) -> None:
    path = tmp_path / "wide.png"
    Image.new("RGB", (400, 200), "red").save(path)
    with qtbot.waitSignal(loader.loaded, timeout=3000) as blocker:
        loader.load(ThumbnailRequest(str(path), 100, 100, 0))
    image = blocker.args[0].image
    assert image is not None
    assert (image.width(), image.height()) == (100, 50)


def test_exif_orientation_is_applied(
    loader: ThumbnailLoader,
    qtbot: Any,
    tmp_path: Path,
) -> None:
    path = tmp_path / "oriented.jpg"
    source = Image.new("RGB", (40, 20), "blue")
    exif = source.getexif()
    exif[274] = 6
    source.save(path, exif=exif)
    with qtbot.waitSignal(loader.loaded, timeout=3000) as blocker:
        loader.load(ThumbnailRequest(str(path), 100, 100, 0))
    image = blocker.args[0].image
    assert image is not None
    assert image.height() > image.width()


def test_decode_runs_off_gui_and_delivery_runs_on_gui_thread(
    loader: ThumbnailLoader,
    qtbot: Any,
    sample_image: Path,
) -> None:
    delivered_threads: list[QThread] = []
    loader.loaded.connect(lambda result: delivered_threads.append(QThread.currentThread()))
    with qtbot.waitSignal(loader.loaded, timeout=3000):
        loader.load(ThumbnailRequest(str(sample_image), 40, 40, 0))
    assert loader.last_decode_thread is loader.worker_thread
    assert loader.last_decode_thread is not loader.thread()
    assert delivered_threads == [loader.thread()]


def test_failure_does_not_stop_later_success(
    loader: ThumbnailLoader,
    qtbot: Any,
    sample_image: Path,
    corrupt_image: Path,
) -> None:
    with qtbot.waitSignal(loader.loaded, timeout=3000) as first:
        loader.load(ThumbnailRequest(str(corrupt_image), 50, 50, 0))
    assert first.args[0].error
    with qtbot.waitSignal(loader.loaded, timeout=3000) as second:
        assert loader.load(ThumbnailRequest(str(sample_image), 50, 50, 0)) is True
    assert second.args[0].image is not None


def test_only_one_request_is_accepted_while_busy(
    loader: ThumbnailLoader,
    qtbot: Any,
    sample_image: Path,
) -> None:
    first = ThumbnailRequest(str(sample_image), 50, 50, 0)
    second = ThumbnailRequest(str(sample_image), 40, 40, 1)
    with qtbot.waitSignal(loader.loaded, timeout=3000):
        assert loader.load(first) is True
        assert loader.is_busy is True
        assert loader.load(second) is False
    assert loader.is_busy is False


def test_cache_hit_and_clear_cache(
    loader: ThumbnailLoader,
    qtbot: Any,
    sample_image: Path,
) -> None:
    request = ThumbnailRequest(str(sample_image), 60, 60, 0)
    with qtbot.waitSignal(loader.loaded, timeout=3000) as first:
        loader.load(request)
    assert first.args[0].from_cache is False
    with qtbot.waitSignal(loader.loaded, timeout=3000) as second:
        loader.load(request)
    assert second.args[0].from_cache is True
    loader.clear_cache()
    with qtbot.waitSignal(loader.loaded, timeout=3000) as third:
        loader.load(request)
    assert third.args[0].from_cache is False


def test_cache_key_includes_dimensions(
    loader: ThumbnailLoader,
    qtbot: Any,
    sample_image: Path,
) -> None:
    with qtbot.waitSignal(loader.loaded, timeout=3000):
        loader.load(ThumbnailRequest(str(sample_image), 60, 60, 0))
    with qtbot.waitSignal(loader.loaded, timeout=3000) as blocker:
        loader.load(ThumbnailRequest(str(sample_image), 61, 60, 0))
    assert blocker.args[0].from_cache is False


def test_lru_cache_is_bounded(
    loader: ThumbnailLoader,
    qtbot: Any,
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "image-0.png"
    for index in range(65):
        path = tmp_path / f"image-{index}.png"
        Image.new("RGB", (8, 8), (index, 0, 0)).save(path)
        with qtbot.waitSignal(loader.loaded, timeout=3000):
            loader.load(ThumbnailRequest(str(path), 8, 8, 0))
    with qtbot.waitSignal(loader.loaded, timeout=3000) as blocker:
        loader.load(ThumbnailRequest(str(first_path), 8, 8, 0))
    assert blocker.args[0].from_cache is False


def test_idle_shutdown_is_orderly_and_idempotent(
    loader: ThumbnailLoader,
    qtbot: Any,
) -> None:
    with qtbot.waitSignal(loader.stopped, timeout=3000):
        loader.shutdown()
        loader.shutdown()
    assert loader.worker_thread.isFinished() is True
    assert loader.is_stopping is True


def test_active_shutdown_finishes_request_then_stops(
    loader: ThumbnailLoader,
    qtbot: Any,
    sample_image: Path,
) -> None:
    events: list[str] = []
    loader.loaded.connect(lambda result: events.append("loaded"))
    loader.stopped.connect(lambda: events.append("stopped"))
    assert loader.load(ThumbnailRequest(str(sample_image), 50, 50, 0)) is True
    with qtbot.waitSignal(loader.stopped, timeout=3000):
        loader.shutdown()
    assert events == ["loaded", "stopped"]
    assert loader.worker_thread.isFinished() is True


def test_worker_source_uses_no_qpixmap_or_forced_termination() -> None:
    source = Path(__file__).parents[1] / "eas" / "gui" / "thumbnails.py"
    text = source.read_text(encoding="utf-8")
    assert "QPixmap" not in text
    assert ".terminate(" not in text
    assert ".wait(" not in text


def test_qpixmap_remains_available_only_to_gui_consumers() -> None:
    image = QImage(2, 2, QImage.Format.Format_RGB32)
    pixmap = QPixmap.fromImage(image)
    assert pixmap.isNull() is False
