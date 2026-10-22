-- Migrasi 013 — Operasi lapangan & logistik hijau (audit SOP PETA_FLOW, Okt 2026)
--  1. Siklus stop rute: pending | picked_up | failed | cancelled + pembatalan rute (panen bisa dijadwalkan ulang)
--  2. Jejak GPS store-and-forward + kolom emisi ISO 14083 per rute
--  3. Retur / karantina sekam basah-berjamur (seluruh lot atau sortir sebagian di QC)
--  4. BOM multi-output: kolom rendemen per produk + buku stok produk jadi (append-only)
--  5. Lelang: status tawaran 'cancelled' + fungsi PL/pgSQL accept_bid_atomic (SELECT ... FOR UPDATE)
-- Idempoten (IF NOT EXISTS / OR REPLACE). Rollback: 013_field_ops_green_logistics.rollback.sql
BEGIN;
SET LOCAL lock_timeout = '5s';

-- ---------------------------------------------------------------- 1. stop & rute
ALTER TABLE route_stops ADD COLUMN IF NOT EXISTS stop_status VARCHAR(12) NOT NULL DEFAULT 'pending';
ALTER TABLE route_stops ADD COLUMN IF NOT EXISTS fail_reason VARCHAR(30);
ALTER TABLE route_stops ADD COLUMN IF NOT EXISTS fail_note TEXT;
ALTER TABLE route_stops ADD COLUMN IF NOT EXISTS failed_at TIMESTAMPTZ;
UPDATE route_stops SET stop_status = 'picked_up' WHERE qr_scanned AND stop_status = 'pending';
ALTER TABLE route_stops DROP CONSTRAINT IF EXISTS ck_stop_status;
ALTER TABLE route_stops ADD CONSTRAINT ck_stop_status
  CHECK (stop_status IN ('pending', 'picked_up', 'failed', 'cancelled'));
ALTER TABLE route_stops DROP CONSTRAINT IF EXISTS ck_stop_pickup_consistent;
ALTER TABLE route_stops ADD CONSTRAINT ck_stop_pickup_consistent
  CHECK ((stop_status = 'picked_up') = COALESCE(qr_scanned, FALSE));
-- Satu stop HIDUP per harvest; stop gagal/batal melepas harvest untuk dijadwalkan ulang
DROP INDEX IF EXISTS uq_route_stops_harvest;
CREATE UNIQUE INDEX IF NOT EXISTS uq_route_stops_harvest_live ON route_stops (harvest_id)
  WHERE harvest_id IS NOT NULL AND stop_status IN ('pending', 'picked_up');

ALTER TABLE routes ADD COLUMN IF NOT EXISTS optimizer VARCHAR(40);
ALTER TABLE routes ADD COLUMN IF NOT EXISTS actual_km DOUBLE PRECISION;
ALTER TABLE routes ADD COLUMN IF NOT EXISTS fuel_l DOUBLE PRECISION;
ALTER TABLE routes ADD COLUMN IF NOT EXISTS co2e_wtw_kg DOUBLE PRECISION;
ALTER TABLE routes ADD COLUMN IF NOT EXISTS co2e_per_ton_kg DOUBLE PRECISION;
ALTER TABLE routes ADD COLUMN IF NOT EXISTS emission_detail JSON;
ALTER TABLE routes ADD COLUMN IF NOT EXISTS cancel_reason TEXT;
ALTER TABLE routes ADD COLUMN IF NOT EXISTS cancelled_by_id INTEGER REFERENCES users(id);
ALTER TABLE routes ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;

