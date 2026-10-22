# 09 — Riset Standar ESG untuk Pabrik Biochar Sekam Padi (Bio-Chain, Sleman)

> Status: riset, belum diimplementasikan. Tanggal akses sumber: **2026-10-11**.
> Tujuan: dasar untuk layar/ekspor **"Laporan ESG"** pabrik dari data yang sudah ada di aplikasi.
> Aturan sumber: hanya sumber primer (regulator, penerbit standar). Kalau fakta hanya ditemukan di sumber sekunder, ditandai **[perlu verifikasi]**.

---

## 1. Ringkasan

1. **Pabrik biochar UKM tidak wajib membuat Laporan Keberlanjutan OJK.** Kewajiban POJK 51/2017 hanya berlaku bagi LJK, Emiten, dan Perusahaan Publik (Pasal 10 ayat 1). Meski begitu, pembeli korporat (emiten), bank (kredit hijau), dan pembeli kredit karbon akan meminta data dengan struktur yang sama: energi, emisi, limbah, keterlibatan pihak lokal, dan pengaduan. Karena itu laporan ESG Bio-Chain sebaiknya **dipetakan ke POJK 51 Lampiran II + GRI + IFRS S2**, supaya datanya bisa langsung dipakai di laporan Scope 3 pelanggan.
2. **Sejak 1 Januari 2027 standar Indonesia = ISSB.** DSK IAI menerbitkan **PSPK 1** (persyaratan umum, setara IFRS S1) dan **PSPK 2** (iklim, setara IFRS S2), efektif 1 Jan 2027. OJK sedang merevisi POJK 51/2017 agar laporan keberlanjutan mengacu ke PSPK. Konsultasi publik ditutup 13 Mar 2026; teks final belum ditemukan per 11 Okt 2026.
3. **Pasar karbon Indonesia sekarang diatur Perpres 110/2025**, yang berlaku 10 Okt 2025 dan mencabut Perpres 98/2021. Registri nasional tetap SRN-PPI. Perdagangan dilakukan di IDXCarbon. Unit dari standar internasional (Verra, Gold Standard, dsb.) boleh diperdagangkan setelah ada persetujuan menteri **[perlu verifikasi: pasal]**.
4. **Ada tiga metodologi biochar yang relevan**, dan ketiganya diperbarui pada 2025–2026:
   - **Puro.earth Biochar Edition 2025 v2** (disetujui 27 Nov 2025): CORC200+, syarat H/Corg < 0,70, faktor persistensi PF = a − b·(H/Corg) yang bergantung pada suhu tanah.
   - **Verra VM0044 v1.2** (Juni 2025): disetujui ICVCM (berlabel CCP) pada Agustus 2025.
   - **Global Biochar C-Sink v3.3** (eks-EBC, berlaku 9 Jun 2026): H/Corg ≤ 0,40 memberi 75% karbon persisten-geologis. Jika juga Ro ≥ 3,8%, porsinya naik ke 90%.
5. **Koreksi konsep penting untuk aplikasi.** Tabel `carbon_credits` saat ini menghitung *avoided emissions* dengan IPCC Tier 2 (substitusi batubara dikurangi transport). Semua standar pelaporan (GRI 102, IFRS S2, GHG Protocol LSR) meminta **tiga angka dilaporkan terpisah**:
   - (a) emisi bruto Scope 1/2/3;
   - (b) *removal* (karbon tersimpan di biochar, dikali faktor persistensi);
   - (c) kredit karbon yang dijual atau dipakai.

   Ketiganya **tidak boleh di-netting** di angka emisi bruto. Angka *net carbon removal* tetap boleh ditampilkan sebagai KPI terpisah.

---

## 2. Regulasi Indonesia

### 2.1 POJK 51/POJK.03/2017 — Penerapan Keuangan Berkelanjutan

| Hal | Isi | Rujukan |
|---|---|---|
| Wajib lapor | LJK, Emiten, Perusahaan Publik wajib menyusun Laporan Keberlanjutan | Pasal 10 (1) |
| Bentuk | Terpisah dari laporan tahunan atau menjadi bagian darinya | Pasal 10 (2) |
| Tenggat | Bersama laporan tahunan. Jika terpisah, paling lambat **30 April** tahun berikutnya | Pasal 10 (3)–(4) |
| Bertahap | Mulai periode 2019 (bank besar) sampai 2025 (dana pensiun ≥ Rp1 T). Emiten aset menengah mulai 2022, emiten aset kecil mulai 2024 | Pasal 10 (6), salinan yang diakses |
| Bahasa | Bahasa Indonesia (boleh berdampingan dengan Inggris) | Lampiran II, I.4 |

**Isi minimum (Lampiran II):**
- strategi keberlanjutan;
- **ikhtisar kinerja 3 tahun**:
  - ekonomi: kuantitas produksi, pendapatan, laba, produk ramah lingkungan, *pelibatan pihak lokal*;
  - lingkungan: energi (listrik & air), pengurangan emisi, pengurangan limbah/efluen, keanekaragaman hayati;
  - sosial;
- profil (termasuk jumlah karyawan per gender/usia/status);
- penjelasan Direksi;
- tata kelola keberlanjutan;
- kinerja keberlanjutan;
- verifikasi independen (jika ada);
- lembar umpan balik.

