# 29 — Audit Kesiapan Produksi (Security · Arsitektur · Performa · DevOps · AI) — 23 Okt 2026

Basis: commit `6c41265` (main). Metode: pembacaan kode langsung, pemindaian AST, uji Playwright & pytest pada server SQLite bersih,
audit UX visual (screenshot 360×800 & 1366×800 per persona + metrik otomatis). Tidak ada perubahan pada deploy live,
DB Supabase, atau env Vercel. Temuan yang belum bisa dibuktikan dari kode ditandai **UNVERIFIED**.

> **Catatan stack.** Template audit mengasumsikan Next.js + Supabase Auth. Repo ini **FastAPI + PWA vanilla JS** dengan
> auth JWT sendiri; Supabase dipakai sebagai Postgres (pooler 6543) + Storage. Item khusus Next.js (RSC, `'use client'`,
> `getUser()` vs `getSession()`, `next/image`) **N/A**; padanannya (wrapper `api()`, service worker, bundle statis) diaudit.

---

## 1. Executive Summary & Scorecard

| Pilar | Sebelum | Setelah perbaikan sesi ini* |
|---|---|---|
| Security | 5/10 | 7/10 |
| Arsitektur & Type Safety | 5/10 | 5.5/10 |
| Performa & Konkurensi | 6/10 | 7/10 |
| DevOps & Infrastruktur | 4/10 | 4/10 (butuh aksi akun/infra) |
| AI / Layanan Eksternal | 5/10 | 6/10 |
| **Kesiapan produksi** | **5/10** | **6/10** |

\* Perbaikan ada di kode lokal & sudah lulus uji; **belum di-deploy** (lihat §7).

**Ringkasan.** Fondasinya kuat: RBAC tiga lapis (middleware deny-by-default + `require_role` + RLS Postgres FORCE),
PBKDF2 600k, kontrol konkurensi transaksi (fungsi atomik, CAS, indeks unik parsial), dan sanitasi XSS yang konsisten.
Risiko terbesar ada di **tata kelola data pribadi dan konfigurasi**:
- Notifikasi bocor antar-pengguna dengan peran yang sama.
- Nomor HP dan GPS petani terkirim mentah ke semua pengepul. Ini aktif di demo publik.
- Server publik berjalan dengan `DEBUG=true`, sehingga semua guard produksi mati.
- Preview dan Production berbagi DB serta `JWT_SECRET` yang sama.
- Rate limiter mati total di Vercel.

Kode untuk kebocoran data dan rate limit sudah diperbaiki. Konfigurasi env dan infrastruktur memerlukan aksi Anda di Vercel dan Supabase.

---

## 2. CRITICAL FINDINGS (P0 — blocker produksi)

### [P0-1] Notifikasi bocor lintas pengguna + IDOR tandai-baca — ✅ DIPERBAIKI
**Lokasi:** `app/services/notifications.py` (`get_persona_notifications`, `mark_notification_read`, `mark_all_notifications_read`)

**Dampak:**
- `farmer.py:223` dan `custody.py:170-210` mengisi `user_id` sekaligus `target_role`.
- Filter `user_id == me OR target_role == peran` membuat setiap petani melihat laporan, penolakan, dan kode WR/TRX milik petani lain. Pengepul juga melihat tawaran untuk pengepul lain.
- Siapa pun bisa menandai-baca notifikasi orang lain.
- Tabel `notifications` tidak punya RLS, jadi bug ini juga berlaku di live.

```python
# Before
role_filter = (Notification.user_id == user.id) | (Notification.target_role.in_([u_role, "all"]))
update(Notification).where(Notification.id == notif_id)
# After
def _visibility_filter(user):
    ...
    return (Notification.user_id == user.id) | (
        Notification.user_id.is_(None) & Notification.target_role.in_([u_role, "all"]))
update(Notification).where(Notification.id == notif_id, _visibility_filter(user))
```

**Sisa (P2):** status baca notifikasi siaran masih satu kolom global (`is_read`). Solusi tuntas: tabel `notification_reads(user_id, notification_id)` dan RLS pada `notifications`.

### [P0-2] Nomor HP & GPS rumah petani tidak disamarkan di dashboard pengepul (UU PDP) — ✅ DIPERBAIKI
**Lokasi:** `app/routers/collector_bidding.py:303,368,445` (`/collector/offers-dashboard`)

