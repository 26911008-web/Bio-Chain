-- Bio-Chain v2 · Migrasi 005 — Pasar B2B (listing, tawaran, resi serah-terima) · PostgreSQL 16
-- Expand-only: tabel & kolom baru nullable → kode lama tetap berjalan. Rollback: 005_b2b_trade.rollback.sql

BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE TABLE IF NOT EXISTS stock_listings (
  id                 SERIAL PRIMARY KEY,
  farmer_id          INTEGER NOT NULL REFERENCES users(id),
  mill_id            INTEGER REFERENCES mills(id),
  quantity_kg        DOUBLE PRECISION NOT NULL,
  remaining_kg       DOUBLE PRECISION NOT NULL,
  moisture_pct       DOUBLE PRECISION,
  grade_estimate     VARCHAR(5),
  allow_jemput       BOOLEAN NOT NULL DEFAULT TRUE,     -- ≈ Incoterms EXW
  allow_antar        BOOLEAN NOT NULL DEFAULT FALSE,    -- ≈ Incoterms DAP
  ask_price_jemput   DOUBLE PRECISION,                  -- reserve price Rp/kg
  ask_price_antar    DOUBLE PRECISION,
  lat DOUBLE PRECISION, lon DOUBLE PRECISION,
  evidence_photo_url TEXT,
  status             VARCHAR(17) NOT NULL DEFAULT 'open'
                     CHECK (status IN ('open','partially_awarded','closed','cancelled')),
  expires_at         TIMESTAMPTZ,
  version            INTEGER NOT NULL DEFAULT 1,
  created_at         TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT ck_listing_qty CHECK (quantity_kg > 0 AND remaining_kg >= 0 AND remaining_kg <= quantity_kg),
  CONSTRAINT ck_listing_scheme CHECK (allow_jemput OR allow_antar)
);
CREATE INDEX IF NOT EXISTS ix_stock_listings_farmer_id ON stock_listings (farmer_id);
CREATE INDEX IF NOT EXISTS ix_stock_listings_status ON stock_listings (status);

CREATE TABLE IF NOT EXISTS bids (
  id                      SERIAL PRIMARY KEY,
  listing_id              INTEGER NOT NULL REFERENCES stock_listings(id),
  collector_id            INTEGER NOT NULL REFERENCES users(id),
  scheme                  VARCHAR(6) NOT NULL CHECK (scheme IN ('jemput','antar')),
  price_per_kg            DOUBLE PRECISION NOT NULL,
  quantity_kg             DOUBLE PRECISION NOT NULL,
  accepted_kg             DOUBLE PRECISION NOT NULL DEFAULT 0,
  pickup_date             VARCHAR(10),
  est_logistic_cost_per_kg DOUBLE PRECISION,
  note                    TEXT,
  status                  VARCHAR(9) NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active','withdrawn','accepted','rejected')),
  created_at              TIMESTAMPTZ DEFAULT now(),
  decided_at              TIMESTAMPTZ,
  CONSTRAINT ck_bid_pos CHECK (price_per_kg > 0 AND quantity_kg > 0),
  CONSTRAINT ck_bid_accepted CHECK (accepted_kg >= 0)
);
CREATE INDEX IF NOT EXISTS ix_bids_listing_id ON bids (listing_id);
CREATE INDEX IF NOT EXISTS ix_bids_collector_id ON bids (collector_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_bid_active ON bids (listing_id, collector_id, scheme) WHERE status = 'active';

-- Penghitung resi: UPSERT ... RETURNING mengunci baris (sender, receiver, yymm) → nomor tidak pernah ganda
CREATE TABLE IF NOT EXISTS trx_sequences (
  id            SERIAL PRIMARY KEY,
  sender_code   VARCHAR(12) NOT NULL,
  receiver_code VARCHAR(12) NOT NULL,
  yymm          VARCHAR(4)  NOT NULL,
  last_seq      INTEGER NOT NULL DEFAULT 0,
  CONSTRAINT uq_trx_seq UNIQUE (sender_code, receiver_code, yymm)
);

ALTER TABLE harvests ADD COLUMN IF NOT EXISTS listing_id INTEGER REFERENCES stock_listings(id);
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS bid_id INTEGER REFERENCES bids(id);
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS agreed_price_per_kg DOUBLE PRECISION;
ALTER TABLE harvests ADD COLUMN IF NOT EXISTS delivery_scheme VARCHAR(10);
CREATE INDEX IF NOT EXISTS ix_harvests_listing_id ON harvests (listing_id);

ALTER TABLE custody_events ADD COLUMN IF NOT EXISTS verification_code VARCHAR(40);
ALTER TABLE custody_events ADD COLUMN IF NOT EXISTS sender_id INTEGER REFERENCES users(id);
ALTER TABLE custody_events ADD COLUMN IF NOT EXISTS receiver_id INTEGER REFERENCES users(id);
ALTER TABLE custody_events ADD COLUMN IF NOT EXISTS evidence_photo_url TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS uq_custody_verification_code ON custody_events (verification_code);
DO $$ BEGIN
  ALTER TABLE custody_events ADD CONSTRAINT ck_verification_code_format
    CHECK (verification_code IS NULL OR verification_code ~ '^TRX-[A-Z]{3}[0-9]{4,}-[A-Z]{3}[0-9]{4,}-[0-9]{4}-[0-9]{5,}$');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- RLS (melanjutkan 004): petani melihat listing & tawaran miliknya; pengepul melihat pasar terbuka
-- dan tawarannya sendiri; pabrik/admin/system penuh; auditor baca.
ALTER TABLE stock_listings ENABLE ROW LEVEL SECURITY; ALTER TABLE stock_listings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS listings_rw ON stock_listings;
CREATE POLICY listings_rw ON stock_listings FOR ALL
  USING (app_is_operator()
         OR (app_role() = 'petani' AND farmer_id = app_uid())
         OR (app_role() = 'pengepul' AND (status IN ('open','partially_awarded')
                                          OR id IN (SELECT listing_id FROM bids WHERE collector_id = app_uid()))))
  WITH CHECK (app_is_operator() OR (app_role() = 'petani' AND farmer_id = app_uid()));
DROP POLICY IF EXISTS listings_audit ON stock_listings;
CREATE POLICY listings_audit ON stock_listings FOR SELECT USING (app_role() = 'auditor');

ALTER TABLE bids ENABLE ROW LEVEL SECURITY; ALTER TABLE bids FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bids_rw ON bids;
CREATE POLICY bids_rw ON bids FOR ALL
  USING (app_is_operator()
         OR (app_role() = 'pengepul' AND collector_id = app_uid())
         OR (app_role() = 'petani' AND listing_id IN (SELECT id FROM stock_listings WHERE farmer_id = app_uid())))
  WITH CHECK (app_is_operator()
              OR (app_role() = 'pengepul' AND collector_id = app_uid())
              OR (app_role() = 'petani' AND listing_id IN (SELECT id FROM stock_listings WHERE farmer_id = app_uid())));
DROP POLICY IF EXISTS bids_audit ON bids;
CREATE POLICY bids_audit ON bids FOR SELECT USING (app_role() = 'auditor');

COMMIT;
