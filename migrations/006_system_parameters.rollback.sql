-- Rollback migrasi 006. Semua modul kembali memakai default bawaan kode. Riwayat perubahan ikut terhapus —
-- ekspor dulu: pg_dump "$DATABASE_URL_SYNC" -t system_parameters -t parameter_changes > backup_006.sql
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TRIGGER IF EXISTS trg_param_changes_append_only ON parameter_changes;
DROP TABLE IF EXISTS parameter_changes;
DROP TABLE IF EXISTS system_parameters;
COMMIT;
