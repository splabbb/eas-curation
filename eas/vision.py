"""Vision analysis module for image quality scoring."""

import logging
import numpy as np
from typing import Tuple
from PIL import Image
import torch
import open_clip

logger = logging.getLogger(__name__)


class VisionAnalyzer:
    """Analyzes images using CLIP embeddings for quality scoring."""

    def __init__(self, model_name: str = "ViT-B/32", threshold: float = 0.5):
        """Initialize vision analyzer with CLIP model.
        
        Args:
            model_name: CLIP model identifier
            threshold: Quality score threshold
        """
        self.model_name = model_name
        self.threshold = threshold
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._load_model()

    def _load_model(self):
        """Load CLIP model and preprocessing."""
        try:
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                self.model_name, pretrained="openai"
            )
            self.model = self.model.to(self.device)
            self.model.eval()
            logger.info(f"Loaded model {self.model_name} on {self.device}")
        except Exception as e:
            logger.error(f"Failed to load model {self.model_name}: {e}")
            raise

    def analyze(self, image: Image.Image, image_name: str = "image") -> Tuple[float, bool]:
        """Analyze an image and return score.
        
        Args:
            image: PIL Image object
            image_name: Name for logging
            
        Returns:
            Tuple of (score, passed_threshold)
        """
        try:
            score = self._compute_score(image)
            passed = score >= self.threshold
            logger.info(f"Technical analysis {image_name}: score={score:.3f} passed={passed}")
            return score, passed
        except Exception as e:
            logger.error(f"Error analyzing {image_name}: {e}")
            return 0.0, False

    def get_embeddings(self, image: Image.Image) -> np.ndarray:
        """Extract normalized CLIP embedding.
        
        Args:
            image: PIL Image object
            
        Returns:
            Normalized embedding vector
        """
        try:
            with torch.no_grad():
                image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)
                image_features = self.model.encode_image(image_tensor)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                embedding = image_features.squeeze(0).cpu().numpy()
            return embedding.astype(np.float32)
        except Exception as e:
            logger.error(f"Error extracting embeddings: {e}")
            return np.zeros(512, dtype=np.float32)

    def _compute_score(self, image: Image.Image) -> float:
        """Compute image quality score.
        
        Args:
            image: PIL Image object
            
        Returns:
            Quality score between 0 and 1
        """
        embedding = self.get_embeddings(image)
        magnitude = float(np.linalg.norm(embedding))
        score = np.clip(magnitude, 0.0, 1.0)
        return score
