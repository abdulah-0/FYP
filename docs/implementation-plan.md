# Implementation Plan
## AI-Based Forest Fire Detection System with Satellite-Assisted Deforestation Risk Mapping

This document is the living implementation plan for the FYP. It is written to be pasted into an AI
coding agent (e.g. Antigravity, Cursor, Windsurf) phase by phase. Each phase lists:

- **What the agent should build** (code, in the monorepo)
- **What you must do manually** — things an AI coding agent cannot do for you: creating accounts,
  downloading/registering for external models and datasets, physically wiring hardware, flashing
  firmware onto real boards, and anything requiring a browser login or a soldering iron.

Do the manual steps for a phase *before* asking the agent to build that phase's code, since the code
usually depends on a file, model, or credential that only you can obtain.

---

## 0. Monorepo Structure

Create the repository with this structure up front. Every phase below adds files inside it.

```
forest-fire-guardian/
├── apps/
│   ├── firmware/                # ESP32 + ESP32-CAM code (C++/Arduino or PlatformIO)
│   │   ├── sensor-node/          # ESP32: DHT22, MQ-2, flame sensor -> sends JSON over Wi-Fi
│   │   └── cam-node/              # ESP32-CAM: captures frames -> sends to gateway
│   ├── edge-gateway/             # Python service on Raspberry Pi
│   │   ├── ingest/                # receives sensor + camera data
│   │   ├── inference/             # runs classifier + pretrained CV model
│   │   ├── fusion/                # rule-based fusion scoring
│   │   └── api/                   # REST/WebSocket API feeding the dashboard
│   └── dashboard/                 # Web dashboard (Next.js or plain React + Flask API)
├── packages/
│   ├── ml-classifier/             # training code + saved model for sensor classification
│   │   ├── data/                   # (gitignored) training CSVs
│   │   ├── train.py
│   │   └── model/                  # (gitignored) exported .pkl/.joblib model file
│   ├── cv-inference/               # wrapper around the pretrained flame/smoke model
│   │   ├── model_cache/             # (gitignored, optional) local HF cache copy for offline/field use
│   │   └── infer.py
│   ├── fusion-engine/              # shared rule-based fusion logic (importable by gateway + tests)
│   │   └── fusion.py
│   └── deforestation/              # NDVI risk layer generation (offline, periodic)
│       ├── gee_auth/
│       ├── compute_ndvi.py
│       └── cache/                  # (gitignored) cached risk lookup by GPS coordinate
├── data/
│   ├── raw/                       # raw sensor logs, satellite exports
│   └── processed/                 # cleaned datasets used for training/validation
├── docs/
│   ├── proposal.pdf
│   ├── architecture.md
│   └── setup-guides/              # copies of the manual steps below, one file per external service
├── scripts/                       # deployment/dev utility scripts
├── .env.example
├── .gitignore
├── README.md
└── docker-compose.yml             # optional: run gateway + dashboard together locally
```

**Manual step (do this first):**
1. Create a new GitHub repository named `forest-fire-guardian` (or your preferred name).
2. Clone it locally, create the folder structure above (empty folders with `.gitkeep` files are fine).
3. Add a `.gitignore` that excludes: `data/raw/`, `data/processed/`, `**/model/`, `**/cache/`, `.env`,
   `__pycache__/`, `node_modules/`, `*.pkl`, `*.joblib`, `*.h5`, `*.tflite`. Model weights and datasets
   should never be committed — they're large and often have separate licenses.

---

## Phase 1 — Sensor Classification Model *(Semester 1)*

**Goal:** One trained model that classifies fire risk (Safe / Warning / High Risk / Fire Detected) from
temperature, humidity, smoke, and gas readings, plus rate-of-change features.

### What the agent builds
- `packages/ml-classifier/train.py`: loads the CSV dataset, engineers rate-of-change features
  (Δtemperature/Δt, Δhumidity/Δt over the last N readings), trains a Random Forest or Logistic
  Regression classifier, evaluates accuracy/precision/recall, and exports the model.
- A small `predict.py` that loads the exported model and classifies a single new reading.
- Unit tests using a held-out slice of the dataset.

### Manual step: obtaining a training dataset
An AI coding agent cannot browse Kaggle/UCI, accept dataset terms, or download files behind a login —
you need to do this yourself:

1. Go to Kaggle (kaggle.com) and search **"forest fire sensor dataset"** or **"Algerian forest fires
   dataset"** (a well-known public dataset with temperature, humidity, wind, and a fire/no-fire label).
   Alternatively search the **UCI Machine Learning Repository** for "Forest Fires" or "Algerian Forest
   Fires Dataset."
2. Create a free Kaggle account if you don't have one, and download the CSV.
3. Place the file at `data/raw/forest_fire_sensors.csv` in your repo (this path is gitignored, so it
   won't be pushed — that's expected).
4. If the dataset doesn't include a smoke/gas column (many don't, since MQ-2 data is less commonly
   published), note this as a limitation in your report: you can either (a) simulate a smoke/gas column
   using a simple formula correlated with temperature and humidity for now, clearly labeled as
   synthetic, or (b) wait until Phase 4 hardware data collection gives you real smoke/gas readings and
   retrain later. Tell the agent which option you're taking so it builds the pipeline to match.

### Manual step: none for training itself
Once the CSV is in place, training runs locally via `python train.py` — no external accounts needed.

---

## Phase 2 — Pretrained Computer Vision Model *(Semester 1)*

**Goal:** Flame/smoke detection from camera frames using an existing pretrained model — no training.

**Model chosen:** [`prithivMLmods/Forest-Fire-Detection`](https://huggingface.co/prithivMLmods/Forest-Fire-Detection)
on Hugging Face — a SigLIP2-based image classifier (fine-tuned from
`google/siglip2-base-patch16-512`) that outputs Fire / Normal / Smoke with a self-reported 99.52%
accuracy. It was chosen over YOLO-based alternatives because:
- It's a classifier, not an object detector — it returns a confidence score per class, which is exactly
  what the fusion engine needs, without the extra complexity of bounding-box output.
- Apache 2.0 license, publicly downloadable with **no login gate or "request access" step** (unlike some
  YOLO fire-detection models on Hugging Face that require agreeing to share contact info first).
- Clean integration via the standard `transformers` library — no Ultralytics/YOLO dependency needed.
- 92.9M parameters — light enough to run comfortably on a Raspberry Pi gateway.

### What the agent builds
- `packages/cv-inference/infer.py`: loads the model via `transformers`, exposes a `classify_image(image)`
  function returning `{"Fire": 0.xx, "Normal": 0.xx, "Smoke": 0.xx}`.
- Integration point in `apps/edge-gateway/inference/` that calls this on incoming camera frames and feeds
  the Fire/Smoke scores into the fusion engine's `vision_score`.

### Manual step: none — no account, no license request, no binary file to hunt down
Unlike the general Hugging Face search process in earlier drafts of this plan, this specific model has no
manual download step. You only need to install the library once and let the first run cache the weights:

1. Install dependencies:
   ```
   pip install -q transformers torch pillow hf_xet
   ```
2. Run this one-time sanity check yourself (not the agent) to confirm the model loads and produces sane
   output before wiring it into the gateway — this avoids the agent debugging an environment issue that
   was never about the code:
   ```python
   from transformers import AutoImageProcessor, SiglipForImageClassification
   from PIL import Image
   import torch

   model_name = "prithivMLmods/Forest-Fire-Detection"
   model = SiglipForImageClassification.from_pretrained(model_name)
   processor = AutoImageProcessor.from_pretrained(model_name)

   id2label = {"0": "Fire", "1": "Normal", "2": "Smoke"}
   image = Image.open("path/to/test_image.jpg").convert("RGB")
   inputs = processor(images=image, return_tensors="pt")
   with torch.no_grad():
       logits = model(**inputs).logits
       probs = torch.nn.functional.softmax(logits, dim=1).squeeze().tolist()
   print({id2label[str(i)]: round(probs[i], 3) for i in range(len(probs))})
   ```
   The first run downloads the weights automatically into your local Hugging Face cache (`~/.cache/huggingface`)
   — no manual file placement needed. This means `packages/cv-inference/model/` from the original monorepo
   layout is no longer required; the model is fetched by name at runtime instead of stored as a local file.
   If you'd rather have an offline copy for the Raspberry Pi (which may have a slower/no internet
   connection in the field), download it once on your dev machine and copy the cache folder over manually.
3. Note the model name, license (Apache 2.0), and reported accuracy in `docs/architecture.md` for citation
   in your final report, since you did not train this model yourself.