**Kinerja lingkungan untuk usaha yang terkait langsung dengan lingkungan (Lampiran II huruf e)** — kategori yang cocok untuk pabrik pirolisis:
- jumlah & intensitas energi, serta upaya efisiensi termasuk energi terbarukan;
- jumlah & intensitas emisi per jenis, serta upaya pengurangannya;
- limbah & efluen per jenis, mekanisme pengelolaan, dan tumpahan;
- jumlah & materi pengaduan lingkungan yang diterima dan diselesaikan.

Aspek sosial mencakup mekanisme pengaduan masyarakat dan jumlah pengaduan yang ditindaklanjuti, serta program pemberdayaan (TJSL). Aspek produk mencakup jumlah produk yang ditarik kembali dan alasannya, serta survei kepuasan pelanggan.

**Revisi 2026.** OJK menyusun RPOJK dan RPADK perubahan POJK 51/2017 berdasarkan UU P2SK (UU 4/2023) agar selaras dengan PSPK 1 & 2 (tata kelola, strategi, manajemen risiko, metrik & target, serta tahapan penerapan). Konsultasi publik dibuka Februari 2026 dan tanggapan ditutup **13 Maret 2026**. Per 11 Okt 2026, POJK pengganti belum ditemukan di portal regulasi OJK **[cek ulang sebelum rilis]**.

### 2.2 Standar Pengungkapan Keberlanjutan (SPK) — PSPK 1 & PSPK 2 (DSK IAI)

- **PSPK 1** "Persyaratan Umum Pengungkapan Informasi Keuangan terkait Keberlanjutan" dan **PSPK 2** "Pengungkapan terkait Iklim". Keduanya konvergen dengan IFRS S1 & S2.
- **Efektif 1 Januari 2027.** Peluncuran resmi bersama BI, Kemenkeu, dan OJK pada Agustus 2025. Penerapan dini diperbolehkan **[perlu verifikasi: syarat harus diterapkan bersamaan]**.
- Dampak bagi Bio-Chain: pelanggan emiten wajib melaporkan **Scope 3** (IFRS S2 ¶29(a)). Data per pengiriman dari Bio-Chain (kgCO2e per ton, metodologi GHG Protocol) bisa menjadi data pemasok primer untuk Scope 3 kategori 1 mereka.

### 2.3 Pasar karbon — Perpres 110/2025 (NEK)

- **Judul:** Penyelenggaraan Instrumen Nilai Ekonomi Karbon dan Pengendalian Emisi Gas Rumah Kaca Nasional. Ditetapkan dan diundangkan **10 Okt 2025** (LN 2025 No. 172). Status berlaku. **Mencabut Perpres 98/2021.**
- **Ruang lingkup** (abstrak JDIH BPK): alokasi karbon, penyusunan NDC, tata cara instrumen NEK, kerangka transparansi, monev, pembinaan & pendanaan, serta pembentukan Komite Pengarah.
- **Poin dari sumber sekunder [perlu verifikasi ke teks pasal]:**
  - perdagangan karbon tidak harus menunggu tercapainya target NDC (Pasal 58);
  - unit karbon non-SPE-GRK dari standar internasional dapat diperdagangkan setelah persetujuan menteri terkait (Pasal 63(2));
  - Indonesia telah menandatangani MRA dengan JCM, Gold Standard, GCC, Plan Vivo, dan Verra (2024–2025);
  - sistem lama wajib menyesuaikan dalam 1 tahun, yaitu sampai sekitar 10 Okt 2026.
- **SRN-PPI** tetap menjadi registri. **IDXCarbon** (BEI, diawasi OJK) memulai perdagangan internasional pada 20 Jan 2025. Informasi bahwa POJK 10/2026 mengubah POJK 14/2023 (perdagangan karbon melalui bursa) dan berlaku 6 Jul 2026 **[perlu verifikasi]**.
- **Implikasi.** Kolom `srn_ppi_eligible` di aplikasi hanya penanda internal. Kredit biochar baru menjadi unit yang sah setelah melalui validasi/verifikasi (Puro/Verra/C-Sink, atau SPE-GRK), pencatatan di SRN-PPI, dan persetujuan menteri sesuai Perpres 110/2025.

### 2.4 PROPER (KLH/BPLH)

- Dasar hukum terbaru: **Permen LH/Kepala BPLH No. 7 Tahun 2025**. KLH mensosialisasikan aturan ini pada 5 Nov 2025. Status Permen LHK 1/2021 (aturan sebelumnya) **[perlu verifikasi apakah dicabut]**.
- Peringkat: **Hitam, Merah** (belum taat), **Biru** (taat), **Hijau, Emas** (melampaui ketaatan). Sejak 2025 peringkat Hijau dan Emas diverifikasi lapangan.
- Indikator baru: SML, **LCA**, efisiensi energi & air, pengurangan emisi & limbah, keanekaragaman hayati, pemberdayaan masyarakat. Peringkat Emas juga mensyaratkan eco-innovation, SROI, dan skema NEK dalam model bisnis.
- PROPER 2025 menilai 5.476 perusahaan. KLH menyatakan izin perusahaan berperingkat merah/hitam bisa dicabut. Pabrik kecil biasanya belum menjadi peserta, tetapi indikator PROPER Hijau berguna sebagai kerangka KPI lingkungan.

### 2.5 UU 27/2022 Pelindungan Data Pribadi (UU PDP)

Masa transisi UU PDP berakhir Oktober 2024. Aplikasi sudah punya tabel `consents` (jejak persetujuan append-only) dan `data_requests` (hak subjek data: ekspor/hapus). Untuk laporan ESG (GRI 418-1), yang perlu dilaporkan:
- jumlah pengaduan dan insiden kebocoran data;
- jumlah permintaan subjek data yang dipenuhi beserta waktu penyelesaiannya.