-- ---------------------------------------------------------------- 2. jejak GPS
CREATE TABLE IF NOT EXISTS route_track_points (
  id               SERIAL PRIMARY KEY,
  route_id         INTEGER NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
  driver_id        INTEGER NOT NULL REFERENCES users(id),
  client_point_id  VARCHAR(64) NOT NULL UNIQUE,              -- idempotensi unggah ulang setelah offline
  recorded_at      TIMESTAMPTZ NOT NULL,                     -- jam perangkat saat GPS merekam
  lat              DOUBLE PRECISION NOT NULL CHECK (lat BETWEEN -90 AND 90),
  lon              DOUBLE PRECISION NOT NULL CHECK (lon BETWEEN -180 AND 180),
  accuracy_m       DOUBLE PRECISION,
  speed_mps        DOUBLE PRECISION,
  received_at      TIMESTAMPTZ DEFAULT now()                 -- jam server saat tersinkron
);
CREATE INDEX IF NOT EXISTS ix_track_route_time ON route_track_points (route_id, recorded_at);
ALTER TABLE route_track_points ENABLE ROW LEVEL SECURITY; ALTER TABLE route_track_points FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS track_rw ON route_track_points;
CREATE POLICY track_rw ON route_track_points FOR ALL
  USING (app_is_operator() OR (app_role() = 'driver' AND driver_id = app_uid()))
  WITH CHECK (app_is_operator() OR (app_role() = 'driver' AND driver_id = app_uid()
                                    AND route_id IN (SELECT id FROM routes)));
DROP POLICY IF EXISTS track_audit ON route_track_points;
CREATE POLICY track_audit ON route_track_points FOR SELECT USING (app_role() = 'auditor');
-- Titik GPS adalah bukti MRV: tidak boleh diubah/dihapus (hanya ikut terhapus bila rute dihapus)
DROP TRIGGER IF EXISTS trg_track_no_update ON route_track_points;
CREATE TRIGGER trg_track_no_update BEFORE UPDATE ON route_track_points
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ---------------------------------------------------------------- 3. retur / karantina
ALTER TABLE inbound_qc ADD COLUMN IF NOT EXISTS rejected_kg DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE inbound_qc DROP CONSTRAINT IF EXISTS ck_qc_rejected;
ALTER TABLE inbound_qc ADD CONSTRAINT ck_qc_rejected CHECK (rejected_kg >= 0);

CREATE TABLE IF NOT EXISTS return_cases (
  id                  SERIAL PRIMARY KEY,
  harvest_id          INTEGER REFERENCES harvests(id),
  request_id          INTEGER REFERENCES delivery_requests(id),
  qc_id               INTEGER REFERENCES inbound_qc(id),
  stage               VARCHAR(20) NOT NULL,                  -- gerbang_pabrik | qc_pabrik | gudang_pabrik
  reason_code         VARCHAR(20) NOT NULL
                      CHECK (reason_code IN ('basah','berjamur','kontaminan','selisih_berat','stok_tidak_ada',
                                             'dibatalkan_pengepul','lainnya')),
  moisture            DOUBLE PRECISION,
  quantity_kg         DOUBLE PRECISION NOT NULL,
  location            VARCHAR(20) NOT NULL DEFAULT 'pabrik',
  disposition         VARCHAR(24) NOT NULL DEFAULT 'menunggu'
                      CHECK (disposition IN ('menunggu','kembalikan_ke_pengirim','keringkan_ulang','turun_grade',
                                             'bahan_bakar_boiler','musnahkan')),
  cost_bearer         VARCHAR(10) CHECK (cost_bearer IS NULL OR cost_bearer IN ('petani','pengepul','pabrik')),
  handling_cost_rp    DOUBLE PRECISION,
  status              VARCHAR(8) NOT NULL DEFAULT 'terbuka',
  evidence_photo_url  TEXT,
  note                TEXT,
  opened_by_id        INTEGER NOT NULL REFERENCES users(id),
  resolved_by_id      INTEGER REFERENCES users(id),
  resolution_note     TEXT,
  created_at          TIMESTAMPTZ DEFAULT now(),
  resolved_at         TIMESTAMPTZ,
  CONSTRAINT ck_ret_qty CHECK (quantity_kg > 0),
  CONSTRAINT ck_ret_cost CHECK (handling_cost_rp IS NULL OR handling_cost_rp >= 0),
  CONSTRAINT ck_ret_ref CHECK (harvest_id IS NOT NULL OR qc_id IS NOT NULL OR request_id IS NOT NULL),
  CONSTRAINT ck_ret_status CHECK (status IN ('terbuka', 'selesai')),
  CONSTRAINT ck_ret_resolved CHECK ((status = 'selesai') = (disposition <> 'menunggu'))
);
CREATE INDEX IF NOT EXISTS ix_return_cases_status ON return_cases (status);
CREATE INDEX IF NOT EXISTS ix_return_cases_harvest_id ON return_cases (harvest_id);
CREATE INDEX IF NOT EXISTS ix_return_cases_request_id ON return_cases (request_id);
CREATE INDEX IF NOT EXISTS ix_return_cases_qc_id ON return_cases (qc_id);
ALTER TABLE return_cases ENABLE ROW LEVEL SECURITY; ALTER TABLE return_cases FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ret_operator ON return_cases;
CREATE POLICY ret_operator ON return_cases FOR ALL USING (app_is_operator()) WITH CHECK (app_is_operator());
DROP POLICY IF EXISTS ret_audit ON return_cases;
CREATE POLICY ret_audit ON return_cases FOR SELECT USING (app_role() = 'auditor');
-- Kasus yang sudah selesai terkunci (disposisi = keputusan final yang diaudit)
CREATE OR REPLACE FUNCTION forbid_resolved_return_update() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'selesai' THEN
    RAISE EXCEPTION 'return_cases #% sudah selesai dan tidak dapat diubah', OLD.id;
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_return_locked ON return_cases;
CREATE TRIGGER trg_return_locked BEFORE UPDATE ON return_cases
  FOR EACH ROW EXECUTE FUNCTION forbid_resolved_return_update();
