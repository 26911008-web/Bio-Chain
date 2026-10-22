-- Rollback 018 — multi-biomassa, gudang pengepul, ledger abu. Data transaksi lama (sekam) tidak tersentuh.
BEGIN;
DROP VIEW IF EXISTS warehouse_stock;
DROP TABLE IF EXISTS industrial_ash_ledgers;
DROP TABLE IF EXISTS farmer_groups;
DROP TABLE IF EXISTS warehouse_stock_movements;
DROP TABLE IF EXISTS collector_warehouses;
ALTER TABLE harvests DROP CONSTRAINT IF EXISTS fk_harvest_commodity;
ALTER TABLE stock_listings DROP CONSTRAINT IF EXISTS fk_listing_commodity;
DROP INDEX IF EXISTS ix_harvests_commodity_status;
DROP INDEX IF EXISTS ix_listings_commodity_status;
ALTER TABLE harvests DROP COLUMN IF EXISTS commodity;
ALTER TABLE stock_listings DROP COLUMN IF EXISTS commodity;
DROP TABLE IF EXISTS biomass_parameters;
COMMIT;
