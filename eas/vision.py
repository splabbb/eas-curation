"""Vision analysis for technical and semantic image-quality scoring."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from PIL import Image, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

try:
    import torch
    import open_clip
except ImportError:  # Graceful technical-only fallback.
    torch = None  # type: ignore[assignment]
    open_clip = None  # type: ignore[assignment]


@dataclass(frozen=True)
class QualityMetrics:
    """Normalized image-quality metrics in the inclusive range 0..1."""

    sharpness: float
    exposure: float
    contrast: float
    dynamic_range: float
    resolution: float
    clipping: float
    aesthetic: float

    def to_dict(self) -> dict[str, float]:
        """Return metrics as JSON-safe Python floats."""
        return {key: float(value) for key, value in asdict(self).items()}


@dataclass(frozen=True)
class AnalysisResult:
    """Complete analysis result for one image."""

    score: float
    passed: bool
    metrics: QualityMetrics


class VisionAnalyzer:
    """Score images using technical heuristics and optional CLIP semantics."""

    POSITIVE_PROMPTS = (
        "a high quality sharp well exposed professional photograph",
        "a visually pleasing photograph with good composition and lighting",
    )
    NEGATIVE_PROMPTS = (
        "a blurry badly exposed low quality photograph",
        "a photograph with poor lighting low contrast and technical defects",
    )

    def __init__(self, model_name: str = "ViT-B/32", threshold: float = 0.5) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        self.model_name = model_name
        self.threshold = float(threshold)
        self.device = "cpu"
        self.model: Any | None = None
        self.preprocess: Any | None = None
        self.tokenizer: Any | None = None
        self.text_features: Any | None = None
        self._load_model()

    def _load_model(self) -> None:
        """Load CLIP, or continue with technical-only scoring if unavailable."""
        if torch is None or open_clip is None:
            logger.warning("OpenCLIP is unavailable; using technical-only scoring")
            return
        try:
            if torch.cuda.is_available():
                self.device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.device = "mps"
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                self.model_name, pretrained="openai"
            )
            self.model = self.model.to(self.device).eval()
            self.tokenizer = open_clip.get_tokenizer(self.model_name)
            prompts = list(self.POSITIVE_PROMPTS + self.NEGATIVE_PROMPTS)
            with torch.no_grad():
                tokens = self.tokenizer(prompts).to(self.device)
                features = self.model.encode_text(tokens)
                self.text_features = features / features.norm(dim=-1, keepdim=True).clamp_min(1e-12)
            logger.info("Loaded model %s on %s", self.model_name, self.device)
        except Exception as exc:
            logger.warning("CLIP unavailable (%s); using technical-only scoring", exc)
            self.model = self.preprocess = self.tokenizer = self.text_features = None

    def analyze(self, image: Image.Image, image_name: str = "image") -> AnalysisResult:
        """Analyze one image and return its score, decision, and components."""
        try:
            rgb = ImageOps.exif_transpose(image).convert("RGB")
            metrics = self._compute_metrics(rgb)
            technical = (
                0.30 * metrics.sharpness
                + 0.22 * metrics.exposure
                + 0.16 * metrics.contrast
                + 0.12 * metrics.dynamic_range
                + 0.10 * metrics.resolution
                + 0.10 * metrics.clipping
            )
            if self.model is not None:
                score = 0.75 * technical + 0.25 * metrics.aesthetic
            else:
                score = technical
            score = float(np.clip(score, 0.0, 1.0))
            passed = bool(score >= self.threshold)
            logger.info("Quality analysis %s: score=%.3f passed=%s metrics=%s", image_name, score, passed, metrics.to_dict())
            return AnalysisResult(score, passed, metrics)
        except Exception as exc:
            logger.exception("Error analyzing %s: %s", image_name, exc)
            empty = QualityMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5)
            return AnalysisResult(0.0, False, empty)

    def get_embeddings(self, image: Image.Image) -> np.ndarray:
        """Return a normalized CLIP image embedding, or an empty vector."""
        if self.model is None or self.preprocess is None or torch is None:
            return np.empty(0, dtype=np.float32)
        try:
            with torch.no_grad():
                tensor = self.preprocess(image.convert("RGB")).unsqueeze(0).to(self.device)
                features = self.model.encode_image(tensor)
                features = features / features.norm(dim=-1, keepdim=True).clamp_min(1e-12)
            return features.squeeze(0).float().cpu().numpy().astype(np.float32)
        except Exception as exc:
            logger.error("Error extracting embeddings: %s", exc)
            return np.empty(0, dtype=np.float32)

    def _compute_metrics(self, image: Image.Image) -> QualityMetrics:
        """Calculate normalized technical and aesthetic metrics."""
        gray_image = image.convert("L")
        gray = np.asarray(gray_image, dtype=np.float32) / 255.0
        mean = float(gray.mean())
        std = float(gray.std())
        p01, p05, p95, p99 = (float(x) for x in np.percentile(gray, [1, 5, 95, 99]))

        # Edge energy from a small high-pass filter. The scale maps typical photos into 0..1.
        edges = np.asarray(gray_image.filter(ImageFilter.FIND_EDGES), dtype=np.float32) / 255.0
        sharpness = float(np.clip(edges.std() / 0.18, 0.0, 1.0))

        # Full credit near middle gray, tapering toward black or white.
        exposure = float(np.clip(1.0 - abs(mean - 0.5) / 0.5, 0.0, 1.0))
        contrast = float(np.clip(std / 0.25, 0.0, 1.0))
        dynamic_range = float(np.clip((p95 - p05) / 0.80, 0.0, 1.0))

        megapixels = (image.width * image.height) / 1_000_000.0
        resolution = float(np.clip(np.log1p(megapixels) / np.log1p(12.0), 0.0, 1.0))

        clipped_fraction = float(np.mean((gray <= 0.01) | (gray >= 0.99)))
        clipping = float(np.clip(1.0 - clipped_fraction / 0.20, 0.0, 1.0))

        aesthetic = self._aesthetic_score(image)
        return QualityMetrics(sharpness, exposure, contrast, dynamic_range, resolution, clipping, aesthetic)

    def _aesthetic_score(self, image: Image.Image) -> float:
        """Compare an image with positive and negative quality prompts."""
        if self.model is None or self.preprocess is None or self.text_features is None or torch is None:
            return 0.5
        try:
            with torch.no_grad():
                tensor = self.preprocess(image).unsqueeze(0).to(self.device)
                image_features = self.model.encode_image(tensor)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True).clamp_min(1e-12)
                logits = (100.0 * image_features @ self.text_features.T).softmax(dim=-1)
                positive_count = len(self.POSITIVE_PROMPTS)
                positive = logits[0, :positive_count].sum()
                negative = logits[0, positive_count:].sum()
                return float((positive / (positive + negative).clamp_min(1e-12)).cpu().item())
        except Exception as exc:
            logger.warning("Aesthetic scoring failed: %s", exc)
            return 0.5