**Dampak:** untuk semua listing terbuka, nomor HP lengkap dan koordinat presisi dikirim ke setiap akun pengepul, termasuk akun demo publik. Padahal sudah ada `mask_phone()` dan jalur ber-log `/harvests/{id}/contact`.

```python
# Before
"farmer_phone": f.phone if f else "-",   "farmer_lat": f.lat ...
# After
"farmer_phone": (mask_phone(f.phone) or "-") if f else "-",   "farmer_lat": round(f.lat, 2) ...  # ±1 km
```

### [P0-3] Server publik berjalan `DEBUG=true` → semua guard produksi mati; Preview = Production — ⚠️ BUTUH AKSI ENV
**Lokasi:** `app/config.py:88` (`DEBUG: bool = True`), `:123` (`if not self.DEBUG:` membungkus semua cek), `docs/28 §3` (env sama untuk Production + Preview)

**Dampak:**
- Defaultnya fail-open. Docs dan OpenAPI terbuka.
- Setiap deploy preview (branch/PR mana pun) memakai `DATABASE_URL` dan `JWT_SECRET` produksi. Kode yang belum di-review bisa menulis ke DB live, dan token preview berlaku di produksi.

**Sudah diperbaiki di kode:**
- `JWT_SECRET` default ditolak bila `PUBLIC_DEMO` atau `VERCEL` aktif (`config.py`, validator `_validate_public_demo`).
- `/docs`, `/redoc` dan `/openapi.json` ditutup saat `PUBLIC_DEMO` (`main.py`).

**Aksi Anda:**
1. Pisahkan env **Preview** dengan DB sendiri (Supabase branch/proyek kedua) dan `JWT_SECRET` berbeda.
2. Aktifkan Vercel Deployment Protection untuk Preview.
3. Untuk produksi sungguhan (bukan demo), set `DEBUG=false`, `DEMO_MODE=false`, `CORS_ORIGINS=https://…`.

---

## 3. HIGH & MEDIUM (P1)

### Security
| ID | Temuan | Lokasi | Status |
|---|---|---|---|
| S-1 | **Rate limiter mati total di Vercel.** Fail-open bila Redis tidak ada; `REDIS_URL` menunjuk localhost. Login, registrasi, AI dan upload tidak dibatasi. Klaim docs/28 §5 ("batas per-instance tetap ada") keliru. | `app/middleware/rate_limiter.py:95` | ✅ Fallback jendela geser in-memory per instance. Tetap disarankan Upstash Redis + aturan WAF untuk `/auth/register`, `/assistant/*`, `/uploads` |
| S-2 | **Login korban bisa dikunci (500 permanen).** Penyerang mendaftar dengan `username` = nomor HP korban, lalu `scalar_one_or_none()` melempar `MultipleResultsFound`. | `app/routers/auth.py` login & register | ✅ HP dicocokkan dulu, baru username (`.first()`); username berupa angka/telepon ditolak; cek silang username↔phone saat registrasi |
| S-3 | `JWT_SECRET` default di repo dipakai bila env hilang pada mode `DEBUG`. Token admin bisa dipalsukan, QR HMAC ikut turun dari secret yang sama. | `app/config.py:45` | ✅ Gagal start di Vercel/PUBLIC_DEMO. **Aksi:** set `QR_HMAC_KEY` terpisah (sekarang turunan JWT_SECRET, sehingga rotasi JWT membatalkan semua QR cetak) |
| S-4 | Endpoint publik traceability mengembalikan PII penuh (HP, koordinat). Lot bisa dienumerasi lewat ID angka atau `ilike` wildcard. Di live tertutup RLS, sehingga fitur QR publik justru **tidak berfungsi** (`/recent` → `[]`). | `app/services/circular_traceability.py:230,262,126` | ✅ (tahap 2) HP disamarkan, koordinat ±1 km, lookup tanpa `ILIKE %…%`. ⏳ Lookup hanya token QR bertanda tangan + role RLS `public_trace` (fitur QR publik di live masih kosong karena RLS) |
| S-5 | `POST /api/v1/biomass` tanpa cek peran. Petani/pengepul bisa mengisi harga dasar dan ambang. Di PG ditolak RLS → 500; di SQLite terjadi eskalasi. | `app/routers/multibiomass.py:111` | ✅ (tahap 2) Non-operator hanya nama/kode + harga & ambang kadar air untuk komoditas **baru**, dibatasi data (harga ≤ 2× harga dasar tertinggi aktif; kadar air acuan 5–30 %, tolak ≤ 40 %). Parameter lab/kimia khusus Pabrik/Admin |
| S-6 | `/uploads/{name}` tanpa auth + `Cache-Control: public, immutable`. Bucket privat Supabase jadi publik lewat proxy ini; field `duplicate` menjadi oracle. | `app/main.py:216`, `app/routers/uploads.py:79` | ✅ (tahap 2) `Cache-Control: private`, PDF `attachment` + `CSP: sandbox`. ⏳ URL bertanda tangan (perlu ubah `<img src>`) |
| S-7 | `/readyz` publik mengembalikan `str(e)` dari driver DB (host/user). | `app/main.py:283` | ✅ Hanya ke log |
| S-8 | Akun demo publik `pabrik` bisa mengubah parameter global & membayar settlement, sehingga merusak demo bagi pengunjung lain. | `app/security/demo_guard.py` | ✅ (tahap 2) Akun demo bersama tidak bisa ubah/reset parameter global saat `PUBLIC_DEMO` (`can_edit=false`) |

