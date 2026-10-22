# Bab 4 — Panduan Langkah demi Langkah Modul Pengepul / Agregator

Modul Pengepul dipakai oleh agregator (KUD, pedagang sekam, pemilik gudang) yang membeli biomassa dari petani,
menimbang dan menguji mutunya, mengatur rute jemput, membayar petani, lalu menjual dan mengirim ke pabrik.
Semua layar di bab ini diambil pada laptop/desktop (1440 × 900) dengan akun demo **Pak Ahmad (KUD Tani …)**.
Pengepul demo ini dikunci ke **satu komoditas** (Sekam Padi). Sistem menolak tawaran atau verifikasi untuk
komoditas lain dengan pesan "Isolasi spesialisasi" (`app/services/trade.py` → `place_bid`, `app/routers/collector.py` → `verify_harvest`).

Alur kerja harian pengepul:

1. **4.1** Lihat penawaran petani, kirim tawaran lelang, periksa margin kontrak.
2. **4.2** Susun rute jemput yang memperhitungkan berat **dan** volume bak, termasuk muatan balik biochar.
3. **4.3** Timbang dan uji mutu di lokasi, terbitkan resi TRX, lalu bayar petani (DP atau lunas).
4. **4.4** Ajukan pengiriman ke pabrik, pantau piutang, dan baca umpan balik QC gerbang pabrik.

---

## 4.1 Dashboard Konsolidasi, Bursa Lelang & Margin Kontrak

### Layar 4.1a — Dashboard Penawaran Biomassa Petani (tiga jalur masuk)

**Tujuan Proses & Standar Terkait:** Menyatukan semua biomassa yang ditawarkan petani dalam satu dashboard. Penawaran
dibagi menurut cara transaksi dan cara angkut, supaya pengepul tahu lot mana yang harus dijemput, ditawar, atau ditunggu.
Setiap lot membawa nomor QR ketelusuran yang menjadi awal rantai *chain of custody* (selaras ISO 22095).

