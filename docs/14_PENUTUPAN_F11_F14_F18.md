# 14 — Penutupan Celah F11, F14, F18 + Perbaikan Skema SQLite

**Tanggal:** 11 Oktober 2026
**Branch:** `feat/modul-petani-esg-audit`
**Status:** Selesai dan teruji di SQLite, PostgreSQL (skema per tes) dan PostgreSQL + RLS (peran `biochain_app`), plus e2e browser.

Dokumen ini menutup tiga temuan audit lapangan yang sebelumnya berstatus *sebagian* di `docs/06` §7. Dokumen ini juga mencatat satu bug yang ditemukan saat menguji ulang checkpoint `docs/13`.

---

## 0. Bug: pelunasan ber-DP ditolak "kirim ganda" (SQLite)

| | |
|---|---|
| **Gejala** | Pengepul melunasi lot yang sudah dibayar DP. Server menjawab 409 "Pembayaran untuk lot ini baru saja tercatat (kirim ganda)". |
| **Penyebab** | `biochain.db` dibuat sebelum migrasi 016. SQLite `create_all` tidak pernah memperbarui CHECK, jadi `ck_fpay_net` masih `net = bruto − pajak`, tanpa `dp_rp`. PostgreSQL tidak terdampak. |
| **Perbaikan** | `app/migrations.py`: `SQLITE_CHECK_UPGRADES` + `_sqlite_refresh_checks()`. Teks CHECK lama diganti lewat `writable_schema`, yaitu prosedur resmi SQLite untuk perubahan yang tidak mengubah format disk. Pembaruan hanya dilakukan bila semua baris lama memenuhi CHECK baru; bila tidak, server memberi peringatan dan tidak mengubah apa pun. |
| **Aturan ke depan** | Migrasi PG yang mengubah CHECK wajib menambah entri di `SQLITE_CHECK_UPGRADES`. |
| **Uji** | `tests/test_sqlite_check_upgrade.py` |

---

## 1. F18 — HP bersama (keluarga / KUD)

**Kondisi lapangan:** satu HP Android dipakai bergantian, misalnya dua supir satu armada atau petani sekeluarga. Sinyal desa putus-sambung, jadi data sering tertahan di HP.

**Bug nyata yang ditemukan:**
- Supir B login di HP yang sama, lalu `trackFlush()` mengirim titik GPS milik supir A.
- Server menolaknya dengan 404 (rute bukan milik B), dan klien **menghapus** titik-titik itu.
- Akibatnya jejak GPS A, yang merupakan bukti jarak dan emisi Scope 3, hilang permanen.

**Perbaikan (`app/static/app.js`, service worker v11):**
- Titik GPS, foto antrean dan item antrean menyimpan `user_id` + `owner_name`. Flush dan penghitung hanya memproses milik pengguna yang sedang masuk. Data tanpa `user_id` (dari versi lama) dianggap milik pengguna saat ini, sama seperti perilaku sebelumnya.
- Cache rute supir dipisah per pengguna (`biochain_driver_route:<uid>`). Kunci lama tanpa pemilik dihapus saat logout.
- Setelah login muncul pemberitahuan: "HP ini menyimpan N data offline milik ‹nama›… baru terkirim saat pemiliknya login di HP ini." Data tidak pernah dikirim dengan token orang lain.

---

## 2. F14 — QR lot bertanda tangan + cek offline

**Masalah:** QR `BIO-XXXXXXXX` (32 bit) bisa dipalsukan dengan generator QR mana pun. Selain itu, supir yang offline baru tahu QR salah setelah sinyal kembali, padahal truk sudah meninggalkan penggilingan.

**Solusi (`app/services/qr_sign.py`):**
- Format baru `BIO-XXXXXXXX-TTTTTT`: 8 heks acak + 6 karakter base32 dari HMAC-SHA256 dengan kunci server `QR_HMAC_KEY` (env).
- QR palsu atau salah ketik saat input manual langsung ditolak: "QR tidak sah: tanda tangan tidak cocok".
- `GET /driver/active-route` memuat `qr_check` = {salt, SHA-256(salt + QR)} per stop. HP supir mencocokkan QR di lokasi **tanpa sinyal** (`qrMatchesStop`, Web Crypto), sedangkan kode QR tidak pernah dikirim ke supir.
  - Tebak-paksa digest butuh sekitar 2^62 percobaan karena tag bergantung pada kunci server.
- **Rencana migrasi QR tercetak:** QR lama tetap diterima dan pickup-nya ditandai `QR_LAMA` di custody untuk auditor, selama parameter `logistik.qr_legacy_policy` = `terima_tandai`. Ubah ke `tolak` setelah lot lama habis terangkut.
  - QR lama tidak mendapat digest offline, karena 32 bit terlalu mudah ditebak-paksa dari digest.
