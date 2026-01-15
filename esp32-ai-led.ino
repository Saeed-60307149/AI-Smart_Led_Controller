// ======================
// ESP32 + ThingsBoard + AI auto-switch (analogWrite version)
// ======================

#include <WiFi.h>
#include <HTTPClient.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ---------- WiFi ----------
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// ---------- Flask Server ----------
const char* flaskServer = "http://192.168.1.100:5000/predict";
const char* flaskStatus = "http://192.168.1.100:5000/status";

// ---------- ThingsBoard ----------
const char* tbServer = "demo.thingsboard.io";
const int tbPort = 1883;
const char* tbToken = "YOUR_THINGSBOARD_DEVICE_TOKEN";

// ---------- MQTT ----------
WiFiClient espClient;
PubSubClient tbClient(espClient);

// ---------- Sensors ----------
#define LDR_PIN 34
#define PIR_PIN 27
#define LED_PIN 2  // Built-in LED on most ESP32 boards

// ---------- Variables ----------
float ldrValue = 0;
int motionValue = 0;
int ledValue = 0;
bool aiMode = false;

// ---------- MQTT Callback ----------
void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  Serial.println("MQTT Shared Attribute: " + message);

  StaticJsonDocument<200> doc;
  deserializeJson(doc, message);

  if (doc.containsKey("shared") && doc["shared"].containsKey("led")) {
    ledValue = doc["shared"]["led"];
    Serial.println("Updated Manual LED from TB: " + String(ledValue));
  }
}

// ---------- Setup ----------
void setup() {
  Serial.begin(115200);
  pinMode(LDR_PIN, INPUT);
  pinMode(PIR_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);

  // THIS IS THE MAGIC FIX FOR analogWrite()
  // Must be AFTER pinMode and BEFORE WiFi.begin()
  analogWrite(LED_PIN, 0);  // Initialize PWM

  connectWiFi();
  tbClient.setServer(tbServer, tbPort);
  tbClient.setCallback(onMqttMessage);
  connectThingsBoard();

  Serial.println("System Ready (analogWrite version)");
}

// ---------- Loop ----------
void loop() {
  if (!tbClient.connected()) connectThingsBoard();
  tbClient.loop();

  ldrValue = analogRead(LDR_PIN);
  motionValue = digitalRead(PIR_PIN);

  static unsigned long lastModelCheck = 0;
  if (millis() - lastModelCheck > 30000) {
    checkAIModel();
    lastModelCheck = millis();
  }

  if (aiMode) {
    getAIPrediction();
  }

  analogWrite(LED_PIN, ledValue);  // WORKS PERFECTLY NOW
  sendTelemetry();

  delay(5000);
}

// ---------- Connect WiFi ----------
void connectWiFi() {
  Serial.print("Connecting to WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(500);
  }
  Serial.println("\nWiFi connected.");
}

// ---------- Connect to ThingsBoard ----------
void connectThingsBoard() {
  while (!tbClient.connected()) {
    Serial.print("Connecting to ThingsBoard...");
    if (tbClient.connect("ESP32Client", tbToken, NULL)) {
      Serial.println("connected.");
      tbClient.subscribe("v1/devices/me/attributes");
    } else {
      Serial.print("failed, rc=");
      Serial.println(tbClient.state());
      delay(5000);
    }
  }
}

// ---------- Send Telemetry ----------
void sendTelemetry() {
  StaticJsonDocument<200> data;
  data["ldr"] = ldrValue;
  data["motion"] = motionValue;
  data["led"] = ledValue;
  data["mode"] = aiMode ? "AI" : "Manual";

  char payload[200];
  serializeJson(data, payload);

  tbClient.publish("v1/devices/me/telemetry", payload);
  Serial.println("Sent: " + String(payload));
}

// ---------- Check AI Model ----------
void checkAIModel() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(flaskStatus);
    int code = http.GET();
    if (code == 200) {
      String resp = http.getString();
      aiMode = (resp == "ready");
    }
    http.end();
  }
  Serial.println(aiMode ? "AI Mode Active" : "Manual Mode");
}

// ---------- Get AI Prediction ----------
void getAIPrediction() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(flaskServer);
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<128> doc;
    doc["ldr"] = ldrValue;
    doc["motion"] = motionValue;

    String body;
    serializeJson(doc, body);
    int code = http.POST(body);

    if (code == 200) {
      String resp = http.getString();
      StaticJsonDocument<64> result;
      deserializeJson(result, resp);
      ledValue = result["led"];
      Serial.println("Predicted LED: " + String(ledValue));
    }
    http.end();
  }
}