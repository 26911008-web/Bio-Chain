-- Rollback migrasi 026 (autocommit; DROP INDEX CONCURRENTLY tidak boleh di dalam transaksi)
DROP INDEX CONCURRENTLY IF EXISTS ix_notifications_role_id;
DROP INDEX CONCURRENTLY IF EXISTS ix_notifications_user_id_id;
DROP INDEX CONCURRENTLY IF EXISTS ix_biochar_ledger_harvest_id;
DROP INDEX CONCURRENTLY IF EXISTS ix_custody_events_actor_id;
ALTER TABLE delivery_requests ALTER COLUMN biomass_type DROP DEFAULT;
ALTER TABLE stock_listings ALTER COLUMN transaction_mode DROP DEFAULT;
ALTER TABLE harvests ALTER COLUMN transaction_mode DROP DEFAULT;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'biochain_app') THEN
    ALTER ROLE biochain_app RESET statement_timeout;
    ALTER ROLE biochain_app RESET lock_timeout;
    ALTER ROLE biochain_app RESET idle_in_transaction_session_timeout;
  END IF;
EXCEPTION WHEN insufficient_privilege THEN
  RAISE NOTICE 'Lewati RESET peran (butuh CREATEROLE).';
END $$;
