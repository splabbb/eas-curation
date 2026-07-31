"""Image discovery tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from eas.pipeline import ImageCurationPipeline


def test_discover_images_returns_supported_files(
    tmp_path: Path,
) -> None:
    """Only supported image formats should be returned."""

    Image.new("RGB", (10, 10)).save(tmp_path / "a.jpg")
    Image.new("RGB", (10, 10)).save(tmp_path / "b.png")

    (tmp_path / "notes.txt").write_text("hello")

    pipeline = ImageCurationPipeline({"top_n": 10})

    results = pipeline.discover_images(str(tmp_path))

    assert len(results) == 2


def test_discover_images_missing_directory() -> None:
    """Missing directory should raise."""

    pipeline = ImageCurationPipeline({"top_n": 10})

    with pytest.raises(NotADirectoryError):
        pipeline.discover_images("/definitely/not/here")


def test_run_empty_directory(
    tmp_path: Path,
) -> None:
    """Empty directory should return empty results."""

    pipeline = ImageCurationPipeline({"top_n": 10})

    results = pipeline.run(
        input_dir=str(tmp_path),
        dry_run=True,
    )

    assert results == []
