# Migrasi Database

Strategi **expand → deploy → contract**: setiap migrasi hanya *menambah* (kolom nullable/berdefault,
tabel, indeks), sehingga kode lama tetap berjalan selama migrasi. Kolom tidak pernah di-rename
atau di-drop dalam rilis yang sama.

| # | File | Sifat | Mengunci tabel? | Rollback |
|---|------|-------|-----------------|----------|
| 002 | `002_circular_mass_balance.sql` | tambah kolom timbangan, tabel custody/ledger, trigger append-only | `ALTER ... ADD COLUMN` dengan default konstan = metadata-only di PG ≥ 11 (sekejap) | `002_circular_mass_balance.rollback.sql` (**menghapus data audit**; ekspor dulu) |
| 003 | `003_concurrency_indexes.sql` | indeks hot-path + unique `route_stops(harvest_id)` | Tidak — `CREATE INDEX CONCURRENTLY` | `003_concurrency_indexes.rollback.sql` (hanya indeks) |
| 004 | `004_row_level_security.sql` | RLS per peran (petani/pengepul/driver/pabrik/auditor) | Tidak (DDL kebijakan) | `004_row_level_security.rollback.sql` |
| 005 | `005_b2b_trade.sql` | pasar B2B: listing, tawaran, resi `TRX-…`, bukti foto, RLS | Tidak (tabel/kolom baru) | `005_b2b_trade.rollback.sql` (data lelang hilang; resi di custody tetap) |
| 006 | `006_system_parameters.sql` | parameter asumsi yang dapat diubah lewat menu + riwayat append-only | Tidak (tabel baru) | `006_system_parameters.rollback.sql` (kembali ke default) |
| 007 | `007_factory_operations.sql` | procurement B2B (ajuan & negosiasi), QC masuk, batch manufaktur 1→3+loss, biaya, RLS | Tidak (tabel baru) | `007_factory_operations.rollback.sql` (data operasi pabrik hilang; ekspor dulu) |
| 008 | `008_silica_routes_wallet_link.sql` | 3 jalur bio-silika, loss gas pembakaran, Delivery Request → harvest → dompet biochar | Tidak (kolom/constraint baru) | `008_silica_routes_wallet_link.rollback.sql` (entri dompet dipertahankan) |
| 009 | `009_fix_rls_recursion.sql` | perbaiki siklus RLS `stock_listings` ↔ `bids` (ditemukan saat uji di PostgreSQL) via `bids.farmer_id` | Tidak | `009_fix_rls_recursion.rollback.sql` |
| 010 | `010_reporting_warehouse.sql` | view gudang data bulanan (pasokan, konversi, biaya, dompet) `security_invoker` + indeks | Tidak | `010_reporting_warehouse.rollback.sql` (hanya view/indeks) |
| 011 | `011_collector_settlements.sql` | pembayaran pabrik→pengepul untuk jalur QC **dan** rute armada; RLS (pengepul baca miliknya); `wh_monthly_cost` dari settlements + `unpriced_kg`; backfill lot QC lama | Tidak | `011_collector_settlements.rollback.sql` (hapus catatan pembayaran) |
| 000 | `000_app_role.sql` | peran `biochain_app` NOSUPERUSER NOBYPASSRLS + GRANT (jalankan TERAKHIR) | Tidak | `DROP OWNED BY biochain_app; DROP ROLE biochain_app;` |

## Urutan produksi (PostgreSQL)

```bash
pg_dump "$DATABASE_URL_SYNC" -Fc -f backup_pre_002.dump          # 1. cadangan penuh
psql "$DATABASE_URL_SYNC" -v ON_ERROR_STOP=1 -f migrations/002_circular_mass_balance.sql
psql "$DATABASE_URL_SYNC" -v ON_ERROR_STOP=1 -f migrations/003_concurrency_indexes.sql   # autocommit
psql "$DATABASE_URL_SYNC" -v ON_ERROR_STOP=1 -f migrations/004_row_level_security.sql
psql "$DATABASE_URL_SYNC" -v ON_ERROR_STOP=1 -f migrations/005_b2b_trade.sql
psql "$DATABASE_URL_SYNC" -v ON_ERROR_STOP=1 -f migrations/006_system_parameters.sql
psql "$DATABASE_URL_SYNC" -v ON_ERROR_STOP=1 -f migrations/007_factory_operations.sql
psql "$DATABASE_URL_SYNC" -v ON_ERROR_STOP=1 -f migrations/008_silica_routes_wallet_link.sql
psql "$DATABASE_URL_SYNC" -v ON_ERROR_STOP=1 -f migrations/009_fix_rls_recursion.sql
psql "$DATABASE_URL_SYNC" -v ON_ERROR_STOP=1 -f migrations/010_reporting_warehouse.sql
psql "$DATABASE_URL_SYNC" -v ON_ERROR_STOP=1 -f migrations/011_collector_settlements.sql
psql "$DATABASE_URL_SYNC" -v ON_ERROR_STOP=1 -f migrations/012_settlement_events_and_constraints.sql
psql "$DATABASE_URL_SYNC" -v ON_ERROR_STOP=1 -v app_password="'<rahasia>'" -f migrations/000_app_role.sql
# 2. deploy kode baru (gunicorn reload bertahap)
```

Rollback: deploy kode lama dulu, lalu jalankan `003_*.rollback.sql`, kemudian (bila perlu) `002_*.rollback.sql`.

## SQLite / dev

Tidak perlu langkah manual: `app/migrations.py` dijalankan saat startup, menambah kolom & indeks
yang belum ada secara idempoten. Unique index `uq_route_stops_harvest` dilewati (dengan peringatan)
bila data lama berisi harvest di lebih dari satu stop — hapus stop duplikat, lalu restart.


## Menjalankan di PostgreSQL (lokal, Docker)

```bash
docker compose up -d postgres                         # PostgreSQL 16 di localhost:5433 (5432 sering terpakai)
py scripts/pg_setup.py --reset                        # skema → migrasi 002–008 → peran biochain_app
# Jalankan aplikasi sebagai peran TANPA hak bypass RLS (superuser/pemilik tabel melewati RLS!)
set DATABASE_URL=postgresql+asyncpg://biochain_app:biochain_app_dev@localhost:5433/biochain
set AUTO_MIGRATE=false
py -m uvicorn app.main:app --port 8000
# Tes: seluruh suite + uji khusus PG (RLS, trigger, CHECK, resi atomik); alur bisnis di skema PG terisolasi
set BIOCHAIN_TEST_PG_OWNER_URL=postgresql+asyncpg://biochain:biochain_dev_2026@localhost:5433/biochain
py -m pytest -q
```
