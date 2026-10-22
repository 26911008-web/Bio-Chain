-- Rollback migrasi 007. PERINGATAN: menghapus data procurement, QC, batch & biaya. Ekspor dulu:
--   pg_dump "$DATABASE_URL_SYNC" -t 'delivery_requests' -t 'negotiation_events' -t 'inbound_qc' \
--           -t 'manufacturing_batches' -t 'batch_*' > backup_007.sql
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL biochain.allow_reset = 'on';
DROP TABLE IF EXISTS batch_costs, batch_losses, batch_outputs, batch_inputs, manufacturing_batches;
DROP TABLE IF EXISTS inbound_qc;
DROP TRIGGER IF EXISTS trg_negotiation_append_only ON negotiation_events;
DROP TABLE IF EXISTS negotiation_events, delivery_requests;
COMMIT;