---

## 3. Standar internasional

### 3.1 GRI Standards

| Topik | Disclosure (berlaku) | Catatan 2025–2027 |
|---|---|---|
| Umum | **GRI 2-1** profil organisasi, **2-6** rantai nilai, **2-7** karyawan, **2-8** pekerja non-karyawan, **2-9** tata kelola, **2-23/2-24** kebijakan, **2-25** proses remediasi, **2-26** mekanisme pengaduan, **2-29** pelibatan pemangku kepentingan | — |
| Energi | **302-1** konsumsi energi dalam organisasi, **302-3** intensitas energi, **302-4** pengurangan konsumsi | Diganti **GRI 103: Energy 2025** (terbit Jun 2025, efektif 1 Jan 2027) |
| Emisi | **305-1** Scope 1, **305-2** Scope 2, **305-3** Scope 3, **305-4** intensitas, **305-5** pengurangan, 305-7 NOx/SOx | Diganti **GRI 102: Climate Change 2025** (efektif 1 Jan 2027): 102-1 rencana transisi, 102-2 adaptasi, **102-5** Scope 1, **102-6** Scope 2, **102-7** Scope 3, **102-8** intensitas, **102-9** *removal* GRK di rantai nilai, **102-10** kredit karbon. 305-6/305-7 tetap di GRI 305 |
| Limbah | **306-1** timbulan & dampak, **306-2** pengelolaan, **306-3** limbah dihasilkan, **306-4** dialihkan dari pembuangan, **306-5** dibuang | — |
| Pengadaan | **204-1** proporsi belanja ke pemasok lokal | Dasar KPI % pengadaan lokal/petani kecil |
| Komunitas | **413-1** operasi dengan pelibatan komunitas, penilaian dampak, program pengembangan | — |
| Privasi | **418-1** pengaduan terbukti atas pelanggaran privasi & kehilangan data pelanggan | — |
| Pendukung | 308-1 / 414-1 skrining pemasok (lingkungan/sosial), 403-9 kecelakaan kerja, 416-1 keamanan produk | Opsional |

Catatan: data GHG yang disusun sesuai IFRS S2 dengan metode GHG Protocol dinyatakan memenuhi GRI 102 untuk Scope 1–3 (interoperabilitas GRI–IFRS, Jun 2025) **[perlu verifikasi di dokumen GSSB]**.

### 3.2 GHG Protocol

- **Corporate Standard**:
  - Scope 1 mencakup pembakaran syngas/bio-oil di reaktor, solar genset dan forklift, serta CH4/N2O dari pirolisis.
  - Scope 2 mencakup listrik PLN (faktor grid JAMALI, sudah ada di parameter `karbon.grid_ef_kg_co2_per_kwh`).
  - CO2 biogenik dari pembakaran biomassa dilaporkan **terpisah dari scope** menurut GHG Protocol. Namun staf ISSB (TIG, Mar 2026, makalah AP2) berpandangan bahwa di bawah **IFRS S2**, CO2 biogenik **termasuk** dalam Scope 1/2/3 bruto. Pandangan ini belum final, jadi **simpan kedua angka** (fosil dan biogenik) secara terpisah.
- **Scope 3 Standard** — kategori yang relevan untuk pabrik:
  - **Kat. 1** *purchased goods* (sekam dari petani/pengepul, termasuk emisi pengumpulan di hulu);
  - **Kat. 4** *upstream transportation* (truk penjemputan sekam: `routes.co2e_wtw_kg`, metode ISO 14083, B40);
  - **Kat. 9** *downstream transportation* (pengiriman biochar/bio-silica/pelet ke pembeli);
  - **Kat. 5** *waste generated* (residu, retur yang dibuang);
  - Kat. 3 *fuel & energy related* (WTT solar dan T&D listrik).
- **Land Sector and Removals Standard (LSR)**: v1.0 terbit 30 Jan 2026, **efektif 1 Jan 2027**, v1.1 terbit 30 Jun 2026. Standar ini mengatur pelaporan *removal* CO2 (termasuk removal teknologi) secara terpisah dari emisi, dengan syarat pemantauan persistensi dan risiko pembalikan. Perlakuan biochar secara rinci perlu dicek di bab removal LSR **[perlu verifikasi]**.

### 3.3 IFRS S2 (dan PSPK 2) — metrik inti

- **¶29(a)** emisi GRK bruto absolut Scope 1, 2, 3 (tCO2e).
  - ¶29(a)(ii): diukur dengan GHG Protocol Corporate Standard (kecuali yurisdiksi mewajibkan metode lain).
  - ¶29(a)(vi): kategori Scope 3 yang dicakup; semua 15 kategori dipertimbangkan (B32).
- **¶29(b)–(g)** kategori metrik lintas industri: aset/aktivitas yang rentan risiko transisi & fisik, peluang iklim, pengerahan modal, harga karbon internal, dan remunerasi terkait iklim.
- **¶33–36** target iklim, termasuk penggunaan **kredit karbon** yang direncanakan (jenis: removal/avoidance; skema sertifikasi).
- **Amandemen IFRS S2 (11 Des 2025, efektif 1 Jan 2027)**: keringanan Scope 3 kategori 15 (financed emissions), keringanan yurisdiksi untuk metode pengukuran GRK dan nilai GWP. Tidak ada dampak langsung untuk pabrik, tetapi memengaruhi pelanggan dari sektor keuangan.
- Transisi tahun pertama: Scope 3 boleh belum diungkapkan (keringanan IFRS S2 C4).

