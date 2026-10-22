-- Rollback migrasi 010 — hanya view, fungsi & indeks pelaporan; tidak ada data yang hilang.
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP VIEW IF EXISTS wh_monthly_wallet, wh_monthly_cost, wh_monthly_conversion, wh_monthly_supply;
DROP FUNCTION IF EXISTS wib_month(timestamptz);
DROP INDEX IF EXISTS ix_inbound_qc_created, ix_batches_created, ix_ledger_created,
                     ix_harvests_verified_at, ix_harvests_delivered_at;
COMMIT;
