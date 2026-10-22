# Revisi SOP — PETA_FLOW_DAN_STEP_BY_STEP_BIOCHAIN

Panduan penyuntingan manual (Okt 2026). Setiap butir berisi **LOKASI** di dokumen SOP, **TINDAKAN** (GANTI / TAMBAHKAN / HAPUS), dan **TEKS BARU** yang siap ditempel. Semua perilaku yang dijelaskan sudah ada di kode dan teruji (`tests/test_field_ops.py`, `tests/e2e_offline_driver.spec.ts`).

## R-01 · BAB 1.5 Matriks Engine — TAMBAHKAN 2 baris

| Engine | Nama | Algoritma & Metodologi | Fungsi |
|---|---|---|---|
| Engine ⑫ | Emisi Logistik Hijau | ISO 14083:2023 / GLEC v3.2, berbasis BBM, B40 | kg CO₂e per rute & per ton sekam dari jarak GPS nyata (termasuk km kosong) |
| Engine ⑬ | Green Scorecard | IPCC 2006/2019, E-factor Sheldon | Neraca karbon bersih, indikator sirkular, E-factor lini silika |

Ubah juga baris Engine ⑤ menjadi: "CVRP Exact (Held-Karp+DP) / Clarke-Wright+ILS / **Google OR-Tools (alokasi armada, objektif CO₂e)**".

## R-02 · BAB 2.3 Protokol Offline-First — GANTI seluruh isi butir 1–4

1. Setiap aksi lapangan (lapor stok, timbang, scan pickup, stop gagal, mulai/selesai rute) diberi `client_event_id` (UUID v4) dan `client_recorded_at` (jam perangkat).
2. Bila sinyal hilang atau server membalas 408/429/5xx, aksi disimpan di **IndexedDB** perangkat (tahan aplikasi ditutup/HP restart), bukan dibuang.
3. Pengiriman ulang dipicu oleh: sinyal kembali, aplikasi dibuka lagi, interval 30 detik, ketukan pada indikator antrean, dan **Background Sync** (Chrome/Edge Android). Safari/Firefox tidak mendukung Background Sync, jadi memakai pemicu lainnya.
4. Server memeriksa `client_event_id`. Kiriman ganda menghasilkan respons sukses yang sama **tanpa data ganda**, termasuk kasus "server sudah memproses tetapi respons hilang di jalan".
5. **BARU** — Bila sesi login kedaluwarsa saat offline lama (> 8 jam), antrean **tetap disimpan**. Pengguna diminta login ulang, lalu antrean dikirim.
6. **BARU** — Aksi yang ditolak aturan bisnis (mis. stok sudah diambil pihak lain) dipindah ke **kotak gagal** agar bisa ditinjau, tidak hilang diam-diam.
7. **BARU** — Jam perangkat yang menyimpang (> 72 jam ke belakang atau > 10 menit ke depan) tidak dipakai untuk laporan. Server memakai jam server dan mencatat penyimpangan di jejak custody.

## R-03 · BAB 2.4 BARU — Pelacakan GPS Store & Forward

TAMBAHKAN sub-bab baru setelah 2.3:

> Selama rute berjalan, aplikasi supir merekam titik GPS perangkat setiap ≥ 25 m atau 60 detik, dengan akurasi ≤ 100 m. Titik direkam **walau tanpa sinyal data**, karena GPS satelit tidak membutuhkan internet. Titik disimpan di IndexedDB dan dikirim per batch (≤ 500 titik) saat online. Setiap titik punya `client_point_id` unik, sehingga unggah ulang tidak menggandakan data. Layar dijaga tetap menyala (Screen Wake Lock), karena browser menghentikan GPS saat layar terkunci. Server menyaring titik buruk: akurasi > 50 m, lompatan > 110 km/jam, dan langkah < 15 m saat berhenti. Celah GPS > 5 menit diisi jarak lurus × faktor jalan dan ditandai sebagai estimasi. Jejak yang baru terkirim setelah rute selesai memicu perhitungan ulang jarak & emisi.

## R-04 · BAB 3 State Machine — TAMBAHKAN status stop & retur

TAMBAHKAN setelah diagram status harvest:

| Objek | Status | Arti |
|---|---|---|
| Stop rute | `pending` | Menunggu dijemput |
| Stop rute | `picked_up` | QR dipindai, barang di truk |
| Stop rute | `failed` | Supir tiba, barang tidak bisa diambil (alasan wajib: stok_tidak_ada, dibatalkan_pengepul, mutu_buruk, akses_jalan, penggilingan_tutup, truk_penuh, lainnya) |
| Stop rute | `cancelled` | Dibatalkan sebelum dijemput (pabrik batalkan rute / pengepul batal jual) |
| Kasus retur | `terbuka` → `selesai` | Sekam ditolak dikarantina sampai disposisi diputuskan |

