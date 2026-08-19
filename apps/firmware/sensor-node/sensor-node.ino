/*
 * Forest Fire Guardian - ESP32 Sensor Node Firmware
 *
 * Sensors:
 *   - DHT22: Temperature (Celsius) & Relative Humidity (%) on GPIO 4
 *   - MQ-2: Combustible Gas & Smoke Concentration (Analog ADC) on GPIO 34
 *   - Flame Sensor: Digital (GPIO 15) & Analog (GPIO 35)
 *   - Battery Monitor: LiFePO4 Battery Voltage (Voltage Divider) on GPIO 32
 *
 * Target: ESP32 Dev Module (WROOM-32)
 * Framework: Arduino / PlatformIO
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

// ================= USER CONFIGURATION =================
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Raspberry Pi Edge Gateway IP & Ingest Endpoint
const char* GATEWAY_HOST  = "192.168.1.100";
const int   GATEWAY_PORT  = 8000;
const char* INGEST_PATH   = "/api/v1/telemetry/sensor";

const char* NODE_ID       = "ESP32_SENSOR_NODE_01";
const float NODE_LAT      = 33.7431; // Margalla Hills Reserve Test Coordinates
const float NODE_LON      = 73.0232;

// Sampling Interval (milliseconds)
const unsigned long SAMPLING_INTERVAL_MS = 5000; // 5 seconds
// ======================================================

// Pin Definitions
#define PIN_DHT           4
#define DHT_TYPE          DHT22
#define PIN_MQ2_ANALOG    34
#define PIN_FLAME_DIGITAL 15
#define PIN_FLAME_ANALOG  35
#define PIN_BATTERY_ADC   32
#define PIN_STATUS_LED    2

DHT dht(PIN_DHT, DHT_TYPE);

unsigned long lastSampleTime = 0;
unsigned long messageSeqNumber = 0;

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.printf("[WiFi] Connecting to %s...", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 20) {
    delay(500);
    Serial.print(".");
    retries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WiFi] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
    digitalWrite(PIN_STATUS_LED, HIGH);
  } else {
    Serial.println("\n[WiFi] Connection timeout. Retrying in next cycle.");
    digitalWrite(PIN_STATUS_LED, LOW);
  }
}

// Convert MQ-2 Raw ADC reading (0-4095) to approximate ppm estimate
float readMQ2GasPpm(int rawAdc) {
  // ADC voltage: 0V to 3.3V
  float voltage = (rawAdc / 4095.0) * 3.3;
  // Approximated calibration curve for LPG/Smoke ppm
  float ppm = pow(10, ((voltage - 0.4) / 0.6) + 1.2);
  return constrain(ppm, 5.0, 2000.0);
}

// Estimate LiFePO4 Battery Voltage & Percentage (1S Cell: 2.8V empty, 3.6V full)
float readBatteryVoltage(int rawAdc) {
  // 1:1 voltage divider (R1=100k, R2=100k -> factor 2.0)
  float pinVoltage = (rawAdc / 4095.0) * 3.3;
  float batteryVoltage = pinVoltage * 2.0;
  return batteryVoltage;
}

int calculateBatteryPercentage(float voltage) {
  // LiFePO4 1S nominal discharge curve: 3.0V (0%) to 3.4V (100%)
  if (voltage >= 3.40) return 100;
  if (voltage <= 3.00) return 0;
  return (int)(((voltage - 3.00) / 0.40) * 100.0);
}

void sendSensorTelemetry() {
  // Read DHT22
  float temperature = dht.readTemperature();
  float humidity    = dht.readHumidity();

  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("[DHT22] Warning: Failed to read from sensor!");
    temperature = 25.0; // Safe fallback
    humidity    = 50.0;
  }

  // Read MQ-2 Gas / Smoke
  int rawMq2 = analogRead(PIN_MQ2_ANALOG);
  float gasPpm = readMQ2GasPpm(rawMq2);
  float smokePpm = gasPpm * 0.75; // Correlated smoke channel

  // Read Flame Sensor
  int flameDigital = digitalRead(PIN_FLAME_DIGITAL); // Active LOW on most modules
  int rawFlameAnalog = analogRead(PIN_FLAME_ANALOG);
  bool flameDetected = (flameDigital == LOW) || (rawFlameAnalog < 1500);

  // Read Battery
  int rawBattery = analogRead(PIN_BATTERY_ADC);
  float batteryVoltage = readBatteryVoltage(rawBattery);
  int batteryPercent = calculateBatteryPercentage(batteryVoltage);

  // Build JSON Payload
  JsonDocument doc;
  doc["node_id"]            = NODE_ID;
  doc["seq"]                = ++messageSeqNumber;
  doc["timestamp_ms"]       = millis();
  doc["latitude"]           = NODE_LAT;
  doc["longitude"]          = NODE_LON;

  JsonObject telemetry = doc["telemetry"].to<JsonObject>();
  telemetry["temperature_c"]     = round(temperature * 10.0) / 10.0;
  telemetry["humidity_percent"]   = round(humidity * 10.0) / 10.0;
  telemetry["gas_ppm"]            = round(gasPpm * 10.0) / 10.0;
  telemetry["smoke_ppm"]          = round(smokePpm * 10.0) / 10.0;
  telemetry["flame_detected"]     = flameDetected;
  telemetry["raw_flame_adc"]      = rawFlameAnalog;

  JsonObject power = doc["power"].to<JsonObject>();
  power["battery_voltage_v"]      = round(batteryVoltage * 100.0) / 100.0;
  power["battery_percent"]        = batteryPercent;
  power["solar_charging"]         = (batteryVoltage > 3.35);

  String payloadStr;
  serializeJson(doc, payloadStr);

  // Send via HTTP POST
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    String url = String("http://") + GATEWAY_HOST + ":" + GATEWAY_PORT + INGEST_PATH;
    http.begin(url);
    http.addHeader("Content-Type", "application/json");

    int httpCode = http.POST(payloadStr);
    if (httpCode > 0) {
      String response = http.getString();
      Serial.printf("[HTTP] POST %d OK. Response: %s\n", httpCode, response.c_str());
    } else {
      Serial.printf("[HTTP] POST failed, error: %s\n", http.errorToString(httpCode).c_str());
    }
    http.end();
  } else {
    Serial.println("[WiFi] Cannot send: WiFi disconnected.");
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== Forest Fire Guardian: ESP32 Sensor Node ===");

  pinMode(PIN_STATUS_LED, OUTPUT);
  pinMode(PIN_FLAME_DIGITAL, INPUT);
  pinMode(PIN_FLAME_ANALOG, INPUT);
  pinMode(PIN_MQ2_ANALOG, INPUT);
  pinMode(PIN_BATTERY_ADC, INPUT);

  analogReadResolution(12); // 12-bit ADC (0-4095)

  dht.begin();
  connectWiFi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  unsigned long currentMillis = millis();
  if (currentMillis - lastSampleTime >= SAMPLING_INTERVAL_MS) {
    lastSampleTime = currentMillis;
    sendSensorTelemetry();
  }

  delay(100);
}
