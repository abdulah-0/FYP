"""
Inference module for Sensor Risk Classifier.
Provides an easy-to-use prediction interface for edge gateway and standalone scripts.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import joblib
import numpy as np
import pandas as pd

from preprocess import FEATURE_COLUMNS, RISK_TIERS


class SensorFireClassifier:
    """
    Wrapper for loading the trained sensor classification model and performing single or batch predictions.
    """

    def __init__(self, model_dir: Optional[str] = None):
        if model_dir is None:
            model_dir = str(Path(__file__).parent / "model")
        
        self.model_dir = Path(model_dir)
        self.model_path = self.model_dir / "sensor_classifier.joblib"
        self.metadata_path = self.model_dir / "metadata.json"

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model file not found at {self.model_path}. Please run train.py first."
            )

        self.pipeline = joblib.load(self.model_path)
        
        if self.metadata_path.exists():
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {}

        self.risk_tiers = RISK_TIERS
        self.feature_columns = FEATURE_COLUMNS

    def predict_reading(
        self,
        temperature: float,
        rh: float,
        ws: float = 10.0,
        rain: float = 0.0,
        gas_ppm: float = 30.0,
        smoke_ppm: float = 15.0,
        delta_temp: float = 0.0,
        delta_rh: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Predicts the risk tier for a single sensor telemetry reading.

        Returns:
            Dict containing:
                - tier_id: int (0 to 3)
                - tier_label: str ("Safe", "Warning", "High Risk", "Fire Detected")
                - probabilities: Dict[str, float]
                - sensor_score: float normalized risk score [0.0, 1.0] for fusion engine
                - raw_features: Dict[str, float]
        """
        features_dict = {
            "Temperature": float(temperature),
            "RH": float(rh),
            "Ws": float(ws),
            "Rain": float(rain),
            "Gas_ppm": float(gas_ppm),
            "Smoke_ppm": float(smoke_ppm),
            "Delta_Temp": float(delta_temp),
            "Delta_RH": float(delta_rh),
        }

        df_input = pd.DataFrame([features_dict])[self.feature_columns]

        predicted_tier = int(self.pipeline.predict(df_input)[0])
        tier_label = self.risk_tiers.get(predicted_tier, f"Unknown ({predicted_tier})")

        # Class probabilities
        probs = self.pipeline.predict_proba(df_input)[0]
        classes = self.pipeline.classes_
        prob_dict = {self.risk_tiers.get(int(cls), f"Tier_{cls}"): round(float(p), 4) for cls, p in zip(classes, probs)}

        # Continuous normalized sensor risk score for fusion engine [0.0 - 1.0]:
        # Weighted expectation of risk tier (0->0.0, 1->0.33, 2->0.66, 3->1.0)
        risk_weights = np.array([float(c) / 3.0 for c in classes])
        sensor_score = round(float(np.dot(probs, risk_weights)), 4)

        return {
            "tier_id": predicted_tier,
            "tier_label": tier_label,
            "probabilities": prob_dict,
            "sensor_score": sensor_score,
            "features": features_dict,
        }

    def predict_batch(self, df_readings: pd.DataFrame) -> List[Dict[str, Any]]:
        """Predicts risk tier for a DataFrame of readings."""
        results = []
        for _, row in df_readings.iterrows():
            res = self.predict_reading(
                temperature=row.get("Temperature", 25.0),
                rh=row.get("RH", 60.0),
                ws=row.get("Ws", 10.0),
                rain=row.get("Rain", 0.0),
                gas_ppm=row.get("Gas_ppm", 30.0),
                smoke_ppm=row.get("Smoke_ppm", 15.0),
                delta_temp=row.get("Delta_Temp", 0.0),
                delta_rh=row.get("Delta_RH", 0.0),
            )
            results.append(res)
        return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Predict Forest Fire Risk from Sensor Readings")
    parser.add_argument("--temp", type=float, default=32.0, help="Temperature in Celsius")
    parser.add_argument("--rh", type=float, default=45.0, help="Relative Humidity (%)")
    parser.add_argument("--ws", type=float, default=15.0, help="Wind Speed (km/h)")
    parser.add_argument("--rain", type=float, default=0.0, help="Rain (mm)")
    parser.add_argument("--gas", type=float, default=50.0, help="MQ-2 Gas (ppm)")
    parser.add_argument("--smoke", type=float, default=30.0, help="Smoke (ppm)")
    parser.add_argument("--dtemp", type=float, default=1.5, help="Delta Temperature")
    parser.add_argument("--drh", type=float, default=-3.0, help="Delta Humidity")

    args = parser.parse_args()

    clf = SensorFireClassifier()
    result = clf.predict_reading(
        temperature=args.temp,
        rh=args.rh,
        ws=args.ws,
        rain=args.rain,
        gas_ppm=args.gas,
        smoke_ppm=args.smoke,
        delta_temp=args.dtemp,
        delta_rh=args.drh
    )

    print("\n--- Sensor Fire Risk Prediction ---")
    print(f"Predicted Tier : [{result['tier_id']}] {result['tier_label']}")
    print(f"Sensor Score   : {result['sensor_score']} / 1.0000")
    print(f"Probabilities  : {json.dumps(result['probabilities'], indent=2)}")


if __name__ == "__main__":
    main()
