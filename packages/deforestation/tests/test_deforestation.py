"""
Unit tests for Deforestation Risk Layer & Spatial Lookup (Phase 3).
"""

import json
import os
import sys
import unittest
from pathlib import Path
import numpy as np

# Add package path to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compute_ndvi import (
    DEFAULT_BOUNDING_BOX,
    build_and_save_risk_cache,
    calculate_ndvi,
    classify_ndvi_risk,
    generate_region_grid,
)
from lookup import DeforestationLookupService, get_deforestation_risk


class TestDeforestationRiskEngine(unittest.TestCase):

    def test_ndvi_calculation(self):
        # 1. Healthy vegetation (High NIR, Low Red) -> High NDVI (~0.66)
        ndvi_healthy = calculate_ndvi(nir_band=0.80, red_band=0.16)
        self.assertAlmostEqual(ndvi_healthy, (0.80 - 0.16) / (0.80 + 0.16), places=4)
        self.assertGreater(ndvi_healthy, 0.6)

        # 2. Deforested / Dry soil (Moderate NIR, High Red) -> Low NDVI (~0.11)
        ndvi_dry = calculate_ndvi(nir_band=0.25, red_band=0.20)
        self.assertAlmostEqual(ndvi_dry, (0.25 - 0.20) / (0.25 + 0.20), places=4)
        self.assertLess(ndvi_dry, 0.25)

        # 3. Water / Negative NDVI
        ndvi_water = calculate_ndvi(nir_band=0.05, red_band=0.15)
        self.assertLess(ndvi_water, 0.0)

        # 4. Array inputs
        nir_arr = np.array([0.7, 0.3])
        red_arr = np.array([0.1, 0.2])
        res_arr = calculate_ndvi(nir_arr, red_arr)
        self.assertEqual(len(res_arr), 2)
        self.assertTrue(res_arr[0] > res_arr[1])

    def test_ndvi_risk_classification(self):
        # Dry degraded scrub -> High fire vulnerability
        dry_risk = classify_ndvi_risk(0.18)
        self.assertEqual(dry_risk["risk_tier"], "High Deforestation Risk")
        self.assertGreaterEqual(dry_risk["deforestation_score"], 0.8)

        # Dense moist canopy -> Low fire vulnerability
        dense_risk = classify_ndvi_risk(0.78)
        self.assertEqual(dense_risk["risk_tier"], "Very Low Risk")
        self.assertLessEqual(dense_risk["deforestation_score"], 0.2)

    def test_grid_generation_and_cache(self):
        test_cache_path = str(Path(__file__).parent / "temp_test_risk_layer.json")
        try:
            cache_data = build_and_save_risk_cache(output_path=test_cache_path)
            self.assertTrue(os.path.exists(test_cache_path))
            self.assertGreater(cache_data["total_cells"], 10)
            self.assertIn("grid", cache_data)

            # Check individual node schema
            node = cache_data["grid"][0]
            self.assertIn("lat", node)
            self.assertIn("lon", node)
            self.assertIn("ndvi", node)
            self.assertIn("deforestation_score", node)
            self.assertTrue(0.0 <= node["deforestation_score"] <= 1.0)
        finally:
            if os.path.exists(test_cache_path):
                os.remove(test_cache_path)

    def test_spatial_lookup(self):
        # Margalla Hills test point: 33.7431 N, 73.0232 E
        res = get_deforestation_risk(lat=33.7431, lon=73.0232)
        self.assertIn("ndvi", res)
        self.assertIn("deforestation_score", res)
        self.assertIn("distance_km", res)
        self.assertTrue(res["is_cached"])
        self.assertLess(res["distance_km"], 2.0)  # Should be within ~1km of nearest grid point
        self.assertTrue(0.0 <= res["deforestation_score"] <= 1.0)


if __name__ == "__main__":
    unittest.main()