---

## 4. Metodologi karbon biochar

### 4.1 Puro.earth — Biochar Methodology Edition 2025 v2 (disetujui 27 Nov 2025)

- **Persamaan utama (Eq. 5.1):** `CORCs = C_stored − C_baseline − C_loss − E_project − E_leakage` (tCO2e).
  - `C_stored` = massa biochar kering × Corg × 44/12 (bagian 6.1).
  - `C_loss` = porsi yang terurai = C_stored × (1 − PF) (bagian 6.2).
  - `E_project` = emisi LCA *cradle-to-grave*: pengumpulan biomassa, transport, energi produksi, CH4/N2O reaktor, aplikasi biochar, dan emisi tertanam peralatan (bagian 7).
  - `E_leakage` = kebocoran pasar/ekologis/pergeseran aktivitas (bagian 8). Contoh: sekam yang sebelumnya dipakai sebagai bahan bakar bata/tembikar.
- **Durabilitas:** dinaikkan menjadi **CORC200+** (≥ 200 tahun, sejalan dengan definisi "permanen" EU CRCF). Sebelumnya cakrawala 100 tahun.
- **Kelayakan:** biochar harus memiliki **H/Corg molar < 0,70** (rule 3.5.x). H/Corg = (H/Corg massa) × 12,0 (Eq. 6.5).
- **Faktor persistensi:** **PF = a − b × (H/Corg)** (Eq. 6.4). Parameter a dan b bergantung pada suhu tanah rata-rata tahunan (kedalaman 5–15 cm, dataset Puro/Lembrechts 2022, wilayah pemakaian pertama, dibulatkan ke atas).
  - Contoh (Tabel 6.1): Ts 26 °C → a = 88,37; b = 40,59. Ts 27 °C → a = 88,18; b = 41,27. Ts 28 °C → a = 87,99; b = 41,91.
  - Ilustrasi: H/Corg 0,30 pada 27 °C menghasilkan PF ≈ 88,18 − 12,38 = **75,8%**.
  - Nilai Ts Sleman **wajib diambil dari dataset Puro**, bukan diasumsikan.
- **Random reflectance (Ro):** sukarela, belum memengaruhi kuantifikasi.
- **Sampling & lab:**
  - Sampel komposit dari *grab sampling* multi-hari, dihomogenkan, dan diarsipkan minimal 2 tahun.
  - **Regime A** (proses termonitor & seragam): minimal 2 analisis per tahun. Untuk proses batch, grab sampling dilakukan harian.
  - **Regime B**: minimal 4 analisis per tahun.
  - Lab terakreditasi ISO 17025.
  - Parameter yang diukur: Corg, H, kadar abu, kadar air, kerapatan curah, kontaminan (PAH, logam berat), serta pengukuran emisi CH4/N2O reaktor (FID/GC/NDIR).
- **Relevansi sekam padi:** kadar abu/SiO2 sekam tinggi, sehingga **Corg harus diukur di lab**. Jangan memakai fixed carbon proksimat (`biochar_fc`) sebagai pengganti Corg. Bio-silica yang diekstraksi dari biochar mengurangi massa biochar yang tersimpan, jadi alokasi co-product (bagian 7.5) perlu diperhatikan.

### 4.2 Verra VM0044 — Biochar Utilization in Soil and Non-Soil Applications

- **Versi berlaku: v1.2** (Juni 2025). Ini revisi minor dari v1.1 yang menambahkan analisis investasi untuk membuktikan additionality. **ICVCM menyetujui VM0044 v1.2 sebagai CCP** (diumumkan 13 Agt 2025). Revisi mayor sedang disiapkan dan dapat mengubah pemantauan H:Corg dan kadar air.
- Permanence dihitung dengan cakrawala **100 tahun** dari massa biochar × Corg × faktor sisa yang ditentukan terutama oleh suhu produksi (dengan syarat H/Corg). Nilai tabel persis untuk v1.2 **[perlu verifikasi di PDF Verra; unduhan diblokir saat riset]**.
- **Rujukan nilai IPCC 2019 Refinement (Vol. 4 Ch. 2 Ap. 4)** — fraksi karbon biochar yang tersisa setelah 100 tahun (F_perm), hanya untuk tanah mineral di lahan pertanian/padang rumput:
  - suhu tinggi > 600 °C: **0,89**;
  - suhu sedang 450–600 °C: **0,80**;
  - suhu rendah 350–450 °C: **0,65**.

  Nilai inilah yang paling dekat dengan pendekatan "IPCC Tier 2" yang sudah dipakai aplikasi. Kolom `conversions.pyrolysis_temp_c` bisa dipakai memilih kelas suhu.

### 4.3 Global Biochar C-Sink Standard (eks-EBC C-Sink) — v3.3

