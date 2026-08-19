# Project Memory & Implementation Log

## Overview
- **Project**: AI-Based Forest Fire Detection System with Satellite-Assisted Deforestation Risk Mapping (FYP)
- **Repository**: `https://github.com/abdulah-0/FYP.git`
- **Reference Plan**: `docs/implementation-plan.md`
- **Status**: In Progress

---

## Phase Status Summary

| Phase | Description | Status | Verification Status | Git Sync |
|---|---|---|---|---|
| **Phase 0** | Monorepo Structure & Environment Setup | Completed | Verified | Pushed (`main`) |
| **Phase 1** | Sensor Classification Model (`packages/ml-classifier/`) | Completed | Verified (89.8% Acc, 0.898 F1) | Pushed (`main`) |
| **Phase 2** | Pretrained CV Inference Wrapper (`packages/cv-inference/`) | Completed | Verified (SigLIP2 / Vision Tests OK) | Pushed (`main`) |
| **Phase 3** | Deforestation Risk Layer (`packages/deforestation/`) | Completed | Verified (Sentinel-2 NDVI / Spatial Cache OK) | Pushed (`main`) |
| **Phase 4** | Hardware Firmware & Edge Gateway (`apps/firmware/`, `apps/edge-gateway/`) | Completed | Verified (ESP32 Ingest API / Tests OK) | Pushed (`main`) |
| **Phase 5** | Weather API Integration (`apps/edge-gateway/fusion/`) | Completed | Verified (OpenWeather API / Cache OK) | Pushed (`main`) |
| **Phase 6** | Rule-Based Multi-Modal Fusion Engine (`packages/fusion-engine/`) | Completed | Verified (Weighted Scoring / Tiers OK) | Pushed (`main`) |
| **Phase 7** | Minimal Web Dashboard (`apps/dashboard/`) | In Progress | Pending | Pending |

---

## Detailed Task Log

### Phase 0: Monorepo Structure & Memory Tracking Setup
- **Task**: Initialize project repository, establish standard monorepo folder layout, configure `.gitignore`, `.env.example`, `README.md`, and `docs/memory.md`.
- **Why**: Establishes clean modular architecture separation across edge firmware, gateway services, ML classifier packages, computer vision modules, deforestation calculations, and frontend dashboard as defined in Phase 0 of the implementation plan.
- **What was done**:
  - Created directory hierarchy for `apps/` (firmware nodes, edge gateway, dashboard) and `packages/` (ml-classifier, cv-inference, fusion-engine, deforestation) and `data/`, `docs/`, `scripts/`.
  - Configured `.gitignore` to prevent committing raw datasets, model weights, cache artifacts, environment secrets, and virtual environments.
  - Created `README.md`, `docs/architecture.md`, and `.env.example`.
  - Initialized git repository with remote origin pointing to `https://github.com/abdulah-0/FYP.git`.
- **Status / Verification**:
  - [x] Monorepo directory tree created with `.gitkeep` placeholders.
  - [x] `.gitignore` verified.
  - [x] `docs/memory.md` created.
  - [x] Git initial commit pushed to remote repository.
  - [x] Working: Yes.

### Phase 1: Sensor Classification Model (`packages/ml-classifier/`)
- **Task**: Clean Algerian Forest Fires dataset, synthesize MQ-2 gas/smoke proxy channels, calculate rate-of-change temporal features, train multi-tier classifiers, evaluate metrics, and export prediction module.
- **Why**: The edge gateway requires an intelligent sensor risk classification model capable of detecting fire risk (Safe, Warning, High Risk, Fire Detected) from environmental sensor telemetry (temperature, relative humidity, wind speed, rain, gas/smoke concentrations, and temporal deltas).
- **What was done**:
  - Built `packages/ml-classifier/preprocess.py`: Cleans raw Algerian dataset, handles headers/anomalies, engineers rate-of-change ($\Delta T/\Delta t, \Delta RH/\Delta t$) and combustion gas/smoke proxy readings, and generates 4 risk tiers.
  - Built `packages/ml-classifier/train.py`: Trains Random Forest and Gradient Boosting pipelines with StandardScaler, 5-fold stratified cross-validation, and exports `sensor_classifier.joblib` and `metadata.json`.
  - Built `packages/ml-classifier/predict.py`: Provides `SensorFireClassifier` class and CLI returning predicted risk tier, class probabilities, and normalized continuous `sensor_score` $[0.0, 1.0]$.
  - Built `packages/ml-classifier/tests/test_classifier.py`: 4 comprehensive unit tests verifying data pipeline, feature engineering, deterministic safe/fire boundary predictions, and batch scoring.
