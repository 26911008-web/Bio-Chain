# 13 — Catatan Sesi & Titik Pulih (Checkpoint) Bio-Chain

**Tanggal Disimpan:** 11 Oktober 2026, 15:52 WIB  
**Status Sesi:** SELESAI, TERSIMPAN & TERVERIFIKASI  
**Branch Git:** `feat/modul-petani-esg-audit`  
**Commit Terakhir:** `8289463` (`feat: penguatan audit metodologi karbon (Puro 2025/VM0044), kadar air biochar, verifikasi end-use & dokumentasi gap persona`)

---

## 1. Ringkasan Status Bio-Chain Prototype

### A. Fitur & Penguatan Mutu
1. **Audit Metodologi Karbon & ESG:**
   - Standar referensi: *Puro.earth Biochar Methodology 2025 v2*, *Verra VM0044*, *IPCC 2019 Refinement*, *GHG Protocol Land Sector and Removals*, *Perpres No. 110/2025 NEK*.
   - Parameter baru terintegrasi: `karbon.biochar_moisture_pct` (10%), `karbon.uncertainty_deduction_pct` (10%), `karbon.pyrolysis_ch4_kg_per_t_biochar` (0.0), `karbon.lpg_ef_kg_co2e_per_kg` (2.985).
   - Logika removal karbon terverifikasi hanya menghitung biochar yang telah diserahkan ke lahan (`biochar_redemptions`).
   - Emisi pembakaran terbuka dihindari (*avoided open burning*) dipisahkan dari removal neto.
   - Status di UI diubah menjadi *"Pra-verifikasi (Belum terdaftar SRN-PPI · Perpres 110/2025)"*.

2. **Penguatan Persona Pengguna:**
   - **Petani:** Form terpadu lapor & lelang, info mutu opsional, dukungan petani tanpa HP, modul biochar sawah (ekonomi sirkular).
   - **Pengepul:** Kontrol margin %, tombol WA langsung, tombol tolak lot berdasar 6 kategori cacat.
   - **Driver:** Mode offline-first (PWA + Service Worker + IndexedDB), faktor emisi solar WTW B40.
   - **Pabrik/QC:** Verifikasi serah terima biochar sekali pakai, laporan ESG (29 KPI), register aksi efisiensi 4-mata.

### B. Dokumentasi Terkait
- [10_PEMBARUAN_MODUL_PETANI_PENGEPUL_ESG.md](file:///d:/IDE/bio-chain-prototype/docs/10_PEMBARUAN_MODUL_PETANI_PENGEPUL_ESG.md)
- [11_RUNBOOK_OPERASIONAL.md](file:///d:/IDE/bio-chain-prototype/docs/11_RUNBOOK_OPERASIONAL.md)
- [12_AUDIT_GAP_PERSONA_DAN_STANDAR_ILMIAH.md](file:///d:/IDE/bio-chain-prototype/docs/12_AUDIT_GAP_PERSONA_DAN_STANDAR_ILMIAH.md)

### C. Hasil Pengujian
- Total pengujian: 487 item
- Hasil: **473 passed, 14 skipped, 0 failed** (100% hijau)
- Lingkungan teruji: SQLite lokal & PostgreSQL dengan RLS

---

## 2. Cara Melanjutkan atau Menjalankan Sesi Berikutnya

- Menjalankan dev server Bio-Chain:
  ```powershell
  .\jalankan.ps1
  # atau
  jalankan.bat
  ```
- Menjalankan seluruh test suite:
  ```powershell
  python -m pytest
  ```
