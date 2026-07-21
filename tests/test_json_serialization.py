"""Tests for JSON serialization."""

from __future__ import annotations

from eas.pipeline import ImageResult
from eas.vision import QualityMetrics


def test_image_result_to_dict() -> None:
    """Ensure ImageResult serializes safely."""
    metrics = QualityMetrics(
        sharpness=0.8,
        exposure=0.7,
        contrast=0.6,
        dynamic_range=0.5,
        resolution=0.9,
        clipping=1.0,
        aesthetic=0.75,
    )

    result = ImageResult(
        path="/tmp/image.jpg",
        score=0.81,
        passed=True,
        metrics=metrics,
    )

    data = result.to_dict()

    assert data["path"] == "/tmp/image.jpg"
    assert data["score"] == 0.81
    assert data["passed"] is True

    assert isinstance(
        data["metrics"],
        dict,
    )

    assert (
        data["metrics"]["sharpness"]
        == 0.8
    )
