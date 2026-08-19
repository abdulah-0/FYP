"""
Edge Gateway Telemetry Ingest & Management Service.
FastAPI service running on Raspberry Pi receiving real-time sensor streams and camera frames.
"""

import io
import json
import logging
import os
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image

# Ensure packages and gateway modules are in sys.path
root_dir = Path(__file__).resolve().parents[3]
ml_pkg_path = str(root_dir / "packages" / "ml-classifier")
cv_pkg_path = str(root_dir / "packages" / "cv-inference")
gateway_inference_path = str(Path(__file__).resolve().parents[1] / "inference")

for p in [ml_pkg_path, cv_pkg_path, gateway_inference_path]:
    if p not in sys.path:
        sys.path.insert(0, p)

from models import IngestCameraResponse, IngestSensorResponse, SensorTelemetryPayload
from predict import SensorFireClassifier
from vision_service import GatewayVisionService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("edge_gateway.ingest")

app = FastAPI(
    title="Forest Fire Guardian - Edge Gateway",
    description="Raspberry Pi Edge Telemetry Ingestion & Real-time AI Inference Service",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-Memory Telemetry State
MAX_HISTORY_LEN = 200
node_previous_readings: Dict[str, Dict[str, Any]] = {}
telemetry_history: Deque[Dict[str, Any]] = deque(maxlen=MAX_HISTORY_LEN)
latest_sensor_telemetry: Optional[Dict[str, Any]] = None
latest_vision_telemetry: Optional[Dict[str, Any]] = None

# Storage paths
LOGS_DIR = root_dir / "data" / "raw"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
SENSOR_LOG_FILE = LOGS_DIR / "sensor_telemetry.jsonl"
LATEST_FRAME_PATH = Path(__file__).parent / "latest_frame.jpg"

# Lazy-loaded Model Services
sensor_classifier: Optional[SensorFireClassifier] = None
gateway_vision_service: Optional[GatewayVisionService] = None


def get_sensor_classifier() -> SensorFireClassifier:
    global sensor_classifier
    if sensor_classifier is None:
        model_dir = str(root_dir / "packages" / "ml-classifier" / "model")
        sensor_classifier = SensorFireClassifier(model_dir=model_dir)
    return sensor_classifier


def get_vision_service() -> GatewayVisionService:
    global gateway_vision_service
    if gateway_vision_service is None:
        gateway_vision_service = GatewayVisionService(min_inference_interval_sec=1.0)
    return gateway_vision_service


def append_sensor_log(data: Dict[str, Any]):
    """Appends reading to local jsonl file for auditing and retraining."""
    try:
        with open(SENSOR_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")
    except Exception as err:
        logger.error(f"Failed to log sensor data to disk: {err}")


@app.get("/health")
@app.get("/api/v1/health")
def health_check():
    """Returns gateway service status and uptime."""
    return {
        "status": "healthy",
        "service": "Forest Fire Guardian Edge Gateway",
        "uptime_sec": round(time.time() - SERVER_START_TIME, 1),
        "history_count": len(telemetry_history),
        "active_nodes": list(node_previous_readings.keys())
    }


@app.post("/api/v1/telemetry/sensor", response_model=IngestSensorResponse)
async def ingest_sensor_telemetry(payload: SensorTelemetryPayload, background_tasks: BackgroundTasks):
    """
    Ingests JSON sensor telemetry from ESP32 node, computes temporal deltas,
    and runs ML fire classifier inference.
    """
    global latest_sensor_telemetry
    node_id = payload.node_id
    t = payload.telemetry
    p = payload.power

    # Compute rate-of-change deltas against previous reading from same node
    delta_temp = 0.0
    delta_rh = 0.0
    if node_id in node_previous_readings:
        prev = node_previous_readings[node_id]
        delta_temp = round(t.temperature_c - prev["temperature_c"], 2)
        delta_rh = round(t.humidity_percent - prev["humidity_percent"], 2)

    node_previous_readings[node_id] = {
        "temperature_c": t.temperature_c,
        "humidity_percent": t.humidity_percent,
        "timestamp": time.time()
    }

    # Run ML classifier
    classifier = get_sensor_classifier()
    prediction = classifier.predict_reading(
        temperature=t.temperature_c,
        rh=t.humidity_percent,
        gas_ppm=t.gas_ppm,
        smoke_ppm=t.smoke_ppm,
        delta_temp=delta_temp,
        delta_rh=delta_rh
    )

    # Force Fire Detected tier if physical optical flame sensor is active
    if t.flame_detected:
        prediction["tier_id"] = 3
        prediction["tier_label"] = "Fire Detected"
        prediction["sensor_score"] = max(prediction["sensor_score"], 0.95)

    record = {
        "timestamp": time.time(),
        "node_id": node_id,
        "seq": payload.seq,
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "telemetry": t.model_dump(),
        "power": p.model_dump(),
        "delta_temp": delta_temp,
        "delta_rh": delta_rh,
        "prediction": prediction
    }

    latest_sensor_telemetry = record
    telemetry_history.append(record)
    background_tasks.add_task(append_sensor_log, record)

    return IngestSensorResponse(
        node_id=node_id,
        seq=payload.seq,
        sensor_score=prediction["sensor_score"],
        predicted_tier_id=prediction["tier_id"],
        predicted_tier_label=prediction["tier_label"],
        probabilities=prediction["probabilities"],
        delta_temp=delta_temp,
        delta_rh=delta_rh
    )


@app.post("/api/v1/telemetry/camera/frame", response_model=IngestCameraResponse)
async def ingest_camera_frame(
    request: Request,
    file: Optional[UploadFile] = File(None),
    x_node_id: Optional[str] = Header(None),
    x_frame_index: Optional[int] = Header(None)
):
    """
    Ingests JPEG camera frames from ESP32-CAM (as binary stream or multipart upload)
    and executes real-time vision inference.
    """
    global latest_vision_telemetry
    node_id = x_node_id or "ESP32_CAM_DEFAULT"
    frame_index = x_frame_index

    # Read binary content
    if file:
        frame_bytes = await file.read()
    else:
        frame_bytes = await request.body()

    if not frame_bytes:
        raise HTTPException(status_code=400, detail="Empty frame payload received")

    # Save latest frame to disk
    try:
        with open(LATEST_FRAME_PATH, "wb") as f:
            f.write(frame_bytes)
    except Exception as err:
        logger.warning(f"Could not save latest frame to disk: {err}")

    vision_service = get_vision_service()
    inf_res = vision_service.process_frame(frame_bytes)

    record = {
        "timestamp": time.time(),
        "node_id": node_id,
        "frame_index": frame_index,
        "bytes_received": len(frame_bytes),
        "vision_score": inf_res.get("vision_score", 0.0),
        "predicted_label": inf_res.get("predicted_label", "Unknown"),
        "confidence": inf_res.get("confidence", 0.0),
        "probabilities": inf_res.get("probabilities", {}),
        "latency_ms": inf_res.get("latency_ms", 0.0),
        "is_cached": inf_res.get("is_cached", False)
    }

    latest_vision_telemetry = record

    return IngestCameraResponse(
        node_id=node_id,
        frame_index=frame_index,
        bytes_received=len(frame_bytes),
        vision_score=record["vision_score"],
        predicted_label=record["predicted_label"],
        confidence=record["confidence"],
        probabilities=record["probabilities"],
        latency_ms=record["latency_ms"]
    )


@app.get("/api/v1/telemetry/camera/latest_image")
def get_latest_camera_image():
    """Returns the latest captured JPEG image file."""
    if not LATEST_FRAME_PATH.exists():
        raise HTTPException(status_code=404, detail="No frame has been captured yet")
    return FileResponse(LATEST_FRAME_PATH, media_type="image/jpeg")


@app.get("/api/v1/telemetry/latest")
def get_latest_telemetry():
    """
    Returns consolidated live state (latest sensor readings, latest camera inference,
    and gateway status) for the web dashboard.
    """
    return {
        "timestamp": time.time(),
        "sensor": latest_sensor_telemetry,
        "vision": latest_vision_telemetry,
        "history_count": len(telemetry_history)
    }


@app.get("/api/v1/telemetry/history")
def get_telemetry_history(limit: int = 50):
    """Returns the last N historical sensor telemetry records for dashboard charts."""
    limit = min(max(1, limit), MAX_HISTORY_LEN)
    history_list = list(telemetry_history)
    return {
        "total": len(history_list),
        "limit": limit,
        "records": history_list[-limit:]
    }


SERVER_START_TIME = time.time()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
