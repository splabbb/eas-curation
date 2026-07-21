"""
EAS Feature Extractor - Embedding extraction with caching
"""

import logging
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
from PIL import Image
from eas.vision import VisionAnalyzer

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """Extracts and caches image embeddings."""

    def __init__(self, cache_dir: Path, model_name: str = "ViT-B-32", device: str = "auto", threshold: float = 0.45):
        """Initialize Feature Extractor."""
        self.cache_dir = Path(cache_dir)
        self.model_name = model_name
        self.model_cache_dir = self.cache_dir / model_name
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initialized FeatureExtractor with cache at {self.model_cache_dir}")
        self.analyzer = VisionAnalyzer(model_name=model_name, threshold=threshold)

    def get_embeddings(self, image_path: Path) -> np.ndarray:
        """Get embeddings, using cache if available."""
        cache_path = self._get_cache_path(image_path)

        if cache_path.exists():
            try:
                embeddings = self._load_from_cache(cache_path)
                logger.debug(f"Cache hit: {cache_path}")
                return embeddings
            except Exception as e:
                logger.warning(f"Cache load failed, regenerating: {e}")

        try:
            image = Image.open(image_path).convert("RGB")
            embeddings = self.analyzer.get_embeddings(image)
            self._save_to_cache(embeddings, cache_path, image_path)
            return embeddings
        except Exception as e:
            logger.error(f"Error extracting embeddings: {e}")
            return np.zeros(512, dtype=np.float32)

    def _get_cache_path(self, image_path: Path) -> Path:
        """Generate cache path using SHA256 hash."""
        path_hash = hashlib.sha256(str(image_path).encode()).hexdigest()
        return self.model_cache_dir / f"{path_hash}.json"

    def _load_from_cache(self, cache_path: Path) -> np.ndarray:
        """Load embeddings from cache."""
        with open(cache_path, "r") as f:
            cache_data = json.load(f)
        return np.array(cache_data["embeddings"], dtype=np.float32)

    def _save_to_cache(self, embeddings: np.ndarray, cache_path: Path, image_path: Path):
        """Save embeddings to cache."""
        try:
            cache_data = {
                "embeddings": embeddings.tolist(),
                "model": self.model_name,
                "image_path": str(image_path),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            with open(cache_path, "w") as f:
                json.dump(cache_data, f)
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
