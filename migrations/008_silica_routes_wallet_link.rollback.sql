-- Rollback migrasi 008. Entri dompet dari batch TIDAK dihapus (jejak keuangan petani); kolom batch_id dilepas
-- setelah diekspor: pg_dump "$DATABASE_URL_SYNC" -t biochar_ledger > backup_008_ledger.sql
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL biochain.allow_reset = 'on';
ALTER TABLE biochar_ledger DROP CONSTRAINT IF EXISTS uq_ledger_batch_alloc_once;
DROP INDEX IF EXISTS ix_biochar_ledger_batch_id;
ALTER TABLE biochar_ledger DROP COLUMN IF EXISTS batch_id;
DROP INDEX IF EXISTS ix_harvests_delivery_request_id;
ALTER TABLE harvests DROP COLUMN IF EXISTS delivery_request_id;
ALTER TABLE batch_losses DROP CONSTRAINT IF EXISTS ck_batch_losses_kind;
DELETE FROM batch_losses WHERE kind = 'gas_pembakaran';
ALTER TABLE batch_losses ADD CONSTRAINT batch_losses_kind_check
  CHECK (kind IN ('air','volatil_syngas','residu_ekstraksi','susut_proses'));
ALTER TABLE manufacturing_batches DROP CONSTRAINT IF EXISTS ck_batch_silica_route;
ALTER TABLE manufacturing_batches DROP COLUMN IF EXISTS silica_husk_share, DROP COLUMN IF EXISTS silica_route;
COMMIT;
