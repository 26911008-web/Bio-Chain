# Dokumen Desain Teknis — Bio-Chain v2
**Smart Rice-Husk Supply Chain for Pyrolysis Biochar**  
*ANGEL Innovation Hackathon 2026 · Track Sustainable Energy · Topik #4 Smart Bioenergy Feedstock Optimization*

---

## 1. Arsitektur Sistem Tingkat Tinggi

Bio-Chain v2 dibangun dengan arsitektur **Edge-to-Cloud Closed Loop** yang menghubungkan entitas rantai pasok biomassa (petani sekam, pengepul KUD, pengemudi armada logistik, pabrik pirolisis, dan regulator) dalam satu platform terpadu.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       LAPISAN PENGGUNA (FRONTEND)                       │
│  🌾 Petani       📦 Pengepul         🚛 Driver          🏭 Pabrik       │
│ (Lapor Stok)   (Uji Mutu/Grade)   (Rute & Pickup)    (ESG & Blending)   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTPS / REST API / WebSocket
┌────────────────────────────────────▼────────────────────────────────────┐
│                    GATEWAY & KEAMANAN (API BACKEND)                     │
│  - JWT Bearer Authentication & Role-Based Access Control (RBAC)         │
│  - In-Memory & Redis Sliding-Window Rate Limiter (60 req/min)           │
│  - Fast Failover Connection Pool Manager (PostgreSQL 16 / SQLite local) │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│                      7 ENGINE KOMPUTASI BIO-CHAIN                       │
│  ① Supply Forecaster        : Proyeksi musiman cosinus ganda (BPS Jawa) │
│  ② Quality & Yield Scorer   : Evaluasi kinetika proksimat (300-700°C)   │
│  ③ Blending Optimizer       : Linear Programming (HiGHS SciPy)          │
│  ④ Demand-Supply Matcher    : Mixed-Integer Linear Programming (MILP)   │
│  ⑤ Route Optimizer          : Clarke-Wright Savings Heuristic + 2-Opt   │
│  ⑥ Incentive Engine         : Gamifikasi XP kuadrilateral (Mitra Emas)  │
│  ⑦ ESG Carbon Calculator    : IPCC 2006 Tier 2 & Perpres 110/2025 NEK   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│                      LAPISAN DATA & INFRASTRUKTUR                       │
│  - PostgreSQL 16 (Produksi) / SQLite 3 Aiosqlite (Offline/Edge Standalone)
│  - Redis 7 Cache & Message Broker                                      │
│  - Docker Containerization & Systemd Service                            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Desain Hardware & IoT Edge: Bio-Chain Scout Pro

Untuk memastikan transparansi dan integritas data di tingkat penggilingan padi pedesaan, dikembangkan perangkat uji cepat portabel bernama **Bio-Chain Scout Pro**.

```
                ┌──────────────────────────────────────┐
                │        Bio-Chain Scout Pro           │
                │        (Perangkat IoT Lapangan)      │
                └──────────────────┬───────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
┌────────▼────────┐       ┌────────▼────────┐       ┌────────▼────────┐
│  Probe Optik NIR│       │ Load Cell 24-bit│       │ Modul Telemetri │
│ 900 - 1700 nm   │       │ ADC HX711       │       │ 4G LTE + GPS    │
│ (Kadar Air/Abu) │       │ (Penimbangan)   │       │ (NEO-6M Sync)   │
└─────────────────┘       └─────────────────┘       └─────────────────┘
         │                         │                         │
         └─────────────────────────┼─────────────────────────┘
                                   │
                          ┌────────▼────────┐
                          │ Printer Thermal │
                          │ Tiket Label QR  │
                          └─────────────────┘
```

### 2.1 Spesifikasi Teknis Hardware
1. **Mikrokontroler Utama**: ESP32-S3 Dual-Core Xtensa LX7 @ 240 MHz, 8MB PSRAM, Wi-Fi 802.11 b/g/n + Bluetooth 5 (LE).
2. **Sensor Spektroskopi NIR**:
   - Spektrum Deteksi: 900 nm – 1700 nm (Near-Infrared Reflectance).
   - Waktu Pembacaan: < 3 detik per sampel.
   - Parameter Estimasi: Kadar Air (% wet basis, rentang 8% - 35%), Estimasi Volatile Matter & Kadar Abu silika.
3. **Sensor Penimbangan Digital**:
   - Load Cell S-Type Stainless Steel 500 kg dengan ADC 24-bit HX711 ultra-low noise.
   - Presisi pembacaan: ±0.1 kg (terkalibrasi standar metrologi lokal).
