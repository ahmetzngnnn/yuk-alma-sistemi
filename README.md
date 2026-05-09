# Yük Alma Sistemi — Otonom İniş Hizalama Yazılımı

Dört köşeye yerleştirilmiş **VL53L1X ToF (Time-of-Flight)** sensörleri kullanarak
insansız hava aracının yük alma platformuna hassas hizalamasını sağlayan iki bileşenli sistem.

---

## Sistem Bileşenleri

```
Arduino (Deneyap)                    Python (PC)
──────────────────────────────────   ──────────────────────────────
  TCA9548A I2C Multiplexer           Serial → L1,L2,L5,L4 (mm)
    ├── Ch0 → L1 (Sağ Üst)           └── Durum Makinesi
    ├── Ch1 → L2 (Sağ Alt)                ├── KİLİTLENDİ
    ├── Ch2 → L5 (Sol Üst)                ├── ARAMA MODU
    └── Ch4 → L4 (Sol Alt)                ├── DÜZELTME (yön komutu)
                                          └── KARARSIZLIK
  Kalibrasyon (12 nokta)
  Uyarlanabilir Kalman Filtresi
  Seri port: 115200 baud
```

---

## Sensör Yerleşim Düzeni

```
        ┌─────────────────┐
        │  L5       L1   │
        │  Sol Üst  Sağ  │
        │                │
        │     [İHA]      │  ← Araç buradan iner
        │                │
        │  L4       L2   │
        │  Sol Alt  Sağ  │
        └─────────────────┘
                 ↑
           Yük Platformu
```

Her sensör, doğrudan altındaki platform yüzeyine olan mesafeyi mm cinsinden ölçer.

---

## Donanım

| Bileşen | Model | Adet |
|---------|-------|------|
| Mikrodenetleyici | Deneyap (Arduino uyumlu) | 1 |
| Mesafe sensörü | VL53L1X ToF (I2C) | 4 |
| I2C multiplexer | TCA9548A (0x70) | 1 |
| Bağlantı | USB Serial (115200 baud) | — |

### I2C Bağlantıları

| Sensör | TCA9548A Kanalı | Konum |
|--------|----------------|-------|
| L1 | Ch 0 | Sağ Üst |
| L2 | Ch 1 | Sağ Alt |
| L5 | Ch 2 | Sol Üst |
| L4 | Ch 4 | Sol Alt |

---

## Arduino Yazılımı — `KalibrasyonluVeriOkuma.cpp`

### Kalibrasyon

Her sensörün ham okuması, 12 noktalı gerçek mesafe tablosuna göre doğrusal interpolasyon ile düzeltilir.

```
Gerçek mesafeler: 52.0, 104.1, 156.1, ..., 624.3 mm (12 adım, ~52 mm aralık)
Ham → Gerçek dönüşüm: Binary search + linear interpolation
```

Yeni bir sensör eklendiğinde veya mekanik değişiklik olduğunda kalibrasyon tablosu (`raw_dna`) güncellenir.

### Uyarlanabilir Kalman Filtresi

Standart Kalman filtresi yerine **uyarlanabilir gürültü modeli** kullanılır:

- Anlık değişim < 15 mm → düşük süreç gürültüsü (`Q × 0.1`) → yumuşak izleme
- Anlık değişim ≥ 15 mm → yüksek süreç gürültüsü (`Q × 100`) → hızlı tepki

```cpp
float base_Q = 0.05;   // temel süreç gürültüsü
float R      = 5.0;    // ölçüm gürültüsü
```

### Hata Koruması ve Oto-Reset

| Koruma | Açıklama |
|--------|---------|
| **Timeout (60 ms)** | `dataReady()` 60 ms içinde gelmezse sensörü atla |
| **I2C Kilitleme Koruması** | `Wire.setWireTimeout(3000, true)` ile donanım seviyesinde 3 sn timeout |
| **Oto-Reset** | Herhangi bir sensör `-1` döndürürse `initSensors()` ile tümü yeniden başlatılır |
| **Dar FOV** | `setNarrowFOV()` ile parazit ölçümler azaltılır |

