-- Peran aplikasi untuk PostgreSQL: TANPA superuser, TANPA BYPASSRLS, TANPA hak DDL.
-- Superuser & pemilik tabel melewati RLS; aplikasi wajib login sebagai peran ini agar migrasi 004/005/007 berlaku.
-- Jalankan sebagai pemilik skema SETELAH semua migrasi. Ganti password via variabel psql:
--   psql -v app_password="'rahasia'" -f migrations/000_app_role.sql
\if :{?app_password}
\else
  \set app_password '''biochain_app_dev'''
\endif

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'biochain_app') THEN
    CREATE ROLE biochain_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  END IF;
END $$;
ALTER ROLE biochain_app WITH PASSWORD :app_password NOBYPASSRLS;

GRANT CONNECT ON DATABASE biochain TO biochain_app;
GRANT USAGE ON SCHEMA public TO biochain_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO biochain_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO biochain_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO biochain_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO biochain_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO biochain_app;