- v3.2 berlaku sejak 15 Nov 2025, **v3.3 berlaku sejak 9 Jun 2026**. Draf V4 dikonsultasikan sampai 30 Apr 2026, dan status adopsinya belum diketahui. Untuk proyek di Uni Eropa, Carbon Standards menyiapkan standar terpisah CS-BCR di bawah Regulasi (EU) 2024/3012 (CRCF) dan Delegated Reg. (EU) 2026/285.
- **Kelas persistensi (untuk aplikasi ke tanah):**

  | Kondisi biochar | GPC (persisten-geologis, > 1000 tahun) | SPC (semi-persisten) |
  |---|---|---|
  | H/Corg ≤ 0,40 | 75% | 25% |
  | H/Corg ≤ 0,40 **dan** Ro ≥ 3,8% atau BC_HyPy ≥ 90% | 90% | 10% |
  | H/Corg > 0,40 | 0% | 100% |

  Istilah PAC diganti GPC di v3.3. SPC (waktu paruh minimum 50 tahun) hanya dapat dipakai sebagai sink sementara, misalnya untuk mengimbangi CH4.
- Emisi CH4 pirolisis wajib dihitung dan diimbangi dengan GWP100 (CH4 biogenik 27,0). Sertifikasi produk dasar mengikuti EBC (analisis H/Corg, Corg, PAH, logam berat).

### 4.4 Ringkasan kuantitas kunci

| Kuantitas | Puro 2025 v2 | VM0044 v1.2 | Global C-Sink v3.3 | IPCC 2019 |
|---|---|---|---|---|
| Ambang H/Corg | < 0,70 | ada (cek tabel) | ≤ 0,40 untuk GPC | — |
| Cakrawala | ≥ 200 tahun | 100 tahun | > 1000 tahun (GPC) | 100 tahun |
| Faktor persistensi | PF = a − b·H/Corg (Ts) | default per suhu produksi | 75% / 90% | 0,65 / 0,80 / 0,89 |
| Ukuran wajib | Corg, H, abu, air, massa kering, CH4/N2O, LCA | Corg, massa, suhu, H:Corg | H/Corg, Corg, (Ro/HyPy), CH4 | suhu, Corg |

---

## 5. Struktur Laporan ESG yang direkomendasikan

### 5.1 Kerangka bab (1–2 halaman ekspor + lampiran)

1. **Profil & batas pelaporan**: periode, fasilitas, kapasitas, jumlah pemasok (GRI 2-1, 2-6; POJK 51 Lampiran II.3).
2. **Ikhtisar 3 periode** (POJK 51 Lampiran II.A.2): produksi, pendapatan, energi, emisi, limbah, pelibatan lokal.
3. **Lingkungan (E)**: neraca massa, energi, emisi GRK bruto (Scope 1/2/3, biogenik terpisah), *removal* biochar, kredit karbon, limbah & retur.
4. **Sosial (S)**: petani kecil, pembayaran, mutu & keamanan produk, pengaduan, K3.
5. **Tata kelola (G)**: privasi data (UU PDP), integritas data (*custody chain*, audit parameter), status verifikasi.
6. **Metodologi & asumsi**: faktor emisi beserta sumber dan versinya (dari `system_parameters`/`parameter_changes`), standar yang dirujuk, serta keterbatasan, misalnya "angka removal belum diverifikasi pihak ketiga".

### 5.2 Tabel KPI

Singkatan sumber data: `INQC` = `inbound_qc`, `HV` = `harvests`, `CONV` = `conversions`, `BO`/`BI`/`BL` = `batch_outputs`/`batch_inputs`/`batch_losses`, `RT` = `routes`, `EN` = `energy_readings`, `CC` = `carbon_credits`, `RC` = `return_cases`, `FP` = `farmer_payments`, `CS` = `consents`, `DR` = `data_requests`, `FGM` = `finished_goods_movements`.

#### E — Lingkungan

