-- Rollback 014 — hapus tabel kepatuhan & kolom users baru. PERINGATAN: bukti bayar & jejak persetujuan ikut hilang;
-- ekspor dulu (pg_dump -t farmer_payments -t consents -t data_requests) bila sudah dipakai di lapangan.
BEGIN;
DROP TABLE IF EXISTS data_requests;
DROP TABLE IF EXISTS consents;
DROP TABLE IF EXISTS farmer_payments;
DROP INDEX IF EXISTS ix_users_managed_by;
ALTER TABLE users DROP COLUMN IF EXISTS anonymized_at;
ALTER TABLE users DROP COLUMN IF EXISTS managed_by_id;
ALTER TABLE users DROP COLUMN IF EXISTS must_change_password;
COMMIT;
