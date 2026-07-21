"""Main image-curation pipeline."""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from eas.vision import QualityMetrics, VisionAnalyzer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImageResult:
    """JSON-safe result for one curated image."""

    path: str
    score: float
    passed: bool
    metrics: QualityMetrics

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        data = asdict(self)
        data["path"] = str(self.path)
        data["score"] = float(self.score)
        data["passed"] = bool(self.passed)
        data["metrics"] = self.metrics.to_dict()
        return data


class ImageCurationPipeline:
    """Discover, score, rank, and export images."""

    SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = dict(config)
        self.top_n = int(config.get("top_n", 100))
        if self.top_n < 1:
            raise ValueError("top_n must be at least 1")
        self.analyzer = VisionAnalyzer(
            model_name=str(config.get("model_name", "ViT-B/32")),
            threshold=float(config.get("threshold", 0.5)),
        )

    def discover_images(self, input_dir: str) -> list[Path]:
        """Recursively discover supported images in deterministic order."""
        root = Path(input_dir).expanduser().resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"Input directory not found: {root}")
        images = sorted(
            (path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in self.SUPPORTED_FORMATS),
            key=lambda path: str(path).casefold(),
        )
        logger.info("Found %d images in %s", len(images), root)
        return images

    def process_images(self, image_paths: list[Path]) -> list[ImageResult]:
        """Analyze images while ensuring source files are closed promptly."""
        results: list[ImageResult] = []
        for index, image_path in enumerate(image_paths, start=1):
            logger.info("Processing %d/%d: %s", index, len(image_paths), image_path.name)
            try:
                with Image.open(image_path) as source:
                    image = ImageOps.exif_transpose(source).convert("RGB")
                analysis = self.analyzer.analyze(image, image_path.name)
                results.append(ImageResult(str(image_path), analysis.score, analysis.passed, analysis.metrics))
            except Exception as exc:
                logger.exception("Error processing %s: %s", image_path, exc)
        return results

    def select_top_n(self, results: list[ImageResult]) -> list[ImageResult]:
        """Filter by threshold and return the highest-scoring results."""
        eligible = [result for result in results if result.passed]
        selected = sorted(eligible, key=lambda result: (-result.score, result.path.casefold()))[: self.top_n]
        logger.info("Selected %d of %d eligible images", len(selected), len(eligible))
        return selected

    def save_results(self, results: list[ImageResult], output_dir: str) -> None:
        """Write results atomically and copy selected images."""
        output = Path(output_dir).expanduser().resolve()
        selected_dir = output / "selected"
        selected_dir.mkdir(parents=True, exist_ok=True)

        exported: list[dict[str, Any]] = []
        for rank, result in enumerate(results, start=1):
            source = Path(result.path)
            destination = selected_dir / f"{rank:03d}_{source.name}"
            shutil.copy2(source, destination)
            item = result.to_dict()
            item["rank"] = rank
            item["exported_path"] = str(destination)
            exported.append(item)

        temporary = output / "results.json.tmp"
        target = output / "results.json"
        temporary.write_text(json.dumps(exported, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(target)
        logger.info("Saved results to %s", target)

    def run(self, input_dir: str, output_dir: str | None = None, dry_run: bool = False) -> list[ImageResult]:
        """Execute discovery, scoring, filtering, ranking, and optional export."""
        images = self.discover_images(input_dir)
        if not images:
            logger.warning("No images found in %s", input_dir)
            return []
        results = self.process_images(images)
        selected = self.select_top_n(results)
        if not dry_run:
            self.save_results(selected, output_dir or "./output")
            logger.info("Pipeline completed successfully")
        else:
            logger.info("Dry run completed")
        return selected