### Arsitektur
| ID | Temuan | Lokasi | Status |
|---|---|---|---|
| A-1 | Gagal import router ditelan. App hidup tanpa satu pun API persona, sementara `/health` tetap "ok". Ini pernah terjadi (python-multipart). | `app/main.py:258` | ✅ Gagal keras (`raise`) |
| A-2 | Handler `LookupError` mengubah setiap `KeyError`/`IndexError` (bug kode) menjadi 404 yang membocorkan nama kunci. | `app/main.py:164` | ✅ KeyError/IndexError → 500 + log; `LookupError` domain tetap 404 |
| A-3 | Kegagalan notifikasi di dalam transisi custody ditelan tanpa savepoint. Di PG flush gagal membatalkan transaksi, lalu commit gagal dengan pesan menyesatkan. | `app/services/custody.py:162-215` | ✅ (tahap 2) `begin_nested()` + log; notifikasi angkut/terima kini hanya ke petani pemilik (dulu siaran `all` berisi kode WR & nama driver) |
| A-4 | Migrasi 021–025 tidak ada di `scripts/pg_setup.py`, sehingga CI tidak pernah mengujinya. 024/025 tanpa rollback; 024 tanpa `BEGIN`. RPC di 024/025 tidak dipanggil dari kode mana pun (SQL mati). Tidak ada tabel `schema_migrations`. | `scripts/pg_setup.py:22`, `migrations/` | ✅ (tahap 2) `pg_setup.py` 002–026; rollback 024/025; 024 dalam transaksi. **Diuji di PostgreSQL 16 bersih**: migrasi 023 & 025 ternyata gagal (INSERT seed tanpa kolom NOT NULL) — diperbaiki. ⏳ Tabel `schema_migrations`; RPC 024/025 yang tidak dipakai |
| A-5 | Pemanggilan `fetch()` mentah melanggar CLAUDE.md §3.2. Akibatnya timeout 15 s dan logout-401 dari `api()` tidak berlaku, sehingga UI menggantung di sinyal lemah. | `app.js:1112,1123,1250,2245`, `ui-enhance.js:711`, `factory-ops.js:465`, `field-ops.js:746`, `ai-assistant-widget.js:142` | ✅ (tahap 2) `apiRaw()` + `apiDownload()` di `app.js`; 7 lokasi dialihkan (unduhan, unggah foto timeout 60 s, stream AI timeout header 30 s) |
| A-6 | Batas 500 baris jauh terlampaui: `app.js` 6.328, `field-ops.js` 2.255, `factory.py` 1.990, `farmer.py` 1.208 (tren menurun). | — | ⏳ Lanjutkan pemecahan per persona |
| A-7 | Hanya 5 dari 226 endpoint memakai `response_model`. 285 dari 553 fungsi publik tanpa type hint lengkap. Tidak ada ruff/mypy di CI. | — | ⏳ |

