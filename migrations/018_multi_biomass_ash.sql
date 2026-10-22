-- Migrasi 018 — disetujui pengguna 11 Okt 2026 ("lanjut dan approve semua")
-- Multi-biomassa Jawa, gudang pengepul multi-komoditas dengan refraksi otomatis, dan ledger abu agronomi.
--   1. biomass_parameters        : master karakteristik proksimat/ultimat/oksida abu per komoditas (+ sumber)
--   2. harvests/stock_listings   : kolom commodity (default 'sekam_padi' → data & alur lama tidak berubah)
--   3. collector_warehouses      : gudang milik pengepul (bisa > 1)
--      warehouse_stock_movements : ledger stok APPEND-ONLY per gudang × komoditas (saldo = SUM), refraksi tercatat
--   4. farmer_groups             : kelompok tani (Poktan) penerima abu
--      industrial_ash_ledgers    : abu boiler/pirolisis → uji logam berat → alokasi ke Poktan → serah-terima berfoto
-- Idempoten & aman diulang. Rollback: 018_multi_biomass_ash.rollback.sql
BEGIN;
SET LOCAL lock_timeout = '5s';

-- ---------------------------------------------------------------- 1. master biomassa
CREATE TABLE IF NOT EXISTS biomass_parameters (
  code                  VARCHAR(24) PRIMARY KEY,           -- sekam_padi, tongkol_jagung, ampas_tebu, ...
  name                  VARCHAR(80) NOT NULL,
  is_active             BOOLEAN NOT NULL DEFAULT TRUE,
  -- proksimat (MC % basis basah as-received; lainnya % basis kering)
  moisture_typ_pct      DOUBLE PRECISION NOT NULL,
  moisture_min_pct      DOUBLE PRECISION,
  moisture_max_pct      DOUBLE PRECISION,
  ash_pct_db            DOUBLE PRECISION NOT NULL,
  volatile_pct_db       DOUBLE PRECISION,
  fixed_carbon_pct_db   DOUBLE PRECISION,
  -- energi & fisik
  hhv_db_mj_kg          DOUBLE PRECISION,
  lhv_db_mj_kg          DOUBLE PRECISION NOT NULL,
  bulk_density_kg_m3    DOUBLE PRECISION,
  -- ultimat (% bk)
  carbon_pct_db         DOUBLE PRECISION,
  hydrogen_pct_db       DOUBLE PRECISION,
  nitrogen_pct_db       DOUBLE PRECISION,
  sulfur_pct_db         DOUBLE PRECISION,
  chlorine_pct_db       DOUBLE PRECISION,
  -- oksida abu (% massa ABU) → indeks alkali, B/A, Rs, Fu
  sio2_pct_ash          DOUBLE PRECISION,
  k2o_pct_ash           DOUBLE PRECISION,
  na2o_pct_ash          DOUBLE PRECISION,
  cao_pct_ash           DOUBLE PRECISION,
  mgo_pct_ash           DOUBLE PRECISION,
  fe2o3_pct_ash         DOUBLE PRECISION,
  al2o3_pct_ash         DOUBLE PRECISION,
  p2o5_pct_ash          DOUBLE PRECISION,
  -- dagang: acuan refraksi pengepul
  moisture_ref_pct      DOUBLE PRECISION NOT NULL,          -- kadar air acuan harga (basis kering setara)
  moisture_reject_pct   DOUBLE PRECISION NOT NULL,          -- di atas ini lot ditolak/opsi keringkan sendiri
  contaminant_tol_pct   DOUBLE PRECISION NOT NULL DEFAULT 2, -- tanah/batu yang ditoleransi tanpa potongan
  base_price_per_kg     DOUBLE PRECISION,                    -- harga beli dasar Rp/kg: WAJIB diisi pabrik (tanpa bawaan)
  source                TEXT NOT NULL,                       -- rujukan setiap angka (docs/15)
  updated_by_id         INTEGER REFERENCES users(id),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_bp_moisture CHECK (moisture_typ_pct BETWEEN 0 AND 95 AND moisture_ref_pct BETWEEN 0 AND 95
                                   AND moisture_reject_pct > moisture_ref_pct),
  CONSTRAINT ck_bp_ash      CHECK (ash_pct_db >= 0 AND ash_pct_db < 60),
  CONSTRAINT ck_bp_lhv      CHECK (lhv_db_mj_kg > 5 AND lhv_db_mj_kg < 35),
  CONSTRAINT ck_bp_price    CHECK (base_price_per_kg IS NULL OR base_price_per_kg >= 0)
);

