DROP TABLE IF EXISTS by_product_ledgers CASCADE;
DROP TABLE IF EXISTS production_blends CASCADE;
DROP TABLE IF EXISTS factory_invoices CASCADE;
DROP FUNCTION IF EXISTS fn_allocate_to_ramp_recursive CASCADE;
DROP TABLE IF EXISTS gate_receptions CASCADE;
DROP TABLE IF EXISTS loading_ramps CASCADE;

ALTER TABLE routes DROP COLUMN IF EXISTS logistics_carrier;
ALTER TABLE delivery_requests DROP COLUMN IF EXISTS logistics_carrier;
