-- ============================================================================
-- MIGRATION 023: Gate Reception, Weighbridge QC, Dynamic Loading Ramp,
-- Multi-Ramp Blending, Financial Invoices & Dispatch Isolation
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. ISOLASI DISPATCH ARMADA PABRIK vs PENGANTARAN MANDIRI PENGEPUL
-- ----------------------------------------------------------------------------
ALTER TABLE routes 
ADD COLUMN IF NOT EXISTS logistics_carrier VARCHAR(30) DEFAULT 'FACTORY_FLEET';

ALTER TABLE delivery_requests 
ADD COLUMN IF NOT EXISTS logistics_carrier VARCHAR(30) DEFAULT 'FACTORY_FLEET';

CREATE INDEX IF NOT EXISTS idx_routes_carrier_status 
ON routes (logistics_carrier, status);

CREATE INDEX IF NOT EXISTS idx_dr_carrier_status 
ON delivery_requests (logistics_carrier, status);

-- ----------------------------------------------------------------------------
-- 2. SKEMA LOADING RAMP DINAMIS & MUTU REKURSIF
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS loading_ramps (
    id SERIAL PRIMARY KEY,
    ramp_code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    mill_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    biomass_type VARCHAR(50) NOT NULL,
    max_capacity_kg DOUBLE PRECISION NOT NULL DEFAULT 50000.0,
    current_stock_kg DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    aggregate_mc DOUBLE PRECISION NOT NULL DEFAULT 12.0,
    aggregate_ash DOUBLE PRECISION NOT NULL DEFAULT 15.0,
    aggregate_lhv_kcal DOUBLE PRECISION NOT NULL DEFAULT 3500.0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ramps_biomass_mill 
ON loading_ramps (mill_id, biomass_type, is_active);

-- Seed Ramp Awal Jika Kosong
INSERT INTO loading_ramps (ramp_code, name, biomass_type, max_capacity_kg, current_stock_kg, aggregate_mc, aggregate_ash, aggregate_lhv_kcal)
VALUES 
    ('RAMP-01', 'Ramp Utama Sekam Padi', 'sekam_padi', 60000.0, 15000.0, 13.5, 17.0, 3450.0),
    ('RAMP-02', 'Ramp Tongkol Jagung Cacah', 'tongkol_jagung', 45000.0, 8000.0, 14.0, 2.5, 4100.0),
    ('RAMP-03', 'Ramp Serbuk Kayu Sengon', 'serbuk_sengon', 40000.0, 5000.0, 28.0, 1.5, 3800.0),
    ('RAMP-04', 'Ramp Cangkang & Tempurung Kelapa', 'tempurung_kelapa', 50000.0, 12000.0, 10.5, 2.0, 4600.0)
ON CONFLICT (ramp_code) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 3. SKEMA GERBANG MASUK, QC TIMBANGAN JEMBATAN & DECISION 3-STATE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gate_receptions (
    id SERIAL PRIMARY KEY,
    ticket_number VARCHAR(50) UNIQUE NOT NULL,
    mill_id INTEGER NOT NULL REFERENCES users(id),
    collector_id INTEGER NOT NULL REFERENCES users(id),
    delivery_request_id INTEGER NULL REFERENCES delivery_requests(id),
    vehicle_plate VARCHAR(20) NOT NULL,
    driver_name VARCHAR(100) NOT NULL,
    logistics_carrier VARCHAR(30) NOT NULL DEFAULT 'FACTORY_FLEET',
    biomass_type VARCHAR(50) NOT NULL,
    
    -- Metrologi Timbangan Jembatan
    gross_weight DOUBLE PRECISION NOT NULL,
    tare_weight DOUBLE PRECISION NOT NULL,
    net_weight DOUBLE PRECISION NOT NULL,
    
    -- Parameter Pengujian Mutu Lapangan
    tested_mc_pct DOUBLE PRECISION NOT NULL,
    tested_ash_pct DOUBLE PRECISION NOT NULL,
    tested_lhv_kcal DOUBLE PRECISION NOT NULL DEFAULT 3500.0,
    contamination_pct DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    
    -- Keputusan QC 3-State
    qc_decision VARCHAR(25) NOT NULL DEFAULT 'ACCEPTED',
    accepted_qty_kg DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    rejected_qty_kg DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    rejection_reason TEXT NULL,
    qc_photo_url VARCHAR(500) NULL,
    
    -- Alokasi Ramp
    allocated_ramp_id INTEGER NULL REFERENCES loading_ramps(id),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gate_receptions_decision 
ON gate_receptions (mill_id, qc_decision, created_at);

-- ----------------------------------------------------------------------------
-- 4. FUNGSI STORED PROCEDURE REKURSIF MUTU RAMP (ATOMIC CONCURRENCY)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_allocate_to_ramp_recursive(
    p_ramp_id INTEGER,
    p_inbound_qty DOUBLE PRECISION,
    p_inbound_mc DOUBLE PRECISION,
    p_inbound_ash DOUBLE PRECISION,
    p_inbound_lhv DOUBLE PRECISION
)
RETURNS TABLE (
    success BOOLEAN,
    ramp_code VARCHAR,
    new_stock_kg DOUBLE PRECISION,
    new_mc DOUBLE PRECISION,
    new_ash DOUBLE PRECISION,
    new_lhv DOUBLE PRECISION,
    message TEXT
) 
LANGUAGE plpgsql
AS $$
DECLARE
    v_ramp RECORD;
    v_total_stock DOUBLE PRECISION;
    v_weighted_mc DOUBLE PRECISION;
    v_weighted_ash DOUBLE PRECISION;
    v_weighted_lhv DOUBLE PRECISION;
BEGIN
    -- Locking baris ramp dengan SELECT ... FOR UPDATE (Pessimistic Lock / Anti-Race Condition)
    SELECT * INTO v_ramp 
    FROM loading_ramps 
    WHERE id = p_ramp_id 
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, NULL::VARCHAR, 0.0, 0.0, 0.0, 0.0, 'Loading Ramp ID tidak ditemukan';
        RETURN;
    END IF;

    -- Validasi Kapasitas Fisik Ramp
    IF (v_ramp.current_stock_kg + p_inbound_qty) > v_ramp.max_capacity_kg THEN
        RETURN QUERY SELECT FALSE, v_ramp.ramp_code, v_ramp.current_stock_kg, 
                            v_ramp.aggregate_mc, v_ramp.aggregate_ash, v_ramp.aggregate_lhv_kcal, 
                            format('Kapasitas fisik terlampaui! Maksimal: %s kg, Permintaan: %s kg', 
                                   v_ramp.max_capacity_kg, (v_ramp.current_stock_kg + p_inbound_qty));
        RETURN;
    END IF;

    -- Kalkulasi Rata-Rata Tertimbang Rekursif (Weighted Average)
    v_total_stock := v_ramp.current_stock_kg + p_inbound_qty;
    
    IF v_total_stock <= 0 THEN
        v_weighted_mc := p_inbound_mc;
        v_weighted_ash := p_inbound_ash;
        v_weighted_lhv := p_inbound_lhv;
    ELSE
        v_weighted_mc := ((v_ramp.current_stock_kg * v_ramp.aggregate_mc) + (p_inbound_qty * p_inbound_mc)) / v_total_stock;
        v_weighted_ash := ((v_ramp.current_stock_kg * v_ramp.aggregate_ash) + (p_inbound_qty * p_inbound_ash)) / v_total_stock;
        v_weighted_lhv := ((v_ramp.current_stock_kg * v_ramp.aggregate_lhv_kcal) + (p_inbound_qty * p_inbound_lhv)) / v_total_stock;
    END IF;

    -- Pembaruan State Mutu Ramp
    UPDATE loading_ramps 
    SET current_stock_kg = v_total_stock,
        aggregate_mc = ROUND(v_weighted_mc::numeric, 2),
        aggregate_ash = ROUND(v_weighted_ash::numeric, 2),
        aggregate_lhv_kcal = ROUND(v_weighted_lhv::numeric, 1),
        updated_at = NOW()
    WHERE id = p_ramp_id;

    RETURN QUERY SELECT TRUE, v_ramp.ramp_code, v_total_stock, 
                        ROUND(v_weighted_mc::numeric, 2)::DOUBLE PRECISION, 
                        ROUND(v_weighted_ash::numeric, 2)::DOUBLE PRECISION, 
                        ROUND(v_weighted_lhv::numeric, 1)::DOUBLE PRECISION, 
                        'Stok dan mutu agregat berhasil diperbarui secara rekursif';
END;
$$;

-- ----------------------------------------------------------------------------
-- 5. SKEMA FINANSIAL & INVOICE MULTI-OPSI (CASH, DP, TOP JATUH TEMPO)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS factory_invoices (
    id SERIAL PRIMARY KEY,
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    mill_id INTEGER NOT NULL REFERENCES users(id),
    collector_id INTEGER NOT NULL REFERENCES users(id),
    gate_reception_id INTEGER NULL REFERENCES gate_receptions(id),
    biomass_type VARCHAR(50) NOT NULL,
    
    -- Kuantitas & Harga
    billable_qty_kg DOUBLE PRECISION NOT NULL,
    unit_price_rp DOUBLE PRECISION NOT NULL,
    total_amount_rp DOUBLE PRECISION NOT NULL,
    
    -- Skema Pembayaran
    payment_scheme VARCHAR(15) NOT NULL DEFAULT 'CASH',
    dp_paid_amount DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    remaining_amount DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    
    -- Kontrol Jatuh Tempo (Overdue Control)
    due_date DATE NOT NULL,
    is_overdue BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
        
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    settled_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_factory_invoices_due 
ON factory_invoices (mill_id, is_overdue, status, due_date);

-- ----------------------------------------------------------------------------
-- 6. SKEMA BLENDING MULTI-RAMP & LEDGER BY-PRODUCTS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS production_blends (
    id SERIAL PRIMARY KEY,
    blend_code VARCHAR(50) UNIQUE NOT NULL,
    mill_id INTEGER NOT NULL REFERENCES users(id),
    target_product VARCHAR(30) NOT NULL,
    
    ramp_allocations JSONB NOT NULL,
    total_input_kg DOUBLE PRECISION NOT NULL,
    
    -- Karakteristik Campuran Akhir
    final_mc_pct DOUBLE PRECISION NOT NULL,
    final_ash_pct DOUBLE PRECISION NOT NULL,
    final_lhv_kcal DOUBLE PRECISION NOT NULL,
    
    -- Analisis Finansial & Karbon
    cost_per_kg DOUBLE PRECISION NOT NULL,
    target_selling_price_per_kg DOUBLE PRECISION NOT NULL,
    estimated_margin_rp DOUBLE PRECISION NOT NULL,
    net_tco2e DOUBLE PRECISION NOT NULL,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS by_product_ledgers (
    id SERIAL PRIMARY KEY,
    blend_id INTEGER NULL REFERENCES production_blends(id) ON DELETE SET NULL,
    mill_id INTEGER NOT NULL REFERENCES users(id),
    by_product_type VARCHAR(30) NOT NULL,
    quantity_kg DOUBLE PRECISION NOT NULL,
    circular_status VARCHAR(30) NOT NULL DEFAULT 'STORED',
    recipient_farmer_id INTEGER NULL REFERENCES users(id),
    notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_byproducts_mill_circular 
ON by_product_ledgers (mill_id, circular_status, by_product_type);
