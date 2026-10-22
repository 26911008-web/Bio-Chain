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
| 🔍 **Auditor** | `auditor_esg` / `081677889900` | `audit2026` | Auditor Rantai Pasok & ESG | Baca-saja: jejak timbangan, susut, alokasi biochar ke dompet petani |

> 🔐 **Gerbang peran**: halaman muka memiliki 5 gerbang (Petani · Pengepul · Driver · Pabrik · Auditor) + tautan Admin. Tiap gerbang menawarkan akun demo perannya (klik untuk isi otomatis). Setelah masuk, pengguna hanya melihat modul perannya; Lab 7 Engine khusus Pabrik/Admin. Ganti persona lewat menu di header.
>
> 🤖 **Asisten AI**: tombol "Asisten" di kanan bawah — tanya jawab & saran optimasi berbasis data peran Anda. Provider: Gemini, Mistral, Groq, OpenRouter (tier gratis) atau AI lokal Ollama. Isi kunci di `.env` (lihat `.env.example`).
>
> 🎛️ **Parameter Asumsi** (tab khusus Pabrik/Admin; Auditor baca-saja): ±100 angka asumsi di 13 kelompok — harga & grade, ambang mutu, model rendemen, toleransi susut, porsi biochar petani, biaya angkut, faktor jalan, emisi IPCC, produktivitas panen, tier insentif, efisiensi konversi, tarif listrik & kriteria IKE, bobot TOPSIS, spesifikasi produk, preset biomassa (tabel). Perubahan berlaku langsung di semua modul, tervalidasi (rentang + konsistensi antar-parameter) dan tercatat (siapa/kapan/alasan). Konstanta fisika & parameter teknis algoritma sengaja tidak diekspos. Registry: `app/params.py`.
>
> 🔄 **Reset Data Demo** (header) hanya tampil & diizinkan untuk Admin — ganti persona ke Admin untuk mengembalikan data contoh.

### 1b. Mode PostgreSQL (opsional, mendekati produksi)

```bash
docker compose up -d postgres          # PostgreSQL 16 di port 5433
py scripts/pg_setup.py --reset         # skema + migrasi 002–008 + peran biochain_app (tanpa bypass RLS)
set DATABASE_URL=postgresql+asyncpg://biochain_app:biochain_app_dev@localhost:5433/biochain
set AUTO_MIGRATE=false
py -m uvicorn app.main:app --port 8000
```
Detail & rollback: [migrations/README.md](migrations/README.md).

### 2. Testing Otomatis

```bash
py -m pytest -q                       # unit + E2E siklus sirkular + HA
py -m tests.test_routing              # tabel benchmark Engine ⑤
k6 run loadtest/k6_double_submit.js   # chaos test 1.000 user (server harus hidup)
```

Dokumen: [Audit SRE & High-Availability](docs/05_SRE_HIGH_AVAILABILITY.md) · [Migrasi DB & rollback](migrations/README.md)

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
| `pabrik` | Pabrik pirolisis | `/api/v1/factory/*`, `/api/v1/labs/*`, `/api/v1/jobs/*` |
| `auditor` | Audit rantai pasok & ESG (baca-saja) | `/api/v1/auditor/*`, baca `/api/v1/factory/energy/*` & `mass-balance` |
| `admin` | System admin | semua di atas + `/api/v1/admin/*` |

Kebijakan deny-by-default: `app/security/policy.py` (path `/api/*` tak terdaftar → 403). RLS PostgreSQL: `migrations/004_row_level_security.sql`.

## 🧪 Engine Scientific References

