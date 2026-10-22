-- Bio-Chain v2 · Migrasi 021: Atomic Bidding RPC, Multi-Output BOM & Chain of Custody
-- Target: PostgreSQL 16 / Supabase
-- Rollback: migrations/021_concurrency_and_bom.rollback.sql

BEGIN;
SET LOCAL lock_timeout = '5s';

-- 1. TABEL NERACA MASSA MULTI-OUTPUT PABRIK (FACTORY BOM & MASS BALANCE)
CREATE TABLE IF NOT EXISTS factory_conversions_bom (
    id                          SERIAL PRIMARY KEY,
    batch_code                  VARCHAR(40) UNIQUE NOT NULL,
    factory_id                  INTEGER NOT NULL REFERENCES users(id),
    feedstock_commodity         VARCHAR(30) NOT NULL, -- sekam_padi, tongkol_jagung, serbuk_sengon, ampas_tebu
    
    -- Parameter Input Umpan
    input_gross_kg              DOUBLE PRECISION NOT NULL CHECK (input_gross_kg > 0),
    input_moisture_pct          DOUBLE PRECISION NOT NULL CHECK (input_moisture_pct BETWEEN 0 AND 95),
    input_ash_pct               DOUBLE PRECISION NOT NULL CHECK (input_ash_pct BETWEEN 0 AND 60),
    input_dry_kg                DOUBLE PRECISION NOT NULL,
    
    -- Alokasi Output Produk Bernilai Tambah
    output_biochar_kg           DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (output_biochar_kg >= 0),
    output_biosilica_kg         DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (output_biosilica_kg >= 0),
    output_biopellet_kg         DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (output_biopellet_kg >= 0),
    output_briquette_kg         DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (output_briquette_kg >= 0),
    output_syngas_m3            DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (output_syngas_m3 >= 0),
    recovered_energy_gj         DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (recovered_energy_gj >= 0),

    -- Fraksi Residu & Kehilangan Termal (Losses)
    moisture_evaporation_loss_kg DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (moisture_evaporation_loss_kg >= 0),
    tar_residual_kg             DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (tar_residual_kg >= 0),
    shrinkage_loss_kg           DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (shrinkage_loss_kg >= 0),

    -- Indikator Neraca Massa (% Penutupan Neraca Massa)
    mass_balance_closure_pct    DOUBLE PRECISION NOT NULL CHECK (mass_balance_closure_pct BETWEEN 90.0 AND 110.0),
    
    status                      VARCHAR(20) NOT NULL DEFAULT 'completed' CHECK (status IN ('in_progress', 'completed', 'flagged')),
    evidence_photo_url          TEXT,
    note                        TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_factory_conversions_bom_factory_id ON factory_conversions_bom (factory_id);
CREATE INDEX IF NOT EXISTS ix_factory_conversions_bom_commodity ON factory_conversions_bom (feedstock_commodity);


-- 2. ATOMIC BIDDING ENGINE (POSTGRESQL RPC DENGAN ROW-LEVEL 'FOR UPDATE')
CREATE OR REPLACE FUNCTION fn_place_bid_atomic(
    p_listing_id       INTEGER,
    p_collector_id     INTEGER,
    p_scheme           VARCHAR,
    p_price_per_kg     DOUBLE PRECISION,
    p_quantity_kg      DOUBLE PRECISION,
    p_pickup_date      VARCHAR DEFAULT NULL,
    p_note             TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_listing          RECORD;
    v_reserve_price    DOUBLE PRECISION;
    v_new_bid_id       INTEGER;
    v_now              TIMESTAMPTZ := now();
BEGIN
    -- 1. Kunci Baris Listing secara Eksklusif (Row-Level Lock)
    SELECT * INTO v_listing
    FROM stock_listings
    WHERE id = p_listing_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Listing #% tidak ditemukan', p_listing_id USING ERRCODE = 'P0002';
    END IF;

    -- 2. Validasi Status Listing
    IF v_listing.status NOT IN ('open', 'partially_awarded') THEN
        RAISE EXCEPTION 'Listing #% sudah tidak aktif (status: %)', p_listing_id, v_listing.status USING ERRCODE = '22000';
    END IF;

    IF v_listing.expires_at IS NOT NULL AND v_listing.expires_at < v_now THEN
        RAISE EXCEPTION 'Listing #% sudah kedaluwarsa pada %', p_listing_id, v_listing.expires_at USING ERRCODE = '22000';
    END IF;

    -- 3. Validasi Skema & Harga Cadangan (Reserve Price)
    IF p_scheme = 'jemput' THEN
        IF NOT v_listing.allow_jemput THEN
            RAISE EXCEPTION 'Petani tidak membuka skema jemput (EXW) untuk listing ini' USING ERRCODE = '22000';
        END IF;
        v_reserve_price := v_listing.ask_price_jemput;
    ELSIF p_scheme = 'antar' THEN
        IF NOT v_listing.allow_antar THEN
            RAISE EXCEPTION 'Petani tidak membuka skema antar (DAP) untuk listing ini' USING ERRCODE = '22000';
        END IF;
        v_reserve_price := v_listing.ask_price_antar;
    ELSE
        RAISE EXCEPTION 'Skema tidak sah: %. Gunakan jemput atau antar', p_scheme USING ERRCODE = '22000';
    END IF;

    IF v_reserve_price IS NOT NULL AND p_price_per_kg < v_reserve_price THEN
        RAISE EXCEPTION 'Tawaran Rp%/kg di bawah harga minimum petani (Rp%/kg)', p_price_per_kg, v_reserve_price USING ERRCODE = '22000';
    END IF;

    -- 4. Validasi Ketersediaan Sisa Tonase
    IF p_quantity_kg > v_listing.remaining_kg + 1e-6 THEN
        RAISE EXCEPTION 'Jumlah tawaran (% kg) melebihi sisa stok (% kg)', p_quantity_kg, v_listing.remaining_kg USING ERRCODE = '22000';
    END IF;

    -- 5. Tarik Tawaran Aktif Sebelumnya dari Pengepul yang Sama
    UPDATE bids
    SET status = 'withdrawn', decided_at = v_now
    WHERE listing_id = p_listing_id
      AND collector_id = p_collector_id
      AND scheme = p_scheme
      AND status = 'active';

    -- 6. Masukkan Tawaran Baru
    INSERT INTO bids (
        listing_id, collector_id, scheme, price_per_kg, quantity_kg,
        pickup_date, note, status, created_at
    )
    VALUES (
        p_listing_id, p_collector_id, p_scheme, p_price_per_kg, p_quantity_kg,
        p_pickup_date, p_note, 'active', v_now
    )
    RETURNING id INTO v_new_bid_id;

    -- 7. Update Versi Listing
    UPDATE stock_listings
    SET version = version + 1
    WHERE id = p_listing_id;

    RETURN jsonb_build_object(
        'success', TRUE,
        'bid_id', v_new_bid_id,
        'listing_id', p_listing_id,
        'collector_id', p_collector_id,
        'scheme', p_scheme,
        'price_per_kg', p_price_per_kg,
        'quantity_kg', p_quantity_kg,
        'remaining_stock_kg', v_listing.remaining_kg,
        'created_at', v_now
    );
END;
$$;


-- 3. SEQUENCE GENERATOR UNIK BULANAN (CHAIN OF CUSTODY)
CREATE OR REPLACE FUNCTION fn_generate_trx_verification_code(
    p_sender_id      INTEGER,
    p_receiver_id    INTEGER
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_yymm           VARCHAR(4) := to_char(now(), 'YYMM');
    v_sender_code    VARCHAR(12) := 'USR' || lpad(p_sender_id::text, 4, '0');
    v_receiver_code  VARCHAR(12) := 'USR' || lpad(p_receiver_id::text, 4, '0');
    v_seq            INTEGER;
BEGIN
    INSERT INTO trx_sequences (sender_code, receiver_code, yymm, last_seq)
    VALUES (v_sender_code, v_receiver_code, v_yymm, 1)
    ON CONFLICT (sender_code, receiver_code, yymm)
    DO UPDATE SET last_seq = trx_sequences.last_seq + 1
    RETURNING last_seq INTO v_seq;

    RETURN 'TRX-' || v_sender_code || '-' || v_receiver_code || '-' || v_yymm || '-' || lpad(v_seq::text, 5, '0');
END;
$$;

COMMIT;
