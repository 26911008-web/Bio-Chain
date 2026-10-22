-- Bio-Chain v2 · Migrasi 022: Multi-Mode Bidding, Reverse Logistics Biochar, Chain of Custody & Payment Reputation
-- Target: PostgreSQL 16 / Supabase
-- Rollback: migrations/022_omni_multi_mode_and_reverse_logistics.rollback.sql

BEGIN;
SET LOCAL lock_timeout = '5s';

-- 1. EXTEND STOCK_LISTINGS FOR MULTI-MODE TRANSACTIONS & DEVIATION
ALTER TABLE stock_listings 
    ADD COLUMN IF NOT EXISTS transaction_mode VARCHAR(16) NOT NULL DEFAULT 'DIRECT',
    ADD COLUMN IF NOT EXISTS auction_status VARCHAR(16) NOT NULL DEFAULT 'OPEN',
    ADD COLUMN IF NOT EXISTS auction_expiry TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS floor_price DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS logistics_mode VARCHAR(16) NOT NULL DEFAULT 'PICKUP',
    ADD COLUMN IF NOT EXISTS payment_status VARCHAR(16) NOT NULL DEFAULT 'UNPAID',
    ADD COLUMN IF NOT EXISTS farmer_claimed_qty DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS actual_weighed_qty DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS deviation_kg DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS deviation_pct DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS qc_status VARCHAR(16) DEFAULT 'PENDING',
    ADD COLUMN IF NOT EXISTS qc_rejection_reason TEXT;

-- 2. EXTEND HARVESTS FOR CHAIN OF CUSTODY & WEIGHBRIDGE EVIDENCE
ALTER TABLE harvests
    ADD COLUMN IF NOT EXISTS transaction_mode VARCHAR(16) NOT NULL DEFAULT 'DIRECT',
    ADD COLUMN IF NOT EXISTS logistics_mode VARCHAR(16) NOT NULL DEFAULT 'PICKUP',
    ADD COLUMN IF NOT EXISTS payment_status VARCHAR(16) NOT NULL DEFAULT 'UNPAID',
    ADD COLUMN IF NOT EXISTS farmer_claimed_qty DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS actual_weighed_qty DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS deviation_kg DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS deviation_pct DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS qc_status VARCHAR(16) DEFAULT 'PENDING',
    ADD COLUMN IF NOT EXISTS qc_rejection_reason TEXT,
    ADD COLUMN IF NOT EXISTS qr_verification_token VARCHAR(64),
    ADD COLUMN IF NOT EXISTS gross_weight DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS tare_weight DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS net_weight DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS weighbridge_slip_url TEXT,
    ADD COLUMN IF NOT EXISTS biochar_backhaul_requested BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS biochar_backhaul_kg DOUBLE PRECISION DEFAULT 0;

CREATE UNIQUE INDEX IF NOT EXISTS uq_harvests_qr_token ON harvests (qr_verification_token) WHERE qr_verification_token IS NOT NULL;

-- 3. EXTEND BIDS FOR LOGISTICS & SCHEDULE CONFIRMATION
ALTER TABLE bids
    ADD COLUMN IF NOT EXISTS logistics_mode VARCHAR(16) DEFAULT 'PICKUP',
    ADD COLUMN IF NOT EXISTS payment_term VARCHAR(16) DEFAULT 'COD',
    ADD COLUMN IF NOT EXISTS pickup_schedule_proposed TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS farmer_schedule_status VARCHAR(16) DEFAULT 'PENDING',
    ADD COLUMN IF NOT EXISTS farmer_schedule_note TEXT;

