# 22 — Catatan Sesi & Titik Pulih (Checkpoint) Bio-Chain

**Disimpan:** 12 Oktober 2026 · **Branch:** `feat/modul-petani-esg-audit` · **Commit terakhir:** `970e2f1`
**Status:** semua pekerjaan sudah di-commit, tidak ada perubahan menggantung. Hanya `bash.bat` dan `load_test_40_accounts_report.json` yang masih tidak dilacak, dan sengaja tidak disentuh.

## 1. Yang dikerjakan sesi 11–12 Oktober 2026

| Commit | Isi | Dokumen |
|---|---|---|
| aedafd6 | Penutupan F11 (klaim karbon empat mata), F14 (QR HMAC + cek offline), F18 (HP bersama); perbaikan CHECK SQLite (pelunasan ber-DP) | docs/14 |
| b671d8e | **Fase 1:** master 7 komoditas biomassa Jawa, gudang pengepul berefraksi, ledger abu ke Poktan (migrasi 018) | docs/15 (riset), docs/16 |
| cf44986, ea0e81c | **Fase 2 / Prototipe 1:** blend bahan bakar biaya terendah + indeks terak; fix keamanan payload master | docs/17 |
| 4e5c92e | **Fase 3 / Prototipe 2:** energi riil basis kadar air lapangan & pohon keputusan rute konversi | docs/18 |
| 6848d72 | **Fase 4 / Prototipe 3:** SEC/IKE ternormalisasi & detektor anomali ISO 50001 (migrasi 019) | docs/19 |
| a8c9601 | **Fase 5:** uji stres multi-node & validasi sirkular; race SQLite diperbaiki dengan CAS | docs/20 |
| d210a62 | Audit pasca-protokol: **19 bug** diperbaiki (migrasi 020) | docs/21 |
| 970e2f1 | Temuan minor D1–D6 (ekor lambat PG, CUSUM, daftar admin PG, tes flaky) | docs/21 |

## 2. Hasil uji terakhir

| Suite | Hasil |
|---|---|
| pytest SQLite (`py -m pytest -q --deselect tests/test_routing.py::test_latency_slo`) | **526 lulus**, 16 dilewati (khusus PG) |
| pytest PostgreSQL + RLS (`test_postgres`, `test_farmer_feedback`, `test_audit_hardening`) | **36 lulus** |
| Playwright e2e (22 spec) | **22 lulus** |
| Uji stres 40 pengguna (`scripts/stress_multibiomass.py`) | error 0 %; PG hangat p95 ±0,5–0,65 s; dingin ±1,0 s |

## 3. Cara melanjutkan

```powershell
docker start biochain-postgres
py scripts/pg_setup.py                      # migrasi s.d. 020 (idempoten)
.\jalankan.ps1                              # atau jalankan.bat
py -m pytest -q -p no:cacheprovider --deselect "tests/test_routing.py::test_latency_slo"
```

PG + RLS:
```powershell
$env:DATABASE_URL="postgresql+asyncpg://biochain_app:biochain_app_dev@localhost:5433/biochain"; $env:AUTO_MIGRATE="false"
py -m pytest -q tests/test_postgres.py tests/test_farmer_feedback.py tests/test_audit_hardening.py
```

E2E: jalankan server SQLite bersih di :8766, lalu `scripts/seed_e2e_audit.py`, lalu `npx -y @playwright/test@1.64.0 test tests/ --workers=1` dengan `BIOCHAIN_URL=http://127.0.0.1:8766`.

## 4. Aturan & catatan penting

- **SQLite mengabaikan `SELECT … FOR UPDATE`.** Setiap alur "baca status/saldo → cek → tulis" wajib memakai `app/services/locks.py::lock_row` atau UPDATE bersyarat (CAS).
- Tes tanpa `DATABASE_URL` memakai **PostgreSQL dev** (default config) saat Docker hidup, bukan `biochain.db`.
- Setelah uji stres `--workers 2`, matikan juga proses anak `spawn_main`. Kalau tidak, mereka memegang koneksi PG ("too many clients").
- Server e2e berjalan tanpa `--reload`, jadi restart setelah mengubah engine.

## 5. Sisa pekerjaan (di luar kode)

1. Ganti nilai master biomassa (literatur) dengan **hasil lab per lot** (ISO 18134/18122/18125, XRF oksida abu).
2. Pabrik mengisi **harga dasar** tiap komoditas dan **biaya pengeringan per kg air** (sengaja tanpa nilai bawaan).
3. Isi `QR_HMAC_KEY` di `.env` produksi **sebelum** mencetak QR baru.
4. Status hukum abu 100 % biomassa belum eksplisit di PP 22/2021: simpan uji karakteristik dan konsultasi ke DLH.
5. Opsional: OTP WhatsApp (F6), analisis NPV/biaya modal untuk rute konversi, readiness probe/PgBouncer untuk produksi.