4. **Modul Geospasial & Komunikasi**:
   - GPS/GLONASS Module Quectel L76K / u-blox NEO-6M (akurasi posisi < 2.5 meter CEP).
   - Seluler Modem: SIMCom SIM7600E (4G LTE Cat-1 dengan fallback 2G).
5. **Printer Thermal Terintegrasi**:
   - 58mm Thermal Printer Unit ESC/POS 203 DPI.
   - Otomatis mencetak label barcode/QR code tahan cuaca berisi identitas batch sekam, tanggal penimbangan, koordinat GPS, dan hasil uji mutu awal.
6. **Sistem Daya**:
   - Baterai internal LiFePO4 12.8V 6000 mAh (tahan 16 jam pengoperasian aktif lapangan).
   - Port input DC 12-24V / solar charging kit 50W foldable panel.

---

## 3. Desain Software & Arsitektur API Backend

### 3.1 Stack Teknologi
- **Bahasa & Runtime**: Python 3.14 (AsyncIO, Type Annotations penuh).
- **Web Framework**: FastAPI (High performance ASGI, OpenAPI/Swagger 3.1).
- **ORM & Database Driver**: SQLAlchemy 2.0 (Modern Declarative Mapping) + `aiosqlite` (development/offline) / `asyncpg` (PostgreSQL 16 produksi).
- **Matematika & Sains Data**: SciPy (HiGHS Linear Programming Solver), NumPy.
- **Frontend SPA**: Vanilla ES6+, CSS Glassmorphism Design System, Leaflet.js (GIS Map), Chart.js (Visualisasi Kurva & KPI).

### 3.2 Model Keamanan & Autentikasi
1. **Password Hashing**: `passlib` dengan algoritma `bcrypt` (12 rounds) / PBKDF2 fallback.
2. **Token Format**: Stateless JSON Web Token (JWT) dengan enkripsi HMAC-SHA256, masa aktif 24 jam.
3. **Role Enforcement**:
   - `@router` dependencies mengecek klausa `role` pada payload JWT secara ketat.
   - Roles terdaftar: `PETANI`, `PENGEPUL`, `DRIVER`, `PABRIK`, `ADMIN`.

---

## 4. Spesifikasi Matematika 7 Engine Optimasi

### 4.1 Engine ①: Supply Forecaster (Model Cosinus Ganda)
Memodelkan dinamika ketersediaan sekam padi bulanan di wilayah Jawa berdasarkan pola panen raya (Maret–Mei) dan panen gadu (Agustus–September):
$$\hat{S}(t) = S_{\text{base}} \times \left(1 + A_1 \cos\left(\frac{2\pi (t - \phi_1)}{12}\right) + A_2 \cos\left(\frac{4\pi (t - \phi_2)}{12}\right)\right)$$
- $S_{\text{base}}$: Kebutuhan dasar bulanan (ton/bulan).
- $A_1 = 0.42, \phi_1 = 4.1$: Gelombang panen raya musim hujan.
- $A_2 = 0.25, \phi_2 = 8.6$: Gelombang panen gadu musim kemarau.

### 4.2 Engine ②: Quality & Yield Scorer (Kinetika Pirolisis Lambat)
Menilai sampel sekam berdasarkan uji proksimat dan menghitung prediksi rendemen biochar cair/padat:
$$\text{Yield}_{\text{biochar}}(T) = Y_0 \cdot \exp\left(-k \cdot (T - T_0)\right) \times \left(1 - \frac{\text{Moisture}}{100}\right) \times \left(1 - \frac{\text{Contamination}}{100}\right)$$
- Nilai empiris pada sekam padi: Rendemen 57.2% pada 300°C menurun menjadi 36.8% pada 700°C.
- Penentuan Grade Mutu:
  - **Grade A**: Kadar Air $\le 12\%$, Abu $\le 20\%$, Kontaminan $\le 2\%$ (Pengali Harga: 1.10x, +10% Bonus).
  - **Grade B**: Kadar Air $\le 16\%$, Abu $\le 25\%$, Kontaminan $\le 5\%$ (Pengali Harga: 1.00x).
  - **Grade C**: Kadar Air $\le 20\%$, Abu $\le 30\%$, Kontaminan $\le 8\%$ (Pengali Harga: 0.85x).
  - **Tolak**: Kadar Air $> 20\%$ atau Kontaminan $> 8\%$ (Pengali Harga: 0.00x).

