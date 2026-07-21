"""
EAS Pipeline - Main orchestration
"""

import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from datetime import datetime, timezone
import numpy as np
from PIL import Image
from tqdm import tqdm
from eas.config import SUPPORTED_FORMATS, BATCH_SIZE
from eas.vision import VisionAnalyzer
from eas.extractor import FeatureExtractor

logger = logging.getLogger(__name__)


@dataclass
class ImageResult:
    """Result data class for processed images."""
    path: Path
    score: float
    passed: bool
    embedding: Optional[np.ndarray] = None
    explanation: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": str(self.path),
            "score": float(self.score),
            "passed": bool(self.passed),
            "explanation": self.explanation,
            "metadata": self.metadata or {},
        }


class ImageCurationPipeline:
    """Main orchestration pipeline for automated image curation."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the curation pipeline."""
        config = config or {}
        self.top_n = config.get("top_n", 20)
        self.threshold = config.get("threshold", 0.45)
        self.model_name = config.get("model_name", "ViT-B-32")
        self.cache_dir = Path(config.get("cache_dir", ".eas_cache"))
        self.device = config.get("device", "auto")
        self.explain = config.get("explain", False)
        self.verbose = config.get("verbose", False)

        logger.info(f"Initialized Pipeline: top_n={self.top_n}, threshold={self.threshold}")

        self.analyzer = VisionAnalyzer(model_name=self.model_name, device=self.device, threshold=self.threshold)
        self.extractor = FeatureExtractor(cache_dir=self.cache_dir, model_name=self.model_name, device=self.device, threshold=self.threshold)

    def discover_images(self, input_dir: str) -> List[Path]:
        """Recursively discover all supported image files."""
        input_path = Path(input_dir)
        if not input_path.exists():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")

        image_paths = []
        for ext in SUPPORTED_FORMATS:
            image_paths.extend(input_path.rglob(f"*{ext}"))

        image_paths = sorted(set(image_paths))
        logger.info(f"Discovered {len(image_paths)} images in {input_path}")
        return image_paths

    def process_images(self, image_paths: List[Path]) -> List[ImageResult]:
        """Orchestrate full pipeline."""
        results = []
        logger.info(f"Starting processing of {len(image_paths)} images")

        with tqdm(total=len(image_paths), desc="Processing images") as pbar:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(self._process_single_image, img_path): img_path for img_path in image_paths}
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result:
                            results.append(result)
                    except Exception as e:
                        logger.error(f"Error: {e}")
                    pbar.update(1)

        results.sort(key=lambda r: r.score, reverse=True)
        logger.info(f"Completed: {len(results)} images analyzed")
        return results

    def _process_single_image(self, image_path: Path) -> Optional[ImageResult]:
        """Process a single image."""
        try:
            image = Image.open(image_path).convert("RGB")
            metadata = {"width": image.width, "height": image.height, "format": image.format}
            score, passed = self.analyzer.analyze(image, image_path.name)
            embedding = self.extractor.get_embeddings(image_path)

            return ImageResult(path=image_path, score=score, passed=passed, embedding=embedding, metadata=metadata)
        except Exception as e:
            logger.warning(f"Skipping {image_path}: {e}")
            return None

    def select_top_n(self, results: List[ImageResult], n: Optional[int] = None) -> List[ImageResult]:
        """Select top N images by score."""
        n = n or self.top_n
        top_results = results[:n]
        logger.info(f"Selected top {len(top_results)} images")
        return top_results

    def save_results(self, results: List[ImageResult], output_dir: Path, copy_images: bool = True):
        """Save results and optionally copy top images."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if copy_images:
            images_dir = output_dir / "top_images"
            images_dir.mkdir(parents=True, exist_ok=True)
            for i, result in enumerate(results, 1):
                try:
                    import shutil
                    dest_path = images_dir / f"{i:03d}_{result.path.name}"
                    shutil.copy2(result.path, dest_path)
                except Exception as e:
                    logger.warning(f"Failed to copy {result.path}: {e}")

        results_data = {
            "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "total_images": len(results)},
            "results": [r.to_dict() for r in results],
        }

        results_file = output_dir / "results.json"
        with open(results_file, "w") as f:
            json.dump(results_data, f, indent=2)

        logger.info(f"Saved results to {results_file}")

    def run(self, input_dir: str, output_dir: Optional[str] = None, dry_run: bool = False) -> List[ImageResult]:
        """Execute the complete curation pipeline."""
        output_dir = Path(output_dir or "./output")

        try:
            image_paths = self.discover_images(input_dir)
            if not image_paths:
                logger.warning(f"No images found in {input_dir}")
                return []

            all_results = self.process_images(image_paths)
            if not all_results:
                logger.warning("No images processed")
                return []

            top_results = self.select_top_n(all_results)

            if not dry_run:
                self.save_results(top_results, output_dir)
                logger.info(f"Pipeline completed successfully")
            else:
                logger.info(f"Dry run completed")

            return top_results

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise
