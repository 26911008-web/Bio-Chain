-- Bio-Chain v2 · Migrasi 003 — Indeks hot-path & guard dispatch ganda (PostgreSQL 16)
--
-- NON-BLOCKING: CREATE INDEX CONCURRENTLY tidak mengunci tabel dari INSERT/UPDATE, tetapi TIDAK boleh
-- di dalam transaksi. Jalankan dengan autocommit:
--   psql "$DATABASE_URL_SYNC" -v ON_ERROR_STOP=1 -f migrations/003_concurrency_indexes.sql
-- Bila satu CONCURRENTLY gagal, indeks tertinggal INVALID; hapus dengan rollback 003 lalu ulangi.
-- Rollback: migrations/003_concurrency_indexes.rollback.sql

SET lock_timeout = '5s';          -- jangan antre lama di belakang transaksi panjang
SET statement_timeout = 0;        -- pembuatan indeks boleh lama (tidak memblokir penulis)

-- 0. Pra-cek: dispatch ganda yang sudah terlanjur ada akan menggagalkan unique index.
DO $$
DECLARE dup integer;
BEGIN
  SELECT harvest_id INTO dup FROM route_stops WHERE harvest_id IS NOT NULL
   GROUP BY harvest_id HAVING COUNT(*) > 1 LIMIT 1;
  IF dup IS NOT NULL THEN
    RAISE EXCEPTION 'harvest_id % ada di lebih dari satu route_stop — bereskan sebelum migrasi 003', dup;
  END IF;
END $$;

-- 1. Antrean pengepul: WHERE status='reported' ORDER BY reported_at DESC
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_harvests_status_reported ON harvests (status, reported_at DESC);
-- 2. Riwayat petani: WHERE farmer_id=? ORDER BY reported_at DESC
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_harvests_farmer_reported ON harvests (farmer_id, reported_at DESC);
-- 3. Rute aktif supir & daftar stop
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_routes_driver_status ON routes (driver_id, status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_route_stops_route_order ON route_stops (route_id, stop_order);
-- 4. Satu harvest hanya di satu stop: dua dispatch serentak → unique violation → API 409
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_route_stops_harvest
  ON route_stops (harvest_id) WHERE harvest_id IS NOT NULL;

-- 5. Isolasi transaksi: tetap READ COMMITTED (default). Kebenaran dijamin compare-and-swap
--    (UPDATE ... WHERE status = <asal>) yang dievaluasi ulang setelah row lock, ditambah unique
--    constraint. SERIALIZABLE tidak dipakai: menambah abort 40001 di bawah beban tanpa manfaat
--    tambahan bagi pola akses ini. Timeout per sesi diset aplikasi (statement/lock/idle timeout).