| # | KPI | Satuan | Rumus dari data aplikasi | Rujukan standar | Sumber data |
|---|---|---|---|---|---|
| E1 | Sekam diterima (bersih) | ton | Σ `INQC.net_kg`/1000 (alternatif Σ `HV.received_kg`) | POJK 51 L-II A.2.a.1; GRI 301-1 | INQC, HV |
| E2 | Rendemen neraca massa | % | Σ output (biochar + bio-silica + pelet) / Σ input × 100. Selisihnya harus sama dengan Σ `BL.quantity_kg` (air, volatil, susut) | GRI 301-1; Puro §6.1 | BI, BO, BL, CONV |
| E3 | Konsumsi listrik | kWh; GJ | Σ `EN.kwh`; GJ = kWh × 0,0036 | GRI 302-1 / 103 (2027); POJK L-II d.3.a | EN |
| E4 | Intensitas energi | kWh/t biochar | E3 / Σ biochar_ton | GRI 302-3; POJK d.3.a | EN, CONV |
| E5 | Emisi Scope 1 (fosil) | tCO2e | Σ solar genset/forklift × EF B40 + CH4/N2O reaktor × GWP (jika diukur) | IFRS S2 ¶29(a)(i); GRI 305-1 / 102-5 | parameter, meter |
| E5b | CO2 biogenik (syngas/bio-oil dibakar) | tCO2e | C volatil dibakar × 44/12. **Dilaporkan terpisah** | GHG Protocol Ch.9; ISSB TIG AP2 (2026) | BL (`gas_pembakaran`, `volatil_syngas`) |
| E6 | Emisi Scope 2 | tCO2e | E3 × `karbon.grid_ef_kg_co2_per_kwh` / 1000 | IFRS S2 ¶29(a); GRI 305-2 / 102-6 | EN, params |
| E7 | Scope 3 kat. 4 — transport sekam masuk | tCO2e | Σ `RT.co2e_wtw_kg`/1000 (ISO 14083 WTW, B40) | GHG Protocol S3 Cat 4; GRI 305-3 / 102-7 | RT |
| E8 | Scope 3 kat. 9 — distribusi produk | tCO2e | Σ jarak × ton × EF t·km pada pengiriman keluar | GHG Protocol S3 Cat 9 | FGM, RT |
| E9 | Intensitas emisi per ton sekam | kgCO2e/t sekam | (E5 + E6 + E7) × 1000 / E1 | GRI 305-4 / 102-8; POJK e.4.a | turunan |
| E10 | Intensitas emisi per ton biochar | kgCO2e/t biochar | (E5 + E6 + E7 + E8) × 1000 / Σ biochar_ton | GRI 305-4 / 102-8 | turunan |
| E11 | Karbon tersimpan bruto | tCO2e | Σ massa biochar kering × Corg(lab) × 44/12 | Puro Eq. 5.1 C_stored | CONV + hasil lab |
| E12 | Removal durabel | tCO2e | E11 × PF. PF = Puro (a − b·H/Corg) **atau** IPCC F_perm per kelas suhu (`pyrolysis_temp_c`). Pilihan metode dicantumkan | Puro §6.2; IPCC 2019 Ap.4; GRI 102-9 | CONV, lab |
| E13 | **Net carbon removal** | tCO2e | E12 − (E5 + E5b-CH4 + E6 + E7 + E8 + emisi aplikasi) − leakage. Tidak di-netting ke E5–E8 | Puro Eq. 5.1; GHG Protocol LSR | turunan |
| E14 | Emisi dihindari (substitusi batubara) | tCO2e | `CC.emission_avoided_tco2`. Diberi label **avoided**, bukan removal | IPCC 2006 Tier 2; GRI 305-5 | CC |
| E15 | Kredit karbon terbit / dijual / dipensiunkan | tCO2e | per status verifikasi (`CC.verified`), standar, registri (SRN-PPI) | GRI 102-10; IFRS S2 ¶36(e) | CC |
| E16 | Limbah & residu | t; % | Σ `BL` residu_ekstraksi + karung tolak (`INQC.rejected_kg`), dipilah dialihkan vs dibuang | GRI 306-3/4/5; POJK e.5 | BL, INQC |
| E17 | Rasio retur produk | % | Σ kg retur / Σ kg terkirim × 100, menurut `RC` alasan & disposisi | GRI 306-4; POJK f.4 | RC, FGM |
| E18 | Utilisasi muatan truk | % | rata-rata `RT.utilization_pct` | ISO 14083 (efisiensi) | RT |

#### S — Sosial

| # | KPI | Satuan | Rumus | Rujukan | Sumber |
|---|---|---|---|---|---|
| S1 | Jumlah petani kecil pemasok aktif | orang | COUNT DISTINCT `HV.farmer_id` dengan received_kg > 0 dalam periode | GRI 2-6; POJK A.2.a.5 | HV |
| S2 | **% pengadaan dari petani kecil lokal** | % (nilai Rp) | Σ Rp ke pemasok di Kab. Sleman/DIY / Σ total belanja sekam × 100 | **GRI 204-1** | FP, INQC, `mills.kabupaten` |
| S3 | Total pembayaran ke petani | Rp | Σ `FP.net_rp` (dan gross, pajak) | GRI 201-1 (nilai ekonomi didistribusikan) | FP |
| S4 | **Pembayaran tepat waktu** | % | COUNT(`FP.paid_at` − waktu verifikasi harvest ≤ SLA hari) / COUNT(FP) × 100. SLA dijadikan parameter | GRI 204 (praktik pengadaan); POJK sosial | FP, HV |
| S5 | Median hari bayar | hari | median(`paid_at` − verifikasi) | — | FP, HV |
| S6 | Pembayaran non-tunai | % | COUNT(method ∈ transfer/qris/ewallet) / COUNT × 100 | POJK (inklusi keuangan) | FP |
| S7 | Biochar dikembalikan ke petani | kg; % | Σ `CONV.allocated_biochar_kg`; penebusan dari `biochar_redemptions` | GRI 413-1 (program komunitas) | CONV, circular |
| S8 | Tingkat tolak/defect mutu masuk | % | Σ `INQC.rejected_kg` / Σ `gross_kg` × 100, dirinci per `HV.reject_category` | GRI 308-2 (proxy); internal QC | INQC, HV |
| S9 | Selisih timbang (susut) | % | Σ `HV.shrinkage_kg` / Σ `verified_kg`; jumlah `discrepancy_flag` | integritas rantai pasok | HV |
| S10 | Batch produk lolos spesifikasi | % | batch sesuai spek / total batch | GRI 416-1 | BO, lab |
| S11 | Pengaduan masyarakat/lingkungan diterima & diselesaikan | jumlah | dari modul feedback | GRI 2-25/2-26; POJK e.6, sosial 3.b | `services/feedback` |
| S12 | Kecelakaan kerja | jumlah; LTIFR | log K3 (belum ada → *gap*) | GRI 403-9 | — |

#### G — Tata kelola

