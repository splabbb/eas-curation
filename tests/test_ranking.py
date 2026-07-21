"""Ranking and ordering tests."""

from __future__ import annotations

from eas.pipeline import ImageCurationPipeline
from eas.pipeline import ImageResult
from eas.vision import QualityMetrics


def make_result(
    path: str,
    score: float,
    passed: bool = True,
) -> ImageResult:
    """Create a reusable test result."""

    metrics = QualityMetrics(
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        0.5,
    )

    return ImageResult(
        path=path,
        score=score,
        passed=passed,
        metrics=metrics,
    )


def test_results_sorted_by_score() -> None:
    """Highest score should rank first."""

    pipeline = ImageCurationPipeline(
        {
            "top_n": 10,
            "threshold": 0.5,
        }
    )

    results = [
        make_result("c.jpg", 0.4),
        make_result("a.jpg", 0.9),
        make_result("b.jpg", 0.7),
    ]

    ranked = pipeline.select_top_n(results)

    assert ranked[0].score == 0.9
    assert ranked[1].score == 0.7
    assert ranked[2].score == 0.4


def test_tie_breaks_on_path() -> None:
    """Scores equal → path determines order."""

    pipeline = ImageCurationPipeline(
        {
            "top_n": 10,
            "threshold": 0.5,
        }
    )

    ranked = pipeline.select_top_n(
        [
            make_result("z.jpg", 0.8),
            make_result("a.jpg", 0.8),
        ]
    )

    assert ranked[0].path == "a.jpg"
