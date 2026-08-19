"""
Unit tests for Weather Service & Multi-Modal Fusion Engine (Phase 5 & 6).
"""

import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

# Add paths
root_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root_dir / "packages" / "fusion-engine"))
sys.path.insert(0, str(root_dir / "apps" / "edge-gateway" / "fusion"))
sys.path.insert(0, str(root_dir / "apps" / "edge-gateway" / "ingest"))

from fusion import MultiModalFusionEngine, compute_fusion_score
from weather_service import WeatherRiskService
from server import app


class TestWeatherAndFusionEngine(unittest.TestCase):

    def test_weather_risk_scoring(self):
        service = WeatherRiskService()

        # 1. Hot, dry, windy conditions -> High meteorological risk
        score_hot = service.calculate_weather_risk_score(
            temperature_c=42.0,
            humidity_percent=20.0,
            wind_speed_kmh=35.0,
            rain_mm=0.0
        )
        self.assertGreaterEqual(score_hot, 0.70)
        self.assertTrue(0.0 <= score_hot <= 1.0)

        # 2. Cool, humid, rainy conditions -> Low meteorological risk (rain suppression)
        score_rain = service.calculate_weather_risk_score(
            temperature_c=18.0,
            humidity_percent=85.0,
            wind_speed_kmh=10.0,
            rain_mm=5.0
        )
        self.assertLessEqual(score_rain, 0.15)
        self.assertTrue(0.0 <= score_rain <= 1.0)

    def test_weather_cache(self):
        service = WeatherRiskService(cache_ttl_sec=60.0)
        w1 = service.fetch_current_weather(lat=33.74, lon=73.02)
        self.assertIn("weather_score", w1)
        self.assertFalse(w1.get("is_cached", False))

        # Immediate repeat should be cached
        w2 = service.fetch_current_weather(lat=33.74, lon=73.02)
        self.assertTrue(w2.get("is_cached", False))

    def test_multi_modal_fusion_math(self):
        engine = MultiModalFusionEngine(
            weight_sensor=0.40,
            weight_vision=0.30,
            weight_weather=0.20,
            weight_deforestation=0.10
        )

        # Exact calculation test
        # (0.50 * 0.40) + (0.60 * 0.30) + (0.70 * 0.20) + (0.80 * 0.10)
        # = 0.20 + 0.18 + 0.14 + 0.08 = 0.60 -> High Risk
        res = engine.compute_fusion_score(
            sensor_score=0.50,
            vision_score=0.60,
            weather_score=0.70,
            deforestation_score=0.80
        )
        self.assertAlmostEqual(res["confidence_score"], 0.60, places=3)
        self.assertEqual(res["tier_id"], 2)
        self.assertEqual(res["severity_tier"], "High Risk")
        self.assertEqual(res["tier_badge"], "🟠")
        self.assertTrue(res["critical_alert"])

    def test_severity_tier_boundaries(self):
        # 1. Safe condition
        safe = compute_fusion_score(sensor_score=0.10, vision_score=0.05, weather_score=0.15, deforestation_score=0.20)
        self.assertEqual(safe["tier_id"], 0)
        self.assertEqual(safe["severity_tier"], "Safe")
        self.assertEqual(safe["tier_badge"], "🟢")
        self.assertFalse(safe["critical_alert"])

        # 2. Warning condition
        warn = compute_fusion_score(sensor_score=0.45, vision_score=0.20, weather_score=0.50, deforestation_score=0.40)
        self.assertEqual(warn["tier_id"], 1)
        self.assertEqual(warn["severity_tier"], "Warning")
        self.assertEqual(warn["tier_badge"], "🟡")

        # 3. Fire Detected condition
        fire = compute_fusion_score(sensor_score=0.95, vision_score=0.90, weather_score=0.80, deforestation_score=0.70)
        self.assertEqual(fire["tier_id"], 3)
        self.assertEqual(fire["severity_tier"], "Fire Detected")
        self.assertEqual(fire["tier_badge"], "🔴")
        self.assertTrue(fire["critical_alert"])

    def test_flame_override_safety(self):
        # Even if weather and deforestation are zero, flame override elevates to Fire Detected
        override_res = compute_fusion_score(
            sensor_score=0.10,
            vision_score=0.10,
            weather_score=0.0,
            deforestation_score=0.0,
            flame_override=True
        )
        self.assertEqual(override_res["tier_id"], 3)
        self.assertEqual(override_res["severity_tier"], "Fire Detected")
        self.assertTrue(override_res["is_override"])
        self.assertGreaterEqual(override_res["confidence_score"], 0.90)

    def test_gateway_fusion_endpoint(self):
        client = TestClient(app)
        response = client.get("/api/v1/fusion/score")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("fusion", data)
        self.assertIn("confidence_score", data["fusion"])
        self.assertIn("severity_tier", data["fusion"])
        self.assertIn("weather", data)
        self.assertIn("deforestation", data)


if __name__ == "__main__":
    unittest.main()
