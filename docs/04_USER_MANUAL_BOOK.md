# 📖 Buku Panduan Pengguna (User Manual Book)
## Bio-Chain v2 — Smart Rice-Husk Supply Chain for Pyrolysis Biochar
*Panduan Operasional Lengkap untuk Petani, Pengepul, Driver, Pabrik, dan Administrator*

---

## DAFTAR ISI
1. [BAB 1: Pengenalan & Petunjuk Memulai Cepat](#bab-1-pengenalan--petunjuk-memulai-cepat)
2. [BAB 2: Panduan Peran Petani (🌾)](#bab-2-panduan-peran-petani-)
3. [BAB 3: Panduan Peran Pengepul / KUD (📦)](#bab-3-panduan-peran-pengepul--kud-)
4. [BAB 4: Panduan Peran Driver Armada Logistik (🚛)](#bab-4-panduan-peran-driver-armada-logistik-)
5. [BAB 5: Panduan Peran Pabrik Pirolisis (🏭)](#bab-5-panduan-peran-pabrik-pirolisis-)
6. [BAB 6: Panduan Peran Administrator & Lab Engine (⚙️)](#bab-6-panduan-peran-administrator--lab-engine-️)
7. [BAB 7: Panduan Pengoperasian IoT "Bio-Chain Scout Pro"](#bab-7-panduan-pengoperasian-iot-bio-chain-scout-pro)
8. [BAB 8: FAQ & Troubleshooting (Penyelesaian Masalah)](#bab-8-faq--troubleshooting-penyelesaian-masalah)

---

## BAB 1: Pengenalan & Petunjuk Memulai Cepat

Bio-Chain v2 adalah platform cerdas yang menghubungkan seluruh pemangku kepentingan rantai pasok sekam padi menjadi biochar bernilai tinggi.

### 1.1 Persyaratan Sistem
- Sistem Operasi: Windows 10/11, macOS, atau Linux.
- Python 3.10+ (direkomendasikan Python 3.12 atau 3.14).
- Browser Modern: Google Chrome, Microsoft Edge, Mozilla Firefox, atau Safari.

### 1.2 Cara Menjalankan Aplikasi
Terdapat dua cara mudah untuk menyalakan server lokal:
- **Opsi A (Paling Mudah)**: Dobel-klik file `jalankan.bat` pada folder root proyek. Browser otomatis terbuka di `http://127.0.0.1:8000`.
- **Opsi B (Terminal Command)**:
  ```bash
  py -m uvicorn app.main:app --port 8000
  ```

### 1.3 Masuk ke Akun Demo (Fitur 1-Klik)
1. Buka alamat `http://127.0.0.1:8000`.
2. Pada layar login, terdapat 5 kartu persona peran di bawah judul:
   - 🌾 **Petani** (`petani_sugeng` / `sekam123`)
   - 📦 **Pengepul** (`pengepul_sleman` / `kud2026`)
   - 🚛 **Driver** (`sopir_budi` / `truk2026`)
   - 🏭 **Pabrik** (`pabrik_indmira` / `pabrik2026`)
   - ⚙️ **Admin** (`admin` / `admin2026`)
3. **Cukup klik kartu peran yang Anda inginkan**, formulir username dan password akan terisi secara otomatis.
4. Klik tombol hijau **"Masuk ke Sistem Bio-Chain ➔"**.
5. Atau, klik tombol **"⚡ Masuk Cepat sebagai Tamu Demo (Admin)"** untuk langsung menjelajah seluruh fitur tanpa login bertahap.

---

## BAB 2: Panduan Peran Petani (🌾)

Portal Petani didesain ramah pengguna, ringkas, dan fokus pada kecepatan pelaporan stok sekam.

### 2.1 Melaporkan Stok Sekam Siap Jual
1. Masuk sebagai akun **Petani** (contoh: Pak Sugeng).
2. Di sisi kiri dashboard, terdapat formulir **"🌾 Lapor Stok Sekam Siap Jual"**:
   - Masukkan **Jumlah Sekam (kg)**: Masukkan berat perkiraan sekam yang tersedia (misal: 2500 kg).
   - Pilih **Lokasi Penggilingan Padi**: Pilih penggilingan terdekat tempat sekam ditampung (misal: *Penggilingan Padi Berkah Tani, Godean*).
3. Perhatikan kotak hijau di bawah form: Sistem otomatis mengkalkulasi **Estimasi Pendapatan** berdasarkan harga dasar Grade A.
4. Klik tombol **"🚀 Kirim Laporan Stok Sekam"**.
5. Pop-up dialog akan muncul menampilkan **Bukti QR Code Resmi** (contoh: `BIO-A4B7C9D2`) dan konfirmasi berat.

### 2.2 Memantau Status & Bukti Penyetoran
1. Di sisi kanan dashboard, terdapat tabel **"📜 Riwayat Laporan Sekam"**.
2. Anda dapat melihat status batch Anda:
   - `REPORTED`: Sekam telah terdaftar dan menunggu verifikasi pengepul/armada.
   - `VERIFIED`: Sekam telah diuji proksimat dan diberikan grade mutu.
   - `IN_TRANSIT`: Sekam sedang dalam perjalanan diangkut truk armada.
   - `DELIVERED`: Sekam telah tiba dan diterima di fasilitas reaktor pabrik.

### 2.3 Memantau XP Gamifikasi & Tier Mitra
1. Kotak KPI di bagian atas dashboard menampilkan akumulasi **XP Gamifikasi** Anda.
2. Setiap pengiriman sekam kering dan bersih Grade A memberikan bonus XP lebih besar.
3. Kenaikan tier memberikan hak istimewa:
   - **Mitra Perunggu (100 XP)**: Prioritas penjadwalan truk armada.
   - **Mitra Perak (500 XP)**: Bantuan subsidi karung terpal anti-hujan.
   - **Mitra Emas (1500 XP)**: Tambahan insentif tunai flat +Rp 25/kg serta kuota bibit padi unggul bersertifikat.

---

## BAB 3: Panduan Peran Pengepul / KUD (📦)

Pengepul bertindak sebagai agregator lokal dan penjamin mutu (*quality gatekeeper*) sebelum biomassa dimuat ke armada truk.

### 3.1 Melihat Daftar Laporan Sekam Masuk
1. Masuk sebagai akun **Pengepul** (contoh: Pak Ahmad, KUD Sleman).
2. Di tabel **"📋 Antrean Verifikasi Laporan Petani"**, Anda dapat memfilter laporan berdasarkan kecamatan.
3. Setiap baris menunjukkan nama petani, nomor telepon, berat sekam, dan tombol aksi verifikasi.

### 3.2 Melakukan Verifikasi Mutu & Uji Proksimat
1. Klik tombol **"🔍 Uji Mutu & Verifikasi"** pada baris laporan petani yang hendak diperiksa.
2. Masukkan parameter hasil pembacaan alat uji cepat (*Bio-Chain Scout Pro* atau uji lab lapangan):
   - **Kadar Air (% wet basis)**: Batas ideal $\le 12\%$.
   - **Kadar Abu (% dry basis)**: Batas ideal $\le 20\%$.
   - **Volatile Matter (%)**: Rata-rata sekam berkisar $60\% - 68\%$.
   - **Fixed Carbon (%)**: Rata-rata sekam berkisar $14\% - 18\%$.
   - **Tingkat Kontaminan (%)**: Batas toleransi $\le 2\%$ (kerikil, tanah, jerami basah).
3. Klik tombol **"Kalkulasi Grade & Konfirmasi"**.
4. Engine ② secara otomatis menetapkan:
   - **Grade A / B / C / Tolak**.
   - **Skor Mutu Kualitas (0 - 100)**.
   - **Total Pembayaran**: Hasil kali berat $\times$ harga acuan $\times$ pengali insentif grade mutu.
5. Status laporan sekam seketika berubah menjadi `VERIFIED` dan siap dimasukkan ke antrean rute penjemputan driver.

### 3.3 Memantau Rekapitulasi Harian
Kotak KPI atas menyajikan ringkasan agregat hari ini:
- Total Pickup Batch.
- Akumulasi Tonase Terkumpul.
- Rata-rata Skor Kualitas Sekam.
- Total Dana Pembayaran yang Disalurkan ke Petani.

---

## BAB 4: Panduan Peran Driver Armada Logistik (🚛)

Portal Driver membantu pengemudi armada logistik mengefisienkan rute penjemputan dan memvalidasi serah-terima biomassa.

### 4.1 Membuka Rute Aktif & Peta Interaktif
1. Masuk sebagai akun **Driver** (contoh: Budi Santoso).
2. Di bagian tengah, peta interaktif GIS menampilkan posisi depot pabrik dan urutan penggilingan padi yang harus dikunjungi.
3. Di sebelah kanan peta, tertera metrik efisiensi rute hasil algoritma Clarke-Wright:
   - Total Jarak Rute (km).
   - Estimasi Utilisasi Kapasitas Truk (% muatan).
   - Penghematan Jarak dibandingkan penjemputan acak (hingga 32.4%).

### 4.2 Memulai Perjalanan (*Start Route*)
1. Klik tombol **"🚚 Mulai Rute Penjemputan"**.
2. Status rute berubah menjadi aktif dan GPS melacak urutan perhentian (*stops*).

### 4.3 Konfirmasi Pengambilan Sekam (QR Code Scan)
1. Setibanya di lokasi penggilingan padi atau rumah petani:
   - Cocokkan fisik sekam dengan tiket QR Code yang ditunjukkan petani/pengepul.
   - Masukkan kode tiket (contoh: `BIO-A4B7C9D2`) pada kolom konfirmasi atau scan menggunakan kamera.
2. Klik tombol **"✅ Konfirmasi Pickup Selesai"**.
3. Muatan truk otomatis ter-update dan status batch berubah menjadi `IN_TRANSIT`.

### 4.4 Menyelesaikan Rute (*Complete Route*)
1. Setelah seluruh titik penggilingan dikunjungi dan truk tiba kembali di depot pabrik pirolisis:
2. Klik tombol **"🏁 Selesaikan Pengiriman ke Pabrik"**.
3. Seluruh sekam yang dimuat otomatis masuk ke buku stok bahan baku pabrik (*Raw Feedstock Inventory*).

---

## BAB 5: Panduan Peran Pabrik Pirolisis (🏭)

Portal Pabrik memberikan visibilitas menyeluruh terhadap kontinuitas pasokan bahan baku, formulasi campuran pakan reaktor, dan sertifikasi kredit karbon ESG.

### 5.1 Memantau Proyeksi Pasokan 30 Hari (*Supply Forecaster*)
1. Masuk sebagai akun **Pabrik** (contoh: PT Indmira Biochar Plant).
2. Grafik tren proyeksi pasokan bulanan menampilkan kurva fluktuasi panen raya dan musim gadu.
3. Pabrik dapat mengantisipasi defisit bahan baku 30 hari ke depan dengan mengaktifkan pengadaan dari penggilingan di luar radius utama.

### 5.2 Optimasi Blending Bahan Baku Reaktor (Solver HiGHS)
1. Masuk ke panel **"🧪 Blending Optimizer"**.
2. Pilih produk biochar target yang hendak diproduksi:
   - *Biochar Pembenah Tanah SNI 8984:2021*.
   - *Biochar Filtrasi Air & Remediasi Lahan*.
   - *Briket Bio-Energi Kalori Tinggi*.
3. Masukkan target total produksi (misal: 50 Ton).
4. Klik tombol **"Optimasi Campuran (HiGHS) ➔"**.
5. Solver Linear Programming akan memproses data stok dan menghasilkan proporsi racikan bahan baku dengan biaya terendah (*minimum cost*) yang tetap memenuhi spesifikasi kadar air $\le 12\%$ dan kadar abu $\le 22\%$.

### 5.3 Menghitung Sertifikasi Kredit Karbon & ESG (IPCC Tier 2)
1. Buka tab **"🌿 Kalkulator Karbon & ESG"**.
2. Masukkan total tonase sekam yang diproses dalam periode berjalan.
3. Sistem secara otomatis menghitung:
   - Emisi Baseline yang Dihindarkan (*Avoided Open Burning Emissions*).
   - Emisi Transportasi & Pemrosesan Reaktor.
   - Emisi Bersih Terhindarkan (*Net Carbon Offset* dalam satuan $\text{tCO}_2\text{e}$).
   - Estimasi Nilai Ekonomi Karbon (Rp) sesuai harga acuan bursa IDX Carbon.
4. Klik **"Cetak Laporan ESG"** untuk mengunduh berkas kepatuhan sertifikasi.

---

## BAB 6: Panduan Peran Administrator & Lab Engine (⚙️)

### 6.1 Dashboard Pemantauan Sistem
1. Masuk sebagai akun **Admin**.
2. Kotak ringkasan atas menyajikan metrik makro:
   - Total Petani & Penggilingan Aktif.
   - Total Volume Sekam Tersirkulasi (Ton).
   - Total Emisi Karbon Terhindarkan ($\text{tCO}_2\text{e}$).
   - Status Koneksi Database (PostgreSQL 16 / SQLite Lokal).

### 6.2 Tombol 1-Klik Reset Data Demo
- Di pojok kanan atas header terdapat tombol **"🔄 Reset Data Demo"**.
- Fitur ini sangat berguna jika juri atau penguji ingin mengembalikan seluruh transaksi, rute, dan status panen ke kondisi awal demo tanpa perlu menginstal ulang aplikasi.

### 6.3 Eksplorasi Laboratorium 7 Engine
1. Klik tab navigasi **"🧪 Lab 7 Engine"**.
2. Administrator dapat menguji parameter matematis setiap engine secara mandiri:
   - Simulasi sensitivitas kadar air terhadap rendemen biochar.
   - Simulasi perubahan harga bahan baku terhadap komposisi blending HiGHS.
   - Uji optimasi rute logistik dengan penambahan titik koordinat baru.

---

## BAB 7: Panduan Pengoperasian IoT "Bio-Chain Scout Pro"

```
              ┌──────────────────────────────────────┐
              │          PANDUAN OPERASI IOT         │
              ├──────────────────────────────────────┤
              │ 1. Tancapkan probe NIR ke karung     │
              │ 2. Letakkan karung di atas timbangan │
              │ 3. Tekan tombol hijau SCAN           │
              │ 4. Tunggu 3 detik hingga LED biru    │
              │ 5. Ambil label thermal tercetak      │
              │ 6. Tempel label QR pada karung       │
              └──────────────────────────────────────┘
```

1. **Pemeriksaan Awal**: Pastikan indikator baterai pada layar LCD menunjukkan voltase di atas 11.5V.
2. **Penancapan Probe Optik**: Masukkan probe NIR ke dalam karung sekam dengan kedalaman minimal 20 cm untuk mendapatkan pembacaan yang representatif.
3. **Penimbangan Digital**: Letakkan karung di atas platform timbangan load cell.
4. **Eksekusi Pengukuran**: Tekan tombol hijau **"SCAN & VERIFY"**.
5. **Pencetakan Tiket QR**: Perangkat akan memproses data selama 3 detik, lalu printer thermal otomatis mengeluarkan label identitas batch tahan cuaca.
6. **Sinkronisasi Otomatis**: Data berat dan proksimat otomatis terunggah ke server Bio-Chain melalui jaringan seluler 4G LTE.

---

## BAB 8: FAQ & Troubleshooting (Penyelesaian Masalah)

### Q1: Muncul pesan error "Port 8000 is already in use" saat menjalankan aplikasi?
**Solusi**:
Jalankan aplikasi pada port alternatif, misalnya port 8080:
```bash
py -m uvicorn app.main:app --port 8080
```
Lalu buka browser di `http://127.0.0.1:8080`.

### Q2: Saya tidak memiliki instalasi Docker atau PostgreSQL di komputer saya, apakah aplikasi tetap bisa berjalan?
**Solusi**:
Ya, tentu saja! Bio-Chain v2 memiliki fitur *automatic zero-configuration fallback*. Jika PostgreSQL tidak ditemukan, sistem otomatis beralih ke database lokal SQLite (`biochain.db`) tanpa memerlukan instalasi software database tambahan apa pun.

### Q3: Bagaimana jika saya lupa kredensial login akun demo?
**Solusi**:
Cukup klik salah satu kartu peran di halaman login (Petani, Pengepul, Driver, Pabrik, Admin) untuk mengisi username dan password secara otomatis. Anda juga dapat menggunakan tombol **"⚡ Masuk Cepat sebagai Tamu Demo (Admin)"**.

### Q4: Di mana saya dapat melihat dokumentasi lengkap seluruh endpoint REST API?
**Solusi**:
Saat server menyala, buka alamat `http://127.0.0.1:8000/docs` untuk melihat dokumentasi interaktif Swagger UI, atau `http://127.0.0.1:8000/redoc` untuk ReDoc.

---
*Bio-Chain v2 — Sustainable Energy Innovation for Net Zero Indonesia 2026*
