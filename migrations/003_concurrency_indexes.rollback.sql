-- Rollback migrasi 003 — hanya menghapus indeks; tidak ada data yang hilang.
-- Jalankan dengan autocommit (DROP INDEX CONCURRENTLY tidak boleh di dalam transaksi).
SET lock_timeout = '5s';
DROP INDEX CONCURRENTLY IF EXISTS uq_route_stops_harvest;
DROP INDEX CONCURRENTLY IF EXISTS ix_route_stops_route_order;
DROP INDEX CONCURRENTLY IF EXISTS ix_routes_driver_status;
DROP INDEX CONCURRENTLY IF EXISTS ix_harvests_farmer_reported;
DROP INDEX CONCURRENTLY IF EXISTS ix_harvests_status_reported;
