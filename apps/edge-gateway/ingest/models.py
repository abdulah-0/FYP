"""
Pydantic data schemas for Edge Gateway Ingest API.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TelemetryData(BaseModel):
    temperature_c: float = Field(..., description="Temperature in Celsius")
    humidity_percent: float = Field(..., description="Relative Humidity percentage")
    gas_ppm: float = Field(..., description="MQ-2 Gas concentration in ppm")
    smoke_ppm: float = Field(..., description="MQ-2 Smoke concentration in ppm")
    flame_detected: bool = Field(False, description="IR Flame sensor boolean state")
    raw_flame_adc: Optional[int] = Field(None, description="Raw ADC flame reading")


class PowerData(BaseModel):
    battery_voltage_v: float = Field(..., description="Battery voltage in Volts")
    battery_percent: int = Field(..., ge=0, le=100, description="Estimated state of charge (%)")
    solar_charging: bool = Field(False, description="Solar charge indicator")


class SensorTelemetryPayload(BaseModel):
    node_id: str = Field(..., description="Unique node identifier")
    seq: int = Field(..., description="Message sequence number")
    timestamp_ms: int = Field(..., description="Node uptime timestamp in ms")
    latitude: float = Field(..., description="GPS Latitude")
    longitude: float = Field(..., description="GPS Longitude")
    telemetry: TelemetryData
    power: PowerData


class IngestSensorResponse(BaseModel):
    status: str = "success"
    node_id: str
    seq: int
    sensor_score: float
    predicted_tier_id: int
    predicted_tier_label: str
    probabilities: Dict[str, float]
    delta_temp: float
    delta_rh: float


class IngestCameraResponse(BaseModel):
    status: str = "success"
    node_id: str
    frame_index: Optional[int] = None
    bytes_received: int
    vision_score: float
    predicted_label: str
    confidence: float
    probabilities: Dict[str, float]
    latency_ms: float
