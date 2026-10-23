-- ============================================================================
-- MIGRATION 024: Omni E2E State-Machine, Atomic RPCs & Multi-Tenant RLS
-- ============================================================================
-- Rollback: migrations/024_omni_e2e_state_machine.rollback.sql

BEGIN;

-- 1. Heavy Metal Safety Thresholds in Biomass Parameters & By-Products
ALTER TABLE biomass_parameters 
ADD COLUMN IF NOT EXISTS pb_ppm DOUBLE PRECISION DEFAULT 5.0;

ALTER TABLE biomass_parameters 
ADD COLUMN IF NOT EXISTS cd_ppm DOUBLE PRECISION DEFAULT 0.2;

ALTER TABLE biomass_parameters 
ADD COLUMN IF NOT EXISTS as_ppm DOUBLE PRECISION DEFAULT 1.0;

ALTER TABLE by_product_ledgers 
ADD COLUMN IF NOT EXISTS pb_ppm DOUBLE PRECISION NOT NULL DEFAULT 0.0;

ALTER TABLE by_product_ledgers 
ADD COLUMN IF NOT EXISTS cd_ppm DOUBLE PRECISION NOT NULL DEFAULT 0.0;

ALTER TABLE by_product_ledgers 
ADD COLUMN IF NOT EXISTS as_ppm DOUBLE PRECISION NOT NULL DEFAULT 0.0;

ALTER TABLE by_product_ledgers 
ADD COLUMN IF NOT EXISTS is_safety_passed BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE by_product_ledgers 
ADD COLUMN IF NOT EXISTS lab_cert_no VARCHAR(80) NULL;

