# 12 — Audit Komprehensif: Gap Persona Lapangan, Metodologi Ilmiah & Penguatan Repositori

**Tanggal:** 11 Oktober 2026  
**Status:** Selesai diuji (473 passed, 14 skipped di SQLite & PostgreSQL)  
**Tujuan:** Menyelesaikan mandat peninjauan audit dari sudut pandang persona pengguna dan auditor kepatuhan ilmiah/standar pasar karbon (Puro.earth 2025, Verra VM0044, IPCC 2019 Refinement, GHG Protocol Land Sector and Removals, POJK 51/2017, Perpres 110/2025).

---

## 1. Ringkasan Eksekutif & Gap Kritis yang Ditemukan

Audit mendalam terhadap alur bisnis, perhitungan teknis, dan interaksi UI menghasilkan perbaikan signifikan pada 2 pilar utama:
1. **Integritas Metodologi Karbon & ESG (Pilar Auditor):** Mengeliminasi risiko *over-crediting* dan *greenwashing* dalam perhitungan removal karbon biochar dan emisi rantai pasok.
2. **Kesesuaian Praktik Lapangan (Pilar Persona):** Menyesuaikan sistem dengan realitas operasional di pedesaan Indonesia (keterbatasan sinyal, timbangan manual/dacin, kadar air pasca-pendinginan biochar, dll.).

---

## 2. Analisis Gap per Persona & Solusi Lapangan

### A. Persona Petani (Kecil & Menengah)
* **Kondisi Riil Lapangan:**
  - Petani tidak memiliki *grain moisture meter* digital; kadar air diperkirakan secara fisik/organoleptik.
  - Sering kali menjual sekam dalam kondisi basah pasca-musim hujan atau penjemuran singkat.
  - Sebagian besar petani tidak memiliki akses aplikasi perbankan digital secara langsung atau tidak memiliki HP pintar (kelompok lanjut usia).
* **Temuan Gap Sebelumnya:**
  - Laporan stok dan lelang terpisah membuat petani bingung memilih alur.
  - Wajib input kadar air presisi membebani petani.
  - Penyerahan biochar sekam untuk sawah belum memiliki kalkulator manfaat ekonomi konkret.
* **Solusi & Penguatan yang Diterapkan:**
  - Form digabung menjadi satu kartu terpadu **🌾 Lapor & Jual Sekam**: mode *Jual ke Pengepul* (harga standar/offline) atau *Lelang* (tawaran masuk).
  - Kolom kadar air & grade dijadikan **opsional** (hanya sebagai estimasi awal; verifikasi mutlak oleh pengepul/pabrik).
  - Dukungan petani tanpa HP (**👵 Tanpa HP**) diakomodasi melalui input perwakilan oleh pengepul dengan validasi GPS & desa.
  - Modul **♻️ Biochar untuk Sawah** dilengkapi rumus ekonomi sirkular (peningkatan panen gabah GKP 1.8–5% + penghematan urea 15% selama 4 musim).

### B. Persona Pengepul (Kolektor Lokal)
* **Kondisi Riil Lapangan:**
  - Pengepul beroperasi di tingkat kecamatan/desa menggunakan pikap (L300, Gran Max).
  - Menghadapi fluktuasi margin harian dan risiko penolakan sekam oleh pabrik akibat jamur/kotoran/batu.
  - Menghubungi petani secara langsung lewat WhatsApp ketimbang telepon reguler.
* **Temuan Gap Sebelumnya:**
  - Tidak ada mekanisme pengaturan margin fleksibel berbasis persentase.
  - Pengepul tidak memiliki tombol tolak lot di antarmuka (hanya ada tombol verifikasi), sehingga jika barang rusak data menumpuk tanpa status jelas.