GANTI kalimat "REJECTED (final)" menjadi: "REJECTED — barang fisik dicatat sebagai **kasus retur** (lihat BAB 6.9)".

TAMBAHKAN ke matriks 3.1:

| Aksi | Peran | Syarat |
|---|---|---|
| Laporkan stop gagal | DRIVER | Rute berjalan; stop masih `pending` |
| Batalkan rute | PABRIK | Rute `planned`/`in_progress`; muatan yang sudah naik tetap diantar |
| Batalkan pembelian | PENGEPUL (pemilik) | Lelang belum ditimbang **atau** stop belum dijemput; bila truk sudah berangkat dikenai ongkos km kosong |
| Selesaikan retur | PABRIK | Kasus `terbuka`; keputusan final dan terkunci |

## R-05 · BAB 5 Path A — GANTI langkah A.3–A.6

**A.3 (GANTI)** — Pabrik memilih panen `VERIFIED` dan daftar supir yang tersedia (volume bak masing-masing), lalu menjalankan **Optimasi Armada** (`POST /factory/dispatch/optimize`, Google OR-Tools). Sistem membagi panen ke supir dengan kapasitas volume dan meminimalkan gram CO₂e. Panen yang tidak muat di armada dilaporkan sebagai "belum tertampung", tidak dipaksakan. Pabrik meninjau pratinjau, lalu menekan **Tetapkan** (`commit=true`). Dispatch manual tetap tersedia dan kini juga menghitung km & CO₂e rencana.

**A.4 (GANTI)** — Supir menekan **Mulai Rute**. GPS mulai merekam dan status rute menjadi `IN_PROGRESS`. Di setiap penggilingan supir memindai QR tiket. Bila barang tidak bisa diambil, supir memilih alasan lalu menekan **Gagal**. Scan yang dilakukan jauh (> 500 m) dari titik penggilingan tetap diterima tetapi **ditandai untuk auditor**. Semua aksi tetap bisa dilakukan tanpa sinyal.

**A.5 (GANTI)** — **Selesaikan Rute** hanya aktif bila semua stop sudah dijemput, gagal, atau dibatalkan. Sistem menampilkan jarak (GPS), liter solar, dan kg CO₂e rute.

**A.5a (TAMBAHKAN) Pembatalan oleh pengepul** — Pengepul boleh membatalkan penjualan panen yang dijadwalkan selama **belum dimuat**. Bila truk sudah berangkat, ongkos jarak kosong (2 × km depot→penggilingan × tarif menu Parameter) dibebankan ke pengepul. Barang yang sudah di truk tidak bisa dibatalkan dan diselesaikan melalui penolakan/retur di pabrik.

**A.6 (TAMBAHKAN di akhir)** — Bila pabrik menolak muatan di gerbang, operator memilih kode alasan (basah / berjamur / kontaminan / selisih berat) dan mengisi kadar air terukur. Sistem otomatis membuka **kasus retur**.

## R-06 · BAB 6 Path B — GANTI B.5, TAMBAHKAN B.6a & B.8a

**B.5 (GANTI kalimat harga)** — "Untuk panen lelang, harga kontrak hanya **dipotong secara basis kering** bila kadar air saat ditimbang lebih tinggi dari kadar air yang diiklankan petani: `harga × (1 − M_aktual)/(1 − M_iklan)`. Tidak ada bonus bila lebih kering. Kontaminan (batu/plastik) tidak dibayar: `kg_bayar = timbangan × (1 − kontaminan)`."

**B.6a (TAMBAHKAN) Pembatalan lelang** — Pengepul boleh membatalkan pembelian lelang yang **belum ditimbang**. Tawaran berstatus `dibatalkan` dan sisa stok listing petani dikembalikan otomatis, sehingga petani bisa menerima tawaran pengepul lain.

**B.8a (TAMBAHKAN) Sortir sebagian di QC** — Bila sebagian karung basah/berjamur, petugas QC menimbang karung yang disortir (`rejected_kg`) dan memilih alasannya. Karung sortir tidak dibayar dan dikarantina sebagai kasus retur. Sisa lot dinilai dan dibayar seperti biasa. Lot ditolak seluruhnya hanya bila mutu sisa juga di bawah batas.