| # | KPI | Satuan | Rumus | Rujukan | Sumber |
|---|---|---|---|---|---|
| G1 | Cakupan persetujuan data aktif | % | pengguna dengan consent `layanan_inti` granted terbaru / pengguna aktif × 100; rincian `method` (aplikasi/lisan/tertulis) | UU PDP Pasal 20–22; GRI 418 | CS |
| G2 | Permintaan hak subjek data dipenuhi | jumlah; hari | COUNT `DR` per kind, % selesai, rata-rata hari | UU PDP Pasal 5–11 | DR |
| G3 | **Insiden privasi/kebocoran data** | jumlah | insiden tercatat + pengaduan terbukti (target 0) | **GRI 418-1**; UU PDP Pasal 46 (notifikasi 3×24 jam) | log insiden (*gap*) |
| G4 | Ketertelusuran (*custody*) | % | ton biochar yang punya rantai `custody_events` lengkap / total × 100 | Puro §3.8 (cegah hitung ganda); GRI 2-6 | ledger |
| G5 | Perubahan parameter emisi teraudit | jumlah | COUNT `parameter_changes` periode, dengan alasan & pengubah | IFRS S1 (penilaian & estimasi) | params |
| G6 | Status verifikasi pihak ketiga | teks | lab terakreditasi (ISO 17025) / VVB / standar (Puro/Verra/C-Sink) | POJK L-II A.7; IFRS S2 ¶36 | manual |
| G7 | Kesiapan regulasi | checklist | PROPER (peserta/tidak), NIB/izin lingkungan, SRN-PPI | Permen LH 7/2025; Perpres 110/2025 | manual |

### 5.3 Aturan tampilan yang disarankan

- Tampilkan **tiga blok terpisah**: "Emisi bruto", "Removal biochar", "Kredit karbon". Jangan menampilkan satu angka "netral karbon" tanpa rincian (GRI 102-10, IFRS S2).
- Setiap angka removal diberi lencana status:
  - **Estimasi**: lab belum ada, memakai default IPCC;
  - **Terukur**: lab ISO 17025;
  - **Terverifikasi**: VVB.
- Bandingkan 3 periode (POJK 51) dan cantumkan versi faktor emisi pada periode itu.
- Ekspor CSV per pengiriman untuk pelanggan, berisi kgCO2e/ton dan metode. Data ini mendukung Scope 3 pelanggan berdasarkan PSPK 2.

---

## 6. Catatan perubahan 2025–2026

| Tanggal | Perubahan | Dampak ke Bio-Chain |
|---|---|---|
| 1 Jan 2025 | Mandatori B40 (Kepmen ESDM 341.K/2024) | Sudah dipakai di faktor emisi transport |
| 20 Jan 2025 | Perdagangan karbon internasional perdana di IDXCarbon | Jalur jual kredit domestik |
| Jun 2025 | GRI 102 Climate Change & GRI 103 Energy terbit (efektif 2027), menggantikan GRI 305 (GHG) & 302 | Petakan KPI ke nomor baru: 102-5…102-10 |
| 27 Jun 2025 | Verra VM0044 v1.2 (additionality, analisis investasi) | — |
| Jun–Agt 2025 | DSK IAI mengesahkan PSPK 1 & 2 (efektif 1 Jan 2027); peluncuran resmi Agt 2025 | Pelanggan emiten akan meminta data Scope 3 |
| 13 Agt 2025 | ICVCM menyetujui VM0044 v1.2 (CCP) | Kredit biochar Verra berlabel CCP |
| 10 Okt 2025 | **Perpres 110/2025** menggantikan Perpres 98/2021 | Rujukan regulasi karbon di aplikasi perlu diperbarui |
| Nov 2025 | Permen LH/BPLH 7/2025 (PROPER baru, verifikasi lapangan Hijau/Emas, LCA) | Kerangka KPI lingkungan |
| 15 Nov 2025 | Global Biochar C-Sink v3.2 berlaku | — |
| 27 Nov 2025 | **Puro Biochar Edition 2025 v2**: CORC200+, PF = a − b·H/Corg | Rumus E12 versi Puro |
| 11 Des 2025 | Amandemen IFRS S2 (GHG; efektif 2027) | Kecil untuk pabrik |
| 30 Jan 2026 | GHG Protocol LSR Standard v1.0 (efektif 2027); v1.1 pada 30 Jun 2026 | Removal dilaporkan terpisah dari emisi |
| Feb–Mar 2026 | Konsultasi publik RPOJK perubahan POJK 51/2017 (ditutup 13 Mar 2026) | Pantau terbitnya POJK baru |
| Mar 2026 | ISSB TIG AP2: CO2 biogenik termasuk dalam Scope 1–3 bruto (pandangan staf) | Simpan CO2 biogenik terpisah, siap dijumlahkan |
| 9 Jun 2026 | Global Biochar C-Sink v3.3 (PAC → GPC; Ro ≥ 3,8% kelas atas) | — |
| Jul 2026 | POJK 10/2026 mengubah POJK 14/2023 (bursa karbon) **[perlu verifikasi]** | — |
| Agt–Sep 2026 | Konsultasi CS-BCR (EU CRCF biochar) | Relevan jika ekspor kredit ke UE |

---

## 7. Daftar pustaka (diakses 2026-10-11)