* **Solusi & Penguatan yang Diterapkan:**
  - Tombol **Margin %** dinamis (− / + langkah 0,5%) dengan referensi parameter pasar `pasar.default_margin_pct`.
  - Integrasi tombol **💬 WA** langsung membuka pesan terformat ke petani.
  - Tombol **⛔ Tolak Lot** dengan 6 kategori penyebab penolakan standar industri: *Kadar air terlalu tinggi*, *Berjamur/busuk*, *Kontaminan fisik (batu/tanah)*, *Selisih berat timbang*, *Stok fisik tidak tersedia*, dan *Lainnya*. Data ini menjadi dasar perhitungan *defect rate* di Laporan Mutu.

### C. Persona Sopir Armada (Logistik Hijau)
* **Kondisi Riil Lapangan:**
  - Sekam memiliki kerapatan ruah (*bulk density*) sangat rendah (100–120 kg/m³), sehingga volume bak truk penuh jauh sebelum kapasitas berat (tonase) tercapai.
  - Rute jalan pedesaan sering melewati area *blank spot* (tanpa sinyal internet).
* **Temuan Gap Sebelumnya:**
  - Pengemudi tidak dapat menginput serah terima jika tidak ada koneksi internet.
  - Emisi bahan bakar armada mengasumsikan diesel murni (B0) padahal Indonesia telah mewajibkan biosolar B35/B40.
* **Solusi & Penguatan yang Diterapkan:**
  - Driver didukung arsitektur **Offline-First** (PWA + Service Worker + IndexedDB) dengan antrean sinkronisasi otomatis saat sinyal kembali.
  - Perhitungan emisi logistik menerapkan faktor emisi *Well-to-Wheel* (WTW) biodiesel B40 (Kepmen ESDM 341.K/2024), mencerminkan emisi riil solar campuran Indonesia.

### D. Persona Operator & QC Pabrik (Pirolisis & Silika)
* **Kondisi Riil Lapangan:**
  - Biochar sekam padi pasca-keluar dari reaktor pirolisis bersuhu 450–650°C **wajib disemprot air (water quenching)** guna mencegah pembakaran spontan saat kontak dengan oksigen atmosfer.
  - Akibat pendinginan ini, biochar yang ditimbang memiliki kadar air 10%–25% (as-received).
* **Temuan Gap Kritis Sebelumnya:**
  - Perhitungan karbon sebelumnya mengalikan seluruh bobot biochar basah secara langsung dengan fraksi karbon organik ($F_C = 0.49$), mengasumsikan biochar berkadar air 0%! Ini adalah celah *over-claiming* karbon sebesar 10–25%.
  - Biochar yang baru keluar reaktor dan masih menumpuk di gudang pabrik langsung diakui sebagai *durable carbon removal*.
* **Solusi & Penguatan yang Diterapkan:**
  - Parameter baru `karbon.biochar_moisture_pct` (default 10%, dapat diatur sesuai hasil uji oven). Seluruh perhitungan karbon sekarang dikonversi ke **basis massa kering (dry matter basis)**:
    $$\text{Biochar Kering (ton)} = \text{Biochar Basah (ton)} \times (1 - \text{kadar air})$$
  - Pencatatan suhu operasional reaktor pirolisis divalidasi terhadap faktor persistensi karbon $F_{perm}(T)$ mengacu IPCC 2019 Refinement. Batch tanpa catatan suhu dikenai $F_{perm} = 0$.

---

## 3. Analisis Auditor: Penyelarasan Metodologi Ilmiah & Regulasi

Audit menemukan 5 ketidaksesuaian metodologis penting terhadap standar sertifikasi karbon global dan regulasi nasional:

