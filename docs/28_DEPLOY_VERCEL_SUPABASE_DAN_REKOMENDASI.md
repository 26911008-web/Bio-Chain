# 28 — Deploy Live Vercel + Supabase dan Rekomendasi Perbaikan

Tanggal: 23 Oktober 2026 · Akun: `26911008@students.uii.ac.id` (GitHub `26911008-web`, Vercel tim MM-OP, Supabase org "26911008-web's Org")

## 1. Status live

| Komponen | Nilai |
|---|---|
| URL publik | https://bio-chain-three.vercel.app |
| Proyek Vercel | `mm-op/bio-chain`, preset FastAPI, region `bom1` (Mumbai), tersambung ke GitHub `26911008-web/Bio-Chain` (setiap push ke `main` = deploy production) |
| Database | Supabase proyek `hlwlugdpeqzmiafilnkw` ("26911008-web's Project"), region `ap-south-1`, PostgreSQL 17 |
| Koneksi app | Supavisor **transaction pooler** `aws-0-ap-south-1.pooler.supabase.com:6543`, TLS wajib, peran `biochain_app` |
| Mode | **DEMO** (`DEMO_MODE=true`, `DEBUG=true`): akun demo publik, seed otomatis |

Verifikasi yang sudah dijalankan pada URL live:
- login dan `/auth/me` untuk 7 akun demo (admin, pabrik, pengepul, driver, auditor, 2 petani): semua 200
- Playwright `e2e_csp_offline_photo.spec.ts -g "CSP tanpa"`: 6/6 dashboard peran terbuka tanpa pelanggaran CSP

## 2. Arsitektur database di Supabase

Dipasang dengan alur yang sama seperti `scripts/pg_setup.py`: `create_all` + `upgrade_schema`, lalu migrasi 002–020.

| Peran | Hak | Dipakai oleh |
|---|---|---|
| `biochain_owner` | pemilik skema, BYPASSRLS (diperlukan migrasi 009 di bawah FORCE RLS) | migrasi / DBA saja |
| `biochain_app` | CRUD + EXECUTE saja, **tanpa** BYPASSRLS, tanpa DDL | aplikasi di Vercel (`AUTO_MIGRATE=false`) |
| `anon`, `authenticated` | **tidak punya hak** atas tabel/fungsi `public` | Data API Supabase ditutup untuk tabel Bio-Chain |

Password kedua peran dibuat acak dan tidak pernah dicetak. Salinannya hanya ada di env Vercel (`DATABASE_URL`, Sensitive). Untuk mengganti password: Supabase → SQL Editor → `ALTER ROLE biochain_app PASSWORD '...'`, lalu perbarui `DATABASE_URL` di Vercel dan redeploy.

Menjalankan migrasi baru (contoh 021): sambung sebagai `biochain_owner` lewat session pooler (port 5432) lalu jalankan file SQL, atau tempel ke Supabase SQL Editor. Setelah itu berikan hak ke `biochain_app` bila ada tabel/fungsi baru (default privileges sudah diset untuk objek milik `biochain_owner`).

## 3. Env Vercel (Production + Preview)

