"""OpenCLIP fallback tests."""

from __future__ import annotations

from PIL import Image

from eas.vision import VisionAnalyzer


def test_technical_only_mode() -> None:
    """Analyzer should work without CLIP."""

    analyzer = VisionAnalyzer(
        threshold=0.0,
    )

    analyzer.model = None
    analyzer.preprocess = None
    analyzer.text_features = None

    image = Image.new(
        "RGB",
        (128, 128),
        (128, 128, 128),
    )

    result = analyzer.analyze(
        image,
        "test.jpg",
    )

    assert 0.0 <= result.score <= 1.0