4. **Fallback / optional extra**: if you want a demo visual with a bounding box drawn around the detected
   flame (useful for your presentation), `SalahALHaismawi/yolov26-fire-detection` on Hugging Face is a
   good ungated, MIT-licensed YOLO alternative. This is optional and not required for core functionality.

---

## Phase 3 — Deforestation Risk Layer *(Semester 1)*

**Goal:** NDVI-based deforestation risk map for one test region, cached locally by GPS coordinate.
This is a formula (vegetation index thresholding), not a trained model.

### What the agent builds
- `packages/deforestation/compute_ndvi.py`: authenticates to Google Earth Engine, pulls Sentinel-2
  bands (B4 red, B8 near-infrared) for the chosen region, computes NDVI = (B8-B4)/(B8+B4), thresholds
  it into risk tiers, and writes the result to `cache/risk_layer.json` keyed by lat/lon grid cell.
- A small lookup function the fusion engine can call with the sensor node's GPS coordinate.

### Manual step: Google Earth Engine account and authentication
1. Go to **code.earthengine.google.com** and sign up for a free Earth Engine account using a Google
   account (approval is sometimes instant, sometimes takes a day or two for new accounts — do this
   early, don't leave it for the week the deliverable is due).
2. Once approved, install the Python API locally:
   ```
   pip install earthengine-api
   earthengine authenticate
   ```
   This opens a browser login — you must complete this yourself; an agent cannot log into your Google
   account.
3. Pick your test region (e.g. a forested area in Pakistan you can justify in your report — Margalla
   Hills or a Khyber Pakhtunkhwa forest reserve are reasonable choices given your location). Note the
   bounding box coordinates (lat/lon) — get these from Google Maps by right-clicking a point.
4. Give the agent the region's bounding box and your authenticated environment; it can then write and
   run the NDVI script against real data.

---

## Phase 4 — Hardware Node & Edge Gateway *(Semester 1)*

**Goal:** One physical sensor node (ESP32 + DHT22 + MQ-2 + flame sensor + ESP32-CAM) powered by solar +
LiFePO4 battery, streaming data to a Raspberry Pi edge gateway.

### What the agent builds
- `apps/firmware/sensor-node/`: Arduino/PlatformIO code reading DHT22, MQ-2, and flame sensor, packaging
  readings as JSON, and sending them over Wi-Fi to the gateway's IP on a fixed interval.
- `apps/firmware/cam-node/`: ESP32-CAM code capturing a frame every N seconds and POSTing it to the
  gateway.
- `apps/edge-gateway/ingest/`: a small server (Flask/FastAPI) on the Raspberry Pi that receives both
  streams and stores/queues them for the inference pipeline.

### Manual step: purchasing and assembling hardware
This cannot be done by an agent at all — physical parts and wiring:

1. **Order parts** (if not already owned): ESP32 dev board, ESP32-CAM module, DHT22, MQ-2 gas/smoke
   sensor, a basic flame sensor module, a 5–10W solar panel, a solar charge controller rated for
   LiFePO4 chemistry (important — a Li-ion charge controller uses the wrong voltage curve for LiFePO4),
   a single LiFePO4 cell or small pack (e.g. 3.2V or 12.8V pack depending on your controller), a
   Raspberry Pi (3B+ or 4), a Raspberry Pi power supply or a second small battery for it, jumper wires,
   a breadboard or perfboard, and a weatherproof enclosure box.
2. **Wire the sensors to the ESP32** following each sensor's datasheet pinout (DHT22 data pin to a
   digital GPIO with a pull-up resistor, MQ-2 analog output to an ADC pin, flame sensor digital/analog
   output to a GPIO). Do this on a breadboard first, test each sensor individually with a simple test
   sketch, before finalizing wiring in the enclosure.
3. **Wire the solar panel → charge controller → LiFePO4 battery → ESP32/ESP32-CAM power input.** Double
   check polarity before connecting the battery — reversed polarity can damage the charge controller.
4. **Flash the firmware**: install the Arduino IDE (or PlatformIO extension in VS Code), install the
   ESP32 board package, connect the ESP32 via USB, and upload the sketch the agent writes for you. This
   physical upload step must be done by you each time firmware changes, since it requires a USB
   connection to the real board.
5. **Set up the Raspberry Pi**: flash Raspberry Pi OS onto an SD card using the Raspberry Pi Imager tool
   (from a separate computer), boot it, connect it to the same Wi-Fi network as the ESP32/ESP32-CAM, and
   note its local IP address — the firmware needs this IP to know where to send data.
