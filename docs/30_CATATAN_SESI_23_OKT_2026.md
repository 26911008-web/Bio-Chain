# 30 — Catatan Sesi 23 Okt 2026 (checkpoint)

Status akhir sesi: semua pekerjaan **sudah di `main` (`06dbd55`) dan live** di <https://bio-chain-three.vercel.app>.
Laporan lengkap: `docs/29_AUDIT_KESIAPAN_PRODUKSI_2026-10-23.md` (+ `.docx` lokal).

## Yang selesai
| Area | Hasil |
|---|---|
| Audit 5 pilar + UX | docs/29 — skor kesiapan 5/10 → ±7/10 setelah perbaikan |
| Keamanan | kebocoran notifikasi & PII ditutup, login lockout, JWT fail-closed, rate limit, batas model AI, QR publik bertanda tangan, RLS notifikasi, rating pengepul hanya dari transaksi nyata |
| Database (live) | migrasi **026** (indeks, timeout peran, 92 DEFAULT server), **027** (`notification_reads`, RLS notifikasi, `schema_migrations`), **028** (rating unik per panen) |
| UX | layout HP 360 px (navigasi bawah pabrik yang hilang), "Lompat ke bagian", token warna, aria-label |
| Kode | `factory.py` 1.990→1.071, `farmer.py` 1.208→680, `app.js` 6.328→5.549 baris; `apiRaw()`/`apiDownload()` |
| CI | 3 job per PR/push: ruff · pytest SQLite + **PostgreSQL 17 tes sebagai `biochain_app`** · **Playwright 38 tes** (PR #1) |
| Redis | Upstash gratis `biochain-ratelimit` (bom1) → `/readyz` = `"rate_limiter":"redis"`, login ke-11/menit → 429 |

## Hasil uji terakhir
CI run PR #2: pytest 594 lulus · PostgreSQL 17/17 · Playwright 38/38 · ruff lulus.

## Keputusan tertunda
- **Database Preview terpisah** — opsi gratis: **A** SQLite sementara di `/tmp` (rekomendasi), **B** proyek Supabase gratis kedua, **C** Neon (cabang per preview). Balas "pakai opsi A" untuk menjalankan.
- **`QR_HMAC_KEY`** — isi hanya sebelum mencetak QR produksi (mengisinya membatalkan QR yang sudah tercetak).
- Env Upstash ditandai *Non-sensitive* oleh integrasi — ubah ke Sensitive bila perlu.

## Catatan teknis untuk sesi berikutnya
- Migrasi live: `supabase db query --linked --workdir <folder sb lama> -f <path absolut>` (izin `Bash(supabase db query:*)` sudah ada). Urutan aman skema+kode: tabel dulu → deploy → RLS.
- Uji PG lokal: `docker compose start postgres` → `py scripts/pg_setup.py --reset` → seed (TestClient dengan URL pemilik) → `test_postgres.py` dengan `AUTO_MIGRATE=false ALLOW_SQLITE_FALLBACK=false`.
- Preview Vercel dilindungi login → `MSYS_NO_PATHCONV=1 npx vercel curl /path --deployment <url> --scope mm-op -- <arg curl>`.
- Berkas tak ter-commit (sengaja): `.agents/skills/upstash-*`, `.claude/skills/`, perubahan `skills-lock.json` (skill JS dari instalasi Upstash; tidak dipakai aplikasi Python). `.claude/settings.local.json` = izin lokal.
- Sisa roadmap kode (docs/29 §7): pagination daftar, `response_model` jalur utama, Sentry (perlu DSN), klien HTTP AI bersama.
