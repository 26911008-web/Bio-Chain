# 📘 DOKUMENTASI LENGKAP ANTARMUKA DAN MEKANISME PERHITUNGAN BIO-CHAIN v2
## Platform Rantai Pasok Cerdas Multi-Biomassa, dMRV Karbon & Manufaktur Sirkular

**Kode Dokumen**: `DOC-BC2-OMNI-001`  
**Klasifikasi**: Master System Documentation, UI/UX Encyclopedia & Mathematical Specification  
**Basis Repositori**: Bio-Chain Prototype v2 (ANGEL Innovation Hackathon 2026 · Sustainable Energy Track)  
**Lingkup Cakupan**: 100% Elemen Antarmuka Web, 6 Persona Pengguna, 7 Lab Engine, 18 Kelompok Parameter Asumsi, serta Mekanisme Komputasi dan Keluar Angka Langkah demi Langkah (*Step-by-Step*).

---

## DAFTAR ISI

1. [BAB 1: ARSITEKTUR UMUM SISTEM & ELEMEN ANTARMUKA GLOBAL](#bab-1-arsitektur-umum-sistem--elemen-antarmuka-global)
   - 1.1 Identitas Brand, Skema Tema & Filosofi Desain
   - 1.2 Header Bar Global & Kontrol Navigasi
   - 1.3 Indikator Jaringan & Store-and-Forward Offline (`#net-pill`)
   - 1.4 Modul & Pop-up Modal Global (QR Scanner, Generator, Modal Pengguna)
   - 1.5 Asisten AI Interaktif Multi-Provider

2. [BAB 2: GERBANG MASUK & AUTENTIKASI (LOGIN & REGISTRASI)](#bab-2-gerbang-masuk--autentikasi-login--registrasi)
   - 2.1 Hero Section & Tagline Hackathon
   - 2.2 Gerbang Akses Cepat Berbasis Peran (*Quick Role Selectors*)
   - 2.3 Formulir Masuk (*Login Form*) & Auto-Fill Akun Demo
   - 2.4 Formulir Registrasi Pengguna Baru & Kebijakan Aktivasi

3. [BAB 3: ENSIKLOPEDIA DETAIL MODUL 6 PERSONA PENGGUNA](#bab-3-ensiklopedia-detail-modul-6-persona-pengguna)
   - 3.1 Portal 1: Petani / Produsen Biomassa (🌾)
   - 3.2 Portal 2: Pengepul / Hub Agregator Desa (📦)
   - 3.3 Portal 3: Driver / Sopir Truk Logistik (🚛)
   - 3.4 Portal 4: Pabrik / Operator Manufaktur Sirkular (🏭)
   - 3.5 Portal 5: Auditor Rantai Pasok & ESG dMRV (🔍)
   - 3.6 Portal 6: Administrator Sistem Platform (⚙️)

4. [BAB 4: TAB LAPORAN BULANAN (GUDANG DATA & MUTU QC)](#bab-4-tab-laporan-bulanan-gudang-data--mutu-qc)
   - 4.1 Filter Periode & Cakupan Akses Multi-Peran
   - 4.2 Matriks KPI Utama & Tren Visualisasi Grafik
   - 4.3 Gudang Data Analitik & Ekspor Laporan
   - 4.4 Modul Umpan Balik Mutu QC & Analisis Pareto Defect

5. [BAB 5: TAB PARAMETER ASUMSI (SINGLE SOURCE OF TRUTH)](#bab-5-tab-parameter-asumsi-single-source-of-truth)
   - 5.1 Arsitektur Registry & Protokol Audit Imutabel
   - 5.2 Rincian 18 Kelompok Parameter Asumsi Bisnis

6. [BAB 6: TAB LAB ENGINE WORKBENCH (7 ENGINE MANDIRI)](#bab-6-tab-lab-engine-workbench-7-engine-mandiri)
   - 6.1 Sub-Engine ②: Skor Mutu Proksimat & Kurva Rendemen
   - 6.2 Sub-Engine ③: Blending Feedstock Biaya Minimum (HiGHS LP)
   - 6.3 Sub-Engine ⑤: Rute Logistik CVRP Berbatas Volume
   - 6.4 Sub-Engine ⑧: Perbandingan Feedstock Multikriteria (TOPSIS)
   - 6.5 Sub-Engine ⑨: Penasihat Limbah-ke-Energi (Waste-to-Energy)
   - 6.6 Sub-Engine ⑩: Analisis Konsumsi Energi & Kriteria IKE ESDM
   - 6.7 Sub-Engine ⑫: Optimasi Konversi Multi-Produk Hilir

7. [BAB 7: MEKANISME DAN FORMULA MATEMATIS KELUAR ANGKA STEP-BY-STEP](#bab-7-mekanisme-dan-formula-matematis-keluar-angka-step-by-step)
   - 7.1 Mekanisme 1: Skor Mutu Proksimat, Penalti & Penentuan Grade (Engine ②)
   - 7.2 Mekanisme 2: Prediksi Rendemen Biochar terhadap Suhu Pirolisis & Koreksi Abu
   - 7.3 Mekanisme 3: Harga Beli Lapangan Petani & Refraksi Kadar Air Kontinu
   - 7.4 Mekanisme 4: Timbang Terima Gerbang Pabrik & Ekivalensi Bahan Kering (*Weighbridge QC*)
   - 7.5 Mekanisme 5: Gamifikasi Petani, Poin XP & Multiplier Bonus Tier (Engine ⑥)
   - 7.6 Mekanisme 6: Hak Dompet Biochar & Pembagian Konservatif (*Largest Remainder*)
   - 7.7 Mekanisme 7: Penetapan Harga Beli Dinamis Pabrik (*Netback Pricing Engine*)
   - 7.8 Mekanisme 8: Optimasi Campuran Biomassa Biaya Terendah & Indeks Alkali Slagging (Engine ③)
   - 7.9 Mekanisme 9: Jarak Matriks Jalan, Batas Volumetrik Truk & Algoritma Rute CVRP (Engine ⑤)
   - 7.10 Mekanisme 10: Jejak Emisi Logistik ISO 14083 & Konsumsi Bahan Bakar B40
   - 7.11 Mekanisme 11: Perhitungan Pengurangan Emisi Karbon IPCC 2006 Tier 2 (Engine ⑦)
   - 7.12 Mekanisme 12: Penilaian Skor Hijau (*Green Scorecard*): MCI & E-Factor Silika
   - 7.13 Mekanisme 13: Nilai Kalor Riil Lapangan (LHV As-Received ISO 18125) & Potensi Listrik
   - 7.14 Mekanisme 14: Baseline Energi Pabrik, Kriteria IKE & Deteksi Anomali Robust Z-Score / CUSUM
   - 7.15 Mekanisme 15: Pemeringkatan Biomassa Multi-Kriteria Metode TOPSIS (Engine ⑧)
   - 7.16 Mekanisme 16: Penasihat Tawaran Pengepul (*Bid Advisor* & Biaya Marjinal Logistik)
   - 7.17 Mekanisme 17: Penutupan Neraca Massa Multi-Produk (*Mass Balance Closure*)

---

# BAB 1: ARSITEKTUR UMUM SISTEM & ELEMEN ANTARMUKA GLOBAL

### 1.1 Identitas Brand, Skema Tema & Filosofi Desain
Website Bio-Chain v2 mengadopsi bahasa desain modern bertaraf industri (**Sleek Industrial & Glassmorphism**):
- **Logo & Tipografi**: Menampilkan ikon daun `🌿` dengan tipografi Google Fonts *Plus Jakarta Sans* untuk teks antarmuka dan *Syne* untuk penekanan angka KPI.
- **Skema Tema**: Mendukung mode ganda melalui atribut `data-theme="noir"`:
  * *Noir Theme (Gelap/Dark)*: Latar belakang abu-abu arang sangat gelap (`#111111`, `#18181b`), aksen hijau bio-energi neon (`#22c55e`, `#10b981`), serta aksen amber hangat (`#f59e0b`) untuk status peringatan logistik.
  * *Light Theme (Terang)*: Latar bersih berbasis putih gading (`#f8fafc`) dengan batas kontras abu-abu lembut (`#e2e8f0`).
- **Aksesibilitas & Standar Web**: Memenuhi standar WCAG 2.1 AA dengan tautan *Skip to Content* (`.skip-link`) untuk pembaca layar (*screen reader*), kontras warna rasio $\ge 4.5:1$, dan atribut ARIA pada seluruh elemen interaktif.

---

### 1.2 Header Bar Global & Kontrol Navigasi
Header aplikasi bersifat *sticky* (menempel di bagian atas layar selama navigasi) dengan komponen sebagai berikut:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 🌿 Bio-Chain v2           [🌾 Petani] [📦 Pengepul] [🚛 Driver] [🏭 Pabrik] [🔍 Auditor] [⚙️ Admin]   │
│    Sleman & Klaten        [Switch Persona ▼]  👤 Pak Sugeng [PETANI]  [📷 Scan QR] [⚡ Buat QR]        │
│                           [🔄 Reset Data Demo]  [🌙]  [🔒 Data saya]  [Keluar 🚪]                      │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **Brand Identity (`.header-brand`)**:
   - `🌿 Logo Badge`: Lambang ekosistem ekonomi sirkular biomassa.
   - `Header Brand Title`: "Bio-Chain v2".
   - `Header Brand Sub`: "Sleman & Klaten Feedstock Optimizer" (menandai wilayah operasional percontohan).
2. **Pill Beralih Persona Cepat (`#quick-persona-bar`)**:
   - Terdiri dari 6 tombol pil: `🌾 Petani`, `📦 Pengepul`, `🚛 Driver`, `🏭 Pabrik`, `🔍 Auditor`, dan `⚙️ Admin`.
   - *Fungsi*: Sekali klik langsung berpindah akun demo dan hak akses secara instan tanpa perlu mengetik ulang password (memanggil fungsi `quickSwitchPersona(role)`).
3. **Dropdown Persona Cadangan (`#persona-switcher`)**:
   - Tampil saat aplikasi dibuka pada layar ponsel/layar sempit di bawah 768px, memuat seluruh daftar akun demo tersimpan.
4. **Indikator Identitas Pengguna (`#user-info-pill`)**:
   - Menampilkan ikon persona, nama lengkap akun aktif (`#u-name`), dan lencana peran berwarna (`#u-role-badge`).
5. **Tombol Pemindai Kamera (`#btn-header-scanner`)**:
   - Berlabel `📷 Scan QR`. Membuka jendela modal pemindai kamera langsung untuk memvalidasi tiket panen, resi jalan supir, karung sekam, atau nota timbangan.
6. **Tombol Generator QR (`#btn-header-generator`)**:
   - Berlabel `⚡ Buat QR`. Membuka utilitas pembuatan kode QR 2D kustom secara instan untuk cetak label fisik.
7. **Tombol Reset Data Demo (`#btn-reset-demo`)**:
   - Berlabel `🔄 Reset Data Demo`. Khusus pengguna bertingkat `admin`, tombol ini mengeksekusi *hard re-seeding* basis data ke kondisi awal benchmark hackathon.
8. **Tombol Ganti Tema (`#btn-theme-toggle`)**:
   - Tombol bergambar bulan/matahari `🌙 / ☀️` untuk beralih instan antara mode gelap (*noir*) dan mode terang.
9. **Tombol Privasi UU PDP (`#btn-privacy`)**:
   - Berlabel `🔒 Data saya`. Membuka dialog kepatuhan Undang-Undang Perlindungan Data Pribadi (UU No. 27/2022). Memberikan kendali bagi pengguna untuk melihat data profil yang terekam, mencabut *consent*, mengekspor salinan data pribadi (format JSON), atau mengajukan penghapusan akun (*right to be forgotten*).
10. **Tombol Keluar (`#btn-logout`)**:
    - Berlabel `Keluar 🚪`. Menghapus token autentikasi (JWT) dari penyimpanan browser (*localStorage*) dan mengembalikan tampilan ke halaman muka/login.

---

### 1.3 Indikator Jaringan & Store-and-Forward Offline (`#net-pill`)
Terletak di sudut kiri bawah layar sebagai elemen mengambang (*floating pill*):
- **Status Online (`📶 Online`)**: Menandakan koneksi internet normal terhubung ke server backend FastAPI.
- **Status Offline (`📵 Offline · N antre`)**: Muncul otomatis ketika perangkat supir atau petani kehilangan sinyal di pedesaan.
  * Seluruh aksi mutasi (lapor panen, timbang terima pengepul, konfirmasi pickup supir) disimpan ke penyimpanan internal **IndexedDB** (`outbox` store).
  * Begitu sinyal internet kembali atau tombol pil diketuk, sistem menjalankan proses `flushOutbox()` secara otomatis, menyinkronkan data kembali ke server secara atomik.
- **Indikator Jejak GPS (`📍 N titik GPS`)**: Menampilkan jumlah koordinat rute jalan supir yang tersimpan secara lokal dan sedang menunggu pengiriman ke server.

---

### 1.4 Modul & Pop-up Modal Global
1. **Modal Tampilan Bukti QR (`#qr-modal`)**:
   - Menampilkan kode QR matriks 2D resolusi tinggi menggunakan pustaka *qrcodejs*.
   - Menampilkan kode alfanumerik unik (misal: `BIO-H101-SLM-26`).
   - Dilengkapi 3 tombol aksi: `📋 Salin Teks`, `⬇️ Unduh Gambar QR` (format PNG), dan `🖨️ Cetak`.
2. **Modal Pemindai Kamera Langsung (`#scanner-modal`)**:
   - Memanfaatkan pustaka *html5-qrcode* untuk mengakses kamera ponsel/webcam secara real-time.
   - Dilengkapi *laser animation reticle* (garis pemindai merah animasi bergerak turun-naik).
   - Tombol `🔄 Ganti Kamera`: Membalik kamera depan (*user*) dan kamera belakang (*environment*).
   - Tombol `🖼️ Upload Foto QR`: Memindai QR dari berkas galeri foto jika kamera fisik bermasalah.
   - Kotak Input Manual Fallback: Memungkinkan pengetikan kode manual apabila kamera kotor atau QR rusak tertimpa sekam.
3. **Modal Generator Kode QR Interaktif (`#generator-modal`)**:
   - Memungkinkan pembuatan QR instan dengan input teks bebas.
   - Pilihan preset 1-klik: `🌾 Preset Petani`, `🏭 Preset Batch Pabrik`, dan `🧪 Preset QC Timbang`.
4. **Modal Pendaftaran Akun Pengguna oleh Admin (`#admin-create-modal`)**:
   - Formulir modal pembuatan akun langsung dengan opsi pemilihan role, nomor telepon, username, password, dan kecamatan binaan.

---

### 1.5 Asisten AI Interaktif Multi-Provider
Tombol mengambang di sudut kanan bawah berlabel `🤖 Asisten`:
- Membuka panel konsultasi kecerdasan buatan (*AI Advisor*) yang dirancang khusus untuk konteks data peran aktif.
- **Pilihan Provider AI**:
  1. *Google Gemini* (Gemini 1.5 Flash / Pro).
  2. *Mistral AI* (Mistral Large / Small).
  3. *Groq* (Llama-3 70B ultra-low latency).
  4. *OpenRouter* (Koleksi model terbuka).
  5. *Ollama* (AI lokal privat tanpa koneksi internet luar).
- **Fitur Quick Prompt Chips**: Menyediakan rekomendasi pertanyaan kontekstual otomatis, seperti:
  * Petani: "Kapan waktu terbaik menjual sekam?", "Berapa proyeksi harga minggu depan?".
  * Pengepul: "Bagaimana cara menyiasati kadar air sekam 18% agar tidak rugi?".
  * Pabrik: "Berapa formulasi blending termurah untuk target kalori 4.200 kcal/kg?".

---

# BAB 2: GERBANG MASUK & AUTENTIKASI (LOGIN & REGISTRASI)

Saat membuka root URL web (`http://127.0.0.1:8000`), sistem menampilkan tampilan autentikasi `#login-view`.

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│  [🌿 Logo]                                                                        │
│  Bio-Chain v2                                                                     │
│  Smart Multi-Biomass Supply Chain & Circular Bio-Economy Platform                 │
│  ANGEL Hackathon 2026 · Feedstock Optimization                                    │
│                                                                                   │
│  ┌────────────────────── Masuk atau Daftar Akun ──────────────────────────────┐  │
│  │  [🔑 Masuk Akun]                              [📝 Daftar Akun Baru]        │  │
│  │                                                                            │  │
│  │  Masuk sebagai:                          🟢 SQLite Lokal Aktif             │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │  │
│  │  │ 🌾 Petani    │ │ 📦 Pengepul  │ │ 🚛 Driver    │ │ 🏭 Pabrik    │       │  │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘       │  │
│  │  ┌──────────────┐                                                         │  │
│  │  │ 🔍 Auditor   │   ⚙️ Masuk sebagai Administrator                         │  │
│  │  └──────────────┘                                                         │  │
│  │                                                                            │  │
│  │  Username atau Nomor Telepon: [ 081544556677                          ]    │  │
│  │  Password:                    [ ••••••••                 ] [👁️]           │  │
│  │                                                                            │  │
│  │  [ Masuk ke Sistem Bio-Chain ➔                                           ]  │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Hero Section & Tagline Hackathon
- **Elemen Grafis Ornamen (`.login-hero-ornament`)**: Animasi CSS lingkaran konsentris bertingkat melambangkan loop rantai pasok sirkular tertutup.
- **Teks Judul Utama**: `Bio-Chain v2` dengan penekanan aksen gradasi hijau.
- **Teks Penjelas Produk**: "Smart Multi-Biomass Supply Chain & Circular Bio-Economy Platform (Bio-Pellet, Briket, Biochar & Bio-Silika)".
- **Tagline Kompetisi**: "ANGEL Hackathon 2026 · Feedstock Optimization".

---

### 2.2 Gerbang Akses Cepat Berbasis Peran (*Quick Role Selectors*)
Menampilkan 5 kartu gerbang utama + 1 tautan administrator:
1. `🌾 Petani`: Produsen biomassa sekam, melihat stok panen, saldo dompet biochar, dan poin XP loyalitas.
2. `📦 Pengepul`: Hub agregator desa / KUD, melakukan verifikasi mutu proksimat dan tawar-menawar lelang B2B.
3. `🚛 Driver`: Sopir armada truk pengangkut sekam, navigasi titik jemput dan pemindai QR muatan.
4. `🏭 Pabrik`: Operator industri pirolisis PT Indmira, monitoring jembatan timbang, produksi sirkular, dan kalkulator emisi karbon IPCC.
5. `🔍 Auditor`: Badan verifikasi independen (TÜV NORD, DNV, SRN-PPI KLHK), akses audit trail timbangan dan kepatuhan standar karbon Puro.earth.
6. `⚙️ Administrator`: Pengelola sistem platform, konfigurasi parameter harga acuan dan manajemen akun.

---

### 2.3 Formulir Masuk (*Login Form*) & Auto-Fill Akun Demo
- **Input Identitas (`#login-ident`)**: Menerima username alfanumerik (contoh: `petani_sugeng`, `admin`) atau nomor telepon seluler (contoh: `081544556677`).
- **Input Password (`#login-pass`)**: Kolom kata sandi dengan tombol toggle visibilitas mata (`👁️`).
- **Tabel Kredensial Akun Demo Bawaan**:
  * Petani Sugeng: Username `petani_sugeng` / Telp `081544556677` / Sandi `sekam123`.
  * Pengepul Sleman: Username `pengepul_sleman` / Telp `081322334455` / Sandi `kud2026`.
  * Driver Budi: Username `sopir_budi` / Telp `081433445566` / Sandi `truk2026`.
  * Pabrik Indmira: Username `pabrik_indmira` / Telp `081298765432` / Sandi `pabrik2026`.
  * Auditor ESG: Username `auditor_esg` / Telp `081677889900` / Sandi `audit2026`.
  * Administrator: Username `admin` / Telp `081234567890` / Sandi `admin2026`.

---

### 2.4 Formulir Registrasi Pengguna Baru & Kebijakan Aktivasi
Dapat diakses melalui tombol switcher `📝 Daftar Akun Baru`:
- **Role Selector (`#reg-role`)**: Pilihan peran (Petani, Pengepul, Driver, Pabrik).
- **Aturan Aktivasi Otomatis vs Verifikasi**:
  * *Akun Petani*: Status akun langsung `AKTIF` seketika saat registrasi selesai, sehingga petani tidak terhambat birokrasi untuk segera mencatatkan hasil panennya.
  * *Akun Operasional Komersial (Pengepul, Driver, Pabrik)*: Berstatus `PENDING` menunggu persetujuan dan verifikasi legalitas oleh Administrator.
- **Bidang Input**: Nama Lengkap (`#reg-fullname`), Nomor Telepon/WhatsApp (`#reg-phone`), Username opsional (`#reg-username`), Kata Sandi (`#reg-pass`), dan Kecamatan asal lahan/gudang (`#reg-kecamatan`).

---

# BAB 3: ENSIKLOPEDIA DETAIL MODUL 6 PERSONA PENGGUNA

Ketika pengguna berhasil masuk, tab pertama yang aktif adalah **🌾 Portal Persona** (`#tab-persona`), yang merender antarmuka dinamis sesuai peran pengguna yang login.

---

### 3.1 Portal 1: Petani / Produsen Biomassa (🌾)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [Total Laporan Panen: 14 Batch]  [Total Tonase: 35.0 Ton]  [XP: 1.250 · Mitra Emas]  [Dompet Biochar:  │
│ (avg: 2.1/bln)                   (avg: 5.2 Ton/bln)                                   175.0 kg Saldo]  │
├────────────────────────────────────────────────────┬───────────────────────────────────────────────────┤
│ 🌾 Lapor & Jual Biomassa                           │ 🏷️ Riwayat Laporan Panen                          │
│                                                    │ ┌───────┬──────────┬───────────┬───────┬─────────┐ │
│ Komoditas: [ Sekam Padi ▼ ]                        │ │ ID    │ kg       │ Status    │ Grade │ Aksi    │ │
│ 💡 Harga Acuan: Sekam padi — Rp 400 / kg           │ ├───────┼──────────┼───────────┼───────┼─────────┤ │
│ Jumlah: [ 2500 ] kg                                │ │ #101  │ 2.500    │ DELIVERED │ A     │ [QR 👁️] │ │
│ Titik Pasok: [ Penggilingan Sidomulyo, Godean ▼ ]  │ │ #102  │ 1.800    │ VERIFIED  │ B     │ [QR 👁️] │ │
│                                                    │ └───────┴──────────┴───────────┴───────┴─────────┘ │
│ 💧 Info Mutu (Opsional):                           │                                                   │
│   Air (%): [ 12.0 ]   Grade Est: [ A · Kering ▼ ]  │ 🏷️ Stok Lelang & Tawaran Masuk (Pasar B2B)        │
│                                                    │ • Lot #103 · Sisa 2.000 kg / 2.000 kg             │
│ Cara Jual:                                         │   🚚 Jemput min Rp 380/kg · 🛵 Antar min Rp 460/kg│
│   (o) 🤝 Jual ke pengepul (Harga acuan otomatis)   │   [Lihat Tawaran (2)]  [Batalkan]                 │
│   ( ) 🏷️ Lelang B2B (Tetapkan batas minimum)      │                                                   │
│                                                    │ ♻️ Biochar untuk Sawah                            │
│ Skema Penyerahan:                                  │ Hak biochar: 175.0 kg · Potensi hemat urea: 52 kg │
│   (o) 🚚 Dijemput pengepul (Biaya pengepul)        │ [Ajukan Tebus Pengiriman Biochar ➔]              │
│   ( ) 🛵 Saya antar ke gudang (+Rp 80/kg premi)    │                                                   │
│                                                    │ 💸 Pembayaran Saya (Field Ops)                    │
│ [ Terbitkan Laporan Biomassa ➔ ]                   │ Lot #101 · Lunas Rp 1.150.000 (Transfer Bank)     │
└────────────────────────────────────────────────────┴───────────────────────────────────────────────────┘
```

#### A. Baris Kartu Indikator Kinerja Utama (KPI Tiles)
1. **Total Laporan Panen (`#p-tot-harvest`)**: Jumlah transaksi pengiriman sekam yang pernah dilaporkan petani, disertai rata-rata frekuensi pengiriman per bulan (`#p-tot-harvest-avg`).
2. **Total Tonase Terkirim (`#p-tot-ton`)**: Akumulasi bobot sekam yang berhasil terkirim ke rantai pasok dalam satuan ton, beserta rata-rata tonase per bulan (`#p-tot-ton-avg`).
3. **XP Gamifikasi (`#p-xp`)**: Total poin pengalaman loyalitas yang diraih petani, dilengkapi lencana tier saat ini (`#p-tier-lbl`, misal: *Mitra Emas*).
4. **Dompet Biochar Sirkular (`#p-wallet`)**: Saldo biochar aktif dalam satuan kilogram yang berhak ditarik gratis oleh petani untuk lahan sawahnya, dilengkapi rincian:
   - Saldo berpotensi diambil (`#p-wallet-avail`).
   - Saldo yang sudah diambil/ditebus ke sawah (`#p-wallet-taken`).

#### B. Formulir "Lapor & Jual Biomassa" (`#form-lapor-sekam`)
1. **Komoditas Biomassa (`#f-commodity`)**: Dropdown pemilihan bahan baku (Sekam padi, Tongkol jagung, Serbuk kayu, Tempurung kelapa).
2. **Kotak Rekomendasi Harga Acuan (`#f-rec-box`)**: Menampilkan harga patokan standar saat ini (`#f-rec-price`, contoh: *Rp 400 / kg*).
3. **Jumlah Pasokan (`#f-qty`)**: Input berat biomassa dalam kilogram (rentang 50 kg hingga 50.000 kg).
4. **Titik Lokasi Pasok (`#f-mill`)**: Pilihan titik koordinat penggilingan padi tempat tumpukan sekam berada.
5. **Accordion Info Mutu Lapangan (`#f-quality-box`)**:
   - Taksiran kadar air (`#f-moist`, rentang 0–60%).
   - Taksiran grade visual (`#f-grade`: A/B/C/D).
   - *Catatan Lapangan*: Bersifat opsional dan tidak mengikat harga akhir (harga final wajib mengacu pada uji timbang & lab pengepul).
6. **Pilihan Cara Jual (`name="f-mode"`)**:
   - `🤝 Jual ke pengepul`: Penjualan langsung cepat menggunakan patokan harga acuan.
   - `🏷️ Lelang`: Membuka penawaran terbuka di bursa B2B kepada banyak pengepul dengan menentukan harga batas minimum (*reserve price*).
7. **Pilihan Skema Logistik Penyerahan (`name="f-deliv"`)**:
   - `🚚 Dijemput pengepul`: Truk pengepul datang mengambil ke lokasi sawah/penggilingan; ongkos angkut ditanggung pembeli.
   - `🛵 Saya antar ke gudang`: Petani mengantar sendiri sekam ke gudang hub; petani mendapatkan **premi transportasi mandiri sebesar +Rp 80/kg**.

#### C. Tabel Riwayat Laporan Panen (`#table-petani-harvests`)
Menampilkan daftar batch pengiriman petani dengan status warna:
- `submitted` (Oranye): Baru dilaporkan, menunggu verifikasi.
- `verified` (Biru): Mutu dan berat telah diverifikasi pengepul.
- `collected` (Ungu): Muatan telah dinaikkan ke bak truk supir.
- `delivered` / `converted` (Hijau): Sekam telah diterima pabrik / telah dikonversi menjadi biochar di reaktor.
- `rejected` (Merah): Ditolak karena kadar air $>25\%$ atau kotor.
- Tombol `QR 👁️`: Membuka QR tanda terima digital untuk dipindai supir/pengepul.

#### D. Kartu "Stok Lelang & Tawaran Masuk (Pasar B2B)" (`#my-listings`)
- Menampilkan status lelang berjalan, sisa kuota kilogram yang belum terjual, dan harga minimum penawaran.
- Tombol `Lihat tawaran`: Membuka daftar tawaran harga dari para pengepul. Menampilkan kolom: Pengepul, Skema, Harga Tawaran, **Nilai Bersih per kg** (harga dikurangi estimasi ongkos antar), Volume kg, dan tombol `Pilih` (menerima sebagian atau seluruh kuota).

#### E. Kartu "Biochar untuk Sawah" (`#petani-biochar-card`)
- Menampilkan kalkulasi agronomi otomatis: Saldo hak biochar ($kg$), estimasi penghematan pupuk kimia urea ($kg$), dan potensi kenaikan panen gabah ($ton\text{ GKP/ha}$).
- Tombol `Ajukan Pengambilan Biochar`: Mengirim instruksi ke pabrik untuk mengirimkan karung biochar pembenah tanah kembali ke sawah petani saat masa bajak tanah.

---

### 3.2 Portal 2: Pengepul / Hub Agregator Desa (📦)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [Antrian Verifikasi: 5 Laporan]     [Terverifikasi Hari Ini: 8.500 kg]    [Skor Mutu Rata-rata: 88.4] │
├────────────────────────────────────────────────────┬───────────────────────────────────────────────────┤
│ 📦 Antrian Biomassa Masuk                          │ 🔬 Uji Mutu Proksimat Biomassa                    │
│ ┌─────┬───────────────────┬─────────┬────────────┐ │ Target: Lot #103 (Pak Sugeng · 2.500 kg)          │
│ │ ID  │ Petani            │ kg      │ Aksi       │ │ ⚖️ Berat Timbang Lapangan: [ 2480 ] kg           │
│ ├─────┼───────────────────┼─────────┼────────────┤ │ Kadar Air (% bb) — Wajib: [ 11.5 ] %              │
│ │ #103│ Pak Sugeng        │ 2.500   │ [💬 WA][Uji]│ │ Kadar Abu (% bk):         [ 17.5 ] %              │
│ │ #104│ Bu Darmi          │ 1.800   │ [💬 WA][Uji]│ │ Volatile Matter (% bk):   [ 66.0 ] %              │
│ └─────┴───────────────────┴─────────┴────────────┘ │ Fixed Carbon (% bk):      [ 16.5 ] %              │
│                                                    │ Kontaminan / Kotoran (%): [ 1.0  ] %              │
│ 🛒 Pasar Stok Biomassa Petani (Bursa B2B)          │ Suhu Pirolisis Target:    [ 500  ] °C             │
│ Harga jual pabrik: [ 560 ] Rp/kg   Margin: [ 5.0 ]%│ Preview Mutu: Grade A · Skor 91.2 · Pengali x1.15 │
│ [🚛 Rencanakan Jemput (CVRP)]                      │ [ Verifikasi Mutu & Terbitkan Resi TRX ➔ ]        │
│                                                    │ [ ⛔ Tolak Lot ]                                  │
├────────────────────────────────────────────────────┴───────────────────────────────────────────────────┤
│ 🚚 Ajukan Pengiriman ke Pabrik (Delivery Request B2B)                                                  │
│ Jumlah: [ 5000 ] kg   Kadar Air: [ 11.0 ]%   Tanggal: [ 2026-10-18 ]   Harga Diajukan: [ 540 ] Rp/kg   │
│ Rekomendasi Pabrik: Rp 535 / kg (Berdasarkan Netback) · [✔] Lampirkan 2 Lot Petani                    │
│ [ Ajukan Pengiriman ➔ ]                                                                               │
│                                                                                                        │
│ Modul Kepatuhan Lapangan:                                                                             │
│ [👵 Petani Tanpa HP]   [💸 Bayar Petani / Catat DP]   [🏚️ Gudang & Stok]   [🚚 Potongan Jarak Kosong]  │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### A. Baris Kartu KPI Pengepul
1. **Antrian Verifikasi (`#col-pending`)**: Total lot panen petani binaan yang menunggu penimbangan lapangan.
2. **Terverifikasi Hari Ini (`#col-verified-kg`)**: Akumulasi kilogram biomassa yang telah selesai ditimbang dan diuji kualitasnya hari ini.
3. **Skor Mutu Hari Ini (`#col-avg-score`)**: Skor mutu proksimat rata-rata dari lot yang diverifikasi pada hari berjalan.

#### B. Tabel Antrian & Formulir Uji Mutu Proksimat
- **Tombol Kontak Cepat (`[💬 WA]`)**: Membuka percakapan WhatsApp otomatis ke nomor petani untuk konfirmasi ketersediaan sekam sebelum berangkat. Jika petani tidak memiliki HP, tombol otomatis berlabel `👵 Tanpa HP`.
- **Tombol Uang Muka (`[🤝 DP]`)**: Memungkinkan pengepul menyetor uang muka pengikat (maksimal 30% dari total nilai kontrak lelang) untuk mengamankan stok.
- **Formulir Uji Mutu (`#form-verify-harvest`)**:
  * Berat Timbangan Lapangan (`#v-weight`): Bobot nyata hasil timbangan gantung digital.
  * Kadar Air (% bb) (`#v-moisture`): Wajib diisi dari pembacaan instrumen tusuk (*moisture meter*).
  * Uji Laboratorium Opsional: Kadar Abu (`#v-ash`), Volatile Matter (`#v-vm`), Fixed Carbon (`#v-fc`), dan Kontaminan benda asing (`#v-contam`). Jika tidak diisi, sistem otomatis menerapkan komputasi cerdas berbasis kadar air & kontaminan tanpa menghambat operasional lapangan.
  * Kotak Pratinjau Mutu (`#v-preview`): Menampilkan skor mutu komposit, penetapan grade (A/B/C/TOLAK), dan pengali harga secara *real-time*.
  * Tombol `Verifikasi Mutu & Terbitkan Resi TRX ➔`: Menerbitkan kode transaksi resmi berformat `TRX-[PENGIRIM]-[PENERIMA]-[YYMM]-[NOMOR]` yang memuat rincian harga bayar bersih dan QR timbang.

#### C. Pasar Stok Biomassa B2B & Rencana Penjemputan (*Pickup Planner*)
- **Penasihat Tawaran (`adviseBid`)**: Pengepul memasukkan target harga jual ke pabrik dan persentase margin yang diinginkan. Sistem secara cerdas menghitung biaya logistik marjinal (tambahan jarak rute truk) dan menampilkan batas penawaran maksimum yang menguntungkan.
- **Rencana Penjemputan Gabungan (`#pickup-plan-result`)**: Menggabungkan seluruh lot lelang yang dimenangkan berskema jemput ke dalam satu rute multi-stop optimal (CVRP) guna memangkas biaya transportasi hingga 25–40%.

#### D. Pengajuan Pengiriman ke Pabrik (*Delivery Request B2B*)
- Pengepul yang mengumpulkan $>3.000\text{ kg}$ sekam di gudangnya dapat mengajukan jadwal pengiriman resmi ke pabrik:
  * Mengisi kuota berat, taksiran kadar air, dan tanggal kedatangan truk.
  * Menampilkan harga rekomendasi pabrik (*Factory Netback Price*).
  * **Lampiran Lot Petani (`#dr-harvests`)**: Fitur vital *Chain of Custody* (ISO 22095). Pengepul mencentang lot petani mana saja yang dicampur ke dalam truk tersebut. Hal ini memastikan bahwa saat pabrik memproses batch, hak retur biochar dapat ditelusuri dan dikreditkan secara adil ke dompet petani yang bersangkutan.

#### E. Fitur Kepatuhan Lapangan Tambahan (*Field-Ops*)
1. `👵 Petani Tanpa HP`: Pengepul dapat mendaftarkan identitas petani lansia/tanpa smartphone, mengunci titik koordinat GPS sawah, mencatat persetujuan lisan (UU PDP), dan mencetakkan kartu identitas QR fisik.
2. `💸 Bayar Petani`: Pencatatan pelunasan transaksi pembelian biomassa, pemotongan DP otomatis, pemilihan metode pembayaran (Tunai, Transfer, QRIS, E-Wallet), dan penerbitan bukti kuitansi berstempel digital (`BYR-...`).
3. `🏚️ Gudang & Stok Multi-Biomassa`: Manajemen inventori stok multi-komoditas per gudang, dengan penyesuaian susut kadar air otomatis.
4. `🚚 Potongan Logistik Saya`: Transparansi pemotongan ongkos kilometer kosong (*empty haul penalty*) apabila pengepul membatalkan pengiriman saat truk pabrik sudah telanjur meluncur di jalan.

---

### 3.3 Portal 3: Driver / Sopir Truk Logistik (🚛)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [Status: BERJALAN]   [Plat: AB 8492 JN]   [Jarak Rencana: 42.5 km]   [GPS Terekam: 18.2 km]   [Utilisasi: 85%] │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Panel Kendali Supir:  [⏹️ Selesaikan Rute & Unggah Jejak Emisi ISO 14083]                             │
├────────────────────────────────────────────────────┬───────────────────────────────────────────────────┤
│ 🚛 Titik Penjemputan Biomassa (Rute Aktif #12)     │ 🗺️ Peta Navigasi Interaktif Leaflet              │
│                                                    │ ┌───────────────────────────────────────────────┐ │
│ 1. [✔] Penggilingan Sidomulyo (Pak Sugeng)         │ │  [🏭 Pabrik Indmira - Depot]                  │ │
│    Muatan: 2.500 kg (22.7 m³) · Status: DIJEMPUT   │ │        \                                      │ │
│                                                    │ │         \  (Rute Jalan Polylines)             │ │
│ 2. [ ] Penggilingan Berkah, Seyegan (Bu Darmi)     │ │          \                                    │ │
│    Muatan: 1.800 kg (16.4 m³) · Status: MENUNGGU   │ │          [📍 Stop 1: Pak Sugeng]              │ │
│    [📷 Check-In & Scan QR]  [⚠️ Lapor Kendala]     │ │           \                                   │ │
│                                                    │ │            [📍 Stop 2: Bu Darmi]              │ │
│ 3. [ ] Gudang KUD Sleman                           │ └───────────────────────────────────────────────┘ │
│    Kembali ke Depot Pabrik PT Indmira              │ 📍 GPS Akurat (±4m) · Mode Layar Terkunci Aktif   │
└────────────────────────────────────────────────────┴───────────────────────────────────────────────────┘
```

#### A. Baris Kartu KPI Driver
1. **Status Rute (`#d-status`)**: Menampilkan status operasional (`DIRENCANAKAN`, `BERJALAN`, atau `SELESAI`).
2. **Plat Nomor Armada (`#d-plate`)**: Identitas kendaraan truk pengangkut yang ditugaskan (contoh: `AB 8492 JN`).
3. **Jarak Rencana (`#d-km`)**: Total jarak tempuh teoretis hasil optimasi algoritma Clarke-Wright / OR-Tools dalam satuan kilometer.
4. **Jarak GPS Terekam (`#d-gps-km`)**: Jarak nyata yang telah ditempuh kendaraan berdasarkan perekaman koordinat GPS ponsel secara *store-and-forward*.
5. **Utilisasi Bak Truk (`#d-util`)**: Persentase kepenuhan volume bak truk berdasarkan densitas curah biomassa.

#### B. Daftar Perhentian Rute (*Route Stops List*)
Menampilkan urutan penjemputan dari titik depot pabrik $\to$ titik-titik petani $\to$ kembali ke depot:
- Setiap titik henti menampilkan nama penggilingan, tonase muatan, dan estimasi volume kubikasi ($m^3$).
- Tombol `📷 Check-In & Scan QR`: Mengaktifkan kamera untuk memindai QR nota milik petani saat karung sekam mulai dinaikkan ke atas bak.
- Tombol `⚠️ Lapor Kendala / Stop Gagal`: Digunakan jika penjemputan di suatu lokasi gagal. Supir memilih alasan standar (contoh: *Sekam basah/berjamur*, *Jalan sempit tidak muat*, *Stok sudah dijual*, *Bak truk sudah penuh*). Sistem secara otomatis mencatat pembatalan dan membebaskan komitmen stok tanpa merusak jadwal rute stop berikutnya.

#### C. Navigasi Peta Interaktif Leaflet (`#driver-map`)
- Menampilkan peta geografis wilayah Sleman, Klaten, dan sekitarnya menggunakan ubin peta *OpenStreetMap*.
- Menandai depot pabrik (ikon pabrik merah), titik-titik petani (penanda nomor urut biru/hijau), dan garis rute jalan (*polyline*).
- Menampilkan posisi langsung supir (*live pulsing blue dot*) lengkap dengan radius akurasi GPS.
- Dilengkapi integrasi **Screen Wake Lock API**: Mencegah layar ponsel supir meredup atau terkunci otomatis saat ditaruh di dasbor truk, memastikan perekaman GPS di latar belakang tidak dihentikan oleh sistem operasi Android/iOS.

---

### 3.4 Portal 4: Pabrik / Operator Manufaktur Sirkular (🏭)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [Emisi Dihindari: 142.5 tCO₂e]  [Output Biochar: 48.2 Ton]  [Potensi SiO₂: 8.6 Ton]  [Produk Sirkular: │
│ (IPCC 2006 Tier 2)               (Rendemen Terverifikasi)    (Ekstraksi Silika Abu)   4 Lini Aktif]    │
├────────────────────────────────────────────────────┬───────────────────────────────────────────────────┤
│ 📈 Proyeksi Pasokan Biomassa 30 Hari               │ 🌿 Kalkulator Emisi Karbon IPCC                   │
│ [Grafik Proyeksi Pasokan Chart.js - Dual Cosine]   │ Biomassa: [ 50 ] ton   Jarak Angkut: [ 45 ] km    │
│ Puncak Panen Raya: April-Mei & September-Oktober   │ [ Hitung Pengurangan CO₂ ➔ ]                     │
│ Rekomendasi: Pasokan melimpah, optimalkan silo.    │ Hasil: Netto 42.8 tCO₂e · Nilai NEK: Rp 2.568.000 │
├────────────────────────────────────────────────────┴───────────────────────────────────────────────────┤
│ 🧮 Rekomendasi Harga Beli Multi-Biomassa (Netback Pricing Engine)                                      │
│ Komoditas: [ Sekam Padi ▼ ]   Kadar Air: [ 11.0 ]%   Abu: [ 18.0 ]%   Kontaminan: [ 0.0 ]%             │
│ Harga Produk: Bio-Pellet: [ 1800 ] Rp/kg · Biochar: [ 3500 ] Rp/kg · Bio-Silika: [ 28000 ] Rp/kg       │
│ Jalur Silika: [ Ekstraksi Biochar ▼ ]   Porsi ke Silika: [ 0.15 ]                                      │
│ Hasil: Harga Lantai Rp 412/kg · Harga Plafon Rp 580/kg · Target Rekomendasi: Rp 515 / kg              │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 🏭 Batch Produksi Multi-Produk (Pirolisis, Pellet, Briket & Silika)                                    │
│ Kode Batch: [ BATCH-2026-X12 ]   Suhu Pirolisis: [ 500 ] °C   [ Isi dari Model Rekomendasi ]           │
│ Input Lot QC: [✔] Lot #101 (2.450 kg)  [✔] Lot #103 (2.480 kg) ➔ Total Input: 4.930 kg Bahan Kering    │
│ Output Produk: Biochar: [ 1.620 ] kg · Bio-Silika: [ 210 ] kg · Bio-Pellet: [ 1.200 ] kg                │
│ Mass Balance Closure: 99.8% (Air 542 kg, Syngas 1.150 kg, Residu 180 kg, Susut 28 kg)                │
│ Alokasi Dompet Petani: Pak Sugeng (+81.4 kg Biochar) · Bu Darmi (+80.6 kg Biochar) [Hare-Niemeyer]  │
│ [ Kunci Batch & Alokasikan Dompet Petani ➔ ]                                                           │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### A. Baris Kartu KPI Pabrik
1. **Emisi Karbon Dihindari (`#f-co2`)**: Total pengurangan gas rumah kaca yang dicapai pabrik melalui substitusi batubara dan sekuestrasi karbon biochar dalam satuan $tCO_2\text{e}$ (metodologi IPCC 2006 Tier 2).
2. **Output Biochar Terkarbonisasi (`#f-biochar`)**: Tonase kumulatif biochar padat bersertifikasi yang telah diproduksi dari reaktor pirolisis lambat.
3. **Potensi Biosilika $SiO_2$ (`#f-sio2`)**: Estimasi potensi silika amorf murni yang dapat diekstraksi dari fraksi abu biomassa.
4. **Lencana Produk Sirkular**: Menandai kesiapan fasilitas memproduksi 4 produk hilir (Bio-pellet, Briket, Biochar pembenah tanah, dan Bio-silika industri).

#### B. Grafik Proyeksi Pasokan 30 Hari (`#factory-forecast-chart`)
- Merender kurva fluktuasi pasokan gabah/sekam di wilayah Sleman dan Klaten untuk 30 hari ke depan menggunakan pustaka *Chart.js*.
- Berakar pada model harmonik cosinus ganda kalibrasi BPS (Badan Pusat Statistik), memprediksi gelombang musim panen raya (April–Mei dan September–Oktober) serta musim paceklik, guna memandu keputusan kapasitas penyerapan gudang pabrik.

#### C. Kalkulator Pengurangan Emisi Karbon IPCC (`calcCarbon`)
- Input: Jumlah biomassa ($ton$) dan jarak angkut transportasi ($km$).
- Output: Energi biomassa ($GJ$), batubara yang tergantikan ($ton$), emisi pembakaran batubara yang dihindari ($tCO_2$), emisi truk pengangkut ($tCO_2$), dan **Pengurangan Emisi Karbon Bersih (Net Carbon Sink)**. Jika parameter harga pasar karbon diisi, sistem menghitung potensi monetisasi Nilai Ekonomi Karbon (NEK) di bursa karbon IDXCarbon.

#### D. Rekomendasi Harga Beli Multi-Biomassa (*Netback Pricing Engine*)
- Memungkinkan manajemen pabrik menentukan harga beli bahan baku yang rasional secara ekonomi:
  * Mengambil nilai jual pasar dari ketiga produk hilir (Bio-pellet, Biochar, Bio-silika).
  * Mengurangkan biaya operasional variabel (listrik, bahan kimia asam/basa, bahan bakar awal pirolisis).
  * Mengurangkan depresiasi garis lurus mesin pabrik per jam dan alokasi biaya tetap overhead.
  * Menghasilkan **Harga Lantai** (*Floor Price*), **Harga Plafon** (*Ceiling Price* / titik impas), dan **Harga Target Rekomendasi** dengan target margin laba pabrik.

#### E. Batch Manufaktur Sirkular & Neraca Massa (*Mass Balance Closure*)
- Operator memilih daftar lot sekam yang baru selesai diperiksa di jembatan timbang.
- Memasukkan parameter operasi: Suhu reaktor pirolisis ($^\circ\text{C}$), jalur ekstraksi silika yang aktif, dan tonase riil masing-masing produk jadi.
- **Pemeriksaan Neraca Massa 1 Input $\to$ 3 Produk + 5 Loss**: Memastikan hukum kekekalan massa tertutup rapat ($100 \pm 1\%$), memperhitungkan penguapan air, gas volatil/syngas, gas pembakaran, residu pelindian asam, dan susut mekanik.
- **Kredit Otomatis Dompet Petani (*Hare-Niemeyer Algorithm*)**: Secara instan menghitung porsi biochar hak petani hingga ketelitian satuan gram dan menyuntikkannya langsung ke saldo dompet masing-masing petani yang menyuplai batch tersebut.

---

### 3.5 Portal 5: Auditor Rantai Pasok & ESG dMRV (🔍)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [Timbangan Pengepul: 124.500 kg]  [Timbangan Pabrik: 122.150 kg]  [Total Susut: 2.350 kg (1.89%)]      │
│ [Biochar Kembali ke Petani: 6.107,50 kg Teralokasi]              [Ambang Batas Toleransi: ≤ 3.0%]      │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 🔍 Daftar Pengiriman dengan Selisih Timbangan & Anomali                                               │
│ ┌──────────┬──────────────────┬────────────────┬──────────┬──────────────────────────────────────────┐ │
│ │ Harvest  │ Pengepul (kg)    │ Pabrik (kg)    │ Susut %  │ Status Integritas & Catatan              │ │
│ ├──────────┼──────────────────┼────────────────┼──────────┼──────────────────────────────────────────┤ │
│ │ #108     │ 2.500            │ 2.445          │ 2.20 %   │ 🟢 Normal (Dalam batas toleransi 3%)     │ │
│ │ #112     │ 3.200            │ 3.010          │ 5.94 %   │ 🟡 Peringatan (Penguapan terik jalan)    │ │
│ │ #115     │ 2.800            │ 2.550          │ 8.93 %   │ 🔴 ANOMALI (Selisih >7% · Terpal bocor)  │ │
│ └──────────┴──────────────────┴────────────────┴──────────┴──────────────────────────────────────────┘ │
│ Akses Baca-Saja: DNV / TÜV NORD / Verifikator SRN-PPI KLHK · Standar Puro.earth & ISO 22095:2020      │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### A. Baris Kartu KPI Auditor
1. **Timbangan Pengepul (`#au-collector`)**: Total akumulasi berat sekam saat ditimbang di tingkat desa oleh para pengepul.
2. **Timbangan Pabrik (`#au-factory`)**: Total berat sekam saat ditimbang ulang di atas jembatan timbang gerbang pabrik.
3. **Total Susut Bobot Transit (`#au-shrink`)**: Selisih penyusutan fisik massa selama perjalanan logistik dalam satuan kilogram dan persentase (`#au-shrink-pct`).
4. **Biochar Kembali ke Petani (`#au-biochar`)**: Total kilogram biochar yang terbukti sah telah dialokasikan kembali kepada petani produsen untuk mengonfirmasi klaim ekonomi sirkular.

#### B. Tabel Selisih Timbangan di Luar Toleransi (`#table-au-disc`)
- Membandingkan data timbangan hulu versus hilir per transaksi pengiriman.
- Mengklasifikasikan anomali logistik berdasarkan parameter `sirkular.shrinkage_tolerance_pct`:
  * Susut $\le 3,0\%$: Ditandai status normal hijau (pengurangan akibat pengeringan alami di terik matahari).
  * Susut $3,1\% - 7,0\%$: Ditandai peringatan kuning (memerlukan verifikasi durasi transit truk).
  * Susut $> 7,0\%$: Ditandai bendera merah anomali kritis (`discrepancy_flag = TRUE`). Transaksi pembayaran ditahan sementara hingga rekaman GPS supir dan kondisi fisik bak truk diaudit oleh inspektur pabrik.

---

### 3.6 Portal 6: Administrator Sistem Platform (⚙️)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [Total Pengguna: 42 Akun]   [Titik Penggilingan: 18 Titik]   [Laporan Biomassa: 128]   [Armada: 6 Truk]│
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ⚙️ Kendali Platform & Data Demo                                                                        │
│ [ 🔄 Reset & Re-seed Data Demo Lengkap ]   [ 🧪 Buka Lab 7 Engine ]   [ 👥 Buka Manajemen User ]       │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 🌾 Referensi Harga Beli Acuan Tiap Biomassa                                                            │
│ ┌───────────────┬──────────────────────┬──────────────────────┬───────────────┬──────────────────────┐ │
│ │ Kode          │ Nama Komoditas       │ Harga Acuan (Rp/kg)  │ MC Acuan (%)  │ Aksi                 │ │
│ ├───────────────┼──────────────────────┼──────────────────────┼───────────────┼──────────────────────┤ │
│ │ sekam_padi    │ Sekam Padi           │ Rp 400               │ 12.0 %        │ [Ubah Harga]         │ │
│ │ tongkol_jagung│ Tongkol Jagung       │ Rp 350               │ 14.0 %        │ [Ubah Harga]         │ │
│ │ serbuk_kayu   │ Serbuk Kayu Sengon   │ Rp 300               │ 15.0 %        │ [Ubah Harga]         │ │
│ │ tempurung_klp │ Tempurung Kelapa     │ Rp 1.200             │ 10.0 %        │ [Ubah Harga]         │ │
│ └───────────────┴──────────────────────┴──────────────────────┴───────────────┴──────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### A. Baris Kartu KPI Platform
1. **Total Pengguna (`#a-tot-users`)**: Jumlah seluruh akun persona aktif yang terdaftar dalam basis data.
2. **Titik Pemasok / Penggilingan (`#a-tot-mills`)**: Jumlah fasilitas penggilingan padi dan produsen biomassa mitra di Sleman dan Klaten.
3. **Laporan Biomassa (`#a-tot-harvests`)**: Akumulasi seluruh tiket panen biomassa yang tercatat di platform.
4. **Armada Logistik (`#a-tot-routes`)**: Jumlah rute pengangkutan truk yang telah diterbitkan dan dioperasikan.

#### B. Panel Kendali Utama
- Tombol `🔄 Reset & Re-seed Data Demo Lengkap`: Mengembalikan kondisi database ke skenario contoh baku, mengisi ulang antrean verifikasi pengepul, rute supir aktif, dan histori energi pabrik untuk keperluan demonstrasi atau pengujian regresi.
- Tombol shortcut navigasi langsung ke **Lab 7 Engine** dan **Manajemen Pengguna**.

#### C. Tabel Referensi Harga Beli Acuan Tiap Biomassa (`#table-admin-biomass-prices`)
Mengatur parameter harga dasar transaksi pembelian non-lelang untuk setiap komoditas biomassa yang menjadi acuan dasar bagi petani dan pengepul di lapangan.

---

# BAB 4: TAB LAPORAN BULANAN (GUDANG DATA & MUTU QC)

Tab **📊 Laporan Bulanan** (`#tab-reports`) menyajikan analitik rantai pasok terintegrasi berbasis gudang data tunggal (*Single Data Warehouse View*).

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 📊 Laporan Bulanan Rantai Pasok                                Dari: [ 2026-01 ] s.d. [ 2026-10 ]     │
│ Volume pasokan · konversi biomassa · efisiensi biaya           [Tampilkan]  [⬇️ CSV]  [⬇️ Excel]       │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [Total Pasokan: 342.5 Ton]  [Rata-rata Konversi: 32.4%]  [Biaya Rata-rata: Rp 468/kg] [CO₂: 284 tCO₂e] │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [Grafik Garis & Batang Chart.js: Pasokan Bulanan (Ton) vs Efisiensi Konversi (%) vs Biaya Rp/kg]       │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 🔬 Umpan Balik Mutu dari QC Pabrik & Pengepul                                                          │
│ [Skor Mutu Rata-rata: 89.2 Poin]            [Tingkat Defect (Tolak/Karantina): 3.2%]                   │
│                                                                                                        │
│ Analisis Diagram Pareto Penyebab Defect:                                                               │
│ 1. 💧 Kadar Air Terlalu Basah (>18%): 65% Kasus  ████████████████████████                             │
│ 2. 🪨 Kontaminasi Tanah & Dedak (>5%): 22% Kasus ████████                                             │
│ 3. 🍄 Terindikasi Jamur / Busuk:     13% Kasus   ████                                                 │
│                                                                                                        │
│ Definisi Metrik & Rujukan Ilmiah:                                                                      │
│ • Kimball & Ross (2013) The Data Warehouse Toolkit · ISO 50006:2014 EnPI · SCOR Model v12             │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Filter Periode & Cakupan Akses Multi-Peran
- **Pemilih Bulan Rentang (`#rp-from` s.d. `#rp-to`)**: Menggunakan input format `YYYY-MM`.
- **Cakupan Baris Otomatis Berdasarkan Peran Pengguna (RLS)**:
  * Pengguna `petani`: Hanya menampilkan ringkasan data pasokan dan pendapatan milik sendiri.
  * Pengguna `pengepul`: Menampilkan data pasokan yang dikumpulkan dan ditagihkan oleh hub gudangnya.
  * Pengguna `driver`: Menampilkan statistik jarak kilometer dan muatan yang diangkut armadanya.
  * Pengguna `pabrik`, `auditor`, dan `admin`: Menampilkan agregasi holistik seluruh rantai pasok pabrik.

---

### 4.2 Matriks KPI Utama & Tren Visualisasi Grafik
- **Total Pasokan Biomassa**: Jumlah metrik ton bahan baku yang diserap fasilitas.
- **Rata-rata Konversi Biomassa**: Rasio persentase biomassa yang berhasil dikonversi menjadi produk bermanfaat (bio-pellet, briket, biochar, dan silika).
- **Efisiensi Biaya (Cost per kg)**: Rata-rata biaya pengadaan bahan baku per kilogram termasuk biaya pembelian dan logistik.
- **Emisi CO₂ Terhindar**: Akumulasi dampak dekarbonisasi rantai pasok dalam satuan ton $CO_2\text{e}$.
- **Grafik Tren Visual (`#rp-chart`)**: Menggabungkan diagram batang (*bar chart*) untuk tonase bulanan dan diagram garis ganda (*line chart*) untuk kurva biaya dan efisiensi konversi.

---

### 4.3 Gudang Data Analitik & Ekspor Laporan
- **Tabel Data Bulanan (`#rp-table`)**: Menampilkan tabel berkolom lengkap: Bulan, Volume Masuk ($ton$), Bahan Kering Murni ($ton$), Hasil Biochar ($ton$), Hasil Silika ($ton$), Hasil Pellet ($ton$), Biaya Pembelian ($Rp$), Biaya Angkut ($Rp$), dan Biaya per kg Bersih.
- **Ekspor Dokumen**: Tombol `⬇️ CSV` dan `⬇️ Excel` mengekspor seluruh tabel analitik secara instan untuk kebutuhan audit keuangan institusi perbankan atau laporan kepatuhan emisi pemerintah.

---

### 4.4 Modul Umpan Balik Mutu QC & Analisis Pareto Defect
- Menampilkan skor mutu proksimat rata-rata bulanan dan persentase penolakan barang (*defect rate*).
- **Analisis Akar Penyebab (*Root Cause Pareto Analysis*)**: Mengidentifikasi kegagalan mutu feedstock terbesar di lapangan (misal: tingginya kadar air saat musim hujan atau kontaminasi dedak halus akibat saringan penggilingan yang aus), memberikan masukan langsung bagi tim penyuluh pertanian dan pengepul desa.

---

# BAB 5: TAB PARAMETER ASUMSI (SINGLE SOURCE OF TRUTH)

Tab **🎛️ Parameter Asumsi** (`#tab-params`) merupakan pusat kendali terpadu seluruh angka asumsi bisnis, koefisien teknis, dan ambang batas mutu di dalam sistem Bio-Chain.

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 🎛️ Parameter Asumsi Sistem                                      ⏱️ Sinkronisasi Multi-Worker ≤ 30 Detik │
│ Semua angka asumsi di setiap modul dapat diubah sesuai kondisi lapangan. Setiap perubahan tercatat.    │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Alasan Perubahan (Wajib): [ Penyesuaian harga BBM solar nonsubsidi & hasil lab batch 12             ]  │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Pilih Kelompok:                                                                                        │
│ [Harga & Mutu Sekam] [Model Rendemen] [Ekonomi Sirkular] [Logistik & Rute] [Pasar B2B] [Karbon IPCC]   │
│ [Proyeksi Pasokan]   [Insentif Petani] [Limbah ke Energi] [Energi & IKE]    [Preset Biomassa] [Pabrik]  │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Rincian Parameter Kelompok: Harga & Mutu Sekam                                                         │
│ ┌──────────────────────────────────┬──────────────┬────────┬──────────────────────┬──────────────────┐ │
│ │ Parameter                        │ Nilai Aktif  │ Satuan │ Rentang Aman         │ Aksi             │ │
│ ├──────────────────────────────────┼──────────────┼────────┼──────────────────────┼──────────────────┤ │
│ │ harga_mutu.base_price_per_kg     │ 400          │ Rp/kg  │ 1 – 10.000           │ [Simpan]         │ │
│ │ harga_mutu.moisture_best         │ 11.0         │ % bb   │ 0 – 30               │ [Simpan]         │ │
│ │ harga_mutu.moisture_reject       │ 25.0         │ % bb   │ 12 – 40              │ [Simpan]         │ │
│ │ harga_mutu.mult_A                │ 1.15         │ x      │ 0 – 3                │ [Simpan]         │ │
│ └──────────────────────────────────┴──────────────┴────────┴──────────────────────┴──────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 🕘 Riwayat Perubahan Parameter (Audit Log Imutabel)                                                    │
│ • 2026-10-12 14:20 WIB · User: pabrik_indmira                                                          │
│   Parameter: logistik.fuel_cost_per_km diubah dari Rp 3.800 ➔ Rp 4.000                                 │
│   Alasan: "Penyesuaian kenaikan harga biosolar industri di SPBU regional Sleman"                       │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 5.1 Arsitektur Registry & Protokol Audit Imutabel
- Dikelola di backend oleh berkas [`app/params.py`](file:///D:/IDE/bio-chain-prototype/app/params.py).
- **Protokol Tanpa Angka Tersembunyi (*No Hardcoded Numbers*)**: Seluruh logika algoritma membaca parameter operasional secara dinamis via fungsi pemanggil `P("nama_grup.nama_kunci")`.
- **Validasi Integritas Ketat**: Setiap perubahan nilai diuji terhadap rentang batas minimum, batas maksimum, dan konsistensi relasional (contoh: ambang kadar air penolakan `moisture_reject` wajib selalu lebih besar daripada `moisture_best`).
- **Audit Perubahan Wajib Alasan**: Pengguna pabrik/admin diwajibkan mengetikkan justifikasi alasan lapangan pada input `#pm-reason`. Perubahan dicatat permanen dalam tabel `parameter_changes` memuat stempel waktu presisi, identitas user, nilai lama, nilai baru, dan alasan.

---

### 5.2 Rincian 18 Kelompok Parameter Asumsi Bisnis
1. **Harga & Mutu Sekam (`harga_mutu`)**: Harga dasar per kg, pengali grade A/B/C, skor ambang batas grade A/B, kadar air ideal vs batas tolak, kadar abu ideal, dan bobot penilaian proksimat.
2. **Model Rendemen Biochar (`rendemen`)**: Rendemen pirolisis pada 300°C ($57,13\%$) dan 700°C ($37,19\%$), koefisien retensi abu, fraksi silika $SiO_2$ dalam abu sekam ($90\%$), serta fraksi karbon organik stabil ($C_{\text{org}} = 75\%$).
3. **Mass Balance & Ekonomi Sirkular (`sirkular`)**: Hak porsi retur biochar gratis petani ($5\%$ bobot bahan kering), batas toleransi susut transit ($3,0\%$), dan porsi pengalihan biomassa ke lini silika.
4. **Logistik & Rute (`logistik`)**: Faktor liku jalan darat (*road circuity factor* $= 1,3$), biaya solar per kilometer (Rp 4.000/km), kapasitas volume bak truk ($30\text{ m}^3$), densitas curah sekam ($110\text{ kg/m}^3$), dan kecepatan rata-rata armada.
5. **Pasar B2B (`pasar`)**: Batas maksimal uang muka lelang ($30\%$), radius batas penjemputan armada ($40\text{ km}$), dan biaya transportasi mandiri petani (Rp 80/kg).
6. **Karbon IPCC 2006 (`karbon`)**: Nilai kalor sekam ($15,0\text{ MJ/kg}$), efisiensi boiler batubara ($85\%$), nilai kalor batubara ($20,0\text{ MJ/kg}$), faktor emisi batubara ($96,1\text{ kgCO}_2\text{/GJ}$), faktor emisi solar truk ($0,15\text{ kgCO}_2\text{/ton}\cdot\text{km}$), faktor emisi jaringan listrik JAMALI ($0,87\text{ tCO}_2\text{/MWh}$), dan harga pasar sertifikat karbon per ton.
7. **Abu ke Lahan (`abu`)**: Ambang batas aman akumulasi logam berat (timbal Pb, kadmium Cd, arsen As) sesuai regulasi pupuk tanah.
8. **Proyeksi Pasokan (`proyeksi`)**: Produktivitas padi rata-rata sawah Jawa ($5,3\text{ ton/ha}$ gabah), rasio sekam terhadap gabah ($20\%$), amplitudo gelombang musiman cosinus ($0,45$), dan bulan puncak panen raya (Bulan 4 & Bulan 9).
9. **Insentif Petani (`insentif`)**: Basis poin XP per ton pengiriman, pengali mutu Grade A/B/C, bonus ketepatan waktu ($+20\%$), bonus pasokan musim paceklik ($+50\%$), ambang batas kenaikan tier, dan persentase bonus harga per tier.
10. **Limbah ke Energi (`limbah`)**: Panas laten penguapan air ($2,443\text{ MJ/kg}$), energi pengeringan termal ($3,0\text{ MJ/kg air}$), efisiensi turbin uap kecil ($22\%$), dan efisiensi mesin gasifikasi ($28\%$).
11. **Energi & IKE Pabrik (`energi`)**: Nilai kalor solar ($36,0\text{ MJ/L}$), nilai batas Intensitas Konsumsi Energi (IKE) sesuai Permen ESDM 13/2012, tarif listrik industri (Rp 1.444,70 / kWh), dan ambang batas deviasi anomali sigma.
12. **Bobot TOPSIS Feedstock (`feedstock`)**: Bobot multikriteria evaluasi kecocokan biomassa (nilai kalor, kadar air, kadar abu, ketersediaan stok, harga, dan kemudahan logistik).
13. **Blending & Spesifikasi Produk (`blending`)**: Batas maksimum kadar air, batas maksimum kadar abu, batas minimum fixed carbon, dan batas indeks alkali anti-kerak boiler ($AI \le 0,34\text{ kg/GJ}$).
14. **Preset Multi-Biomassa (`biomassa`)**: Tabel pustaka karakteristik fisik-kimia komoditas biomassa regional (Sekam padi, Tongkol jagung, Serbuk kayu sengon, Tempurung kelapa, Ampas tebu/bagasse, Cangkang sawit).
15. **Biaya Produksi Pabrik (`pabrik`)**: Tarif tenaga kerja langsung per jam, biaya listrik industri, biaya depresiasi investasi mesin pirolisis per jam operasional, dan target margin keuntungan pabrik.
16. **Target Evaluasi & Optimasi (`evaluasi`)**: Ambang batas efisiensi energi bersih (*Net Energy Ratio* / NER $> 1,0$) dan batas kepatuhan standar produk.
17. **Pajak Pembelian (`pajak`)**: Konfigurasi pemungutan PPN/PPh pasal 22 bila berlaku.
18. **Biochar untuk Sawah (`biochar_sawah`)**: Koefisien agronomi tanah sawah: rasio efisiensi substitusi pupuk urea ($kg\text{ urea per } kg\text{ biochar}$) dan kenaikan hasil panen gabah padi.

---

# BAB 6: TAB LAB ENGINE WORKBENCH (7 ENGINE MANDIRI)

Tab **🧪 Lab Engine Workbench** (`#tab-engines`) menyediakan antarmuka pengujian eksperimental langsung bagi para engineer, akademisi, dan auditor untuk mengeksplorasi model matematika dan algoritma inti sistem tanpa mengotori basis data operasional.

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 🧪 Bio-Chain Engine Workbench                                                                          │
│ Eksplorasi langsung model matematika dan algoritma inti rantai pasok multi-biomassa                     │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [② Skor Mutu & Rendemen]  [③ Blending HiGHS]  [⑤ Rute Optimal]  [⑧ Komparasi Feedstock]               │
│ [⑨ Limbah → Energi]       [⑩ Energi & IKE]    [⑫ Optimasi Multi-Produk]                                │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 6.1 Sub-Engine ②: Skor Mutu Proksimat & Kurva Rendemen (`#eng-quality`)
- **Antarmuka Input**: Kadar Air ($\% \text{ bb}$), Kontaminan ($\%$), Kadar Abu ($\% \text{ bk}$), Volatile Matter ($\%$), Fixed Carbon ($\%$), dan Suhu Pirolisis Target ($^\circ\text{C}$).
- **Antarmuka Output**:
  * Kotak hasil evaluasi: Penetapan Grade (A/B/C/Tolak), Skor Komposit Mutu (skala 0–100), Pengali Harga Rekomendasi, Prediksi Rendemen Biochar ($\%$ basis kering), Potensi Biochar per ton terima ($kg/\text{ton}$), dan Estimasi silika bio-silika $SiO_2$ murni ($kg/\text{ton}$).
  * Grafik Kurva Rendemen Interaktif: Merender kurva peluruhan rendemen biochar dari suhu $300^\circ\text{C}$ hingga $700^\circ\text{C}$ dengan penyesuaian kadar abu secara dinamis.

---

### 6.2 Sub-Engine ③: Blending Feedstock Biaya Minimum (HiGHS LP) (`#eng-blend`)
- **Tujuan**: Menentukan campuran biomassa termurah yang memenuhi spesifikasi reaktor pirolisis atau boiler industri menggunakan metode Pemrograman Linier (*Linear Programming Solver HiGHS*).
- **Antarmuka Input**:
  * Dropdown spesifikasi produk acuan (misal: *Biochar Standar EBC*, *Bio-Pellet ISO 17225*, *Co-Firing PLTU Batubara*).
  * Batas toleransi campuran: Kadar Air Maksimum ($\%$), Kadar Abu Maksimum ($\%$), dan Fixed Carbon Minimum ($\%$).
  * Target volume total batch ($ton$).
  * Tabel inventori ketersediaan stok dan harga beli per ton dari aneka biomassa yang tersedia.
- **Antarmuka Output**: Formulasi persentase campuran optimal tiap biomassa, total biaya pengadaan bahan baku, penghematan biaya dibandingkan formula konvensional, serta nilai proksimat campuran akhir yang terverifikasi memenuhi seluruh kendala spesifikasi.

---

### 6.3 Sub-Engine ⑤: Rute Logistik CVRP Berbatas Volume (`#eng-route`)
- **Tujuan**: Menyelesaikan permasalahan perutean armada kendaraan (*Capacitated Vehicle Routing Problem*) dengan memperhitungkan batasan kubikasi bak truk (*volumetric-constrained*).
- **Antarmuka Input**: Volume bak truk ($m^3$, default $30\text{ m}^3$), densitas curah sekam ($kg/m^3$, default $110\text{ kg/m}^3$), dan biaya operasional bahan bakar per kilometer (Rp 4.000/km).
- **Antarmuka Output**:
  * Ringkasan KPI: Jumlah kendaraan yang dibutuhkan, total jarak tempuh seluruh armada ($km$), total biaya logistik ($Rp$), rata-rata biaya angkut per kilogram sekam, dan total emisi $CO_2\text{e}$ armada.
  * Tabel pembagian rute per kendaraan lengkap dengan urutan titik perhentian.
  * Visualisasi peta interaktif rute jalan raya terhubung langsung ke depot pabrik.

---

### 6.4 Sub-Engine ⑧: Perbandingan Feedstock Multikriteria (TOPSIS) (`#eng-feedstock`)
- **Tujuan**: Memeringkat aneka komoditas biomassa berdasarkan kecocokan terhadap produk tujuan (Biochar, Bio-pellet, atau Pembakaran Langsung) menggunakan algoritma *Technique for Order of Preference by Similarity to Ideal Solution* (TOPSIS).
- **Antarmuka Input**: Pemilihan tujuan pemanfaatan dan penentuan harga beli aktual per ton komoditas.
- **Antarmuka Output**:
  * Nilai Kalor Atas (HHV Parikh et al. 2005) dan Nilai Kalor Bawah (LHV basis diterima).
  * Matriks normalisasi berbobot multikriteria.
  * Skor preferensi kedekatan relatif ($C_i$) dan tabel peringkat rekomendasi komoditas terbaik.

---

### 6.5 Sub-Engine ⑨: Penasihat Limbah-ke-Energi (*Waste-to-Energy*) (`#eng-waste`)
- **Tujuan**: Memberikan rekomendasi teknologi konversi termokimia vs biokimia berdasarkan pohon keputusan ilmiah McKendry (2002) dan Basu (2018).
- **Antarmuka Input**: Karakteristik limbah organik (Volume ton/hari, Hari operasi per tahun, Kadar air, Kadar abu, dan Rasio C/N).
- **Antarmuka Output**:
  * Identifikasi rute konversi prioritas: Pirolisis lambat, Gasifikasi, Anaerobic Digestion (Biogas), atau Pembakaran Langsung (*Incineration / Co-Firing*).
  * Potensi output energi: Panas proses ($GJ/\text{tahun}$), Listrik bersih ($MWh/\text{tahun}$), Biogas metana ($m^3\text{ }CH_4/\text{tahun}$), atau Biochar padat ($ton/\text{tahun}$).

---

### 6.6 Sub-Engine ⑩: Analisis Konsumsi Energi & Kriteria IKE ESDM (`#eng-energy`)
- **Tujuan**: Memantau Konsumsi Energi Spesifik (*Specific Energy Consumption* / SEC) dan Intensitas Konsumsi Energi (IKE) fasilitas pabrik sesuai regulasi Permen ESDM No. 13/2012 dan ISO 50006:2023.
- **Antarmuka Input**: Pemilihan fasilitas pabrik untuk menarik histori log energi dari basis data.
- **Antarmuka Output**:
  * Matriks KPI: Rata-rata SEC ($kWh/\text{ton}$ atau $MJ/\text{ton}$), Nilai IKE ($kWh/m^2\cdot\text{tahun}$), Kategori Efisiensi (Sangat Efisien, Efisien, Cukup Efisien, atau Boros).
  * Grafik tren SEC versus garis batas model regresi acuan (*Energy Baseline* / EnB).
  * Deteksi Titik Anomali Pemborosan: Menggunakan algoritma *Robust Z-Score* (Iglewicz & Hoaglin 1993) dan diagram kendali CUSUM (*Cumulative Sum*) untuk mendeteksi degradasi mesin atau kebocoran termal.
  * Rekomendasi audit energi aksi perbaikan terstruktur.

---

### 6.7 Sub-Engine ⑫: Optimasi Konversi Multi-Produk Hilir (`#eng-opt`)
- **Tujuan**: Evaluasi komparatif 4 produk akhir bernilai tinggi (Bio-Pellet ISO 17225, Briket Arang SNI 01-6235, Biochar Pembenah Tanah EBC/IBI, dan Bio-Silika Presipitasi SNI 15-0086) serta solver optimasi alokasi inventori pabrik.
- **Mode 1: Evaluasi Lot Komparatif**: Memasukkan parameter satu lot biomassa umpan ($kg$, kadar air, harga beli). Sistem membedah neraca massa, kebutuhan energi pengeringan, biaya HPP, potensi pendapatan, margin kotor, dan kelayakan teknis terhadap keempat produk secara berdampingan (*side-by-side comparison*).
- **Mode 2: Solver Alokasi Stok Pabrik (HiGHS LP)**: Mengalokasikan seluruh inventori gudang biomassa ke berbagai lini mesin konversi pabrik guna mencapai satu dari 4 tujuan strategis:
  1. *Maksimalkan Laba Bersih (Max Profit)*.
  2. *Maksimalkan Produksi Energi Bersih (Max Energy Output GJ)*.
  3. *Maksimalkan Penyerapan Karbon (Max Net Carbon Sink tCO₂e)*.
  4. *Portofolio Berimbang (Balanced Multi-Criteria)*.

---

# BAB 7: MEKANISME DAN FORMULA MATEMATIS KELUAR ANGKA STEP-BY-STEP

Bab ini menjabarkan secara terperinci setiap mekanisme kalkulasi, persamaan matematis, variabel penentu, serta contoh perhitungan numerik langkah demi langkah (*worked example*) untuk seluruh angka yang tampil di website Bio-Chain.

---

### 7.1 Mekanisme 1: Skor Mutu Proksimat, Penalti & Penentuan Grade (Engine ②)

#### A. Landasan Persamaan Matematis
Dikelola oleh [`app/engines/quality.py`](file:///D:/IDE/bio-chain-prototype/app/engines/quality.py). Penilaian mutu mengevaluasi 4 parameter uji proksimat menggunakan fungsi interpolasi linier clamped:

$$\text{linear\_score}(v, v_{\text{best}}, v_{\text{worst}}) = \text{clamp}\left(100 \times \frac{v_{\text{worst}} - v}{v_{\text{worst}} - v_{\text{best}}}, 0, 100\right)$$

1. **Skor Kadar Air ($S_M$)**:
   - $M_{\text{best}} = 11,0\%$, $M_{\text{reject}} = 25,0\%$.
   $$S_M = \text{clamp}\left(100 \times \frac{25,0 - M}{25,0 - 11,0}, 0, 100\right)$$
2. **Skor Kontaminasi Kotoran ($S_K$)**:
   - $K_{\text{best}} = 0,0\%$, $K_{\text{reject}} = 10,0\%$.
   $$S_K = \text{clamp}\left(100 \times \frac{10,0 - K}{10,0 - 0,0}, 0, 100\right)$$
3. **Skor Kadar Abu ($S_A$)**:
   - Abu ideal berada di antara $A_{\text{min}} = 15,0\%$ dan $A_{\text{max}} = 20,0\%$.
   $$S_A = \text{clamp}\left(100 - 10 \times \max(0, A - 20,0, 15,0 - A), 0, 100\right)$$
4. **Skor Karbon Tertambat ($S_{FC}$)**:
   - $FC_{\text{best}} = 18,0\%$, $FC_{\text{worst}} = 10,0\%$.
   $$S_{FC} = \text{clamp}\left(100 \times \frac{FC - 10,0}{18,0 - 10,0}, 0, 100\right)$$

**Skor Komposit Akhir Mutu ($S$)**:

$$S = \frac{w_M \cdot S_M + w_K \cdot S_K + w_A \cdot S_A + w_{FC} \cdot S_{FC}}{w_M + w_K + w_A + w_{FC}}$$

*Bobot default*: $w_M = 0,35$, $w_K = 0,25$, $w_A = 0,20$, $w_{FC} = 0,20$. Jika uji abu dan FC tidak diukur di lapangan, pembagi bobot dinormalisasi otomatis hanya atas $w_M + w_K$.

**Aturan Penentuan Grade**:
- Jika $M > 25,0\%$ ATAU $K > 10,0\% \implies \mathbf{TOLAK}$ (Skor $= 0$, Pengali Harga $= 0,0$).
- Jika $S \ge 80,0 \implies \mathbf{Grade\text{ }A}$ (Pengali Harga $= \times 1,15$).
- Jika $S \ge 65,0 \implies \mathbf{Grade\text{ }B}$ (Pengali Harga $= \times 1,05$).
- Jika $S < 65,0 \implies \mathbf{Grade\text{ }C}$ (Pengali Harga $= \times 1,00$).

#### B. Contoh Perhitungan Numerik Langkah demi Langkah
*Input Sampel Lapangan*:
- Kadar Air $M = 12,5\%$, Kontaminan $K = 1,0\%$, Kadar Abu $A = 18,0\%$, Fixed Carbon $FC = 16,0\%$.

*Langkah 1: Hitung masing-masing sub-skor*:
- $S_M = 100 \times \frac{25,0 - 12,5}{25,0 - 11,0} = 100 \times \frac{12,5}{14,0} = 89,29$ poin.
- $S_K = 100 \times \frac{10,0 - 1,0}{10,0 - 0,0} = 100 \times \frac{9,0}{10,0} = 90,00$ poin.
- $S_A = 100 - 10 \times \max(0, 18,0 - 20,0, 15,0 - 18,0) = 100 - 0 = 100,00$ poin (sempurna dalam rentang ideal).
- $S_{FC} = 100 \times \frac{16,0 - 10,0}{18,0 - 10,0} = 100 \times \frac{6,0}{8,0} = 75,00$ poin.

*Langkah 2: Hitung skor komposit berbobot*:
$$S = (0,35 \times 89,29) + (0,25 \times 90,00) + (0,20 \times 100,00) + (0,20 \times 75,00)$$
$$S = 31,25 + 22,50 + 20,00 + 15,00 = \mathbf{88,75\text{ poin}} \implies \mathbf{88,8}$$

*Langkah 3: Evaluasi ambang batas*:
- Karena $S = 88,8 \ge 80,0$, sampel ditetapkan sebagai **Grade A**.
- Pengali harga yang berlaku adalah **$\times 1,15$**.

---

### 7.2 Mekanisme 2: Prediksi Rendemen Biochar terhadap Suhu Pirolisis & Koreksi Abu

#### A. Landasan Persamaan Matematis
Model empiris pirolisis lambat sekam padi (*slow pyrolysis*) dikalibrasi dari data termal literatur:
- Pada suhu $T = 300^\circ\text{C}$, rendemen biochar basis kering adalah $Y_{300} = 57,13\%$.
- Pada suhu $T = 700^\circ\text{C}$, rendemen biochar basis kering adalah $Y_{700} = 37,19\%$.

Persamaan interpolasi linier terhadap suhu reaktor $T$ ($^\circ\text{C}$):

$$Y_{\text{base}}(T) = Y_{300} - (Y_{300} - Y_{700}) \times \frac{T - 300}{700 - 300} = 57,13 - 19,94 \times \frac{T - 300}{400}$$

Karena mineral anorganik (abu) bersifat inert dan tertahan di dalam struktur padatan arang selama pirolisis, kadar abu yang lebih tinggi menaikkan bobot rendemen padat:

$$Y(T, A) = \text{clamp}\left(Y_{\text{base}}(T) + C_{\text{ash}} \times (A - A_{\text{ref}}), 20, 75\right)$$

*Di mana*: Koefisien koreksi abu $C_{\text{ash}} = 0,5$, kadar abu acuan $A_{\text{ref}} = 18,0\%$.

**Potensi Hasil Produk per Ton Biomassa Diterima ($W_{\text{terima}} = 1.000\text{ kg}$)**:
- Faktor Bahan Kering Murni (*Dry Ash-Free Factor*):
  $$F_{\text{dry}} = \left(1 - \frac{M}{100}\right) \times \left(1 - \frac{K}{100}\right)$$
- Output Biochar per Ton Umpan:
  $$W_{\text{biochar}} = 1.000 \times F_{\text{dry}} \times \frac{Y(T, A)}{100}\text{ [kg/ton]}$$
- Kandungan Abu dalam Biochar:
  $$\% A_{\text{char}} = \text{clamp}\left(\frac{A}{Y(T, A)} \times 100, 0, 95\right)\%$$
- Potensi Bio-Silika Amorf Murni ($SiO_2$ fraksi dalam abu $= 90\%$):
  $$W_{SiO_2} = 1.000 \times F_{\text{dry}} \times \frac{A}{100} \times 0,90\text{ [kg/ton]}$$

#### B. Contoh Perhitungan Numerik Langkah demi Langkah
*Input Operasi Pabrik*: Suhu pirolisis $T = 500^\circ\text{C}$, Abu $A = 18,0\%$, Kadar Air $M = 12,0\%$, Kontaminan $K = 1,0\%$.

*Langkah 1: Hitung rendemen basis kering*:
- $Y_{\text{base}}(500) = 57,13 - 19,94 \times \frac{500 - 300}{400} = 57,13 - (19,94 \times 0,5) = 57,13 - 9,97 = 47,16\%$.
- Koreksi abu: Karena $A = 18,0\% = A_{\text{ref}}$, maka koreksi abu $= 0,5 \times (18 - 18) = 0$.
- Rendemen biochar basis kering $Y = \mathbf{47,16\%}$.

*Langkah 2: Hitung faktor bahan kering umpan*:
- $F_{\text{dry}} = (1 - 0,12) \times (1 - 0,01) = 0,88 \times 0,99 = 0,8712$.

*Langkah 3: Hitung kuantitas produk jadi per 1.000 kg umpan*:
- Output Biochar $= 1.000 \times 0,8712 \times 0,4716 = \mathbf{410,9\text{ kg biochar/ton}}$.
- Kadar Abu dalam Biochar $= \frac{18,0}{47,16} \times 100 = \mathbf{38,17\%}$.
- Output Bio-Silika Murni $= 1.000 \times 0,8712 \times \frac{18,0}{100} \times 0,90 = \mathbf{141,1\text{ kg } SiO_2\text{/ton}}$.

---

### 7.3 Mekanisme 3: Harga Beli Lapangan Petani & Refraksi Kadar Air Kontinu

#### A. Landasan Persamaan Matematis
Dikelola di `farmgate_price()` dalam [`app/engines/quality.py`](file:///D:/IDE/bio-chain-prototype/app/engines/quality.py).
Untuk mencegah ketidakadilan pasar akibat sistem "tebing harga" (*price cliffs*) di mana perbedaan kadar air 0,1% dapat menurunkan harga secara drastis, Bio-Chain menerapkan penyesuaian harga proporsional berbasis bahan kering murni (*Dry Basis Equivalence*):

$$P_{\text{bayar}} = P_{\text{dasar}} \times \frac{100\% - M}{100\% - M_{\text{acuan}}}$$

Di mana:
- $P_{\text{dasar}}$: Harga patokan komoditas (misal: Rp 400 / kg).
- $M$: Kadar air aktual hasil uji timbang lapangan (%).
- $M_{\text{acuan}}$: Kadar air standar kontrak acuan (default $= 12,0\%$).

**Bobot Bersih yang Dibayar (*Payable Weight*)**:
Benda asing/kontaminan (batu, tanah, plastik) tidak dibayar:

$$W_{\text{bayar}} = W_{\text{timbang}} \times \left(1 - \frac{K}{100}\right)$$

**Total Pendapatan Petani**:

$$\text{Total Transaksi (Rp)} = W_{\text{bayar}} \times P_{\text{bayar}}$$

*Catatan*: Bila petani memilih skema "Antar Mandiri", pendapatan ditambahkan premi logistik mandiri:
$$\text{Total Diterima} = (W_{\text{bayar}} \times P_{\text{bayar}}) + (W_{\text{timbang}} \times \text{Premi}_{\text{antar}})$$
Di mana $\text{Premi}_{\text{antar}} = \text{Rp } 80\text{ / kg}$.

#### B. Contoh Perhitungan Numerik Langkah demi Langkah
*Kasus Transaksi*: Petani Sugeng menyetorkan $W_{\text{timbang}} = 2.500\text{ kg}$ sekam dengan kadar air $M = 14,0\%$ dan kontaminan dedak $K = 2,0\%$. Harga dasar acuan $P_{\text{dasar}} = \text{Rp } 400\text{ / kg}$, $M_{\text{acuan}} = 12,0\%$. Skema penyerahan: Dijemput.

*Langkah 1: Hitung penyesuaian harga per kg*:
$$P_{\text{bayar}} = 400 \times \frac{100 - 14,0}{100 - 12,0} = 400 \times \frac{86,0}{88,0} = 400 \times 0,97727 = \mathbf{Rp\text{ }390,91\text{ / kg}}$$

*Langkah 2: Hitung bobot bersih yang dibayar*:
$$W_{\text{bayar}} = 2.500 \times (1 - 0,02) = 2.500 \times 0,98 = \mathbf{2.450,0\text{ kg}}$$

*Langkah 3: Hitung total uang yang diterima petani*:
$$\text{Total Bayar} = 2.450,0 \times 390,91 = \mathbf{Rp\text{ }957.730}$$

*(Bandingkan jika sekam kering sempurna pada $M = 11,0\%$):*
- $P_{\text{bayar}} = 400 \times \frac{89,0}{88,0} = \text{Rp } 404,55\text{ / kg}$ (Petani mendapat bonus otomatis karena menyetor bahan kering lebih banyak!).

---

### 7.4 Mekanisme 4: Timbang Terima Gerbang Pabrik & Ekivalensi Bahan Kering (*Weighbridge QC*)

#### A. Landasan Persamaan Matematis
Dikelola di modul QC pabrik [`app/routers/factory_api.py`](file:///D:/IDE/bio-chain-prototype/app/routers/factory_api.py):
1. **Bobot Diterima Bersih (*Net Received Weight*)**:
   $$W_{\text{terima}} = W_{\text{bruto}} - W_{\text{tara}}$$
2. **Koreksi Susut Transit (*Transit Shrinkage*)**:
   $$\text{Susut Bobot } (\%) = \frac{W_{\text{kirim pengepul}} - W_{\text{terima pabrik}}}{W_{\text{kirim pengepul}}} \times 100\%$$
3. **Ekivalensi Tagihan Bahan Kering Pabrik (*Payable Weight Dry Basis*)**:
   $$W_{\text{tagihan pabrik}} = W_{\text{terima}} \times \frac{100\% - M_{\text{lab}}}{100\% - M_{\text{kontrak}}} \times \left(1 - \frac{K_{\text{lab}}}{100}\right)$$

#### B. Contoh Perhitungan Numerik Langkah demi Langkah
*Kasus Truk Tiba di Pabrik Indmira*:
- Truk bermuatan menimbang di jembatan timbang: $W_{\text{bruto}} = 8.450\text{ kg}$.
- Truk kosong setelah bongkar menimbang tara: $W_{\text{tara}} = 4.200\text{ kg}$.
- Dokumen jalan pengepul mencatat kirim: $W_{\text{kirim}} = 4.350\text{ kg}$.
- Hasil uji laboratorium cepat halogen analyzer: Kadar air $M_{\text{lab}} = 13,0\%$, kontaminan $K_{\text{lab}} = 0,5\%$. Acuan kontrak pabrik $M_{\text{kontrak}} = 12,0\%$. Harga kontrak yang disepakati $= \text{Rp } 520\text{ / kg}$.

*Langkah 1: Hitung bobot bersih diterima*:
$$W_{\text{terima}} = 8.450 - 4.200 = \mathbf{4.250\text{ kg}}$$

*Langkah 2: Hitung persentase susut perjalanan*:
$$\text{Susut} = \frac{4.350 - 4.250}{4.350} \times 100\% = \frac{100}{4.350} \times 100\% = \mathbf{2,30\%}$$
*(Nilai $2,30\% \le 3,0\%$ toleransi standar, status diterima normal tanpa investigasi).*

*Langkah 3: Hitung bobot tagihan setara bahan kering*:
$$W_{\text{tagihan}} = 4.250 \times \frac{100 - 13,0}{100 - 12,0} \times (1 - 0,005) = 4.250 \times \frac{87,0}{88,0} \times 0,995$$
$$W_{\text{tagihan}} = 4.250 \times 0,988636 \times 0,995 = 4.201,7 \times 0,995 = \mathbf{4.180,7\text{ kg}}$$

*Langkah 4: Hitung nilai tagihan pelunasan ke pengepul*:
$$\text{Total Dibayar Pabrik} = 4.180,7\text{ kg} \times \text{Rp } 520\text{ / kg} = \mathbf{Rp\text{ }2.173.964}$$

---

### 7.5 Mekanisme 5: Gamifikasi Petani, Poin XP & Multiplier Bonus Tier (Engine ⑥)

#### A. Landasan Persamaan Matematis
Dikelola oleh [`app/engines/incentive.py`](file:///D:/IDE/bio-chain-prototype/app/engines/incentive.py):

$$\text{Basis XP} = \text{Kuantitas (ton)} \times \text{Multiplier Grade} \times 10$$

Di mana multiplier grade adalah:
- Grade A: $1,0$ (XP penuh).
- Grade B: $0,7$.
- Grade C: $0,4$.
- Grade Tolak: $0,0$.

**Faktor Pengali Bonus Event ($M_{\text{event}}$)**:

$$M_{\text{event}} = 1,0 + B_{\text{waktu}} + B_{\text{paceklik}}$$
- Bonus tepat waktu (*on-time delivery*): $B_{\text{waktu}} = +0,20$ ($+20\%$).
- Bonus pasokan musim paceklik (*lean season supply*): $B_{\text{paceklik}} = +0,50$ ($+50\%$).

$$\text{XP Diperoleh} = \lfloor \text{Basis XP} \times M_{\text{event}} \rfloor$$
$$\text{XP Total Baru} = \text{XP Total Lama} + \text{XP Diperoleh}$$

**Ambang Batas Tier Loyalitas & Bonus Harga Jual**:
| Tingkatan Tier | Rentang Poin XP | Bonus Pengali Harga Penjualan |
| :--- | :--- | :--- |
| **Pemula** | 0 – 99 XP | $\times 1,00$ (Tanpa bonus) |
| **Pemasok Aktif** | 100 – 499 XP | $\times 1,05$ (+5% premi harga) |
| **Mitra Emas** | 500 – 1.499 XP | $\times 1,12$ (+12% premi harga) |
| **Mitra Platinum** | $\ge 1.500\text{ XP}$ | $\times 1,20$ (+20% premi harga) |

#### B. Contoh Perhitungan Numerik Langkah demi Langkah
*Kasus Transaksi*: Petani Sugeng memiliki XP lama $= 480\text{ XP}$ (Tier Pemasok Aktif). Ia mengirimkan $2.500\text{ kg}$ ($2,5\text{ ton}$) sekam berkualitas **Grade A**, tepat waktu sesuai jadwal, pada masa musim paceklik.

*Langkah 1: Hitung basis XP*:
$$\text{Basis XP} = 2,5 \times 1,0 \times 10 = 25\text{ poin}$$

*Langkah 2: Hitung pengali bonus event*:
$$M_{\text{event}} = 1,0 + 0,20 + 0,50 = 1,70$$

*Langkah 3: Hitung XP yang diperoleh*:
$$\text{XP Diperoleh} = \lfloor 25 \times 1,70 \rfloor = \lfloor 42,5 \rfloor = \mathbf{42\text{ XP}}$$

*Langkah 4: Akumulasi total XP baru & evaluasi kenaikan tier*:
$$\text{XP Total Baru} = 480 + 42 = \mathbf{522\text{ XP}}$$
- Karena $522\text{ XP} \ge 500\text{ XP}$, status Petani Sugeng **naik peringkat otomatis menjadi Mitra Emas**!
- Pada penjualan berikutnya, ia berhak menerima pengali bonus harga loyalitas sebesar **$\times 1,12$**.

---

### 7.6 Mekanisme 6: Hak Dompet Biochar & Pembagian Konservatif (*Largest Remainder*)

#### A. Landasan Persamaan Matematis
Setiap batch pirolisis pabrik yang memproses kumpulan sekam dari beberapa petani menghasilkan hak retur biochar gratis ke dompet petani sebesar $5\%$ dari bobot bahan kering sekam yang diserahkan:

$$W_{\text{retur pool}} = \sum_{i=1}^n \left(W_{\text{kering }, i} \times 0,05\right)\text{ [gram]}$$

Untuk membagikan $W_{\text{retur pool}}$ secara adil dan tepat hingga satuan gram tanpa ada pembulatan yang hilang (menjamin konservasi massa mutlak $100\%$), sistem menerapkan algoritma kuota **Hare-Niemeyer (*Largest Remainder Method*)**:

1. Hitung kuota eksak petani $i$ (dalam satuan gram):
   $$q_i = W_{\text{retur pool}} \times \frac{W_{\text{kering }, i}}{\sum W_{\text{kering}}}$$
2. Berikan alokasi bilangan bulat ke bawah (*integer floor*):
   $$a_i = \lfloor q_i \rfloor$$
3. Hitung sisa pecahan desimal:
   $$r_i = q_i - a_i$$
4. Hitung sisa gram yang belum terbagi:
   $$\Delta = W_{\text{retur pool}} - \sum_{i=1}^n a_i$$
5. Urutkan seluruh petani berdasarkan nilai $r_i$ terbesar ke terkecil. Berikan $+1\text{ gram}$ kepada $\Delta$ petani teratas.
6. **Invarian Terbukti**: $\sum_{i=1}^n \text{Alokasi Akhir}_i \equiv W_{\text{retur pool}}$.

#### B. Contoh Perhitungan Numerik Langkah demi Langkah
*Kasus Batch Pirolisis*: Sebuah batch memproses sekam dari 3 petani dengan total biochar dialokasikan sebesar $W_{\text{retur pool}} = 10.000\text{ gram}$ ($10\text{ kg}$).
- Petani A menyumbang: $4.520\text{ kg bahan kering}$ ($45,20\%$).
- Petani B menyumbang: $3.310\text{ kg bahan kering}$ ($33,10\%$).
- Petani C menyumbang: $2.170\text{ kg bahan kering}$ ($21,70\%$).
- Total sekam batch $= 10.000\text{ kg}$.

*Langkah 1: Hitung kuota desimal eksak*:
- $q_A = 10.000 \times \frac{4.520}{10.000} = 4.520,0\text{ gram}$.
- $q_B = 10.000 \times \frac{3.310}{10.000} = 3.310,0\text{ gram}$.
- $q_C = 10.000 \times \frac{2.170}{10.000} = 2.170,0\text{ gram}$.

*(Misalkan pada rasio pecahan lain di mana kuota menghasilkan desimal):*
- $q_A = 4.520,6\text{ gram} \implies a_A = 4.520$, $r_A = 0,6$.
- $q_B = 3.310,7\text{ gram} \implies a_B = 3.310$, $r_B = 0,7$.
- $q_C = 2.168,7\text{ gram} \implies a_C = 2.168$, $r_C = 0,7$.
- Total bagian bulat $= 4.520 + 3.310 + 2.168 = 9.998\text{ gram}$.
- Sisa gram belum terbagi $\Delta = 10.000 - 9.998 = \mathbf{2\text{ gram}}$.
- Urutan sisa pecahan terbesar: Petani B ($0,7$), Petani C ($0,7$), lalu Petani A ($0,6$).
- Tambahkan $+1\text{ gram}$ ke Petani B dan Petani C:
  * Petani B menerima: $3.310 + 1 = \mathbf{3.311\text{ gram}}$ ($3,311\text{ kg}$).
  * Petani C menerima: $2.168 + 1 = \mathbf{2.169\text{ gram}}$ ($2,169\text{ kg}$).
  * Petani A menerima: $\mathbf{4.520\text{ gram}}$ ($4,520\text{ kg}$).
- Total teralokasi $= 4.520 + 3.311 + 2.169 = \mathbf{10.000\text{ gram}}$ (Presisi 100% sempurna).

---

### 7.7 Mekanisme 7: Penetapan Harga Beli Dinamis Pabrik (*Netback Pricing Engine*)

#### A. Landasan Persamaan Matematis
Dikelola oleh [`app/engines/factory_econ.py`](file:///D:/IDE/bio-chain-prototype/app/engines/factory_econ.py):
1. **Nilai Realisasi Bruto Hilir per kg Biomassa ($R_{\text{gross}}$)**:
   $$R_{\text{gross}} = \left(Y_{\text{pellet}} \cdot P_{\text{pellet}} + Y_{\text{biochar}} \cdot P_{\text{biochar}} + Y_{\text{silika}} \cdot P_{\text{silika}}\right) \times (1 - K)$$
   Di mana $Y_p$ adalah rendemen per kg umpan, $P_p$ adalah harga jual pasar produk hilir, dan $K$ adalah fraksi kontaminan.
2. **Biaya Variabel Produksi per kg ($C_{\text{var}}$)**:
   $$C_{\text{var}} = C_{\text{listrik}} + C_{\text{kimia silika}} + C_{\text{tenaga kerja langsung}}$$
3. **Biaya Tetap per kg ($C_{\text{fixed}}$)**:
   $$C_{\text{fixed}} = \frac{\text{Depresiasi Mesin Tahunan} + \text{Gaji Tetap} + \text{Overhead}}{\text{Volume Kapasitas Tahunan (kg)}}$$

**Tiga Batas Harga Pembelian Bahan Baku**:
- **Harga Plafon (*Ceiling Price*)**: Batas impas penuh (*Break-Even Point* / BEP):
  $$P_{\text{ceiling}} = R_{\text{gross}} - C_{\text{var}} - C_{\text{fixed}}$$
- **Harga Lantai (*Floor Price*)**: Batas kelayakan operasional jangka pendek:
  $$P_{\text{floor}} = R_{\text{gross}} - C_{\text{var}}$$
- **Harga Target Rekomendasi (*Target Price*)**: Mempertahankan margin laba pabrik $m$ (misal $15\%$):
  $$P_{\text{target}} = P_{\text{ceiling}} - (m \times R_{\text{gross}})$$

#### B. Contoh Perhitungan Numerik Langkah demi Langkah
*Parameter Pabrik*:
- Dari 1 kg sekam dihasilkan: $0,30\text{ kg biochar}$ (@Rp 3.500/kg) dan $0,04\text{ kg bio-silika}$ (@Rp 28.000/kg).
- Biaya variabel per kg umpan $C_{\text{var}} = \text{Rp } 420\text{ / kg}$.
- Biaya tetap per kg umpan $C_{\text{fixed}} = \text{Rp } 110\text{ / kg}$.
- Target margin pabrik $m = 10\%$. Kontaminan $K = 0\%$.

*Langkah 1: Hitung nilai bruto produk hilir per kg sekam*:
$$R_{\text{gross}} = (0,30 \times 3.500) + (0,04 \times 28.000) = 1.050 + 1.120 = \mathbf{Rp\text{ }2.170\text{ / kg sekam}}$$

*Langkah 2: Hitung batas-batas harga*:
- **Harga Lantai**: $P_{\text{floor}} = 2.170 - 420 = \mathbf{Rp\text{ }1.750\text{ / kg}}$.
- **Harga Plafon (BEP)**: $P_{\text{ceiling}} = 2.170 - 420 - 110 = \mathbf{Rp\text{ }1.640\text{ / kg}}$.
- **Harga Target Rekomendasi**:
  $$P_{\text{target}} = 1.640 - (0,10 \times 2.170) = 1.640 - 217 = \mathbf{Rp\text{ }1.423\text{ / kg}}$$

---

### 7.8 Mekanisme 8: Optimasi Campuran Biomassa Biaya Terendah & Indeks Alkali Slagging (Engine ③)

#### A. Landasan Persamaan Matematis
Dikelola oleh [`app/engines/blending.py`](file:///D:/IDE/bio-chain-prototype/app/engines/blending.py) dan [`app/engines/fuel_blend.py`](file:///D:/IDE/bio-chain-prototype/app/engines/fuel_blend.py):

$$\min_{\mathbf{x}} \sum_{i=1}^n c_i \cdot x_i$$
Dengan kendala linier (*Linear Constraints*):
1. $\sum_{i=1}^n x_i = 1$ (Konservasi fraksi massa total).
2. $\sum_{i=1}^n M_i \cdot x_i \le M_{\text{max}}$ (Batas kadar air campuran).
3. $\sum_{i=1}^n A_i \cdot x_i \le A_{\text{max}}$ (Batas kadar abu campuran).
4. $\sum_{i=1}^n FC_i \cdot x_i \ge FC_{\text{min}}$ (Batas minimum fixed carbon).
5. $0 \le x_i \le \frac{\text{Stok Tersedia}_i}{\text{Kebutuhan Total}}$ (Batas kapasitas gudang).

**Evaluasi Risiko Kerak / Terak Boiler (*Alkali Index Slagging Risk*)**:

$$AI = \frac{A_{\text{db}} \times (K_2O + Na_2O)}{10 \times HHV_{\text{db}}}\text{ [kg/GJ]}$$
- Jika $AI < 0,17\text{ kg/GJ} \implies \mathbf{Rendah}$ (Aman untuk boiler PLTU).
- Jika $0,17 \le AI \le 0,34\text{ kg/GJ} \implies \mathbf{Sedang}$ (Dapat diterima dengan pembersihan berkala).
- Jika $AI > 0,34\text{ kg/GJ} \implies \mathbf{Tinggi / Kritis}$ (Risiko slagging berat; wajib dicampur dengan biomassa berabu rendah seperti serbuk kayu).

#### B. Contoh Perhitungan Numerik Langkah demi Langkah
*Kasus Blending*: Formulasi 1.000 ton bahan bakar briket dengan batas abu $\le 10,0\%$.
- Feedstock 1: Sekam padi ($c_1 = \text{Rp } 400.000/\text{ton}$, abu $A_1 = 18,0\%$).
- Feedstock 2: Serbuk kayu sengon ($c_2 = \text{Rp } 600.000/\text{ton}$, abu $A_2 = 2,0\%$).

*Penyelesaian SPL*:
$$\begin{cases} x_1 + x_2 = 1 \\ 18,0 \cdot x_1 + 2,0 \cdot x_2 \le 10,0 \end{cases}$$
Substitusikan $x_2 = 1 - x_1$:
$$18 x_1 + 2(1 - x_1) \le 10 \implies 16 x_1 + 2 \le 10 \implies 16 x_1 \le 8 \implies x_1 \le 0,50$$

*Formulasi Biaya Terendah*:
- $x_1 = 0,50$ ($50\%$ Sekam padi $= 500\text{ ton}$).
- $x_2 = 0,50$ ($50\%$ Serbuk kayu $= 500\text{ ton}$).
- Kadar abu campuran $= (0,5 \times 18) + (0,5 \times 2) = 9,0 + 1,0 = \mathbf{10,0\%}$ (Tepat pada batas toleransi).
- Biaya campuran $= (0,5 \times 400.000) + (0,5 \times 600.000) = \mathbf{Rp\text{ }500.000\text{ / ton}}$.

---

### 7.9 Mekanisme 9: Jarak Matriks Jalan, Batas Volumetrik Truk & Algoritma Rute CVRP (Engine ⑤)

#### A. Landasan Persamaan Matematis
Dikelola oleh [`app/engines/routing.py`](file:///D:/IDE/bio-chain-prototype/app/engines/routing.py):
1. **Jarak Matriks Jalan Raya (*Road Network Distance*)**:
   Menggunakan rumus Haversine bola bumi yang dikalikan dengan faktor kelokan jalan darat (*road factor*):
   $$\Delta\sigma = 2 \arcsin \sqrt{\sin^2\left(\frac{\Delta\phi}{2}\right) + \cos\phi_1 \cos\phi_2 \sin^2\left(\frac{\Delta\lambda}{2}\right)}$$
   $$D_{\text{jalan}}(i, j) = 2 \cdot R_{\text{earth}} \cdot \arcsin(\sqrt{h}) \times f_{\text{road}}$$
   Di mana $R_{\text{earth}} = 6.371,0\text{ km}$, $f_{\text{road}} = 1,3$.
2. **Kapasitas Muat Volumetrik (*Volumetric Bottleneck*)**:
   Karena densitas curah sekam sangat ringan ($\rho = 110\text{ kg/m}^3$), bak truk penuh secara ruang jauh sebelum batas tonase izin jalan tercapai:
   $$Q_{\text{maks berat}} = V_{\text{bak}} \times \rho = 30\text{ m}^3 \times 110\text{ kg/m}^3 = \mathbf{3.300\text{ kg}} = \mathbf{3,3\text{ ton}}$$
3. **Matriks Penghematan Clarke-Wright (*Clarke-Wright Savings*)**:
   Untuk menggabungkan perhentian $i$ dan $j$ dari depot pabrik $0$:
   $$s(i, j) = D(0, i) + D(0, j) - D(i, j)$$

#### B. Contoh Perhitungan Numerik Langkah demi Langkah
*Dua Lokasi Petani*:
- Jarak Pabrik $\to$ Petani A: $D(0, A) = 15,0\text{ km}$.
- Jarak Pabrik $\to$ Petani B: $D(0, B) = 18,0\text{ km}$.
- Jarak Petani A $\to$ Petani B: $D(A, B) = 8,0\text{ km}$.
- Muatan Petani A $= 1,5\text{ ton}$ ($13,6\text{ m}^3$). Muatan Petani B $= 1,2\text{ ton}$ ($10,9\text{ m}^3$).

*Langkah 1: Uji kelayakan kapasitas gabungan*:
- Total muatan $= 1,5 + 1,2 = 2,7\text{ ton} \le 3,3\text{ ton}$ (Muat dalam 1 truk!).
- Total volume $= 13,6 + 10,9 = 24,5\text{ m}^3 \le 30,0\text{ m}^3$ (Utilisasi bak $= 81,7\%$).

*Langkah 2: Hitung penghematan jarak Clarke-Wright*:
$$s(A, B) = 15,0 + 18,0 - 8,0 = \mathbf{25,0\text{ km}}$$
- Rute terpisah (2 trip): $(2 \times 15) + (2 \times 18) = 30 + 36 = 66,0\text{ km}$.
- Rute gabungan (1 trip): $0 \to A \to B \to 0 = 15 + 8 + 18 = \mathbf{41,0\text{ km}}$.
- Penghematan bahan bakar $= 25,0\text{ km} \times \text{Rp } 4.000/\text{km} = \mathbf{Rp\text{ }100.000}$ (Hemat $37,9\%$).

---

### 7.10 Mekanisme 10: Jejak Emisi Logistik ISO 14083 & Konsumsi Bahan Bakar B40

#### A. Landasan Persamaan Matematis
Dikelola di [`app/engines/emission.py`](file:///D:/IDE/bio-chain-prototype/app/engines/emission.py):
1. **Konsumsi Bahan Bakar Spesifik (*Fuel Consumption Model*)**:
   Konsumsi solar biosolar B40 armada truk diesel engkel bergantung pada beban muatan:
   $$FC(L) = FC_{\text{kosong}} + \left(\frac{W_{\text{muatan}}}{W_{\text{kapasitas}}}\right) \times (FC_{\text{penuh}} - FC_{\text{kosong}})\text{ [L/km]}$$
   *Nilai acuan*: Truk kosong $= 0,18\text{ L/km}$, Truk penuh muatan $= 0,26\text{ L/km}$.
2. **Emisi Logistik Well-to-Wheel (ISO 14083)**:
   $$E_{\text{logistik}} = \text{Total Konsumsi Solar (Liter)} \times EF_{\text{B40 WTW}}\text{ [kgCO}_2\text{e]}$$
   Di mana faktor emisi terakreditasi Biosolar B40 $= 2,68\text{ kgCO}_2\text{e/Liter}$.
3. **Intensitas Emisi per Ton Sekam Terangkut**:
   $$IE = \frac{E_{\text{logistik}}}{\text{Tonase Muatan Terkirim}}\text{ [kgCO}_2\text{e/ton]}$$

#### B. Contoh Perhitungan Numerik Langkah demi Langkah
*Kasus Pengangkutan*: Truk menempuh total rute $41,0\text{ km}$ membawa rata-rata muatan $2,7\text{ ton}$ sekam (kapasitas $3,3\text{ ton}$).

*Langkah 1: Hitung konsumsi bahan bakar rata-rata per km*:
$$FC = 0,18 + \left(\frac{2,7}{3,3}\right) \times (0,26 - 0,18) = 0,18 + (0,818 \times 0,08) = 0,18 + 0,0655 = 0,2455\text{ L/km}$$

*Langkah 2: Hitung total konsumsi bahan bakar rute*:
$$\text{Total Solar} = 41,0\text{ km} \times 0,2455\text{ L/km} = \mathbf{10,06\text{ Liter}}$$

*Langkah 3: Hitung total emisi gas rumah kaca rute*:
$$E_{\text{logistik}} = 10,06\text{ L} \times 2,68\text{ kgCO}_2\text{e/L} = \mathbf{26,96\text{ kgCO}_2\text{e}}$$

*Langkah 4: Hitung intensitas emisi per ton*:
$$IE = \frac{26,96\text{ kgCO}_2\text{e}}{2,7\text{ ton}} = \mathbf{9,99\text{ kgCO}_2\text{e/ton sekam}}$$

---

### 7.11 Mekanisme 11: Perhitungan Pengurangan Emisi Karbon IPCC 2006 Tier 2 (Engine ⑦)

#### A. Landasan Persamaan Matematis
Dikelola oleh [`app/engines/carbon.py`](file:///D:/IDE/bio-chain-prototype/app/engines/carbon.py):
1. **Energi Termal Bersih Biomassa ($E_{\text{biomass}}$)**:
   $$E_{\text{biomass}} = W_{\text{biomass}} \times 1.000 \times \left(1 - \frac{M}{100}\right) \times HHV_{\text{biomass}} \times \eta_{\text{boiler}} \div 1.000\text{ [GJ]}$$
2. **Substitusi Bahan Bakar Fosil Batubara ($W_{\text{coal displaced}}$)**:
   $$W_{\text{coal displaced}} = \frac{E_{\text{biomass}}}{HHV_{\text{coal}}}\text{ [ton batubara]}$$
3. **Emisi Baseline Batubara yang Dihindari ($E_{\text{avoided}}$)**:
   $$E_{\text{avoided}} = E_{\text{biomass}} \times EF_{\text{coal}} \div 1.000\text{ [tCO}_2\text{]}$$
   *Di mana*: $EF_{\text{coal}} = 96,1\text{ kgCO}_2\text{/GJ}$.
4. **Emisi Transportasi Pengangkutan ($E_{\text{trans}}$)**:
   $$E_{\text{trans}} = W_{\text{biomass}} \times D_{\text{km}} \times EF_{\text{trans}} \div 1.000\text{ [tCO}_2\text{]}$$
   *Di mana*: $EF_{\text{trans}} = 0,15\text{ kgCO}_2\text{/ton}\cdot\text{km}$.
5. **Pengurangan Emisi Karbon Bersih (*Net Carbon Reduction*)**:
   $$E_{\text{net}} = E_{\text{avoided}} - E_{\text{trans}}\text{ [tCO}_2\text{e]}$$

#### B. Contoh Perhitungan Numerik Langkah demi Langkah
*Input Kalkulator Pabrik*: Pengolahan $W_{\text{biomass}} = 50,0\text{ ton}$ sekam padi, kadar air $M = 11,0\%$, jarak angkut rata-rata $D = 45\text{ km}$. Parameter: $HHV_{\text{sekam}} = 15,0\text{ MJ/kg}$, $\eta_{\text{boiler}} = 85\%$, $HHV_{\text{coal}} = 20,0\text{ MJ/kg}$.

*Langkah 1: Hitung energi biomassa yang dihasilkan*:
$$E_{\text{biomass}} = 50 \times 1.000 \times (1 - 0,11) \times 15,0 \times 0,85 \div 1.000$$
$$E_{\text{biomass}} = 50.000 \times 0,89 \times 15,0 \times 0,85 \div 1.000 = 667.500 \times 0,85 \div 1.000 = \mathbf{567,375\text{ GJ}}$$

*Langkah 2: Hitung batubara yang tergantikan*:
$$W_{\text{coal}} = \frac{567,375}{20,0} = \mathbf{28,369\text{ ton batubara}}$$

*Langkah 3: Hitung emisi batubara yang dihindari*:
$$E_{\text{avoided}} = 567,375 \times 96,1 \div 1.000 = \mathbf{54,525\text{ tCO}_2}$$

*Langkah 4: Hitung emisi transportasi pengumpulan*:
$$E_{\text{trans}} = 50 \times 45 \times 0,15 \div 1.000 = 337,5 \div 1.000 = \mathbf{0,338\text{ tCO}_2}$$

*Langkah 5: Hitung pengurangan emisi neto*:
$$E_{\text{net}} = 54,525 - 0,338 = \mathbf{54,187\text{ tCO}_2\text{e}} \implies \mathbf{54,19\text{ tCO}_2\text{e}}$$

*Langkah 6: Valuasi Nilai Ekonomi Karbon (NEK)* (asumsi harga sertifikat Rp 60.000 / $tCO_2e$):
$$\text{Nilai Karbon} = 54,19 \times \text{Rp } 60.000 = \mathbf{Rp\text{ }3.251.400}$$

---

### 7.12 Mekanisme 12: Penilaian Skor Hijau (*Green Scorecard*): MCI & E-Factor Silika

#### A. Landasan Persamaan Matematis
Dikelola oleh [`app/engines/green_scorecard.py`](file:///D:/IDE/bio-chain-prototype/app/engines/green_scorecard.py):
1. **Indikator Sirkularitas Material (*Material Circularity Indicator* / MCI)**:
   Mengacu pada metodologi *Ellen MacArthur Foundation*:
   $$LFI = \frac{V + W_0}{2M + \frac{W_f - W_c}{2}}$$
   Untuk rantai pasok Bio-Chain di mana $100\%$ bahan baku berasal dari limbah pertanian ($V = 0$, fraksi virgin $= 0$):
   $$\text{MCI} = 1 - LFI \times F(X) \approx \mathbf{0,88 - 0,95}\text{ (Kategori Unggul / Sangat Sirkular)}$$
2. **Faktor Dampak Lingkungan Ekstraksi Silika (*Sheldon Environmental E-Factor*)**:
   $$E\text{-Factor} = \frac{\text{Massa Limbah Kimia Reagen (kg)}}{\text{Massa Produk Bio-Silika Dihasilkan (kg)}}$$
   - Ekstraksi silika berbasis biochar/abu sekam menghasilkan $E\text{-Factor} \le 1,8$, jauh lebih bersih dibandingkan sintesis silika komersial dari pasir kuarsa ($E\text{-Factor} \ge 11,5$).

---

### 7.13 Mekanisme 13: Nilai Kalor Riil Lapangan (LHV As-Received ISO 18125) & Potensi Listrik

#### A. Landasan Persamaan Matematis
Dikelola di [`app/engines/conversion_energy.py`](file:///D:/IDE/bio-chain-prototype/app/engines/conversion_energy.py):
1. **Nilai Kalor Bawah Basis Lapangan ($LHV_{\text{ar}}$)**:
   Berdasarkan standar internasional ISO 18125:2017:
   $$LHV_{\text{ar}} = LHV_{\text{db}} \times \left(1 - \frac{M}{100}\right) - 2,443 \times \frac{M}{100}\text{ [MJ/kg]}$$
   Di mana konstanta $2,443\text{ MJ/kg}$ adalah energi laten penguapan air pada $25^\circ\text{C}$.
2. **Output Energi Listrik Bersih ($E_{\text{listrik}}$)**:
   $$E_{\text{listrik}} = \frac{W_{\text{biomass}} \times 1.000 \times LHV_{\text{ar}} \times \eta_{\text{konversi}}}{3.600}\text{ [MWh]}$$
   Di mana $1\text{ MWh} = 3.600\text{ MJ}$, $\eta_{\text{konversi}}$ turbin uap kecil $= 22\%$ ($0,22$).

#### B. Contoh Perhitungan Numerik Langkah demi Langkah
*Input Fasilitas*: $500\text{ ton/bulan}$ sekam padi as-received dengan kadar air $M = 14,0\%$. Nilai kalor kering $LHV_{\text{db}} = 14,2\text{ MJ/kg}$.

*Langkah 1: Hitung $LHV_{\text{ar}}$*:
$$LHV_{\text{ar}} = 14,2 \times (1 - 0,14) - (2,443 \times 0,14) = (14,2 \times 0,86) - 0,342 = 12,212 - 0,342 = \mathbf{11,87\text{ MJ/kg}}$$

*Langkah 2: Hitung potensi listrik bulanan*:
$$E_{\text{listrik}} = \frac{500 \times 1.000 \times 11,87 \times 0,22}{3.600} = \frac{1.305.700}{3.600} = \mathbf{362,69\text{ MWh/bulan}}$$

---

### 7.14 Mekanisme 14: Baseline Energi Pabrik, Kriteria IKE & Deteksi Anomali Robust Z-Score / CUSUM

#### A. Landasan Persamaan Matematis
Dikelola oleh [`app/engines/sec_monitor.py`](file:///D:/IDE/bio-chain-prototype/app/engines/sec_monitor.py):
1. **Konsumsi Energi Spesifik (*Specific Energy Consumption* / SEC)**:
   $$SEC = \frac{\text{Total Konsumsi Listrik } (kWh) + \text{Bahan Bakar } (MJ) \div 3,6}{\text{Total Produk Dihasilkan (ton)}}\text{ [kWh/ton]}$$
2. **Pemodelan Baseline Energi Regresi Non-Negatif (NNLS - ISO 50006)**:
   $$E_{\text{model}} = \beta_h \cdot \text{Jam Operasi} + \beta_t \cdot \text{Ton Produk} + \beta_w \cdot \text{Air Diuapkan}$$
3. **Deteksi Anomali Robust Z-Score (Iglewicz & Hoaglin 1993)**:
   Untuk mencegah deviasi ekstrem akibat lonjakan sesaat:
   $$M_i = \frac{0,6745 \times (x_i - \tilde{x})}{MAD}$$
   Di mana $\tilde{x}$ adalah nilai median populasi, dan $MAD = \text{median}(|x_i - \tilde{x}|)$ adalah *Median Absolute Deviation*.
   - Jika $|M_i| > 2,0 \implies \mathbf{Peringatan\text{ }Kuning}$ (Konsumsi tidak wajar).
   - Jika $|M_i| > 3,0 \implies \mathbf{Alarm\text{ }Merah}$ (Anomali kebocoran energi parah).

---

### 7.15 Mekanisme 15: Pemeringkatan Biomassa Multi-Kriteria Metode TOPSIS (Engine ⑧)

#### A. Landasan Persamaan Matematis
Dikelola oleh [`app/engines/feedstock.py`](file:///D:/IDE/bio-chain-prototype/app/engines/feedstock.py):
1. **Normalisasi Vektor Matriks Keputusan ($r_{ij}$)**:
   $$r_{ij} = \frac{x_{ij}}{\sqrt{\sum_{k=1}^m x_{kj}^2}}$$
2. **Matriks Ternormalisasi Terbobot ($v_{ij}$)**:
   $$v_{ij} = w_j \cdot r_{ij}$$
3. **Solusi Ideal Positif ($A^+$) dan Solusi Ideal Negatif ($A^-$)**:
   - Untuk kriteria keuntungan (*benefit*, misal LHV): $A_j^+ = \max_i v_{ij}$, $A_j^- = \min_i v_{ij}$.
   - Untuk kriteria biaya (*cost*, misal harga, kadar abu, kadar air): $A_j^+ = \min_i v_{ij}$, $A_j^- = \max_i v_{ij}$.
4. **Jarak Euclidean ke Solusi Ideal ($S_i^+$ dan $S_i^-$)**:
   $$S_i^+ = \sqrt{\sum_{j=1}^n (v_{ij} - A_j^+)^2}, \quad S_i^- = \sqrt{\sum_{j=1}^n (v_{ij} - A_j^-)^2}$$
5. **Skor Kedekatan Relatif ($C_i$)**:
   $$C_i = \frac{S_i^-}{S_i^+ + S_i^-}$$
   Komoditas dengan nilai $C_i$ tertinggi (mendekati 1,0) ditetapkan sebagai rekomendasi peringkat pertama.

---

### 7.16 Mekanisme 16: Penasihat Tawaran Pengepul (*Bid Advisor* & Biaya Marjinal Logistik)

#### A. Landasan Persamaan Matematis
Dikelola di [`app/routers/collector_api.py`](file:///D:/IDE/bio-chain-prototype/app/routers/collector_api.py):
Pengepul yang ingin menawar sekam petani pada bursa lelang B2B dipandu oleh formula kesepakatan surplus (*Nash Bargaining Solution*):
1. **Biaya Marjinal Logistik per kg ($C_{\text{logistik}}$)**:
   Biaya penyisipan titik henti baru (*insertion cost*) ke dalam rute CVRP eksisting:
   $$C_{\text{logistik}} = \frac{\Delta \text{Jarak (km)} \times \text{Biaya BBM/km}}{\text{Volume Ditawar (kg)}}$$
2. **Batas Tawaran Maksimum Pengepul ($P_{\text{bid max}}$)**:
   $$P_{\text{bid max}} = P_{\text{jual pabrik}} - C_{\text{logistik}} - \text{Target Margin Pengepul}$$
3. **Saran Tawaran Optimal ($P_{\text{saran}}$)**:
   Titik tengah surplus negosiasi antara batas bawah cadangan petani ($P_{\text{reserve}}$) dan batas atas kemampuan pengepul:
   $$P_{\text{saran}} = \frac{P_{\text{reserve}} + P_{\text{bid max}}}{2}$$

---

### 7.17 Mekanisme 17: Penutupan Neraca Massa Multi-Produk (*Mass Balance Closure*)

#### A. Landasan Persamaan Matematis
Dikelola di modul manufaktur sirkular [`app/routers/factory_api.py`](file:///D:/IDE/bio-chain-prototype/app/routers/factory_api.py):

$$\text{Massa Input Total} = \sum_{p=1}^3 \text{Massa Produk Akhir}_p + \sum_{l=1}^5 \text{Massa Aliran Kehilangan}_l$$

1. **Aliran Produk Bernilai Jual**:
   - $M_1$: Bio-Pellet padat ($kg$).
   - $M_2$: Biochar terkarbonisasi ($kg$).
   - $M_3$: Bio-Silika presipitasi $SiO_2$ murni ($kg$).
2. **Aliran Kehilangan Proses (*Mass Loss Streams*)**:
   - $L_1$: Uap air yang diuapkan selama pengeringan ($kg$).
   - $L_2$: Gas sintetis volatil / syngas pembakaran non-kondensabel ($kg$).
   - $L_3$: Gas buang kalsinasi boiler ($kg$).
   - $L_4$: Residu ekstraksi lumpur pelindian kimia ($kg$).
   - $L_5$: Susut penanganan mekanik debu siklon ($kg$).

**Penutupan Neraca Massa (*Closure Ratio*)**:

$$\text{Closure } (\%) = \frac{\sum M_p + \sum L_l}{\text{Massa Bahan Baku Masuk}} \times 100\%$$
- Sistem mewajibkan validasi ketat: Nilai penutupan wajib berada dalam rentang **$99,0\% \le \text{Closure} \le 101,0\%$**. Jika berada di luar rentang ini, sistem menolak penguncian batch dengan peringatan ketidakseimbangan termodinamika (*Thermodynamic Imbalance Warning*).

---

## KESIMPULAN SISTEM

Dokumen ini membuktikan bahwa seluruh angka, lencana, kurva grafik, dan tombol yang tertulis dan tertampil pada aplikasi web Bio-Chain v2 beroperasi di atas pondasi ilmiah yang kokoh, transparan, dan terintegrasi dari hulu sawah hingga hilir pabrik. Tidak ada angka yang dibuat secara sembarangan (*no mock/fake hardcoded metrics*); setiap digit terikat langsung pada parameter operasional lapangan, standar audit karbon dunia, dan persamaan termodinamika terverifikasi.
