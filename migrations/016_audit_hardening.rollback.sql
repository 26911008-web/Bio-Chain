-- Rollback 016 — PERINGATAN: catatan DP & potongan logistik ikut hilang; ekspor dulu:
--   pg_dump -t farmer_down_payments -t logistics_charges
-- Pembayaran yang sudah memakai dp_rp > 0 membuat CHECK lama (net = gross − pajak) gagal; rollback ditolak
-- otomatis bila ada baris seperti itu — selesaikan secara manual.
BEGIN;
ALTER TABLE batch_losses DROP CONSTRAINT IF EXISTS ck_batch_losses_kind;
ALTER TABLE batch_losses ADD CONSTRAINT ck_batch_losses_kind
  CHECK (kind IN ('air','volatil_syngas','gas_pembakaran','residu_ekstraksi','susut_proses'));
ALTER TABLE inbound_qc DROP COLUMN IF EXISTS dry_basis_kg;
ALTER TABLE inbound_qc DROP COLUMN IF EXISTS refraction_kg;
DROP TABLE IF EXISTS logistics_charges;
ALTER TABLE farmer_payments DROP CONSTRAINT IF EXISTS ck_fpay_dp;
ALTER TABLE farmer_payments DROP CONSTRAINT IF EXISTS ck_fpay_net;
ALTER TABLE farmer_payments ADD CONSTRAINT ck_fpay_net CHECK (net_rp = gross_rp - tax_rp);
ALTER TABLE farmer_payments DROP COLUMN IF EXISTS dp_rp;
DROP TABLE IF EXISTS farmer_down_payments;
ALTER TABLE users DROP COLUMN IF EXISTS token_version;
COMMIT;