- **Status / Verification**:
  - [x] Preprocessing produced 243 balanced instances across 4 risk tiers.
  - [x] Random Forest achieved **89.8% test accuracy** and **0.898 F1-macro score** (100% precision on Fire Detected, 0.97 F1).
  - [x] All 4 unit tests passing (`Ran 4 tests ... OK`).
  - [x] Working: Yes.

### Phase 2: Pretrained Computer Vision Model Wrapper (`packages/cv-inference/`)
- **Task**: Implement wrapper around pretrained SigLIP2 `prithivMLmods/Forest-Fire-Detection` image classifier, support multi-format image inputs (PIL, JPEG bytes, OpenCV array), compute continuous normalized vision risk score, build edge gateway vision service with caching, and create comprehensive unit tests.
- **Why**: Optical flame and smoke detection from camera frames provides direct visual confirmation for the multi-modal fusion engine, significantly cutting false alarm rates when sensor readings fluctuate due to ambient weather.
- **What was done**:
  - Built `packages/cv-inference/infer.py`: Implemented `VisionFireClassifier` with `SiglipImageProcessorPil` and `AutoModelForImageClassification` / fallback combustion heuristic, returning Fire/Normal/Smoke probability distribution and continuous `vision_score` $[0.0, 1.0]$.
  - Built `apps/edge-gateway/inference/vision_service.py`: Gateway inference integration layer with frame rate throttling (`min_inference_interval_sec`), latency measurement, result caching, and safe error boundaries for Raspberry Pi edge gateways.
  - Built `packages/cv-inference/tests/test_vision.py`: 4 unit tests testing image conversions (PIL, bytes, numpy), vision score bounds $[0.0, 1.0]$, fire vs normal contrast, and gateway caching.
- **Status / Verification**:
  - [x] Model wrapper supports PIL Image, bytes, and OpenCV numpy arrays.
  - [x] Gateway service handles frame caching and avoids CPU saturation.
  - [x] All 4 unit tests passing (`Ran 4 tests ... OK`).
  - [x] Working: Yes.

### Phase 3: Deforestation Risk Layer (`packages/deforestation/`)
- **Task**: Implement Sentinel-2 NDVI mathematical computation $(B8 - B4)/(B8 + B4)$, vegetation degradation and fuel flammability classification, spatial grid generator for Margalla Hills / test regions, spatial cache export (`cache/risk_layer.json`), and coordinate lookup service.
- **Why**: Satellite-derived vegetation health and deforestation degradation provide long-term baseline vulnerability scores, establishing whether dry fuel biomass exists at the IoT node's GPS location.
- **What was done**:
  - Built `packages/deforestation/compute_ndvi.py`: Formula calculating Sentinel-2 NDVI with division-by-zero protection, 5-tier classification mapping NDVI to fire vulnerability scores $[0.10, 0.85]$, GEE integration pipeline, and spatial grid generator generating 390 geographic nodes for Margalla Hills National Park.
  - Built `packages/deforestation/lookup.py`: Implemented `DeforestationLookupService` and `get_deforestation_risk(lat, lon)` performing closest grid node matching, Haversine distance calculation, and normalized `deforestation_score` $[0.0, 1.0]$.
  - Built `packages/deforestation/tests/test_deforestation.py`: 4 unit tests verifying NDVI math, edge tier classification, JSON cache generation, and spatial coordinate lookup.
- **Status / Verification**:
  - [x] Accurate mathematical NDVI calculation and array vectorization verified.
  - [x] Generated 390 grid cells in `packages/deforestation/cache/risk_layer.json`.
  - [x] Coordinate lookup tested for Margalla Hills coordinates `(33.7431, 73.0232)` with sub-kilometer nearest node resolution.
  - [x] All 4 unit tests passing (`Ran 4 tests in 0.037s ... OK`).
  - [x] Working: Yes.

