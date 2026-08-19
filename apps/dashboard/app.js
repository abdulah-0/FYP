// Forest Fire Guardian - Edge Dashboard Application Logic

let telemetryChart = null;
const POLLING_INTERVAL_MS = 2000;
let apiBaseUrl = localStorage.getItem("fg_gateway_url") || "";

// Initialize Dashboard
document.addEventListener("DOMContentLoaded", () => {
  initChart();
  setupSettingsModal();
  fetchDashboardData();
  setInterval(fetchDashboardData, POLLING_INTERVAL_MS);

  document.getElementById("btn-refresh").addEventListener("click", () => {
    fetchDashboardData(true);
  });
});

function setupSettingsModal() {
  const modal = document.getElementById("settings-modal");
  const btnSettings = document.getElementById("btn-settings");
  const btnClose = document.getElementById("btn-close-settings");
  const btnSave = document.getElementById("btn-save-gateway-url");
  const btnReset = document.getElementById("btn-reset-gateway-url");
  const inputUrl = document.getElementById("input-gateway-url");

  inputUrl.value = apiBaseUrl;

  btnSettings.addEventListener("click", () => {
    inputUrl.value = apiBaseUrl;
    modal.classList.remove("hidden");
  });

  btnClose.addEventListener("click", () => modal.classList.add("hidden"));

  btnSave.addEventListener("click", () => {
    let val = inputUrl.value.trim();
    if (val.endsWith("/")) val = val.slice(0, -1);
    apiBaseUrl = val;
    localStorage.setItem("fg_gateway_url", apiBaseUrl);
    modal.classList.add("hidden");
    fetchDashboardData(true);
  });

  btnReset.addEventListener("click", () => {
    apiBaseUrl = "";
    localStorage.removeItem("fg_gateway_url");
    inputUrl.value = "";
    modal.classList.add("hidden");
    fetchDashboardData(true);
  });
}

function getApiUrl(path) {
  return `${apiBaseUrl}${path}`;
}

// Initialize Chart.js Real-time Telemetry Graph
function initChart() {
  const ctx = document.getElementById("telemetryChart").getContext("2d");
  telemetryChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Temperature (°C)",
          data: [],
          borderColor: "#f97316",
          backgroundColor: "rgba(249, 115, 22, 0.1)",
          borderWidth: 2,
          tension: 0.3,
          yAxisID: "y"
        },
        {
          label: "Humidity (%)",
          data: [],
          borderColor: "#06b6d4",
          backgroundColor: "rgba(6, 182, 212, 0.1)",
          borderWidth: 2,
          tension: 0.3,
          yAxisID: "y"
        },
        {
          label: "MQ-2 Gas (ppm)",
          data: [],
          borderColor: "#eab308",
          backgroundColor: "rgba(234, 179, 8, 0.1)",
          borderWidth: 2,
          borderDash: [4, 4],
          tension: 0.3,
          yAxisID: "y1"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          labels: { color: "#94a3b8", font: { family: "Inter", size: 12 } }
        }
      },
      scales: {
        x: {
          grid: { color: "rgba(51, 65, 85, 0.3)" },
          ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 10 } }
        },
        y: {
          type: "linear",
          display: true,
          position: "left",
          min: 0,
          max: 60,
          title: { display: true, text: "Temp / RH", color: "#64748b" },
          grid: { color: "rgba(51, 65, 85, 0.3)" },
          ticks: { color: "#94a3b8" }
        },
        y1: {
          type: "linear",
          display: true,
          position: "right",
          min: 0,
          max: 600,
          title: { display: true, text: "Gas (ppm)", color: "#eab308" },
          grid: { drawOnChartArea: false },
          ticks: { color: "#eab308" }
        }
      }
    }
  });
}

