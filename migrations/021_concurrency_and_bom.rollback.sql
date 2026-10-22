-- Bio-Chain v2 · Rollback Migrasi 021: Atomic Bidding RPC, Multi-Output BOM & Chain of Custody
-- Target: PostgreSQL 16 / Supabase

BEGIN;
SET LOCAL lock_timeout = '5s';

DROP FUNCTION IF EXISTS fn_generate_trx_verification_code(INTEGER, INTEGER);
DROP FUNCTION IF EXISTS fn_place_bid_atomic(INTEGER, INTEGER, VARCHAR, DOUBLE PRECISION, DOUBLE PRECISION, VARCHAR, TEXT);
DROP TABLE IF EXISTS factory_conversions_bom CASCADE;

COMMIT;
