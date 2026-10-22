-- Rollback migrasi 012
BEGIN;
SET LOCAL lock_timeout = '5s';

DROP FUNCTION IF EXISTS next_trx_seq(text, text, text);

DROP TRIGGER IF EXISTS trg_settlement_events_immutable ON settlement_events;
DROP TABLE IF EXISTS settlement_events;

-- Kembalikan kebijakan RLS harvests
DROP POLICY IF EXISTS harvests_rw ON harvests;
CREATE POLICY harvests_rw ON harvests FOR ALL
  USING (
    app_is_operator()
    OR (app_role() = 'petani'   AND farmer_id = app_uid())
    OR (app_role() = 'pengepul' AND (status = 'reported' OR collector_id = app_uid()))
    OR (app_role() = 'driver'   AND id IN (SELECT harvest_id FROM route_stops WHERE harvest_id IS NOT NULL)))
  WITH CHECK (
    app_is_operator()
    OR (app_role() = 'petani'   AND farmer_id = app_uid())
    OR (app_role() = 'pengepul' AND collector_id = app_uid())
    OR (app_role() = 'driver'   AND id IN (SELECT harvest_id FROM route_stops WHERE harvest_id IS NOT NULL)));

ALTER TABLE collector_settlements DROP CONSTRAINT IF EXISTS ck_settle_status;
ALTER TABLE collector_settlements DROP CONSTRAINT IF EXISTS ck_settle_paid_ref;

COMMIT;