## R-07 · BAB 6.9 BARU — Retur & Karantina Sekam

| Disposisi | Kapan dipakai | Catatan |
|---|---|---|
| Kembalikan ke pengirim | Mutu tidak bisa dipulihkan dan pengirim mau menjemput | Ongkos angkut ke penanggung biaya |
| Keringkan ulang | Basah tanpa jamur | Jemur/pengering hingga ≤ 12–14% lalu QC ulang |
| Turun grade | Mutu C setelah pengeringan | Harga basis kering |
| Bahan bakar boiler | Jamur ringan | Panas memusnahkan spora; **jangan** untuk pakan/alas ternak |
| Musnahkan | Jamur berat / panas sendiri (self-heating) | Kompos terkontrol; catat berat & foto |

Penanggung biaya default: pihak terakhir yang menimbang dan menyatakan lolos mutu. Kasus yang sudah diputuskan **terkunci** dan tidak dapat diubah (jejak audit).

## R-08 · BAB 7 Manufaktur — TAMBAHKAN 7.6 Bill of Materials & Stok Produk Jadi

> Setiap batch mencatat per produk (biochar, bio-silika, bio-pellet): **kg aktual, kg harapan model Engine ⑪** untuk mutu lot yang sama, **rendemen % terhadap input**, dan **varians rendemen**. Aliran loss (air, volatil/syngas, gas pembakaran, residu ekstraksi, susut proses) tetap dicatat terpisah, dan penutupan neraca massa wajib ≤ 2%. Output batch otomatis masuk **buku stok produk jadi** (append-only). Biochar yang dialokasikan ke dompet petani keluar dari stok jual. Penjualan dicatat dengan nomor DO/faktur dan tidak boleh membuat stok negatif.

## R-09 · BAB 8.2 Engine ② — GANTI aturan pengali harga

HAPUS daftar "Pengali Harga 1,10x / 1,00x / 0,85x". GANTI dengan:

> **Harga beli berbasis bahan kering (default).** `harga/kg = harga_dasar × (1 − M)/(1 − M_acuan)` dengan M_acuan = 12% (menu Parameter). `kg_bayar = timbangan × (1 − kontaminan)`. Grade tetap dinilai untuk insentif (Engine ⑥) dan pemilihan lot. Harga turun merata ±Rp 4,5/kg per 1% air, tanpa "tebing harga" di batas grade. Metode lama (pengali grade) masih bisa dipilih di menu Parameter.
>
> **Ambang kadar air:** ≤ 15% aman simpan. > 15% = **risiko jamur**, wajib dijemput/dikeringkan ≤ 48 jam dan dilarang disimpan tertutup. > 20% = tolak (samakan `harga_mutu.moisture_reject` menjadi 20). Di atas batas tolak, pengepul hanya boleh membeli dengan mencentang **"beli untuk dikeringkan"** (harga basis kering, risiko ditanggung pengepul).
>
> **Simulasi harga di depan petani:** cukup berat + kadar air (moisture meter). Abu/VM/FC opsional dan ditandai "estimasi" bila tidak diukur.

## R-10 · BAB 8.4 Engine ⑤ — TAMBAHKAN

> **Optimasi armada (Google OR-Tools 9.15).** Model CVRP multi-kendaraan dengan kapasitas volume per truk. Pencarian PATH_CHEAPEST_ARC + Guided Local Search berbatas waktu. Objektif = gram CO₂e: biaya busur = jarak × konsumsi BBM bergantung muatan × faktor emisi B40. Titik yang tidak muat di armada dilaporkan, tidak dipaksakan.

## R-11 · BAB 8.6 Engine ⑦ — GANTI angka baseline & sekuestrasi

HAPUS: "E_baseline = 1,28 tCO₂e/ton sekam" dan "0,85 × 0,80 × 3,67 = 2,49". GANTI dengan:

> CO₂ dari pembakaran biomassa bersifat biogenik dan **tidak** dihitung. Baseline pembakaran terbuka hanya CH₄ dan N₂O: `t_kering × porsi_dibakar × CF(0,8) × (2,7 g CH₄ × 28 + 0,07 g N₂O × 265)/kg`, ≈ 0,075 tCO₂e per ton sekam kering yang benar-benar dibakar (IPCC 2006 Vol.4 Ch.2). Sekuestrasi biochar = `t_biochar × F_C × F_perm × 44/12`. F_C sekam ≈ 0,49 (abu 35–45%), dan wajib diganti hasil uji CHN per batch. F_perm = 0,65 (350–<450 °C) / 0,80 (450–<600 °C) / 0,89 (≥600 °C) (IPCC 2019 Refinement Ap.4). Hasil bersifat **estimasi internal, bukan kredit karbon**, sampai diverifikasi pihak ketiga (Puro.earth: H/C_org < 0,7; Verra VM0044).

