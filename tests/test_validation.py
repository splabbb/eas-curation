"""Validation tests."""

from __future__ import annotations

import pytest

from eas.pipeline import ImageCurationPipeline
from eas.vision import VisionAnalyzer


def test_invalid_top_n() -> None:
    """top_n must be at least 1."""

    with pytest.raises(ValueError):
        ImageCurationPipeline(
            {
                "top_n": 0,
            }
        )


@pytest.mark.parametrize(
    "threshold",
    [
        -0.1,
        1.1,
    ],
)
def test_invalid_threshold(
    threshold: float,
) -> None:
    """Threshold must be between 0 and 1."""

    with pytest.raises(ValueError):
        VisionAnalyzer(
            threshold=threshold,
        )
