"""
Edge Gateway Vision Service.
Consumes camera frames (JPEG bytes or numpy frames from ESP32-CAM) and coordinates with
packages.cv_inference to produce real-time fire and smoke vision scores.
"""

import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union
from PIL import Image

# Ensure packages are importable
cv_pkg_path = str(Path(__file__).resolve().parents[3] / "packages" / "cv-inference")
if cv_pkg_path not in sys.path:
    sys.path.insert(0, cv_pkg_path)

from infer import VisionFireClassifier

logger = logging.getLogger("edge_gateway.vision_service")


class GatewayVisionService:
    """
    Manages vision inference on the edge gateway with frame throttling, caching, and fallback metrics.
    """

    def __init__(self, model_name: Optional[str] = None, min_inference_interval_sec: float = 1.0):
        self.min_inference_interval_sec = min_inference_interval_sec
        self.last_inference_time = 0.0
        self.last_result: Optional[Dict[str, Any]] = None

        logger.info("Initializing GatewayVisionService...")
        self.classifier = VisionFireClassifier(
            model_name=model_name or "prithivMLmods/Forest-Fire-Detection",
            lazy_load=True
        )

    def process_frame(
        self,
        frame_data: Union[bytes, Image.Image, str, Path],
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Processes an incoming frame from ESP32-CAM or gateway storage.
        If called more frequently than `min_inference_interval_sec` and `force=False`,
        returns the cached last result to avoid saturating Raspberry Pi CPU/GPU.
        """
        now = time.time()
        if not force and self.last_result is not None and (now - self.last_inference_time) < self.min_inference_interval_sec:
            cached = dict(self.last_result)
            cached["is_cached"] = True
            return cached

        start_t = time.perf_counter()
        try:
            inference_output = self.classifier.classify_image(frame_data)
            duration_ms = round((time.perf_counter() - start_t) * 1000, 2)

            result = {
                "success": True,
                "timestamp": now,
                "latency_ms": duration_ms,
                "vision_score": inference_output["vision_score"],
                "predicted_label": inference_output["predicted_label"],
                "confidence": inference_output["confidence"],
                "probabilities": inference_output["probabilities"],
                "is_cached": False,
            }
            self.last_inference_time = time.time()
            self.last_result = result
            return result
        except Exception as err:
            logger.error(f"Error executing vision inference: {err}")
            return {
                "success": False,
                "timestamp": now,
                "error": str(err),
                "vision_score": 0.0,
                "predicted_label": "Unknown",
                "confidence": 0.0,
                "probabilities": {"Fire": 0.0, "Normal": 1.0, "Smoke": 0.0},
                "is_cached": False,
            }

    def get_latest_score(self) -> float:
        """Returns the latest vision risk score [0.0, 1.0] for the fusion engine."""
        if self.last_result is None:
            return 0.0
        return float(self.last_result.get("vision_score", 0.0))
