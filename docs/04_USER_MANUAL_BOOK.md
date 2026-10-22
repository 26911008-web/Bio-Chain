# 📖 Buku Panduan Pengguna (User Manual Book)
## Bio-Chain v2.4 — Hardened Circular Bioeconomy Supply Chain
*Panduan Operasional Lengkap untuk Petani, Pengepul, Driver, Pabrik, dan Administrator*
**Klasifikasi:** Manual Operasional Produksi & Protokol Lapangan Industri

---

## DAFTAR ISI
1. [BAB 1: Pengenalan & Petunjuk Memulai Cepat](#bab-1-pengenalan--petunjuk-memulai-cepat)
2. [BAB 2: Panduan Peran Petani (🌾)](#bab-2-panduan-peran-petani-)
   - 2.1 Pendaftaran Multi-Biomassa & Parameter Mutu Awal
   - 2.2 Dua Jalur Penjualan: Direct Price vs Bursa Lelang
   - 2.3 Program Penebusan Biochar Muatan Balik (Backhaul Redemption)
   - 2.4 Transparansi Rincian Refraksi Kadar Air ("Potongan Air")
   - 2.5 Pemantauan Status Batch, QR Code & XP Gamifikasi
3. [BAB 3: Panduan Peran Pengepul / KUD (📦)](#bab-3-panduan-peran-pengepul--kud-)
   - 3.1 Antrean Verifikasi & Uji Mutu Multi-Biomassa
   - 3.2 Kalkulasi Refraksi Deviasi & Penetapan Grade Mutu
   - 3.3 Gudang Pengepul sebagai Decoupling Buffer Hub Biochar
   - 3.4 Konsolidasi Rute & Manajemen Arus Kas Talangan Petani
4. [BAB 4: Panduan Peran Driver Armada Logistik (🚛)](#bab-4-panduan-peran-driver-armada-logistik-)
   - 4.1 Validasi Dual Limit CDD: Kubikasi (30 m³) vs Tonase (5 Ton) Bebas ODOL
   - 4.2 Prosedur Logistik Sirkular: Dropping Biochar & Pemuatan Biomassa
   - 4.3 Verifikasi Checkpoint QR Code & Anti-Pemalsuan HMAC
   - 4.4 Operasional Mode Offline di Blank Spot Persawahan
5. [BAB 5: Panduan Peran Pabrik Pirolisis & Bioenergi (🏭)](#bab-5-panduan-peran-pabrik-pirolisis--bioenergi-)
   - 5.1 Prosedur Jembatan Timbang (Weighbridge Metrology: Gross - Tare = Net)
   - 5.2 Evaluasi Susut Alami & Threshold Deviasi 3.0%
   - 5.3 Penerbitan Slip Timbangan Digital & Cetak Thermal Ber-QR
   - 5.4 Otomatisasi Settlement Saldo Rekening
   - 5.5 Solver Blending Reaktor (HiGHS) & Sertifikasi Karbon ESG
6. [BAB 6: Panduan Administrator & SRE Konsorsium (⚙️)](#bab-6-panduan-administrator--sre-konsorsium-️)
   - 6.1 Pemantauan Invarian Integritas & Optimistic Locking (CAS)
   - 6.2 Audit Trail Forensik & Row-Level Security (RLS)
   - 6.3 Manajemen Parameter Dinamis (Master Registry)
7. [BAB 7: Panduan Pengoperasian IoT Lapangan & Printer Thermal](#bab-7-panduan-pengoperasian-iot-lapangan--printer-thermal)
8. [BAB 8: FAQ & Troubleshooting Lapangan](#bab-8-faq--troubleshooting-lapangan)

---

## BAB 1: Pengenalan & Petunjuk Memulai Cepat

Bio-Chain v2.4 adalah platform agritech sirkular generasi baru yang menghubungkan rantai pasok biomassa pertanian (sekam padi, tongkol jagung, ampas tebu, serbuk kayu, limbah kelapa) menjadi produk bernilai tinggi (biochar penyubur tanah, bahan bakar boiler, dan kredit karbon tersertifikasi).

### 1.1 Persyaratan Sistem
- **Sistem Operasi**: Windows 10/11, macOS, atau Linux (Ubuntu 22.04+).
- **Runtime**: Python 3.10+ (Direkomendasikan Python 3.12 atau 3.14) & Node.js 18+ (untuk tooling asset).
- **Peramban**: Google Chrome, Microsoft Edge, Safari, atau Mozilla Firefox (Mendukung Kamera untuk pemindai QR Code).

### 1.2 Cara Menjalankan Aplikasi
```bash
# Menjalankan server lokal FastAPI
py -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Aplikasi dapat diakses melalui peramban di `http://127.0.0.1:8000`.

### 1.3 Akses Akun Demo 1-Klik
Halaman login menyediakan 5 kartu persona instan:
- 🌾 **Petani**: `petani_sugeng` / `sekam123`
- 📦 **Pengepul**: `pengepul_sleman` / `kud2026`
- 🚛 **Driver**: `sopir_budi` / `truk2026`
- 🏭 **Pabrik**: `pabrik_indmira` / `pabrik2026`
- ⚙️ **Admin**: `admin` / `admin2026`

---

## BAB 2: Panduan Peran Petani (🌾)

Portal Petani dirancang dengan estetika modern, kontras tinggi, dan antarmuka ramah pengguna (*mobile-friendly*) untuk pelaporan cepat di tengah persawahan.

```
+---------------------------------------------------------------------------------------------------+
|                                     ALUR PELAPORAN PETANI                                         |
+---------------------------------------------------------------------------------------------------+
|  1. Pilih Biomassa (Sekam / Jagung / Serbuk) & Estimasi Bobot (kg)                                |
|  2. Input Hasil Uji Lapangan: Kadar Air (%), Kebersihan / Kontaminan (%)                          |
|  3. PILIH JALUR TRANSAKSI:                                                                        |
|       ├─ [MODE 1: DIRECT PRICE] ──> Harga Katalog Tetap, Kepastian Tunai Instan                   |
|       └─ [MODE 2: BURSA LELANG] ──> Set Batas Minimum (Reserve Price), Lelang 48 Jam Multi-Buyer  |
|  4. OPSI: Centang "Tukar Muatan Balik Biochar" (Gratis Ongkir Rute Truk)                          |
|  5. Terbitkan Batch & Dapatkan TIKET QR RESMI (HMAC-SHA256)                                       |
+---------------------------------------------------------------------------------------------------+
```

### 2.1 Pendaftaran Multi-Biomassa & Parameter Mutu Awal
1. Buka dashboard Petani, pilih panel **"🌾 Lapor Stok Biomassa"**.
2. Pilih jenis komoditas pada dropdown:
   - **Sekam Padi** (Kadar air referensi: 12%, Bulk density: 120 kg/m³)
   - **Tongkol Jagung** (Kadar air referensi: 15%, Bulk density: 200 kg/m³)
   - **Ampas Tebu / Bagasse** (Kadar air referensi: 50%, Bulk density: 120 kg/m³)
   - **Tempurung Kelapa** (Kadar air referensi: 12%, Bulk density: 425 kg/m³)
   - **Sabut Kelapa** (Kadar air referensi: 15%, Bulk density: 85 kg/m³)
   - **Serbuk Kayu Sengon / Karet** (Kadar air referensi: 30%, Bulk density: 200–230 kg/m³)
3. Masukkan **Estimasi Kuantitas (kg)** (misal: 3.500 kg).
4. Masukkan **Kadar Air (%)** hasil pengukuran probe tusuk dan **Tingkat Kebersihan** (foto tumpukan opsional).

### 2.2 Dua Jalur Penjualan: Direct Price vs Bursa Lelang
Petani memiliki kendali penuh atas cara menjual panennya:
- **Jalur A: Direct Price (Harga Tetap Katalog)**:
  - Mengikuti harga acuan pasar harian (misal: Rp 450/kg untuk Sekam Grade A).
  - Pembayaran terjamin cair instan saat penjemputan oleh pengepul/driver. Sangat disarankan bagi petani yang membutuhkan likuiditas tunai di hari panen untuk upah buruh tani.
- **Jalur B: Bursa Lelang (Open Auction Marketplace)**:
  - Masukkan **Harga Dasar Minimum (Reserve Price)** (misal: Rp 470/kg).
  - Tentukan durasi lelang (12, 24, atau 48 jam).
  - Tawaran masuk secara real-time dari berbagai pembeli pabrik. Sistem dilengkapi proteksi *anti-sniping* (perpanjangan waktu 5 menit otomatis jika ada penawaran baru di detik-detik akhir).

### 2.3 Program Penebusan Biochar Muatan Balik (Backhaul Redemption)
Petani dapat menukar poin panen atau saldo hasil penjualan biomassa dengan produk biochar untuk memperbaiki pH dan kesuburan tanah:
1. Centang opsi **"Tebus Biochar Muatan Balik"**.
2. Masukkan kuantitas karung biochar yang diinginkan (misal: 20 karung @ 25 kg = 500 kg).
3. **Keuntungan**: Truk logistik yang menjemput sekam akan membawa biochar langsung dari pabrik (*zero extra shipping fee*).
4. **Fleksibilitas Pengambilan**: Jika sawah belum masuk jadwal bajak tanah, petani dapat memilih opsi **"Simpan di Gudang Pengepul"** agar biochar tetap kering dan aman dari hujan.

### 2.4 Transparansi Rincian Refraksi Kadar Air ("Potongan Air")
Jika kadar air aktual melampaui batas referensi, sistem menerapkan formula refraksi kontinu:
$$W_{\text{net}} = W_{\text{actual}} \times \left( \frac{100 - \text{MC}_{\text{actual}}}{100 - \text{MC}_{\text{ref}}} \right)$$
Aplikasi tidak memotong timbangan secara sepihak. Pada notifikasi dan slip digital petani tertera rincian:
- **Bobot Timbang Kotor**: 5.000 kg
- **Kadar Air Aktual**: 17,5% (Batas standar: 14,0%)
- **Potongan Air**: 203,49 kg (Kadar air berlebih yang diuapkan di reaktor)
- **Bobot Bersih Kering Dasar**: 4.796,51 kg
- **Total Pembayaran**: Dihitung transparan dari bobot bersih.

### 2.5 Pemantauan Status Batch, QR Code & XP Gamifikasi
- Setiap laporan menerbitkan **QR Code Tamper-Evident** unik berformat `BIO-XXXXXX`.
- Tiket QR ini memuat tanda tangan HMAC-SHA256 yang dapat diverifikasi oleh driver secara offline.
- Petani memperoleh poin **XP Gamifikasi** untuk setiap batch biomassa dengan kualitas bersih dan kering (Grade A), yang meningkatkan level keanggotaan (Perunggu $\to$ Perak $\to$ Emas) dengan insentif tambahan hingga +Rp 25/kg.

---

## BAB 3: Panduan Peran Pengepul / KUD (📦)

Pengepul berfungsi sebagai agregator lokal, penjamin kualitas (*quality gatekeeper*), serta penyedia modal talangan panen di tingkat pedesaan.

### 3.1 Antrean Verifikasi & Uji Mutu Multi-Biomassa
1. Masuk ke dashboard Pengepul (misal: KUD Sleman).
2. Panel **"📋 Antrean Verifikasi Lapangan"** menampilkan seluruh listing petani di wilayah binaan.
3. Klik tombol **"🔍 Uji Mutu & Verifikasi"** pada batch yang hendak diperiksa.

### 3.2 Kalkulasi Refraksi Deviasi & Penetapan Grade Mutu
1. Masukkan hasil pembacaan parameter proksimat:
   - Kadar Air (MC) %
   - Kadar Abu (Ash) %
   - Kontaminasi Kotoran % (tanah, kerikil, tali rafia)
2. Sistem otomatis menghitung skor kualitas (0–100) dan menentukan grade:
   - **Grade A**: Kadar air $\le 12\%$, kontaminan $\le 1\%$ (Insentif penuh + bonus).
   - **Grade B**: Kadar air $12 - 14\%$, kontaminan $\le 2\%$ (Harga standar).
   - **Grade C**: Kadar air $14 - 18\%$ (Dikenakan refraksi potongan air proporsional).
   - **Tolak**: Kadar air $> 20\%$ atau kontaminan $> 5\%$ (Beresiko merusak boiler/reaktor).
3. Status batch berubah menjadi `VERIFIED` dan otomatis siap dikonsolidasikan ke rute armada.

### 3.3 Gudang Pengepul sebagai Decoupling Buffer Hub Biochar
- Pengepul menyediakan ruang gudang berpalet kayu kering untuk menampung drop-off biochar muatan balik dari truk pabrik.
- Biochar disimpan aman dari paparan hujan tropis, dan baru disalurkan kepada petani saat kelompok tani (Poktan) memasuki fase **Olah Tanah (Bajak Singkal/Rotari)**.
- Pengepul menerima komisi jasa penyimpanan dan distribusi pupuk biochar per kilogram.

### 3.4 Konsolidasi Rute & Manajemen Arus Kas Talangan Petani
- Panel **"Pencairan Dana Petani"** mencatat transaksi talangan instan yang dibayarkan pengepul kepada petani.
- Panel **"Piutang Pabrik"** melacak invoice konsolidasi tonase yang telah diserahkan ke jembatan timbang pabrik, lengkap dengan estimasi tanggal jatuh tempo pembayaran transfer industri.

---

## BAB 4: Panduan Peran Driver Armada Logistik (🚛)

Portal Driver membantu pengemudi truk logistik menjalankan rute penjemputan, memverifikasi serah-terima biomassa, dan menjamin keselamatan berkendara bebas pelanggaran ODOL.

```
+---------------------------------------------------------------------------------------------------+
|                            ALUR KERJA HARIAN DRIVER BIOCHAIN                                      |
+---------------------------------------------------------------------------------------------------+
|  1. Buka Manifest Rute di Aplikasi PWA (Tersedia Mode Offline)                                     |
|  2. Muat Biochar Outbound dari Pabrik (Misal: 1.200 kg / 4 m3)                                     |
|  3. Berangkat ke Titik Penjemputan Sawah / Pengepul:                                              |
|       ├─ Stop 1: Turunkan Biochar Pesanan Petani A -> Ruang Bak Kosong                             |
|       ├─ Stop 1: Muat Sekam Petani A -> Scan QR Tiket Petani -> Input Timbangan Saung             |
|       ├─ Stop 2: Muat Biomassa Petani B -> Scan QR Tiket Petani -> Validasi Batas Bak Truk        |
|  4. Pastikan Beban Truk: Volume <= 30 m3 & Berat <= 5.000 kg (Bebas Razia ODOL)                   |
|  5. Tiba di Pabrik -> Masuk Jembatan Timbang (Timbang Kotor & Timbang Kosong)                     |
+---------------------------------------------------------------------------------------------------+
```

### 4.1 Validasi Dual Limit CDD: Kubikasi (30 m³) vs Tonase (5 Ton) Bebas ODOL
Armada truk utama adalah **Colt Diesel Double (CDD 6 Roda)** dengan spesifikasi legal:
- **Kapasitas Tonase Muatan Bersih**: Maksimal $5.000\text{ kg}$ (JBI $7.500\text{ kg} - \text{Kosong } 2.500\text{ kg}$).
- **Kapasitas Volume Bak Modifikasi**: Maksimal $28 - 30\text{ m}^3$ (Tinggi muatan tidak boleh melampaui $3,2\text{ meter}$).

**Perlindungan Algoritma Sistem**:
- Saat membawa sekam padi curah ($\rho \approx 110\text{ kg/m}^3$), sistem membatasi muatan pada volume $30\text{ m}^3$ (sekitar $3.300\text{ kg}$), menolak penambahan order sekam yang membuat muatan menjulang berbahaya.
- Saat membawa komoditas padat seperti cangkang sawit ($\rho \approx 600\text{ kg/m}^3$), sistem membatasi muatan pada berat $5.000\text{ kg}$ meskipun bak masih terlihat kosong dua pertiga.
- **Hasil**: Sopir aman dari sanksi tilang jembatan timbang Dishub dan terlindung dari resiko truk terbalik di jalanan pedesaan yang sempit.

### 4.2 Prosedur Logistik Sirkular: Dropping Biochar & Pemuatan Biomassa
1. Driver memulai rute dari pabrik dengan membawa muatan outbound biochar.
2. Di titik perhentian pertama, driver menurunkan karung biochar pesanan petani/pengepul terlebih dahulu.
3. Penurunan biochar membebaskan volume ruang bak truk, sehingga biomassa baru dapat langsung dimuat ke atas bak tanpa kekurangan kapasitas.
4. Efisiensi rute sirkular mencapai penghematan biaya bahan bakar solar hingga $32,4\%$ dibandingkan truk kosong (*empty backhaul*).

### 4.3 Verifikasi Checkpoint QR Code & Anti-Pemalsuan HMAC
1. Di setiap lokasi muat, driver meminta petani menunjukkan kode QR tiket panen.
2. Driver menekan tombol **"📷 Scan QR Petani"** pada aplikasi driver.
3. Sistem memverifikasi keaslian tiket:
   - Validitas cryptographic signature HMAC-SHA256.
   - Status batch harus `VERIFIED` dan belum pernah dimuat oleh sopir lain.
4. Driver memasukkan berat timbangan saung dan konfirmasi pengambilan. Status batch seketika berubah menjadi `IN_TRANSIT`.

### 4.4 Operasional Mode Offline di Blank Spot Persawahan
- Jika penjemputan dilakukan di area blank spot tanpa sinyal internet seluler:
  - Aplikasi secara otomatis beralih ke **Mode Offline PWA**.
  - Manifest rute, daftar perhentian, dan algoritma verifikasi QR tetap berfungsi penuh melalui penyimpanan lokal *IndexedDB*.
  - Begitu kendaraan kembali ke jalan raya yang memiliki sinyal 4G, antrean transaksi offline otomatis tersinkronisasi (*background sync*) ke server pusat.

---

## BAB 5: Panduan Peran Pabrik Pirolisis & Bioenergi (🏭)

Portal Pabrik memberikan kontrol komprehensif terhadap penerimaan jembatan timbang, audit deviasi susut perjalanan, optimasi pakan reaktor pirolisis, dan sertifikasi kredit karbon ESG.

### 5.1 Prosedur Jembatan Timbang (Weighbridge Metrology)
Pabrik wajib mengoperasikan jembatan timbang berkalibrasi resmi Dinas Metrologi Legal:
1. **Timbang Kotor (Gross Weight)**:
   - Truk tiba di gerbang pabrik dan naik ke platform jembatan timbang.
   - Operator mencatat berat kotor total truk beserta muatan ($W_{\text{gross}}$).
2. **Pembongkaran Muatan (Unloading)**:
   - Truk menuju area gudang pakan/silo dan membongkar seluruh biomassa.
3. **Timbang Kosong (Tare Weight)**:
   - Truk kembali ke jembatan timbang yang sama dalam keadaan bak kosong.
   - Operator mencatat berat tara truk kosong ($W_{\text{tare}}$).
4. **Bobot Bersih Pabrik (Net Weight)**:
   $$W_{\text{net}} = W_{\text{gross}} - W_{\text{tare}}$$

### 5.2 Evaluasi Susut Alami & Threshold Deviasi 3.0%
Sistem BioChain secara otomatis membandingkan bobot bersih jembatan timbang pabrik dengan akumulasi timbangan saung petani:
$$\text{Deviasi (\%) } = \frac{|W_{\text{pabrik}} - \sum W_{\text{saung}}|}{\sum W_{\text{saung}}} \times 100\%$$
- **Kasus A: Deviasi $\le 3,0\%$ (STATUS: ACCEPTED)**:
  - Diakui sebagai susut alami perjalanan cuaca tropis (penguapan kelembaban bebas dan hembusan debu mikro).
  - Pembayaran ke rekening pengepul langsung dicairkan secara otomatis.
- **Kasus B: Deviasi $> 3,0\%$ (STATUS: DISCREPANCY_FLAG)**:
  - Sistem otomatis **mengunci pencairan dana (Hold Payment)**.
  - Tiket diteruskan ke tim audit pabrik untuk investigasi anomali (kemungkinan kalibrasi timbangan saung menyimpang, muatan tercecer parah, atau indikasi kecurangan sopir di jalan).

### 5.3 Penerbitan Slip Timbangan Digital & Cetak Thermal Ber-QR
1. Klik tombol **"🖨️ Terbitkan Slip Timbangan"**.
2. Sistem menerbitkan tiket penimbangan resmi yang memuat:
   - ID Tiket Unik & Nomor Resi Transaksi
   - Nomor Polisi Truk & Nama Pengemudi
   - Rincian Berat: Gross, Tare, Netto
   - Persentase Susut Transit & Status Audit
   - QR Code Validasi Keabsahan Dokumen
3. Slip otomatis dicetak menggunakan printer thermal Bluetooth pos satpam (58mm atau 80mm) untuk diserahkan kepada driver, seraya salinan digital tersinkronisasi ke aplikasi pengepul.

### 5.4 Otomatisasi Settlement Saldo Rekening
- Setelah status tiket penimbangan diverifikasi `ACCEPTED`, sistem akuntansi pabrik melakukan settlement saldo secara otomatis ke dompet digital / rekening bank mitra pengepul dan petani.
- Bebas dari keterlambatan administrasi manual dan meminimalkan resiko kesalahan input kasir.

### 5.5 Solver Blending Reaktor (HiGHS) & Sertifikasi Karbon ESG
- **HiGHS Linear Programming Solver**: Memformulasikan racikan multi-biomassa optimal (sekam + jagung + cangkang sawit) untuk menghasilkan biochar berdaya serap tinggi sesuai standar SNI 8984:2021 dengan biaya bahan baku terendah.
- **Kalkulator Karbon ESG (IPCC Tier 2 & ISO 14083)**: Menghitung secara otomatis emisi pembakaran terbuka yang dihindarkan (*avoided open burning*), dikurangi jejak karbon solar truk, menghasilkan saldo kredit karbon bersih ($\text{tCO}_2\text{e}$) yang siap diaudit untuk pasar bursa karbon IDX Carbon.

---

## BAB 6: Panduan Administrator & SRE Konsorsium (⚙️)

### 6.1 Pemantauan Invarian Integritas & Optimistic Locking (CAS)
Untuk mencegah *race condition* pada saat penawaran lelang atau pembaruan status pengiriman, database BioChain mengimplementasikan *Compare-And-Swap (CAS)* berbasis kolom `version`:
```sql
UPDATE harvests 
SET status = 'collected', version = version + 1 
WHERE id = :id AND version = :current_version;
```
Jika terjadi konflik konkuren dari dua pengguna bersamaan, server mengembalikan respon `409 Conflict` dan mewajibkan penyegaran data, menjamin nol duplikasi penjualan.

### 6.2 Audit Trail Forensik & Row-Level Security (RLS)
- Seluruh riwayat perubahan status tercatat secara permanen di tabel audit log (siapa pengguna, alamat IP, timestamp UTC, serta payload perubahan data).
- Pada deployment PostgreSQL / Supabase, kebijakan *Row-Level Security (RLS)* membatasi petani hanya dapat melihat datanya sendiri, pengepul mengelola wilayahnya, dan data sensitif finansial pabrik terlindung dari akses publik.

### 6.3 Manajemen Parameter Dinamis (Master Registry)
Administrator dapat mengatur parameter acuan ekonomi dan agronomi melalui modul `app/params.py`:
- `biomass.moisture_ref_pct` (Kadar air acuan)
- `biomass.moisture_reject_pct` (Batas tolak kadar air)
- `freight.cdd_max_ton` & `freight.cdd_max_m3` (Batas armada truk)
- `weighbridge.max_discrepancy_pct` (Threshold toleransi deviasi susut)

---

## BAB 7: Panduan Pengoperasian IoT Lapangan & Printer Thermal

```
              ┌──────────────────────────────────────┐
              │          PANDUAN OPERASI IOT         │
              ├──────────────────────────────────────┤
              │ 1. Tancapkan probe optik ke tumpukan │
              │ 2. Letakkan sampel pada timbangan    │
              │ 3. Tekan tombol SCAN pada perangkat  │
              │ 4. Tunggu lampu hijau READY menyala  │
              │ 5. Printer mencetak label QR thermal │
              │ 6. Tempel label identitas pada karung│
              └──────────────────────────────────────┘
```

1. **Uji Cepat Kadar Air**: Tancapkan pin probe alat ukur kadar air (*moisture tester*) pada minimal 3 titik tumpukan berbeda untuk memperoleh rata-rata yang valid.
2. **Pencetakan Slip Thermal**:
   - Pastikan printer thermal POS 58mm/80mm terhubung via Bluetooth atau USB.
   - Dari aplikasi BioChain, tekan ikon cetak. Label memuat teks ringkas dan kode QR kontras tinggi yang mudah dipindai kamera ponsel di bawah terik sinar matahari.

---

## BAB 8: FAQ & Troubleshooting Lapangan

### Q1: Truk ditolak di pos timbang karena deviasi timbangan melebihi 3.0%?
**Penyebab & Solusi**:
- Selisih $> 3,0\%$ menandakan perbedaan signifikan antara timbangan saung dan jembatan timbang pabrik.
- **Langkah**: Petugas QC pabrik melakukan pemeriksaan fisik bersama sopir. Periksa apakah terpal penutup bak sobek sehingga muatan sekam terbang di jalan tol, atau apakah alat timbang saung belum ditera. Jika terbukti ada ceceran alamiah, Administrator dapat memberikan persetujuan override khusus (*discrepancy override approval*) dengan mencantumkan berita acara formal.

### Q2: Sinyal internet hilang saat sopir sedang memindai QR Code petani di sawah?
**Penyebab & Solusi**:
- Tidak perlu panik. Aplikasi driver secara otomatis menyimpan bukti penjemputan di memori ponsel (*IndexedDB offline*).
- Sopir dapat melanjutkan perjalanan. Begitu truk memasuki area ber-sinyal di jalan raya, aplikasi akan mengunggah data penjemputan secara otomatis ke server.

### Q3: Petani ingin membatalkan lelang karena butuh uang tunai cepat?
**Penyebab & Solusi**:
- Selama belum ada penawaran pembeli di atas *reserve price*, petani dapat membatalkan lelang dan langsung mengalihkan komoditasnya ke mode **Direct Price** untuk dibeli seketika oleh mitra Pengepul lokal.

### Q4: Apakah biochar muatan balik aman jika ditampung sementara di gudang pengepul?
**Penyebab & Solusi**:
- Sangat aman, asalkan diletakkan di atas palet kayu dengan jarak minimal 10 cm dari lantai semen dan terlindung dari tampias air hujan. Pengepul bertindak sebagai buffer hub sebelum biochar diambil petani pada saat musim bajak tanah.

---
*Bio-Chain v2.4 — Sustainable Energy & Circular Agriculture Innovation for Net Zero Indonesia 2026*
