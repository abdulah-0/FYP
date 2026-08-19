# Forest Fire Guardian: AI-Based Forest Fire Detection & Deforestation Risk Mapping

An end-to-end intelligent environmental monitoring system integrating IoT edge sensors (ESP32), computer vision (SigLIP2 / pretrained fire-smoke classifier), satellite remote sensing (Sentinel-2 NDVI deforestation risk), and real-time multi-modal fusion scoring.

---

## System Architecture Overview

```
                          +-------------------------+
                          |   ESP32 Sensor Node     |
                          | (DHT22, MQ-2, Flame)    |
                          +------------+------------+
                                       | Wi-Fi (JSON Telemetry)
                                       v
+------------------------+      +------------------+      +-----------------------+
|  ESP32-CAM Node        | ---> |   Edge Gateway   | <--- |  Weather API Service  |
|  (Frames / JPEG)       |      |  (Raspberry Pi)  |      |  (Wind, Rain, Temp)   |
+------------------------+      +--------+---------+      +-----------------------+
                                         |
                                         v
                         +-------------------------------+
                         | Multi-Modal Fusion Engine     |
                         | - Sensor Classifier (40%)     |
                         | - Computer Vision (30%)       |
                         | - Weather Threat (20%)        |
                         | - Deforestation Risk (10%)    |
                         +---------------+---------------+
                                         |
                                         v
                         +-------------------------------+
                         | Web Dashboard & Alerting      |
                         +-------------------------------+
```

---

## Directory Structure

```
forest-fire-guardian/
├── apps/
│   ├── firmware/                # ESP32 + ESP32-CAM code (C++/Arduino/PlatformIO)
│   │   ├── sensor-node/          # ESP32: DHT22, MQ-2, flame sensor -> JSON over Wi-Fi
│   │   └── cam-node/              # ESP32-CAM: captures frames -> POST to gateway
│   ├── edge-gateway/             # Python service (FastAPI) on Raspberry Pi
│   │   ├── ingest/                # receives sensor + camera streams
│   │   ├── inference/             # runs classifier + pretrained CV model
│   │   ├── fusion/                # multi-modal rule-based fusion scoring
│   │   └── api/                   # REST/WebSocket API feeding the dashboard
│   └── dashboard/                 # Web dashboard UI
├── packages/
│   ├── ml-classifier/             # Sensor classifier (data prep, training, prediction)
│   ├── cv-inference/              # Pretrained vision inference wrapper
│   ├── fusion-engine/             # Multi-modal fusion scoring engine
│   └── deforestation/             # Satellite NDVI calculation and spatial caching
├── data/
│   ├── raw/                       # Raw training CSVs and satellite exports (gitignored)
│   └── processed/                 # Cleaned datasets used for training/validation (gitignored)
├── docs/
│   ├── implementation-plan.md     # Reference phase-by-phase roadmap
│   ├── memory.md                  # Detailed task log and verification status
│   └── architecture.md            # System architecture and technical specifications
├── scripts/                       # Deployment and helper scripts
├── .env.example
├── .gitignore
└── README.md
```

---

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+ (for dashboard)
- Git

### Quick Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/abdulah-0/FYP.git
   cd FYP
   ```
2. Set up environment variables:
   ```bash
   cp .env.example .env
   ```
3. Install Python dependencies:
   ```bash
   pip install -r packages/ml-classifier/requirements.txt
   ```