- QR baru dibuat di semua jalur: lapor petani, lapor via pengepul (petani tanpa HP), lelang, dan seed demo.

**Uji:**
- `tests/test_qr_hmac.py` (5)
- `tests/e2e_f11_f14_f18.spec.ts`
- `e2e_field_compliance` diperbarui ke format baru.

---

## 3. F11 — Alur verifikator klaim removal karbon

**Masalah:** angka karbon hanya berupa estimasi per periode. Serah-terima biochar yang sama bisa muncul di beberapa laporan, dan tidak ada pihak kedua yang memeriksa.

**Solusi (migrasi `017_carbon_claims.sql`, `app/services/carbon_claims.py`):**

| Langkah | Siapa | Aturan |
|---|---|---|
| Pratinjau | Pabrik | Hitung ulang dengan **C-org lab** (menggantikan parameter F_C). Daftar ⛔ penghalang & ⚠️ celah metodologi. |
| Ajukan | Pabrik (bukan admin) | Penghalang wajib nol: ada serah-terima ke lahan yang belum diklaim; H/C-org ≤ `karbon.h_corg_max` (0,7, Puro 2025); removal bersih > 0; periode tidak tumpang-tindih dengan klaim aktif. Snapshot (hasil + nilai parameter + daftar serah-terima) dibekukan dengan **SHA-256**, dan serah-terima **dikunci** (UNIQUE `redemption_id`). |
| Putuskan | Auditor (bukan pengaju, bukan admin) | Catatan wajib ≥ 10 karakter. Verifikasi diblokir bila integritas gagal (hash/kunci berubah). Ditolak → kunci dilepas, pabrik mengajukan klaim perbaikan. |

- **Lapisan DB (PG):**
  - CHECK empat mata (`verified_by_id <> submitted_by_id`).
  - RLS: auditor hanya boleh UPDATE klaim `diajukan` atas namanya sendiri, dan tidak bisa INSERT.
  - Pabrik tidak bisa menyetel status selain `diajukan`.
- **Laporan ESG:** KPI G6 sekarang menampilkan jumlah klaim terverifikasi auditor dan tCO₂e-nya, dengan label tetap *bukan kredit karbon*.
- **Status hukum:** "diverifikasi" = verifikasi internal. Klaim publik atau kredit tetap butuh VVB (Puro/Verra) dan registrasi SRN-PPI (Perpres 110/2025).
- **UI:** kartu 🧾 Klaim Removal Karbon di dashboard pabrik (formulir + pratinjau) dan auditor (daftar + Verifikasi/Tolak).

**Uji:**
- `tests/test_carbon_claims.py` (5)
- `tests/test_postgres.py::test_carbon_claims_rls_only_auditor_decides_in_own_name`
- `tests/test_farmer_feedback.py::test_carbon_claim_submit_and_reject_through_rls`
- e2e

---

## 4. Berkas berubah

| Berkas | Isi |
|---|---|
| `app/migrations.py` | Pembaruan CHECK SQLite |
| `app/static/app.js`, `app/static/sw.js` (v11) | F18; cek QR offline F14 |
| `app/services/qr_sign.py` (baru), `app/config.py` (`QR_HMAC_KEY`) | F14 |
| `app/routers/farmer.py`, `app/routers/collector.py`, `app/services/trade.py`, `app/seed.py` | F14: QR bertanda tangan |
| `app/routers/driver.py` | Verifikasi QR, `qr_check`, penanda `QR_LAMA` |
| `app/params.py` | `logistik.qr_legacy_policy`, `karbon.h_corg_max` |
| `app/models/carbon.py` (baru), `app/services/carbon_claims.py` (baru) | F11 |
| `migrations/017_carbon_claims.sql` (+ rollback), `scripts/pg_setup.py` | F11 |
| `app/engines/green_scorecard.py` | `fc_override` (C-org lab) |
| `app/routers/factory.py`, `app/routers/auditor.py`, `app/security/policy.py`, `app/services/esg.py` | F11 |
| `app/static/factory-ops.js` | UI klaim |
| `docs/06` §7, `docs/11` §4.1a–b | Status & runbook |

## 5. Langkah produksi

1. Isi `QR_HMAC_KEY` di `.env` produksi **sebelum** mencetak QR baru.
2. `py scripts/pg_setup.py`, atau terapkan `migrations/017_carbon_claims.sql`.
3. Umumkan ke pengepul/supir: QR baru lebih panjang; QR lama masih diterima selama masa transisi.
4. Setelah semua lot lama terangkut, ubah `logistik.qr_legacy_policy` ke `tolak` di menu Parameter.
5. Sisa opsional: OTP WhatsApp untuk F6, karena butuh penyedia berbayar dan izin.
