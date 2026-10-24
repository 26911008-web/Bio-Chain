-- Bio-Chain v2 · Migrasi 029 — Kuota harian Asisten AI per akun (default 3 pertanyaan/hari, reset 00.00 WIB).
-- Logika pemesanan kuota: app/services/ai_quota.py (satu UPSERT atomik; kuota dikembalikan bila provider gagal).
-- Jalankan sebagai pemilik skema (biochain_owner):
--   psql "$OWNER_URL" -v ON_ERROR_STOP=1 -f migrations/029_ai_daily_quota.sql
-- Rollback: migrations/029_ai_daily_quota.rollback.sql

BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE TABLE IF NOT EXISTS user_ai_usage (
  id               serial  PRIMARY KEY,
  user_id          integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  request_count    integer NOT NULL DEFAULT 0 CHECK (request_count >= 0),
  last_reset_date  date    NOT NULL,
  CONSTRAINT uq_user_ai_usage_user_id UNIQUE (user_id)       -- target ON CONFLICT (user_id)
);

-- RLS: tiap akun hanya membaca/mengubah barisnya sendiri; admin/sistem untuk pemeliharaan.
ALTER TABLE user_ai_usage ENABLE ROW LEVEL SECURITY;  ALTER TABLE user_ai_usage FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ai_usage_own ON user_ai_usage;
CREATE POLICY ai_usage_own ON user_ai_usage FOR ALL
  USING (user_id = app_uid() OR app_role() IN ('admin', 'system'))
  WITH CHECK (user_id = app_uid() OR app_role() IN ('admin', 'system'));

INSERT INTO schema_migrations (version, note) VALUES ('029_ai_daily_quota', 'kuota AI harian 25 Okt 2026')
ON CONFLICT (version) DO NOTHING;

-- Hak hanya untuk peran aplikasi (bukan PUBLIC: di Supabase itu termasuk anon/authenticated PostgREST)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'biochain_app') THEN
    GRANT SELECT, INSERT, UPDATE ON user_ai_usage TO biochain_app;
    GRANT USAGE ON SEQUENCE user_ai_usage_id_seq TO biochain_app;
  END IF;
END $$;

COMMIT;
