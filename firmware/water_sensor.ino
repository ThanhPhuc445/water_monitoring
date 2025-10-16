#include <WiFi.h>
#include <HTTPClient.h>
#include "DFRobot_ESP_PH.h"
#include <EEPROM.h>
#include <Arduino.h>
#include <math.h>

// ========================== WIFI CONFIG ==========================
const char* ssid       = "Bong Food & Drink";
const char* password   = "trasuabong";
// Endpoint sử dụng Strict WHO Labeler (rule-based, không cần ML model)
const char* serverName = "http://192.168.110.231:8000/api/upload-reading-strict/";
// Server config
const char* serverURL = "http://192.168.110.231:8000";  // Thay bằng IP của Django server
const char* uploadEndpoint = "/api/upload-reading-strict/";  // Sử dụng strict labeler
const char* statusEndpoint = "/api/ai-status/";

// ========================== PIN CONFIG ==========================
#define PH_PIN   35   // pH sensor
#define NTU_PIN  33   // Turbidity sensor
#define TDS_PIN  34   // TDS sensor

// ========================== PH SENSOR ==========================
DFRobot_ESP_PH ph;
#define ESPADC     4096.0
#define ESPVOLTAGE 3300.0
float phVoltage_mV = 0, pHValue = 0;
float waterTempC = 25.0;

// ========================== TDS SENSOR ==========================
namespace device {
  float aref = 3.3; // ADC reference
}
namespace sensor {
  float ec = 0;
  unsigned int tds = 0;
  float ecCalibration = 1.112; // calibration factor
}
float rawEc = 0;

// ========================== NTU SENSOR ==========================
float ntuValue = 0;
float ntu = 0;
float rawClear = 2165;  // giá trị ADC khi nước cất (trong)
float rawTurbid = 1275; // giá trị ADC khi nước đục
String ntuStatus = "";

// ========================== TIME VARIABLES ==========================
unsigned long t_lastSend = 0;
unsigned long t_lastPrint = 0;
unsigned long t_lastPH = 0;
unsigned long t_lastNTU = 0;
unsigned long t_lastTDS = 0;

// ========================== FUNCTION ==========================
float mapfloat(float x, float in_min, float in_max, float out_min, float out_max) {
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

// ========================== SETUP ==========================
void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  WiFi.begin(ssid, password);
  Serial.print("Dang ket noi WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
  Serial.println("=====================================");

  EEPROM.begin(32);
  ph.begin();

  pinMode(TDS_PIN, INPUT);
  pinMode(PH_PIN, INPUT);
  pinMode(NTU_PIN, INPUT);
}

// ========================== LOOP ==========================
void loop() {
  unsigned long now = millis();

  // ----------------- ĐO pH -----------------
  if (now - t_lastPH >= 1000) {
    t_lastPH = now;
    float phADC = analogRead(PH_PIN);
    phVoltage_mV = (phADC / ESPADC) * ESPVOLTAGE; // mV
    pHValue = ph.readPH(phVoltage_mV, waterTempC);
    ph.calibration(phVoltage_mV, waterTempC);
  }

  // ----------------- ĐO NTU -----------------
  if (now - t_lastNTU >= 1000) {
    t_lastNTU = now;
    int turbidityValue = analogRead(NTU_PIN);
    ntu = (turbidityValue - 2221.4) / 81.43;  // công thức đã hiệu chỉnh
  }

  // ----------------- ĐO TDS -----------------
  if (now - t_lastTDS >= 1000) {
    t_lastTDS = now;
    rawEc = analogRead(TDS_PIN) * device::aref / 4095.0;

    float offset = 0.14;
    sensor::ec = (rawEc * sensor::ecCalibration) - offset;
    if (sensor::ec < 0) sensor::ec = 0;

    sensor::tds = (133.42 * pow(sensor::ec, 3)
                - 255.86 * pow(sensor::ec, 2)
                + 857.39 * sensor::ec) * 0.5;
  }

  // ----------------- IN RA SERIAL -----------------
  if (now - t_lastPrint >= 1000) {
    t_lastPrint = now;
    Serial.print("pH: ");  Serial.print(pHValue, 2);
    Serial.print(" | NTU: "); Serial.print(ntu, 2);
    Serial.print(" ("); Serial.print(ntuStatus); Serial.print(")");
    Serial.print(" | TDS: "); Serial.print(sensor::tds); Serial.println(" ppm");
  }

  // ----------------- GỬI LÊN SERVER -----------------
  if (now - t_lastSend >= 3000) {
    t_lastSend = now;

    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(serverName);
      http.addHeader("Content-Type", "application/x-www-form-urlencoded");

      String postData = "ph=" + String(pHValue, 2)
                      + "&ntu=" + String(ntu, 2)
                      + "&tds=" + String((float)sensor::tds, 0);
      Serial.print("POST data: ");
      Serial.println(postData);

      int httpResponseCode = http.POST(postData);
      Serial.print("Response code: ");
      Serial.println(httpResponseCode);

      if (httpResponseCode == 200) {
        String response = http.getString();
        Serial.println("=> Gui du lieu THANH CONG");
        Serial.println("Response from server:");
        Serial.println(response);
        
        // Parse kết quả gắn nhãn từ response
        // Tìm "is_safe":true hoặc "is_safe":false
        if (response.indexOf("\"is_safe\":true") > 0) {
          Serial.println("✅ NUOC SACH - An toan de su dung");
        } else if (response.indexOf("\"is_safe\":false") > 0) {
          Serial.println("❌ NUOC BAN - KHONG an toan");
        }
        
        // Tìm label
        if (response.indexOf("\"label\":\"clean\"") > 0) {
          Serial.println("WHO Label: CLEAN");
        } else if (response.indexOf("\"label\":\"dirty\"") > 0) {
          Serial.println("WHO Label: DIRTY");
        }
        
        // Có thể thêm code để bật LED dựa trên kết quả
        // if (response.indexOf("\"is_safe\":false") > 0) {
        //   digitalWrite(LED_RED_PIN, HIGH);  // Bật LED đỏ
        //   digitalWrite(LED_GREEN_PIN, LOW);
        // } else {
        //   digitalWrite(LED_RED_PIN, LOW);
        //   digitalWrite(LED_GREEN_PIN, HIGH); // Bật LED xanh
        // }
      } else {
        Serial.println("=> Loi khi gui du lieu");
      }
      http.end();
    } else {
      Serial.println("WiFi mat ket noi, bo qua lan gui nay.");
    }
  }
    }
  }
}
