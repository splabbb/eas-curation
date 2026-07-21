"""Threshold filtering tests."""

from __future__ import annotations

from eas.pipeline import ImageCurationPipeline
from eas.pipeline import ImageResult
from eas.vision import QualityMetrics


def make_result(
    score: float,
    passed: bool,
) -> ImageResult:
    """Create test result."""

    return ImageResult(
        path=f"{score}.jpg",
        score=score,
        passed=passed,
        metrics=QualityMetrics(
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            0.5,
        ),
    )


def test_failed_images_removed() -> None:
    """Only passed images should remain."""

    pipeline = ImageCurationPipeline(
        {
            "top_n": 10,
            "threshold": 0.5,
        }
    )

    results = [
        make_result(0.9, True),
        make_result(0.8, True),
        make_result(0.1, False),
    ]

    selected = pipeline.select_top_n(results)

    assert len(selected) == 2

    assert all(
        item.passed
        for item in selected
    )


def test_top_n_limit_applied() -> None:
    """Selection should honor top_n."""

    pipeline = ImageCurationPipeline(
        {
            "top_n": 2,
            "threshold": 0.5,
        }
    )

    results = [
        make_result(0.9, True),
        make_result(0.8, True),
        make_result(0.7, True),
    ]

    selected = pipeline.select_top_n(results)

    assert len(selected) == 2