### Performa
| ID | Temuan | Lokasi | Status |
|---|---|---|---|
| P-1 | Solver rute (CVRP) dijalankan sinkron di event loop: dua kali di saran tawaran, satu kali di rencana jemput konsolidasi. `harvest_ids` tanpa batas atas (O(n²)). | `app/services/trade.py:430`, `app/routers/collector_logistics.py:297` | ✅ `run_cpu()`, `max_length=200`, plus filter kepemilikan panen |
| P-2 | Dashboard penawaran memuat **seluruh** tabel `Bid` hanya untuk menghitung jumlah dan nilai max. Tidak ada pagination di mana pun. | `app/routers/collector_bidding.py:264` (+ `factory.py:1747,1757`, `farmer.py:443…`) | ✅ (tahap 2) `max`/`count` per listing via `GROUP BY`. ⏳ Pagination daftar lain |
| P-3 | Polling notifikasi (25 s/pengguna) menjalankan 2 full-table scan seed-check di setiap panggilan. | `app/services/notifications.py:194` | ✅ Seed-check sekali per proses. ⏳ Gabungkan hitungan ke satu query, jeda polling saat tab tersembunyi |
| P-4 | N+1 query: `insights.py:213,231` (per baris QC/settlement), `driver.py:226` (per rute), `multibiomass.py:459` (hingga 1.500 round-trip). | — | ✅ (tahap 2) `driver.py` (1 query untuk semua rute), `insights.py` (batch komoditas), `multibiomass.py` ops-logs (prefetch event & slot, duplikat dalam batch tetap terlewati) |
| P-5 | **UNVERIFIED:** `statement_timeout`/`lock_timeout` dikirim sebagai startup param asyncpg, padahal Supavisor transaction mode bisa mengabaikannya. Akibatnya kueri lambat atau `FOR UPDATE` menunggu sampai Vercel memutus di 60 s. | `app/database.py:43` | ✅ (tahap 2) Migrasi 026: `ALTER ROLE biochain_app SET statement_timeout=15s, lock_timeout=5s, idle_in_transaction_session_timeout=30s` |
| P-6 | Indeks hilang: `custody_events.actor_id`, `biochar_ledger.harvest_id`; notifikasi `(target_role,id)`, `(user_id,id)`. | `app/models/ledger.py:39,84` | ✅ (tahap 2) Migrasi 026 (+ `index=True` di model) |
| P-7 | Leaflet (147 KB) memblokir render di `<head>`. | `app/static/index.html:13` | ✅ `defer` |
| P-8 | SW meng-cache halaman navigasi tanpa cek `res.ok`, sehingga halaman 500 bisa menjadi shell offline. | `app/static/sw.js:27` | ✅ (cache v20) |

### DevOps
| ID | Temuan | Status |
|---|---|---|
| D-1 | Tidak ada error tracking/alerting (Sentry/OTel). `print()` di startup. Tidak ada handler `Exception` global berstruktur. | ⏳ `sentry-sdk[fastapi]` dengan `environment=VERCEL_ENV` |
| D-2 | `requirements.txt` semua `>=`, tanpa lockfile. pytest/pytest-asyncio ikut ke bundle prod. `httpx` salah label "Testing" padahal runtime. | ⏳ `requirements.txt` + `requirements-dev.txt` + `uv pip compile --generate-hashes` |
| D-3 | Versi Python berbeda: CI 3.11, Docker 3.12, Vercel tidak dipin (`.python-version` tidak ada). | ⏳ Pin 3.12 di semua tempat |
| D-4 | CI tidak menjalankan Playwright, ruff, mypy, pip-audit. Deploy Vercel tidak menunggu CI. | ⏳ (token `gh` perlu scope `workflow`) |
| D-5 | Dockerfile single-stage, tanpa `.dockerignore`, tanpa `HEALTHCHECK`, base image tidak dipin digest. `COPY app` ikut membawa `app/static/uploads/*` lokal. | ✅ (tahap 2) `.dockerignore` + `HEALTHCHECK` `/readyz`. ⏳ multi-stage, pin digest (build lokal tidak bisa diuji: TLS PyPI dicegat proxy/antivirus mesin ini) |
| D-6 | `.vercelignore` tidak mencakup `.env.*`, `app/static/uploads/`, `tests/`, `scripts/`. **UNVERIFIED** apakah deploy CLI ikut membawanya. | ✅ (tahap 2) Diverifikasi live: foto lokal `/static/uploads/*` → 404 (deploy dari git). `.vercelignore` dilengkapi sebagai pencegahan |
| D-7 | Tidak ada rencana backup/PITR untuk Supabase live. `backup_pg.sh` hanya untuk self-host. | ⏳ |

