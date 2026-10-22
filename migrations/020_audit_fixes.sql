-- Migrasi 020 — perbaikan hasil audit pasca-protokol multi-biomassa.
--   * satu lot pembelian hanya boleh dibukukan masuk gudang sekali (indeks unik parsial)
-- Idempoten & aman diulang. Rollback: 020_audit_fixes.rollback.sql
BEGIN;
SET LOCAL lock_timeout = '5s';
CREATE UNIQUE INDEX IF NOT EXISTS uq_wsm_harvest_in ON warehouse_stock_movements (harvest_id)
  WHERE movement = 'masuk' AND harvest_id IS NOT NULL;
COMMIT;