ALTER TABLE biomass_parameters ADD COLUMN IF NOT EXISTS base_price_per_kg DOUBLE PRECISION;
-- create_all aplikasi bisa membuat tabel lebih dulu (default hanya di Python) → samakan default server
ALTER TABLE biomass_parameters ALTER COLUMN is_active SET DEFAULT TRUE;
ALTER TABLE biomass_parameters ALTER COLUMN updated_at SET DEFAULT now();
ALTER TABLE biomass_parameters ALTER COLUMN contaminant_tol_pct SET DEFAULT 2;

-- Seed: diisi dari docs/15_RISET_MULTI_BIOMASSA_ABU_WTE.md (setiap angka bersumber). ON CONFLICT DO NOTHING agar
-- koreksi lab pabrik tidak tertimpa saat migrasi diulang.
-- Nilai = titik tengah rentang literatur, BUKAN hasil lab. Ganti per lot dengan hasil uji (ISO 18134/18122/18125).
INSERT INTO biomass_parameters (code, name, moisture_typ_pct, moisture_min_pct, moisture_max_pct, ash_pct_db, volatile_pct_db, fixed_carbon_pct_db, hhv_db_mj_kg, lhv_db_mj_kg, bulk_density_kg_m3, sulfur_pct_db, chlorine_pct_db, sio2_pct_ash, k2o_pct_ash, na2o_pct_ash, cao_pct_ash, mgo_pct_ash, fe2o3_pct_ash, al2o3_pct_ash, p2o5_pct_ash, moisture_ref_pct, moisture_reject_pct, contaminant_tol_pct, source) VALUES
  ('sekam_padi', 'Sekam padi', 12, 8, 14, 17.5, 66, 16.5, 15.5, 14.3, 120, 0.05, 0.1, 91, 3, 0.5, 1.5, 0.6, 0.3, 0.5, 0.9, 12, 20, 2, '[V] SiO2 abu: Fernandes dkk. 2016 Fuel 165:351; [L] Jenkins 1998, Vassilev 2010/2013, Phyllis2 — nilai tengah docs/15 §1'),
  ('tongkol_jagung', 'Tongkol jagung', 13, 9, 30, 2.0, 80, 18.0, 18.2, 17.0, 200, 0.05, 0.15, 32, 35, 1.5, 6, 5, 1.5, 2.5, 6, 15, 30, 2, '[L] Phyllis2; Vassilev 2010/2013 — K2O abu tinggi → indeks alkali tinggi walau abu rendah (docs/15 §1–2)'),
  ('ampas_tebu', 'Ampas tebu (bagasse)', 50, 45, 55, 3.0, 83, 14.0, 18.7, 17.5, 120, 0.05, 0.05, 55, 7, 1, 5, 3, 6, 10, 3, 50, 60, 3, '[L] Jenkins 1998; Vassilev 2010/2013 — Fe2O3/Al2O3 tinggi = kontaminasi tanah (docs/15 §1)'),
  ('tempurung_kelapa', 'Tempurung kelapa', 10, 8, 12, 1.0, 76, 23.0, 20.1, 18.9, 425, 0.05, 0.15, 25, 32, 5, 9, 5, 2.5, 2.5, 3, 12, 20, 1, '[V] VM/C: review T&F 2024 doi:10.1080/23311916.2024.2307201; [L] Phyllis2, Vassilev 2013 (docs/15 §1)'),
  ('sabut_kelapa', 'Sabut/serat kelapa (coir)', 15, 10, 20, 4.0, 70, 26.0, 18.7, 17.5, 85, 0.1, 0.8, 20, 32, 8, 6, 4, 1.5, 1.5, 2.5, 15, 30, 3, '[L] Vassilev 2010; Phyllis2 coir — Cl 0,3–1,5 % (korosi/HCl), dipisah dari tempurung (docs/15 §1)'),
  ('serbuk_sengon', 'Serbuk gergaji sengon', 40, 30, 55, 1.2, 82, 16.8, 19.1, 17.9, 200, 0.03, 0.02, 20, 12, 1.5, 32, 6, 2.5, 4, 3, 30, 60, 2, '[V] MC sawmill 50–70 %: J. Mat. Dev. Tech. UGM (PLTU Pelabuhan Ratu); [L] Phyllis2 hardwood sawdust (docs/15 §1)'),
  ('serbuk_karet', 'Serbuk kayu karet', 40, 30, 55, 1.6, 80, 18.4, 18.7, 17.5, 230, 0.03, 0.02, 20, 12, 1.5, 32, 6, 2.5, 4, 3, 30, 60, 2, '[L] Phyllis2 hardwood (proxy) — wajib uji lab per lot (docs/15 §1)')
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------- 2. komoditas pada alur transaksi
ALTER TABLE harvests       ADD COLUMN IF NOT EXISTS commodity VARCHAR(24) NOT NULL DEFAULT 'sekam_padi';
ALTER TABLE stock_listings ADD COLUMN IF NOT EXISTS commodity VARCHAR(24) NOT NULL DEFAULT 'sekam_padi';
DO $$ BEGIN
  ALTER TABLE harvests ADD CONSTRAINT fk_harvest_commodity FOREIGN KEY (commodity) REFERENCES biomass_parameters(code);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  ALTER TABLE stock_listings ADD CONSTRAINT fk_listing_commodity FOREIGN KEY (commodity) REFERENCES biomass_parameters(code);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS ix_harvests_commodity_status ON harvests (commodity, status);
