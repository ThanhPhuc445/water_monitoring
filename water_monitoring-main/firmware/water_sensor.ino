#include <WiFi.h>
#include <HTTPClient.h>
#include "DFRobot_ESP_PH.h"
#include <EEPROM.h>

const char* ssid       = "PHUONG NAM";
const char* password   = "0787767770";
const char* serverName = "http://192.168.1.9:8000/api/upload-reading/";

#define PH_PIN   35 
#define NTU_PIN  33  
#define TDS_PIN  32 

// ========== pH (DFRobot_ESP_PH) ========== 
DFRobot_ESP_PH ph;
#define ESPADC     4096.0  
#define ESPVOLTAGE 3300  
float phVoltage_mV = 0, pHValue = 0;
float waterTempC = 25.0;  

// ========== TDS (SEN0244) ========== 
#define VREF      3.3     
#define SCOUNT    30    
int   tdsBuf[SCOUNT];
int   tdsBufTmp[SCOUNT];
int   tdsIdx = 0;
float tdsAvgVolt = 0, tdsValue = 0;

// ========== NTU ========== 
float rawClear = 3200;
float rawTurbid = 850; 

unsigned long t_lastTdsSample = 0;  
unsigned long t_lastTdsCalc   = 0; 
unsigned long t_lastSend      = 0;  
unsigned long t_lastPH        = 0;  
unsigned long t_lastNTU       = 0;  

int medianFilter(int bArray[], int len) {
  int bTab[len];
  for (int i = 0; i < len; i++) bTab[i] = bArray[i];
  for (int j = 0; j < len - 1; j++) {
    for (int i = 0; i < len - j - 1; i++) {
      if (bTab[i] > bTab[i + 1]) {
        int t = bTab[i]; bTab[i] = bTab[i + 1]; bTab[i + 1] = t;
      }
    }
  }
  if (len & 1) return bTab[(len - 1) / 2];
  return (bTab[len / 2] + bTab[len / 2 - 1]) / 2;
}

float mapfloat(float x, float in_min, float in_max, float out_min, float out_max) {
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

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
  for (int i = 0; i < SCOUNT; i++) tdsBuf[i] = analogRead(TDS_PIN);
}

void loop() {
  unsigned long now = millis();

  if (now - t_lastTdsSample >= 40) {
    t_lastTdsSample = now;
    tdsBuf[tdsIdx] = analogRead(TDS_PIN);
    tdsIdx = (tdsIdx + 1) % SCOUNT;
  }

  if (now - t_lastTdsCalc >= 1000) {
    t_lastTdsCalc = now;

    for (int i = 0; i < SCOUNT; i++) tdsBufTmp[i] = tdsBuf[i];
    int medianADC = medianFilter(tdsBufTmp, SCOUNT);

    tdsAvgVolt = medianADC * (VREF / 4095.0);

    float kTemp = 1.0 + 0.02 * (waterTempC - 25.0);
    float compVolt = tdsAvgVolt / kTemp;

    tdsValue = (133.42 * compVolt * compVolt * compVolt
             - 255.86 * compVolt * compVolt
             + 857.39 * compVolt) * 0.5;
    if (tdsValue < 0) tdsValue = 0;
  }

  if (now - t_lastPH >= 1000) {
    t_lastPH = now;
    float phADC = analogRead(PH_PIN);
    phVoltage_mV = (phADC / ESPADC) * ESPVOLTAGE; // mV
    pHValue = ph.readPH(phVoltage_mV, waterTempC);
    ph.calibration(phVoltage_mV, waterTempC);
  }

  static float ntuValue = 0;
  if (now - t_lastNTU >= 1000) {
    t_lastNTU = now;
    int ntuRaw = analogRead(NTU_PIN);

    ntuValue = mapfloat((float)ntuRaw, rawClear, rawTurbid, 0.0, 1000.0);
    if (ntuValue < 0) ntuValue = 0;
  }

  static unsigned long t_lastPrint = 0;
  if (now - t_lastPrint >= 1000) {
    t_lastPrint = now;
    Serial.print("pH: ");  Serial.print(pHValue, 2);
    Serial.print(" | NTU: "); Serial.print(ntuValue, 2);
    Serial.print(" | TDS: "); Serial.print(tdsValue, 0); Serial.println(" ppm");
  }

  if (now - t_lastSend >= 2000) {
    t_lastSend = now;

    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(serverName);
      http.addHeader("Content-Type", "application/x-www-form-urlencoded");

      String postData = "ph=" + String(pHValue, 2)
                      + "&ntu=" + String(ntuValue, 2)
                      + "&tds=" + String(tdsValue, 0);
      Serial.print("POST data: ");
      Serial.println(postData);
     
      int httpResponseCode = http.POST(postData);
      Serial.print("Response code: ");
      Serial.println(httpResponseCode);

      if (httpResponseCode == 200) {
        Serial.println("=> Gui du lieu THANH CONG");
      } else {
        Serial.print("=> Loi: "); 
        Serial.println(httpResponseCode);
      }
      http.end();
    } else {
      Serial.println("WiFi mat ket noi, bo qua lan gui nay.");
    }
  }
}
