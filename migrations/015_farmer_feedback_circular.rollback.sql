-- Rollback 015 — PERINGATAN: riwayat pengambilan biochar & kategori tolak ikut hilang. Ledger redemption yang
-- sudah tertulis TIDAK dihapus (saldo petani tetap benar); ekspor dulu: pg_dump -t biochar_redemptions.
BEGIN;
DROP TABLE IF EXISTS efficiency_actions;
DROP TABLE IF EXISTS biochar_redemptions;
DROP INDEX IF EXISTS ix_harvests_farmer_rejected;
ALTER TABLE harvests DROP CONSTRAINT IF EXISTS ck_harvest_reject_category;
ALTER TABLE harvests DROP CONSTRAINT IF EXISTS ck_harvest_farmer_est;
ALTER TABLE harvests DROP COLUMN IF EXISTS reject_category;
ALTER TABLE harvests DROP COLUMN IF EXISTS farmer_grade_est;
ALTER TABLE harvests DROP COLUMN IF EXISTS farmer_moisture_est;
COMMIT;