| No | Parameter Audit | Praktik Lama | Standar Resmi / Best Practice | Implementasi Baru |
|---|---|---|---|---|
| 1 | **Syarat Pengakuan Removal (End-Use Verification)** | Biochar diakui sebagai removal seketika saat selesai diproduksi di reaktor. | **Puro.earth Biochar 2025 v2 & Verra VM0044:** Biochar belum boleh diklaim tahan lama sebelum ada bukti serah-terima fisik ke tanah/lahan (*end-use application*), untuk mencegah biochar dibakar ulang. | Dipisahkan: **Potensi Removal Bruto** (kapasitas seluruh produksi) vs **Removal Tahan Lama Terbukti** (hanya biochar dengan riwayat serah-terima sah via `biochar_redemptions`). |
| 2 | **Pemisahan Emisi Dihindari vs Removal** | Emisi pembakaran terbuka dihindari (*avoided open burning*) dijumlahkan ke dalam nilai neto removal. | **GHG Protocol Land Sector & Removals, IFRS S2, ISO 14064:** Emisi yang dihindari (*avoidance*) dan pengikatan karbon tahan lama (*removals*) adalah dua kategori terpisah dan **dilarang digabungkan**. | Emisi dihindari dilaporkan terpisah pada KPI E12; nilai removal bersih (E11) hanya memperhitungkan removal fisik dikurangi emisi proyek. |
| 3 | **Emisi Proyek Scope 1 Pabrik** | Hanya menghitung listrik (Scope 2) dan angkutan (Scope 3); bahan bakar pemanasan awal reaktor diabaikan. | **Puro Eq. 5.1 & GHG Protocol Scope 1:** Konsumsi solar/LPG pemanas awal (*startup burner*) dan metana reaktor harus dipotong dari gross removal. | Ditambahkan input solar/LPG pabrik (`karbon.lpg_ef_kg_co2e_per_kg`) dan parameter emisi cerobong `karbon.pyrolysis_ch4_kg_per_t_biochar`. |
| 4 | **Potongan Ketidakpastian (Uncertainty Deduction)** | Klaim 100% tanpa memperhitungkan variasi laboratorium. | **Verra VM0044 & Puro 2025:** Jika pengujian $C_{org}$ dan $H/C_{org}$ belum dilakukan per batch di laboratorium terakreditasi, wajib diterapkan diskon konservatif. | Diterapkan potongan ketidakpastian `karbon.uncertainty_deduction_pct` (default 10%) hingga sertifikat uji lab tersedia. |
| 5 | **Status Hukum Klaim Sertifikasi** | UI menampilkan badge *"SRN-PPI Eligible"*. | **Perpres No. 110/2025 tentang NEK & Permen LHK:** Klaim kelayakan SRN-PPI tanpa registrasi resmi DRAM/SPE-GRK melanggar regulasi dan tergolong *greenwashing*. | Badge diubah menjadi **"Pra-verifikasi (Belum terdaftar SRN-PPI · Perpres 110/2025)"**. |

---

## 4. Daftar Perubahan Kode & File

1. `app/params.py`:
   - Menambahkan `karbon.biochar_moisture_pct` (10.0% default).
   - Menambahkan `karbon.uncertainty_deduction_pct` (10.0% default).
   - Menambahkan `karbon.pyrolysis_ch4_kg_per_t_biochar` (0.0 default).
   - Menambahkan `karbon.lpg_ef_kg_co2e_per_kg` (2.985 kgCO₂e/kg).
2. `app/engines/green_scorecard.py`:
   - Mengubah fungsi `scorecard` untuk menghitung bobot biochar kering.
   - Mengintegrasikan verifikasi `biochar_end_use_kg`.
   - Menghitung Scope 1 BBM dan metana pirolisis.
   - Menerapkan pemisahan `avoided_open_burning` dari `net`.
   - Menambahkan daftar `claim_gaps` transparan di payload respon.
3. `app/services/esg.py`:
   - Menyelaraskan KPI E9, E10, E11, E12 dengan metodologi Puro 2025 dan VM0044.
4. `app/static/app.js`:
   - Menyesuaikan badge status sertifikasi ke "Pra-verifikasi".
5. `tests/test_field_ops.py`:
   - Memperbarui pengujian `test_green_scorecard_uses_real_batches_routes_and_returns` untuk memverifikasi logika kadar air dan end-use.

---

## 5. Hasil Verifikasi Pengujian

Seluruh rangkaian pengujian unit, integrasi, dan kepatuhan audit dijalankan:
- **Total Test:** 487 item
- **Status:** **473 passed, 14 skipped, 0 failed** (100% lulus)
- **Kompatibilitas:** Terverifikasi aman pada SQLite bawaan dan PostgreSQL dengan Row-Level Security (RLS).