CREATE INDEX IF NOT EXISTS ix_listings_commodity_status ON stock_listings (commodity, status);
-- accept_bid_atomic (013) tidak berubah: penguncian SELECT ... FOR UPDATE per listing berlaku untuk semua komoditas;
-- harvest hasil lelang mewarisi listing.commodity (diisi aplikasi di services/trade.py).

-- ---------------------------------------------------------------- 3. gudang pengepul & ledger stok
CREATE TABLE IF NOT EXISTS collector_warehouses (
  id            SERIAL PRIMARY KEY,
  collector_id  INTEGER NOT NULL REFERENCES users(id),
  name          VARCHAR(80) NOT NULL,
  lat           DOUBLE PRECISION,
  lon           DOUBLE PRECISION,
  capacity_m3   DOUBLE PRECISION,
  is_covered    BOOLEAN NOT NULL DEFAULT TRUE,               -- beratap? (musim hujan: sekam terbuka cepat basah)
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_warehouse_name UNIQUE (collector_id, name)
);

CREATE TABLE IF NOT EXISTS warehouse_stock_movements (
  id                 SERIAL PRIMARY KEY,
  warehouse_id       INTEGER NOT NULL REFERENCES collector_warehouses(id),
  commodity          VARCHAR(24) NOT NULL REFERENCES biomass_parameters(code),
  movement           VARCHAR(12) NOT NULL,                   -- masuk | keluar | susut | koreksi
  gross_kg           DOUBLE PRECISION NOT NULL,              -- timbangan (+ masuk, − keluar/susut)
  moisture_pct       DOUBLE PRECISION,                       -- kadar air terukur saat timbang
  contaminant_pct    DOUBLE PRECISION,                       -- tanah/batu/plastik terukur
  payable_kg         DOUBLE PRECISION NOT NULL,              -- setelah refraksi kadar air & kontaminan
  refraction_kg      DOUBLE PRECISION NOT NULL DEFAULT 0,    -- gross − payable (tercatat di nota)
  refraction_basis   JSONB,                                  -- rumus & acuan saat itu (audit)
  harvest_id         INTEGER REFERENCES harvests(id),
  delivery_ref       VARCHAR(40),                            -- DR/rute tujuan untuk 'keluar'
  note               TEXT,
  client_event_id    VARCHAR(64) UNIQUE,                     -- idempoten antrean offline
  created_by_id      INTEGER NOT NULL REFERENCES users(id),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_wsm_movement CHECK (movement IN ('masuk', 'keluar', 'susut', 'koreksi')),
  CONSTRAINT ck_wsm_sign     CHECK ((movement = 'masuk' AND gross_kg > 0) OR (movement IN ('keluar', 'susut') AND gross_kg < 0)
                                    OR movement = 'koreksi'),
  CONSTRAINT ck_wsm_refr     CHECK (refraction_kg >= 0 AND (movement <> 'masuk' OR payable_kg <= gross_kg)),
  CONSTRAINT ck_wsm_quality  CHECK ((moisture_pct IS NULL OR moisture_pct BETWEEN 0 AND 95)
                                    AND (contaminant_pct IS NULL OR contaminant_pct BETWEEN 0 AND 100))
);
CREATE INDEX IF NOT EXISTS ix_wsm_wh_commodity ON warehouse_stock_movements (warehouse_id, commodity);
DROP TRIGGER IF EXISTS trg_wsm_append_only ON warehouse_stock_movements;
CREATE TRIGGER trg_wsm_append_only BEFORE UPDATE OR DELETE ON warehouse_stock_movements
  FOR EACH ROW WHEN (current_setting('biochain.allow_reset', true) IS DISTINCT FROM 'on')
  EXECUTE FUNCTION forbid_mutation();

