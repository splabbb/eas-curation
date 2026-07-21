"""Export tests."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from eas.pipeline import ImageCurationPipeline
from eas.pipeline import ImageResult
from eas.vision import QualityMetrics


def test_save_results_exports_images(
    tmp_path: Path,
) -> None:
    """Images should be copied and JSON written."""

    image_path = tmp_path / "image.jpg"

    Image.new(
        "RGB",
        (100, 100),
        (128, 128, 128),
    ).save(image_path)

    pipeline = ImageCurationPipeline(
        {
            "top_n": 10,
            "threshold": 0.5,
        }
    )

    result = ImageResult(
        path=str(image_path),
        score=0.9,
        passed=True,
        metrics=QualityMetrics(
            1,
            1,
            1,
            1,
            1,
            1,
            0.5,
        ),
    )

    output_dir = tmp_path / "output"

    pipeline.save_results(
        [result],
        str(output_dir),
    )

    results_file = output_dir / "results.json"

    assert results_file.exists()

    selected_dir = output_dir / "selected"

    exported_files = list(
        selected_dir.glob("*")
    )

    assert len(exported_files) == 1

    data = json.loads(
        results_file.read_text()
    )

    assert data[0]["rank"] == 1

    assert "exported_path" in data[0]
