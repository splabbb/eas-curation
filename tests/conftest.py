"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from eas.vision import VisionAnalyzer


@pytest.fixture(autouse=True)
def disable_openclip(monkeypatch):
    """Prevent OpenCLIP loading during unit tests."""

    def _skip_model_load(self):
        self.model = None
        self.preprocess = None
        self.tokenizer = None
        self.text_features = None

    monkeypatch.setattr(
        VisionAnalyzer,
        "_load_model",
        _skip_model_load,
    )


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    """Create a valid sample image."""

    image_path = tmp_path / "sample.jpg"

    Image.new(
        "RGB",
        (256, 256),
        (128, 128, 128),
    ).save(image_path)

    return image_path


@pytest.fixture
def corrupt_image(tmp_path: Path) -> Path:
    """Create an invalid image file."""

    path = tmp_path / "corrupt.jpg"

    path.write_bytes(
        b"not-an-image"
    )

    return path
