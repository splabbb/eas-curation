"""FeatureExtractor tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from eas.extractor import FeatureExtractor


def test_feature_extractor_initialization(
    tmp_path: Path,
) -> None:
    """FeatureExtractor should initialize correctly."""

    FeatureExtractor(
        cache_dir=tmp_path,
    )


def test_feature_extractor_creates_cache_dir(
    tmp_path: Path,
) -> None:
    """Cache directory should be created."""

    extractor = FeatureExtractor(
        cache_dir=tmp_path,
    )

    assert extractor.model_cache_dir.exists()
