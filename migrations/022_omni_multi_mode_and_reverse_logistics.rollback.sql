-- Bio-Chain v2 · Rollback Migrasi 022
BEGIN;
DROP FUNCTION IF EXISTS fn_allocate_backhaul_biochar(INTEGER, INTEGER, DOUBLE PRECISION);
DROP FUNCTION IF EXISTS fn_accept_bid_atomic(INTEGER, INTEGER, DOUBLE PRECISION, VARCHAR);
DROP TABLE IF EXISTS collector_payment_reputations CASCADE;
DROP TABLE IF EXISTS biochar_distributions CASCADE;
DROP TABLE IF EXISTS biochar_requests CASCADE;

ALTER TABLE bids
    DROP COLUMN IF EXISTS farmer_schedule_note,
    DROP COLUMN IF EXISTS farmer_schedule_status,
    DROP COLUMN IF EXISTS pickup_schedule_proposed,
    DROP COLUMN IF EXISTS payment_term,
    DROP COLUMN IF EXISTS logistics_mode;

ALTER TABLE harvests
    DROP COLUMN IF EXISTS biochar_backhaul_kg,
    DROP COLUMN IF EXISTS biochar_backhaul_requested,
    DROP COLUMN IF EXISTS weighbridge_slip_url,
    DROP COLUMN IF EXISTS net_weight,
    DROP COLUMN IF EXISTS tare_weight,
    DROP COLUMN IF EXISTS gross_weight,
    DROP COLUMN IF EXISTS qr_verification_token,
    DROP COLUMN IF EXISTS qc_rejection_reason,
    DROP COLUMN IF EXISTS qc_status,
    DROP COLUMN IF EXISTS deviation_pct,
    DROP COLUMN IF EXISTS deviation_kg,
    DROP COLUMN IF EXISTS actual_weighed_qty,
    DROP COLUMN IF EXISTS farmer_claimed_qty,
    DROP COLUMN IF EXISTS payment_status,
    DROP COLUMN IF EXISTS logistics_mode,
    DROP COLUMN IF EXISTS transaction_mode;

ALTER TABLE stock_listings
    DROP COLUMN IF EXISTS qc_rejection_reason,
    DROP COLUMN IF EXISTS qc_status,
    DROP COLUMN IF EXISTS deviation_pct,
    DROP COLUMN IF EXISTS deviation_kg,
    DROP COLUMN IF EXISTS actual_weighed_qty,
    DROP COLUMN IF EXISTS farmer_claimed_qty,
    DROP COLUMN IF EXISTS payment_status,
    DROP COLUMN IF EXISTS logistics_mode,
    DROP COLUMN IF EXISTS floor_price,
    DROP COLUMN IF EXISTS auction_expiry,
    DROP COLUMN IF EXISTS auction_status,
    DROP COLUMN IF EXISTS transaction_mode;

COMMIT;