### 4.3 Engine ③: Blending Optimizer (Linear Programming via HiGHS)
Menentukan proporsi campuran bahan baku biomassa (sekam kering, sekam basah, tongkol jagung, serbuk kayu) yang meminimalkan total biaya pengadaan dengan memenuhi batasan mutu reaktor:
$$\min \sum_{i=1}^n c_i \cdot x_i$$
Dengan kendala:
$$\sum_{i=1}^n x_i = W_{\text{target}}$$
$$\sum_{i=1}^n M_i \cdot x_i \le M_{\max} \cdot W_{\text{target}} \quad (\text{Batas Maksimal Kadar Air})$$
$$\sum_{i=1}^n A_i \cdot x_i \le A_{\max} \cdot W_{\text{target}} \quad (\text{Batas Maksimal Kadar Abu})$$
$$\sum_{i=1}^n \text{FC}_i \cdot x_i \ge \text{FC}_{\min} \cdot W_{\text{target}} \quad (\text{Batas Minimal Fixed Carbon})$$
$$0 \le x_i \le S_i \quad (\text{Ketersediaan Stok Bahan Baku } i)$$

### 4.4 Engine ⑤: Route Optimizer (Clarke-Wright Savings + 2-Opt)
Mengelompokkan dan mengurutkan titik penjemputan penggilingan padi ke dalam rute truk berkapasitas terbatas ($C_{\max} = 8\text{ ton}$):
$$s_{ij} = d(0, i) + d(0, j) - d(i, j)$$
Di mana $0$ adalah depot pabrik, $i$ dan $j$ adalah lokasi penggilingan. Rute kemudian dihaluskan menggunakan algoritma 2-Opt untuk mengeliminasi persilangan jalur.

### 4.5 Engine ⑥: Gamification & Incentive Engine
Mendorong petani menjaga kebersihan dan kekeringan sekam melalui sistem Experience Points (XP) dan sertifikasi Mitra:
$$\text{XP}_{\text{earned}} = \text{Round}\left(\frac{\text{Qty}_{\text{kg}}}{10} \times \text{Multiplier}(\text{Grade}) \times \text{BonusStreak}\right)$$
Tingkatan Mitra:
- **Pemula**: 0 – 99 XP (Akses standar).
- **Mitra Perunggu**: 100 – 499 XP (Prioritas penjemputan armada).
- **Mitra Perak**: 500 – 1499 XP (Subsidi karung terpal + prioritas penjemputan).
- **Mitra Emas**: $\ge 1500$ XP (+Rp 25/kg flat premium bonus + akses bibit padi unggul bersertifikat).

### 4.6 Engine ⑦: ESG Carbon Credit Calculator (IPCC Tier 2)
Menghitung emisi bersih yang dihindarkan dari pembakaran sekam terbuka di sawah (*open field burning*) dan sekuestrasi karbon stabil biochar:
$$\Delta E_{\text{net}} = E_{\text{baseline}} - E_{\text{transport}} - E_{\text{pyrolysis}} + E_{\text{sequestration}}$$
Sesuai Perpres 110/2025 tentang Nilai Ekonomi Karbon (NEK):
- Faktor emisi open burning: $1.28 \text{ tCO}_2\text{e / ton sekam}$.
- Stabilitas karbon biochar ($C_{\text{org}} \times F_{\text{perm}}$): $0.85 \times 0.80 = 0.68 \text{ tC / ton biochar} \approx 2.49 \text{ tCO}_2\text{e / ton biochar}$.

---

## 5. Desain Reaktor Pirolisis Lambat Indmira

Unit reaktor pirolisis beroperasi pada temperatur $450^\circ\text{C} - 550^\circ\text{C}$ dengan waktu tinggal (*residence time*) 25–40 menit. Reaktor dilengkapi:
1. **Airlock Rotary Valve**: Mencegah oksigen masuk ke ruang pirolisis.
2. **Indirect-Fired Rotary Kiln**: Pemanasan tidak langsung dengan pembakaran syngas internal sirkulasi tertutup (self-sustaining).
3. **Cyclone Separator**: Menangkap partikel abu terbang (*fly ash*).
4. **Water-Jacketed Cooling Auger**: Mendinginkan biochar dari $500^\circ\text{C}$ ke $< 50^\circ\text{C}$ tanpa penyiraman air berlebih untuk menjaga mutu kekeringan.
5. **IoT Telemetry Enclosure**: Sensor termokopel tipe-K 8 titik dan transmisi data ke API `/api/v1/factory/pyrolysis/telemetry`.