### AI / Eksternal
| ID | Temuan | Status |
|---|---|---|
| AI-1 | Klien memilih provider & **model apa saja** (`model: str`, bebas). Tanpa kuota, akun mana pun bisa memakai model mahal atas biaya server. | ✅ Non-admin hanya model default atau `AI_ALLOWED_MODELS`. ⏳ Kuota harian per pengguna + simpan `usage` |
| AI-2 | Input pengguna (`focus`, `full_name`) disisipkan ke system prompt; `history` peran assistant bisa dipalsukan. Dampaknya terbatas (tanpa tool/tulis). | ✅ (tahap 2) `focus` dipindah ke pesan user. ⏳ `full_name` di blok DATA, riwayat sisi server |
| AI-3 | Tanpa retry/backoff/fallback provider. Tanpa batas waktu total stream (60 s per potongan = maxDuration Vercel). | ✅ (tahap 2) Batas total jawaban 50 s di Vercel (`AI_TOTAL_TIMEOUT_S`, otomatis), akhiri rapi dengan catatan terpotong. ⏳ retry/fallback provider |
| AI-4 | `httpx.AsyncClient` dan konteks TLS dibuat per request (AI & Supabase Storage). | ⏳ Klien modul tunggal |

---

## 4. LOW / TECH DEBT (P2)
- `str(e)` di 22 `HTTPException`. `ZeroDivisionError` global → 422 menyamarkan bug (`main.py:208`).
- `except Exception: pass` di `admin.py:194` (dashboard menampilkan nol palsu), `forecaster.py:42` (tanggal invalid diganti diam-diam), `params_store.py:28`.
- Layering terbalik: `services/privacy.py:286` mengimpor `hash_password` dari router. Pindahkan ke `app/security/passwords.py`.
- `lock_row` memakai `UPDATE … SET id=id`, yang ikut menaikkan `updated_at`. Di PG pakai `SELECT … FOR UPDATE`.
- `mark_settlement_paid` memakai `amount_rp` basi (`factory_ops.py:521`). Pakai `UPDATE … RETURNING`.
- 56 `any` di spec Playwright (CLAUDE.md §3.2). Skrip ad-hoc di `tests/` (`reset_driver.py`, dll.).
- Clutter root ter-commit: `bash.bat`, `extracted_spec.txt`, `AUDIT_REPORT.md` (basi), `load_test_40_accounts_report.json`, `seed_biomass_e2e.py`.
- CLAUDE.md §3.2 mengklaim `api()` menangani CSRF/notifikasi/antrean offline. Wrapper tidak melakukannya; perbaiki dokumen.
- Password minimal 6 karakter. Hash legacy `salt$sha256` tidak di-rehash. Tidak ada `POST /auth/logout` server-side. JWT tanpa `aud`/`iss`.
- CSP mengizinkan seluruh host `cdn.jsdelivr.net`/`cdnjs`. Persempit ke path versi, atau self-host.
- `config.py` default `DB_POOL_SIZE=20/OVERFLOW=10/WARMUP=20` berbahaya bila env Vercel hilang.
- scipy diimpor di top-level 4 engine (≈1,3 s cold start). Lazy-import.

---

## 5. Audit UX (Nielsen + Refactoring UI) — persona di HP 360×800

Metode:
- Screenshot setiap persona.
- Metrik DOM otomatis: lebar gulir, target sentuh <40 px, teks <13 px, field tanpa label, error konsol.
- Heuristik Nielsen (severity 0–4).