**Regulasi Indonesia**
1. OJK — POJK 51/POJK.03/2017 Penerapan Keuangan Berkelanjutan. https://ojk.go.id/id/regulasi/Pages/Penerapan-Keuangan-Berkelanjutan-bagi-Lembaga-Jasa-Keuangan,-Emiten,-dan-Perusahaan-Publik.aspx (salinan teks yang dibaca: https://aaui.or.id/wp-content/uploads/2025/10/POJK-51-2017-KEUANGAN-BERKELANJUTAN.pdf)
2. OJK — Konsultasi Publik atas Perubahan POJK 51/2017 (Feb 2026). https://keuanganberkelanjutan.ojk.go.id/keuanganberkelanjutan/ArticleList/View/2049/otoritas-jasa-keuangan-gelar-konsultasi-publik-atas-perubahan-pojk-51-2017-tentang-penerapan-keuangan-berkelanjutan-bagi-lembaga-jasa-keuangan-emiten-dan-perusahaan-publik
3. IAI — Standar Pengungkapan Keberlanjutan Efektif per 1 Januari 2027. https://web.iaiglobal.or.id/Berita-IAI/detail/standar_pengungkapan_keberlanjutan_efektif_per_1_januari_2027
4. IAI — DSK IAI Sahkan PSPK 1 dan PSPK 2. https://web.iaiglobal.or.id/Berita-IAI/detail/dsk_iai_sahkan_standar_pengungkapan_keberlanjutan_pspk_1_dan_pspk_2
5. JDIH BPK — Perpres No. 110 Tahun 2025. https://peraturan.bpk.go.id/Details/334733/perpres-no-110-tahun-2025
6. JDIH Kemenko Infra — Perpres No. 110 Tahun 2025. https://jdih.kemenkoinfra.go.id/perpres-no-110-tahun-2025
7. KLH/BPLH — Sosialisasi aturan PROPER terbaru (5 Nov 2025). https://kemenlh.go.id/news/detail/klhbplh-sosialisasikan-aturan-proper-terbaru-dorong-industri-melampaui-ketaatan-lingkungan
8. KLH/BPLH — 5.476 perusahaan dipantau lewat PROPER 2025. https://kemenlh.go.id/news/detail/5476-perusahaan-dipantau-lewat-proper-2025-untuk-perkuat-perlindungan-lingkungan-industri-di-daerah-aliran-sungai-das-menjadi-prioritas

**Standar internasional**

9. GRI — GRI 102: Climate Change 2025. https://www.globalreporting.org/publications/documents/english/gri-102-climate-change-2025/
10. GRI Standards (GRI 2, 204, 302, 305, 306, 413, 418). https://www.globalreporting.org/standards/
11. IFRS Foundation — Amendments to IFRS S2 (ISSB 2025-1). https://www.ifrs.org/content/dam/ifrs/publications/amendments/english/2025/issb-2025-1-amendments-ifrs-s2.pdf
12. IFRS Foundation — IFRS S2 Illustrative Guidance. https://www.ifrs.org/content/dam/ifrs/publications/html-standards-issb/english/2023/issued/issbs2-ag.html
13. IFRS Foundation — TIG Staff Paper AP2 "Biogenic emissions applying IFRS S2" (Mar 2026). https://www.ifrs.org/content/dam/ifrs/meetings/2026/march/tig/ap2-biogenic-emissions-applying-ifrs-s2.pdf
14. GHG Protocol — Land Sector and Removals Standard v1.0 (Jan 2026). https://ghgprotocol.org/sites/default/files/2026-01/Land-Sector-and-Removals-Standard.pdf ; v1.1: https://ghgprotocol.org/sites/default/files/2026-06/Land-Sector-and-Removals-Standard-v1.1.pdf
15. GHG Protocol — Corporate Standard & Scope 3 Standard. https://ghgprotocol.org/standards

**Metodologi biochar**

16. Puro.earth — Biochar Methodology Edition 2025 v2 (Approved 27 Nov 2025). https://7518557.fs1.hubspotusercontent-na1.net/hubfs/7518557/Puro%20Biochar%20Methodology%20-%20Edition%202025%20(version%202)%20-%20For%20Publication.pdf
17. Puro.earth — Advancing the Science of Biochar Permanence. https://puro.earth/insights/post/biochar-permanence/
18. Verra — VM0044 Methodology for Biochar Utilization v1.1 (PDF). https://verra.org/wp-content/uploads/2023/07/VM0044-Methodology-for-Biochar-Utilization-in-Soil-and-Non-Soil-Applications-v1.1.pdf
19. Verra — Verra Publishes Minor Revision to Biochar Methodology (v1.2). https://verra.org/verra-publishes-minor-revision-to-biochar-methodology/
20. Verra — Revision to VM0044. https://verra.org/methodologies/revision-to-vm0044-methodology-for-biochar-utilization-in-soil-and-non-soil-applications/
21. ICVCM — Integrity Council approves Biochar & IFM methodologies. https://icvcm.org/integrity-council-approves-biochar-amp-improved-forest-management-methodologies/
22. Ithaka Institute / Carbon Standards — Global Biochar C-Sink Standard v3.3 (9 Jun 2026). https://www.carbon-standards.com/docs/transfer/4000039EN.pdf
23. Carbon Standards — Global Biochar C-Sink (halaman layanan, V4, CS-BCR). https://www.carbon-standards.com/en/standards/service-501~global-biochar-c-sink.html
24. IPCC — 2019 Refinement, Vol. 4 Ch. 2 Appendix 4 (Biochar). https://www.ipcc-nggip.iges.or.jp/public/2019rf/pdf/4_Volume4/19R_V4_Ch02_Ap4_Biochar.pdf

**Catatan verifikasi:** butir bertanda **[perlu verifikasi]** bersumber dari ringkasan sekunder atau dokumen primer yang tidak bisa diunduh saat riset (PDF Verra v1.2, teks pasal Perpres 110/2025). Butir tersebut harus dicek ke teks resmi sebelum dipakai di laporan yang dipublikasikan.
