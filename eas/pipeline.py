"""Main image curation pipeline."""

import logging
import json
from pathlib import Path
from typing import List, Optional, NamedTuple
from PIL import Image
import numpy as np
from eas.vision import VisionAnalyzer
from eas.cache import EmbeddingCache

logger = logging.getLogger(__name__)


class ImageResult(NamedTuple):
    """Result for a curated image."""
    path: str
    score: float
    passed: bool


class ImageCurationPipeline:
    """Main pipeline for image curation."""

    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}

    def __init__(self, config: dict):
        """Initialize pipeline.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.analyzer = VisionAnalyzer(
            model_name=config.get("model_name", "ViT-B/32"),
            threshold=config.get("threshold", 0.5),
        )
        self.cache = EmbeddingCache(config.get("cache_dir", "./.eas_cache"), self.analyzer)
        self.top_n = config.get("top_n", 100)

    def discover_images(self, input_dir: str) -> List[Path]:
        """Discover images in directory.
        
        Args:
            input_dir: Input directory path
            
        Returns:
            List of image paths
        """
        input_path = Path(input_dir)
        if not input_path.exists():
            logger.error(f"Input directory not found: {input_dir}")
            return []

        images = []
        for ext in self.SUPPORTED_FORMATS:
            images.extend(input_path.glob(f"**/*{ext}"))
            images.extend(input_path.glob(f"**/*{ext.upper()}"))

        logger.info(f"Found {len(images)} images in {input_dir}")
        return images

    def process_images(self, image_paths: List[Path]) -> List[ImageResult]:
        """Process images and compute scores.
        
        Args:
            image_paths: List of image paths
            
        Returns:
            List of ImageResult objects
        """
        results = []
        for i, image_path in enumerate(image_paths, 1):
            try:
                logger.info(f"Processing {i}/{len(image_paths)}: {image_path.name}")
                score, passed = self.analyzer.analyze(Image.open(image_path), image_path.name)
                results.append(ImageResult(str(image_path), score, passed))
            except Exception as e:
                logger.error(f"Error processing {image_path}: {e}")
                results.append(ImageResult(str(image_path), 0.0, False))

        return results

    def select_top_n(self, results: List[ImageResult]) -> List[ImageResult]:
        """Select top N images by score.
        
        Args:
            results: List of all results
            
        Returns:
            Top N results
        """
        sorted_results = sorted(results, key=lambda x: x.score, reverse=True)
        top_results = sorted_results[: self.top_n]
        logger.info(f"Selected top {len(top_results)} images")
        return top_results

    def save_results(self, results: List[ImageResult], output_dir: str):
        """Save results to disk.
        
        Args:
            results: List of results
            output_dir: Output directory
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results_data = [
            {
                "path": str(result.path),
                "score": float(result.score),
                "passed": bool(result.passed),
            }
            for result in results
        ]
        results_file = output_path / "results.json"
        with open(results_file, "w") as f:
            json.dump(results_data, f, indent=2)

        logger.info(f"Saved results to {results_file}")

    def run(
        self,
        input_dir: str,
        output_dir: Optional[str] = None,
        dry_run: bool = False,
    ) -> List[ImageResult]:
        """Execute the complete curation pipeline.
        
        Args:
            input_dir: Input directory with images
            output_dir: Output directory for results
            dry_run: If True, don't save results
            
        Returns:
            List of top results
        """
        output_dir = output_dir or "./output"

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
                logger.info("Pipeline completed successfully")
            else:
                logger.info("Dry run completed")

            return top_results

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise
