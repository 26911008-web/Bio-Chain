# 05 · Audit SRE, Konkurensi & High-Availability

Tanggal: 4 Oktober 2026 · Lingkup: backend FastAPI, frontend `app/static/index.html`, skema DB.

## 1. Bukti beban (k6, `loadtest/k6_double_submit.js`)

Host uji: laptop Windows 11, k6 dan API di mesin yang sama, SQLite, 1 proses Uvicorn.

| Metrik | Sebelum | Sesudah (200 VU, 1.000 klik spam serentak) |
|---|---|---|
| Error 5xx | **2.954** (pool habis 2.858, `database is locked` 61, `IntegrityError` 44) | **0** |
| Efek ganda (harvest/verifikasi dobel) | 0 (diselamatkan constraint, tapi user dapat 500) | **0** (dijawab replay / 409) |
| Health probe p95 | 1,39 s (event loop membeku saat login) | **0,21 s** |
| Penolakan terkendali 503/429 | — | ~62% request saat banjir (Retry-After) |

Batas tersisa yang terukur: **≈10 ms CPU Python per request ⇒ ±100–125 rps per proses**, dan SQLite
hanya punya satu penulis. Pada 1.000 VU di host Windows ini, kegagalan terjadi di level TCP (antrean
`listen` Windows non-server ±200) sebelum aplikasi. Kapasitas produksi = jumlah proses Gunicorn ×
~100 rps, dengan PostgreSQL + PgBouncer untuk penulis paralel. Ulangi uji di staging Linux:

```bash
k6 run -e BASE_URL=https://staging.example -e VUS=1000 -e DURATION=60s loadtest/k6_double_submit.js
```

## 2. Temuan & perbaikan

| # | Temuan | Dampak | Perbaikan |
|---|---|---|---|
| S1 | `/auth/register` menerima role apa pun | siapa pun bisa jadi **admin** | hanya petani/pengepul/supir/pabrik; non-petani menunggu aktivasi admin |
| S2 | `/auth/reset-demo` tanpa autentikasi | hapus seluruh DB | terbuka hanya saat `DEBUG`; produksi khusus admin |
| S3 | `JWT_SECRET` default di kode | token bisa dipalsukan | startup ditolak bila `DEBUG=false` dan secret default |
| S4 | XSS tersimpan: nama petani → `innerHTML` dasbor pengepul | ambil token pengepul | `esc()` + tidak ada data user di atribut `onclick` |
| S5 | Supir bisa konfirmasi stop rute supir lain | manipulasi custody | filter `Route.driver_id == user.id` |
| S6 | Login membocorkan keberadaan akun lewat waktu respons | enumerasi user | hash tiruan untuk user tak dikenal |
| S7 | CDN tanpa SRI | kompromi CDN = XSS | `integrity` sha384 + `crossorigin` |
| S8 | Rate limiter memakai IP Nginx | semua user satu kuota | `X-Forwarded-For` hanya dari `TRUSTED_PROXIES`; bucket login terpisah |
| B1 | PBKDF2 600k sinkron di `async def` | server membeku | `run_cpu` (thread pool terbatas), koneksi DB dilepas sebelum hashing |
| B2 | Pool DB 5+10, tunggu 30 s → 500 | kaskade timeout | pool dari settings, timeout 5 s → **503 + Retry-After** |
| B3 | SQLite tanpa WAL/busy_timeout | `database is locked` | WAL, `busy_timeout`, `synchronous=NORMAL` |
| B4 | Kiriman kembar serentak → `IntegrityError` 500 | user mengira gagal | tangkap → jawab replay |
| B5 | Dispatch ganda serentak harvest yang sama | harvest di 2 rute | unique partial index `route_stops(harvest_id)` → 409 |
| B6 | Form verifikasi pengepul tidak pernah terpasang handler-nya | fitur mati, halaman reload | bind setelah render |
| U1 | Tombol aktif selama request | double submit | `withBusy()` + `aria-busy` |
| U2 | Optimasi rute sinkron | layar menunggu | job 202 + polling "Proses sedang berjalan…" |
| U3 | `prompt()` QR berisi kode contoh palsu | scan salah tercatat | input kosong |

## 3. Arsitektur yang diterapkan

```
Klien ── Nginx (limit_req, keepalive, X-Forwarded-For)
           └─ Gunicorn × (2·CPU+1) UvicornWorker
                 ├─ RateLimiter (Redis sliding window, fail-open)
                 ├─ jalur ringan: CRUD + compare-and-swap state machine
                 ├─ jalur CPU: run_cpu() → thread pool terbatas → 503 bila penuh
                 └─ jalur berat: POST /api/v1/jobs/... → 202 → Redis → arq worker × N
           PgBouncer (transaction) ── PostgreSQL 16 (READ COMMITTED + CAS + unique constraint)
```

## 4. Instalasi stack tambahan

```bash
pip install -r requirements.txt                 # + arq, gunicorn (Linux)
docker compose up -d postgres redis pgbouncer
psql "$DATABASE_URL_SYNC" -f migrations/002_circular_mass_balance.sql
psql "$DATABASE_URL_SYNC" -f migrations/003_concurrency_indexes.sql
# .env produksi
#   DEBUG=false
#   JWT_SECRET=<acak 64 byte>
#   DATABASE_URL=postgresql+asyncpg://biochain:...@localhost:6432/biochain
#   PGBOUNCER=true
#   TRUSTED_PROXIES=127.0.0.1
gunicorn -c deploy/gunicorn.conf.py app.main:app
arq app.worker.WorkerSettings                    # ≥1 proses; wajib bila API > 1 proses
```

Catatan: `JOB_BACKEND=local` hanya valid untuk satu proses API (status job disimpan di memori proses).

## 5. Referensi

- Xing, J. et al. (2025). *Rajomon: Decentralized and Coordinated Overload Control for Latency-Sensitive Microservices.* USENIX NSDI '25.
- Park, J. et al. (2024). *TopFull: An Adaptive Top-Down Overload Control for SLO-Oriented Microservices.* ACM SIGCOMM '24.
- Zhou, H. et al. (2018). *Overload Control for Scaling WeChat Microservices (DAGOR).* ACM SoCC '18.
- Studi PgBouncer (2024), Russian Technological Journal (MIREA): penurunan beban CPU ±15%, RAM 25–50%.
- Tesis UFU (2026). *Connection pooling em PostgreSQL: caracterização empírica do ponto de equilíbrio entre sobrecarga e contenção.*
