"""
Multi-Modal Fire Risk Fusion Engine.
Fuses Sensor Telemetry (40%), Computer Vision (30%), Meteorological Threat (20%),
and Deforestation Risk (10%) into a unified early wildfire detection and confidence score.
"""

import time
from typing import Any, Dict, Optional, Tuple, Union


# Standard Default Fusion Weights (Tunable in Phase 8)
DEFAULT_WEIGHT_SENSOR = 0.40
DEFAULT_WEIGHT_VISION = 0.30
DEFAULT_WEIGHT_WEATHER = 0.20
DEFAULT_WEIGHT_DEFORESTATION = 0.10

# Threshold Tiers
THRESHOLD_SAFE = 0.30
THRESHOLD_WARNING = 0.60
THRESHOLD_HIGH_RISK = 0.80


class MultiModalFusionEngine:
    """
    Rule-based and weighted fusion engine combining multiple environmental data modalities.
    """

    def __init__(
        self,
        weight_sensor: float = DEFAULT_WEIGHT_SENSOR,
        weight_vision: float = DEFAULT_WEIGHT_VISION,
        weight_weather: float = DEFAULT_WEIGHT_WEATHER,
        weight_deforestation: float = DEFAULT_WEIGHT_DEFORESTATION,
    ):
        total_weight = weight_sensor + weight_vision + weight_weather + weight_deforestation
        if total_weight <= 0:
            raise ValueError("Total fusion weight must be greater than zero.")

        # Normalize weights to sum to 1.0
        self.w_sensor = weight_sensor / total_weight
        self.w_vision = weight_vision / total_weight
        self.w_weather = weight_weather / total_weight
        self.w_deforestation = weight_deforestation / total_weight

    def map_severity_tier(self, confidence_score: float) -> Tuple[int, str, str]:
        """
        Maps a continuous score [0.0, 1.0] to severity tier ID, label, and emoji badge.
        """
        score = float(min(1.0, max(0.0, confidence_score)))

        if score < THRESHOLD_SAFE:
            return (0, "Safe", "🟢")
        elif score < THRESHOLD_WARNING:
            return (1, "Warning", "🟡")
        elif score < THRESHOLD_HIGH_RISK:
            return (2, "High Risk", "🟠")
        else:
            return (3, "Fire Detected", "🔴")

    def compute_fusion_score(
        self,
        sensor_score: float,
        vision_score: float = 0.0,
        weather_score: float = 0.0,
        deforestation_score: float = 0.0,
        flame_override: bool = False,
        vision_flame_confidence: float = 0.0
    ) -> Dict[str, Any]:
        """
        Computes weighted multi-modal fire risk score and assigns severity tier.

        Formula:
            Confidence = (Sensor * 0.4) + (Vision * 0.3) + (Weather * 0.2) + (Deforestation * 0.1)

        Safety Overrides:
            - If physical flame sensor triggered or optical camera confirms flame > 90%,
              elevates severity to 🔴 Fire Detected.
        """
        # Clamp inputs to [0.0, 1.0]
        s_sensor = float(min(1.0, max(0.0, sensor_score)))
        s_vision = float(min(1.0, max(0.0, vision_score)))
        s_weather = float(min(1.0, max(0.0, weather_score)))
        s_deforest = float(min(1.0, max(0.0, deforestation_score)))

        raw_score = (
            (s_sensor * self.w_sensor)
            + (s_vision * self.w_vision)
            + (s_weather * self.w_weather)
            + (s_deforest * self.w_deforestation)
        )

        is_override = False
        if flame_override or vision_flame_confidence >= 0.90 or (s_sensor >= 0.95 and s_vision >= 0.80):
            raw_score = max(raw_score, 0.92)
            is_override = True

        confidence_score = round(float(min(1.0, max(0.0, raw_score))), 4)
        tier_id, tier_label, tier_badge = self.map_severity_tier(confidence_score)

        return {
            "confidence_score": confidence_score,
            "severity_tier": tier_label,
            "tier_badge": tier_badge,
            "tier_id": tier_id,
            "critical_alert": (tier_id >= 2),
            "is_override": is_override,
            "sub_scores": {
                "sensor_score": s_sensor,
                "vision_score": s_vision,
                "weather_score": s_weather,
                "deforestation_score": s_deforest
            },
            "weights": {
                "sensor": round(self.w_sensor, 3),
                "vision": round(self.w_vision, 3),
                "weather": round(self.w_weather, 3),
                "deforestation": round(self.w_deforestation, 3)
            },
            "timestamp": time.time()
        }


# Global singleton instance
_default_engine: Optional[MultiModalFusionEngine] = None


def compute_fusion_score(
    sensor_score: float,
    vision_score: float = 0.0,
    weather_score: float = 0.0,
    deforestation_score: float = 0.0,
    flame_override: bool = False,
    vision_flame_confidence: float = 0.0
) -> Dict[str, Any]:
    """Convenience functional access."""
    global _default_engine
    if _default_engine is None:
        _default_engine = MultiModalFusionEngine()
    return _default_engine.compute_fusion_score(
        sensor_score=sensor_score,
        vision_score=vision_score,
        weather_score=weather_score,
        deforestation_score=deforestation_score,
        flame_override=flame_override,
        vision_flame_confidence=vision_flame_confidence
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate Multi-Modal Fire Risk Fusion")
    parser.add_argument("--sensor", type=float, default=0.75, help="Sensor Risk Score (0.0 - 1.0)")
    parser.add_argument("--vision", type=float, default=0.85, help="Vision Risk Score (0.0 - 1.0)")
    parser.add_argument("--weather", type=float, default=0.60, help="Weather Threat Score (0.0 - 1.0)")
    parser.add_argument("--deforest", type=float, default=0.55, help="Deforestation Risk Score (0.0 - 1.0)")
    parser.add_argument("--flame", action="store_true", help="Optical flame detected flag")

    args = parser.parse_args()
    engine = MultiModalFusionEngine()
    result = engine.compute_fusion_score(
        sensor_score=args.sensor,
        vision_score=args.vision,
        weather_score=args.weather,
        deforestation_score=args.deforest,
        flame_override=args.flame
    )

    print("\n--- Multi-Modal Fire Risk Fusion Result ---")
    print(f"Confidence Score : {result['confidence_score']} / 1.0000")
    print(f"Severity Tier    : {result['tier_badge']} [{result['tier_id']}] {result['severity_tier']}")
    print(f"Critical Alert   : {result['critical_alert']}")
    print(f"Sub-Scores       : {result['sub_scores']}")
    print(f"Weights          : {result['weights']}")
