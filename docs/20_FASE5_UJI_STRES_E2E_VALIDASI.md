# 20 — Fase 5: Uji Stres Multi-Node, E2E & Validasi Sirkular

**Tanggal:** 12 Oktober 2026 · **Status protokol multi-biomassa:** Fase 1–5 selesai

## 1. Skenario protokol → hasil

| # | Skenario | Uji | Hasil |
|---|---|---|---|
| 1 | Pengepul membeli tongkol jagung & sekam **paralel** | `tests/test_phase5_integrated.py::test_parallel_multi_commodity_purchases`: 2 pengepul berebut 12 lot (24 permintaan serentak); 2 tawaran lelang jagung diterima bersamaan; 40 mutasi gudang serentak (20 unik + 20 kirim ulang) | Tiap lot tepat **1 pemenang**; komoditas & harga basis kering benar; total lelang ≤ stok; stok gudang = 1.000 kg per komoditas (kirim ulang tidak menggandakan) |
| 2 | Campuran pemicu **slagging** ditolak/ditandai | `test_slagging_blend_rejected_or_flagged` | Tongkol jagung murni: optimizer **menolak**. Campuran jagung + kayu: LAYAK dengan AI ≤ 0,34. Slider 100 % jagung: **BAHAYA**, "Risiko Tinggi Terak/Slagging pada Boiler Industri". Rute energi ikut memperingatkan |
| 3 | Abu lulus uji → **ID kelompok tani** | `test_passing_ash_assigned_to_farmer_group_and_failing_blocked` | Abu lulus dialokasikan ke Poktan; ketua Poktan melihatnya. Alokasi ganda serentak ke 2 Poktan: **satu menang**. Abu Cd 3,1 mg/kg: "gagal" dan diblokir (409) |
| 4 | Injeksi konsumsi daya tinggi → **notifikasi anomali** | `test_injected_power_spikes_flagged_precisely`: 45 log dengan 3 injeksi +30 %, 3 hari beban parsial, 2 hari bahan basah | Alarm **aksi tepat di 3 hari injeksi** (presisi & recall 100 %); beban parsial & bahan basah tanpa alarm; bahan basah muncul sebagai indikator pengering |

## 2. Bug nyata yang ditemukan uji paralel (sudah diperbaiki)

SQLite (mode cadangan lapangan) **mengabaikan `SELECT … FOR UPDATE`**. Pemeriksaan "status → ubah" yang aman di PostgreSQL bisa lolos ganda di SQLite.

| Alur | Akibat sebelum diperbaiki | Perbaikan |
|---|---|---|
| Alokasi abu ke Poktan | Abu yang sama tercatat ke **dua** Poktan | UPDATE bersyarat (compare-and-swap) `WHERE status='tersedia' AND heavy_metal_status='lulus'`; yang kalah mendapat 409 |
| Serah-terima biochar ke sawah | Dua klik "Serahkan" **memotong dompet petani dua kali** | Status diklaim dengan CAS sebelum entri ledger ditulis |
| Putusan klaim karbon | Dua auditor memutus bersamaan, putusan kedua menimpa yang pertama | CAS `WHERE status='diajukan'` |
| Stok gudang keluar (Fase 1) | Stok bisa minus | Cek saldo ulang setelah tulis, di transaksi yang sama |

Uji regresi: `test_double_click_biochar_handover_debits_wallet_once`, `test_parallel_auditor_decisions_record_one`.

## 3. Uji stres multi-node (`scripts/stress_multibiomass.py`)

40 pengguna virtual × 5 putaran, berisi campuran semua peran:
- petani melapor;
- pengepul berebut verifikasi dan mencatat stok dengan kirim ulang;
- pabrik menjalankan blend dan rute konversi;
- auditor membaca ledger.

| Server | Request | Throughput | Error | p50 / p95 / p99 (ms) | Integritas stok |
|---|---|---|---|---|---|
| SQLite (1 proses) | 390 | 121 rps | **0 %** | 283 / 395 / 464 | ✅ |
| PostgreSQL + RLS, 2 worker, dingin | 390 | 75 rps | **0 %** | 257 / 1.741 / 2.037 | ✅ |
| PostgreSQL + RLS, 2 worker, hangat | 390 | 130 rps | **0 %** | 213 / 528 / 686 | ✅ |

Ekor lambat saat dingin merata di semua endpoint, termasuk endpoint baca. Penyebabnya pembukaan koneksi pool (pre-ping + identitas RLS) saat 40 pengguna masuk serentak, bukan logika fitur. Rekomendasi produksi: pemanasan pool saat start, atau PgBouncer.

## 4. Regresi menyeluruh

| Suite | Hasil |
|---|---|
| pytest SQLite (semua) | 506 lulus sebelum Fase 5; ditambah 6 tes Fase 5 → lulus |
| pytest skema PostgreSQL (fitur baru + Fase 5) | lulus |
| pytest PostgreSQL + RLS (`test_postgres.py`, `test_farmer_feedback.py`) | 27 lulus |
| Playwright e2e (22 spec, termasuk multi-biomassa, offline driver, CSP, F11/F14/F18) | **22 lulus** |

## 5. Ringkasan protokol multi-biomassa

| Fase | Commit | Dokumen |
|---|---|---|
| 1 Skema multi-biomassa, gudang berefraksi, ledger abu | b671d8e | docs/16 |
| 2 Prototipe 1: blend biaya terendah + indeks terak | cf44986 (+ ea0e81c keamanan) | docs/17 |
| 3 Prototipe 2: energi riil & rute konversi | 4e5c92e | docs/18 |
| 4 Prototipe 3: SEC/IKE ternormalisasi & anomali | 6848d72 | docs/19 |
| 5 Uji stres & validasi | (commit ini) | docs/20 |
| Riset literatur | — | docs/15 |