![Dashboard penawaran dengan tab Langsung Diambil, Lelang, Diantar Petani dan filter verifikasi](./screenshots/13_pengepul_dashboard_penawaran.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Tab "LANGSUNG DIAMBIL" (412):** lot yang dijual langsung oleh petani dengan skema *dijemput armada*. Pada
  gambar, tab ini sedang aktif. Kartu bulan "Oktober 2026" menampilkan "412 Lot Penawaran". Dari sinilah lot masuk ke
  antrean timbang dan uji (Layar 4.3a).
- **② Tab "Lelang" (65):** stok yang dilelang petani di Bursa Lelang. Di sini Anda mengirim tawaran harga (Layar 4.1b).
- **③ Tab "Diantar Petani" (50):** lot yang diantar sendiri oleh petani ke gudang Anda, jadi tidak perlu dijemput.
- **④ Filter "Belum Verifikasi Qty & Harga" (412):** menyaring lot yang berat dan harganya belum Anda konfirmasi.
  Di sampingnya ada "SEMUA (412)" dan "Sudah Terverifikasi (0)". Baris "Periode Bulan" menyaring per bulan
  ("SEMUA BULAN (412 LOT)", "Oktober 2026 (412)").

*Catatan data contoh: baris tabel pada gambar menampilkan kode "WR-LST-undefined", status Non-Aktif, dan Qty 0, dan
ringkasan bulan menunjukkan "Total: 0 Ton · Est. Nilai: Rp 0". Ini cacat tampilan data demo, bukan isi lot yang
sebenarnya.*

Tombol di atas tab: **Kontrak & Harga Pabrik Multi-Biomassa** (Layar 4.1c), **OPTIMASI RUTE TERVERIFIKASI & BIOCHAR**
(Layar 4.2a), dan **RENCANAKAN JEMPUT** (rencana jemput cepat dari tawaran lelang yang sudah diterima petani).

> **🔧 Di Balik Layar (Sistem):** Data diambil dari `GET /api/v1/collector/offers-dashboard`
> (`app/routers/collector_bidding.py`) lewat fungsi `loadMarket()` di `app/static/app.js`. Server mengelompokkan
> lot menjadi `langsung_diambil`, `lelang`, dan `diantar_petani`. Stok lelang hanya muncul untuk komoditas
> spesialisasi pengepul, diurutkan dari yang paling dekat ke gudang. Tombol **WA** pada setiap baris membuka WhatsApp
> ke petani. Nomor HP diambil lewat `GET /collector/harvests/{id}/contact`, dan setiap akses tercatat sesuai kontrol
> privasi PDP (masking di daftar, nomor lengkap hanya saat diminta).

### Layar 4.1b — Tab Bursa Lelang: Mengirim Tawaran

**Tujuan Proses & Standar Terkait:** Pengepul mengajukan harga beli untuk stok yang dilelang petani. Keputusan tetap
ada di tangan petani. Server menolak tawaran di bawah harga minimum (*reserve price*) yang dipasang petani.

![Tab Lelang aktif dengan kotak harga tawaran dan tombol TAWAR di kolom Aksi](./screenshots/14_pengepul_bursa_lelang_tawar.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Tab "LELANG (65)":** klik untuk membuka daftar stok lelang. Kolom tabel: Jenis Biomassa, Qty (kg), Kualitas &
  Titik Pasok, Pilihan Kirim, Harga/kg, Detail Petani, dan Aksi Finalisasi.
- **② Kotak harga tawaran (Rp/kg):** ketik harga beli Anda, contoh **470**. Kotak kosong di bawahnya untuk jumlah
  kg (boleh sebagian dari stok). Tombol **Hitung saran** (penasihat harga) mengisi otomatis harga yang masih
  menguntungkan. Contoh data skenario: stok 3.000 kg, harga minimum petani Rp450/kg (dijemput), tawaran Rp470/kg.
- **③ TAWAR ➔:** kirim tawaran. Muncul notifikasi "Tawaran terkirim. Petani yang memutuskan." Harga di bawah harga
  minimum petani ditolak dengan pesan berisi angka minimumnya.

*Catatan data contoh: baris pada gambar menampilkan Qty 0, Harga/kg Rp 0, dan Pilihan Kirim "Diantar". Ini cacat data
demo yang sama dengan Layar 4.1a.*

> **🔧 Di Balik Layar (Sistem):**
> - **Anti klik-ganda:** tombol dibungkus `withBusy()` (`app/static/app.js`). Selama permintaan berjalan, tombol
>   dinonaktifkan dan klik kedua diabaikan (`btn.dataset.busy === "1"`).
> - **Satu tawaran aktif per pengepul per skema:** `trade.place_bid` (`app/services/trade.py`) menarik otomatis
>   (status `WITHDRAWN`) tawaran aktif sebelumnya dari pengepul yang sama pada lot dan skema yang sama, lalu membuat
>   yang baru. Validasi yang dijalankan: lot masih terbuka dan belum kedaluwarsa, harga ≥ *reserve* petani, dan
>   jumlah ≤ sisa stok.
> - **Penerimaan atomik (CAS):** saat petani menerima tawaran (`trade.accept_bid`), stok dikurangi dengan
>   *compare-and-swap* `UPDATE … WHERE remaining_kg >= qty AND status IN (OPEN, PARTIAL)`. Tawaran dikunci sekali
>   pakai (`WHERE status = ACTIVE`). Jika dua penerimaan datang bersamaan, yang kalah mendapat pesan "Sisa stok tidak
>   mencukupi atau listing sudah ditutup — muat ulang data". Pada PostgreSQL dipakai fungsi `accept_bid_atomic`
>   (migrasi 013, `SELECT … FOR UPDATE`). Ketika stok habis, tawaran lain otomatis berstatus `REJECTED`.
> - **Penasihat harga** (`POST /collector/bid-advisor`):
>   `tawaran_maks = harga_jual_ke_pabrik − biaya_logistik_marginal/kg − margin/kg`.
>   Biaya logistik marginal = (km rute dengan lot ini − km rute tanpa lot ini) × Rp/km ÷ kg, dihitung oleh mesin rute
>   `app/engines/routing.py` (konsep *insertion cost*).

### Layar 4.1c — Modul Kontrak & Harga Jual Multi-Biomassa (margin agregator)

**Tujuan Proses & Standar Terkait:** Mencatat harga beli ke petani dan harga jual ke pabrik mitra untuk tiap komoditas,
supaya margin pengepul terlihat transparan. Margin ini dipakai sebagai dasar perhitungan tawaran yang adil bagi petani
dan pengepul.

![Tabel kontrak harga beli petani, harga jual pabrik, dan margin per komoditas](./screenshots/15_pengepul_margin_kontrak_pabrik.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Harga Beli Petani (Rp/kg):** isi harga acuan beli. Contoh baris Sekam Padi: **450**.
- **② Harga Jual Pabrik (Rp/kg):** isi harga kontrak dengan offtaker. Contoh: **580** (PT Bio-Energi Sleman).
- **③ Baris komoditas (hasil):** kolom **Margin Laba** dihitung otomatis = 580 − 450 = **+Rp130/kg**. Komoditas lain
  pada gambar: Tongkol Jagung 380/520 (+Rp140), Ampas Tebu 260/390 (+Rp130), Serbuk Sengon 320/470 (+Rp150),
  Serbuk Karet 300/460 (+Rp160), Tempurung/Sabut Kelapa 500/780 (+Rp280).
- **④ Simulasi Margin Truk:** membuka form proyeksi satu ritase. Isinya pilihan komoditas, muatan (ton, default 5),
  jarak ke pabrik (km, default 35), dan biaya truk per km (default Rp4.500). Klik **SIMPAN PERUBAHAN KONTRAK** setelah
  mengubah harga.

> **🔧 Di Balik Layar (Sistem):**
> - Simulasi margin truk (`openSimulateTruckMarginModal`, `app/static/app.js`):
>   `laba_bersih = kg × (harga_jual − harga_beli) − km × biaya_per_km`.
>   Contoh: 5.000 kg × Rp130 − 35 km × Rp4.500 = Rp650.000 − Rp157.500 = **Rp492.500 per ritase**.
> - **Margin proporsional:** penasihat tawaran (Layar 4.1b) mengambil margin dalam bentuk **persen** dari tabel ini,
>   bukan angka rupiah tetap, sehingga margin naik-turun mengikuti harga. Server menghitung
>   `margin_per_kg = harga_jual × margin_pct / 100` (`collector_bidding.py` → `bid_advisor`). Nilai default parameter:
>   `pasar.default_margin_pct` = 5 % dan `pasar.default_margin_per_kg` = Rp30/kg.
> - Tabel kontrak ini **disimpan di browser perangkat** (`localStorage`, kunci `biochain_factory_pricing_v1`), bukan di
>   server. Jika pengepul berganti HP/laptop, harga harus diisi ulang. Harga yang mengikat pabrik tetap mengikuti ajuan
>   pengiriman (Layar 4.4a).

---

## 4.2 Optimasi Rute Angkut Berbasis Volume & Muatan Balik Biochar

**Mengapa volume penting?** Sekam padi sangat ringan, dengan densitas curah ±110–120 kg/m³. Truk CDD 5.000 kg / 30 m³
yang diisi sekam akan **penuh secara volume** (30 m³ × 120 kg/m³ = 3.600 kg) jauh sebelum batas beratnya tercapai.
Karena itu rute di Bio-Chain dihitung dengan **dua batas sekaligus**: kg dan m³ bak.

### Layar 4.2a — Pilih Armada, Batas Muatan & Lot Terverifikasi

**Tujuan Proses & Standar Terkait:** Menyusun penjemputan multi-titik khusus untuk lot yang **sudah terverifikasi**
pengepul, dengan memeriksa kapasitas berat dan volume truk. Muatan balik biochar ke sawah ikut diperhitungkan.

![Modal Optimasi & Analisis Teknis Rute Penjemputan: pilihan truk, batas volume, checklist lot](./screenshots/16_pengepul_rute_clarke_wright.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Pilihan armada:** pilih truk, misalnya **"Truk CDD Box (5.000 kg / 30 m³) · AB 8421 CS"**. Plat, Batas Berat
  (**5000 kg**), dan Batas Volume terisi otomatis dari preset armada. Di sebelahnya ada pilihan jadwal ("Rotasi
  Multi-Hari (Senin – Jumat …)") dan tanggal jemput (**19/10/2026**).
- **② Batas Volume (m³):** kotak isian kapasitas bak, bersebelahan dengan Batas Berat. Untuk truk CDD nilainya
  30 m³ (lencana di judul modal: "Bak Truk: 30 m³ / 5.000 kg"). Boleh diubah bila bak diberi tambahan pagar/jaring.
- **③ Checklist lot terverifikasi:** centang lot yang akan dijemput. Contoh: #1165, #1163, dan #1161 milik Pak Sugeng
  (Penggilingan Padi Godean), masing-masing 3.000 kg sekam padi (Ref WR-HV-1165 dst.), semua berlabel "Terverifikasi
  Pengepul". Label "Muatan Balik: ~450 kg Biochar Sawah" adalah **perkiraan 15 % dari berat lot**. Gunakan
  **[✓ Pilih Semua]** / **[X Kosongkan]** untuk memilih cepat.
- **④ JALANKAN SIMULASI & ANALISIS TEKNIS ROUTING:** klik untuk menghitung. Hasilnya muncul di bawah: banner
  **"RUTE TRIP-01 LAYAK & SEIMBANG (FEASIBLE)"** dengan puncak muatan 3.300 kg (66 % kapasitas) dan 27,5 m³ (91,7 %
  volume), daftar alternatif armada/driver/hari ("149 Trip Armada Terpisah"), lalu tombol **TETAPKAN & KIRIM SURAT
  TUGAS KE BUDI SANTOSO (SENIN)** dan **Export PDF / Cetak**.

> **🔧 Di Balik Layar (Sistem):** Modal ini (`app/static/js/modules/route-optimization-modal.js`) mengirim
> `POST /api/v1/collector/consolidated-pickup-plan` (`app/routers/collector_logistics.py`) dengan `harvest_ids`,
> `truck_max_kg`, dan `truck_max_m3`. Server mengubah berat menjadi volume (`V = kg ÷ ρ`) lalu memanggil
> **Engine ⑤** `plan_routes()` di `app/engines/routing.py` dengan `mode="auto"`:
> - **≤ 10 titik** → *exact* (Held-Karp + DP *set-partitioning*), solusi optimal terbukti.
> - **> 10 titik** → **Clarke-Wright Savings** granular + *local search* (relocate, swap, 2-opt) + *iterated local
>   search* (ruin & recreate) dalam anggaran waktu.
>
> **Rumus savings Clarke-Wright (1964):** `s(i,j) = d(0,i) + d(0,j) − d(i,j)`. Artinya, menjemput titik *i* dan *j*
> dalam satu trip menghemat jarak sebesar *s* dibanding dua trip terpisah dari gudang (titik 0). Pasangan diurutkan
> dari *s* terbesar dan digabung **hanya jika** `V_rute_i + V_rute_j ≤ Q` (volume bak). Jarak = haversine × faktor jalan
> `logistik.road_factor` (1,3). Lot yang volumenya melebihi satu bak dipecah: trip penuh langsung ditambah sisa yang
> ikut solver, dengan rumus `trip_langsung = ⌈V/Q⌉ − 1`.
>
> Setelah rute terbentuk, server mensimulasikan **beban per stop**: truk berangkat membawa biochar, menurunkan biochar
> di petani, lalu memuat biomassa. Rute dinilai *feasible* bila puncak berat ≤ `truck_max_kg` **dan** puncak volume ≤
> `truck_max_m3`. Densitas yang dipakai di endpoint ini: biomassa 120 kg/m³ dan biochar 300 kg/m³. Parameter umum
> sistem `logistik.bulk_density_kg_m3` bernilai default 110 kg/m³.
>
> **Pembanding OR-Tools:** `app/engines/routing_ortools.py` (Google OR-Tools, konstruksi PATH_CHEAPEST_ARC +
> *Guided Local Search*) memodelkan **dua dimensi kapasitas sekaligus**, yaitu `Volume` (m³) dan `Weight` (kg,
> `logistik.vehicle_payload_kg` = 5.000). Fungsi tujuannya adalah **gram CO₂e** dengan biaya busur yang
> memperhitungkan muatan. OR-Tools dipakai pada mode `ortools` di `POST /api/v1/routes/optimize` dan pada alokasi
> armada pabrik `POST /factory/dispatch/optimize`. Modal pengepul ini sendiri memakai Engine ⑤ (mode *auto*), sesuai
> keterangan di kaki modal: "Algoritma: Clarke-Wright Savings + Iterated Local Search (ILS) & Dual-Constraint
> Heuristics".

### Layar 4.2b — Hasil Rute: KPI Volume, Peta & Muatan Balik

**Tujuan Proses & Standar Terkait:** Memastikan rute aman secara kapasitas dan menunjukkan penghematan jarak sebelum
surat tugas dikirim ke driver. Jarak dan muatan menjadi dasar estimasi emisi transport (ISO 14083 di sisi driver).

![Banner kelayakan, KPI rute, dan peta Leaflet](./screenshots/17_pengepul_rute_hasil_backhaul.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Banner kelayakan:** **"RUTE TRIP-01 LAYAK & SEIMBANG (FEASIBLE)"**, dengan keterangan "Truk CDD Box (5.000 kg /
  30 m³) (AB 8421 CS) aman membawa muatan di seluruh rute. Puncak muatan: 3.300 kg (66% kapasitas) & 27,5 m³ (91,7%
  volume)". Jika melewati batas, banner berubah merah menjadi peringatan overload dengan saran membagi ke multi-armada.
  Di bawahnya ada kartu **Supir Armada: Budi Santoso** (★ 4.9, telepon, jenis mobil) dan **Jadwal Hari Pengambilan:
  Senin (Gelombang 1 – Sleman Barat: Godean, Moyudan, Minggir)**.
- **② Baris KPI trip (hasil):** **Jarak TRIP-01 25,6 km** ("Hemat 31% vs manual"), **Estimasi Waktu Tempuh 1 jam
  29 mnt** (3 titik transit), **Puncak Beban Berat 3.300 kg** (66 % dari batas 5.000 kg), **Puncak Kubikasi Bak
  27,5 m³** (92 % dari batas 30 m³), **Biomassa Trip Ini 3.300 kg** (vol 27,5 m³), dan **Biochar Muatan Balik 0 kg**
  (vol 0 m³).
- **③ Peta Visualisasi Spasial:** tampilan **PETA SATELIT (OSM)** (Leaflet) atau **Vektor Topologi (SVG)**. Garis
  oranye menghubungkan titik jemput dan gudang di wilayah Sleman (Godean ↔ Pandowo Harjo).

Di bawah peta ada tabel **Urutan Teknis Perjalanan & Timeline Beban Bak (Stop-by-Stop)** dengan kolom Urutan/Tahap,
Titik Lokasi & Aktivitas, Biomassa Dimuat, Biochar Diturunkan, dan Akumulasi. Baris yang melewati batas ditandai
merah. Setelah dicek, klik **TETAPKAN & KIRIM SURAT TUGAS** untuk menugaskan driver, atau **Export PDF / Cetak** untuk
manifest 1–2 halaman.

> **🔧 Di Balik Layar (Sistem):**
> - **Muatan balik (backhaul):** biochar baru dihitung bila permintaan biochar petani (`biochar_backhaul_requests`)
>   ikut dikirim. Volume biochar = kg ÷ 300 kg/m³. Biochar diturunkan di petani pemesan sehingga ruang bak bertambah
>   untuk biomassa yang dimuat. Pada data contoh ini nilainya **0 kg** karena modal belum mengirim daftar permintaan
>   biochar. Angka "~450 kg" pada checklist Layar 4.2a hanya perkiraan tampilan (15 %).
> - **"Hemat … % vs manual"** di kartu KPI dihitung di layar terhadap jarak acuan = jarak rute × 1,45, sehingga
>   nilainya selalu ±31 % (indikatif). Penghematan yang benar-benar dihitung solver terhadap trip langsung per titik
>   ada di `summary.saving_pct` Engine ⑤ (dipakai di Rencana Jemput dan `/routes/optimize`).
> - **Estimasi waktu** = jarak ÷ 35 km/jam + 15 menit per stop.

---

## 4.3 Uji Cepat Lapangan, Timbang Aktual, Resi TRX & Pembayaran Petani

### Layar 4.3a — Uji Mutu Lapangan, Timbang Aktual & Grade Otomatis

**Tujuan Proses & Standar Terkait:** Menetapkan berat **aktual** dan mutu biomassa di lokasi petani sebagai dasar harga.
Harga dihitung dari timbangan pengepul, bukan dari estimasi petani. Inilah prosedur **"Uji Cepat Lapangan"**: sebuah
*prosedur kerja* memakai form Uji Mutu ini (kadar air wajib dengan moisture meter, kontaminan ditaksir visual, abu/VM/FC
opsional dari lab). **Aplikasi tidak memiliki timer atau label "15 menit".** Durasi uji adalah target prosedur di
lapangan.

![Antrean lot di kiri, form timbang dan uji mutu di kanan](./screenshots/18_pengepul_uji_cepat_grade.png)

Sebelum mengisi form, klik tombol **UJI** pada baris lot di tabel antrean kiri (lot Sekam padi 3.000 kg atau 5.000 kg,
taksiran petani 12,5 % / 13,2 %). Tombol cokelat di bawah form berubah menjadi **"VERIFIKASI MUTU #1164 ➔"**.

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Berat Timbangan Pengepul (kg):** ketik hasil timbang aktual, contoh **4950** (petani melapor 5.000 kg). Tombol
  cepat **−50 / +50 / +100 / +500 / +1 ton / +1 truk** membantu koreksi tanpa mengetik.
- **② Kadar Air (% bb) — wajib:** baca dari moisture meter, contoh **13.2**. Kolom **Kadar Abu (% bk)**, **Volatile
  Matter (%)**, dan **Fixed Carbon (%)** bertanda "opsional · uji lab". Biarkan kosong bila tidak ada hasil lab.
- **③ Kontaminan (%):** taksiran pasir/batu/plastik, contoh **0.5**. Suhu Pirolisis default **500 °C**. Foto bukti
  bisa diisi lewat **URL Foto Bukti Serah-Terima (opsional)** atau tombol **Ambil foto**.
- **④ Preview Mutu:** kotak bertuliskan "Grade A · Skor 91.2 · Pengali Harga ×1.10". *Catatan jujur: teks ini adalah
  contoh statis bawaan form dan tidak dihitung ulang saat angka diketik.* Grade resmi baru keluar setelah tombol ⑤
  ditekan dan tampil di resi (Layar 4.3b).
- **⑤ VERIFIKASI MUTU #1164 ➔:** klik untuk mengirim hasil timbang dan uji. Jika mutu tidak layak, gunakan **Tolak lot
  (sebutkan penyebab)** dan pilih kategori: terlalu basah, berjamur, kontaminan, selisih berat, stok tidak ada, atau
  lainnya.

> **🔧 Di Balik Layar (Sistem):** `POST /api/v1/collector/verify` (`app/routers/collector.py`) memanggil
> `score_sample()` di `app/engines/quality.py`:
> - Skor komponen linear: kadar air (ideal `harga_mutu.moisture_best` = 10 %, tolak > `harga_mutu.moisture_reject`
>   = 25 %) dan kontaminan (ideal 1 %, tolak > 10 %). Abu dan fixed carbon ikut dinilai **hanya bila diisi**, dan
>   bobot dinormalisasi atas komponen yang terukur.
> - **Grade hasil verifikasi pengepul:** skor ≥ `harga_mutu.grade_A_min` (80) → **A**, ≥ `grade_B_min` (60) → **B**,
>   di bawahnya → **C**. Jika melewati batas tolak → **TOLAK** (tidak dibeli). Grade **D** hanya muncul pada
>   *estimasi petani* di form lapor (aturan kadar air: ≤ 12 → A, ≤ 15 → B, ≤ 18 → C, > 18 → D).
> - **Harga ke petani** (metode default `harga_mutu.pricing_method = basis_kering`, `quality.farmgate_price`):
>   `harga/kg = harga_dasar × (1 − M) / (1 − M_acuan)`, `kg_bayar = timbangan × (1 − kontaminan)`,
>   `total = kg_bayar × harga/kg`. M_acuan = `harga_mutu.reference_moisture_pct` (12 %). Untuk lot lelang dipakai harga
>   kesepakatan, dan hanya ada potongan bila lebih basah dari kontrak. Contoh pada gambar (harga dasar Rp450/kg):
>   450 × (1 − 0,132)/(1 − 0,12) = Rp443,86/kg; kg bayar = 4.950 × (1 − 0,005) = 4.925,25 kg; total ≈
>   **Rp2.186.121**, sama dengan angka di resi.
> - Pengiriman memakai `apiMutation` dengan `client_event_id`. Bila tanpa sinyal, hasil uji disimpan di antrean HP
>   ("Offline: hasil uji disimpan & dikirim otomatis saat online"), dan pengulangan dari antrean tidak menggandakan data.
>   Status lot: `REPORTED → VERIFIED` dengan *custody event* `COLLECTOR_WEIGH`.

### Layar 4.3b — Resi Serah-Terima TRX & QR (Chain of Custody)

**Tujuan Proses & Standar Terkait:** Memberi petani bukti serah-terima yang unik dan bisa dipindai. Resi ini menyambung
QR asal lot ke tahap berikutnya (driver → pabrik), sesuai prinsip ketertelusuran *chain of custody* ISO 22095.

![Modal Resi Serah-Terima Sekam dengan QR dan kode TRX](./screenshots/19_pengepul_resi_serah_terima.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Judul "Resi Serah-Terima Sekam":** muncul otomatis setelah verifikasi berhasil. Tunjukkan QR 2D ini kepada
  sopir armada atau mitra logistik untuk dipindai.
- **② Kode resi (hasil):** **TRX-PTN0006-PGP0003-2610-00183** dengan ringkasan **"4.950 kg · Grade A ·
  Rp 2.186.121"**. Kotak "Rantai Ketelusuran Batch" menampilkan Kode Dokumen, **QR Code Asal BIO-F4733DAE-DEDHTO**,
  **Batch Referensi WR-HV-1164**, rincian muatan (sekam_padi · 4.950 kg · Grade A), dan alur mutasi *Pelaporan Awal →
  Lelang → Timbang TRX → Pabrik*. Tombol: **TELUSURI SILSILAH SIRKULAR PENUH**, **Salin Teks**, **UNDUH GAMBAR QR**,
  **Cetak**.

> **🔧 Di Balik Layar (Sistem):** Format kode `TRX-<pengirim>-<penerima>-<YYMM>-<urut bulanan>` (PTN0006 = petani,
> PGP0003 = pengepul, 2610 = Oktober 2026, 00183 = nomor urut). Kode dibuat server saat verifikasi dan dicatat sebagai
> *custody event*. Tombol telusuri membuka modal Lacak QR Sirkular (sama dengan Bab 3.5) yang menampilkan rantai
> sawah → pengepul → pabrik → abu/biochar → sawah beserta hash rantainya.

### Layar 4.3c — Instruksi Pembayaran ke Petani (DP / Lunas) & SLA

**Tujuan Proses & Standar Terkait:** Membayar petani tepat waktu dan tercatat. SLA bayar petani di Bio-Chain adalah
**maksimal 3 hari** setelah lot ditimbang (lebih ketat dari target ≤ 14 hari).

![Kartu Bayar petani dengan tabel lot belum dibayar dan tombol DP/BAYAR](./screenshots/20_pengepul_bayar_petani_dp.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Kartu "💸 Bayar petani":** berisi lot yang sudah Anda timbang tetapi belum tercatat dibayar. Keterangannya: "DP
  (uang muka) dipotong otomatis saat pelunasan."
- **② Ringkasan dan tabel lot:** **TOTAL TAGIHAN BELUM DIBAYAR: Rp 59.781.799 (100 lot · 131.880 kg)**, terbagi dalam
  1 periode bulan. Grup **Oktober 2026** berisi 100 lot, 131.880 kg, dan bisa dibuka lewat "Detail Lot ▾". Contoh baris:
  - **#1164** · 4.950 kg · Grade A · Pak Sugeng (Penggilingan Padi Godean) · 18 Okt 2026 · **Rp 2.186.121** (lot dari
    Layar 4.3b)
  - #1165 · 2.950 kg · Grade A · Rp 1.315.988
  - #1141 · 880 kg · Grade A · Mbah Karto (Sidoarum) · Rp 396.492
- **③ Kolom Lot dan tombol aksi per baris:** kolom **Lot** memuat #ID, kg, dan Grade. *Pada gambar, kotak ③ menandai
  judul kolom LOT, bukan tombolnya.* Di ujung kanan setiap baris ada dua tombol:
  - **DP**: mencatat uang muka. Hanya untuk lot yang belum diangkut, maksimal `pasar.dp_max_pct` = **30 %** dari
    perkiraan nilai lot.
  - **BAYAR**: pelunasan. Pilih metode (tunai/transfer/QRIS). **No. referensi wajib** untuk selain tunai.
  Setelah dicatat, muncul **Kuitansi bayar petani** dengan kode kuitansi, nilai bersih, serta rincian bruto − pajak −
  DP untuk diberikan atau difoto petani.

> **🔧 Di Balik Layar (Sistem):** Daftar diambil dari `GET /collector/unpaid-harvests`. Pembayaran dicatat lewat
> `POST /collector/harvests/{id}/pay-farmer` dan DP lewat `POST /collector/harvests/{id}/pay-dp`
> (`app/services/payments.py`).
> - **DP dipotong otomatis saat pelunasan.** Jika DP melebihi nilai timbangan, sisanya dicatat sebagai kewajiban petani
>   untuk mengembalikan.
> - DP dan pelunasan untuk lot yang sama diserialkan dengan **kunci baris harvest** (`lock_row`), sehingga petani tidak
>   bisa menerima DP + pelunasan penuh akibat klik bersamaan. Kiriman ganda DP ditolak ("baru saja tercatat").
> - Pajak (PPh 22 petani) dihitung server bila parameter `pajak.pph22_farmer_pct` diisi.
> - **SLA:** parameter `pasar.farmer_payment_due_days` (default **3 hari**, rentang 0–60). Lot terverifikasi yang belum
>   dibayar melewati batas ini ditandai **terlambat** di menu Pembayaran petani (Bab 3.5). Keterlambatan juga masuk
>   indikator sosial ESG dan temuan efisiensi P8 "Pembayaran petani terlambat".

---

## 4.4 Pengiriman ke Pabrik, Piutang, Muatan Balik & Umpan Balik QC

### Layar 4.4a — Ajukan Pengiriman ke Pabrik (Dijemput Armada Pabrik / Antar Mandiri)

**Tujuan Proses & Standar Terkait:** Pengepul mengajukan *Delivery Request* (DR) ke pabrik: berapa kg, mutu, tanggal, dan
harga. Pabrik bisa menerima, menawar balik, atau menolak (Bab 6.1). Lot petani yang dilampirkan memastikan bagian biochar
sirkular kembali ke dompet petani yang bersangkutan.

![Form Ajukan Pengiriman ke Pabrik dan tabel ajuan](./screenshots/21_pengepul_ajukan_kirim_pabrik.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Jenis Biomassa:** pilih **Sekam Padi**. Pabrik Tujuan: **Pabrik Utama (PLTBm Pusat)**.
- **② Moda Logistik:**
  - **Dijemput Armada Pabrik (Factory Fleet)**: truk pabrik yang menjemput ke gudang Anda.
  - **Antar Mandiri Pengepul (Self-Delivery Slip)**: Anda mengirim sendiri dengan truk pengepul.
  Skema Penentuan Harga: **Ikut Acuan Kadar Air Pabrik** atau **Tawar Bebas**.
- **③ Jumlah (kg):** contoh **4950** (sama dengan hasil timbang di Layar 4.3a). Tersedia tombol cepat −50 … +1 truk.
  Kadar air (%) contoh **11**, Tanggal kirim **21/10/2026**.
- **④ Harga diajukan (Rp/kg):** terisi otomatis dengan harga rekomendasi, contoh **1384**. Di bawahnya tampil
  **"REKOMENDASI PABRIK: RP 1.384/KG (netback produk bio-pellet, biochar, bio-silika − biaya − margin pabrik)"**.
  Ubah angkanya bila ingin menawar lain (pilih skema "Tawar Bebas"). Buka **"Lampirkan lot biomassa petani"** untuk
  mengaitkan lot petani.
- **⑤ AJUKAN PENGIRIMAN ➔:** kirim ajuan. Ajuan masuk ke tabel di bawah dengan status awal **submitted / MENUNGGU
  PABRIK** (contoh #56 dan #55, masing-masing 2.950 kg, Armada Pabrik, Rp 1.350/kg · 2026-10-18). Ajuan yang masih
  menunggu bisa **Batalkan**. Ajuan yang disetujui pabrik berstatus **accepted**. Ringkasan grup: "Sekam Padi · 22 Ajuan ·
  Total 66,77 ton".

> **🔧 Di Balik Layar (Sistem):** `POST /api/v1/collector/delivery-requests` → `factory_ops.submit_request`
> (`app/services/factory_ops.py`). Field `logistics_carrier` bernilai `FACTORY_FLEET | COLLECTOR_SELF` dan
> `pricing_mode` bernilai `FACTORY_PRICE | AUCTION`. Rekomendasi harga diambil dari `GET /collector/factory-price`
> (`factory_ops.factory_price_preview`) untuk kadar air yang diisi. Negosiasi berjalan lewat
> `POST /delivery-requests/{id}/respond` (accept | counter | reject | cancel). **Berat yang menentukan tagihan adalah
> hasil jembatan timbang di gerbang pabrik** (Gross − Tare = Net, Bab 6.1), bukan angka ajuan ini.

### Layar 4.4b — Rute Konsolidasi & Muatan Balik, Piutang Pabrik & Status DR

**Tujuan Proses & Standar Terkait:** Memantau uang yang masih harus dibayar pabrik (piutang) beserta umurnya, dan membuka
modul rute muatan balik biochar.

![Kartu Rute Konsolidasi & Muatan Balik Biochar dan tabel Piutang Pabrik](./screenshots/22_pengepul_backhaul_piutang.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Status muatan balik:** kartu "Rute Konsolidasi & Muatan Balik Biochar" (kapasitas ganda 30 m³ & 5.000 kg).
  Teksnya: "Klik tombol di atas untuk membuka modul pop-up optimasi rute terverifikasi…". Klik **OPTIMASI & TEKNIS
  RUTE TERVERIFIKASI** untuk membuka Layar 4.2a.
- **② Piutang Pabrik & Status DR:** **TOTAL PIUTANG BELUM TERBAYAR: RP 57.520.500 (19 pengiriman)**. Grup **Oktober
  2026** berisi 23 pengiriman, 69.270 kg, Rp 60.557.460. Tabel memuat Kode DR (DR-0056, DR-0055 …), Pabrik (Pabrik
  Biochar Sleman), Net (kg), Tagihan (Rp), **Umur Piutang** (0–2 hari), dan Status (submitted / accepted / rejected).

Di bawah kartu piutang ada kartu **Potongan logistik saya**: ongkos jarak kosong bila pengepul membatalkan saat truk
sudah di jalan atau stok tidak ada saat truk tiba. Potongan ini dikurangkan dari pembayaran pabrik berikutnya.

> **🔧 Di Balik Layar (Sistem):** `GET /collector/factory-receivables` (`app/routers/collector.py`). Umur piutang =
> hari sejak DR dibuat. Status `settled / paid / delivered` dianggap lunas. Angka total di atas hanya menjumlahkan yang
> **belum lunas**, sedangkan angka grup bulan menjumlahkan semua DR pada bulan itu. Karena itu kedua angka bisa berbeda
> (Rp57,52 jt vs Rp60,56 jt). Potongan logistik dari `GET /collector/charges` berstatus *terbuka / dipotong /
> dibebaskan*.

### Layar 4.4c — Transparansi Mutu & Evaluasi QC Gerbang Pabrik

**Tujuan Proses & Standar Terkait:** Pengepul melihat hasil timbang jembatan dan uji mutu pabrik untuk setiap kiriman:
berapa kg yang diterima atau ditolak, dan apa sebabnya. Dengan begitu perbaikan mutu bisa diteruskan ke petani.

![Tabel Transparansi Mutu & Evaluasi QC Gerbang Pabrik](./screenshots/23_pengepul_umpan_balik_qc_pabrik.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Tabel QC gerbang:** dikelompokkan per komoditas. Kolom: **No. Tiket** (mis. GATE-20261016-8C8601, 16 Okt 2026),
  Biomassa, **Netto Timbang**, **Diterima**, **Ditolak**, **Hasil Uji (MC / Abu / LHV)**, **Alasan Penolakan**,
  **Saran Perbaikan Mutu**. Contoh:
  - **SEKAM PADI:** 4.000 kg diterima penuh. Hasil 13 % | 15,5 % | 3.550, dengan saran "Kandungan pasir/tanah
    menyebabkan abu 15.5%".
  - **SERBUK SENGON:** 2.000 kg ditolak. Hasil 28 % | 16 % | 3.500, alasan "Kadar air 28% melebihi batas dan
    terkontaminasi tanah", saran "Lakukan penjemuran terpal".
- **② Refresh:** memuat ulang data terbaru setelah pabrik memproses tiket baru.

> **🔧 Di Balik Layar (Sistem):** `GET /collector/gate-feedback` (`app/routers/collector.py`) membaca catatan penerimaan
> gerbang pabrik (tiket timbang + keputusan QC: diterima / diterima sebagian / ditolak, Bab 6.1). Hasil QC lot juga
> diteruskan ke harvest petani yang dilampirkan, dibagi proporsional timbangan (`factory_ops.py`), sehingga petani
> menerima umpan balik yang sama di Bab 3.5.

---

# Bab 5 — Panduan Langkah demi Langkah Modul Driver & Ketertelusuran Lapangan

Modul Driver dipakai sopir truk di HP (layar 390 × 844), sering di tempat dengan sinyal lemah. Prinsipnya: **setiap
tindakan tetap bisa disimpan tanpa sinyal** dan terkirim otomatis saat sinyal kembali. Akun demo: **Budi Santoso
(Driver)**.

> **Catatan peran:** Driver **tidak** menginput slip timbangan jembatan. Penimbangan resmi (Gross/Tare/Net) dilakukan
> petugas di gerbang pabrik (lihat **Bab 6.1**). Berat yang dibawa driver hanya catatan; angka otoritatif tetap
> timbangan pengepul (Bab 4.3) dan jembatan timbang pabrik.

## 5.1 Daftar Job, Utilisasi Volume Bak & Instruksi Muatan Balik

### Layar 5.1a — Status Rute, Jarak & Utilisasi Bak

**Tujuan Proses & Standar Terkait:** Driver melihat rute yang ditugaskan, jarak rencana, jarak GPS yang terekam, dan
seberapa penuh bak truk (berbasis volume, karena sekam ringan).

![Kartu KPI driver: status rute, jarak rencana, jarak GPS, utilisasi bak](./screenshots/24_driver_daftar_job_kapasitas.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Status Rute:** pada gambar **BERJALAN**, artinya rute sudah dimulai. Sebelum dimulai, statusnya
  **DIRENCANAKAN**. Di sebelahnya: **Jarak Rencana 28,1 km** (estimasi jalan).
- **② Utilisasi Bak: 36,4 %** (volume terisi). Kartu **Jarak GPS Terekam: 0 km** bertanda "tersimpan walau offline".

**Tombol aksi rute** (di bawah daftar stop, tidak tampak pada gambar): **▶️ Mulai Rute (aktifkan GPS)** sebelum
berangkat. Setelah rute berjalan, tombol berubah menjadi **🏁 Selesaikan Rute**. Tombol ini terkunci selama masih ada
stop yang belum ditangani.

Di bawah KPI ada kartu **AI Optimizer & Evaluator Logistik Armada** (skor kesehatan 63 · Grade C, 1 Kritis, 1 Baik)
yang merangkum efisiensi rute, BBM B40, dan muatan bak selama 3 bulan terakhir. Prioritas optimasi teratas pada gambar
adalah **"Utilisasi bak truk (rencana) 38,8 % (target ≥ 85 %)"**, dengan saran "Minta pabrik menggabungkan titik
berdekatan agar bak terisi; susun karung rapat" dan tombol **Tanya AI soal ini**.

> **🔧 Di Balik Layar (Sistem):** `loadDriverData()` (`app/static/app.js`) membaca `GET /api/v1/driver/active-route`
> (`app/routers/driver.py`). Rute terakhir disimpan di HP (`localStorage biochain_driver_route:<id>`) sehingga tetap
> tampil saat offline. `utilization_pct` berasal dari Engine ⑤: `100 × m³ muatan ÷ m³ bak`. **Mulai Rute**
> (`POST /driver/start-route`) dan **Selesaikan Rute** (`POST /driver/complete-route`) dikirim lewat antrean offline.
> Saat selesai, server menghitung jarak nyata dari jejak GPS serta BBM dan CO₂e menurut ISO 14083. Sebelum itu, antrean
> pickup offline dikirim lebih dulu (`flushOutbox`, `trackFlush`).

### Layar 5.1b — Instruksi Muatan Balik Abu/Biochar (Pabrik → Petani)

**Tujuan Proses & Standar Terkait:** Menutup lingkar ekonomi sirkular. Truk yang kembali dari pabrik membawa biochar/abu
untuk sawah petani, dan setiap titik serah-terimanya terekam.

![Daftar penugasan muatan balik biochar dengan tombol Scan Outbound dan Konfirmasi Serah Sawah](./screenshots/27_driver_muatan_balik_biochar.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Daftar penugasan muatan balik:** setiap kartu berisi kode dispatch, plat, muatan, volume, instruksi, dan status.
  Contoh:
  - **DSP-A740A4A4** · Plat AB 8888 XY · 500 kg (20 karung) · 1,67 m³ · "Antar ke sawah binaan petani kelompok tani
    mitra" · **DELIVERED_TO_FARMER** ("✓ Selesai diantar ke sawah").
  - **DSP-BACKHAUL-01** · AB 1234 CD · 500 kg · 1,2 m³ · "Muatan balik biochar mutu A untuk Kelompok Tani Sleman".
  - **DSP-ADE3D931** dan **DSP-10AE14F0** · status **DISPATCHED** (belum diantar). Kartunya masih menampilkan
    tombol aksi ② dan ③.
- **② Scan Outbound:** tekan saat memuat biochar di gerbang keluar pabrik. Checkpoint `FACTORY_OUTBOUND` tercatat.
- **③ KONFIRMASI SERAH SAWAH:** tekan saat tiba di sawah. Isi **ID Petani Penerima**, **Berat Biochar Diserahkan
  (kg)** (default sesuai muatan), dan **Catatan Serah Terima**, lalu **Konfirmasi Serah Terima**. Status berubah menjadi
  **DELIVERED_TO_FARMER**.

> **🔧 Di Balik Layar (Sistem):** Data dari `GET /driver/backhaul-tasks`. Scan outbound memanggil
> `POST /driver/checkpoint-scan` dengan `checkpoint_type = FACTORY_OUTBOUND`, dan serah sawah memanggil
> `POST /driver/confirm-backhaul-drop`. Surat jalan biochar dibuat oleh pabrik (Bab 6.4). Endpoint serah sawah
> menerima `evidence_photo_url`, tetapi dialog di aplikasi driver saat ini belum menyediakan kolom foto.

## 5.2 Titik Jemput, Scan QR Checkpoint, Laporan Gagal & Mode Offline

### Layar 5.2a — Titik Jemput: Scan QR atau Laporkan Gagal

**Tujuan Proses & Standar Terkait:** Membuktikan bahwa lot yang dimuat adalah lot yang benar (QR karung/nota cocok), di
lokasi yang benar, pada waktu yang benar. Ini adalah checkpoint serah-terima kedua dalam rantai ketertelusuran
(selaras ISO 22095).

![Kartu Stop #1 dengan tombol SCAN QR, pilihan alasan gagal, dan tombol Gagal](./screenshots/25_driver_titik_jemput_scan.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Kartu stop:** **Stop #1: Penggilingan #21 – Berbah**, komoditas **sekam padi**, rencana **1.2 Ton**. Tombol aksi
  baru muncul setelah rute dimulai (**Mulai Rute**, Layar 5.1a).
- **② SCAN QR 📷:** tekan saat tiba. Kamera terbuka dengan judul "Scan QR Petani (Stop #…)". Arahkan ke QR karung/nota
  atau resi TRX (Layar 4.3b). Jika berhasil, muncul "✅ Pickup dikonfirmasi!" dan stop berlabel **DIJEMPUT**.
- **③ Alasan gagal + tombol "Gagal ❌":** bila biomassa tidak bisa diambil, pilih alasan lalu tekan **Gagal ❌**.
  Pilihan alasan: *Biomassa tidak ada / sudah dijual*, *Dibatalkan pengepul*, *Basah / berjamur*, *Jalan tidak bisa
  dilalui*, *Lokasi / titik tutup*, *Bak truk penuh*, *Lainnya*. Stop ditutup sebagai **GAGAL** dan lot kembali ke
  antrean.

Di atas layar terlihat banner **"Sinyal tersedia — 1 titik GPS menunggu dikirim"** dengan tombol **Kirim sekarang**.

> **🔧 Di Balik Layar (Sistem):** `confirmPickupStop()` → `startCameraScanner()` → `sendPickup()` di
> `app/static/app.js` → `POST /api/v1/driver/confirm-pickup` (`app/routers/driver.py`).
> - **Cek QR tanpa sinyal:** sebelum dikirim, HP mencocokkan QR dengan *digest* SHA-256 yang ikut dalam rute
>   (`qr_check`, QR bertanda tangan F14). Jika QR salah, muncul "QR tidak cocok dengan lot di stop ini" dan tidak ada
>   yang dikirim. Server mengecek ulang tanda tangan: QR palsu ditolak "QR tidak sah", lot berbeda ditolak "QR code
>   tidak cocok". QR lama tanpa tanda tangan mengikuti kebijakan `logistik.qr_legacy_policy`.
> - **GPS & geofence:** koordinat HP dibandingkan dengan titik penggilingan (haversine). Jika lebih jauh dari
>   `logistik.pickup_geofence_m` (default **500 m**), pickup tetap diterima tetapi **ditandai untuk auditor** ("⚠️ Lokasi
>   scan jauh dari penggilingan").
> - **Waktu & offline:** `client_recorded_at` = waktu scan sebenarnya di HP, walaupun terkirim belakangan. Server
>   memakai jam HP hanya bila berada dalam jendela **−`CLIENT_CLOCK_MAX_PAST_HOURS` (72 jam)** sampai
>   **+`CLIENT_CLOCK_MAX_FUTURE_MINUTES` (10 menit)**. Di luar itu dipakai jam server dan diberi catatan
>   (`trusted_device_time`, `app/services/custody.py`). *Custody event* menyimpan keduanya.
> - **Aman diulang:** setiap aksi membawa `client_event_id`. Kiriman ulang dari antrean dijawab "sudah dikonfirmasi
>   sebelumnya" tanpa data ganda. Status lot: `VERIFIED → COLLECTED` (*custody stage* `DRIVER_PICKUP`).
> - **Foto bukti:** API menerima `photo_url`, tetapi alur Scan QR di aplikasi driver **belum** menyediakan pengambilan
>   foto (dikirim kosong). Foto serah-terima saat ini diambil pengepul di Layar 4.3a.
> - Laporan gagal: `POST /driver/stop-failed` (`logistics.fail_stop`), juga lewat antrean offline dan menyertakan GPS.

### Layar 5.2b — Pemindai QR Checkpoint

**Tujuan Proses & Standar Terkait:** Membaca kode QR karung, nota, atau layar mitra dengan kamera HP. Jika kamera rusak
atau QR buram, kode bisa diketik manual sehingga pekerjaan tidak terhenti.

![Modal Pemindai QR Kamera Bio-Chain dengan area kamera dan input manual](./screenshots/26_driver_scanner_qr_checkpoint.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Judul "Pemindai QR Kamera Bio-Chain":** dibuka dari tombol **SCAN QR** di header. Petunjuknya: "Arahkan kamera
  HP/webcam Anda ke kode QR karung atau layar mitra. Kode akan terbaca otomatis seketika."
- **② Area kamera:** bingkai bidik dengan garis laser pemindai. *Pada gambar, isi kamera berupa pola hijau uji
  (kamera simulasi browser), bukan QR sungguhan.* Tombol **Ganti Kamera** menukar kamera depan/belakang. **Upload Foto
  QR** membaca QR dari foto di galeri.
- **③ "Atau ketik/paste kode QR manual":** ketik kode, contoh `BIO-A1B2C3D4`, lalu tekan **GUNAKAN**. **Tutup
  Pemindai** untuk keluar.

> **🔧 Di Balik Layar (Sistem):** `startCameraScanner()` (`app/static/app.js`) menangani kamera, unggah foto, dan input
> manual. Pemindai yang dibuka dari header (`openGlobalScanner`) hanya **menampilkan isi kode** yang terbaca. Untuk
> mencatat checkpoint pickup, driver harus memakai tombol **SCAN QR** di kartu stop (Layar 5.2a). Pemindai yang sama
> kemudian mengirim `confirm-pickup` beserta GPS dan waktu.

### Layar 5.2c — Mode Hemat Sinyal (Offline) & GPS Tersimpan

**Tujuan Proses & Standar Terkait:** Menjamin data lapangan tidak hilang di daerah tanpa sinyal. Scan, laporan gagal,
mulai/selesai rute, dan titik GPS disimpan di HP, lalu dikirim berurutan saat sinyal kembali.

![Banner Mode Hemat Sinyal di bagian atas layar driver](./screenshots/28_driver_mode_offline.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Banner "Mode Hemat Sinyal":** muncul otomatis saat HP kehilangan koneksi. Isinya: "Data yang Anda simpan aman di
  HP ini dan terkirim otomatis saat sinyal kembali. **1 titik GPS**." Tetap bekerja seperti biasa. Tidak perlu menutup
  aplikasi.

Selama offline, kartu **Jarak GPS Terekam** (Layar 5.1a) terus bertambah dan daftar stop serta muatan balik tetap bisa
dibuka. Saat sinyal kembali, banner berubah menjadi **"Sinyal tersedia — … menunggu dikirim"** dengan tombol **Kirim
sekarang** (lihat Layar 5.2a).

> **🔧 Di Balik Layar (Sistem):**
> - Banner diatur `syncBanner()` (`app/static/ui-enhance.js`). Banner menghitung antrean data (`myOutbox()`) dan titik
>   GPS tertunda (`TRACK.pending`), lalu menampilkan "Sesi berakhir" bila token kedaluwarsa saat offline lama. Antrean
>   **tetap disimpan** dan dikirim setelah login ulang.
> - Antrean aksi tulis disimpan di HP (kunci `biochain_outbox`). Setiap item membawa `client_event_id` dan waktu
>   perangkat. `flushOutbox()` mengirim item **berurutan**: foto antrean diunggah dulu, lalu berhenti bila jaringan
>   masih putus atau server sibuk, dan dicoba lagi nanti.
> - Jejak GPS dan jarak per rute disimpan di penyimpanan lokal (IndexedDB, `track-km-<route>`) dan dikirim lewat
>   `POST /driver/track`.
> - Waktu kejadian dari HP diterima server bila tidak lebih tua dari `CLIENT_CLOCK_MAX_PAST_HOURS` (**72 jam**,
>   `app/config.py`). Lebih dari itu, server memakai jam server untuk laporan dan mencatat selisihnya.
