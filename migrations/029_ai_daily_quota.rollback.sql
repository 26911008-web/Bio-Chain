-- Rollback migrasi 029 — hapus tabel kuota harian Asisten AI (aplikasi versi lama tidak memakainya).
BEGIN;
DROP TABLE IF EXISTS user_ai_usage;
DELETE FROM schema_migrations WHERE version = '029_ai_daily_quota';
COMMIT;
