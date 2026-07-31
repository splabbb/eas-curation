"""Cache tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from eas.cache import EmbeddingCache


class DummyAnalyzer:
    """Analyzer stub."""

    model_name = "dummy"

    def get_embeddings(self, image):
        return np.array(
            [1.0, 2.0, 3.0],
            dtype=np.float32,
        )


def test_cache_directory_created(
    tmp_path: Path,
) -> None:

    cache = EmbeddingCache(
        str(tmp_path),
        DummyAnalyzer(),
    )

    assert cache.model_cache_dir.exists()


def test_cache_round_trip(
    tmp_path: Path,
) -> None:

    cache = EmbeddingCache(
        str(tmp_path),
        DummyAnalyzer(),
    )

    image_path = tmp_path / "image.jpg"

    embeddings = np.array(
        [1.0, 2.0, 3.0],
        dtype=np.float32,
    )

    cache_file = cache._get_cache_path(
        image_path,
    )

    cache._save_to_cache(
        embeddings,
        cache_file,
        image_path,
    )

    loaded = cache._load_from_cache(
        cache_file,
    )

    assert np.array_equal(
        embeddings,
        loaded,
    )