// Demo fallback data when gateway is offline or previewing on cloud without Raspberry Pi
let demoHistory = [];
function generateDemoData() {
  const now = Date.now() / 1000;
  if (demoHistory.length === 0) {
    for (let i = 20; i >= 0; i--) {
      demoHistory.push({
        timestamp: now - (i * 5),
        telemetry: {
          temperature_c: 24.5 + Math.sin(i * 0.5) * 2,
          humidity_percent: 58.0 + Math.cos(i * 0.5) * 4,
          gas_ppm: 22.0 + Math.random() * 5,
          smoke_ppm: 12.0,
          flame_detected: false
        }
      });
    }
  }

  return {
    fusion: {
      fusion: {
        confidence_score: 0.142,
        severity_tier: "Safe",
        tier_badge: "🟢",
        tier_id: 0,
        critical_alert: false,
        is_override: false,
        sub_scores: {
          sensor_score: 0.128,
          vision_score: 0.050,
          weather_score: 0.280,
          deforestation_score: 0.250
        }
      },
      weather: {
        temperature_c: 32.0,
        humidity_percent: 42.0,
        wind_speed_kmh: 14.5,
        rain_mm: 0.0,
        condition: "Clear Sky / Light Breeze",
        source: "OpenWeatherMap Live API"
      },
      deforestation: {
        ndvi: 0.478,
        vegetation_desc: "Dense Healthy Forest Canopy",
        matched_lat: 33.74,
        matched_lon: 73.02
      }
    },
    latest: {
      sensor: {
        node_id: "ESP32_SENSOR_NODE_01",
        latitude: 33.7431,
        longitude: 73.0232,
        telemetry: {
          temperature_c: 25.4,
          humidity_percent: 56.2,
          gas_ppm: 24.8,
          smoke_ppm: 14.1,
          flame_detected: false
        },
        power: {
          battery_voltage_v: 3.34,
          battery_percent: 85,
          solar_charging: true
        }
      },
      vision: {
        node_id: "ESP32_CAM_01",
        predicted_label: "Normal",
        confidence: 0.992,
        latency_ms: 45.2
      }
    },
    history: { records: demoHistory }
  };
}

// Fetch all live gateway endpoints
async function fetchDashboardData(manual = false) {
  try {
    const [resFusion, resLatest, resHistory] = await Promise.all([
      fetch(getApiUrl("/api/v1/fusion/score")),
      fetch(getApiUrl("/api/v1/telemetry/latest")),
      fetch(getApiUrl("/api/v1/telemetry/history?limit=30"))
    ]);

    if (resFusion.ok && resLatest.ok) {
      const fusionData = await resFusion.json();
      const latestData = await resLatest.json();
      const historyData = resHistory.ok ? await resHistory.json() : { records: [] };

      updateFusionBanner(fusionData.fusion);
      updatePillars(fusionData, latestData);
      updateHardwareStatus(latestData.sensor);
      updateChart(historyData.records);

      setConnectionStatus(true);
    } else {
      useDemoFallback();
    }
  } catch (err) {
    useDemoFallback();
  }
}

function useDemoFallback() {
  const demo = generateDemoData();
  updateFusionBanner(demo.fusion.fusion);
  updatePillars(demo.fusion, demo.latest);
  updateHardwareStatus(demo.latest.sensor);
  updateChart(demo.history.records);
  setConnectionStatus(false);
}

// Update Master Fusion Banner
function updateFusionBanner(fusion) {
  const banner = document.getElementById("fusion-banner");
  const badge = document.getElementById("tier-badge");
  const label = document.getElementById("tier-label");
  const desc = document.getElementById("tier-desc");
  const confScore = document.getElementById("confidence-score");
  const confBar = document.getElementById("confidence-bar");
  const overrideBadge = document.getElementById("badge-override");

  const scorePct = (fusion.confidence_score * 100).toFixed(1);
  confScore.textContent = `${scorePct}%`;
  confBar.style.width = `${scorePct}%`;

  badge.textContent = fusion.tier_badge;
  label.textContent = fusion.severity_tier;

  if (fusion.is_override) {
    overrideBadge.classList.remove("hidden");
  } else {
    overrideBadge.classList.add("hidden");
  }

  // Reset classes
  banner.className = "glass-card p-6 rounded-2xl border transition-all duration-500";

  if (fusion.tier_id === 3) { // Fire Detected
    banner.classList.add("fire-alert-pulse");
    desc.textContent = "CRITICAL ALERT: Active flame / critical combustion gas signature confirmed. Emergency protocols active.";
    confScore.className = "text-3xl font-bold font-mono text-red-400";
    confBar.className = "bg-red-500 h-2 rounded-full transition-all duration-500";
  } else if (fusion.tier_id === 2) { // High Risk
    banner.classList.add("warning-pulse");
    desc.textContent = "HIGH WILDFIRE THREAT: Thermal, gas, or dried vegetation indices suggest imminent fire risk.";
    confScore.className = "text-3xl font-bold font-mono text-amber-400";
    confBar.className = "bg-amber-500 h-2 rounded-full transition-all duration-500";
  } else if (fusion.tier_id === 1) { // Warning
    banner.classList.add("border-amber-500/40", "bg-gradient-to-r", "from-amber-950/20", "to-slate-900/60");
    desc.textContent = "ELEVATED CONDITIONS: Low humidity or high ambient temperatures detected.";
    confScore.className = "text-3xl font-bold font-mono text-amber-300";
    confBar.className = "bg-amber-400 h-2 rounded-full transition-all duration-500";
  } else { // Safe
    banner.classList.add("border-emerald-500/30", "bg-gradient-to-r", "from-emerald-950/40", "via-slate-900/60", "to-slate-900/40");
    desc.textContent = "Normal environmental parameters across IoT ground sensors, optical vision classifier, atmospheric conditions, and satellite vegetation index.";
    confScore.className = "text-3xl font-bold font-mono text-emerald-400";
    confBar.className = "bg-emerald-500 h-2 rounded-full transition-all duration-500";
  }
}

