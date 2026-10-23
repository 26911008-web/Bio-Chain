-- Rollback migrasi 024
BEGIN;
DROP FUNCTION IF EXISTS fn_verify_and_release_byproduct_circular_atomic;
DROP FUNCTION IF EXISTS fn_place_or_accept_bid_atomic;
ALTER TABLE by_product_ledgers DROP COLUMN IF EXISTS lab_cert_no;
ALTER TABLE by_product_ledgers DROP COLUMN IF EXISTS is_safety_passed;
ALTER TABLE by_product_ledgers DROP COLUMN IF EXISTS as_ppm;
ALTER TABLE by_product_ledgers DROP COLUMN IF EXISTS cd_ppm;
ALTER TABLE by_product_ledgers DROP COLUMN IF EXISTS pb_ppm;
ALTER TABLE biomass_parameters DROP COLUMN IF EXISTS as_ppm;
ALTER TABLE biomass_parameters DROP COLUMN IF EXISTS cd_ppm;
ALTER TABLE biomass_parameters DROP COLUMN IF EXISTS pb_ppm;
COMMIT;
