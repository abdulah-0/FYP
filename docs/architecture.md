# System Architecture & Technical Specifications

## 1. System Overview
The Forest Fire Guardian system is designed for early wildfire detection and situational awareness. It integrates four complementary modalities:

1. **IoT Sensor Node (Edge Telemetry)**: Temperature, relative humidity, MQ-2 gas/smoke concentration, flame detector state.
2. **Vision Node (Edge CV Inference)**: Vision classifier evaluating optical camera frames for flame and smoke signatures.
3. **Meteorological Risk (Weather API)**: Ambient wind speed, rain probability, and external temperature to evaluate rate-of-spread conditions.
4. **Deforestation Risk Layer (Remote Sensing)**: Sentinel-2 NDVI (Normalized Difference Vegetation Index) mapping dried vegetation and biomass vulnerability.

---

## 2. Multi-Modal Fusion Engine Formula
The edge gateway combines normalized risk probabilities $[0.0, 1.0]$ using a weighted fusion model:

$$\text{Confidence Score} = (0.40 \times S_{\text{sensor}}) + (0.30 \times S_{\text{vision}}) + (0.20 \times S_{\text{weather}}) + (0.10 \times S_{\text{deforestation}})$$

### Threat Severity Tiers
- 🟢 **Safe (`0.00 - 0.29`)**: Normal forest conditions.
- 🟡 **Warning (`0.30 - 0.59`)**: Elevated temperature or low humidity, dry vegetation.
- 🟠 **High Risk (`0.60 - 0.79`)**: Elevated smoke/gas + dry winds, potential ignition impending.
- 🔴 **Fire Detected (`0.80 - 1.00`)**: Active flame detection and confirmed thermal/vision signatures.

---

## 3. Computer Vision Model Specification
- **Primary Model**: `prithivMLmods/Forest-Fire-Detection`
- **Base Architecture**: SigLIP2 (`google/siglip2-base-patch16-512`)
- **License**: Apache 2.0 (Publicly available on Hugging Face Hub)
- **Classes**: `Fire`, `Normal`, `Smoke`
- **Reported Accuracy**: ~99.52%

---

## 4. Hardware Node Specifications
- **Microcontrollers**: ESP32 Dev Module (WROOM-32), ESP32-CAM (AI-Thinker module)
- **Sensors**:
  - DHT22 (Temperature & Humidity)
  - MQ-2 (Combustible Gas & Smoke)
  - IR Flame Sensor (Digital/Analog flame threshold)
- **Power System**: 5-10W Solar Panel, LiFePO4 Solar Charge Controller, LiFePO4 3.2V / 12.8V Battery Cell
- **Gateway**: Raspberry Pi 3B+ / 4B running Linux & Python Edge Service
