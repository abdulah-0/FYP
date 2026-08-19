"""
Deforestation & NDVI Spatial Lookup Module.
Provides fast coordinate lookup (lat, lon) against the cached Sentinel-2 risk layer
for the edge gateway and fusion engine.
"""

import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from compute_ndvi import DEFAULT_CACHE_PATH, build_and_save_risk_cache, classify_ndvi_risk


class DeforestationLookupService:
    """
    Service for querying deforestation risk and NDVI for given GPS coordinates.
    """

    def __init__(self, cache_path: Optional[str] = None):
        self.cache_path = cache_path or DEFAULT_CACHE_PATH
        self.cache_data: Optional[Dict[str, Any]] = None
        self._load_cache()

    def _load_cache(self):
        if not os.path.exists(self.cache_path):
            build_and_save_risk_cache(self.cache_path)

        with open(self.cache_path, "r", encoding="utf-8") as f:
            self.cache_data = json.load(f)

    def get_risk_for_coordinates(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Finds the closest grid cell in the cached risk layer to the specified GPS coordinates.

        Returns:
            Dict containing:
                - query_lat: float
                - query_lon: float
                - matched_lat: float
                - matched_lon: float
                - distance_km: float
                - ndvi: float
                - risk_tier: str
                - deforestation_score: float [0.0 - 1.0]
                - vegetation_desc: str
                - tier_level: int
        """
        if not self.cache_data or "grid" not in self.cache_data:
            self._load_cache()

        grid: List[Dict[str, Any]] = self.cache_data["grid"]

        best_cell = None
        min_dist_sq = float("inf")

        # Find closest grid node via squared Euclidean distance (lat/lon)
        for cell in grid:
            d_lat = cell["lat"] - lat
            d_lon = cell["lon"] - lon
            dist_sq = (d_lat * d_lat) + (d_lon * d_lon)
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                best_cell = cell

        if best_cell is None:
            # Fallback default
            default_risk = classify_ndvi_risk(0.40)
            return {
                "query_lat": lat,
                "query_lon": lon,
                "matched_lat": lat,
                "matched_lon": lon,
                "distance_km": 0.0,
                "ndvi": 0.40,
                "risk_tier": default_risk["risk_tier"],
                "deforestation_score": default_risk["deforestation_score"],
                "vegetation_desc": default_risk["vegetation_desc"],
                "tier_level": default_risk["tier_level"],
                "is_cached": False,
            }

        # Approximate distance in km (1 deg lat ~ 111 km)
        d_lat_deg = best_cell["lat"] - lat
        d_lon_deg = (best_cell["lon"] - lon) * math.cos(math.radians(lat))
        dist_km = math.sqrt((d_lat_deg * 111.0)**2 + (d_lon_deg * 111.0)**2)

        return {
            "query_lat": lat,
            "query_lon": lon,
            "matched_lat": best_cell["lat"],
            "matched_lon": best_cell["lon"],
            "distance_km": round(dist_km, 3),
            "ndvi": best_cell["ndvi"],
            "risk_tier": best_cell["risk_tier"],
            "deforestation_score": best_cell["deforestation_score"],
            "vegetation_desc": best_cell["vegetation_desc"],
            "tier_level": best_cell["tier_level"],
            "is_cached": True,
        }


# Global singleton instance for easy import
_service_instance: Optional[DeforestationLookupService] = None


def get_deforestation_risk(lat: float, lon: float, cache_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to get deforestation risk score for a GPS coordinate.
    """
    global _service_instance
    if _service_instance is None or cache_path is not None:
        _service_instance = DeforestationLookupService(cache_path=cache_path)
    return _service_instance.get_risk_for_coordinates(lat, lon)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Query Deforestation Risk by GPS Coordinates")
    parser.add_argument("--lat", type=float, default=33.7431, help="Latitude")
    parser.add_argument("--lon", type=float, default=73.0232, help="Longitude")
    args = parser.parse_args()

    res = get_deforestation_risk(args.lat, args.lon)
    print(f"\n--- Deforestation Risk for ({args.lat}, {args.lon}) ---")
    print(f"Nearest Grid Node  : ({res['matched_lat']}, {res['matched_lon']}) - {res['distance_km']} km away")
    print(f"NDVI Vegetation    : {res['ndvi']} ({res['vegetation_desc']})")
    print(f"Deforestation Risk : {res['risk_tier']}")
    print(f"Normalized Score   : {res['deforestation_score']} / 1.0000")
