-- ============================================================================
-- MIGRATION 025: Bio-Chain V-Omega Unified State-Machine & Atomic RPCs
-- Target Engine: PostgreSQL 15+ / Supabase
-- Rollback: migrations/025_omni_v_omega_state_machine.rollback.sql
-- ============================================================================

BEGIN;
SET LOCAL lock_timeout = '5s';

-- ----------------------------------------------------------------------------
-- 1. TABEL MASTER PARAMETER KARAKTERISTIK BIOMASSA & LOGAM BERAT
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedstock_parameters (
    code VARCHAR(30) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    moisture_typical_pct DOUBLE PRECISION NOT NULL,
    ash_typical_pct DOUBLE PRECISION NOT NULL,
    lhv_typical_kcal_kg DOUBLE PRECISION NOT NULL,
    bulk_density_kg_m3 DOUBLE PRECISION NOT NULL DEFAULT 150.0,
    sio2_pct_ash DOUBLE PRECISION DEFAULT 0.0,
    k2o_pct_ash DOUBLE PRECISION DEFAULT 0.0,
    -- Ambang Batas Logam Berat Keamanan Lahan (EBC / Kementan RI)
    pb_max_ppm DOUBLE PRECISION NOT NULL DEFAULT 50.0, -- Timbal (Maks 50 ppm)
    cd_max_ppm DOUBLE PRECISION NOT NULL DEFAULT 2.0,  -- Kadmium (Maks 2 ppm)
    as_max_ppm DOUBLE PRECISION NOT NULL DEFAULT 10.0, -- Arsenik (Maks 10 ppm)
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed parameter biomassa standar jika belum ada
INSERT INTO feedstock_parameters (code, name, moisture_typical_pct, ash_typical_pct, lhv_typical_kcal_kg, bulk_density_kg_m3, sio2_pct_ash, k2o_pct_ash)
VALUES 
    ('sekam_padi', 'Sekam Padi Mentah', 13.5, 17.5, 3450.0, 110.0, 92.0, 2.1),
    ('tongkol_jagung', 'Tongkol Jagung Cacah', 14.0, 2.8, 4100.0, 180.0, 35.0, 15.0),
    ('serbuk_sengon', 'Serbuk Gergaji Kayu Sengon', 28.0, 1.5, 3800.0, 220.0, 12.0, 8.5),
    ('tempurung_kelapa', 'Tempurung Kelapa Pecah', 10.5, 2.2, 4600.0, 350.0, 18.0, 12.0)
ON CONFLICT (code) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 2. TABEL PERMINTAAN BIOCHAR SIRKULAR (HULU ↔ HILIR REVERSE LOGISTICS)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS biochar_circular_requests (
    id SERIAL PRIMARY KEY,
    request_code VARCHAR(40) UNIQUE NOT NULL,
    farmer_id INTEGER NOT NULL REFERENCES users(id),
    collector_id INTEGER NOT NULL REFERENCES users(id),
    listing_id INTEGER REFERENCES stock_listings(id) ON DELETE SET NULL,
    harvest_id INTEGER REFERENCES harvests(id) ON DELETE SET NULL,
    route_id INTEGER REFERENCES routes(id) ON DELETE SET NULL,
    requested_kg DOUBLE PRECISION NOT NULL CHECK (requested_kg > 0),
    allocated_kg DOUBLE PRECISION NOT NULL DEFAULT 0.0 CHECK (allocated_kg >= 0),
    land_area_ha DOUBLE PRECISION NULL CHECK (land_area_ha IS NULL OR land_area_ha > 0),
    delivery_point VARCHAR(200) NOT NULL DEFAULT 'Lahan Petani',
    status VARCHAR(30) NOT NULL DEFAULT 'REQUESTED'
        CHECK (status IN ('REQUESTED', 'APPROVED_BY_COLLECTOR', 'LOADED_BACKHAUL', 'DELIVERED', 'CANCELLED')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_biochar_circ_farmer ON biochar_circular_requests(farmer_id, status);
CREATE INDEX IF NOT EXISTS idx_biochar_circ_collector ON biochar_circular_requests(collector_id, status);

-- ----------------------------------------------------------------------------
-- 3. TABEL DINAMIS LOADING RAMP PABRIK
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS loading_ramps (
    id SERIAL PRIMARY KEY,
    ramp_code VARCHAR(25) UNIQUE NOT NULL,
    name VARCHAR(120) NOT NULL,
    mill_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    biomass_type VARCHAR(50) NOT NULL,
    max_capacity_kg DOUBLE PRECISION NOT NULL DEFAULT 60000.0 CHECK (max_capacity_kg > 0),
    current_stock_kg DOUBLE PRECISION NOT NULL DEFAULT 0.0 CHECK (current_stock_kg >= 0),
    aggregate_mc DOUBLE PRECISION NOT NULL DEFAULT 12.0,
    aggregate_ash DOUBLE PRECISION NOT NULL DEFAULT 10.0,
    aggregate_lhv_kcal DOUBLE PRECISION NOT NULL DEFAULT 3500.0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ramps_mill_type ON loading_ramps(mill_id, biomass_type, is_active);

-- Seed Ramp Awal Jika Kosong
INSERT INTO loading_ramps (ramp_code, name, biomass_type, max_capacity_kg, current_stock_kg, aggregate_mc, aggregate_ash, aggregate_lhv_kcal)
VALUES 
    ('RAMP-01', 'Ramp Utama Sekam Padi', 'sekam_padi', 60000.0, 15000.0, 13.5, 17.0, 3450.0),
    ('RAMP-02', 'Ramp Tongkol Jagung Cacah', 'tongkol_jagung', 45000.0, 8000.0, 14.0, 2.5, 4100.0),
    ('RAMP-03', 'Ramp Serbuk Kayu Sengon', 'serbuk_sengon', 40000.0, 5000.0, 28.0, 1.5, 3800.0),
    ('RAMP-04', 'Ramp Cangkang & Tempurung Kelapa', 'tempurung_kelapa', 50000.0, 12000.0, 10.5, 2.0, 4600.0)
ON CONFLICT (ramp_code) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 4. TABEL BATCH PRODUKSI BLENDING MULTI-RAMP & BY-PRODUCTS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS production_blends (
    id SERIAL PRIMARY KEY,
    blend_code VARCHAR(50) UNIQUE NOT NULL,
    mill_id INTEGER NOT NULL REFERENCES users(id),
    target_product VARCHAR(30) NOT NULL 
        CHECK (target_product IN ('BIOPELLET', 'BIOCHAR', 'BIO_SILICA', 'BRIQUETTE')),
    ramp_allocations JSONB NOT NULL,
    total_input_kg DOUBLE PRECISION NOT NULL CHECK (total_input_kg > 0),
    final_mc_pct DOUBLE PRECISION NOT NULL,
    final_ash_pct DOUBLE PRECISION NOT NULL,
    final_lhv_kcal DOUBLE PRECISION NOT NULL,
    alkali_index DOUBLE PRECISION NOT NULL DEFAULT 0.20,
    base_to_acid_ratio DOUBLE PRECISION NOT NULL DEFAULT 0.15,
    cost_per_kg DOUBLE PRECISION NOT NULL,
    target_selling_price_per_kg DOUBLE PRECISION NOT NULL,
    estimated_margin_rp DOUBLE PRECISION NOT NULL,
    net_tco2e DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS by_product_ledgers (
    id SERIAL PRIMARY KEY,
    blend_id INTEGER REFERENCES production_blends(id) ON DELETE SET NULL,
    mill_id INTEGER NOT NULL REFERENCES users(id),
    by_product_type VARCHAR(40) NOT NULL 
        CHECK (by_product_type IN ('WOOD_VINEGAR', 'SILICA_ASH', 'BOTTOM_ASH', 'BIOCHAR_COARSE')),
    quantity_kg DOUBLE PRECISION NOT NULL CHECK (quantity_kg >= 0),
    circular_status VARCHAR(35) NOT NULL DEFAULT 'STORED'
        CHECK (circular_status IN ('STORED', 'APPROVED_FOR_SOIL', 'DISPATCHED_TO_COLLECTOR', 'DELIVERED_TO_FARMER', 'REJECTED_HAZARDOUS')),
    pb_ppm DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    cd_ppm DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    as_ppm DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    is_safety_passed BOOLEAN NOT NULL DEFAULT FALSE,
    lab_cert_no VARCHAR(100),
    recipient_farmer_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_byproducts_safety ON by_product_ledgers(mill_id, circular_status, is_safety_passed);

-- ----------------------------------------------------------------------------
-- 5. ATOMIC RPC 1: BIDDING & KESEPAKATAN LELANG ATOMIK (PESSIMISTIC LOCKING)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION rpc_place_and_accept_auction_atomic(
    p_listing_id INTEGER,
    p_collector_id INTEGER,
    p_action VARCHAR(20), -- 'PLACE_BID' | 'ACCEPT_BID'
    p_bid_id INTEGER DEFAULT NULL,
    p_offered_price DOUBLE PRECISION DEFAULT 0.0,
    p_offered_qty DOUBLE PRECISION DEFAULT 0.0,
    p_scheme VARCHAR(10) DEFAULT 'jemput',
    p_logistics_mode VARCHAR(20) DEFAULT 'PICKUP'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_listing RECORD;
    v_bid RECORD;
    v_new_bid_id INTEGER;
    v_rem_qty DOUBLE PRECISION;
BEGIN
    SELECT * INTO v_listing 
    FROM stock_listings 
    WHERE id = p_listing_id 
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'message', 'Listing biomassa tidak ditemukan.');
    END IF;

    IF v_listing.status NOT IN ('open', 'partially_awarded') THEN
        RETURN jsonb_build_object('success', false, 'message', 'Listing sudah ditutup atau tidak aktif.');
    END IF;

    IF p_action = 'PLACE_BID' THEN
        IF p_offered_qty <= 0 OR p_offered_qty > v_listing.remaining_kg THEN
            RETURN jsonb_build_object('success', false, 'message', 'Kuantitas tawaran melebihi sisa stok yang tersedia.');
        END IF;

        IF v_listing.floor_price IS NOT NULL AND p_offered_price < v_listing.floor_price THEN
            RETURN jsonb_build_object('success', false, 'message', 'Harga tawaran di bawah harga dasar (Floor Price) petani.');
        END IF;

        UPDATE bids 
        SET status = 'withdrawn' 
        WHERE listing_id = p_listing_id AND collector_id = p_collector_id AND status = 'active';

        INSERT INTO bids (
            listing_id, collector_id, farmer_id, scheme, price_per_kg, 
            quantity_kg, status, logistics_mode, created_at
        )
        VALUES (
            p_listing_id, p_collector_id, v_listing.farmer_id, p_scheme, p_offered_price,
            p_offered_qty, 'active', p_logistics_mode, NOW()
        )
        RETURNING id INTO v_new_bid_id;

        RETURN jsonb_build_object(
            'success', true, 
            'bid_id', v_new_bid_id,
            'message', 'Tawaran lelang berhasil diajukan.',
            'remaining_kg', v_listing.remaining_kg
        );

    ELSIF p_action = 'ACCEPT_BID' THEN
        SELECT * INTO v_bid 
        FROM bids 
        WHERE id = p_bid_id AND listing_id = p_listing_id 
        FOR UPDATE;

        IF NOT FOUND OR v_bid.status != 'active' THEN
            RETURN jsonb_build_object('success', false, 'message', 'Tawaran tidak ditemukan atau sudah tidak aktif.');
        END IF;

        IF p_offered_qty <= 0 OR p_offered_qty > v_bid.quantity_kg THEN
            RETURN jsonb_build_object('success', false, 'message', 'Jumlah yang disetujui melebihi kuantitas tawaran.');
        END IF;

        IF p_offered_qty > v_listing.remaining_kg THEN
            RETURN jsonb_build_object('success', false, 'message', 'Jumlah yang disetujui melebihi sisa stok listing.');
        END IF;

        v_rem_qty := v_listing.remaining_kg - p_offered_qty;

        UPDATE bids 
        SET status = 'accepted', accepted_kg = p_offered_qty 
        WHERE id = v_bid.id;

        UPDATE stock_listings 
        SET remaining_kg = GREATEST(0.0, v_rem_qty),
            status = CASE WHEN v_rem_qty <= 1e-6 THEN 'closed' ELSE 'partially_awarded' END,
            auction_status = 'ACCEPTED'
        WHERE id = p_listing_id;

        RETURN jsonb_build_object(
            'success', true,
            'accepted_bid_id', v_bid.id,
            'accepted_qty_kg', p_offered_qty,
            'remaining_stock_kg', GREATEST(0.0, v_rem_qty),
            'message', 'Kesepakatan lelang berhasil disetujui secara atomik.'
        );
    ELSE
        RETURN jsonb_build_object('success', false, 'message', 'Aksi tidak valid.');
    END IF;
END;
$$;

-- ----------------------------------------------------------------------------
-- 6. ATOMIC RPC 2: KONFIRMASI JADWAL JEMPUT PETANI
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION rpc_respond_pickup_schedule_atomic(
    p_bid_id INTEGER,
    p_farmer_id INTEGER,
    p_decision VARCHAR(20),
    p_reschedule_note TEXT DEFAULT NULL,
    p_reschedule_date VARCHAR(30) DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_bid RECORD;
BEGIN
    SELECT b.* INTO v_bid
    FROM bids b
    JOIN stock_listings l ON l.id = b.listing_id
    WHERE b.id = p_bid_id AND l.farmer_id = p_farmer_id
    FOR UPDATE OF b;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'message', 'Tawaran jadwal tidak ditemukan atau bukan hak akses Anda.');
    END IF;

    IF p_decision = 'APPROVE' THEN
        UPDATE bids
        SET farmer_schedule_status = 'APPROVED',
            farmer_schedule_note = COALESCE(p_reschedule_note, 'Disetujui Petani')
        WHERE id = p_bid_id;

        RETURN jsonb_build_object('success', true, 'status', 'APPROVED', 'message', 'Jadwal penjemputan berhasil dikonfirmasi.');
    ELSIF p_decision = 'RESCHEDULE' THEN
        UPDATE bids
        SET farmer_schedule_status = 'RESCHEDULE_REQUESTED',
            farmer_schedule_note = format('Minta ganti jadwal ke %s: %s', COALESCE(p_reschedule_date, '-'), COALESCE(p_reschedule_note, ''))
        WHERE id = p_bid_id;

        RETURN jsonb_build_object('success', true, 'status', 'RESCHEDULE_REQUESTED', 'message', 'Permintaan penyesuaian jadwal terkirim ke pengepul.');
    ELSE
        RETURN jsonb_build_object('success', false, 'message', 'Keputusan jadwal tidak valid.');
    END IF;
END;
$$;

-- ----------------------------------------------------------------------------
-- 7. ATOMIC RPC 3: MUTASI STOK RAMP & REKALKULASI MUTU REKURSIF
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION rpc_allocate_loading_ramp_atomic(
    p_ramp_id INTEGER,
    p_inbound_kg DOUBLE PRECISION,
    p_inbound_mc DOUBLE PRECISION,
    p_inbound_ash DOUBLE PRECISION,
    p_inbound_lhv DOUBLE PRECISION
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_ramp RECORD;
    v_new_total DOUBLE PRECISION;
    v_weighted_mc DOUBLE PRECISION;
    v_weighted_ash DOUBLE PRECISION;
    v_weighted_lhv DOUBLE PRECISION;
BEGIN
    SELECT * INTO v_ramp 
    FROM loading_ramps 
    WHERE id = p_ramp_id 
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'message', 'Loading Ramp ID tidak ditemukan.');
    END IF;

    IF (v_ramp.current_stock_kg + p_inbound_kg) > v_ramp.max_capacity_kg THEN
        RETURN jsonb_build_object(
            'success', false, 
            'message', format('Kapasitas fisik ramp terlampaui! Maks: %s kg, Permintaan: %s kg', 
                              v_ramp.max_capacity_kg, (v_ramp.current_stock_kg + p_inbound_kg))
        );
    END IF;

    v_new_total := v_ramp.current_stock_kg + p_inbound_kg;

    IF v_new_total <= 0 THEN
        v_weighted_mc := p_inbound_mc;
        v_weighted_ash := p_inbound_ash;
        v_weighted_lhv := p_inbound_lhv;
    ELSE
        v_weighted_mc := ((v_ramp.current_stock_kg * v_ramp.aggregate_mc) + (p_inbound_kg * p_inbound_mc)) / v_new_total;
        v_weighted_ash := ((v_ramp.current_stock_kg * v_ramp.aggregate_ash) + (p_inbound_kg * p_inbound_ash)) / v_new_total;
        v_weighted_lhv := ((v_ramp.current_stock_kg * v_ramp.aggregate_lhv_kcal) + (p_inbound_kg * p_inbound_lhv)) / v_new_total;
    END IF;

    UPDATE loading_ramps 
    SET current_stock_kg = v_new_total,
        aggregate_mc = ROUND(v_weighted_mc::numeric, 2),
        aggregate_ash = ROUND(v_weighted_ash::numeric, 2),
        aggregate_lhv_kcal = ROUND(v_weighted_lhv::numeric, 1),
        updated_at = NOW()
    WHERE id = p_ramp_id;

    RETURN jsonb_build_object(
        'success', true,
        'ramp_code', v_ramp.ramp_code,
        'current_stock_kg', v_new_total,
        'aggregate_mc', ROUND(v_weighted_mc::numeric, 2),
        'aggregate_ash', ROUND(v_weighted_ash::numeric, 2),
        'aggregate_lhv_kcal', ROUND(v_weighted_lhv::numeric, 1),
        'message', 'Stok dan agregat mutu ramp berhasil diperbarui secara rekursif.'
    );
END;
$$;

-- ----------------------------------------------------------------------------
-- 8. ATOMIC RPC 4: GATEKEEPER AMBANG BATAS LOGAM BERAT BIOCHAR (KEAMANAN LAHAN)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION rpc_verify_byproduct_heavy_metals_atomic(
    p_byproduct_id INTEGER,
    p_pb_ppm DOUBLE PRECISION,
    p_cd_ppm DOUBLE PRECISION,
    p_as_ppm DOUBLE PRECISION,
    p_lab_cert_no VARCHAR(100)
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_byproduct RECORD;
    v_is_safe BOOLEAN;
BEGIN
    SELECT * INTO v_byproduct 
    FROM by_product_ledgers 
    WHERE id = p_byproduct_id 
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'message', 'Data by-product tidak ditemukan.');
    END IF;

    -- Ambang Batas Aman Pertanian: Pb < 50 ppm, Cd < 2 ppm, As < 10 ppm
    v_is_safe := (p_pb_ppm < 50.0) AND (p_cd_ppm < 2.0) AND (p_as_ppm < 10.0);

    IF v_is_safe THEN
        UPDATE by_product_ledgers 
        SET pb_ppm = p_pb_ppm,
            cd_ppm = p_cd_ppm,
            as_ppm = p_as_ppm,
            is_safety_passed = TRUE,
            lab_cert_no = p_lab_cert_no,
            circular_status = 'APPROVED_FOR_SOIL'
        WHERE id = p_byproduct_id;

        RETURN jsonb_build_object(
            'success', true, 
            'is_safe', true, 
            'status', 'APPROVED_FOR_SOIL',
            'message', '✅ Lolos uji logam berat! Biochar disetujui untuk distribusi sirkular ke lahan petani.'
        );
    ELSE
        UPDATE by_product_ledgers 
        SET pb_ppm = p_pb_ppm,
            cd_ppm = p_cd_ppm,
            as_ppm = p_as_ppm,
            is_safety_passed = FALSE,
            lab_cert_no = p_lab_cert_no,
            circular_status = 'REJECTED_HAZARDOUS'
        WHERE id = p_byproduct_id;

        RETURN jsonb_build_object(
            'success', true, 
            'is_safe', false, 
            'status', 'REJECTED_HAZARDOUS',
            'message', '⛔ Melebihi ambang batas logam berat aman! Ditolak dan dialihkan ke penanganan limbah B3.'
        );
    END IF;
END;
$$;

COMMIT;