| Nama | Nilai | Catatan |
|---|---|---|
| `DATABASE_URL` | `postgres://biochain_app.<ref>:***@…pooler.supabase.com:6543/postgres?sslmode=require` | Sensitive; `config.py` mengubah otomatis ke `postgresql+asyncpg` dan mempertahankan TLS |
| `PGBOUNCER` | `true` | wajib untuk port 6543: cache prepared statement asyncpg + SQLAlchemy dimatikan, listener LISTEN/NOTIFY dilewati |
| `JWT_SECRET` | acak 64 karakter | Sensitive |
| `AUTO_MIGRATE` | `false` | peran app tidak punya hak DDL |
| `ALLOW_SQLITE_FALLBACK` | `false` | cegah split-brain |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_WARMUP` | `2` / `2` / `0` | pool kecil per instance serverless |
| `DEMO_MODE` / `DEBUG` | `true` / `true` | mode demo |

## 4. Perbaikan kode yang dibuat untuk deploy

| Commit | Isi |
|---|---|
| `b11e5d5` | `is_locked` default `0` → `false()` (Postgres menolak, penyebab CI merah); `pg_setup.py` memakai psql host di GitHub Actions; seed demo `route_stops` mematuhi `ck_stop_pickup_consistent` |
| `5457ab9` | `vercel.json`, `.vercelignore`; normalisasi `DATABASE_URL`; upload ke `/tmp` di Vercel; rate limiter membaca `X-Forwarded-For` dari edge Vercel; perbaikan crash `UnboundLocalError` saat seed gagal |
| `28901cc` | `python-multipart` (tanpanya semua router v2 → 404 di instalasi bersih); dukungan transaction pooler |
| `8915bca` | `python-docx` (ekspor data pribadi UU PDP) |

Catatan CI: `.github/workflows/ci.yml` sengaja tidak diubah karena token `gh` tidak punya scope `workflow`. Deteksi CI dilakukan di `pg_setup.py` lewat `GITHUB_ACTIONS=true`.

## 5. Batasan mode demo (harus diketahui sebelum dibagikan)

1. **Siapa pun bisa login sebagai admin.** Kredensial demo ditampilkan di halaman login (`/auth/demo-accounts`), dan admin bisa mereset data. Jangan masukkan data lapangan sungguhan.
2. **Foto bukti tidak permanen.** Foto disimpan di `/tmp` instance serverless dan hilang saat instance berganti.
3. **Rate limit per instance** (in-memory), bukan global.
4. **Job latar berjalan lokal per instance.** Mode produksi butuh Redis + worker arq yang tidak bisa jalan di Vercel.
5. 4 tes Playwright gagal, dan **sudah gagal sebelum perubahan deploy** (diverifikasi pada commit `3aecca7`): `01_farmer_collector_isolation` TC1.2, `e2e_csp_offline_photo` foto offline, `e2e_field_ux` lelang/stepper, `full_circular_lifecycle`.

## 6. Rekomendasi (prioritas)

Item bertanda **[perlu verifikasi]** belum dicek ke dokumen primer.

### P0 — segera
1. **Lindungi demo publik.** Mengatasi batasan §5.1.
   - Aktifkan Vercel Deployment Protection, atau ganti password admin demo lewat env.
   - Matikan endpoint reset di demo publik.
   - Tambahkan rate limit Vercel Firewall (WAF).
   - Rujukan: OWASP ASVS 5.0 (2025); OWASP API Security Top 10 2023 (API4 Unrestricted Resource Consumption, API5 Broken Function Level Authorization).
   - Skill: `vercel:vercel-firewall`, `vercel:access-protected-vercel-deployment`, `security-review`.
2. **Satukan faktor permanensi karbon.**
   - Masalahnya: `green_scorecard.py` memakai F_perm berbasis suhu (gaya IPCC 2019), sementara `product_optimization.py` (sekitar baris 459–460) meng-hardcode 0,74 dan ~2,2 tCO2e/t. Satu biochar menghasilkan dua angka.
   - Pusatkan ke satu fungsi di `app/params.py` dan wajibkan input lab (suhu puncak, C_org, H/C_org).
   - Rujukan: IPCC 2019 Refinement Vol. 4 Ch. 2 Ap. 4; Woolf et al. 2021, *Environ. Sci. Technol.*, doi:10.1021/acs.est.1c02425.
3. **Pisahkan emisi terhindar dari carbon removal.**
   - Masalahnya: `carbon.py` menghitung substitusi batu bara tetapi memberi label `carbon_credit_equivalent`. Ini kategori yang berbeda dari kredit removal biochar dan berisiko double counting.
   - Rujukan: Puro.earth Biochar Methodology Edition 2025; Verra VM0044 v1.2 (2025).
4. **Simpan foto bukti di Supabase Storage**, dengan bucket privat, policy RLS di `storage.objects`, dan signed URL. Pertahankan pembersihan EXIF. Skill: `vercel:vercel-storage`.

### P1 — berikutnya
5. **Job latar.** Pakai Vercel Cron untuk rekap berkala dan Vercel Queues (Python SDK masih beta) untuk CVRP/HiGHS. Untuk produksi di Indonesia, alternatifnya adalah arq + Upstash Redis + worker di VM. Buat abstraksi `enqueue()`. Skill: `vercel:queues`, `vercel:workflow`.
6. **Cold start.** Lazy-import `ortools`/`scipy` di dalam handler engine, lalu ukur lewat runtime logs. Skill: `vercel:vercel-functions`.
7. **Perbaiki 4 tes e2e yang gagal**, karena menyentuh RLS dan bukti offline. Skill: `engineering:testing-strategy`, `engineering:debug`.
8. **MRV per batch.**
   - Simpan hasil lab per batch: C_org, H/C_org, logam berat, dan PAH.
   - Pasang *quality gate* EBC sebelum biochar/abu dialokasikan ke petani [perlu verifikasi versi EBC yang berlaku].
   - Hitung safety margin ketidakpastian yang bergantung pada frekuensi sampling.

### P2 — nanti
9. **Kalibrasi rendemen pirolisis sekam padi** dengan data lab pabrik sendiri. Angka vendor bukan hasil peer review.
10. **Silika abu.** Bedakan jalur abu sebagai pembenah tanah dan sebagai silika amorf. Catat risiko K3 kristobalit pada suhu tinggi [perlu verifikasi].
11. **VRP.** Kembangkan ke multi-trip, time window, dan backhaul biochar/abu ke petani. Skill: `logistics-expert`, `site-logistics-optimization`.
12. **Offline-first.**
    - Kunci idempotensi di server.
    - Simpan foto sebagai Blob, bukan base64.
    - Sediakan fallback untuk Background Sync di iOS.
13. **Higiene keamanan.**
    - Jalankan Supabase Security Advisor.
    - Rotasi `JWT_SECRET`/`QR_HMAC_KEY`.
    - Pasang OTP (F6).
    - Audit dependensi.

## 7. Tindakan manual pemilik akun

- **Cabut GitHub token lama** (`ghp_…` yang dulu tertanam di URL remote): https://github.com/settings/tokens
- Opsional, agar `ci.yml` bisa diubah dari CLI: `gh auth refresh -h github.com -s workflow`
- Proyek Supabase lama "less78745-pixel's Project" (akun lain) tidak disentuh dan masih dalam status paused.