## R-12 · BAB 8.12 BARU — Engine ⑫ Emisi Logistik (ISO 14083)

> `BBM = Σ km × [f_kosong + (f_penuh − f_kosong) × muatan/muatan_maks]`; `EF_B40 = 0,6 × (2,68 + 0,81) + 0,4 × 1,16 = 2,56 kgCO₂e/L` (well-to-wheel, GLEC v3.2; CO₂ biogenik FAME = 0). Perjalanan kosong (depot → stop pertama, setelah stop gagal) **dihitung** dan dibebankan ke t·km bermuatan. Keluaran per rute: km, km kosong, t·km, liter, kg CO₂e WTW & TTW, g/t·km, **kg CO₂e/ton sekam**. Konsumsi BBM kosong/penuh (default 0,15/0,20 L/km) **wajib diganti** catatan BBM armada aktual.

## R-13 · BAB 8.13 BARU — Green Scorecard

> `GET /factory/green-scorecard` (pabrik/admin/auditor) menghitung dari data nyata.
>
> - **Karbon bersih** = pembakaran terbuka dihindari + sekuestrasi biochar − emisi angkut − listrik proses (kWh × faktor grid).
> - **Sirkularitas**: valorisasi massa, porsi biochar kembali ke petani, laju retur, porsi retur dipulihkan.
> - **Green chemistry**: E-factor padat lini silika, efisiensi ekstraksi SiO₂.
> - **Rekomendasi otomatis**: karbonasi CO₂ gas buang untuk presipitasi silika, daur ulang larutan NaOH, syngas untuk pengering, uji H/C_org.

## R-14 · BAB 10.1 Katalog Tabel — TAMBAHKAN

| Tabel | Kolom kunci | Fungsi |
|---|---|---|
| route_track_points | route_id, client_point_id (unik), recorded_at, lat, lon, accuracy_m | Jejak GPS store & forward (bukti MRV, tidak bisa diubah) |
| return_cases | harvest_id/request_id/qc_id, reason_code, quantity_kg, disposition, cost_bearer, status | Retur & karantina |
| finished_goods_movements | product, movement, quantity_kg (±), batch_id, reference | Buku stok produk jadi (append-only) |
| route_stops (+kolom) | stop_status, fail_reason, failed_at | Siklus stop |
| routes (+kolom) | optimizer, actual_km, fuel_l, co2e_wtw_kg, co2e_per_ton_kg, cancel_reason | Realisasi, emisi, pembatalan |
| inbound_qc (+kolom) | rejected_kg | Sortir sebagian |
| batch_outputs (+kolom) | expected_kg, yield_pct, yield_variance_pct | BOM multi-output |

## R-15 · BAB 10.2 Katalog Endpoint — TAMBAHKAN

| Metode | Path | Akses | Fungsi |
|---|---|---|---|
| POST | /api/v1/driver/stop-failed | Driver | Laporkan stop gagal (offline-safe) |
| POST | /api/v1/driver/track | Driver | Unggah titik GPS (idempoten) |
| POST | /api/v1/factory/dispatch/optimize | Pabrik | Alokasi armada OR-Tools (pratinjau/tetapkan) |
| GET | /api/v1/factory/routes | Pabrik, Auditor | Pantau stop, km GPS, BBM, CO₂e |
| POST | /api/v1/factory/routes/{id}/cancel | Pabrik | Batalkan rute |
| GET/POST | /api/v1/factory/returns, /returns/{id}/resolve | Pabrik (tulis), Auditor (baca) | Retur & karantina |
| GET/POST | /api/v1/factory/inventory, /inventory/movements | Pabrik (tulis), Auditor (baca) | Stok produk jadi |
| GET | /api/v1/factory/green-scorecard | Pabrik, Auditor | Karbon bersih, sirkularitas, green chemistry |
| POST | /api/v1/collector/harvests/{id}/cancel-purchase | Pengepul | Batal beli (lelang / jemputan) |
| POST | /api/v1/collector/price-quote | Pengepul | Simulasi harga basis kering |
| GET | /api/v1/collector/returns | Pengepul | Retur atas sekam miliknya |