DROP TRIGGER IF EXISTS trg_return_no_delete ON return_cases;
CREATE TRIGGER trg_return_no_delete BEFORE DELETE ON return_cases
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ---------------------------------------------------------------- 4. BOM multi-output & stok produk jadi
ALTER TABLE batch_outputs ADD COLUMN IF NOT EXISTS expected_kg DOUBLE PRECISION;
ALTER TABLE batch_outputs ADD COLUMN IF NOT EXISTS yield_pct DOUBLE PRECISION;
ALTER TABLE batch_outputs ADD COLUMN IF NOT EXISTS yield_variance_pct DOUBLE PRECISION;

CREATE TABLE IF NOT EXISTS finished_goods_movements (
  id             SERIAL PRIMARY KEY,
  product        VARCHAR(12) NOT NULL CHECK (product IN ('bio_pellet', 'biochar', 'bio_silika')),
  movement       VARCHAR(16) NOT NULL
                 CHECK (movement IN ('produksi','penjualan','penyesuaian','retur_pelanggan','alokasi_petani')),
  quantity_kg    DOUBLE PRECISION NOT NULL CHECK (quantity_kg <> 0),     -- + masuk, − keluar
  batch_id       INTEGER REFERENCES manufacturing_batches(id),
  unit_price_rp  DOUBLE PRECISION,
  reference      VARCHAR(80),
  actor_id       INTEGER NOT NULL REFERENCES users(id),
  note           TEXT,
  created_at     TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_fg_product ON finished_goods_movements (product);
CREATE INDEX IF NOT EXISTS ix_fg_batch ON finished_goods_movements (batch_id);
ALTER TABLE finished_goods_movements ENABLE ROW LEVEL SECURITY; ALTER TABLE finished_goods_movements FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS fg_operator ON finished_goods_movements;
CREATE POLICY fg_operator ON finished_goods_movements FOR ALL USING (app_is_operator()) WITH CHECK (app_is_operator());
DROP POLICY IF EXISTS fg_audit ON finished_goods_movements;
CREATE POLICY fg_audit ON finished_goods_movements FOR SELECT USING (app_role() = 'auditor');
DROP TRIGGER IF EXISTS trg_fg_append_only ON finished_goods_movements;
CREATE TRIGGER trg_fg_append_only BEFORE UPDATE OR DELETE ON finished_goods_movements
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- Saldo stok = Σ mutasi (tidak pernah disimpan sebagai angka yang bisa diedit)
CREATE OR REPLACE VIEW finished_goods_stock WITH (security_invoker = true) AS
SELECT product, sum(quantity_kg) AS balance_kg,
       sum(quantity_kg) FILTER (WHERE movement = 'produksi') AS produced_kg,
       -sum(quantity_kg) FILTER (WHERE movement = 'penjualan') AS sold_kg,
       -sum(quantity_kg) FILTER (WHERE movement = 'alokasi_petani') AS returned_to_farmers_kg
FROM finished_goods_movements GROUP BY product;
GRANT SELECT ON finished_goods_stock TO PUBLIC;

-- Backfill: batch lama → mutasi produksi (sekali; batch yang sudah punya mutasi dilewati)
INSERT INTO finished_goods_movements (product, movement, quantity_kg, batch_id, reference, actor_id, note, created_at)
SELECT o.product, 'produksi', o.quantity_kg, b.id, b.batch_code, b.operator_id, 'backfill migrasi 013', b.created_at
FROM batch_outputs o JOIN manufacturing_batches b ON b.id = o.batch_id
WHERE o.quantity_kg > 0
  AND NOT EXISTS (SELECT 1 FROM finished_goods_movements f WHERE f.batch_id = b.id AND f.product = o.product
                  AND f.movement = 'produksi');

-- ---------------------------------------------------------------- 5. lelang atomik
ALTER TABLE bids DROP CONSTRAINT IF EXISTS bids_status_check;
ALTER TABLE bids ADD CONSTRAINT bids_status_check
  CHECK (status IN ('active', 'withdrawn', 'accepted', 'rejected', 'cancelled'));

-- Penerimaan tawaran dalam SATU fungsi: kunci baris listing lalu tawaran (urutan kunci tetap → bebas deadlock),
-- validasi stok & status di bawah kunci, kurangi stok, kunci tawaran, tutup tawaran lain bila stok habis.
-- SECURITY INVOKER: RLS petani tetap berlaku (hanya listing miliknya yang bisa dikunci).
CREATE OR REPLACE FUNCTION accept_bid_atomic(p_listing integer, p_bid integer, p_farmer integer,
                                             p_qty double precision)
RETURNS TABLE (remaining_kg double precision, listing_status text)
LANGUAGE plpgsql AS $$
DECLARE
  l stock_listings%ROWTYPE;
  b bids%ROWTYPE;
  new_remaining double precision;
  new_status text;
BEGIN
  SELECT * INTO l FROM stock_listings WHERE id = p_listing AND farmer_id = p_farmer FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'not_found:Listing tidak ditemukan';
  END IF;
  SELECT * INTO b FROM bids WHERE id = p_bid AND listing_id = p_listing FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'not_found:Tawaran tidak ditemukan pada listing ini';
  END IF;
  IF b.status <> 'active' THEN
    RAISE EXCEPTION 'conflict:Tawaran berstatus ''%''.', b.status;
  END IF;
  IF p_qty > b.quantity_kg + 1e-9 THEN
    RAISE EXCEPTION 'invalid:Jumlah melebihi tawaran pengepul (% kg).', b.quantity_kg;
  END IF;
  IF l.status NOT IN ('open', 'partially_awarded') OR l.remaining_kg < p_qty - 1e-9 THEN
    RAISE EXCEPTION 'conflict:Sisa stok tidak mencukupi atau listing sudah ditutup — muat ulang data.';
  END IF;
  IF l.expires_at IS NOT NULL AND l.expires_at < now() THEN
    RAISE EXCEPTION 'conflict:Listing sudah kedaluwarsa.';
  END IF;
  new_remaining := l.remaining_kg - p_qty;
  new_status := CASE WHEN new_remaining <= 1e-6 THEN 'closed' ELSE 'partially_awarded' END;
  UPDATE stock_listings SET remaining_kg = new_remaining, status = new_status, version = version + 1
   WHERE id = p_listing;
  UPDATE bids SET status = 'accepted', accepted_kg = p_qty, decided_at = now() WHERE id = p_bid;
  IF new_status = 'closed' THEN
    UPDATE bids SET status = 'rejected', decided_at = now() WHERE listing_id = p_listing AND status = 'active';
  END IF;
  RETURN QUERY SELECT new_remaining, new_status;
END $$;
GRANT EXECUTE ON FUNCTION accept_bid_atomic(integer, integer, integer, double precision) TO PUBLIC;

COMMIT;
