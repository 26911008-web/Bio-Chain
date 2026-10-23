-- Bio-Chain v2 · Migrasi 028 — Satu rating pengepul per (petani, panen) (audit 23 Okt 2026)
-- Mencegah manipulasi skor reputasi pengepul dengan rating berulang. Rollback: 028_…rollback.sql
BEGIN;
SET LOCAL lock_timeout = '5s';
DO $$
DECLARE dup integer;
BEGIN
  SELECT count(*) INTO dup FROM (
    SELECT farmer_id, harvest_id FROM collector_ratings WHERE harvest_id IS NOT NULL
     GROUP BY farmer_id, harvest_id HAVING count(*) > 1) d;
  IF dup > 0 THEN
    RAISE EXCEPTION '% pasangan (petani, panen) punya rating ganda — bereskan sebelum migrasi 028', dup;
  END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS uq_collector_rating_farmer_harvest
  ON collector_ratings (farmer_id, harvest_id) WHERE harvest_id IS NOT NULL;
INSERT INTO schema_migrations (version, note) VALUES ('028_collector_rating_once_per_harvest', 'audit 23 Okt 2026')
ON CONFLICT (version) DO NOTHING;
COMMIT;
