"""
Edge Gateway Fusion Manager.
Orchestrates live telemetry from IoT Sensor Nodes, Camera Vision Inference,
Weather API, and Deforestation Risk Cache into the MultiModalFusionEngine.
"""

import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure packages and gateway directories are in path
root_dir = Path(__file__).resolve().parents[3]
fusion_pkg = str(root_dir / "packages" / "fusion-engine")
deforest_pkg = str(root_dir / "packages" / "deforestation")
cv_pkg = str(root_dir / "packages" / "cv-inference")
ml_pkg = str(root_dir / "packages" / "ml-classifier")

for p in [fusion_pkg, deforest_pkg, cv_pkg, ml_pkg]:
    if p not in sys.path:
        sys.path.insert(0, p)

from fusion import MultiModalFusionEngine
from lookup import get_deforestation_risk
from weather_service import WeatherRiskService

logger = logging.getLogger("edge_gateway.fusion_manager")


class GatewayFusionManager:
    """
    Coordinates multi-modal inputs on the edge gateway for real-time risk assessment.
    """

    def __init__(
        self,
        default_lat: float = 33.7431,
        default_lon: float = 73.0232
    ):
        self.default_lat = default_lat
        self.default_lon = default_lon
        self.fusion_engine = MultiModalFusionEngine()
        self.weather_service = WeatherRiskService(default_lat=default_lat, default_lon=default_lon)

    def evaluate_live_risk(
        self,
        sensor_score: float = 0.0,
        vision_score: float = 0.0,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        flame_detected: bool = False,
        vision_confidence: float = 0.0
    ) -> Dict[str, Any]:
        """
        Gathers live weather and satellite deforestation risk,
        combines them with sensor and vision scores, and outputs a complete assessment.
        """
        node_lat = lat if lat is not None else self.default_lat
        node_lon = lon if lon is not None else self.default_lon

        # 1. Weather risk
        weather_data = self.weather_service.fetch_current_weather(node_lat, node_lon)
        weather_score = weather_data.get("weather_score", 0.0)

        # 2. Deforestation risk
        deforest_data = get_deforestation_risk(node_lat, node_lon)
        deforest_score = deforest_data.get("deforestation_score", 0.0)

        # 3. Compute multi-modal fusion
        fusion_output = self.fusion_engine.compute_fusion_score(
            sensor_score=sensor_score,
            vision_score=vision_score,
            weather_score=weather_score,
            deforestation_score=deforest_score,
            flame_override=flame_detected,
            vision_flame_confidence=vision_confidence
        )

        return {
            "fusion": fusion_output,
            "location": {
                "latitude": node_lat,
                "longitude": node_lon
            },
            "weather": weather_data,
            "deforestation": deforest_data,
            "timestamp": time.time()
        }


# Global singleton manager
_global_manager: Optional[GatewayFusionManager] = None


def get_gateway_fusion_manager() -> GatewayFusionManager:
    global _global_manager
    if _global_manager is None:
        _global_manager = GatewayFusionManager()
    return _global_manager