### Phase 4: Hardware Node Firmware & Edge Gateway Ingest (`apps/firmware/`, `apps/edge-gateway/`)
- **Task**: Develop Arduino/PlatformIO firmware sketches for ESP32 sensor node and ESP32-CAM video node, build FastAPI telemetry ingestion service on Raspberry Pi, calculate live rate-of-change deltas ($\Delta T, \Delta RH$), execute sensor ML classification and CV processing, log data to disk, and write integration tests.
- **Why**: Connects physical edge IoT sensing hardware in the field (DHT22, MQ-2, Flame sensor, OV2640, LiFePO4 battery monitoring) to the Raspberry Pi edge computing server over Wi-Fi.
- **What was done**:
  - Built `apps/firmware/sensor-node/`: `sensor-node.ino` and `platformio.ini` reading DHT22 (Temp/RH), MQ-2 gas/smoke ADC, flame sensor digital/analog pins, and LiFePO4 battery voltage divider, sending JSON telemetry payloads over HTTP POST.
  - Built `apps/firmware/cam-node/`: `cam-node.ino` and `platformio.ini` configuring AI-Thinker OV2640 camera, PSRAM, JPEG compression, capturing frames every 10s, and streaming via HTTP POST.
  - Built `apps/edge-gateway/ingest/`: `models.py` and `server.py` providing FastAPI endpoints for sensor ingestion (`POST /api/v1/telemetry/sensor`), camera stream (`POST /api/v1/telemetry/camera/frame`), live consolidated state (`GET /api/v1/telemetry/latest`), historical charts (`GET /api/v1/telemetry/history`), and health checks.
  - Built `apps/edge-gateway/tests/test_gateway_ingest.py`: 5 unit/integration tests verifying sensor ingestion, temporal delta computation ($\Delta T=15^\circ\text{C}, \Delta RH=-25\%$), camera frame processing, and live history buffering.
- **Status / Verification**:
  - [x] Firmware sketches created for Arduino IDE & PlatformIO with full pin definitions and LiFePO4 power telemetry.
  - [x] Edge gateway endpoints validated with Pydantic schemas.
  - [x] All 5 gateway unit tests passing (`Ran 5 tests in 12.173s ... OK`).
  - [x] Working: Yes.

### Phase 5 & 6: Weather API Integration & Multi-Modal Fusion Engine (`apps/edge-gateway/fusion/`, `packages/fusion-engine/`)
- **Task**: Integrate real-time meteorological API service with TTL caching and thermal/wind threat scoring, build multi-modal weighted fusion scoring engine ($40\%$ Sensor, $30\%$ Vision, $20\%$ Weather, $10\%$ Deforestation), assign severity tiers (🟢 Safe, 🟡 Warning, 🟠 High Risk, 🔴 Fire Detected), implement optical flame safety override, build gateway fusion manager, and expose REST fusion endpoint.
- **Why**: Multi-modal fusion synthesizes disparate edge signals (ground sensors, optical camera vision, atmospheric weather, satellite vegetation indices) to make a reliable early-warning determination with minimal false alarms.
- **What was done**:
  - Built `apps/edge-gateway/fusion/weather_service.py`: Queries OpenWeatherMap / regional meteorological model, computes `weather_score` $[0.0, 1.0]$ based on Canadian FWI principles (thermal dryness index, wind spread multiplier, rain suppression), and implements a 15-minute memory cache.
  - Built `packages/fusion-engine/fusion.py`: Implemented `MultiModalFusionEngine` calculating weighted confidence score $\text{Confidence} = (0.4 \times S) + (0.3 \times V) + (0.2 \times W) + (0.1 \times D)$, mapping to 4 severity tiers with emoji badges, and active flame override logic.
  - Built `apps/edge-gateway/fusion/fusion_manager.py`: Orchestrates live inputs across all 4 pillars and exposes `GET /api/v1/fusion/score` on the edge gateway FastAPI server.
  - Built `packages/fusion-engine/tests/test_fusion.py`: 6 unit tests verifying weather threat scoring, cache TTL, exact fusion math, tier boundaries, flame override, and gateway endpoint integration.
- **Status / Verification**:
  - [x] Weather scoring correctly maps hot/dry/windy to high risk ($\ge 0.70$) and rain to low risk ($\le 0.15$).
  - [x] Fusion engine computes weighted sums and maps severity tiers accurately.
  - [x] Safety override guarantees critical alert on physical flame detection.
  - [x] Gateway endpoint `/api/v1/fusion/score` returns complete structured multi-modal breakdown.
  - [x] All 6 fusion unit tests passing (`Ran 6 tests in 0.017s ... OK`).
  - [x] Total 23 unit tests passing across all 6 project modules.
  - [x] Working: Yes.

---





