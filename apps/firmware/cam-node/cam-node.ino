/*
 * Forest Fire Guardian - ESP32-CAM Node Firmware
 *
 * Captures JPEG frames from OV2640 camera module and streams them
 * via HTTP POST to the Edge Gateway for real-time SigLIP2 computer vision inference.
 *
 * Board: AI-Thinker ESP32-CAM
 * Framework: Arduino / PlatformIO
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>

// ================= USER CONFIGURATION =================
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Edge Gateway Configuration
const char* GATEWAY_HOST  = "192.168.1.100";
const int   GATEWAY_PORT  = 8000;
const char* INGEST_PATH   = "/api/v1/telemetry/camera/frame";

const char* NODE_ID       = "ESP32_CAM_NODE_01";
const unsigned long CAPTURE_INTERVAL_MS = 10000; // 10 seconds per frame
// ======================================================

// AI-Thinker ESP32-CAM Pin Mapping
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

#define FLASH_LED_PIN      4
#define STATUS_LED_PIN    33

unsigned long lastCaptureTime = 0;
unsigned long frameCount = 0;

bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    config.frame_size   = FRAMESIZE_VGA;  // 640x480 resolution
    config.jpeg_quality = 12;             // 10-63 (lower = higher quality)
    config.fb_count     = 2;
  } else {
    config.frame_size   = FRAMESIZE_SVGA;
    config.jpeg_quality = 14;
    config.fb_count     = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[Camera] Init failed with error 0x%x\n", err);
    return false;
  }

  // Adjust camera sensor properties
  sensor_t * s = esp_camera_sensor_get();
  if (s != NULL) {
    s->set_brightness(s, 1);     // -2 to 2
    s->set_contrast(s, 1);       // -2 to 2
    s->set_saturation(s, 0);     // -2 to 2
    s->set_special_effect(s, 0); // 0 = No Effect
    s->set_whitebal(s, 1);       // 1 = Auto White Balance
  }

  Serial.println("[Camera] Initialized successfully.");
  return true;
}

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
    digitalWrite(STATUS_LED_PIN, LOW); // Active LOW on ESP32-CAM
  } else {
    Serial.println("\n[WiFi] Failed to connect.");
  }
}

void captureAndSendFrame() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[Camera] Skipping capture: WiFi not connected.");
    return;
  }

  Serial.println("[Camera] Capturing frame...");
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[Camera] Frame capture failed!");
    return;
  }

  frameCount++;
  Serial.printf("[Camera] Frame #%lu captured (%u bytes). Sending to Gateway...\n", frameCount, fb->len);

  HTTPClient http;
  String url = String("http://") + GATEWAY_HOST + ":" + GATEWAY_PORT + INGEST_PATH;
  http.begin(url);
  http.addHeader("Content-Type", "image/jpeg");
  http.addHeader("X-Node-ID", NODE_ID);
  http.addHeader("X-Frame-Index", String(frameCount));
  http.addHeader("X-Timestamp-Ms", String(millis()));

  int httpCode = http.POST(fb->buf, fb->len);
  if (httpCode > 0) {
    String response = http.getString();
    Serial.printf("[HTTP] POST frame %d OK. Server response: %s\n", httpCode, response.c_str());
  } else {
    Serial.printf("[HTTP] POST frame failed, error: %s\n", http.errorToString(httpCode).c_str());
  }

  http.end();
  esp_camera_fb_return(fb); // Release memory buffer
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== Forest Fire Guardian: ESP32-CAM Node ===");

  pinMode(STATUS_LED_PIN, OUTPUT);
  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW);
  digitalWrite(STATUS_LED_PIN, HIGH);

  if (!initCamera()) {
    Serial.println("[Fatal] Camera hardware initialization failed.");
    while (true) { delay(1000); }
  }

  connectWiFi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  unsigned long currentMillis = millis();
  if (currentMillis - lastCaptureTime >= CAPTURE_INTERVAL_MS) {
    lastCaptureTime = currentMillis;
    captureAndSendFrame();
  }

  delay(100);
}
