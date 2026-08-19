"""
Unit tests for Sensor Risk Classifier (Phase 1).
Verifies data loading, preprocessing, model training, and deterministic inference.
"""

import os
import sys
from pathlib import Path
import unittest
import pandas as pd
import numpy as np

# Add package to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from preprocess import (
    FEATURE_COLUMNS,
    RISK_TIERS,
    engineer_sensor_features,
    load_raw_algerian_dataset,
    prepare_and_save_dataset,
)
from predict import SensorFireClassifier
from train import train_sensor_model


import unittest


class TestSensorFireClassifier(unittest.TestCase):

    def test_raw_dataset_loading(self):
        raw_path = "data/raw/Algerian_forest_fires_dataset.csv"
        self.assertTrue(os.path.exists(raw_path), "Raw dataset must exist")
        df = load_raw_algerian_dataset(raw_path)
        self.assertGreater(len(df), 200, f"Expected >200 records, got {len(df)}")
        self.assertIn("Temperature", df.columns)
        self.assertIn("RH", df.columns)
        self.assertIn("Classes", df.columns)

    def test_feature_engineering(self):
        raw_path = "data/raw/Algerian_forest_fires_dataset.csv"
        df_raw = load_raw_algerian_dataset(raw_path)
        df_feat = engineer_sensor_features(df_raw)

        for col in FEATURE_COLUMNS:
            self.assertIn(col, df_feat.columns, f"Missing feature column: {col}")
        self.assertIn("Risk_Tier", df_feat.columns)

        # Verify no NaNs in engineered feature columns
        self.assertEqual(df_feat[FEATURE_COLUMNS].isna().sum().sum(), 0)

        # Verify tier values are in 0..3
        unique_tiers = set(df_feat["Risk_Tier"].unique())
        self.assertTrue(unique_tiers.issubset({0, 1, 2, 3}))

    def test_model_training_and_prediction(self):
        raw_path = "data/raw/Algerian_forest_fires_dataset.csv"
        processed_path = "data/processed/forest_fire_processed.csv"
        model_dir = "packages/ml-classifier/model"

        train_sensor_model(processed_path, model_dir)
        self.assertTrue(os.path.exists(os.path.join(model_dir, "sensor_classifier.joblib")))
        self.assertTrue(os.path.exists(os.path.join(model_dir, "metadata.json")))

        classifier = SensorFireClassifier(model_dir=model_dir)

        # 1. Safe condition test: Cool temp, high humidity, low gas/smoke
        safe_pred = classifier.predict_reading(
            temperature=18.0,
            rh=85.0,
            ws=5.0,
            rain=2.0,
            gas_ppm=15.0,
            smoke_ppm=8.0,
            delta_temp=0.0,
            delta_rh=0.0
        )
        self.assertIn(safe_pred["tier_id"], [0, 1])
        self.assertLess(safe_pred["sensor_score"], 0.5)
        self.assertTrue(0.0 <= safe_pred["sensor_score"] <= 1.0)

        # 2. Fire condition test: High temp, low humidity, high gas and smoke spike
        fire_pred = classifier.predict_reading(
            temperature=42.0,
            rh=15.0,
            ws=28.0,
            rain=0.0,
            gas_ppm=450.0,
            smoke_ppm=380.0,
            delta_temp=4.5,
            delta_rh=-12.0
        )
        self.assertIn(fire_pred["tier_id"], [2, 3])
        self.assertGreater(fire_pred["sensor_score"], 0.6)
        self.assertTrue(0.0 <= fire_pred["sensor_score"] <= 1.0)

    def test_batch_prediction(self):
        model_dir = "packages/ml-classifier/model"
        classifier = SensorFireClassifier(model_dir=model_dir)
        
        test_df = pd.DataFrame([
            {"Temperature": 22.0, "RH": 70.0, "Ws": 10.0, "Rain": 0.0, "Gas_ppm": 20.0, "Smoke_ppm": 10.0, "Delta_Temp": 0.0, "Delta_RH": 0.0},
            {"Temperature": 38.0, "RH": 25.0, "Ws": 20.0, "Rain": 0.0, "Gas_ppm": 350.0, "Smoke_ppm": 200.0, "Delta_Temp": 2.0, "Delta_RH": -5.0}
        ])
        
        results = classifier.predict_batch(test_df)
        self.assertEqual(len(results), 2)
        self.assertLess(results[0]["sensor_score"], results[1]["sensor_score"])


if __name__ == "__main__":
    unittest.main()

