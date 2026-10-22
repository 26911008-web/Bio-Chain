# 19 — Prototipe 3: Pemantauan SEC/IKE Ternormalisasi & Detektor Anomali (Fase 4)

**Tanggal:** 12 Oktober 2026 · **Engine:** `app/engines/sec_monitor.py` (Engine ⑩b; Engine ⑩ bulanan/IKE gedung tetap ada) · **Migrasi:** `019_energy_operation_logs.sql` · **Riset:** `docs/15` §8

## 1. Data masuk

Log harian/shift (`energy_operation_logs`) berisi:
- kWh total, kWh pengering, kWh hammer mill;
- solar (L), bahan bakar biomassa (kg + komoditas);
- jam operasi, ton produk, kadar air umpan, kapasitas terpasang (t/jam).

Input bisa satu log lewat form atau banyak log sekaligus dengan tempel CSV. Pengiriman idempoten per `client_event_id`, dan slot (fasilitas, tanggal, shift) yang sudah ada tidak ditimpa. Form memakai antrean offline yang sudah ada.

## 2. Metode

| Langkah | Rumus / aturan | Sumber |
|---|---|---|
| Energi | E [MJ] = kWh·3,6 + solar·36,0 MJ/L + biomassa·LHV_ar (dari master) | IPCC 2006 NCV solar 43,0 MJ/kg × 0,84 kg/L |
| SEC aktual | E / ton produk | protokol |
| Baseline (EnB) | E ≈ β_h·jam + β_t·ton + β_w·air diuapkan | ISO 50006:2023 (*relevant variables*) |
| β_w | energi pengeringan per kg air (3,0 MJ/kg, parameter): **dari fisika, bukan regresi** | Thek & Obernberger 2004 (2,9–4,0 MJ/kg) |
| β_h (beban tetap/jam) | **daya idle terukur** (tang ampere saat mesin jalan kosong), atau NNLS bila utilisasi di periode acuan bervariasi ≥ 10 %. Bila tidak keduanya, sistem memberi peringatan eksplisit. | audit energi lapangan |
| Normalisasi beban parsial | EnPI = E aktual / E model; SEC ternormalisasi = E model / ton | DOE EnPI tool |
| Batas bergerak | residual relatif > rata-rata bergerak (7 log normal) + **2σ peringatan / 3σ aksi**. σ minimum = σ baseline; log yang dialarm tidak ikut ke rata-rata. | Montgomery 2019 |
| Degradasi pelan | CUSUM residual (k = 0,5σ, h = 5σ) dan median 5 log terakhir > 1σ, sehingga lonjakan tunggal bukan drift | Page 1954; docs/15 §8 |

## 3. Indikator pemborosan

- **Pengering, bahan basah.** Energi = β_w × (air diuapkan − air pada MC acuan pembelian).
  - Secara model energi ini "wajar", karena kadar air adalah *relevant variable*, sehingga tidak dihitung sebagai alarm.
  - Namun energi ini **dilaporkan terpisah** sebagai pemborosan yang dapat dikendalikan di hulu: refraksi pengepul, penjemuran, gudang beratap.
  - Contoh uji: MC 24 % vs acuan 12 % menghabiskan ±47 % energi hari itu.
- **Hammer mill.** kWh/t dibandingkan median baseline (literatur 13–20 kWh/t pada saringan 6,4 mm):
  - naik > 25 % dengan kadar air normal → "gesekan/aus" (hammer tumpul, saringan sobek/tersumbat, bearing/sabuk);
  - naik bersama kadar air tinggi → "basah, keringkan dulu".

## 4. Rekomendasi audit energi (ISO 50001:2018)

| Kartu | Klausul |
|---|---|
| Tekan kadar air bahan masuk | 8.1 Pengendalian operasional · 6.3 Tinjauan energi (SEU pengering) |
| Perawatan hammer mill / keringkan sebelum giling | 8.1 · 10.2 Perbaikan berkelanjutan |
| Investigasi log anomali | 9.1 Pemantauan · 10.1 Tindakan korektif |
| Degradasi efisiensi persisten | 10.2 · 6.5 EnB (penyesuaian non-rutin) |
| Kumpulkan bahan dulu, operasikan penuh (utilisasi < 60 %) | 6.2 Sasaran energi · 8.1 |

## 5. Uji

`tests/test_sec_monitor.py` (6):

| Skenario | Hasil |
|---|---|
| Beban parsial 40 % | SEC mentah naik > 30 % **tanpa alarm** (EnPI ≈ 1) |
| Injeksi konsumsi +35 % | **alarm aksi** |
| Bahan basah | indikator pengering |
| Hammer aus | indikator gesekan |
| Utilisasi acuan konstan | peringatan, atau daya idle dipakai |
| Drift +1,2 %/hari | terdeteksi CUSUM |
| API | ingest idempoten & analisis per peran |

`tests/e2e_multibiomass.spec.ts`: impor CSV 30 hari menghasilkan alarm aksi di hari lonjakan, tidak ada alarm di hari beban parsial, **bukan** "drift" untuk lonjakan tunggal, ada kartu ISO 50001, dan grafik tampil.

## 6. Catatan

- Minimal 8 log; idealnya ≥ 14 log acuan yang mencakup variasi beban.
- Ukur daya idle sekali per mesin (dan setelah penggantian peralatan) agar normalisasi beban parsial andal.
- Engine ⑩ bulanan (IKE gedung, Permen ESDM 13/2012) tetap dipakai untuk penilaian gedung. Prototipe 3 khusus untuk beban proses.