6. Only after steps 1–5 are physically working can the agent's ingest server code be tested end-to-end.

---

## Phase 5 — Weather API Integration *(Semester 1, pulled forward)*

### What the agent builds
- A small module in `apps/edge-gateway/fusion/` that fetches current weather (wind speed, rain
  probability, temperature) for the node's location and caches it with a short refresh interval.

### Manual step: getting a weather API key
1. Sign up for a free tier account at **OpenWeatherMap** (openweathermap.org/api) or **WeatherAPI.com**.
2. Generate an API key from your account dashboard.
3. Add it to a local `.env` file (never commit this):
   ```
   WEATHER_API_KEY=your_key_here
   ```
4. Give the agent the `.env.example` template (key name only, no real value) so it knows what variable
   to read.

---

## Phase 6 — Rule-Based Fusion Scoring (Draft) *(Semester 1, pulled forward)*

### What the agent builds
- `packages/fusion-engine/fusion.py`: a weighted-scoring function —
  ```
  confidence = (sensor_score * 0.4) + (vision_score * 0.3) + (weather_score * 0.2) + (deforestation_score * 0.1)
  ```
  mapped to severity tiers (🟢🟡🟠🔴), with weights defined as constants you can tune later.
- No manual/external step needed here — this is pure logic, testable with mock inputs.

---

## Phase 7 — Minimal Dashboard *(Semester 1)*

### What the agent builds
- `apps/dashboard/`: a simple React or Next.js page (or even a Flask-rendered page for speed) showing
  current risk tier, latest sensor readings, camera thumbnail, and battery status, polling the
  gateway's API.

### Manual step: none required — this runs entirely from data the gateway already has.

---

## Phase 8 — Fusion Refinement *(Semester 2)*

### What the agent builds
- Extends `fusion.py` with configurable weights loaded from a config file, and a small script to sweep
  weight combinations against a labeled validation set to help you choose good defaults.

### Manual step: labeling validation data
Go through a sample of collected sensor+image+weather snapshots and manually tag each as
Safe/Warning/High Risk/Fire — this judgment call has to be made by a person, not the agent. A simple
CSV or spreadsheet of `timestamp, your_label` is enough.

---

## Phase 9 — Full Dashboard *(Semester 2)*

### What the agent builds
- Adds a live map (e.g. using Leaflet) showing the node's location and the cached deforestation risk
  layer as a colored overlay, historical trend charts, and alert notifications.

### Manual step: none beyond obtaining a free Leaflet/OpenStreetMap tile source (no API key needed for
basic OSM tiles).

---

## Phase 10 — Validation, Testing & Documentation *(Semester 2)*

### What the agent builds
- Test scripts computing accuracy/precision/recall/false-alarm rate against your labeled validation
  set, and a summary report generator.

### Manual step
- Physically observe the hardware node over a test period (e.g. a controlled small-scale heat/smoke
  test, done safely and with supervision) to generate real "positive" events to validate against —
  synthetic/historical data alone won't fully prove the physical system works. Plan this with your
  supervisor for safety.
- Write the final report narrative, defend design decisions, and prepare the presentation — this is
  your academic work, not something to hand fully to an agent.

---

## Appendix: Manual-Only Task Checklist

Quick reference of everything that needs a human, not an agent, across the whole project:

- [ ] Create GitHub repo and folder structure
- [ ] Download sensor training dataset from Kaggle/UCI (account + browser download)
- [ ] Sanity-check the `prithivMLmods/Forest-Fire-Detection` model loads correctly (one-time local run, no account/download needed)
- [ ] Create and authenticate Google Earth Engine account
- [ ] Purchase all hardware components
- [ ] Wire sensors, camera, solar panel, charge controller, LiFePO4 battery
- [ ] Flash ESP32/ESP32-CAM firmware via USB
- [ ] Flash and configure Raspberry Pi OS
- [ ] Sign up for weather API key
- [ ] Manually label validation data for fusion tuning
- [ ] Supervise/run physical test events for validation
- [ ] Write final report narrative and prepare presentation

Everything not on this list — model training code, fusion logic, gateway server, dashboard, firmware
logic itself (not the flashing), NDVI computation script — can be handed to the AI coding agent phase
by phase, referencing this document.