## R-16 · BAB 1.4 / Lampiran Operasi — TAMBAHKAN "Mode Lapangan vs Mode Demo"

> **Mode Demo** (`DEMO_MODE=true`, default laptop/hackathon) memuat akun demo publik, seed otomatis, dan reset data. **Mode Lapangan** (`DEBUG=false`) mewajibkan `DEMO_MODE=false`, `ALLOW_SQLITE_FALLBACK=false`, `JWT_SECRET` ≥ 32 karakter, dan HTTPS (kamera QR & GPS hanya berjalan di HTTPS). Aplikasi menolak start bila syarat ini tidak terpenuhi. Batas laju permintaan dihitung per pengguna, karena banyak petani berbagi satu wifi KUD/IP operator.


## R-17 · BAB 2.2 Protokol Penomoran Resi — GANTI format (selaraskan dengan kode)

SOP saat ini menulis `TRX-PET0001-KUD0002-2610-0042` (urut 4 digit). Kode (`app/services/trx_code.py`) menerbitkan:

> **`TRX-[PERAN+ID 4 digit pengirim]-[PERAN+ID 4 digit penerima]-[YYMM WIB]-[URUT 5 digit]`**
> Kode peran: `PTN` petani, `PGP` pengepul, `DRV` driver, `PBK` pabrik. Contoh: `TRX-PTN0006-PGP0003-2610-00018` = serah-terima ke-18 dari Petani #6 ke Pengepul #3 pada Oktober 2026. Urut direset per pasangan per bulan (atomik, `trx_sequences`).

Tambahkan langkah lapangan pada **A.2 / B.5**: *setelah timbang, layar pengepul menampilkan resi sebagai QR + teks; tunjukkan ke petani dan foto bersama tumpukan karung (atau catat di nota) — resi ini dasar klaim pembayaran & dompet biochar.*

## R-18 · BAB 6 Path B — TAMBAHKAN "Konfirmasi transaksi"

> Setiap aksi yang mengikat (kirim tawaran, terima tawaran, batalkan listing, setujui/tolak Delivery Request, simpan QC, tandai settlement lunas, selesaikan rute, laporkan stop gagal) menampilkan **dialog konfirmasi berisi ringkasan angka** (kg × Rp/kg = total) sebelum dikirim. Dialog menutup pada sentuhan pertama sehingga sentuhan ganda tidak menggandakan transaksi; server tetap idempoten (`client_event_id`).

## R-19 · BAB 2.3 Offline-First — TAMBAHKAN indikator "Mode Hemat Sinyal"

> Saat sinyal hilang, bilah atas menampilkan **"Mode Hemat Sinyal — data yang Anda simpan aman di HP ini dan terkirim otomatis saat sinyal kembali"** beserta jumlah data & titik GPS yang antre. Saat sinyal kembali, bilah menampilkan tombol **"Kirim sekarang"**; setelah antrean kosong bilah hilang. Bila sesi berakhir saat offline, bilah meminta login ulang — antrean **tidak** dihapus.

## R-20 · BAB 9 BARU — Dashboard Evaluasi & Optimasi per Peran

> Setiap portal peran menampilkan kartu **Evaluasi & Optimasi**: skor kesehatan 0–100, KPI dengan status *baik / perhatian / kritis / data kurang*, dan daftar **prioritas optimasi** berurut keparahan & dampak Rupiah. Target diambil dari menu **Parameter → Target Evaluasi & Optimasi** (dapat disesuaikan kondisi lapangan) dan parameter domain yang sudah ada. Tombol **"Susun rencana optimasi AI"** meminta asisten AI (Gemini/Mistral/Groq/Ollama sesuai kunci terpasang) menjelaskan prioritas tersebut — AI tidak menghitung ulang angka; bila AI tidak tersedia, sistem memberi ringkasan otomatis.

| Peran | KPI yang dinilai |
|---|---|
| Petani | harga rata-rata vs harga dasar, porsi Grade A, kadar air saat ditimbang, selisih taksiran vs timbangan, biochar masuk dompet |
| Pengepul | margin per kg, susut ke pabrik, porsi ditolak pabrik, piutang pabrik, kg tanpa harga, antrean verifikasi |
| Driver | stop berhasil dijemput, utilisasi bak, muatan per km, jarak rute |
| Pabrik / Auditor / Admin | margin batch, pemenuhan rencana input, susut, galat penutupan mass balance, SEC kWh/t, porsi ditolak QC, kg tanpa harga settlement, lot ditandai selisih (+ akun menunggu aktivasi untuk admin) |