-- 4. TABEL BIOCHAR REQUESTS (PERMINTAAN BIOCHAR SAWAH / REVERSE LOGISTICS)
CREATE TABLE IF NOT EXISTS biochar_requests (
    id                          SERIAL PRIMARY KEY,
    request_code                VARCHAR(36) UNIQUE NOT NULL,
    farmer_id                   INTEGER NOT NULL REFERENCES users(id),
    collector_id                INTEGER NOT NULL REFERENCES users(id),
    harvest_id                  INTEGER REFERENCES harvests(id),
    route_id                    INTEGER REFERENCES routes(id),
    requested_kg                DOUBLE PRECISION NOT NULL CHECK (requested_kg > 0),
    allocated_kg                DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (allocated_kg >= 0),
    status                      VARCHAR(20) NOT NULL DEFAULT 'REQUESTED' 
                                CHECK (status IN ('REQUESTED', 'ALLOCATED', 'LOADED_BACKHAUL', 'DELIVERED', 'CANCELLED')),
    delivery_point              VARCHAR(150),
    partition_safeguard_verified BOOLEAN NOT NULL DEFAULT TRUE,
    notes                       TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at                TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_biochar_requests_farmer_id ON biochar_requests (farmer_id);
CREATE INDEX IF NOT EXISTS ix_biochar_requests_collector_id ON biochar_requests (collector_id);
CREATE INDEX IF NOT EXISTS ix_biochar_requests_status ON biochar_requests (status);

-- 5. TABEL BIOCHAR DISTRIBUTIONS (MUATAN BALIK DARI PABRIK KE PENGEPUL/DRIVER)
CREATE TABLE IF NOT EXISTS biochar_distributions (
    id                          SERIAL PRIMARY KEY,
    dispatch_code               VARCHAR(36) UNIQUE NOT NULL,
    factory_id                  INTEGER NOT NULL REFERENCES users(id),
    collector_id                INTEGER NOT NULL REFERENCES users(id),
    driver_id                   INTEGER REFERENCES users(id),
    route_id                    INTEGER REFERENCES routes(id),
    vehicle_plate               VARCHAR(20),
    total_bags                  INTEGER DEFAULT 0,
    total_weight_kg             DOUBLE PRECISION NOT NULL CHECK (total_weight_kg > 0),
    volume_m3                   DOUBLE PRECISION NOT NULL CHECK (volume_m3 > 0),
    loading_instructions        TEXT,
    qr_dispatch_token           VARCHAR(64) UNIQUE NOT NULL,
    status                      VARCHAR(25) NOT NULL DEFAULT 'DISPATCHED'
                                CHECK (status IN ('DISPATCHED', 'RECEIVED_BY_COLLECTOR', 'DELIVERED_TO_FARMER')),
    weighed_by_driver_kg        DOUBLE PRECISION,
    slip_url                    TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at                TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_biochar_dist_factory_id ON biochar_distributions (factory_id);
CREATE INDEX IF NOT EXISTS ix_biochar_dist_collector_id ON biochar_distributions (collector_id);
CREATE INDEX IF NOT EXISTS ix_biochar_dist_driver_id ON biochar_distributions (driver_id);

-- 6. TABEL REPUTASI PEMBAYARAN PENGEPUL (COLLECTOR PAYMENT REPUTATION SCORECARD)
CREATE TABLE IF NOT EXISTS collector_payment_reputations (
    collector_id                INTEGER PRIMARY KEY REFERENCES users(id),
    total_transactions          INTEGER NOT NULL DEFAULT 0,
    on_time_dp_count            INTEGER NOT NULL DEFAULT 0,
    on_time_settlement_count    INTEGER NOT NULL DEFAULT 0,
    avg_dp_delay_hours          DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_settlement_delay_days   DOUBLE PRECISION NOT NULL DEFAULT 0,
    punctuality_score           DOUBLE PRECISION NOT NULL DEFAULT 100.0 CHECK (punctuality_score BETWEEN 0 AND 100),
    outstanding_debt_rp         NUMERIC(16, 2) NOT NULL DEFAULT 0,
    settled_amount_rp           NUMERIC(16, 2) NOT NULL DEFAULT 0,
    rating_tier                 VARCHAR(16) NOT NULL DEFAULT 'EXCELLENT' CHECK (rating_tier IN ('EXCELLENT', 'GOOD', 'FAIR', 'POOR')),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 7. ATOMIC BID ACCEPTANCE RPC WITH ROW LOCK (POSTGRESQL / SUPABASE)
CREATE OR REPLACE FUNCTION fn_accept_bid_atomic(
    p_listing_id       INTEGER,
    p_bid_id           INTEGER,
    p_quantity_kg      DOUBLE PRECISION,
    p_logistics_mode   VARCHAR DEFAULT 'PICKUP'
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_listing          RECORD;
    v_bid              RECORD;
    v_new_harvest_id   INTEGER;
    v_verification_code TEXT;
    v_qr_token         TEXT;
    v_now              TIMESTAMPTZ := now();
BEGIN
    -- 1. Kunci Listing
    SELECT * INTO v_listing
    FROM stock_listings
    WHERE id = p_listing_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Listing #% tidak ditemukan', p_listing_id USING ERRCODE = 'P0002';
    END IF;

    IF v_listing.status NOT IN ('open', 'partially_awarded') THEN
        RAISE EXCEPTION 'Listing #% berstatus %, tidak dapat menerima tawaran', p_listing_id, v_listing.status USING ERRCODE = '22000';
    END IF;

    -- 2. Kunci Bid
    SELECT * INTO v_bid
    FROM bids
    WHERE id = p_bid_id AND listing_id = p_listing_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Tawaran #% tidak ditemukan pada listing #%', p_bid_id, p_listing_id USING ERRCODE = 'P0002';
    END IF;

    IF v_bid.status != 'active' THEN
        RAISE EXCEPTION 'Tawaran #% sudah tidak aktif (status: %)', p_bid_id, v_bid.status USING ERRCODE = '22000';
    END IF;

    IF p_quantity_kg > v_listing.remaining_kg + 1e-6 THEN
        RAISE EXCEPTION 'Kuantitas (% kg) melebihi sisa stok (% kg)', p_quantity_kg, v_listing.remaining_kg USING ERRCODE = '22000';
    END IF;

    -- 3. Update Listing & Bid
    UPDATE stock_listings
    SET remaining_kg = remaining_kg - p_quantity_kg,
        status = CASE WHEN remaining_kg - p_quantity_kg <= 1e-6 THEN 'closed' ELSE 'partially_awarded' END,
        version = version + 1
    WHERE id = p_listing_id;

    UPDATE bids
    SET accepted_kg = accepted_kg + p_quantity_kg,
        status = 'accepted',
        decided_at = v_now
    WHERE id = p_bid_id;

    -- 4. Generate Tokens
    v_verification_code := fn_generate_trx_verification_code(v_listing.farmer_id, v_bid.collector_id);
    v_qr_token := 'BIO-TX-' || substr(md5(random()::text || clock_timestamp()::text), 1, 16);

    -- 5. Buat Harvest Record Resmi yang terhubung
    INSERT INTO harvests (
        farmer_id, collector_id, mill_id, quantity_kg, farmer_claimed_qty,
        commodity, status, qr_code, qr_verification_token, transaction_mode,
        logistics_mode, payment_status, agreed_price_per_kg, listing_id,
        bid_id, delivery_scheme, reported_at, created_at
    )
    VALUES (
        v_listing.farmer_id, v_bid.collector_id, v_listing.mill_id, p_quantity_kg, p_quantity_kg,
        v_listing.commodity, 'verified', v_verification_code, v_qr_token, 'BIDDING',
        p_logistics_mode, 'UNPAID', v_bid.price_per_kg, p_listing_id,
        p_bid_id, v_bid.scheme, v_now, v_now
    )
    RETURNING id INTO v_new_harvest_id;

    RETURN jsonb_build_object(
        'success', TRUE,
        'harvest_id', v_new_harvest_id,
        'listing_id', p_listing_id,
        'bid_id', p_bid_id,
        'accepted_kg', p_quantity_kg,
        'remaining_stock_kg', GREATEST(0.0, v_listing.remaining_kg - p_quantity_kg),
        'verification_code', v_verification_code,
        'qr_token', v_qr_token,
        'price_per_kg', v_bid.price_per_kg,
        'contract_value_rp', round((p_quantity_kg * v_bid.price_per_kg)::numeric, 0),
        'timestamp', v_now
    );
END;
$$;

-- 8. ATOMIC REVERSE LOGISTICS BACKHAUL ALLOCATION RPC
CREATE OR REPLACE FUNCTION fn_allocate_backhaul_biochar(
    p_route_id         INTEGER,
    p_request_id       INTEGER,
    p_allocated_kg     DOUBLE PRECISION
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_route            RECORD;
    v_req              RECORD;
    v_density_biochar  DOUBLE PRECISION := 350.0; -- kg/m3 curah biochar
    v_added_vol_m3     DOUBLE PRECISION;
    v_max_vol_m3       DOUBLE PRECISION := 30.0;  -- volume bak truk standar
    v_now              TIMESTAMPTZ := now();
BEGIN
    SELECT * INTO v_route FROM routes WHERE id = p_route_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Rute armada #% tidak ditemukan', p_route_id USING ERRCODE = 'P0002';
    END IF;

    SELECT * INTO v_req FROM biochar_requests WHERE id = p_request_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Permintaan biochar #% tidak ditemukan', p_request_id USING ERRCODE = 'P0002';
    END IF;

    v_added_vol_m3 := p_allocated_kg / v_density_biochar;

    -- Update Alokasi
    UPDATE biochar_requests
    SET allocated_kg = p_allocated_kg,
        route_id = p_route_id,
        status = 'ALLOCATED',
        updated_at = v_now
    WHERE id = p_request_id;

    RETURN jsonb_build_object(
        'success', TRUE,
        'route_id', p_route_id,
        'request_id', p_request_id,
        'allocated_kg', p_allocated_kg,
        'volume_m3', round(v_added_vol_m3::numeric, 2),
        'status', 'ALLOCATED',
        'timestamp', v_now
    );
END;
$$;

COMMIT;