// Update 4 Modality Pillars
function updatePillars(fusionData, latestData) {
  const sub = fusionData.fusion.sub_scores;

  // 1. Sensor Pillar
  document.getElementById("score-sensor").textContent = sub.sensor_score.toFixed(3);
  document.getElementById("bar-sensor").style.width = `${(sub.sensor_score * 100).toFixed(1)}%`;

  if (latestData.sensor && latestData.sensor.telemetry) {
    const tel = latestData.sensor.telemetry;
    document.getElementById("val-temp").textContent = `${tel.temperature_c.toFixed(1)} °C`;
    document.getElementById("val-rh").textContent = `${tel.humidity_percent.toFixed(1)} %`;
    document.getElementById("val-gas").textContent = `${tel.gas_ppm.toFixed(1)} ppm`;

    const flameEl = document.getElementById("val-flame");
    if (tel.flame_detected) {
      flameEl.textContent = "🔥 FLAME DETECTED";
      flameEl.className = "font-mono text-red-400 font-bold animate-pulse";
    } else {
      flameEl.textContent = "Normal (No Flame)";
      flameEl.className = "font-mono text-emerald-400 font-medium";
    }
  }

  // 2. Vision Pillar
  document.getElementById("score-vision").textContent = sub.vision_score.toFixed(3);
  document.getElementById("bar-vision").style.width = `${(sub.vision_score * 100).toFixed(1)}%`;

  if (latestData.vision) {
    const vis = latestData.vision;
    const visClassEl = document.getElementById("val-vis-class");
    visClassEl.textContent = vis.predicted_label;
    if (vis.predicted_label === "Fire") {
      visClassEl.className = "font-mono text-red-400 font-bold";
    } else if (vis.predicted_label === "Smoke") {
      visClassEl.className = "font-mono text-amber-400 font-semibold";
    } else {
      visClassEl.className = "font-mono text-emerald-400 font-semibold";
    }

    document.getElementById("val-vis-conf").textContent = `${(vis.confidence * 100).toFixed(1)}%`;
    document.getElementById("val-vis-lat").textContent = `${vis.latency_ms} ms`;
    document.getElementById("cam-node-id").textContent = vis.node_id || "ESP32_CAM_01";
  }

  // Refresh image timestamp
  const imgEl = document.getElementById("camera-frame");
  imgEl.src = `${getApiUrl("/api/v1/telemetry/camera/latest_image")}?t=${new Date().getTime()}`;
  document.getElementById("cam-timestamp").textContent = new Date().toLocaleTimeString();

  // 3. Weather Pillar
  document.getElementById("score-weather").textContent = sub.weather_score.toFixed(3);
  document.getElementById("bar-weather").style.width = `${(sub.weather_score * 100).toFixed(1)}%`;
  if (fusionData.weather) {
    const w = fusionData.weather;
    document.getElementById("val-wind").textContent = `${w.wind_speed_kmh} km/h`;
    document.getElementById("val-rain").textContent = `${w.rain_mm} mm`;
    document.getElementById("val-cond").textContent = w.condition;
    document.getElementById("val-w-source").textContent = w.source;
  }

  // 4. Deforestation Pillar
  document.getElementById("score-deforest").textContent = sub.deforestation_score.toFixed(3);
  document.getElementById("bar-deforest").style.width = `${(sub.deforestation_score * 100).toFixed(1)}%`;
  if (fusionData.deforestation) {
    const d = fusionData.deforestation;
    document.getElementById("val-ndvi").textContent = d.ndvi.toFixed(3);
    document.getElementById("val-canopy").textContent = d.vegetation_desc;
    document.getElementById("val-grid").textContent = `${d.matched_lat}, ${d.matched_lon}`;
  }
}