### Seri Çıktı Formatı

```
f_L1,f_L2,f_L5,f_L4\n     ← Normal (mm, 1 ondalık)
-1,-1,-1,-1\n              ← Sensör hatası
```

Döngü hızı: **~30 ms** (33 Hz)

---

## Python Yazılımı — `VeriGörselleştirme.py`

### Gereksinimler

```bash
pip install pyserial numpy matplotlib
```

### Çalıştırma

```bash
python VeriGörselleştirme.py
```

> `SERIAL_PORT = 'COM15'` satırını kendi Arduino portuna göre değiştir.

### Temel Parametreler

```python
SERIAL_PORT    = 'COM15'   # ← Arduino'nun bağlı olduğu COM portu
BAUD_RATE      = 115200
ZEMIN_REFERANS = 260.0     # mm — zemin boş iken beklenen mesafe
HEDEF_BEKLENEN = 240.0     # mm — platform üzerinde yük varken beklenen mesafe
TOLERANS       = 15.0      # mm — ±tolerans içinde "hedefte" sayılır
```

### Durum Makinesi

Dört sensörün hedef mesafede olup olmadığına göre 4 durum tanımlanır:

| Durum | Koşul | Görsel Renk |
|-------|-------|-------------|
| **KİLİTLENDİ** | L1 + L2 + L5 + L4 hepsi toleransta | Tüm köşeler **BEYAZ** |
| **ARAMA MODU** | Hiçbiri toleransta değil | Köşeler renkli, merkez gri |
| **DÜZELTME YAPIYOR** | Bir kısmı toleransta | Yön komutu: YUKARI/AŞAĞI/SOLA/SAĞA |
| **KARARSIZLIK** | Çapraz ya da belirsiz pattern | Turuncu uyarı |

### Yön Mantığı

```
Üst sensörler (L5+L1) görmüyor → YUKARI git
Alt sensörler (L4+L2) görmüyor → AŞAĞI git
Sol sensörler (L5+L4) görmüyor → SOLA git
Sağ sensörler (L1+L2) görmüyor → SAĞA git
```

### Görsel Arayüz (3×3 Grid)

```
┌─────────┬─────┬─────────┐
│ SOL ÜST │     │ SAĞ ÜST │   Beyaz  = Hedefte (±15 mm)
│   L5    │     │   L1    │   Renkli = Hedefte değil
├─────────┼─────┼─────────┤
│         │DURUM│         │   Merkez = Durum metni
│         │     │         │
├─────────┼─────┼─────────┤
│ SOL ALT │     │ SAĞ ALT │
│   L4    │     │   L2    │
└─────────┴─────┴─────────┘
```

---

## Kurulum ve Kullanım

### Arduino

1. Arduino IDE veya PlatformIO aç
2. Kütüphaneleri kur: `Adafruit_VL53L1X`
3. `KalibrasyonluVeriOkuma.cpp` dosyasını yükle
4. Seri monitörden veri akışını doğrula (`115200 baud`)

### Python

```bash
# Bağımlılıkları kur
pip install pyserial numpy matplotlib

# COM portunu güncelle (VeriGörselleştirme.py, satır 8)
SERIAL_PORT = 'COM15'   # Kendi portuna göre değiştir

# Çalıştır
python VeriGörselleştirme.py
```

---

## Sorun Giderme

| Belirti | Olası Neden | Çözüm |
|---------|-------------|-------|
| `Bağlantı Hatası!` | Yanlış COM port | Aygıt Yöneticisi'nden doğru portu bul |
| Sensör sürekli `-1` döndürüyor | I2C kilit / kablo sorunu | Kabloları kontrol et; Arduino kendini sıfırlar |
| Ölçümler gürültülü | Dar FOV aktif değil | `setNarrowFOV()` çağrısını kontrol et |
| Tüm köşeler beyaz ama iniş yanlış | `HEDEF_BEKLENEN` yanlış | Platformun gerçek yüksekliğini ölç ve güncelle |
| Pencere açılmıyor | Matplotlib backend | `pip install matplotlib` ve sürücü güncellemesi |
