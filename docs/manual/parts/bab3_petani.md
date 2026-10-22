# Bab 3 — Panduan Langkah demi Langkah Modul Petani / Penggilingan Padi

Bab ini memandu petani dan operator penggilingan padi memakai Bio-Chain di HP: masuk ke aplikasi, melaporkan stok
biomassa (contoh: **Sekam Padi 5.000 kg**, taksiran kadar air **13,2 %**), memilih cara jual dan cara serah, memesan
biochar untuk sawah, lalu memantau mutu, ketertelusuran, dan pembayaran. Semua layar di bab ini diambil dari tampilan HP
(lebar 390 px).

---

## 3.1 Login Aman & Dashboard Utama

### Layar 3.1a — Masuk Akun & Pilih Peran

**Tujuan Proses & Standar Terkait:** Memastikan hanya pemilik akun yang masuk, dan masuk ke gerbang peran yang benar
(Petani). Ini adalah kontrol keamanan yang *selaras* dengan ISO 27001 (kontrol akses berbasis peran/RBAC, kata sandi
ter-hash, token JWT + CSRF). Aplikasi **tidak** tersertifikasi ISO 27001.

![Halaman masuk: pilih peran Petani, isi username dan password](./screenshots/00_login_pilih_peran.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Masuk Sebagai (kartu peran):** ketuk kartu **Petani** (kartu terpilih menyala hijau). Kartu lain — Pengepul,
  Driver, Pabrik, Auditor — untuk peran lain.
- **② Nomor HP atau Username:** ketik nomor HP atau username Anda, contoh `petani_sugeng`.
- **③ Password:** ketik kata sandi. Ketuk ikon mata 👁 untuk melihat ketikan bila ragu salah ketik.
- **④ MASUK SEBAGAI PETANI ➔:** ketuk tombol hijau. Bila berhasil, dashboard Portal Petani terbuka. Bila akun Anda
  bukan akun petani, muncul pesan "Akun ini bukan akun petani. Silakan pilih gerbang yang sesuai."

Belum punya akun? Ketuk **Daftar akun baru di sini**. Kotak "Akun uji coba (mode demo)" hanya muncul di server demo dan
hilang di server produksi.

> **🔧 Di Balik Layar (Sistem):** Form mengirim `POST /api/v1/auth/login` dengan `identifier`, `password`, dan
> `expected_role` (peran dari kartu ①). `app/routers/auth.py` mencocokkan kata sandi dengan hash **PBKDF2-HMAC-SHA256
> 600.000 iterasi**, menolak bila peran akun ≠ `expected_role`, lalu menerbitkan token JWT. Percobaan login dibatasi
> `LOGIN_RATE_LIMIT` = 10 per IP per jendela waktu (`app/middleware/rate_limiter.py`, anti tebak-tebakan kata sandi).
> Respons tidak pernah memuat hash kata sandi.

### Layar 3.1b — Dashboard Utama Petani

**Tujuan Proses & Standar Terkait:** Ringkasan cepat kinerja pasok Anda: jumlah laporan, tonase terkirim, poin XP, dan
saldo biochar yang bisa diambil.

![Dashboard petani: kartu Total Laporan Panen, Total Tonase, XP, Dompet Biochar](./screenshots/01_petani_dashboard.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Total Laporan Panen:** jumlah batch yang sudah Anda laporkan, contoh **312** batch (rata-rata 312 / bln).
- **② Total Tonase Terkirim:** ton biomassa yang sudah terkirim, contoh **545,5** ton (rata-rata 545,5 ton / bln).
- **③ XP Gamifikasi:** poin keaktifan dan mutu pasok, contoh **1450** dengan tingkat **Mitra Emas** ("TIER MITRA_EMAS").
- **④ Dompet Biochar (hasil):** saldo biochar milik Anda, contoh **2.765,4 kg** saldo aktif — "Potensi bisa diambil:
  1.262,4 kg · Sudah diambil: 9.161 kg".
- Di bawahnya ada kartu **Optimizer & Evaluator Petani** (analisis kadar air, potensi margin Grade A, efisiensi
  biochar, periode 2026-08 s.d. 2026-10 dibanding 3 bulan sebelumnya) dengan pilihan periode "3 Bulan Terakhir",
  tombol **↻ Muat ulang**, dan **Skor Kesehatan** (contoh **91 · Grade A**, 1 butir "Perhatian", 3 butir "Baik").
- Di bagian atas: pemilih persona/akun dan tombol **🔔 Notifikasi**. Pelacakan QR dibahas di Layar 3.5c.

> **🔧 Di Balik Layar (Sistem):** Angka kartu dimuat dari `GET /api/v1/farmer/harvests`, `/farmer/wallet`, dan
> `/farmer/incentive` (`app/routers/farmer.py`). XP dihitung per ton sesuai grade dengan parameter
> `insentif.xp_grade_A/B/C` (`app/params.py`). Kartu Optimizer memakai modul evaluasi AI per peran
> (`initAIEvaluationCard("petani")` di `app/static/app.js`).

---

## 3.2 Form Lapor Biomassa

### Layar 3.2a — Jenis Biomassa, Jumlah, dan Lokasi Penggilingan

**Tujuan Proses & Standar Terkait:** Mencatat stok biomassa yang siap dijual sebagai batch baru dengan kode QR unik,
titik awal rantai ketertelusuran (*chain of custody*).

![Form lapor: jenis biomassa Sekam padi, harga acuan, jumlah 5000 kg, lokasi penggilingan](./screenshots/02_petani_lapor_biomassa.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Jenis biomassa:** pilih komoditas, contoh **Sekam padi**.
- **② Harga Acuan Referensi (hasil otomatis):** kotak hijau langsung menampilkan harga acuan komoditas yang dipilih,
  contoh **Rp 450 / kg** untuk sekam padi. Harga ini berubah otomatis bila jenis biomassa diganti.
- **③ Jumlah (kg):** ketik berat, contoh `5000`. Bisa juga memakai tombol cepat **−50, +50, +100, +500, +1 ton,
  +1 truk**.
- **④ Lokasi penggilingan / titik pasok:** pilih penggilingan asal, contoh **Penggilingan #21 – Berbah (Berbah)**.

Di bawahnya ada bagian lipat **💧 Info mutu (opsional)** — lihat Layar 3.2b.

> **🔧 Di Balik Layar (Sistem):** Daftar komoditas & harga acuan diambil dari master biomassa (`biomassList()` →
> harga dasar per komoditas); daftar penggilingan dari `GET /api/v1/farmer/mills`. Jumlah wajib > 0 dan maksimal
> 100.000 kg per laporan (validasi di `doSubmitLapor`, `app/static/app.js`). Bila penggilingan tidak terdaftar,
> server memakai penggilingan aktif pertama (`report_harvest`, `app/routers/farmer.py`).

### Layar 3.2b — Estimasi Mutu (Kadar Air & Grade) dan Foto

**Tujuan Proses & Standar Terkait:** Memberi taksiran mutu awal agar estimasi pendapatan lebih tepat. Taksiran ini
**tidak menentukan harga final** — harga final dari uji kadar air dan timbangan pengepul.

![Info mutu: taksiran kadar air 13,2 % dan taksiran grade](./screenshots/03_petani_estimasi_mutu.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Taksiran kadar air (%):** ketik hasil perkiraan/alat ukur Anda, contoh `13.2`.
- **② Taksiran grade:** pilih A/B/C/D bila tahu, atau biarkan **Tidak tahu** — sistem menebak grade dari kadar air.
  Catatan di bawahnya: "Tidak memengaruhi harga. Harga final dari uji kadar air & timbangan pengepul."
- **③ Foto Biomassa & Muatan (Kompresi Otomatis Canvas ≤ 300KB):** ketuk **Choose File / 📷 Ambil foto** untuk memotret
  tumpukan biomassa. Foto otomatis diperkecil sebelum diunggah.

Gambar ini juga memperlihatkan bagian form berikutnya: **Cara Jual** (Jual ke pengepul dipilih), **Pilih Pengepul
Tujuan** yang otomatis terisi pengepul spesialis sekam — "Terpilih: Haji Mansur (UD Berkah Sekam – Spesialis Sekam) ·
Kec. Godean" — skema **Dijemput pengepul**, kotak **Estimasi pendapatan Rp 2.362.500** ("Perkiraan Grade B (acuan
Rp 450/kg)"), dan tombol **🚀 KIRIM LAPORAN STOK**. Semua bagian ini dijelaskan di 3.3.

Bila tidak tahu grade, aturan tebakan dari kadar air (MC) adalah:

| Kadar air (MC) | Grade taksiran | Pengali harga (parameter) |
|:---|:---:|:---|
| ≤ 12 % | A | `harga_mutu.mult_A` = ×1,15 |
| > 12 – 15 % | B | `harga_mutu.mult_B` = ×1,05 |
| > 15 – 18 % | C | `harga_mutu.mult_C` = ×1,00 |
| > 18 % | D | "Berisiko ditolak" — jemur dulu bila bisa |

Contoh: MC 13,2 % → Grade **B**.

> **🔧 Di Balik Layar (Sistem):** Fungsi `gradeFrom()` di `app/static/app.js` memakai ambang MC ≤12→A, ≤15→B, ≤18→C,
> >18→D. Foto dikompres oleh `BiochainImage.compress()` (`app/static/ui-enhance.js`): gambar digambar ulang lewat
> canvas dengan sisi terpanjang 1600→1280→1024→800→640 px dan mutu JPEG 0,75→0,62→0,5→0,4 sampai ukurannya
> **≤ 300 KB** (`MAX_PHOTO_BYTES = 300 * 1024`). Proses ini juga membuang metadata EXIF (lokasi rumah, info HP). Foto
> lalu diunggah ke `POST /api/v1/uploads`; bila tidak ada sinyal, foto disimpan di HP dan ikut terkirim bersama
> laporannya. Grade resmi kemudian ditetapkan pengepul dari uji mutu (`app/engines/quality.py`, skor minimum
> `harga_mutu.grade_A_min` = 80, `grade_B_min` = 60).

---

## 3.3 Mode Transaksi & Opsi Pengiriman

Petani memilih dua hal:

| Pilihan | Opsi | Arti |
|:---|:---|:---|
| **Cara jual** | 🤝 **Jual ke pengepul** (Jual Langsung) | Harga ikut acuan biomassa × pengali grade; bisa dicatat saat offline. |
| | 🏷️ **Lelang** (Bursa Lelang) | Pengepul menawar; Anda menetapkan batas harga minimum; perlu sinyal. |
| **Skema penyerahan** | 🚚 **Dijemput pengepul** | Armada menjemput ke lokasi; ongkos angkut ditanggung pengepul. |
| | 🛵 **Saya antar ke gudang** (Diantar Mandiri) | Anda mengantar sendiri; dapat **premi transportasi +Rp 80/kg**. |

### Layar 3.3a — Jual Langsung + Dijemput Pengepul

**Tujuan Proses & Standar Terkait:** Menjual langsung ke pengepul mitra dengan harga acuan, biomassa dijemput armada.

![Cara jual Jual ke pengepul, pengepul tujuan, skema Dijemput pengepul](./screenshots/04_petani_jual_langsung_dijemput.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Jual ke pengepul:** ketuk kartu ini (kartu terpilih berwarna hijau muda dengan tanda radio terisi).
- **② Pilih Pengepul Tujuan (Opsional):** sistem otomatis memilih pengepul spesialis komoditas Anda, contoh **Haji
  Mansur (UD Berkah Sekam – Spesialis Sekam)**. Keterangan di bawahnya: "Terpilih: … · Kec. Godean (Spesialis sekam
  padi) · HP: 082222220001". Ganti bila punya langganan lain, atau pilih "Bebas / Pengepul Terdekat (Otomatis)".
- **③ Dijemput pengepul:** ketuk kartu skema penyerahan ini ("Armada jemput ke lokasi · ongkos angkut ditanggung
  pengepul").
- **④ Estimasi pendapatan (hasil):** kotak hijau menampilkan **Rp 2.362.500** — "Perkiraan Grade B (acuan Rp 450/kg).
  Pengepul menanggung biaya truk & jemput. Harga final dari timbangan & QC pengepul." Hitungannya: 5.000 kg × Rp 450 ×
  1,05 (pengali Grade B). Lalu ketuk **🚀 KIRIM LAPORAN STOK**; muncul jendela "Laporan Sekam padi Berhasil!" berisi
  kode QR batch, dan lot baru tampil di kartu **Riwayat Laporan Biomassa** di bawahnya.

> **🔧 Di Balik Layar (Sistem):** `updateEarning()` (`app/static/app.js`) menghitung
> `estimasi = jumlah × harga_acuan × harga_mutu.mult_<grade>`. Bila grade tidak diketahui, ditampilkan rentang
> Grade C–A (`mult_C` s/d `mult_A`). Payload ke `POST /api/v1/farmer/harvest` memuat `transaction_mode: "DIRECT"`,
> `logistics_mode: "PICKUP"`, `delivery_scheme: "jemput"`, dan `collector_id`. Server membuat batch status
> `REPORTED` dengan kode QR baru (`new_qr_code`), yang masuk antrean uji mutu pengepul.

### Layar 3.3b — Bursa Lelang + Saya Antar ke Gudang

**Tujuan Proses & Standar Terkait:** Membuka stok untuk ditawar banyak pengepul dengan batas harga minimum, dan
mengantar sendiri ke gudang untuk mendapat premi.

![Cara jual Lelang, skema Saya antar ke gudang, harga minimum lelang 480](./screenshots/05_petani_bursa_lelang_diantar.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Lelang:** ketuk kartu ini. Kolom "Pilih Pengepul Tujuan" otomatis disembunyikan karena lelang terbuka untuk
  semua pengepul.
- **② Saya antar ke gudang:** ketuk kartu ini — "Mendapat premi transportasi mandiri (+Rp 80/kg ke pendapatan)".
- **③ Harga penawaran minimum lelang (Rp/kg):** ketik batas bawah, contoh `480`. Tawaran di bawah batas ini otomatis
  tidak diterima. (Bila dikosongkan, sistem mengisi harga acuan + premi antar = 450 + 80 = Rp 530/kg.)
- **④ PASANG UNTUK DITAWAR:** pada mode lelang tombol kirim berubah menjadi tombol ini. Sebelum mengetuk, periksa kotak
  hasil di atasnya: **Nilai minimum lelang Rp 2.400.000** (5.000 kg × Rp 480) — "Skema antar gudang (target Rp 480/kg).
  Tawaran di bawah batas minimum Anda ditolak." Setelah diketuk, stok muncul di kartu Stok Lelang (Layar 3.3c).

> **🔧 Di Balik Layar (Sistem):** Pada mode lelang `updateEarning()` mengaktifkan kolom `f-ask-price` dan menghitung
> `nilai_minimum = jumlah × harga_minimum`. Premi antar mandiri adalah konstanta `premiAntar = 80` (Rp/kg) di
> `app/static/app.js`: harga efektif skema antar = harga acuan + 80. Payload memuat `transaction_mode: "BIDDING"`,
> `logistics_mode: "DELIVER_SELF"`, `floor_price: 480`, `collector_id: null`. Lelang membutuhkan sinyal karena
> pengepul harus bisa melihat dan menawar stok secara langsung.

### Layar 3.3c — Stok Lelang & Tawaran Masuk

**Tujuan Proses & Standar Terkait:** Memantau stok yang sedang dilelang, membandingkan tawaran pengepul berdasarkan
**nilai bersih** (harga − ongkos antar Anda), lalu memilih tawaran.

![Kartu Stok Lelang: listing WR-LST-0203 dengan tabel tawaran Rp 470/kg](./screenshots/08_petani_tawaran_lelang_masuk.png)

Kartu **Stok Lelang & Tawaran Masuk** mengelompokkan lelang per bulan (contoh "Oktober 2026 · 50 Sesi Lelang · Total:
102.500 kg (102,5 Ton)"). Tiap lelang menampilkan kode QR lelang (contoh `WR-LST-0203`), nomor list (Listing #203 ·
3.000 / 3.000 kg), status **Aktif Ditawar** (status: open), skema ("Jemput batas min Rp 450/kg"), dan waktu buka lelang
(18 Okt 2026, 16.41.04 WIB).

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Lihat tawaran:** ketuk untuk membuka tabel tawaran pengepul di bawah kartu (kolom Pengepul, Skema & Jadwal,
  harga/kg, nilai bersih/kg, KG, Terima). Contoh: satu tawaran **Rp 470/kg** untuk **3.000 kg**. Geser tabel ke kanan bila
  kolom terpotong.
- **② Terima tawaran:** di kolom **Terima**, isi jumlah yang ingin dijual (contoh `3000`; boleh lebih kecil untuk
  menjual sebagian) lalu ketuk **PILIH**. Muncul jendela "Kontrak Lelang" berisi QR yang ditunjukkan saat serah terima.
- **③ Batalkan:** ketuk untuk menarik lelang yang masih terbuka.

> **🔧 Di Balik Layar (Sistem):** Tawaran dimuat dari `GET /api/v1/farmer/listings/{id}/bids`; nilai bersih per kg
> untuk skema antar dikurangi ongkos antar petani (`trade.bids_for_farmer`). Memilih tawaran memanggil
> `POST /api/v1/farmer/listings/{id}/accept` — **atomik**: stok tidak pernah terjual melebihi sisa, dan penerimaan
> sebagian diperbolehkan. Pembatalan: `POST /api/v1/farmer/listings/{id}/cancel`.

**Konfirmasi jadwal jemput (tanpa screenshot khusus).** Setelah pengepul mengusulkan tanggal penjemputan, di tabel
tawaran kolom Skema & Jadwal muncul label **Rencana: \<tanggal\>** dengan dua tombol:
- **✓ Setujui** — jadwal dikunci; label berubah menjadi "✓ Jadwal: \<tanggal\>".
- **📅 Ubah** — membuka jendela "Ajukan Penyesuaian Jadwal Jemput": isi **Tanggal Penjemputan Baru** dan **Catatan
  untuk Pengepul** (contoh "Panen baru selesai sore, mohon ambil pagi hari."), lalu **Kirim Permintaan**. Label berubah
  menjadi "📅 Diajukan: \<tanggal\>".

> **🔧 Di Balik Layar (Sistem):** Kedua tombol memanggil `POST /api/v1/farmer/bids/{bid_id}/schedule-respond` dengan
> `action` = `APPROVED` atau `RESCHEDULE_REQUESTED` (+ `reschedule_date`, `reschedule_note`); server memeriksa bahwa
> petani adalah pemilik lelang (403 bila bukan) dan menyimpan `farmer_schedule_status` serta `pickup_date` baru.
> Ada pula endpoint setara `POST /api/v1/farmer/schedule/confirm` (`decision` = `APPROVE`/`RESCHEDULE`, dengan
> penguncian baris `with_for_update`) untuk integrasi; tampilan HP saat ini memakai `schedule-respond`.

---

## 3.4 Permintaan Abu/Biochar Sirkular & Alokasi

### Layar 3.4a — Pesan Muatan Balik Biochar untuk Sawah

**Tujuan Proses & Standar Terkait:** Memesan biochar (arang hayati hasil pirolisis) untuk pembenah tanah sawah, yang
dibawa truk yang sama saat menjemput biomassa — hemat ongkos dan tanpa perjalanan kosong (*zero empty trips*).

![Pesan Muatan Balik Biochar: kebutuhan 500 kg, luas 1,5 ha, titik serah terima](./screenshots/06_petani_permintaan_biochar.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Kebutuhan Biochar (kg):** ketik jumlah, contoh `500`.
- **② Luas Sawah Aplikasi (ha):** ketik luas lahan, contoh `1.5`.
- **③ Titik Serah Terima:** ketik lokasi penurunan, contoh "Lahan Petani Dusun Ngepas".
- **④ 💡 Lihat Perkiraan Manfaat Bersih (4 Musim):** ketuk untuk melihat perkiraan tambahan panen, hemat pupuk, biaya
  tebar, dan manfaat bersih selama 4 musim. Ini **perkiraan**, bukan janji panen.

Pesanan ikut terkirim saat Anda mengetuk **🚀 KIRIM LAPORAN STOK** (terlihat di bawah gambar, bersama Estimasi
pendapatan Rp 2.362.500 untuk Jual ke pengepul).

> **🔧 Di Balik Layar (Sistem):** Tombol ④ memanggil `GET /api/v1/farmer/biochar/estimate?kg=500&land_area_ha=1.5`
> → `app/engines/biochar_field.py`. Rumus (parameter `biochar_sawah.*`): dosis `r = kg/1000/luas` (dibatasi `r_cap`);
> kenaikan hasil `f(r) = R_maks·(1 − e^(−k·r))`; efek sisa N musim `M = (1 − dᴺ)/(1 − d)`;
> manfaat bersih = tambahan pendapatan gabah + hemat pupuk − ongkos tebar. Saat laporan dikirim, kolom
> `biochar_request_kg`, `biochar_land_area_ha`, `biochar_delivery_point` membuat permintaan muatan balik yang
> diteruskan ke pengepul/driver (`report_harvest`, `app/routers/farmer.py`).

### Layar 3.4b — Alokasi Abu & Evaluasi Mutu Biochar

**Tujuan Proses & Standar Terkait:** Menampilkan abu boiler yang dialokasikan ke kelompok tani Anda — hanya abu yang
lolos uji logam berat (Pb, Cd, As ≤ ambang aman, mengacu Kepmentan 261/2019) — dan mencatat ulasan mutu biochar setelah
diaplikasikan di sawah.

![Kartu Alokasi Abu & Evaluasi Mutu Biochar dengan tabel kode ASH dan jenis Bottom Ash](./screenshots/12_petani_alokasi_abu_evaluasi.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Tabel Alokasi Abu Pembenah Tanah untuk Kelompok Anda:** tiap baris berisi **Kode** (contoh `ASH-2610-053`),
  **Jenis Abu** (BOTTOM ASH), **Jumlah** (contoh 200 kg atau 100 kg), **Hasil Uji Lab Logam Berat** (contoh "Pb 5 · Cd 0,2
  · As 1 mg/kg" + nomor laporan lab, mis. "E2E-LULUS" atau "T-ASH"), dan **Status Penyerahan** (contoh *dialokasikan*;
  menjadi *diserahkan* setelah abu diterima kelompok).
- **② 📝 ISI EVALUASI MUTU BIOCHAR:** ketuk untuk mengisi ulasan: kode batch, skor 1–5 untuk **Ukuran Mesh**,
  **Kematangan Pirolisis**, **Kadar Kelembapan**, **Dampak Kesuburan Tanah**, plus catatan dampak di lahan.
- **Tabel Evaluasi & Ulasan Mutu Biochar Lapangan** ada di bawah tabel abu (gulir ke bawah; tidak terlihat di gambar):
  riwayat ulasan dengan skor total "⭐ x / 5.0".

Tabel ini lebar; paling nyaman dilihat di tablet/desktop atau dengan HP dimiringkan (gambar diambil dari tampilan
desktop).

> **🔧 Di Balik Layar (Sistem):** Data abu dari `GET /api/v1/farmer/ash` (`app/routers/multibiomass.py`, hanya untuk
> ketua kelompok tani yang menerima alokasi). Ulasan disimpan via `POST /api/v1/farmer/biochar-evaluations` dan
> ditampilkan dari `GET` endpoint yang sama (`app/static/field-ops.js`, `openBiocharEvaluationModal` &
> `loadBiocharEvaluations`). Spesifikasi mutu biochar produk (H/Corg, logam berat) mengacu EBC/IBI dan dikelola di
> sisi pabrik (Bab 6).

---

## 3.5 Ketertelusuran, Hasil Uji Mutu & Grade, Pelacakan Pembayaran

### Layar 3.5a — Riwayat Laporan, Grade & QR

**Tujuan Proses & Standar Terkait:** Melihat semua batch yang pernah dilaporkan beserta kode unik QR-nya, sebagai bukti
asal-usul biomassa.

![Tabel riwayat laporan dengan kode BIO-... dan tombol QR](./screenshots/07_petani_riwayat_grade_qr.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Judul kolom tabel:** No. Unik WR Code, Biomassa, Berat (kg), Status Aktif, Grade, Detail Input, QR. Ketuk ↕
  untuk mengurutkan, ikon saring untuk menyaring. Laporan dikelompokkan per bulan, contoh "Oktober 2026 · 20 Laporan ·
  52.600 kg (52,6 Ton)".
- **② Satu baris laporan:** contoh `BIO-2C56716D-X3UGCX` · SEKAM PADI · 3.000 kg · **Terverifikasi Pengepul** dengan
  "Jadwal Jemput: 2026-10-18" · **Grade A** · tombol **Detail**. Lot yang belum diuji berstatus **Menunggu Verifikasi
  Pengepul** dan kolom Grade masih "–".
- **③ 📱 QR:** ketuk untuk menampilkan kode QR batch untuk ditunjukkan ke pengepul atau driver saat serah terima.

Tabel ini lebar; paling nyaman dilihat di tablet/desktop atau dengan HP dimiringkan (gambar diambil dari tampilan
desktop). Di HP, geser tabel ke kanan.

> **🔧 Di Balik Layar (Sistem):** Data dari `GET /api/v1/farmer/harvests`. Kode QR batch dibuat sekali saat laporan
> dikirim dan disimpan sebagai `origin_qr_code`, sehingga tetap bisa dilacak walau batch kemudian berpindah tangan.

### Layar 3.5b — Hasil Uji Mutu: Deviasi & Refraksi

**Tujuan Proses & Standar Terkait:** Transparansi: membandingkan taksiran Anda dengan timbangan dan uji mutu nyata
pengepul, termasuk potongan berat (refraksi) dan alasan bila lot ditolak.

![Tabel Transparansi Deviasi & Refraksi Mutu per lot](./screenshots/10_petani_deviasi_refraksi.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Tabel Transparansi Deviasi & Refraksi Mutu:** tiap baris = satu lot. Contoh baris pertama: `BIO-2C56716D-X3UGCX`
  (Lot #1165, resi serah terima `TRX-PTN0006-PGP0003-2610-00182`) · Sekam Padi · **Klaim Petani 3.000 kg, air ~12,5 %**
  · **Timbangan Pengepul 2.950 kg, air 12,5 %, Grade A** · **Deviasi & Refraksi −50 kg (−1,7 %)** · Status **PASS**.
  Lot `BIO-4338C4EF-2IOY2E` (Lot #1159): klaim 5.000 kg (air ~13,2 %) → timbangan 4.950 kg (air 13,2 %, Grade A),
  deviasi −50 kg (−1 %). Lot yang belum ditimbang menampilkan "–" dan status **PENDING**. Kolom paling kanan (Status QC
  dan tombol **Aksi** untuk membuka rincian "Ketelusuran Mutu & Refraksi Lot") ada di ujung kanan tabel.
- Di bawah tabel ini ada kartu **⭐ Reputasi & Keandalan Pengepul** (skor ketepatan bayar & tempo bayar pengepul
  terdekat) dengan tombol **⭐ Beri Rating Pengepul** untuk menilai pengepul setelah transaksi (tidak terlihat di gambar).

Tabel ini lebar; paling nyaman dilihat di tablet/desktop atau dengan HP dimiringkan (gambar diambil dari tampilan
desktop).

> **🔧 Di Balik Layar (Sistem):** Data dari `GET /api/v1/farmer/qc-deviations` (klaim, timbangan, deviasi kg/%,
> kadar air taksiran vs terukur, grade, alasan tolak). Berat yang dibayar dihitung `app/engines/refraction.py`:
>
> `kg_bayar = kg_timbang × (1 − max(0, kontaminan − toleransi)) × (1 − MC) / (1 − MC_acuan)`
>
> Tidak ada bonus bila lebih kering dari acuan (kecuali diaktifkan per transaksi). Bila MC di atas batas tolak
> (`harga_mutu.moisture_reject` = 25 %), lot ditolak kecuali pengepul memilih "terima basah" secara eksplisit.
> Grade resmi A/B/C/D berasal dari skor mutu `app/engines/quality.py`. Reputasi pengepul dari
> `GET /api/v1/farmer/collector-reputations`; rating disimpan via `POST /api/v1/farmer/collector-ratings`.

### Layar 3.5c — Lacak QR Sirkular End-to-End

**Tujuan Proses & Standar Terkait:** Melacak perjalanan satu batch dari sawah → pengepul → driver → pabrik (pirolisis /
abu) → muatan balik → sawah, dengan rantai sidik digital SHA-256. Pencatatan *chain of custody* ini *selaras* dengan
prinsip ISO 22095 (bukan sertifikasi).

![Jendela Ketelusuran Sirkular QR Code End-to-End](./screenshots/11_petani_lacak_qr_sirkular.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Kolom kode lot:** ketik atau tempel kode QR batch, contoh `BIO-F4733DAE-DEDHTO`, lalu ketuk **🔍 LACAK** (atau
  tekan Enter). Tersedia tombol contoh "Lot #6 (Converted)", "Lot #25", "Muatan Balik #1".
- **② Lencana tahap (hasil):** posisi batch dalam 6 tahap, contoh **Tahap 1/6** untuk lot yang baru dilaporkan; bila
  siklus tertutup menjadi "🟢 100% Sirkular Terpenuhi".
- **③ Ringkasan aliran massa & linimasa tahap:** kartu Input Biomassa Sawah (**5.000 kg** Sekam Padi), Timbang Terima
  Pabrik (4.750 kg), Biochar Dihasilkan (1.425 kg, yield ~30 %), Abu Sisa Pembakaran (688,8 kg), Kembali ke Sawah
  (57 sak), dan Emisi CO₂ Dihindari (1.211,3 kg, metodologi IPCC Tier 2). Di bawahnya linimasa: **Tahap 1 ✓ Selesai**
  (Pelaporan Stok Biomassa Petani), Tahap 2 dan 3 **Menunggu**.
  ⚠️ Untuk lot yang belum sampai pabrik (seperti contoh ini, Tahap 1/6), angka pabrik/biochar/abu/CO₂ adalah
  **proyeksi** dari angka default sistem, bukan hasil timbang atau produksi nyata.

Di bagian bawah jendela ada **SHA256 Chained Provenance Integrity** (sidik digital rantai data; bila ada data yang diubah
diam-diam, sidiknya tidak cocok), tombol **🖨 Cetak Paspor Sirkular**, dan **Tutup**.

> **🔧 Di Balik Layar (Sistem):** `GET /api/v1/traceability/circular/{kode}` → `app/services/circular_traceability.py`
> menggabungkan data panen, custody event, ledger biochar, konversi pabrik, surat jalan muatan balik, dan penebusan
> biochar. Bila konversi belum ada, yield biochar memakai default 30 % dan abu diperkirakan 14,5 % dari berat terima
> pabrik; bila timbang pabrik belum ada, berat pabrik diperkirakan 95 % berat pengepul. Sidik dihitung `hashlib.sha256`.

### Layar 3.5d — Pembayaran & Kuitansi Saya

**Tujuan Proses & Standar Terkait:** Melacak uang muka (DP), kuitansi digital, dan pelunasan. Batas waktu bayar petani
adalah **maksimal 3 hari** setelah biomassa ditimbang & diuji (lebih ketat dari target ≤ 14 hari); lewat batas ditandai
**terlambat**.

![Pembayaran & Kuitansi Saya: Sudah Diterima, Menunggu Dibayar, Belum Ditimbang, filter status](./screenshots/09_petani_pembayaran_kuitansi_sla.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**

Tiga kartu ringkasan di atas:
- **Sudah Diterima** — **Rp 19,7 jt · 49 kuitansi**.
- **Menunggu Dibayar** — **Rp 108,4 jt · 132 lot · 52 terlambat > 3 hari**.
- **Belum Ditimbang** — **234.750 kg · 119 laporan · harga belum final**.

Lalu di bagian **Riwayat Transaksi & Pelunasan Terpadu**:
- **① Filter status:** pilih **Semua Status**, **✅ Sudah Lunas**, **⏳ Menunggu Pelunasan**, atau **🤝 Ada Uang Muka
  (DP)**. Kolom pencarian di sebelahnya menerima kode QR, nomor kuitansi, atau nama komoditas.
- **② Tabel riwayat:** dikelompokkan per bulan (contoh "Oktober 2026 · 149 Pembayaran"). Contoh baris:
  `BIO-FD72C03E-IDB4FR` (Lot #1134) · **Sekam Padi 1.000 kg** · **Ada DP: Rp 50.000** (`DP-PGP0003-PTN0006-2610-00114`)
  · Status Kuitansi **Diterima** (`BYR-PGP0003-PTN0006-2610-00115`) · Status Akhir **Lunas**. Status lain yang mungkin
  muncul: "⚪ Tanpa DP", "⏳ Menunggu Terbit", "⏳ Menunggu Pelunasan", "⏳ Belum Ditimbang". Di ujung kanan ada kolom
  Nominal Net, Pengepul & Waktu, dan Aksi (tombol **🧾 Kuitansi** / **🤝 Kuitansi DP** untuk membuka kuitansi digital).
- **③ 📱 QR:** ketuk untuk menampilkan kode QR lot asal pembayaran tersebut.

Tabel ini lebar; paling nyaman dilihat di tablet/desktop atau dengan HP dimiringkan (gambar diambil dari tampilan
desktop).

> **🔧 Di Balik Layar (Sistem):** `GET /api/v1/farmer/payments/overview` → `farmer_overview()` di
> `app/services/payments.py` membagi lot menjadi tiga keranjang: **dibayar** (ada `FarmerPayment` + kuitansi BYR),
> **menunggu bayar** (sudah diverifikasi, belum dibayar), dan **belum ditimbang** (status `REPORTED`). Lot menunggu
> ditandai `late = hari_menunggu > pasar.farmer_payment_due_days` (default **3 hari**, rentang 0–60, diatur di menu
> Parameter). Nilai bersih = bruto − PPh 22 (`pajak.pph22_farmer_pct`) − DP aktif. Tabel dirender oleh
> `renderUnifiedPaymentTable()` (`app/static/field-ops.js` → `app/static/js/modules/field-kuitansi.js`). Penanda
> terlambat tampil di kartu "Menunggu Dibayar"; tabel menampilkan status DP, kuitansi, dan lunas.

---

## Tips Lapangan

| Situasi | Yang perlu dilakukan | Yang terjadi di sistem |
|:---|:---|:---|
| Sinyal hilang saat kirim laporan **Jual ke pengepul** | Tetap ketuk **Kirim Laporan Stok**. | Muncul pesan "Sinyal hilang. Laporan disimpan di HP & dikirim otomatis saat online." Laporan masuk antrean (*outbox*) di IndexedDB HP (cadangan `localStorage`). |
| Banner kuning **📵 Mode Hemat Sinyal** muncul di atas layar | Lanjutkan bekerja; jangan hapus data browser/cache aplikasi. | Banner menampilkan jumlah data antre (contoh "2 data antre"). Antrean dikirim otomatis saat sinyal kembali, saat aplikasi dibuka lagi, dan dicoba setiap 30 detik. |
| Sinyal kembali tapi data masih antre | Ketuk **Kirim sekarang** pada banner biru "📶 Sinyal tersedia". | `flushOutbox()` mengirim antrean berurutan; foto antrean diunggah dulu. Tiap laporan punya `client_event_id` sehingga **tidak tercatat dobel**. |
| Muncul banner **🔐 Sesi berakhir** | Login ulang. | Antrean tetap aman di HP dan dikirim setelah login. |
| Data antre ditolak server | Baca pesan "Ditolak server (…)". | Data dipindah ke kotak gagal untuk ditinjau, tidak hilang diam-diam. |
| Ingin **Lelang** | Cari tempat bersinyal. | Lelang perlu sinyal agar pengepul bisa menawar langsung. |
| Kuota/sinyal lemah saat foto | Foto seperti biasa. | Foto otomatis dikecilkan ≤ 300 KB dan disimpan di HP bila offline. |
| Jam HP salah | Atur tanggal & jam HP otomatis. | Waktu catat offline divalidasi server terhadap `CLIENT_CLOCK_MAX_PAST_HOURS` (default 72 jam); di luar jendela itu jam HP tidak dipakai dan server memakai jam server. |
| Biomassa masih basah (MC > 18 %) | Jemur dulu sebelum lapor/serah. | Estimasi menampilkan "Berisiko ditolak"; di atas 25 % lot ditolak saat uji mutu. |