| # | Masalah | Heuristik | Sev | Status |
|---|---|---|---|---|
| UX-1 | **Layout HP melebar & navigasi bawah hilang.** Layout viewport Chrome Android melebar hingga 1.266 px (pabrik), 637 px (admin) dan 389 px (pengepul). Akibatnya bilah navigasi bawah (`position:fixed`) terdorong ke y≈2.763 px, di luar layar, sehingga **tab Engines/Laporan/Parameter pabrik tak terjangkau di HP**. Penyebab: (a) tabel lebar di wadah `overflow-x:auto` tetap melebarkan viewport; (b) `<select>`/input di grid tidak bisa menyusut; (c) grid inline 4 kolom; (d) kartu by-product. | H3, H4, H8 | 4 | ✅ `contain: layout paint` pada wadah gulir tabel (≤767 px); field `width:100%; min-width:0`; grid 4→2 kolom (≤479 px); kartu by-product `flex-wrap`. Diverifikasi: ke-6 persona `innerWidth=360`, navigasi di dasar layar |
| UX-2 | **Dashboard sangat panjang tanpa navigasi:** pabrik ≈32.900 px, admin 21.700, auditor 18.100, petani 14.300. | H6, H7 | 3 | ✅ Modul baru `js/modules/section-jump.js`: chip "Lompat ke:" dari judul kartu + tombol "↑ Bagian" mengambang |
| UX-3 | Baris tombol header (Notifikasi, Scan QR, Data saya, **Keluar**) terpotong di HP tanpa tanda bisa digeser. | H1, H6 | 3 | ✅ Tepi kanan memudar (mask) sebagai petunjuk gulir |
| UX-4 | Kartu hasil-samping, kartu rute & form blending memakai warna gelap yang dipaku (`#2d3748`, `#a0aec0`, …, 39 tempat), sehingga kontrasnya rusak di tema terang "field" untuk kerja di bawah matahari. | H4, aksesibilitas | 3 | ✅ Diganti token (`--surface-2`, `--ink-muted`, `--border-strong`, `--ink`) |
| UX-5 | Field tanpa label untuk pembaca layar: filter status listing & pembayaran, tabel harga pabrik, tabel blend bahan bakar. | aksesibilitas | 2 | ✅ `aria-label` |
| UX-6 | Radio/checkbox 13×18 px untuk petani/pengepul/driver (pilihan jemput/antar). | ergonomi lapangan | 2 | ✅ 22 px untuk persona lapangan |
| UX-7 | Kalkulator harga pabrik menembak `/pricing/recommend` saat dimuat dan menghasilkan 422 "harga jual belum diisi" (sesuai aturan "harga jual selalu input"). | H1, H9 | 1 | ✅ Sudah ditangani: kartu kalkulator menampilkan banner "harga belum diisi" (bukan toast error); 422 hanya di log konsol |
| UX-8 | Teks 11–12 px di header & badge; tombol `btn-sm` 36 px di persona kantor. | H8 | 1 | Disengaja (mode padat pabrik/admin); biarkan |
| UX-9 | Efek dekoratif three.js memuat ±10 modul dari `cdn.jsdelivr.net` di desktop; sebagian sering gagal (`net::ERR_FAILED`), sehingga konsol kotor dan bandwidth terbuang. Sudah ada sebelum sesi ini. | H8 | 1 | ⏳ Self-host atau matikan di `prefers-reduced-data`/HP |

**Metrik HP 360 px (sebelum → sesudah):**

| Persona | Lebar layout | Field tanpa label |
|---|---|---|
| petani | 360 → 360 | 2 → 0 |
| pengepul | 389 → **360** | 15 → 0 |
| pabrik | 1.266 → **360** | 14 → 0 |
| admin | 637 → **360** | 14 → 0 |
| driver / auditor | 360 → 360 | 0 → 0 |

---

## 6. Hasil uji

| Suite | Sebelum | Sesudah |
|---|---|---|
| Playwright (server SQLite bersih :8766) | **38/38 lulus** (4,4 mnt) | **38/38 lulus** (4,0 mnt) |
| pytest penuh | — | **590 lulus**, 16 dilewati (setelah `test_public_demo` disesuaikan dengan aturan JWT baru) |
| Gate CLAUDE.md (4 suite) + tes baru | — | 57/57 lulus |
| Tes regresi baru `tests/test_audit_prod_2026_10.py` | — | 7/7 lulus |
| **Tahap 2** — pytest penuh (SQLite) | — | **591 lulus**, 0 gagal |
| **Tahap 2** — Playwright | — | **38/38 lulus** (3,6 mnt) |
| **Tahap 2** — migrasi 002→026 di PostgreSQL 16 bersih (Docker) | 023 & 025 **gagal** | semua OK |
| **Tahap 2** — `tests/test_postgres.py` (RLS, trigger, CHECK, konkurensi) | **2/16** lulus (baseline commit `6c41265`) | **15/16** lulus; sisa `test_warehouse_views_match_report_api` (angka API ≠ view — sudah gagal sebelumnya, perlu investigasi) |

---

## 7. STEP-BY-STEP REMEDIATION ROADMAP

**Sudah dikerjakan di sesi ini (lokal, belum di-push):**
- [x] P0-1 isolasi notifikasi · P0-2 masking HP/GPS · S-2 login lockout · S-3 JWT fail-closed · S-7 readyz · docs tertutup di demo publik
- [x] S-1 rate limiter fallback in-memory · AI-1 allowlist model · A-1 router gagal keras · A-2 KeyError≠404
- [x] P-1 solver rute ke thread pool + batas input · P-3 seed-check notifikasi · P-7 Leaflet defer · P-8 SW `res.ok`
- [x] UX-1…UX-6 (layout HP + navigasi bawah pabrik yang hilang, navigasi lompat-bagian, petunjuk gulir header, token warna, aria-label, radio besar)

