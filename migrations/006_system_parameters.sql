-- Bio-Chain v2 · Migrasi 006 — Parameter asumsi yang dapat diubah lewat menu + audit · PostgreSQL 16
-- Expand-only. Tabel kosong = semua modul memakai default di app/params.py (perilaku identik versi sebelumnya).
-- Rollback: 006_system_parameters.rollback.sql
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE TABLE IF NOT EXISTS system_parameters (
  key           VARCHAR(80) PRIMARY KEY,
  value         JSONB NOT NULL,
  updated_by_id INTEGER REFERENCES users(id),
  updated_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS parameter_changes (
  id              SERIAL PRIMARY KEY,
  key             VARCHAR(80) NOT NULL,
  old_value       JSONB,
  new_value       JSONB,                 -- NULL = dikembalikan ke default
  changed_by_id   INTEGER NOT NULL REFERENCES users(id),
  changed_by_role VARCHAR(20) NOT NULL CHECK (changed_by_role IN ('pabrik','admin')),
  reason          TEXT NOT NULL CHECK (length(trim(reason)) >= 5),
  created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_parameter_changes_key ON parameter_changes (key);

-- Riwayat asumsi tidak boleh diubah/dihapus (fungsi forbid_mutation dari migrasi 002)
DROP TRIGGER IF EXISTS trg_param_changes_append_only ON parameter_changes;
CREATE TRIGGER trg_param_changes_append_only BEFORE UPDATE OR DELETE ON parameter_changes
  FOR EACH ROW WHEN (current_setting('biochain.allow_reset', true) IS DISTINCT FROM 'on')
  EXECUTE FUNCTION forbid_mutation();
COMMIT;
