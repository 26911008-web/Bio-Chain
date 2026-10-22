-- Rollback migrasi 002 (mass balance, custody, ledger biochar).
--
-- PERINGATAN: menghapus tabel custody_events, conversion_inputs, biochar_ledger beserta isinya
-- (jejak audit & saldo dompet petani). Ekspor dulu:
--   pg_dump "$DATABASE_URL_SYNC" -t custody_events -t conversion_inputs -t biochar_ledger > backup_002.sql
-- Rollback juga harus dibarengi deploy kode versi sebelum 002 (kode baru membutuhkan kolom ini).
-- Harvest berstatus 'converted' dikembalikan ke 'delivered' agar kode lama tetap mengenalinya.

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL biochain.allow_reset = 'on';

DROP TRIGGER IF EXISTS trg_ledger_append_only ON biochar_ledger;
DROP TRIGGER IF EXISTS trg_custody_append_only ON custody_events;
DROP FUNCTION IF EXISTS forbid_mutation();

DROP TABLE IF EXISTS biochar_ledger;
DROP TABLE IF EXISTS conversion_inputs;
DROP TABLE IF EXISTS custody_events;

ALTER TABLE harvests DROP CONSTRAINT IF EXISTS ck_harvest_received_weight;
ALTER TABLE harvests DROP CONSTRAINT IF EXISTS ck_harvest_status;
ALTER TABLE harvests DROP CONSTRAINT IF EXISTS ck_harvest_weights_nonneg;
UPDATE harvests SET status = 'delivered' WHERE status = 'converted';

DROP INDEX IF EXISTS ix_harvests_discrepancy_flag;
DROP INDEX IF EXISTS ix_harvests_conversion_id;
ALTER TABLE harvests
  DROP COLUMN IF EXISTS version,
  DROP COLUMN IF EXISTS conversion_id,
  DROP COLUMN IF EXISTS received_by_id,
  DROP COLUMN IF EXISTS rejected_at,
  DROP COLUMN IF EXISTS rejected_reason,
  DROP COLUMN IF EXISTS discrepancy_note,
  DROP COLUMN IF EXISTS discrepancy_flag,
  DROP COLUMN IF EXISTS shrinkage_pct,
  DROP COLUMN IF EXISTS shrinkage_kg,
  DROP COLUMN IF EXISTS received_kg,
  DROP COLUMN IF EXISTS picked_up_kg,
  DROP COLUMN IF EXISTS verified_kg;
ALTER TABLE conversions
  DROP COLUMN IF EXISTS allocated_biochar_kg,
  DROP COLUMN IF EXISTS farmer_return_share;

-- Akun auditor dinonaktifkan (bukan dihapus) karena kode lama tidak mengenal role ini.
UPDATE users SET is_active = FALSE WHERE role = 'auditor';
COMMIT;
