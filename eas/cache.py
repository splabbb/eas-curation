"""Caching module for image embeddings."""

import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """Manages caching of image embeddings."""

    def __init__(self, cache_dir: str, analyzer):
        """Initialize cache.
        
        Args:
            cache_dir: Directory for cache storage
            analyzer: Vision analyzer for computing embeddings
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model_cache_dir = self.cache_dir / "models"
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)
        self.analyzer = analyzer
        self.model_name = analyzer.model_name

    def get_embeddings(self, image_path: Path) -> np.ndarray:
        """Get or compute embeddings for image.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Embedding vector
        """
        cache_path = self._get_cache_path(image_path)

        if cache_path.exists():
            try:
                return self._load_from_cache(cache_path)
            except Exception as e:
                logger.warning(f"Failed to load cache for {image_path}: {e}")

        try:
            image = Image.open(image_path).convert("RGB")
            embeddings = self.analyzer.get_embeddings(image)
            self._save_to_cache(embeddings, cache_path, image_path)
            return embeddings
        except Exception as e:
            logger.error(f"Error extracting embeddings: {e}")
            return np.zeros(512, dtype=np.float32)

    def _get_cache_path(self, image_path: Path) -> Path:
        """Generate cache path using SHA256 hash.
        
        Args:
            image_path: Path to image
            
        Returns:
            Cache file path
        """
        path_hash = hashlib.sha256(str(image_path).encode()).hexdigest()
        return self.model_cache_dir / f"{path_hash}.json"

    def _load_from_cache(self, cache_path: Path) -> np.ndarray:
        """Load embeddings from cache.
        
        Args:
            cache_path: Path to cache file
            
        Returns:
            Embedding vector
        """
        with open(cache_path, "r") as f:
            cache_data = json.load(f)
        return np.array(cache_data["embeddings"], dtype=np.float32)

    def _save_to_cache(self, embeddings: np.ndarray, cache_path: Path, image_path: Path):
        """Save embeddings to cache.
        
        Args:
            embeddings: Embedding vector
            cache_path: Path to save cache
            image_path: Path to original image
        """
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