CREATE OR REPLACE VIEW warehouse_stock WITH (security_invoker = true) AS
  SELECT w.collector_id, m.warehouse_id, m.commodity,
         SUM(m.gross_kg) AS gross_kg, SUM(m.payable_kg) AS payable_kg, MAX(m.created_at) AS last_movement_at
  FROM warehouse_stock_movements m JOIN collector_warehouses w ON w.id = m.warehouse_id
  GROUP BY w.collector_id, m.warehouse_id, m.commodity;

-- ---------------------------------------------------------------- 4. kelompok tani & ledger abu
CREATE TABLE IF NOT EXISTS farmer_groups (
  id              SERIAL PRIMARY KEY,
  name            VARCHAR(120) NOT NULL,
  simluhtan_id    VARCHAR(40) UNIQUE,                        -- nomor registrasi Poktan (opsional)
  desa            VARCHAR(100),
  kecamatan       VARCHAR(100) NOT NULL,
  kabupaten       VARCHAR(100) NOT NULL,
  leader_user_id  INTEGER REFERENCES users(id),              -- ketua (boleh petani tanpa HP → NULL)
  leader_name     VARCHAR(120) NOT NULL,
  member_count    INTEGER,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS industrial_ash_ledgers (
  id                  SERIAL PRIMARY KEY,
  code                VARCHAR(24) NOT NULL UNIQUE,           -- ASH-2610-001 (label karung/BAST)
  factory_id          INTEGER NOT NULL REFERENCES users(id), -- akun pabrik penghasil
  ash_type            VARCHAR(12) NOT NULL,                  -- fly_ash | bottom_ash | silica_ash
  source_commodity    VARCHAR(24) REFERENCES biomass_parameters(code),
  batch_id            INTEGER REFERENCES manufacturing_batches(id),
  quantity_kg         DOUBLE PRECISION NOT NULL,
  -- uji laboratorium (ppm = mg/kg bk); status dihitung aplikasi dari batas parameter (Kepmentan 261/2019), bukan diketik
  pb_ppm              DOUBLE PRECISION,
  cd_ppm              DOUBLE PRECISION,
  as_ppm              DOUBLE PRECISION,
  hg_ppm              DOUBLE PRECISION,
  cr_ppm              DOUBLE PRECISION,
  ni_ppm              DOUBLE PRECISION,
  lab_name            VARCHAR(120),
  lab_report_no       VARCHAR(80),
  lab_report_url      TEXT,
  limits_snapshot     JSONB,                                  -- batas yang berlaku saat dinilai (parameter)
  heavy_metal_status  VARCHAR(10) NOT NULL DEFAULT 'belum_uji', -- belum_uji | lulus | gagal
  -- agronomi (opsional, untuk dosis aplikasi)
  k2o_pct             DOUBLE PRECISION,
  cao_pct             DOUBLE PRECISION,
  sio2_pct            DOUBLE PRECISION,
  ph                  DOUBLE PRECISION,
  -- alokasi & serah-terima
  status              VARCHAR(12) NOT NULL DEFAULT 'tersedia', -- tersedia | dialokasikan | diserahkan | dibuang
  farmer_group_id     INTEGER REFERENCES farmer_groups(id),
  land_lat            DOUBLE PRECISION,
  land_lon            DOUBLE PRECISION,
  land_area_ha        DOUBLE PRECISION,
  handover_photo_url  TEXT,
  handed_over_at      TIMESTAMPTZ,
  handed_over_by_id   INTEGER REFERENCES users(id),
  disposal_note       TEXT,                                   -- abu gagal uji: tujuan pembuangan berizin
  created_by_id       INTEGER NOT NULL REFERENCES users(id),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_ash_type    CHECK (ash_type IN ('fly_ash', 'bottom_ash', 'silica_ash')),
  CONSTRAINT ck_ash_qty     CHECK (quantity_kg > 0),
  CONSTRAINT ck_ash_metal   CHECK (heavy_metal_status IN ('belum_uji', 'lulus', 'gagal')),
  CONSTRAINT ck_ash_status  CHECK (status IN ('tersedia', 'dialokasikan', 'diserahkan', 'dibuang')),
  -- Gerbang keamanan pangan: abu hanya boleh ke lahan petani bila LULUS uji logam berat
  CONSTRAINT ck_ash_only_pass_to_farm CHECK (status IN ('tersedia', 'dibuang') OR heavy_metal_status = 'lulus'),
  CONSTRAINT ck_ash_lulus_needs_lab   CHECK (heavy_metal_status <> 'lulus' OR (pb_ppm IS NOT NULL AND cd_ppm IS NOT NULL
                                              AND as_ppm IS NOT NULL AND lab_report_no IS NOT NULL)),
  CONSTRAINT ck_ash_alloc   CHECK (status NOT IN ('dialokasikan', 'diserahkan') OR farmer_group_id IS NOT NULL),
  CONSTRAINT ck_ash_handover CHECK (status <> 'diserahkan' OR (handover_photo_url IS NOT NULL AND handed_over_at IS NOT NULL
                                    AND land_lat IS NOT NULL AND land_lon IS NOT NULL)),
  CONSTRAINT ck_ash_dispose CHECK (status <> 'dibuang' OR disposal_note IS NOT NULL)
);
ALTER TABLE industrial_ash_ledgers ALTER COLUMN heavy_metal_status TYPE VARCHAR(10);
ALTER TABLE industrial_ash_ledgers ALTER COLUMN heavy_metal_status SET DEFAULT 'belum_uji';
ALTER TABLE industrial_ash_ledgers ALTER COLUMN status SET DEFAULT 'tersedia';
ALTER TABLE industrial_ash_ledgers ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE collector_warehouses ALTER COLUMN is_covered SET DEFAULT TRUE;
ALTER TABLE collector_warehouses ALTER COLUMN is_active SET DEFAULT TRUE;
ALTER TABLE collector_warehouses ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE warehouse_stock_movements ALTER COLUMN refraction_kg SET DEFAULT 0;
ALTER TABLE warehouse_stock_movements ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE farmer_groups ALTER COLUMN created_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS ix_ash_status ON industrial_ash_ledgers (status, heavy_metal_status);
CREATE INDEX IF NOT EXISTS ix_ash_group ON industrial_ash_ledgers (farmer_group_id);

-- ---------------------------------------------------------------- RLS
ALTER TABLE biomass_parameters ENABLE ROW LEVEL SECURITY; ALTER TABLE biomass_parameters FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bp_read ON biomass_parameters;
CREATE POLICY bp_read ON biomass_parameters FOR SELECT USING (app_role() IS NOT NULL);
DROP POLICY IF EXISTS bp_operator ON biomass_parameters;
CREATE POLICY bp_operator ON biomass_parameters FOR ALL USING (app_is_operator()) WITH CHECK (app_is_operator());

ALTER TABLE collector_warehouses ENABLE ROW LEVEL SECURITY; ALTER TABLE collector_warehouses FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS wh_owner ON collector_warehouses;
CREATE POLICY wh_owner ON collector_warehouses FOR ALL
  USING (app_role() = 'pengepul' AND collector_id = app_uid()) WITH CHECK (app_role() = 'pengepul' AND collector_id = app_uid());
DROP POLICY IF EXISTS wh_operator ON collector_warehouses;
CREATE POLICY wh_operator ON collector_warehouses FOR ALL USING (app_is_operator()) WITH CHECK (app_is_operator());
DROP POLICY IF EXISTS wh_audit ON collector_warehouses;
CREATE POLICY wh_audit ON collector_warehouses FOR SELECT USING (app_role() = 'auditor');

ALTER TABLE warehouse_stock_movements ENABLE ROW LEVEL SECURITY; ALTER TABLE warehouse_stock_movements FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS wsm_owner ON warehouse_stock_movements;
CREATE POLICY wsm_owner ON warehouse_stock_movements FOR ALL
  USING (app_role() = 'pengepul' AND EXISTS (SELECT 1 FROM collector_warehouses w WHERE w.id = warehouse_id AND w.collector_id = app_uid()))
  WITH CHECK (app_role() = 'pengepul' AND created_by_id = app_uid()
              AND EXISTS (SELECT 1 FROM collector_warehouses w WHERE w.id = warehouse_id AND w.collector_id = app_uid()));
DROP POLICY IF EXISTS wsm_operator ON warehouse_stock_movements;
CREATE POLICY wsm_operator ON warehouse_stock_movements FOR ALL USING (app_is_operator()) WITH CHECK (app_is_operator());
DROP POLICY IF EXISTS wsm_audit ON warehouse_stock_movements;
CREATE POLICY wsm_audit ON warehouse_stock_movements FOR SELECT USING (app_role() = 'auditor');

ALTER TABLE farmer_groups ENABLE ROW LEVEL SECURITY; ALTER TABLE farmer_groups FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS fg_read ON farmer_groups;
CREATE POLICY fg_read ON farmer_groups FOR SELECT USING (app_role() IS NOT NULL);
DROP POLICY IF EXISTS fg_operator ON farmer_groups;
CREATE POLICY fg_operator ON farmer_groups FOR ALL USING (app_is_operator()) WITH CHECK (app_is_operator());

ALTER TABLE industrial_ash_ledgers ENABLE ROW LEVEL SECURITY; ALTER TABLE industrial_ash_ledgers FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ash_operator ON industrial_ash_ledgers;
CREATE POLICY ash_operator ON industrial_ash_ledgers FOR ALL USING (app_is_operator()) WITH CHECK (app_is_operator());
DROP POLICY IF EXISTS ash_audit ON industrial_ash_ledgers;
CREATE POLICY ash_audit ON industrial_ash_ledgers FOR SELECT USING (app_role() = 'auditor');
-- Petani anggota Poktan melihat abu yang dialokasikan ke kelompoknya (ketua tercatat sebagai user)
DROP POLICY IF EXISTS ash_group_leader ON industrial_ash_ledgers;
CREATE POLICY ash_group_leader ON industrial_ash_ledgers FOR SELECT
  USING (app_role() = 'petani' AND EXISTS (SELECT 1 FROM farmer_groups g WHERE g.id = farmer_group_id AND g.leader_user_id = app_uid()));

COMMIT;
