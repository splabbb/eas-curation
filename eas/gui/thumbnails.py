"""Asynchronous, cached thumbnail decoding for the Qt results workspace."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QImage, QImageReader

_CACHE_LIMIT = 64


@dataclass(frozen=True)
class ThumbnailRequest:
    """Describe one thumbnail decode request."""

    path: str
    width: int
    height: int
    generation: int

    def __post_init__(self) -> None:
        """Validate the request at its public boundary."""
        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError("path must be a non-empty string")
        if not isinstance(self.width, int) or isinstance(self.width, bool) or self.width <= 0:
            raise ValueError("width must be a positive integer")
        if not isinstance(self.height, int) or isinstance(self.height, bool) or self.height <= 0:
            raise ValueError("height must be a positive integer")
        if (
            not isinstance(self.generation, int)
            or isinstance(self.generation, bool)
            or self.generation < 0
        ):
            raise ValueError("generation must be a nonnegative integer")


@dataclass(frozen=True)
class ThumbnailResult:
    """Contain the exclusive outcome of one thumbnail request."""

    request: ThumbnailRequest
    image: QImage | None
    error: str | None
    from_cache: bool

    def __post_init__(self) -> None:
        """Require exactly one success or failure payload."""
        if not isinstance(self.request, ThumbnailRequest):
            raise TypeError("request must be a ThumbnailRequest")
        if self.image is None and not self.error:
            raise ValueError("a failed result requires an error")
        if self.image is not None and self.error is not None:
            raise ValueError("a successful result cannot contain an error")
        if self.image is not None and self.image.isNull():
            raise ValueError("a successful result requires a non-null image")


class _ThumbnailWorker(QObject):
    """Decode requests inside one dedicated Qt worker thread."""

    completed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.last_execution_thread: QThread | None = None

    @Slot(object)
    def decode(self, request: object) -> None:
        """Decode and scale one request, emitting exactly one result."""
        self.last_execution_thread = QThread.currentThread()
        if not isinstance(request, ThumbnailRequest):
            return
        try:
            source_path = Path(request.path)
            if not source_path.is_file():
                self.completed.emit(
                    ThumbnailResult(
                        request=request,
                        image=None,
                        error=f"Image file not found: {request.path}",
                        from_cache=False,
                    )
                )
                return

            reader = QImageReader(request.path)
            reader.setAutoTransform(True)
            source_size = reader.size()
            if source_size.isValid():
                source_size.scale(
                    request.width,
                    request.height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                )
                reader.setScaledSize(source_size)
            image = reader.read()
            if image.isNull():
                message = reader.errorString().strip() or "Image decoding failed."
                result = ThumbnailResult(request, None, message, False)
            else:
                if image.width() > request.width or image.height() > request.height:
                    image = image.scaled(
                        request.width,
                        request.height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                result = ThumbnailResult(request, image, None, False)
        except Exception as exc:
            message = str(exc).strip() or type(exc).__name__
            result = ThumbnailResult(request, None, message, False)
        self.completed.emit(result)


class ThumbnailLoader(QObject):
    """Schedule one-at-a-time thumbnail decoding with a bounded memory cache."""

    loaded = Signal(object)
    stopped = Signal()
    _decode_requested = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._busy = False
        self._stopping = False
        self._stopped = False
        self._cache: OrderedDict[tuple[str, int, int], QImage] = OrderedDict()
        self._worker = _ThumbnailWorker()
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._decode_requested.connect(
            self._worker.decode,
            Qt.ConnectionType.QueuedConnection,
        )
        self._worker.completed.connect(
            self._on_completed,
            Qt.ConnectionType.QueuedConnection,
        )
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    @property
    def is_busy(self) -> bool:
        """Return whether one decode or queued cache delivery is active."""
        return self._busy

    @property
    def is_stopping(self) -> bool:
        """Return whether orderly shutdown has been requested."""
        return self._stopping

    @property
    def worker_thread(self) -> QThread:
        """Return the dedicated worker thread for lifecycle observation."""
        return self._thread

    @property
    def last_decode_thread(self) -> QThread | None:
        """Return the thread that most recently executed worker decoding."""
        return self._worker.last_execution_thread

    def load(self, request: ThumbnailRequest) -> bool:
        """Accept one request unless loading or shutdown is already active."""
        if not isinstance(request, ThumbnailRequest):
            raise TypeError("request must be a ThumbnailRequest")
        if self._busy or self._stopping or self._stopped:
            return False
        self._busy = True
        key = self._cache_key(request)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            result = ThumbnailResult(request, QImage(cached), None, True)
            QTimer.singleShot(0, lambda value=result: self._deliver_cached(value))
        else:
            self._decode_requested.emit(request)
        return True

    def clear_cache(self) -> None:
        """Remove every in-memory thumbnail entry."""
        self._cache.clear()

    def shutdown(self) -> None:
        """Begin orderly, non-blocking shutdown."""
        if self._stopping or self._stopped:
            return
        self._stopping = True
        if not self._busy:
            self._thread.quit()

    @Slot(object)
    def _on_completed(self, result: object) -> None:
        """Deliver a worker outcome on the loader's owning thread."""
        if not isinstance(result, ThumbnailResult):
            return
        if result.image is not None:
            key = self._cache_key(result.request)
            self._cache[key] = QImage(result.image)
            self._cache.move_to_end(key)
            while len(self._cache) > _CACHE_LIMIT:
                self._cache.popitem(last=False)
        self._busy = False
        self.loaded.emit(result)
        if self._stopping:
            self._thread.quit()

    def _deliver_cached(self, result: ThumbnailResult) -> None:
        """Deliver one cache hit through the loader's event loop."""
        if not self._busy:
            return
        self._busy = False
        self.loaded.emit(result)
        if self._stopping:
            self._thread.quit()

    @Slot()
    def _on_thread_finished(self) -> None:
        """Publish shutdown completion only after the thread has finished."""
        self._busy = False
        self._stopping = True
        self._stopped = True
        self.stopped.emit()

    @staticmethod
    def _cache_key(request: ThumbnailRequest) -> tuple[str, int, int]:
        """Return the normalized result-local memory-cache key."""
        normalized = str(Path(request.path).expanduser().resolve(strict=False))
        return normalized, request.width, request.height


__all__ = ["ThumbnailLoader", "ThumbnailRequest", "ThumbnailResult"]
