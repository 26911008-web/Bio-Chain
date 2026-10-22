# Bio-Chain v2 — Smart Rice-Husk Supply Chain

Smart rice-husk supply chain untuk feedstock pirolisis biochar.
**ANGEL Innovation Hackathon 2026** · Track Sustainable Energy · Topik #4 Smart Bioenergy Feedstock Optimization.

## 🚀 Quick Start

### 1. Jalankan Aplikasi (Cukup Dobel Klik atau Jalankan Command)
Aplikasi mendukung mode offline tanpa Docker (otomatis menggunakan SQLite `biochain.db` dan auto-seeding data contoh):

```bash
# Opsi A: Dobel klik file jalankan.bat
jalankan.bat

# Opsi B: Jalankan via terminal
py -m uvicorn app.main:app --port 8000
```

> **Catatan Docker (Opsional untuk produksi)**: Jika ingin menggunakan PostgreSQL 16 & Redis, jalankan `docker compose up -d`. Sistem akan otomatis mendeteksi ketersediaan PostgreSQL dan memilih database yang tepat.

- **Web Portal & Login UI**: http://127.0.0.1:8000
- **API Docs (Swagger)**: http://127.0.0.1:8000/docs
- **Health Check & Status**: http://127.0.0.1:8000/api/v1/system/status

---

## 🔑 Akun Demo Resmi (Auto-Fill 1-Klik)

Saat membuka halaman web, Anda akan disambut dengan **layar login modern** dengan pilihan kartu peran yang dapat diklik untuk mengisi username dan password secara otomatis:

| Peran | Username / No. HP | Password | Nama Persona | Deskripsi Akses |
|-------|-------------------|----------|--------------|-----------------|
| 🌾 **Petani** | `petani_sugeng` / `081544556677` | `sekam123` | Pak Sugeng (Godean) | Lapor stok sekam siap jual, lihat bukti QR setor, pantau XP & tier insentif (Mitra Emas) |
| 📦 **Pengepul** | `pengepul_sleman` / `081322334455` | `kud2026` | Pak Ahmad (KUD Sleman) | Antrian verifikasi mutu, uji proksimat (air, abu, VM, FC), kalkulasi grade A/B/C/Tolak & harga |
| 🚛 **Driver** | `sopir_budi` / `081433445566` | `truk2026` | Budi Santoso (Armada 01) | Rute penjemputan sekam, peta rute interaktif, daftar stop & scan QR pickup |
| 🏭 **Pabrik** | `pabrik_indmira` / `081298765432` | `pabrik2026` | PT Indmira Biochar Plant | Dashboard ESG karbon (IPCC Tier 2), proyeksi pasokan 30 hari, optimasi blending HiGHS |
| ⚙️ **Admin** | `admin` / `081234567890` | `admin2026` | Administrator Bio-Chain | Statistik platform lengkap, daftar user terdaftar, tombol 1-klik Reset & Re-Seed Data Demo |

> 💡 **Fitur Tambahan**: Terdapat tombol **"⚡ Masuk Cepat sebagai Tamu Demo"** untuk masuk secara instan tanpa mengetik kredensial. Kapan pun dibutuhkan, gunakan tombol **"🔄 Reset Data Demo"** di header untuk mengembalikan data contoh ke kondisi default.

### 2. Testing Otomatis

```bash
py -m pytest -q
```

## 🏗️ Architecture

```
┌────────────────────────────────────────────────┐
│             Next.js 15 Frontend                │
│  🌾 Petani  📦 Pengepul  🚛 Driver  🏭 Pabrik  │
└──────────────────┬─────────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │   Nginx + Redis     │  ← Rate Limiting
        │   Rate Limiter      │
        └──────────┬──────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│              FastAPI Backend                     │
│                                                  │
│  Engine ①  Supply Forecaster (cosinus musiman)   │
│  Engine ②  Quality & Yield Scorer (proksimat)    │
│  Engine ③  Blending Optimizer (LP/HiGHS)         │
│  Engine ④  Demand-Supply Matcher (MILP) *        │
│  Engine ⑤  Route Optimizer (Clarke-Wright/ALNS)  │
│  Engine ⑥  Incentive Engine (XP/gamifikasi)      │
│  Engine ⑦  ESG Carbon Calculator (IPCC Tier 2)   │
│                                                  │
│  * = planned for Sprint 3                        │
└──────────────────┬──────────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │   PostgreSQL 16     │
        │   + Redis 7         │
        └─────────────────────┘
```

## 📡 API Endpoints

### Auth & User Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Registrasi user baru |
| POST | `/api/v1/auth/login` | Login (phone + password) |

### 🌾 Petani Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/farmer/harvest` | Laporkan stok sekam |
| GET | `/api/v1/farmer/harvests` | Riwayat laporan |
| GET | `/api/v1/farmer/incentive` | Status XP & tier |

### 📦 Pengepul Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/collector/available-harvests` | Lihat laporan petani |
| POST | `/api/v1/collector/verify` | Verifikasi kualitas |
| GET | `/api/v1/collector/daily-summary` | Ringkasan harian |

### 🚛 Driver Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/driver/active-route` | Rute aktif |
| POST | `/api/v1/driver/start-route` | Mulai rute |
| POST | `/api/v1/driver/confirm-pickup` | Konfirmasi pickup (QR) |
| POST | `/api/v1/driver/complete-route` | Selesaikan rute |

### 🏭 Pabrik Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/factory/carbon/calculate` | Hitung emisi CO₂ |
| POST | `/api/v1/factory/forecast` | Prediksi pasokan |
| GET | `/api/v1/factory/forecast/30d` | Proyeksi 30 hari |
| POST | `/api/v1/factory/quality/score` | Skor kualitas |
| POST | `/api/v1/factory/blend/recommend` | Optimasi blending |
| GET | `/api/v1/factory/esg/summary` | Ringkasan ESG |

### Standalone Engine Endpoints (No Auth — Demo)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/carbon/calculate` | Kalkulasi karbon IPCC |
| POST | `/forecast/supply` | Prediksi pasokan |
| POST | `/incentive/calculate` | Hitung XP insentif |

### Legacy Endpoints (Backward Compatible)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/quality/score` | Engine ② |
| GET | `/quality/yield-curve` | Kurva rendemen |
| GET | `/blend/defaults` | Default feedstocks |
| POST | `/blend/recommend` | Engine ③ |
| GET | `/supply/mills` | Data penggilingan |
| POST | `/routes/optimize` | Engine ⑤ |

## 🔐 Role-Based Access

| Role | Deskripsi | Endpoints |
|------|-----------|-----------|
| `petani` | Pemasok sekam | `/api/v1/farmer/*` |
| `pengepul` | Aggregator lokal | `/api/v1/collector/*` |
| `driver` | Pengemudi logistik | `/api/v1/driver/*` |
| `pabrik` | Pabrik pirolisis | `/api/v1/factory/*` |
| `admin` | System admin | `/api/v1/admin/*` |

## 🧪 Engine Scientific References

| Engine | Referensi |
|--------|-----------|
| ② Quality | Literatur slow pyrolysis sekam (57% @300°C → 37% @700°C) |
| ③ Blending | Linear Programming via HiGHS/SciPy |
| ⑤ Routing | Clarke-Wright savings + 2-opt (upgrade: ALNS) |
| ⑦ Carbon | IPCC 2006 Tier 2, Perpres 110/2025 NEK |
| ① Forecast | Model cosinus ganda musim panen Jawa (BPS) |
| ⑥ Incentive | XP gamifikasi: Grade × Quantity × Bonus multiplier |
