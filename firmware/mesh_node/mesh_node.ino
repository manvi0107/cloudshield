// CloudShield mesh node (ESP32). Solar cell across a ~10 ohm shunt -> GPIO34 (keep the shunt voltage below 3.3 V).
// USB_ONLY 1: print readings over USB serial only (use the dashboard's "Connect USB" button, no Wi-Fi or broker needed).
// USB_ONLY 0: also publish to MQTT (node/<id>/reading) so the backend and dashboard show the node as hardware.
#define USB_ONLY 1
#include <WiFi.h>
#include <PubSubClient.h>
const char *SSID = "YOUR_WIFI", *PASS = "YOUR_PASS", *BROKER = "192.168.1.10";
const char *ID = "mesh-0";  // mesh-0 .. mesh-4, matching the node's position on the dashboard map
const int PIN = 34;
WiFiClient wc; PubSubClient mq(wc);
float vmax = 1; unsigned long lastPub = 0, lastBeat = 0, lastTry = 0;

void setup() {
  Serial.begin(115200);
#if !USB_ONLY
  WiFi.begin(SSID, PASS);
  while (WiFi.status() != WL_CONNECTED) delay(300);
  mq.setServer(BROKER, 1883);
#endif
}
void loop() {
  float raw = analogRead(PIN);
  vmax = max(raw, vmax * 0.9995f);  // slow-decay clear-sky maximum
  float v = raw / vmax;             // normalised irradiance 0..1
  if (millis() - lastPub >= 100) {  // 10 Hz
    lastPub = millis();
    Serial.printf("{\"id\":\"%s\",\"v\":%.3f,\"fw\":\"1.1\"}\n", ID, v);
#if !USB_ONLY
    if (mq.connected()) { char t[32], b[48]; snprintf(t, 32, "node/%s/reading", ID); snprintf(b, 48, "{\"v\":%.3f}", v); mq.publish(t, b); }
#endif
  }
#if !USB_ONLY
  if (!mq.connected()) { if (millis() - lastTry > 3000) { lastTry = millis(); mq.connect(ID); } }
  else {
    mq.loop();
    if (millis() - lastBeat >= 5000) {
      lastBeat = millis(); char t[32], b[96];
      snprintf(t, 32, "node/%s/status", ID); snprintf(b, 96, "{\"fw\":\"1.1\",\"type\":\"mesh\",\"rssi\":%d}", WiFi.RSSI()); mq.publish(t, b);
    }
  }
#endif
}
