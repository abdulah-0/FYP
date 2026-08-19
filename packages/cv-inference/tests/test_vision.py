"""
Unit tests for Computer Vision Inference & Gateway Vision Service (Phase 2).
"""

import io
import sys
import unittest
from pathlib import Path
import numpy as np
from PIL import Image

# Add package and gateway paths
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps" / "edge-gateway" / "inference"))

from infer import VisionFireClassifier, classify_image
from vision_service import GatewayVisionService


class TestVisionInference(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create test synthetic images in memory
        cls.normal_img = Image.new("RGB", (224, 224), color=(34, 139, 34))   # Forest Green
        cls.fire_img = Image.new("RGB", (224, 224), color=(255, 69, 0))      # Flame Orange/Red
        cls.smoke_img = Image.new("RGB", (224, 224), color=(180, 180, 180))  # Smoke Grey

        # Convert to bytes
        buf = io.BytesIO()
        cls.fire_img.save(buf, format="JPEG")
        cls.fire_bytes = buf.getvalue()

        # Convert to numpy array
        cls.np_img = np.array(cls.normal_img)

    def test_image_preparation(self):
        classifier = VisionFireClassifier(lazy_load=True)

        # 1. PIL Image input
        p1 = classifier._prepare_image(self.normal_img)
        self.assertIsInstance(p1, Image.Image)
        self.assertEqual(p1.mode, "RGB")

        # 2. Bytes input
        p2 = classifier._prepare_image(self.fire_bytes)
        self.assertIsInstance(p2, Image.Image)
        self.assertEqual(p2.mode, "RGB")

        # 3. Numpy array input
        p3 = classifier._prepare_image(self.np_img)
        self.assertIsInstance(p3, Image.Image)
        self.assertEqual(p3.mode, "RGB")

    def test_heuristic_fallback_differentiation(self):
        classifier = VisionFireClassifier(lazy_load=True)

        # Test normal forest image vs fire image using vision analysis
        normal_res = classifier._heuristic_vision_fallback(self.normal_img)
        fire_res = classifier._heuristic_vision_fallback(self.fire_img)
        smoke_res = classifier._heuristic_vision_fallback(self.smoke_img)

        self.assertGreater(normal_res["Normal"], normal_res["Fire"])
        self.assertGreater(fire_res["Fire"], fire_res["Normal"])
        self.assertGreater(smoke_res["Smoke"], normal_res["Smoke"])

    def test_vision_classification_contract(self):
        classifier = VisionFireClassifier(lazy_load=True)

        result = classifier.classify_image(self.fire_img)
        self.assertIn("probabilities", result)
        self.assertIn("Fire", result["probabilities"])
        self.assertIn("Normal", result["probabilities"])
        self.assertIn("Smoke", result["probabilities"])
        self.assertIn("predicted_label", result)
        self.assertIn("vision_score", result)
        self.assertIn("confidence", result)

        self.assertTrue(0.0 <= result["vision_score"] <= 1.0)
        self.assertTrue(0.0 <= result["confidence"] <= 1.0)

    def test_gateway_vision_service_cache_and_pipeline(self):
        service = GatewayVisionService(min_inference_interval_sec=0.5)
        self.assertEqual(service.get_latest_score(), 0.0)

        # First frame processing
        res1 = service.process_frame(self.fire_bytes)
        self.assertTrue(res1.get("success"))
        self.assertIn("vision_score", res1)
        self.assertIn("latency_ms", res1)
        self.assertFalse(res1.get("is_cached", False))

        score = service.get_latest_score()
        self.assertTrue(0.0 <= score <= 1.0)

        # Immediate repeat should hit cache
        res2 = service.process_frame(self.fire_bytes, force=False)
        self.assertTrue(res2.get("is_cached", False))
        self.assertEqual(res2["vision_score"], res1["vision_score"])


if __name__ == "__main__":
    unittest.main()
