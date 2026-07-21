"""Corrupt image handling tests."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from eas.pipeline import ImageCurationPipeline


def test_corrupt_images_are_skipped(
    tmp_path: Path,
) -> None:
    """Pipeline should continue when a file is unreadable."""

    valid = tmp_path / "valid.jpg"

    Image.new(
        "RGB",
        (100, 100),
        (128, 128, 128),
    ).save(valid)

    corrupt = tmp_path / "corrupt.jpg"

    corrupt.write_bytes(
        b"not-an-image"
    )

    pipeline = ImageCurationPipeline(
        {
            "top_n": 10,
            "threshold": 0.0,
        }
    )

    results = pipeline.process_images(
        [valid, corrupt]
    )

    assert len(results) == 1
