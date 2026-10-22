-- Bio-Chain v2 · Migrasi 012 — Jejak audit tagihan (settlement_events), constraint model, fungsi atomic next_trx_seq, & perbaikan RLS harvests
BEGIN;
SET LOCAL lock_timeout = '5s';

-- 1. Pastikan check constraints pada collector_settlements terpasang (jika tabel dibuat via Base.metadata.create_all)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ck_settle_status'
  ) THEN
    ALTER TABLE collector_settlements
      ADD CONSTRAINT ck_settle_status CHECK (status IN ('menunggu_harga', 'terutang', 'dibayar')) NOT VALID;
    ALTER TABLE collector_settlements VALIDATE CONSTRAINT ck_settle_status;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ck_settle_paid_ref'
  ) THEN
    ALTER TABLE collector_settlements
      ADD CONSTRAINT ck_settle_paid_ref CHECK (status <> 'dibayar' OR payment_reference IS NOT NULL) NOT VALID;
    ALTER TABLE collector_settlements VALIDATE CONSTRAINT ck_settle_paid_ref;
  END IF;
END $$;

-- 2. Tabel settlement_events: audit perubahan harga dan status tagihan (append-only)
CREATE TABLE IF NOT EXISTS settlement_events (
  id             SERIAL PRIMARY KEY,
  settlement_id  INTEGER NOT NULL REFERENCES collector_settlements(id) ON DELETE RESTRICT,
  action         VARCHAR(20) NOT NULL,
  old_price      DOUBLE PRECISION,
  new_price      DOUBLE PRECISION,
  old_amount     DOUBLE PRECISION,
  new_amount     DOUBLE PRECISION,
  reason         TEXT,
  actor_id       INTEGER NOT NULL REFERENCES users(id),
  created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_settlement_events_settlement_id ON settlement_events (settlement_id);

-- Trigger immutable (forbid_mutation sudah ada dari migrasi 002)
DROP TRIGGER IF EXISTS trg_settlement_events_immutable ON settlement_events;
CREATE TRIGGER trg_settlement_events_immutable
  BEFORE UPDATE OR DELETE ON settlement_events
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- RLS untuk settlement_events
ALTER TABLE settlement_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE settlement_events FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS se_operator ON settlement_events;
CREATE POLICY se_operator ON settlement_events FOR ALL
  USING (app_is_operator()) WITH CHECK (app_is_operator());

DROP POLICY IF EXISTS se_own_read ON settlement_events;
CREATE POLICY se_own_read ON settlement_events FOR SELECT
  USING (app_role() = 'pengepul' AND settlement_id IN (
    SELECT id FROM collector_settlements WHERE collector_id = app_uid()
  ));

DROP POLICY IF EXISTS se_audit ON settlement_events;
CREATE POLICY se_audit ON settlement_events FOR SELECT
  USING (app_role() = 'auditor');

-- 3. Fungsi PL/pgSQL atomic sequence TRX di database
CREATE OR REPLACE FUNCTION next_trx_seq(p_sender text, p_receiver text, p_yymm text)
RETURNS integer LANGUAGE sql AS $$
  INSERT INTO trx_sequences (sender_code, receiver_code, yymm, last_seq) VALUES (p_sender, p_receiver, p_yymm, 1)
  ON CONFLICT (sender_code, receiver_code, yymm) DO UPDATE SET last_seq = trx_sequences.last_seq + 1
  RETURNING last_seq;
$$;

GRANT EXECUTE ON FUNCTION next_trx_seq(text, text, text) TO PUBLIC;

-- 4. Perbaikan RLS harvests: cegah IDOR pada harvest hasil lelang (hanya pemenang lelang atau unassigned yang bisa diakses)
DROP POLICY IF EXISTS harvests_rw ON harvests;
CREATE POLICY harvests_rw ON harvests FOR ALL
  USING (
    app_is_operator()
    OR (app_role() = 'petani'   AND farmer_id = app_uid())
    OR (app_role() = 'pengepul' AND ((status = 'reported' AND collector_id IS NULL) OR collector_id = app_uid()))
    OR (app_role() = 'driver'   AND id IN (SELECT harvest_id FROM route_stops WHERE harvest_id IS NOT NULL)))
  WITH CHECK (
    app_is_operator()
    OR (app_role() = 'petani'   AND farmer_id = app_uid())
    OR (app_role() = 'pengepul' AND collector_id = app_uid())
    OR (app_role() = 'driver'   AND id IN (SELECT harvest_id FROM route_stops WHERE harvest_id IS NOT NULL)));

COMMIT;