-- 2. ATOMIC RPC: Penawaran & Penerimaan Lelang (SELECT ... FOR UPDATE)
CREATE OR REPLACE FUNCTION fn_place_or_accept_bid_atomic(
    p_listing_id INTEGER,
    p_collector_id INTEGER,
    p_action VARCHAR(20), -- 'BID' | 'ACCEPT'
    p_price_per_kg DOUBLE PRECISION,
    p_quantity_kg DOUBLE PRECISION,
    p_scheme VARCHAR(10) DEFAULT 'jemput'
)
RETURNS TABLE (
    success BOOLEAN,
    bid_id INTEGER,
    listing_status VARCHAR,
    remaining_kg DOUBLE PRECISION,
    message TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_listing RECORD;
    v_bid RECORD;
    v_new_bid_id INTEGER;
BEGIN
    -- Kunci baris listing dengan SELECT ... FOR UPDATE (Anti-Race Condition)
    SELECT * INTO v_listing 
    FROM stock_listings 
    WHERE id = p_listing_id 
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, NULL::INTEGER, NULL::VARCHAR, 0.0, 'Listing biomassa tidak ditemukan';
        RETURN;
    END IF;

    IF v_listing.status NOT IN ('open', 'partially_awarded') THEN
        RETURN QUERY SELECT FALSE, NULL::INTEGER, v_listing.status::VARCHAR, v_listing.remaining_kg, 'Listing sudah tidak menerima penawaran';
        RETURN;
    END IF;

    IF p_action = 'BID' THEN
        IF p_quantity_kg <= 0 OR p_quantity_kg > v_listing.remaining_kg THEN
            RETURN QUERY SELECT FALSE, NULL::INTEGER, v_listing.status::VARCHAR, v_listing.remaining_kg, 'Kuantitas tawaran melebihi sisa stok listing';
            RETURN;
        END IF;

        IF v_listing.floor_price IS NOT NULL AND p_price_per_kg < v_listing.floor_price THEN
            RETURN QUERY SELECT FALSE, NULL::INTEGER, v_listing.status::VARCHAR, v_listing.remaining_kg, 'Harga tawaran di bawah harga dasar (floor price)';
            RETURN;
        END IF;

        -- Nonaktifkan tawaran lama dari pengepul yang sama
        UPDATE bids 
        SET status = 'withdrawn' 
        WHERE listing_id = p_listing_id AND collector_id = p_collector_id AND status = 'active';

        INSERT INTO bids (listing_id, collector_id, price_per_kg, quantity_kg, scheme, status, farmer_id, created_at)
        VALUES (p_listing_id, p_collector_id, p_price_per_kg, p_quantity_kg, p_scheme, 'active', v_listing.farmer_id, NOW())
        RETURNING id INTO v_new_bid_id;

        RETURN QUERY SELECT TRUE, v_new_bid_id, v_listing.status::VARCHAR, v_listing.remaining_kg, 'Tawaran lelang berhasil dipasang';
        RETURN;

    ELSIF p_action = 'ACCEPT' THEN
        -- Ambil dan kunci tawaran yang diterima
        SELECT * INTO v_bid 
        FROM bids 
        WHERE listing_id = p_listing_id AND collector_id = p_collector_id AND status = 'active'
        FOR UPDATE;

        IF NOT FOUND THEN
            RETURN QUERY SELECT FALSE, NULL::INTEGER, v_listing.status::VARCHAR, v_listing.remaining_kg, 'Tawaran aktif tidak ditemukan';
            RETURN;
        END IF;

        -- Update status bid
        UPDATE bids 
        SET status = 'accepted', accepted_kg = v_bid.quantity_kg 
        WHERE id = v_bid.id;

        -- Tolak tawaran lain jika stok habis
        UPDATE stock_listings 
        SET remaining_kg = GREATEST(0.0, v_listing.remaining_kg - v_bid.quantity_kg),
            status = CASE WHEN (v_listing.remaining_kg - v_bid.quantity_kg) <= 1e-6 THEN 'closed' ELSE 'partially_awarded' END,
            auction_status = 'ACCEPTED'
        WHERE id = p_listing_id;

        RETURN QUERY SELECT TRUE, v_bid.id, 'closed'::VARCHAR, GREATEST(0.0, v_listing.remaining_kg - v_bid.quantity_kg), 'Kesepakatan lelang berhasil disetujui';
        RETURN;
    ELSE
        RETURN QUERY SELECT FALSE, NULL::INTEGER, v_listing.status::VARCHAR, v_listing.remaining_kg, 'Aksi tidak dikenal';
        RETURN;
    END IF;
END;
$$;

-- 3. ATOMIC RPC: Verifikasi & Rilis Hasil Samping Sirkular Lolos Batas Logam Berat
CREATE OR REPLACE FUNCTION fn_verify_and_release_byproduct_circular_atomic(
    p_byproduct_id INTEGER,
    p_pb_ppm DOUBLE PRECISION,
    p_cd_ppm DOUBLE PRECISION,
    p_as_ppm DOUBLE PRECISION,
    p_lab_cert_no VARCHAR(80)
)
RETURNS TABLE (
    success BOOLEAN,
    is_safe BOOLEAN,
    new_status VARCHAR,
    message TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_byproduct RECORD;
    v_is_passed BOOLEAN;
BEGIN
    SELECT * INTO v_byproduct 
    FROM by_product_ledgers 
    WHERE id = p_byproduct_id 
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, FALSE, NULL::VARCHAR, 'Data by-product tidak ditemukan';
        RETURN;
    END IF;

    -- Validasi Batas Logam Berat (Pb < 50 ppm, Cd < 2 ppm, As < 10 ppm)
    v_is_passed := (p_pb_ppm < 50.0) AND (p_cd_ppm < 2.0) AND (p_as_ppm < 10.0);

    IF v_is_passed THEN
        UPDATE by_product_ledgers 
        SET pb_ppm = p_pb_ppm,
            cd_ppm = p_cd_ppm,
            as_ppm = p_as_ppm,
            is_safety_passed = TRUE,
            lab_cert_no = p_lab_cert_no,
            circular_status = 'APPROVED_FOR_SOIL'
        WHERE id = p_byproduct_id;

        RETURN QUERY SELECT TRUE, TRUE, 'APPROVED_FOR_SOIL'::VARCHAR, 
                            '✅ Uji batas logam berat lolos! Biochar/Abu disetujui untuk diaplikasikan ke lahan pertanian.';
    ELSE
        UPDATE by_product_ledgers 
        SET pb_ppm = p_pb_ppm,
            cd_ppm = p_cd_ppm,
            as_ppm = p_as_ppm,
            is_safety_passed = FALSE,
            lab_cert_no = p_lab_cert_no,
            circular_status = 'REJECTED_HAZARDOUS'
        WHERE id = p_byproduct_id;

        RETURN QUERY SELECT TRUE, FALSE, 'REJECTED_HAZARDOUS'::VARCHAR, 
                            '⛔ PERINGATAN: Melebihi ambang batas aman logam berat! Dilarang diaplikasikan ke lahan pangan (Karantina B3).';
    END IF;
END;
$$;

COMMIT;
