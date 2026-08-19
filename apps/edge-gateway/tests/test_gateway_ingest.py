"""
Unit and Integration tests for Edge Gateway Ingest Service (Phase 4).
"""

import io
import sys
import unittest
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

# Add gateway and package paths
gateway_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(gateway_dir / "ingest"))
sys.path.insert(0, str(gateway_dir / "inference"))
sys.path.insert(0, str(gateway_dir.parents[1] / "packages" / "ml-classifier"))
sys.path.insert(0, str(gateway_dir.parents[1] / "packages" / "cv-inference"))

from server import app


class TestGatewayIngestService(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

        # Create a test synthetic JPEG in memory
        img = Image.new("RGB", (100, 100), color=(255, 69, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        cls.test_jpeg_bytes = buf.getvalue()

    def test_health_check(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("uptime_sec", data)

    def test_ingest_sensor_telemetry_safe(self):
        payload = {
            "node_id": "TEST_NODE_SAFE",
            "seq": 1,
            "timestamp_ms": 10000,
            "latitude": 33.7431,
            "longitude": 73.0232,
            "telemetry": {
                "temperature_c": 22.5,
                "humidity_percent": 65.0,
                "gas_ppm": 20.0,
                "smoke_ppm": 10.0,
                "flame_detected": False,
                "raw_flame_adc": 3800
            },
            "power": {
                "battery_voltage_v": 3.32,
                "battery_percent": 80,
                "solar_charging": True
            }
        }

        response = self.client.post("/api/v1/telemetry/sensor", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["node_id"], "TEST_NODE_SAFE")
        self.assertIn("sensor_score", data)
        self.assertTrue(0.0 <= data["sensor_score"] <= 1.0)
        self.assertIn(data["predicted_tier_id"], [0, 1])

    def test_ingest_sensor_telemetry_delta_and_fire(self):
        # First reading from NODE_FIRE
        p1 = {
            "node_id": "TEST_NODE_FIRE",
            "seq": 1,
            "timestamp_ms": 10000,
            "latitude": 33.7431,
            "longitude": 73.0232,
            "telemetry": {
                "temperature_c": 30.0,
                "humidity_percent": 40.0,
                "gas_ppm": 50.0,
                "smoke_ppm": 20.0,
                "flame_detected": False
            },
            "power": {"battery_voltage_v": 3.30, "battery_percent": 75, "solar_charging": True}
        }
        self.client.post("/api/v1/telemetry/sensor", json=p1)

        # Second reading with sharp temp rise, humidity drop, high gas, and active flame
        p2 = {
            "node_id": "TEST_NODE_FIRE",
            "seq": 2,
            "timestamp_ms": 15000,
            "latitude": 33.7431,
            "longitude": 73.0232,
            "telemetry": {
                "temperature_c": 45.0,
                "humidity_percent": 15.0,
                "gas_ppm": 500.0,
                "smoke_ppm": 400.0,
                "flame_detected": True
            },
            "power": {"battery_voltage_v": 3.28, "battery_percent": 70, "solar_charging": False}
        }
        res2 = self.client.post("/api/v1/telemetry/sensor", json=p2)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()

        self.assertEqual(data2["delta_temp"], 15.0)
        self.assertEqual(data2["delta_rh"], -25.0)
        self.assertEqual(data2["predicted_tier_id"], 3)
        self.assertEqual(data2["predicted_tier_label"], "Fire Detected")
        self.assertGreaterEqual(data2["sensor_score"], 0.8)

    def test_ingest_camera_frame_binary(self):
        headers = {
            "Content-Type": "image/jpeg",
            "X-Node-ID": "TEST_CAM_01",
            "X-Frame-Index": "42"
        }
        response = self.client.post(
            "/api/v1/telemetry/camera/frame",
            content=self.test_jpeg_bytes,
            headers=headers
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["node_id"], "TEST_CAM_01")
        self.assertIn("vision_score", data)
        self.assertTrue(0.0 <= data["vision_score"] <= 1.0)
        self.assertIn("probabilities", data)

    def test_get_latest_telemetry_and_history(self):
        # Post a sample reading to ensure state
        sample_payload = {
            "node_id": "TEST_NODE_HIST",
            "seq": 100,
            "timestamp_ms": 50000,
            "latitude": 33.7431,
            "longitude": 73.0232,
            "telemetry": {
                "temperature_c": 26.0,
                "humidity_percent": 55.0,
                "gas_ppm": 25.0,
                "smoke_ppm": 12.0,
                "flame_detected": False
            },
            "power": {"battery_voltage_v": 3.33, "battery_percent": 82, "solar_charging": True}
        }
        self.client.post("/api/v1/telemetry/sensor", json=sample_payload)

        res_latest = self.client.get("/api/v1/telemetry/latest")
        self.assertEqual(res_latest.status_code, 200)
        data_latest = res_latest.json()
        self.assertIn("sensor", data_latest)
        self.assertIn("vision", data_latest)

        res_history = self.client.get("/api/v1/telemetry/history?limit=10")
        self.assertEqual(res_history.status_code, 200)
        data_history = res_history.json()
        self.assertIn("records", data_history)
        self.assertGreaterEqual(data_history["total"], 1)


if __name__ == "__main__":
    unittest.main()