**Berikutnya, urut prioritas:**
- [x] **(Tahap 2)** S-4 PII traceability · S-5 batas usulan biomassa · S-6 cache bukti privat · S-8 kunci parameter di demo publik
- [x] **(Tahap 2)** Migrasi 026 (indeks P-6, timeout peran P-5, 92 DEFAULT server) · `pg_setup.py` 002–026 · rollback 024/025 · perbaikan 023/025
- [x] **(Tahap 2)** P-2 agregasi `GROUP BY` · P-4 N+1 (driver, insights, ops-logs) · A-3 savepoint notifikasi custody · A-5 `apiRaw()`
- [x] **(Tahap 2)** AI-2 `focus` keluar dari system prompt · AI-3 batas total 50 s di Vercel · D-5 `.dockerignore`/HEALTHCHECK · D-6 `.vercelignore`
- [ ] **(Low, Anda)** Vercel: env **Preview** terpisah (DB + `JWT_SECRET` beda) + Deployment Protection. Set `QR_HMAC_KEY` terpisah.
- [ ] **(Low, Anda)** Upstash Redis via Vercel Marketplace (`REDIS_URL`) + aturan WAF untuk `/api/v1/auth/register`, `/api/v1/assistant/*`, `/api/v1/uploads`.
- [ ] **(Medium)** RLS `notifications` + tabel `notification_reads` (status baca siaran per pengguna). Tabel `schema_migrations`.
- [ ] **(Medium)** Traceability publik via token QR bertanda tangan + role RLS `public_trace` (fitur QR publik di live saat ini kosong). URL bertanda tangan untuk `/uploads`.
- [ ] **(Medium)** Investigasi `test_warehouse_views_match_report_api` (laporan API ≠ view SQL di PostgreSQL).
- [ ] **(Medium)** D-1 Sentry · D-2 lockfile + pisah dev deps (butuh ubah CI) · D-3 pin Python (cek dulu versi build Vercel saat ini) · D-7 backup/PITR.
- [ ] **(High, butuh token `gh` ber-scope `workflow`)** D-4 CI: ruff + mypy + pip-audit + job PostgreSQL (`test_postgres.py`) + job Playwright, gate promosi produksi.
- [ ] **(High)** A-6 pemecahan `app.js`/`factory.py`/`farmer.py` · A-7 `response_model` di jalur utama · pagination daftar.
- [ ] **(Medium)** AI-3 retry/fallback provider · AI-4 klien HTTP tunggal · kuota token per pengguna.

---

### Temuan baru tahap 2
- **Suite PostgreSQL tidak pernah benar-benar lulus.** CI hanya menjalankan SQLite, dan `test_postgres.py` dilewati. Pada PG bersih hanya 2 dari 16 tes yang lulus. Penyebab utamanya: 92 kolom NOT NULL hanya punya default di Python (dibuat lewat `create_all`), sehingga setiap INSERT lewat SQL, PL/pgSQL, atau alat impor gagal. Migrasi 026 memasang DEFAULT di server untuk semuanya; kolom yang tidak ada dilewati dengan aman. Di live, `harvests.transaction_mode` terverifikasi tanpa DEFAULT (query baca-saja).
- Migrasi 023 dan 025 gagal di skema hasil model (INSERT seed `loading_ramps`/`feedstock_parameters` tanpa `is_active`). Sudah diperbaiki.

## 8. MISSING CONTEXT / BLIND SPOTS
- Nilai env Vercel aktual (Production vs Preview), status Deployment Protection, kunci AI yang aktif: tidak diperiksa (konektor MCP login ke akun lain; nilai rahasia tidak dibuka).
- Status migrasi 021–025 dan RLS aktual di DB Supabase live: tidak di-query.
- Apakah deploy CLI membawa `.env.local` / `app/static/uploads/` (cek `list_deployment_files`).
- Paket & PITR Supabase.
- `app.js` (6.300 baris) dan `factory.py` dicek dengan grep + sampel, belum dibaca utuh baris per baris.
- Uji UX dengan pengguna lapangan sungguhan. Heuristik menemukan ±75% masalah; sisanya butuh uji pengguna.
