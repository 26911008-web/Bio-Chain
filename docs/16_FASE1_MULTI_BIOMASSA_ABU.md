# 16 — Fase 1: Multi-Biomassa, Gudang Pengepul Berefraksi & Ledger Abu Agronomi

**Tanggal:** 11 Oktober 2026 · **Migrasi:** `018_multi_biomass_ash.sql` (+ rollback) · **Riset:** `docs/15_RISET_MULTI_BIOMASSA_ABU_WTE.md`
**Status:** diterapkan; teruji di SQLite, PostgreSQL (skema per tes), PostgreSQL + RLS (`biochain_app`), dan e2e browser.

Catatan stack: protokol menyebut Supabase/Prisma/Next.js. Repo ini memakai FastAPI + PostgreSQL + SPA. RLS PostgreSQL di sini setara dengan RLS Supabase, jadi stack tidak diganti.

## 1. Apa yang dibangun

| Komponen | Isi |
|---|---|
| `biomass_parameters` | Master untuk 7 komoditas Jawa: sekam padi, tongkol jagung, ampas tebu, tempurung kelapa, sabut kelapa, serbuk sengon, serbuk karet. Berisi proksimat, HHV/LHV bk, densitas curah, S, Cl, dan 8 oksida abu (SiO₂, K₂O, Na₂O, CaO, MgO, Fe₂O₃, Al₂O₃, P₂O₅), acuan refraksi (MC acuan, MC tolak, toleransi kotoran), serta **harga dasar beli tanpa nilai bawaan**. Setiap baris menyebut sumber, dan setiap perubahan wajib menyebut dasarnya (no. laporan lab / sumber harga). |
| `commodity` di `harvests` & `stock_listings` | Default `sekam_padi`, sehingga data dan alur lama tidak berubah. Lot hasil lelang mewarisi komoditas listing. `accept_bid_atomic` (SELECT … FOR UPDATE) tetap berlaku untuk semua komoditas. |
| Verifikasi pengepul | Sekam tetap memakai kurva mutu Engine ②. Komoditas lain dinilai dari acuan master (grade A/B/C/TOLAK) dengan harga **basis kering kontinu** terhadap MC acuan, tanpa bonus kering. Bila harga dasar belum diisi pabrik, server menolak (422); tidak ada angka asumsi. |
| `collector_warehouses` + `warehouse_stock_movements` | Gudang pengepul bisa lebih dari satu. Ledger stok **append-only** (trigger `forbid_mutation` di PG), saldo = SUM. Mutasi masuk, keluar, dan susut idempoten (`client_event_id`) sehingga aman dicatat **tanpa sinyal**. |
| Refraksi otomatis (`engines/refraction.py`) | `kg_bayar = kg × (1 − max(0, kotoran − toleransi)) × (1 − MC)/(1 − MC_acuan)`. Tidak ada standar nasional untuk sekam/tongkol, jadi analoginya HPP gabah Bapanas. Di atas MC tolak ada opsi **"terima basah"** yang dicatat eksplisit, sesuai praktik pengepul yang mengeringkan sendiri. |
| `farmer_groups` (Poktan) + `industrial_ash_ledgers` | Alur abu: dicatat → uji logam berat (status **dihitung** dari batas parameter Kepmentan 261/2019: As 10, Hg 1, Pb 50, Cd 2, Cr 180, Ni 50 mg/kg; batas disimpan sebagai snapshot) → dialokasikan ke Poktan → diserahkan dengan foto + GPS lahan. Abu yang gagal uji hanya bisa "dibuang", dengan catatan tujuan berizin. |

## 2. Pengaman berlapis

| Risiko lapangan | Pengaman |
|---|---|
| Abu berlogam berat sampai ke sawah | CHECK di DB: `dialokasikan`/`diserahkan` hanya bila `heavy_metal_status = 'lulus'`. Status `lulus` wajib Pb, Cd, As + no. laporan lab. Serah-terima wajib foto + koordinat. Tes membuktikan tetap tertolak walau aplikasi dilewati. |
| Dua HP pengepul mengeluarkan stok bersamaan (antrean offline) | PG: `SELECT … FOR UPDATE` per gudang. SQLite (mode cadangan): saldo diperiksa ulang setelah tulis di transaksi yang sama. Tes 5 permintaan paralel → tepat 3 lolos, saldo tidak pernah minus. |
| Pengepul lain melihat/menulis stok saya | RLS: pengepul hanya gudang miliknya; auditor baca saja; ketua Poktan hanya abu kelompoknya. |
| Saldo stok "dirapikan" diam-diam | Ledger append-only; koreksi = entri baru. |
| Harga asumsi | `base_price_per_kg` tanpa nilai bawaan; UI menandai "belum diisi". |

## 3. Koreksi baseline protokol (dari riset)

- LHV_db sekam **14,3** MJ/kg (15,5 adalah HHV).
- Bagasse **17,5**. Kelapa dipisah: tempurung **18,9** dan sabut **17,5** (sabut Cl 0,3–1,5 %).
- Serbuk gergaji dari sawmill memiliki MC **30–55 %**, bukan < 12 %.
- Indeks alkali (Miles 1996) = abu% × (K₂O+Na₂O)% / (10 × HHV MJ/kg) dalam kg/GJ; > 0,17 mungkin terak, > 0,34 hampir pasti. Dari data seed:
  - tongkol jagung **0,40** dan sabut **0,86**: tinggi walau abunya rendah;
  - serbuk kayu sekitar 0,1;
  - sekam 0,40 secara formal, tetapi risiko nyatanya adalah volume abu dan silika kristalin.

  Ini dasar untuk Prototipe 1 (blending).

## 4. Uji

- `tests/test_biomass.py` (8): sinkron seed Python↔SQL, rumus refraksi, master + hak ubah, alur multi-komoditas (lapor, verifikasi, lelang), ledger gudang (refraksi, idempoten, overdraft), 5 permintaan keluar paralel, alur abu end-to-end, CHECK DB.
- `tests/test_postgres.py::test_multibiomass_rls_warehouse_isolation_and_ash_visibility`, `tests/test_farmer_feedback.py::test_multibiomass_warehouse_and_ash_through_rls`.
- `tests/e2e_multibiomass.spec.ts` (3): lapor tongkol jagung, gudang + pratinjau refraksi + mutasi **offline**, abu gagal uji tanpa tombol ke Poktan.
- Regresi: SQLite 489 lulus, PG + RLS lulus, 19 spec e2e lulus.

## 5. Catatan produksi

1. `py scripts/pg_setup.py` atau terapkan `migrations/018_multi_biomass_ash.sql`.
2. Pabrik mengisi **harga dasar** tiap komoditas yang akan dibeli. Ganti nilai master dengan hasil lab (ISO 18134 kadar air, ISO 18122 abu, ISO 18125 nilai kalor, XRF oksida abu).
3. Status hukum abu dari 100 % biomassa belum eksplisit di PP 22/2021. Simpan hasil uji karakteristik dan konsultasikan ke DLH setempat sebelum distribusi rutin.
4. Kalibrasi moisture meter pengepul terhadap oven 105 °C (ISO 18134-2).
