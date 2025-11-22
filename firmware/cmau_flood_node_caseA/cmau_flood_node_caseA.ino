/*
 * Cà Mau Flood Node Case A (H–Q)
 * ESP8266/ESP32 firmware for JSN-SR04T (ultrasonic) and YL-83 (rain binary)
 * Telemetry via MQTT or HTTP in JSON schema.
 *
 * Pins:
 *  - ESP8266 (NodeMCU): TRIG=D5(GPIO14), ECHO=D6(GPIO12) [Use voltage divider 5V->3.3V], RAIN=D7(GPIO13)
 *  - ESP32: TRIG=18, ECHO=19 [Use divider], RAIN=21
 */

#include <Arduino.h>

// --- Board selection
#if defined(ESP8266)
  #include <ESP8266WiFi.h>
  #define PIN_TRIG D5
  #define PIN_ECHO D6
  #define PIN_RAIN D7
#elif defined(ESP32)
  #include <WiFi.h>
  #define PIN_TRIG 18
  #define PIN_ECHO 19
  #define PIN_RAIN 21
#else
  #error "Only ESP8266/ESP32 supported"
#endif

#include <time.h>

// Protocol selection
#define PROTOCOL_MQTT 1  // 1=MQTT, 0=HTTP

#if PROTOCOL_MQTT
  #include <PubSubClient.h>
#else
  #if defined(ESP8266)
    #include <ESP8266HTTPClient.h>
  #else
    #include <HTTPClient.h>
  #endif
#endif

#include <ArduinoJson.h>

// --- Config ---
const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASS";
const char* NODE_ID = "CM-01";
const char* BROKER_HOST = "192.168.1.10";
const uint16_t BROKER_PORT = 1883;
const char* HTTP_INGEST = "http://192.168.1.10:8088/ingest";
const float SENSOR_HEIGHT_ABOVE_CREST_M = 0.95; // optional meta

// NTP TZ +07:00
const long TZ_OFFSET = 7 * 3600;
const int   DST_OFFSET = 0;

// Sampling
const uint32_t PING_INTERVAL_MS = 10000; // 10s
const uint32_t UPLOAD_INTERVAL_MS = 60000; // 60s

// --- Globals ---
#if PROTOCOL_MQTT
WiFiClient espClient;
PubSubClient mqtt(espClient);
#endif

float samples[5];
uint8_t samp_idx = 0;
uint32_t last_ping = 0;
uint32_t last_upload = 0;

void wifi_connect() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
}

void ntp_config() {
  configTime(TZ_OFFSET, DST_OFFSET, "pool.ntp.org", "time.nist.gov");
}

String iso8601_local() {
  time_t now = time(nullptr);
  struct tm info;
  localtime_r(&now, &info);
  char buf[40];
  // ISO-8601 with offset +07:00; time.h localtime uses TZ offset already applied
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S+07:00", &info);
  return String(buf);
}

float measure_distance_m() {
  // JSN-SR04T ultrasonic
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);
  unsigned long duration = pulseIn(PIN_ECHO, HIGH, 30000); // up to ~5m
  // speed of sound ~343 m/s -> 29.1 us per cm; distance = duration * 0.0343 / 2 m
  float dist_m = (duration * 0.0343f) / 2000.0f;
  return dist_m;
}

float median_of_5(float* arr) {
  float a[5];
  for (int i=0;i<5;i++) a[i]=arr[i];
  // simple insertion sort
  for (int i=1;i<5;i++) {
    float key=a[i]; int j=i-1; while (j>=0 && a[j]>key){a[j+1]=a[j]; j--; } a[j+1]=key;
  }
  return a[2];
}

void publish_payload(float dist_med, int rain_bin, float batt_v) {
  StaticJsonDocument<256> doc;
  doc["ts"] = iso8601_local();
  doc["node_id"] = NODE_ID;
  JsonObject s = doc.createNestedObject("s");
  s["dist_m"] = dist_med;
  s["rain_bin"] = rain_bin;
  s["batt_v"] = batt_v;
  JsonObject meta = doc.createNestedObject("meta");
  meta["sensor_height_above_crest_m"] = SENSOR_HEIGHT_ABOVE_CREST_M;
  doc["ver"] = 2;

  char buf[512];
  size_t n = serializeJson(doc, buf, sizeof(buf));

#if PROTOCOL_MQTT
  if (!mqtt.connected()) {
    mqtt.setServer(BROKER_HOST, BROKER_PORT);
    String clientId = String("cmau-node-") + String(NODE_ID);
    mqtt.connect(clientId.c_str());
  }
  String topic = String("cmau/flood/nodes/") + NODE_ID + String("/telemetry");
  mqtt.publish(topic.c_str(), buf, n);
#else
  HTTPClient http;
  http.begin(HTTP_INGEST);
  http.addHeader("Content-Type", "application/json");
  http.POST((uint8_t*)buf, n);
  http.end();
#endif
}

int read_rain_bin() {
  int v = digitalRead(PIN_RAIN);
  // Some modules are active-low; normalize to 1 for rain
  return v == LOW ? 1 : 0;
}

float read_batt_v() {
#ifdef ESP8266
  // If wired to A0 with divider for Li-ion; otherwise return dummy
  return 4.2f;
#else
  return 4.0f;
#endif
}

void setup() {
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_RAIN, INPUT);
  wifi_connect();
  ntp_config();
}

void loop() {
  uint32_t now = millis();
  if (now - last_ping >= PING_INTERVAL_MS) {
    last_ping = now;
    float d = measure_distance_m();
    samples[samp_idx % 5] = d;
    samp_idx++;
  }
  if (now - last_upload >= UPLOAD_INTERVAL_MS) {
    last_upload = now;
    float dist_med = median_of_5(samples);
    int rain = read_rain_bin();
    float batt = read_batt_v();
    publish_payload(dist_med, rain, batt);
  }
#if PROTOCOL_MQTT
  mqtt.loop();
#endif
}
