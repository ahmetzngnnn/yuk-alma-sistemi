#include <Wire.h>
#include "Adafruit_VL53L1X.h"
//Arduino Kodu (Oto-Reset ve Anti-Kilitlenme Özellikli)
#define TCAADDR 0x70

Adafruit_VL53L1X sensor1, sensor2, sensor5, sensor4;

#define NUM_STEPS 12
const float gercek_mesafeler[NUM_STEPS] = {
  52.025, 104.050, 156.075, 208.100, 260.125, 312.150, 
  364.175, 416.200, 468.225, 520.250, 572.275, 624.300
};

const float raw_dna[4][NUM_STEPS] = {
  {53.49, 112.62, 168.75, 220.87, 276.31, 329.71, 385.35, 439.73, 493.56, 544.19, 594.69, 644.07}, // L1
  {54.47, 116.47, 169.79, 216.99, 273.10, 321.89, 369.64, 408.18, 443.10, 472.63, 491.80, 505.76}, // L2
  {50.97, 106.41, 162.20, 214.23, 265.90, 314.51, 364.46, 411.56, 461.79, 509.22, 555.19, 602.11}, // L5
  {50.36, 112.96, 165.50, 214.01, 268.47, 317.29, 365.28, 408.60, 450.48, 485.10, 512.02, 539.16}  // L4
};

float base_Q = 0.05; 
float R = 5.0;       
float kalman_X[4] = {150, 150, 150, 150}; 
float kalman_P[4] = {1.0, 1.0, 1.0, 1.0}; 

void tcaSelect(uint8_t i) {
  if (i > 7) return;
  Wire.beginTransmission(TCAADDR);
  Wire.write(1 << i);
  Wire.endTransmission();
}

void setNarrowFOV(uint8_t channel) {
  tcaSelect(channel);
  Wire.beginTransmission(0x29);
  Wire.write(0x01); Wire.write(0x3F); Wire.write(0x33); 
  Wire.endTransmission();
  delay(10); 
}

// ==========================================================
// SENSÖRLERİ BAŞLATMA / RESETLEME FONKSİYONU
// ==========================================================
void initSensors() {
  tcaSelect(0); sensor1.begin(0x29, &Wire); sensor1.startRanging(); sensor1.setTimingBudget(50);
  tcaSelect(1); sensor2.begin(0x29, &Wire); sensor2.startRanging(); sensor2.setTimingBudget(50);
  tcaSelect(2); sensor5.begin(0x29, &Wire); sensor5.startRanging(); sensor5.setTimingBudget(50);
  tcaSelect(4); sensor4.begin(0x29, &Wire); sensor4.startRanging(); sensor4.setTimingBudget(50);

  setNarrowFOV(0); setNarrowFOV(1); setNarrowFOV(2); setNarrowFOV(4);
}

// ==========================================================
// KORUMALI OKUMA (TIMEOUT)
// ==========================================================
int safeRead(Adafruit_VL53L1X &sensor, uint8_t channel) {
  tcaSelect(channel);
  int timeout = 0;
  while(!sensor.dataReady()) {
    delay(1);
    timeout++;
    if(timeout > 60) return -1; // Sensör donduysa -1 dön
  }
  int distance = sensor.distance();
  sensor.clearInterrupt();
  return distance;
}

float interpolateFast(int sensorIndex, float raw) {
  if (raw <= raw_dna[sensorIndex][0]) return (raw / raw_dna[sensorIndex][0]) * gercek_mesafeler[0];
  if (raw >= raw_dna[sensorIndex][NUM_STEPS - 1]) {
    float x_son = raw_dna[sensorIndex][NUM_STEPS - 1], x_bir_once = raw_dna[sensorIndex][NUM_STEPS - 2];
    float y_son = gercek_mesafeler[NUM_STEPS - 1], y_bir_once = gercek_mesafeler[NUM_STEPS - 2];
    return y_bir_once + ((raw - x_bir_once) / (x_son - x_bir_once)) * (y_son - y_bir_once);
  }
  int low = 0, high = NUM_STEPS - 2;
  while (low <= high) {
    int mid = low + (high - low) / 2;
    if (raw >= raw_dna[sensorIndex][mid] && raw <= raw_dna[sensorIndex][mid + 1]) {
      return gercek_mesafeler[mid] + ((raw - raw_dna[sensorIndex][mid]) / (raw_dna[sensorIndex][mid + 1] - raw_dna[sensorIndex][mid])) * (gercek_mesafeler[mid + 1] - gercek_mesafeler[mid]);
    }
    if (raw < raw_dna[sensorIndex][mid]) high = mid - 1;
    else low = mid + 1;
  }
  return raw;
}

float applyAdaptiveKalman(int index, float measurement) {
  float innovation = abs(measurement - kalman_X[index]);
  kalman_P[index] += (innovation > 15.0) ? (base_Q * 100.0) : (base_Q * 0.1);
  float K = kalman_P[index] / (kalman_P[index] + R);
  kalman_X[index] += K * (measurement - kalman_X[index]);
  kalman_P[index] *= (1.0 - K);
  return kalman_X[index];
}

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  Wire.begin();
  
  // DONANIMSAL I2C KİLİTLENME KORUMASI (Arduino'nun donmasını engeller)
  Wire.setWireTimeout(3000, true); 
  
  initSensors();
  delay(500);
}

void loop() {
  int raw1 = safeRead(sensor1, 0);
  int raw2 = safeRead(sensor2, 1);
  int raw5 = safeRead(sensor5, 2);
  int raw4 = safeRead(sensor4, 4);

  // EĞER SENSÖRLERDEN BİRİ BİLE HATA VERDİYSE (Kablo koptu, sensör dondu vs.)
  if (raw1 == -1 || raw2 == -1 || raw5 == -1 || raw4 == -1) {
    // Python'a HATA KODU gönder
    Serial.println("-1,-1,-1,-1");
    
    // Sensörleri I2C üzerinden yeniden ayağa kaldırmayı dene
    Wire.clearWireTimeoutFlag(); // Kilitlenmeyi temizle
    initSensors(); // Sensörleri yeniden başlat
    delay(200); // Toparlanmaları için bekle
    return; // Döngüyü başa sar
  }

  // EĞER HER ŞEY YOLUNDAYSA
  if(raw1 > 10 && raw2 > 10 && raw4 > 10 && raw5 > 10) {
      float f_L1 = applyAdaptiveKalman(0, interpolateFast(0, raw1));
      float f_L2 = applyAdaptiveKalman(1, interpolateFast(1, raw2));
      float f_L5 = applyAdaptiveKalman(2, interpolateFast(2, raw5));
      float f_L4 = applyAdaptiveKalman(3, interpolateFast(3, raw4));

      Serial.print(f_L1, 1); Serial.print(",");
      Serial.print(f_L2, 1); Serial.print(",");
      Serial.print(f_L5, 1); Serial.print(",");
      Serial.println(f_L4, 1);
  }
  delay(30); 
}