| Engine | Referensi |
|--------|-----------|
| ② Quality | Literatur slow pyrolysis sekam (57% @300°C → 37% @700°C) |
| ③ Blending | Linear Programming via HiGHS/SciPy |
| ⑤ Routing | Exact DP (n≤10) · granular Clarke-Wright + relocate/swap/2-opt + ruin & recreate ILS (<500 ms @1000 titik) |
| ⑦ Carbon | IPCC 2006 Tier 2, Perpres 110/2025 NEK |
| ① Forecast | Model cosinus ganda musim panen Jawa (BPS) |
| ⑥ Incentive | XP gamifikasi: Grade × Quantity × Bonus multiplier |
| ⑧ Feedstock | Perbandingan & rekomendasi awal: HHV Parikh et al. (2005) *Fuel* 84:487; LHV basis diterima; peringkat TOPSIS (Hwang & Yoon 1981); campuran termurah via ③ — `POST /api/v1/labs/feedstock/compare` |
| ⑨ Waste-to-Energy | Rekomendasi teknologi (termokimia vs biokimia, McKendry 2002 *Bioresour. Technol.* 83:47) + potensi energi (panas, listrik, biogas VS×BMP, biochar, pellet) — `POST /api/v1/labs/waste-energy/advise` |
| 🤝 Pasar B2B | Listing petani dengan **2 skema** (jemput ≈ Incoterms EXW, antar ≈ DAP) & harga minimum per skema (reserve price, Myerson 1981); pengepul menawar sebagian/seluruh; **petani memilih** (nilai bersih per kg ditampilkan); penerimaan sebagian atomik. Penasihat tawaran: harga jual − biaya logistik marginal (insertion cost pada rute CVRP ⑤) − margin; saran = titik tengah surplus (Nash 1950). Resi serah-terima atomik `TRX-[PENGIRIM]-[PENERIMA]-[YYMM]-[SEQ]` + `evidence_photo_url` — `/api/v1/farmer/listings`, `/api/v1/collector/market`, `/api/v1/collector/bids`, `/api/v1/collector/bid-advisor` |
| ⑪ Pabrik | **Procurement B2B**: pengepul mengajukan Delivery Request (harga rekomendasi pabrik terlihat), pabrik terima/tawar balik/tolak dengan batas putaran; **QC masuk** (bruto−tara, proksimat → grade, harga kontrak disetarakan basis kering, kontaminan tidak dibayar, resi `TRX-PGP…-PBK…`). **Mass balance** 1 input → bio-pellet + biochar + bio-silika + loss (air, volatil/syngas, gas pembakaran, residu ekstraksi, susut); bio-silika **3 jalur**: dari biochar, dari abu pembakaran (panas tungku menutup biaya pengering), atau dari sekam langsung (pelindian asam). **Harga jual 3 produk = input wajib** (tanpa angka bawaan; isi di menu Parameter atau kalkulator). **Rantai ke dompet**: pengepul melampirkan harvest petani pada Delivery Request → QC pabrik (susut dibagi proporsional) → batch → biochar dikreditkan ke dompet tiap petani tepat sampai gram dengan penutupan & varians rendemen vs model. **Biaya**: variabel + depresiasi garis lurus per jam + biaya tetap, alokasi biaya bersama NRV/unit fisik (Horngren), biaya & margin per ton produk, volume impas (CVP). **Pricing Engine**: harga lantai/target/plafon netback + sensitivitas kadar air — `/api/v1/factory/pricing/recommend`, `/qc`, `/batches`, `/delivery-requests` |
| 📊 Laporan Bulanan | Gudang data tunggal (tanpa tabel ringkasan terpisah): **volume pasokan, % konversi biomassa, efisiensi biaya** per bulan WIB; cakupan otomatis per peran (petani/pengepul/supir: data sendiri; pabrik/admin/auditor: seluruh pabrik); JSON & CSV — `GET /api/reports/monthly?from=YYYY-MM&to=YYYY-MM[&format=csv]`. View PostgreSQL `wh_monthly_*` (`security_invoker`, RLS tetap berlaku) untuk alat BI; angka API = angka view (diuji). Rujukan: Kimball & Ross (2013) *Data Warehouse Toolkit*; Brunner & Rechberger (2016) *Handbook of MFA*; Horngren (2015) *Cost Accounting*; ISO 50006:2014; SCOR v12 |
| ⑩ Energi | Histori `energy_readings` di DB → IKE (Permen ESDM 13/2012), SEC kWh/ton, baseline regresi ISO 50006, anomali robust-z (Iglewicz & Hoaglin 1993) + CUSUM, rekomendasi efisiensi — `GET /api/v1/factory/energy/analysis` |