// Update Hardware Status Card
function updateHardwareStatus(sensorRecord) {
  if (!sensorRecord) return;

  const nodeEl = document.getElementById("node-id-badge");
  nodeEl.textContent = sensorRecord.node_id;

  if (sensorRecord.power) {
    const p = sensorRecord.power;
    document.getElementById("val-vbat").textContent = `${p.battery_voltage_v.toFixed(2)} V`;
    document.getElementById("val-soc").textContent = `${p.battery_percent}%`;
    document.getElementById("bar-soc").style.width = `${p.battery_percent}%`;

    const solarEl = document.getElementById("val-solar");
    if (p.solar_charging) {
      solarEl.innerHTML = `<span>☀️</span><span>Charging (${p.battery_voltage_v > 3.35 ? 'Full' : 'Active'})</span>`;
      solarEl.className = "text-sm font-semibold text-amber-400 mt-1.5 flex items-center space-x-1";
    } else {
      solarEl.innerHTML = `<span>🔋</span><span>Battery Discharge</span>`;
      solarEl.className = "text-sm font-semibold text-slate-400 mt-1.5 flex items-center space-x-1";
    }
  }

  if (sensorRecord.latitude && sensorRecord.longitude) {
    document.getElementById("val-gps").textContent = `${sensorRecord.latitude.toFixed(4)}° N, ${sensorRecord.longitude.toFixed(4)}° E`;
  }
}

// Update Real-Time Telemetry Graph
function updateChart(records) {
  if (!telemetryChart || !records || records.length === 0) return;

  const labels = [];
  const tempData = [];
  const rhData = [];
  const gasData = [];

  records.forEach((r, idx) => {
    const d = new Date(r.timestamp * 1000);
    labels.push(d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    if (r.telemetry) {
      tempData.push(r.telemetry.temperature_c);
      rhData.push(r.telemetry.humidity_percent);
      gasData.push(r.telemetry.gas_ppm);
    }
  });

  telemetryChart.data.labels = labels;
  telemetryChart.data.datasets[0].data = tempData;
  telemetryChart.data.datasets[1].data = rhData;
  telemetryChart.data.datasets[2].data = gasData;
  telemetryChart.update();
}

function setConnectionStatus(online) {
  const dot = document.getElementById("conn-dot");
  const text = document.getElementById("conn-status");
  if (online) {
    dot.className = "w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse";
    text.textContent = apiBaseUrl ? `Connected: ${apiBaseUrl}` : "Live (Local Gateway)";
  } else {
    dot.className = "w-2.5 h-2.5 rounded-full bg-amber-500";
    text.textContent = apiBaseUrl ? "Reconnecting to Gateway..." : "Cloud Preview (Simulated Telemetry)";
  }
}

// Simulated Ingestion for Demo / Supervisor Testing
async function simulateTelemetry(scenario) {
  let payload = {
    node_id: "ESP32_DEMO_NODE",
    seq: Math.floor(Math.random() * 1000),
    timestamp_ms: Date.now(),
    latitude: 33.7431,
    longitude: 73.0232,
    telemetry: {},
    power: { battery_voltage_v: 3.33, battery_percent: 85, solar_charging: true }
  };

  if (scenario === "safe") {
    payload.telemetry = {
      temperature_c: 22.0 + Math.random() * 3,
      humidity_percent: 65.0 + Math.random() * 5,
      gas_ppm: 20.0 + Math.random() * 5,
      smoke_ppm: 10.0 + Math.random() * 3,
      flame_detected: false
    };
  } else if (scenario === "warning") {
    payload.telemetry = {
      temperature_c: 36.0 + Math.random() * 2,
      humidity_percent: 32.0 - Math.random() * 5,
      gas_ppm: 110.0 + Math.random() * 15,
      smoke_ppm: 60.0 + Math.random() * 10,
      flame_detected: false
    };
  } else if (scenario === "fire") {
    payload.telemetry = {
      temperature_c: 48.0 + Math.random() * 5,
      humidity_percent: 12.0,
      gas_ppm: 480.0 + Math.random() * 50,
      smoke_ppm: 350.0 + Math.random() * 40,
      flame_detected: true
    };
  }

  try {
    await fetch(getApiUrl("/api/v1/telemetry/sensor"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    fetchDashboardData(true);
  } catch (err) {
    // In cloud preview fallback mode, append to local demo history
    demoHistory.push({
      timestamp: Date.now() / 1000,
      telemetry: payload.telemetry
    });
    if (demoHistory.length > 30) demoHistory.shift();

    const fusionScores = {
      safe: { score: 0.14, tier: "Safe", badge: "🟢", id: 0, override: false },
      warning: { score: 0.52, tier: "Warning", badge: "🟡", id: 1, override: false },
      fire: { score: 0.95, tier: "Fire Detected", badge: "🔴", id: 3, override: true }
    }[scenario];

    updateFusionBanner({
      confidence_score: fusionScores.score,
      severity_tier: fusionScores.tier,
      tier_badge: fusionScores.badge,
      tier_id: fusionScores.id,
      is_override: fusionScores.override
    });
    updateChart(demoHistory);
  }
}
