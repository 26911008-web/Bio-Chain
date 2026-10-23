-- Rollback migrasi 025. loading_ramps / production_blends / by_product_ledgers dibuat oleh 023
-- (025 hanya CREATE ... IF NOT EXISTS) sehingga tidak dihapus di sini — gunakan rollback 023 untuk itu.
BEGIN;
DROP FUNCTION IF EXISTS rpc_verify_byproduct_heavy_metals_atomic;
DROP FUNCTION IF EXISTS rpc_allocate_loading_ramp_atomic;
DROP FUNCTION IF EXISTS rpc_respond_pickup_schedule_atomic;
DROP FUNCTION IF EXISTS rpc_place_and_accept_auction_atomic;
DROP INDEX IF EXISTS idx_byproducts_safety;
DROP INDEX IF EXISTS idx_ramps_mill_type;
DROP TABLE IF EXISTS biochar_circular_requests CASCADE;
DROP TABLE IF EXISTS feedstock_parameters CASCADE;
COMMIT;
