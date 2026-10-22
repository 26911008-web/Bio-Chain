# 11 — Runbook Operasional Bio-Chain

Untuk petugas TI / admin sistem. Setiap prosedur ditulis langkah demi langkah dan bisa dijalankan tanpa pengembang. Stack: FastAPI (gunicorn + UvicornWorker, `deploy/gunicorn.conf.py`) di belakang nginx, PostgreSQL 16 dengan RLS, Redis (rate limit & antrean job), PWA dengan service worker.

---

## 1. Pemeriksaan rutin

| Kapan | Periksa | Cara | Tindakan bila gagal |
|---|---|---|---|
| Harian 07.00 | API hidup | `curl -fsS https://<domain>/api/v1/system/status` | §5 Insiden |
| Harian | Backup semalam ada & utuh | `ls -lh /var/backups/biochain/` (file 02.15) | jalankan `scripts/backup_pg.sh` manual, cek log |
| Harian | Antrean offline tidak menumpuk | Admin → Panel: lot "antre (offline)" > 24 jam | hubungi pengguna; cek sinyal/versi aplikasi |
| Mingguan | Potongan logistik terbuka & DP "wajib dikembalikan" | Pabrik → Potongan Logistik; laporan pembayaran | tindak lanjut dengan pengepul/petani |
| Mingguan | Register penghematan | Pabrik → Optimasi & Penghematan | verifikasi aksi "berjalan" (empat mata + bukti) |
| Bulanan | **Uji pulih backup** | §3.2 | perbaiki skrip/penyimpanan sebelum dibutuhkan |
| Bulanan | Laporan ESG & Laporan Bulanan | Pabrik → Laporan ESG → CSV | arsipkan; cek KPI kosong (data belum dicatat) |
| Tiap 3 bulan | Rotasi password admin & cek akun nonaktif | Admin → Pengguna | nonaktifkan akun tak terpakai |

## 2. Rilis / redeploy

1. **Backup dulu**: `BIOCHAIN_PG_URL=... scripts/backup_pg.sh`.
2. Tarik versi baru, pasang dependensi: `pip install -r requirements.txt`.
3. Jalankan uji di server staging:
   - `py -m pytest -q` (SQLite), lalu
   - PostgreSQL: `DATABASE_URL=postgresql+asyncpg://biochain_app:...@host/biochain AUTO_MIGRATE=false BIOCHAIN_TEST_PG_OWNER_URL=... py -m pytest -q`.
4. Terapkan migrasi (§2.1).
5. **Naikkan versi service worker** bila ada perubahan file `app/static/*`: `const VERSION = "biochain-shell-vN"` di `app/static/sw.js` — tanpa ini HP petani tetap memakai tampilan lama.
6. Restart tanpa putus: `kill -HUP <pid master gunicorn>` (worker diganti bertahap; `gunicorn -c deploy/gunicorn.conf.py app.main:app`). Bila memakai beberapa host di belakang nginx, restart satu per satu (`proxy_next_upstream` mengalihkan sementara).
7. Uji asap: login 1 akun per peran, buka dashboard, kirim 1 laporan uji di akun demo staging.

### 2.1 Migrasi database

- Daftar & urutan: `scripts/pg_setup.py` (`MIGRATIONS`), saat ini 002 → 016, lalu `000_app_role.sql` (hak `biochain_app`).
- Semua migrasi idempoten (`IF NOT EXISTS`); aman diulang: `py scripts/pg_setup.py`.
- Aplikasi produksi berjalan dengan `AUTO_MIGRATE=false` sebagai peran `biochain_app` (NOSUPERUSER, NOBYPASSRLS).
- **Rollback**: setiap migrasi punya `migrations/NNN_*.rollback.sql`. Jalankan sebagai pemilik DB, dari nomor terbaru mundur:
  `psql "$OWNER_URL" -f migrations/016_audit_hardening.rollback.sql`. Baca peringatan di kepala file (data apa yang hilang) dan **ekspor tabel terkait dulu**.

## 3. Backup & pemulihan

### 3.1 Backup
- Cron 02.15 WIB: `scripts/backup_pg.sh` (pg_dump format custom, rotasi, cek isi arsip memuat tabel inti).
- Wajib salinan luar server: `BACKUP_RSYNC_TARGET=user@host:/backup/biochain`.
- RPO harian. Untuk RPO menit gunakan pgBackRest / WAL-G (archive_command).

### 3.2 Uji pulih (bulanan) / pemulihan nyata
1. `createdb biochain_restore`
2. `pg_restore --no-owner -d biochain_restore /var/backups/biochain/biochain-YYYYMMDD-HHMM.dump`
3. Bandingkan: `SELECT count(*) FROM harvests; SELECT count(*) FROM farmer_payments; SELECT max(created_at) FROM custody_events;`
4. Pemulihan nyata: hentikan aplikasi → ganti nama DB lama (`ALTER DATABASE biochain RENAME TO biochain_rusak`) → `biochain_restore` → `biochain` → `py scripts/pg_setup.py` (memastikan peran & RLS) → jalankan aplikasi → uji asap.
5. Catat waktu mulai–selesai (RTO) di log insiden.

## 4. Keamanan

### 4.1 Rotasi rahasia JWT
- Ganti `JWT_SECRET` (≥ 32 karakter acak; produksi menolak nilai default/pendek) → restart semua worker. **Semua pengguna harus login ulang** — umumkan ke pengepul/petani lebih dulu.
- Mencabut sesi SATU akun (HP hilang/dicuri) tanpa memutus semua orang: Admin → reset password akun tersebut. `users.token_version` naik → semua token lama akun itu langsung ditolak; pemilik wajib mengganti password sementara (ditegakkan server).

### 4.1a Kunci tanda tangan QR lot (F14)
- Isi `QR_HMAC_KEY` (≥ 32 karakter acak, terpisah dari `JWT_SECRET`) **sebelum** QR pertama dicetak. Tanpa itu kunci diturunkan dari `JWT_SECRET`, sehingga rotasi JWT ikut membatalkan semua QR tercetak.
- Mengganti `QR_HMAC_KEY` membuat QR bertanda tangan yang sudah tercetak ditolak "QR tidak sah". Lakukan hanya bila kunci bocor, lalu minta pengepul/petani menampilkan ulang QR lot yang belum diangkut dari aplikasi.
- Masa transisi QR lama `BIO-XXXXXXXX` (nota/karung sebelum F14): parameter `logistik.qr_legacy_policy` = `terima_tandai` (diterima, pickup ditandai `QR_LAMA` untuk auditor). Ubah ke `tolak` setelah semua lot lama terangkut.

### 4.1b Klaim removal karbon (F11)
1. Pabrik: menu 🧾 Klaim Removal Karbon → pilih bulan, isi C-org & H/C-org dari laporan lab, foto laporan → **Pratinjau**. Penghalang (⛔) wajib nol sebelum **Ajukan**.
2. Auditor (akun lain): periksa foto lab, serah-terima & suhu batch → Verifikasi/Tolak dengan catatan. Tombol Verifikasi mati bila badge "integritas gagal" muncul (snapshot berubah setelah diajukan → selidiki, lalu tolak).
3. Ditolak → serah-terima dilepas; pabrik mengajukan klaim perbaikan. "Diverifikasi" = verifikasi internal, **bukan kredit karbon**; klaim publik perlu VVB (Puro/Verra) & SRN-PPI (Perpres 110/2025).

### 4.2 Header & CORS
- **CSP diset aplikasi** (`app/security/headers.py`): skrip hanya dari server sendiri + CDN tepercaya, **tanpa `'unsafe-inline'`**; hash importmap dihitung otomatis dari `index.html` saat start. Header HSTS/nosniff/dll. juga di nginx include `/etc/nginx/biochain_security_headers.conf` (jangan tambah CSP kedua di nginx).
- Kode halaman WAJIB di file `/static/*.js`. Tombol memakai `data-onclick="fungsi(arg)"` (argumen literal saja), bukan `onclick=` — handler inline akan diblokir browser.
- Menambah CDN/domain baru = ubah `CDN_SCRIPTS`/direktif di `app/security/headers.py`; bila tidak, browser memblokir (konsol: "Refused to load"). Darurat: `CSP_ENABLED=false` (sementara, catat di log insiden).
- `CORS_ORIGINS` wajib https di produksi; kredensial lintas-origin dimatikan (auth memakai Bearer token).

### 4.3 Kebocoran data pribadi (UU 27/2022 PDP)
1. Hentikan sumber (cabut token: §4.1; nonaktifkan akun/endpoint).
2. Catat kronologi, data apa, berapa subjek (insiden G3 belum punya modul — catat di dokumen insiden).
3. **Pemberitahuan tertulis ke subjek data & lembaga pelaksana paling lambat 3 × 24 jam** (UU PDP Ps. 46).
4. Pulihkan & perbaiki; dokumentasikan untuk laporan ESG (GRI 418-1).

## 5. Insiden umum & penanganan

| Gejala | Kemungkinan | Penanganan |
|---|---|---|
| API 503 / lambat | worker penuh, DB lambat | cek proses gunicorn & log (X-Request-ID); `pg_stat_activity`; naikkan `workers` di `deploy/gunicorn.conf.py`; cek query panjang |
| Login semua orang gagal | `JWT_SECRET` berubah / jam server salah | samakan secret di semua worker; `timedatectl` (NTP) |
| HP petani tampilan lama | service worker belum naik versi | naikkan `VERSION` di `sw.js`, redeploy |
| "Sisa stok tidak mencukupi" saat terima tawaran | balapan lelang (perilaku benar) | tidak perlu tindakan — fungsi `accept_bid_atomic` mencegah alokasi ganda (diuji 20 koneksi serentak) |
| Rute ditolak "melebihi kapasitas truk" | muatan > m³ bak atau > muatan maks | pecah rute / pakai Dispatch Otomatis (OR-Tools membatasi volume **dan** berat) |
| Laporan offline tidak terkirim | sinyal, token kedaluwarsa | minta pengguna buka aplikasi saat ada sinyal; cek kotak "Ditolak server" |
| Harga pabrik "belum diisi" | parameter harga jual kosong | Pabrik → Parameter → Pabrik & Biaya Produksi |

## 6. Uji ketahanan (chaos) yang tersedia

| Uji | File | Membuktikan |
|---|---|---|
| 20 penerimaan tawaran serentak | `tests/test_postgres.py::test_twenty_concurrent_accepts_never_double_allocate` | Σ diterima ≤ stok, tidak ada alokasi ganda |
| Antrean offline driver | `tests/e2e_offline_driver.spec.ts` | data GPS & pickup terkirim tepat sekali saat online |
| Mode hemat sinyal petani | `tests/e2e_field_ux.spec.ts` | laporan offline terkirim otomatis satu kali |
| Kompresi foto 12 MP | `tests/e2e_photo_compression.spec.ts` | ≤ 300 KB, ≤ 1600 px |
| Refraksi sekam basah di gerbang | `tests/test_factory_ops.py::test_qc_wetter_than_contract…` | kg basis kering & harga disetarakan |
| Pencabutan token | `tests/test_audit_hardening.py` | ganti/reset password memutus sesi lama |

Jalankan Playwright: server demo bersih (`DATABASE_URL=sqlite+aiosqlite:///e2e.db py -m uvicorn app.main:app --port 8765`), lalu `BIOCHAIN_URL=http://127.0.0.1:8765 npx -y @playwright/test@1.64.0 test tests/<spec>`.

## 7. Kontak & eskalasi

Isi sesuai organisasi: penanggung jawab TI, admin pabrik, DPO (pejabat pelindungan data pribadi), penyedia hosting.
