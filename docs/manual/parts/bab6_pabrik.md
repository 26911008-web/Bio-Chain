# Bab 6 — Panduan Langkah demi Langkah Modul Pabrik

Bab ini ditujukan bagi staf **Pabrik Pengolahan** (operator gerbang timbang, petugas QC, admin keuangan, kepala
produksi, dan penanggung jawab ESG). Masuk dengan peran **Pabrik Pengolahan** (pilih di menu peran kanan atas). Semua
layar dalam bab ini diambil pada tampilan desktop (layar lebar) karena pekerjaan pabrik umumnya dilakukan di komputer
kantor gerbang atau ruang kendali.

Alur kerja pabrik secara ringkas:

1. **Gerbang** — menanggapi ajuan pengiriman pengepul, menimbang truk (Gross/Tare/Net), menguji sampel, memutuskan
   QC (Diterima Penuh / Sebagian / Ditolak), dan menempatkan biomassa ke *loading ramp* (6.1).
2. **Keuangan** — invoice terbit otomatis dengan skema Cash / DP / TOP, lalu tagihan pengepul dilunasi (6.2).
3. **Produksi** — memantau stok ramp, mengoptimalkan campuran bahan bakar dan pilihan produk akhir (6.3).
4. **Pelaporan & sirkularitas** — KPI karbon, batch produksi, laporan ESG, klaim removal karbon, penyaluran abu ke
   kelompok tani, dan pengiriman biochar balik ke petani (6.4).

---

## 6.1 Gerbang Timbangan & QC 2 Tahap

QC di pabrik berjalan dalam **dua tahap**:
- **Tahap 1 (di hulu, oleh pengepul):** uji cepat kadar air di lokasi petani/gudang (lihat Bab 4). Hasilnya ikut
  terkirim dalam ajuan pengiriman sebagai "AIR xx %".
- **Tahap 2 (di gerbang pabrik):** penimbangan jembatan timbang dan uji sampel ulang oleh petugas QC pabrik.
  Keputusan tahap 2 inilah yang menentukan berat yang dibayar.

### Layar 6.1a — Ajuan Pengiriman dari Pengepul

**Tujuan Proses & Standar Terkait:** Pabrik menyetujui, menawar balik, atau menolak jadwal & harga kiriman yang
diajukan pengepul, lalu membuka form QC saat truk tiba. Setiap tindakan tercatat di jejak audit (kontrol yang
*selaras* dengan ISO 27001 — bukan sertifikasi).

![Tabel ajuan pengiriman dari pengepul dengan tombol Terima, Tawar, dan Tolak](./screenshots/30_pabrik_ajuan_pengiriman.png)

Tabel berisi kolom **#**, **Pengepul** (nama, kadar air hasil uji tahap 1, dan *rekomendasi harga* netback dari sistem,
mis. "Pak Ahmad (KUD Tani Makmur Sleman) · AIR 12,5 % · REKOMENDASI RP 1.350"), **KG** (mis. 2.950), **Tawaran**
(mis. Rp 1.350/kg, tanggal 2026-10-18), **Status** (`submitted` · *MENUNGGU PABRIK*, `accepted`, `delivered`), dan
**Aksi**. Contoh pada gambar: ajuan #56 dari Pak Ahmad, 2.950 kg, Rp 1.350/kg.

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Harga tawar (Rp/kg) & tanggal:** hanya diisi bila ingin menawar balik — ketik harga usulan pabrik di kotak
  *Rp/kg* dan pilih tanggal kirim (contoh `18/10/2026`).
- **② TERIMA:** klik bila jadwal dan harga tawaran pengepul disetujui. Status menjadi `accepted`.
- **③ Tawar:** kirim harga/tanggal dari kotak ① sebagai tawar balik. Pengepul akan melihat tawaran ini di layarnya.
- **④ Tolak:** menolak ajuan (mis. ramp penuh atau mutu tahap 1 di luar spesifikasi).

Setelah ajuan diterima (`accepted`), kolom Aksi menampilkan tombol **QC MASUK**. Klik saat truk sudah di gerbang untuk
mencatat QC tahap 2; setelah QC, status menjadi `delivered` (contoh baris #53 dan #52 pada gambar).

> **🔧 Di Balik Layar (Sistem):** Tombol ②–④ memanggil fungsi `drRespond(id, 'accept'|'counter'|'reject')` dan tombol
> QC MASUK memanggil `showQcForm(id)` di frontend; semua permintaan lewat pembungkus `api()` (token Bearer + CSRF). Kolom "Rekomendasi Rp"
> berasal dari model harga netback pabrik (nilai produk pellet/biochar/silika dikurangi biaya proses), sehingga petugas
> punya acuan sebelum menyetujui harga tawaran.

### Layar 6.1b — Timbang Masuk Jembatan & Keputusan QC 3-State

**Tujuan Proses & Standar Terkait:** Mencatat berat truk bermuatan (Gross) dan kosong (Tare) di jembatan timbang
pabrik, menguji sampel, lalu memutuskan QC dengan tiga kemungkinan. **Penimbangan jembatan hanya dilakukan di gerbang
pabrik** — driver tidak menginput slip timbangan. Ukur kadar air dengan moisture meter yang dikalibrasi terhadap metode
oven 105 °C (ISO 18134-2).

Buka form ini dengan tombol **+ TIMBANG MASUK & INPUT QC** di panel *Gerbang Masuk & QC Timbangan Jembatan*
(lihat Layar 6.3a ③).

![Form timbang masuk jembatan, uji mutu sampel, dan keputusan QC 3-state](./screenshots/31_pabrik_gerbang_timbang_qc.png)

Bagian atas form berisi **Armada Logistik Pengantar** (contoh *Armada Pabrik (FACTORY_FLEET)*; pilihan lain
*Pengantaran Mandiri Pengepul*), **Nomor Polisi Truk** (contoh `AB 8421 CS`), **Nama Sopir**, dan **Komoditas
Biomassa** (contoh *Biomassa Sekam Padi*; pilihan lain tongkol jagung, serbuk sengon, tempurung kelapa, ampas tebu).

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Berat Kotor (Gross):** ketik berat truk bermuatan dari jembatan timbang, contoh `10950` kg.
- **② Berat Kosong (Tare):** ketik berat truk setelah dibongkar, contoh `6000` kg.
- **③ Netto Terhitung:** terisi otomatis = Gross − Tare. Pada gambar tampil **4.950 kg** (10.950 − 6.000). Kolom ini
  hanya-baca.
- **④ Kadar Air (%):** hasil moisture meter sampel, contoh `13.2`. Lengkapi juga **Kadar Abu (%)** `17.5`,
  **LHV (kcal/kg)** `3450`, dan **Kotoran (%)** `0.5` di baris yang sama (*Pengujian Mutu Sampel (Lab Lapangan)*).
- **⑤ Keputusan QC Gerbang (3-State):** pada gambar dipilih **Diterima Sebagian**. Pilihan yang ada:
  - 🟢 **Diterima Penuh** — seluruh netto diterima dan dibayar.
  - 🟡 **Diterima Sebagian** — muncul kolom **Qty Disetujui Masuk (kg)** (contoh `4800`) dan **Qty Ditolak / Retur (kg)**
    (contoh `150`), serta **Alasan Penolakan (Wajib Dicatat)**. Jumlah diterima + ditolak tidak boleh melebihi netto
    (4.800 + 150 = 4.950 kg ✔).
  - 🔴 **Ditolak Total** — seluruh muatan dikembalikan; alasan penolakan wajib diisi.
- **⑥ Alokasi Loading Ramp Tujuan:** pilih ramp penampung, contoh `RAMP-01: Ramp Biomassa 01 (Granular/Sekam)`.
  Lanjutkan ke bagian pembayaran (Layar 6.2a), lalu klik **✅ PROSES MASUK & TERBITKAN INVOICE**.

> **🔧 Di Balik Layar (Sistem):** Form dibuka oleh `openGateReceptionModal()` (`app/static/field-ops.js`); netto dihitung
> ulang setiap kali Gross/Tare diketik. Data dikirim ke `POST /api/v1/factory/gate-receptions`
> (`app/routers/factory_inbound.py`), yang:
> 1. menolak bila `gross ≤ tare`; untuk **Diterima Sebagian** memeriksa `diterima + ditolak ≤ netto (+0,1 kg)` dan
>    mewajibkan alasan bila ada porsi ditolak; untuk **Ditolak Total** alasan wajib;
> 2. mengunci baris ramp lalu memeriksa kapasitas fisik (`stok + diterima ≤ kapasitas maks`, bila lewat → galat 409);
> 3. memperbarui **mutu agregat ramp secara rekursif (rata-rata berbobot massa)**:
>    `MC_baru = (stok_lama × MC_lama + kg_masuk × MC_uji) / (stok_lama + kg_masuk)` — sama untuk abu dan LHV;
> 4. menerbitkan nomor tiket `GATE-YYYYMMDD-xxxxxx`, membuat lot QC (stok untuk batch produksi), dan menyalurkan
>    tagihan ke dompet pengepul.
>
> **Refraksi.** Pada form gerbang, refraksi "Diterima Sebagian" dimasukkan sebagai pemisahan kg diterima/ditolak oleh
> petugas QC. Rumus refraksi otomatis multi-komoditas (`app/engines/refraction.py`) dipakai di gudang pengepul dan
> pratinjau berat bayar:
> `kg_bayar = kg_timbang × (1 − max(0, kontaminan − toleransi)) × (1 − MC) / (1 − MC_acuan)`,
> dengan MC acuan, batas MC tolak, dan toleransi kontaminan diambil dari master parameter tiap komoditas. Tidak ada
> bonus bila lebih kering dari acuan (kecuali diaktifkan per transaksi), dan di atas MC tolak lot ditolak kecuali dipilih
> eksplisit "terima basah".

#### Protokol Uji Lab Proksimat Bulanan & Kalibrasi Alat

> **⚠️ Belum tersedia di aplikasi.** Fitur penjadwalan uji lab proksimat bulanan dan pencatatan kalibrasi alat
> (moisture meter, timbangan jembatan) **belum ada**. Jalankan sebagai prosedur manual:
> 1. Setiap bulan, ambil sampel komposit dari tiap ramp dan kirim ke laboratorium terakreditasi KAN / ISO 17025 untuk
>    uji proksimat (kadar air, abu, zat terbang/VM, karbon tetap/FC) dan nilai kalor.
> 2. Bandingkan hasil lab dengan rata-rata uji gerbang bulan itu; bila selisih kadar air > ±1 poin, kalibrasi ulang
>    moisture meter terhadap metode oven 105 °C.
> 3. Simpan sertifikat lab dan catatan kalibrasi di arsip mutu pabrik.
>
> Yang **sudah tersedia**: kolom kadar abu, LHV, dan kotoran pada form gerbang (di atas), kolom proksimat opsional pada
> uji mutu pengepul, serta isian **nama laboratorium & nomor laporan lab** pada ledger abu (Layar 6.4e) dan klaim
> karbon (Layar 6.4d).

---

## 6.2 Pembayaran & Pengawasan SLA

### Layar 6.2a — Skema Bayar Cash / DP / TOP & Invoice Otomatis

**Tujuan Proses & Standar Terkait:** Menentukan cara pabrik membayar pengepul untuk muatan yang diterima. Invoice
langsung terbit begitu tombol proses diklik — tidak perlu dibuat terpisah.

![Bagian pemicu invoice otomatis pada form gerbang dengan skema DP Bertermin](./screenshots/32_pabrik_skema_bayar_invoice.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Qty Disetujui Masuk / Qty Ditolak (kg):** pastikan kg disetujui (`4800`) dan kg ditolak/retur (`150`) sudah
  benar, karena **invoice hanya dihitung dari kg yang diterima**. Dengan **Harga Dasar (Rp/kg)** `450`:
  4.800 kg × Rp 450 = **Rp 2.160.000**.
- **② Skema Bayar:** pada gambar dipilih **DP Bertermin**. Pilihan yang ada:
  - 💵 **Cash (Lunas Instan)** — invoice langsung berstatus *PAID*.
  - 🪙 **DP Bertermin** — muncul kolom **Nominal DP Dibayarkan di Muka (Rp)**; sisanya menjadi tagihan.
  - ⏳ **TOP (Jatuh Tempo)** — seluruh nilai dibayar pada tanggal jatuh tempo.
- **③ Nominal DP Dibayarkan di Muka (Rp):** contoh `2000000`. Sisa tagihan = Rp 2.160.000 − Rp 2.000.000 =
  **Rp 160.000**.
- **④ Termin (Hari):** jumlah hari sampai jatuh tempo, contoh `14` (bawaan 14, rentang 1–90). Setelah semua benar,
  klik **✅ PROSES MASUK & TERBITKAN INVOICE**. Muncul notifikasi sukses, lalu panel ramp dan riwayat gerbang
  (Layar 6.3a) langsung diperbarui.

> **🔧 Di Balik Layar (Sistem):** `factory_inbound.py` menghitung `total = kg_diterima × harga_dasar`, membuat
> `FactoryInvoice` bernomor `INV-YYYYMMDD-xxxxxx` dengan `due_date = sekarang + termin`:
> - **CASH** → `dibayar = total`, sisa 0, status `PAID`;
> - **DP** → `dibayar = min(DP, total)`, sisa = total − DP, status `PARTIALLY_PAID` (atau `PENDING` bila DP 0);
> - **TOP** → sisa = total, status `PENDING`.
>
> **Blokir TOP (disiplin kredit).** Sebelum menerbitkan invoice, sistem mencari invoice pabrik yang `is_overdue = True`
> dan belum lunas. Bila ada dan skema yang dipilih **TOP**, transaksi ditolak (HTTP 403): *"Pabrik memiliki tagihan TOP
> yang telah jatuh tempo belum dilunasi. Wajib melunasi tagihan overdue sebelum membuka transaksi TOP baru."* Skema Cash
> dan DP tetap bisa dipakai. Penanda jatuh tempo diperbarui otomatis setiap daftar invoice dibuka
> (`GET /factory/invoices`: belum lunas dan lewat `due_date` → overdue), dan dibuka kembali lewat pelunasan
> `POST /factory/invoices/{id}/pay`.

### Layar 6.2b — Pembayaran ke Pengepul & Pengawasan Jatuh Tempo

**Tujuan Proses & Standar Terkait:** Menimbang-terima biomassa yang tiba lewat rute armada pabrik, menetapkan harga
settlement, lalu menandai tagihan pengepul sudah dibayar dengan bukti transfer.

![Daftar tagihan pengepul dengan isian harga Rp/kg dan tombol Tetapkan harga](./screenshots/33_pabrik_pembayaran_pengepul.png)

Kartu **Pembayaran ke Pengepul (jalur QC & rute armada)** memiliki dua bagian:
- **Tiba via rute armada — menunggu timbang terima** (bagian atas gambar): Harvest (mis. #1119), Pengepul / Petani
  (Pak Ahmad (KUD Tani Makmur Sleman) · Pak Sugeng (Penggilingan Padi Godean)), timbang pengepul (800 kg), mutu (air
  11 % · abu 18 % · A), **Timbang Pabrik (kg)** yang dapat dikoreksi, **Harga (Rp/kg, opsional)** — kosong berarti
  memakai rekomendasi *netback* — dan foto bukti. Filter **Semua status / menunggu harga / terutang / dibayar** ada di
  kanan atas kartu.
- **Tagihan pengepul**: ringkasan *Terutang: Rp 86.104.710 · Belum berharga: 945 kg*, lalu tabel #, Pengepul, Jalur
  (mis. *QC lot #46 · Harga kontrak delivery request, disetarakan basis kering saat QC*), kg dibayar (3.000), Rp/kg
  (Rp 597), Jumlah (Rp 1.789.590), Status (*terutang*), dan Aksi.

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Isian Rp/kg:** ketik harga baru per kg pada baris tagihan yang ingin ditetapkan atau dikoreksi.
- **② Tetapkan harga:** klik untuk menyimpan harga. Sistem meminta **alasan** (minimal 5 karakter, contoh "Koreksi mutu
  timbangan pabrik"). Tagihan *menunggu harga* berubah menjadi *terutang*, dan jumlahnya dihitung ulang.

Untuk melunasi, gulir tabel ke kolom paling kanan (di luar gambar): pada tagihan *terutang*, isi **No. transfer**
(minimal 3 karakter) lalu klik **Tandai dibayar**. Status menjadi *dibayar* dan nomor referensi tampil di bawah status.

> **🔧 Di Balik Layar (Sistem):** Timbang terima memanggil `POST /api/v1/factory/receive` dan membuat settlement
> (`kg dibayar × Rp/kg`); bila harga kosong, status *menunggu harga* dan ringkasan "belum berharga: … kg" tampil di
> atas tabel. Penetapan harga (`/settlements/{id}/price`) wajib beralasan dan tercatat di jejak audit; pembayaran
> (`/settlements/{id}/pay`) wajib nomor bukti. Kartu *Evaluasi & Optimasi* di dasbor menandai kg yang "diterima tanpa
> harga settlement" sebagai prioritas (Layar 6.4a).
>
> **SLA hulu ke petani.** Pembayaran pengepul ke petani diawasi oleh parameter `pasar.farmer_payment_due_days`, bawaan
> **3 hari** (dapat diatur 0–60 hari di menu Parameter). Artinya petani wajib dibayar **maksimal 3 hari setelah
> serah-terima (lebih ketat dari target ≤ 14 hari)**; lot yang melewati batas ditandai **terlambat** dan dihitung pada
> ringkasan "… lot · … terlambat > 3 hari".

---

## 6.3 Loading Ramp & Optimasi

### Layar 6.3a — Status Real-Time Loading Ramp & Riwayat Gerbang

**Tujuan Proses & Standar Terkait:** Melihat isi dan mutu rata-rata setiap ramp penampung secara langsung, serta riwayat
semua tiket gerbang, sebagai dasar perencanaan produksi.

![Panel Gerbang Masuk dengan status empat loading ramp dan riwayat penerimaan gerbang](./screenshots/34_pabrik_loading_ramp_status.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Status Real-Time Loading Ramp (Mutu Rekursif):** satu kartu per ramp, contoh **RAMP-01** Ramp Biomassa 01
  (Granular/Sekam) — *Stok: 3.700 kg / 60.000 kg*, lencana **6,2 % Kapasitas**, MC 13 %, Ash 16,8 %, LHV 3.456.
  RAMP-02 (Cacah/Tongkol) 8.000/45.000 kg; RAMP-03 (Serbuk Kayu) 5.000/40.000 kg dengan MC 28 % (perlu pengeringan);
  RAMP-04 (Cangkang/Tempurung) 12.000/50.000 kg, LHV 4.600. Klik **Refresh Ramp** untuk memuat ulang.
- **② Riwayat Penerimaan Gerbang & QC Timbangan:** dikelompokkan per komoditas (mis. *Sekam Padi · 11 Tiket Gerbang ·
  Total Netto 34,7 ton*). Tiap baris: No. Tiket (mis. `GATE-20261018-0019AD`, tombol QR), Plat Truk/Supir (`AB 8421 CS`,
  Driver Slamet), Armada, Biomassa, Netto (2.450 kg), Keputusan QC (`ACCEPTED`), Alokasi Ramp (Diterima: 2.450 kg), dan
  Waktu (WIB).
- **③ + TIMBANG MASUK & INPUT QC:** membuka form gerbang (Layar 6.1b).

> **🔧 Di Balik Layar (Sistem):** Data diambil dari `GET /factory/loading-ramps` dan `GET /factory/gate-receptions`
> (`factory_inbound.py`). Persentase kapasitas = `stok ÷ kapasitas maks × 100`. Mutu ramp adalah rata-rata berbobot
> massa dari semua muatan yang masuk (lihat rumus di Layar 6.1b), sehingga kartu langsung mencerminkan campuran fisik di
> ramp.

### Layar 6.3b — Prototipe 1: Blend Bahan Bakar & Briket Biaya Terendah & Risiko Terak (HiGHS)

**Tujuan Proses & Standar Terkait:** Mencari campuran biomassa **termurah** yang tetap memenuhi spesifikasi produk
(pelet ISO 17225-6, briket SNI/pasar, atau co-firing PLN) — nilai kalor, abu, klorin, sulfur — sekaligus membatasi
**indeks alkali** agar abu tidak membentuk terak (*slagging*) di boiler. Solver yang dipakai adalah **HiGHS** (program
linear) melalui SciPy.

![Form Prototipe 1 blend bahan bakar biaya terendah dengan tabel bahan dan hasil solver](./screenshots/35_pabrik_blend_highs_biaya_terendah.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Spesifikasi produk:** pilih preset, contoh **Pelet non-kayu ISO 17225-6 kelas A** (MC produk 12 %, LHV ≥ 14,5
  MJ/kg, abu ≤ 6 %, Cl ≤ 0,10 %, S ≤ 0,20 %). Pilihan lain: kelas B (abu ≤ 10 %), pelet industri 4.000 kcal/kg, briket
  (GCV ≥ 4.400 kcal/kg, MC ≤ 8 %, abu ≤ 8 %), dan co-firing PLTU (GCV ≥ 3.009 kcal/kg, MC ≤ 25 %).
- **② Tabel bahan:** centang **Pakai** untuk bahan yang tersedia, lalu periksa **Stok (kg)**, **Harga (Rp/kg)**,
  **MC aktual (%)**, dan **Porsi maks (%)**. Pada gambar ketujuh bahan dicentang dengan stok masing-masing `20000` kg;
  harga: ampas tebu 300, sabut kelapa 600, sekam padi 450, serbuk gergaji sengon 500, serbuk kayu karet 600, tempurung
  kelapa 1200, tongkol jagung 650. Tulisan *wajib* pada kolom harga berarti harga harus diisi sebelum bahan dapat dipakai.
  Porsi maks dapat diturunkan, mis. sekam ≤ 30 % demi durabilitas pelet.
- **③ Target produk (kg):** contoh `10000`. **Target kalori (kcal/kg, opsional)** boleh dikosongkan; bila kosong, batas
  kalori dari preset yang dipakai.
- **④ OPTIMASI CAMPURAN:** klik untuk menjalankan solver.
- **⑤ Hasil:** empat kotak ringkasan dan tabel komposisi. Contoh pada gambar:
  - **Kelayakan: LAYAK** · *Terak: WASPADA*.
  - **Biaya total Rp 6.535.324** (Rp 654/kg produk).
  - **Kalori 3.786 kcal/kg GCV ar** · NCV 3.463.
  - **Indeks alkali 0,281 kg/GJ** · sedang.
  - Komposisi: **Ampas tebu** 42,6 % bk (pakai 7.489 kg basah, air diuapkan 3.234 kg, Rp 3.055.040); **Sekam padi**
    14,9 % (1.490 kg, Rp 670.562); **Tongkol jagung** 42,6 % (4.304 kg, air 49 kg, Rp 2.809.722).
  - Daftar cek (semua ✔): nilai kalor 3463 kcal/kg NCV ar vs min 3463; **abu 4,81 % bk vs maks 6,0**; klorin
    0,1 % vs maks 0,1; indeks alkali 0,281 vs maks 0,34 (sedang); sulfur 0,05 % vs maks 0,2. Di bawahnya ada saran uji
    AFT (ISO 21404) dan durabilitas pelet.
  - Pita **Risiko terak: WASPADA** (B/A 0,239 · Rs 0,012 · Fu 2,52 · Cl 0,1 %) dengan peringatan *"Terak mungkin terjadi
    (indeks alkali 0,17–0,34 kg/GJ) — pantau deposit & suhu bed"*.

  Di bawah hasil tersedia **Uji campuran manual (porsi % basis kering)**: geser slider tiap bahan (contoh ampas tebu 43 %,
  sekam padi 15 %, tongkol jagung 43 %) untuk menguji campuran sendiri dengan cek yang sama.

  **Hasil "tidak layak" juga sah.** Bila stok bahan rendah abu tidak cukup (mis. hanya sekam padi, abu ±17 %, padahal
  batas kelas A 6 %), solver menjawab *"Tidak ada campuran yang memenuhi semua batas. Tambah stok bahan rendah
  abu/alkali atau kurangi target."* Bila hanya satu batas yang menghalangi, sistem menyebut batas mana yang bila
  dilonggarkan membuat campuran layak.

> **🔧 Di Balik Layar (Sistem):** `app/engines/fuel_blend.py` (endpoint `POST /factory/fuel-blend/optimize`).
> **Formulasi LP** — variabel keputusan **xᵢ = kg bahan KERING komoditas i** (agar semua kendala linear):
>
> - **Fungsi tujuan (minimasi biaya):**
>   `min Σ xᵢ · [ harga_arᵢ / (1 − MCᵢ) + max(0, wᵢ − w_produk) · biaya_pengeringan ]`,
>   dengan `w = MC/(100 − MC)` = kg air per kg kering (biaya pengeringan opsional).
> - **Kendala massa:** `Σ xᵢ = D`, dengan `D = target × (1 − MC_produk)`.
> - **Kendala kalor (≥ minimum):** `Σ xᵢ · (LHV_d,min − LHV_dᵢ) ≤ 0`, dengan
>   `LHV_d,min = (LHV_ar,min + 2,443·MC) / (1 − MC)` dari rumus ISO 18125
>   `LHV_ar = LHV_d·(1 − MC) − 2,443·MC` [MJ/kg]. Untuk preset berbasis GCV:
>   `Σ xᵢ · (GCV_min/(1 − MC) − HHVᵢ) ≤ 0`.
> - **Kendala abu, klorin, sulfur (≤ maksimum):** `Σ xᵢ · (Aᵢ − A_max) ≤ 0`, `Σ xᵢ · (Clᵢ − Cl_max) ≤ 0`,
>   `Σ xᵢ · (Sᵢ − S_max) ≤ 0`.
> - **Kendala indeks alkali (Miles 1996, ditulis linear):**
>   `Σ xᵢ · (Aᵢ · alkᵢ / 10⁴ − AI_max · HHVᵢ / 1000) ≤ 0`, dengan `alk = K₂O + Na₂O (% abu)` dan `AI_max = 0,34
>   kg/GJ` (bawaan). Ambang: < 0,17 rendah · 0,17–0,34 terak mungkin · > 0,34 hampir pasti terak. Bahan yang K₂O
>   abunya belum diketahui **tidak boleh dipakai** selama batas ini aktif (gagal-tertutup, bukan dianggap 0).
> - **Batas variabel:** `0 ≤ xᵢ ≤ min(stokᵢ · (1 − MCᵢ), porsi_maksᵢ · D)`; porsi minimum opsional
>   `xᵢ ≥ porsi_minᵢ · D`.
>
> Diselesaikan dengan `scipy.optimize.linprog(method="highs")`. Setelah solusi ditemukan, `evaluate()` menghitung indeks
> abu lain dari komposisi oksida berbobot massa abu (B/A, Rs, Fu, Si/Al, viskositas G; ambang Zhu dkk. 2014) dan
> peringatan khusus (sekam > 30 % → risiko kristobalit; K₂O + SiO₂ tinggi → uji AFT ISO 21404). Indeks tersebut hanya
> **penyaring awal**; uji titik leleh abu (AFT, ISO 21404) tetap wajib sebelum produksi rutin.

### Layar 6.3c — Mesin Rekomendasi Blending Multi-Ramp (4 Produk Akhir)

**Tujuan Proses & Standar Terkait:** Memberi usulan cepat alokasi isi ramp untuk empat lini produk — Biopellet, Biochar,
Bio-Silika, dan Briket — lengkap dengan mutu campuran, margin, dan perkiraan serapan karbon, lalu mengunci batch
produksi.

![Kartu rekomendasi blending multi-ramp untuk empat produk akhir](./screenshots/36_pabrik_blending_multiramp_4produk.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Batch Size (kg):** ketik ukuran batch, contoh `10000`.
- **② HITUNG REKOMENDASI:** klik untuk menyusun usulan.
- **③ Kartu 4 produk:** setiap kartu menampilkan input → output dan rendemen, alokasi ramp, mutu campuran (MC, Ash,
  LHV), indeks alkali Miles dengan label (WASPADA/BAHAYA), status spesifikasi MC/derating, penalti pengeringan, HPP,
  harga jual, margin, laba estimasi, dan *Net Serapan Karbon*. Contoh pada gambar:
  - **Biopellet Industri & Ekspor** (lencana *LOW CARBON*): 10.000 kg → 9.200 kg (rendemen 92 %), alokasi RAMP-03
    3.500 kg + RAMP-02 5.600 kg + RAMP-04 900 kg, MC 18,6 % → *Penalti Pengeringan −83 kWh*, laba est. Rp 6.080.000,
    12,54 tCO₂e.
  - **Biochar Pembenah Tanah & C-Sink:** 10.000 → 2.800 kg (28 %), indeks alkali 0,229 (WASPADA), laba Rp 7.540.000.
  - **Bio-Silika Presipitasi Kemurnian Tinggi:** hanya dari ramp sekam (RAMP-01 2.960 kg) → 355 kg (12 %), indeks alkali
    0,395 (**BAHAYA**), laba Rp 4.528.800.
  - **Briket Arang Kalori Tinggi** (lencana *PALING UNTUNG*): 10.000 → 8.500 kg (85 %), RAMP-04 8.400 kg + RAMP-02
    1.600 kg, LHV 4.520, laba Rp 16.750.000.
  Klik **KUNCI BATCH PRODUKSI** pada kartu yang dipilih untuk mencatat batch dan mengurangi stok ramp.

> **🔧 Di Balik Layar (Sistem):** Kartu ini **tidak memakai HiGHS**. `app/routers/factory_production.py` memakai
> **heuristik urut-prioritas**: ramp diurutkan menurut aturan tiap produk (pellet: bahan kayu/tebu/jagung dulu, lalu abu
> terendah dan LHV tertinggi; biochar: sekam/tempurung/tebu dulu; briket: LHV tertinggi; bio-silika: wajib ramp sekam),
> lalu diambil berurutan hingga target terpenuhi dengan batas **70 % stok tiap ramp** (bio-silika 80 % ramp sekam).
> Mutu campuran adalah rata-rata berbobot; indeks alkali memakai rumus Miles yang sama dengan Prototipe 1; penalti
> pengeringan dari `engines/energy.py`. Serapan karbon memakai faktor tetap per ton produk (indikatif, bukan klaim) —
> klaim resmi melalui Layar 6.4d. Untuk campuran biaya terendah yang benar-benar optimal, gunakan Prototipe 1 (Layar
> 6.3b); untuk alokasi stok optimal ke empat produk, gunakan Prototipe 4 (Layar 6.3d).

### Layar 6.3d — Prototipe 4: Optimasi Multi-Biomassa ke Produk Akhir

**Tujuan Proses & Standar Terkait:** Membandingkan secara menyeluruh hasil satu lot biomassa bila diolah menjadi
Bio-Pellet (ISO 17225-2/-6), Briket (SNI 01-6235-2000), Biochar (pembenah tanah & C-sink, EBC/IBI), atau Bio-Silika —
neraca massa, energi (SEC/IKE), margin Rupiah, karbon tCO₂e, dan skor kesesuaian teknis — serta mengalokasikan stok
pabrik secara optimal dengan **HiGHS**.

![Form Prototipe 4 evaluasi lot biomassa ke empat produk akhir](./screenshots/37_pabrik_optimasi_produk_akhir.png)

Kartu memiliki dua tab: **EVALUASI LOT** (satu lot, dibandingkan ke 4 produk) dan **Alokasi Stok Pabrik** (banyak stok
biomassa, dialokasikan dengan LP).

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Komoditas biomassa:** pilih, contoh **Sekam padi**.
- **② Jumlah umpan (kg):** contoh `5000`.
- **③ MC aktual (%):** contoh `13.2`. **Harga beli (Rp/kg)** terisi `450` (dapat diubah).
- **④ EVALUASI 4 PRODUK AKHIR:** klik untuk menghitung.
- **⑤ Hasil:** di bagian atas tampil kotak **Rekomendasi Optimal**. Contoh: *"Sekam padi paling efisien dan
  menguntungkan diolah menjadi Bio-Silika (margin tertinggi) & Biochar pembenah tanah sawah. Jangan dijadikan biopellet
  murni tanpa dicampur karena abu 17,5 % melanggar standar ISO."* Di sampingnya ada ringkasan: *Profit tertinggi:
  Bio-Silika Amorf · Energi maksimal: Bio-Pellet · Carbon sink maksimal: Bio-Pellet · Pilihan terbaik: Bio-Silika Amorf*.
  Di bawahnya tertulis *"Hasil analisis konversi 5.000 kg sekam padi (MC 13,2 %, abu 18 % bk, LHV 14,3 MJ/kg)"*, lalu
  empat kartu produk. Setiap kartu memuat grade/skor, standar acuan, hasil produk, gross margin, SEC listrik, net
  karbon, harga, dan LHV/energi:

  | Produk (standar) | Skor | Hasil produk | Gross margin | SEC listrik | Net karbon | Catatan |
  |---|---|---|---|---|---|---|
  | **Bio-Pellet** (ISO 17225-2 / 17225-6) | D (15/100) | 4.650 kg (yield 93 %) | Rp 4.799.495 (57,3 %) | 95 kWh/t | 5,2 tCO₂e | Kadar abu 16,4 % > 10 %: berisiko kerak berat, wajib blending → *Perlu Blending* |
  | **Briket Biomassa / Arang** (SNI 01-6235-2000) | D (30/100) | 2.265,5 kg (45,3 %) | **Rp −377.705** (−11,1 %) | 75 kWh/t | 4,105 tCO₂e | Abu briket tembus 35,1 % (SNI maks 8 %) → *Di Bawah Standar SNI* |
  | **Biochar Pembenah Tanah** (EBC / IBI) | S (93/100) | 2.203,5 kg (44,1 %) | Rp 4.898.120 (63,5 %) | 45 kWh/t | 2,735 tCO₂e | ✔ EBC / IBI Standard |
  | **Bio-Silika Amorf** (SNI 15-0086-1987 / ASTM D1993) | S (98/100) | 594,5 kg (11,9 %) | **Rp 11.182.005** (67,2 %) | 320 kWh/t | 0,665 tCO₂e | ✔ SNI 15-0086-1987 |

  Margin negatif (briket) berarti jalur itu merugi untuk lot ini. Skor kesesuaian di bawah 45 juga membuat jalur tersebut
  dikunci 0 pada tab **Alokasi Stok Pabrik**.

> **🔧 Di Balik Layar (Sistem):** `app/engines/product_optimization.py`. Tab **Evaluasi Lot** memanggil
> `evaluate_feedstock()` (perhitungan per jalur, tanpa solver). Tab **Alokasi Stok Pabrik** memanggil
> `optimize_allocation()` — **LP HiGHS** dengan variabel **x[i,j] = ton biomassa i ke lini produk j** (j = pellet,
> briket, biochar, bio-silika):
> - **Tujuan** (pilih): *max_profit* → `max Σ laba_kotor_ij · x_ij`; *max_energy* → energi bersih GJ; *max_carbon* →
>   manfaat iklim bersih tCO₂e; *balanced* → `skor_kesesuaian × 100 + margin/5000` (diminimasi sebagai `−c`).
> - **Kendala pasokan:** `Σ_j x_ij ≤ tonase_i`.
> - **Kendala kapasitas lini** (opsional): `Σ_i rendemen_ij · x_ij ≤ kapasitas_j` (ton produk; bio-silika dalam kg).
> - **Larangan teknis:** bila skor kesesuaian jalur < 45, `x_ij = 0` (bahan tidak dipaksakan ke lini yang gagal spek).
>
> Karbon biochar memakai `C_sink = t_biochar × C_org × F_perm × 44/12`.

---

## 6.4 ESG, Output Produksi & Sirkularitas Abu

### Layar 6.4a — Dasbor KPI Karbon, Output & Evaluasi Pabrik

**Tujuan Proses & Standar Terkait:** Ringkasan kinerja pabrik di halaman awal: emisi karbon yang dihindari, output
biochar, potensi biosilika, serta skor kesehatan operasi dan prioritas perbaikan dari *AI Optimizer & Evaluator Pirolisis
Pabrik*.

![Dasbor pabrik dengan KPI karbon, biochar, biosilika, dan kartu evaluasi optimasi](./screenshots/29_pabrik_dashboard_esg_kpi.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Emisi Karbon Dihindari:** **45,48 tCO₂e** (IPCC Tier 2) — kredit karbon bersih dari klaim terverifikasi.
- **② Output Biochar / Terkarbonisasi:** **23,6 ton** biochar terverifikasi.
- **③ Potensi Biosilika SiO₂:** **8,1 ton**, estimasi dari kadar abu. Di sebelahnya, kotak **Produk Sirkular Pabrik** menyebut
  lini produk *Pellet, Briket, Biochar & Silika · Multi-downstream biomassa*.

Di bawah KPI, kartu **Evaluasi & Optimasi — AI Optimizer & Evaluator Pirolisis Pabrik** (neraca massa pasokan, suhu
reaktor, rendemen biochar, dan blending; periode 2026-08 s.d. 2026-10 dibanding 3 bulan sebelumnya) menampilkan:
- **Skor Kesehatan 84 · Grade B**, dengan temuan *Kritis 1 · Perhatian 1 · Baik 6*.
- **Prioritas optimasi** (urut keparahan & dampak):
  1. *Kritis* — **Pemenuhan rencana input 18,3 %** (target ≥ 80 %): buka listing/DR lebih awal di musim gadu; gunakan
     proyeksi pasokan untuk kontrak pengepul.
  2. *Perhatian* — **Diterima tanpa harga settlement 945 kg** (target 0 kg): tetapkan harga settlement agar pengepul
     segera dibayar (Layar 6.2b).

  Tombol **Tanya AI soal ini** membuka Asisten dengan konteks temuan tersebut.
- **Komposisi output produksi:** Biochar 33,2 %, Bio-pellet 0,7 %, Air, gas & susut proses 66,2 % (input batch
  130.380 kg · galat penutupan 0,41 % · biochar ke dompet petani 1.511 kg).
- **Semua indikator:** Margin batch 17,5 % (target ≥ 15 %, Baik); Pemenuhan rencana input 18,3 % (≥ 80 %, Kritis); Susut
  pengepul→pabrik 0,1 % (≤ 5 %); Galat penutupan mass balance 0,4 % (≤ 3 %); Energi spesifik (SEC) 140,4 kWh/t
  (≤ 150 kWh/t, membaik 12,4 %); Porsi sekam ditolak QC 2,4 % (≤ 5 %); Diterima tanpa harga settlement 945 kg (target
  0 kg, Perhatian); Harvest ditandai selisih timbangan 0 lot.

Pilih periode (mis. *3 Bulan Terakhir*) dan klik **Muat ulang** untuk memperbarui. Lebih ke bawah di dasbor ada grafik
**Proyeksi Pasokan Biomassa 30 Hari** (model cosinus musiman panen Sleman & Klaten, BPS), **Kalkulator Pengurangan
Emisi Karbon** (isi biomassa dalam ton dan jarak angkut dalam km, lalu klik **HITUNG PENGURANGAN CO₂ ➔**), dan kartu
**Rekomendasi Harga Beli Multi-Biomassa**.

> **🔧 Di Balik Layar (Sistem):** KPI ①–③ diambil dari ringkasan karbon pabrik (`app/routers/factory.py`,
> metodologi "IPCC 2006 Tier 2"). Emisi dihindari (`app/engines/carbon.py`):
> `E_dihindari = (M_biomassa × (1 − MC) × HHV_biomassa × η_boiler) × EF_batubara`;
> `E_angkut = M × jarak × EF_angkut`; `Neto = E_dihindari − E_angkut` — faktor HHV, η, dan EF batu bara diambil dari
> menu Parameter (`karbon.*`). Estimasi biochar = biomassa × rendemen model aktif (suhu pirolisis & abu acuan); potensi
> SiO₂ = biomassa × abu acuan × fraksi SiO₂ dalam abu (`rendemen.sio2_fraction_of_ash`). Angka ini **estimasi internal**,
> bukan kredit karbon.

### Layar 6.4b — Batch Produksi Multi-Produk: Produk Utama & Hasil Samping

**Tujuan Proses & Standar Terkait:** Mencatat setiap batch produksi — lot biomassa yang dipakai, timbangan output
(bio-pellet/briket, biochar, bio-silika), susut terukur, dan biaya — agar neraca massa tertutup dan biaya per ton produk
diketahui (GRI 301-1).

![Form batch produksi multi-produk dengan daftar lot biomassa stok QC](./screenshots/38_pabrik_batch_produksi_output.png)

**Sebelum bagian yang tampak pada gambar** (di atas kartu):
1. **Kode batch** terisi otomatis (contoh `B-20261018-926`).
2. Pada daftar **Lot biomassa (stok QC)** — lot hasil QC gerbang (Layar 6.1b), mis. *Lot #46 · sisa 3.000 kg · air
   14 % · A* — ketik kg yang masuk reaktor di kotak kanan lot, contoh `2450` pada Lot #46. Lot lain dibiarkan 0.
3. Klik **Isi dari model** (kanan atas kartu). Output dan loss terisi otomatis dari model rendemen, lalu muncul pesan
   *"Terisi dari model — ganti dengan timbangan aktual sebelum menyimpan."* Bila belum ada kg lot, muncul peringatan
   *"Isi kg dari minimal satu lot dulu."*

Contoh hasil model untuk 2.450 kg: Bio-pellet / Briket 667,1 kg; Air diuapkan 272,7; Volatil/syngas 779,3; Gas
pembakaran/kalsinasi 0,0; Bio-oil/tar 0; Residu ekstraksi 98,5.

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Biochar (kg):** ganti angka model (contoh `556.4`) dengan timbangan output biochar yang sebenarnya.
- **② Bio-silika (kg):** timbangan output bio-silika (contoh `40.7`). Kolom *Bio-pellet / Briket* ada di sebelah kiri.
- **③ Susut proses (kg):** contoh `35.0`. Periksa juga kolom **Loss terukur** lainnya: *Air diuapkan*, *Volatil /
  syngas*, *Gas pembakaran/kalsinasi*, *Bio-oil / tar (asap cair)*, dan *Residu ekstraksi*.
- **④ SIMPAN BATCH & HITUNG BIAYA ➔:** menyimpan batch, mengurangi sisa lot, dan menampilkan neraca massa serta biaya
  per ton produk.

Sebelum menyimpan, isi juga **Biaya batch** (listrik kWh, tenaga kerja jam, bahan kimia silika, kemasan, jam operasi)
dan **Jalur bio-silika** (dari biochar / abu pembakaran / biomassa langsung).

> **🔧 Di Balik Layar (Sistem):** *Isi dari model* menghitung MC dan abu rata-rata berbobot dari lot yang dipilih, lalu
> memanggil `POST /factory/pricing/recommend` untuk rendemen dan loss per kg biomassa; output = rendemen × total kg.
> kWh bawaan = `pabrik.kwh_per_ton_input` × ton input. Data batch (`manufacturing_batches`, `batch_outputs`,
> `batch_losses`, `batch_costs`) menjadi sumber KPI E2, E3, E4 laporan ESG.

### Layar 6.4c — Laporan ESG (E · S · G)

**Tujuan Proses & Standar Terkait:** Menyusun laporan Lingkungan, Sosial, Tata kelola dari data operasional nyata,
mengikuti GRI, GHG Protocol LSR, IFRS S2, dan struktur Lampiran II POJK 51/2017. **Emisi bruto, karbon tersimpan, dan
emisi dihindari dilaporkan terpisah** — emisi dihindari tidak mengurangi emisi bruto.

![Laporan ESG dengan ringkasan karbon dan tabel KPI lingkungan](./screenshots/39_pabrik_laporan_esg.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Dari … s.d. …:** pilih bulan awal (contoh *October 2025*) dan akhir (*October 2026*), lalu klik **TAMPILKAN**.
- **② Isi laporan:** baris periode & waktu dibuat (*Periode 2025-10 s.d. 2026-10 · dibuat 2026-10-18 16:46 UTC*),
  empat kotak ringkasan — **Emisi Bruto Proyek 0,22 tCO₂e** (Scope 2 + angkut), **Karbon Tersimpan Tahan Lama 11,85
  tCO₂e** (removal, estimasi), **Emisi Dihindari 5,87 tCO₂e** (tidak dikurangkan), **Penghematan Terealisasi Rp
  33.252.837** (32,3 tCO₂e) — lalu tabel KPI **Lingkungan (E)**: Kode, KPI, Nilai, Rumus & Sumber (tabel basis data),
  Standar. Contoh: E1 Biomassa diterima 273,66 t (POJK 51 Lamp. II; GRI 301-1), E2 Biomassa diolah 130,38 t, E3 Rendemen
  produk 33,83 % (GRI 301-1; Puro §6.1), E4 Listrik proses (GRI 302-1), E5 Intensitas listrik (GRI 302-3). Gulir ke bawah
  untuk bagian **Sosial (S)** dan **Tata kelola (G)**.
- **③ CSV:** unduh laporan sebagai CSV. **Cetak / PDF** untuk mencetak atau menyimpan PDF.

> **🔧 Di Balik Layar (Sistem):** `app/services/esg.py` mengumpulkan batch, rute, retur, pembayaran petani, persetujuan
> data, dan perubahan parameter pada periode, lalu memanggil `engines/green_scorecard.py`. Setiap KPI menyebut rumus,
> tabel sumber, dan rujukan standar. Angka karbon adalah **estimasi internal** sampai diverifikasi pihak ketiga
> (Puro / VM0044 / Global C-Sink). Contoh KPI tampil 0 kWh bila biaya listrik batch belum diisi (Layar 6.4b).

### Layar 6.4d — Klaim Removal Karbon & Uji Lab (H/C-org, EBC/IBI)

**Tujuan Proses & Standar Terkait:** Pabrik mengajukan klaim removal karbon dari biochar yang **terbukti diserahkan ke
lahan petani**, dengan hasil laboratorium C-organik dan rasio H/C-org (kriteria stabilitas EBC/IBI dan Puro.earth).
Auditor (orang lain, bukan pengaju) memverifikasi. **"Terverifikasi" = verifikasi internal, bukan kredit karbon.**

![Form klaim removal karbon dengan isian hasil lab dan daftar klaim](./screenshots/40_pabrik_klaim_karbon_ebc.png)

Pilih **Bulan awal** dan **Bulan akhir** periode klaim (contoh *October 2026*).

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① C-organik lab (% bk):** kadar karbon organik biochar dari laporan lab (basis kering), contoh `45`.
- **② Rasio H/C-org (molar):** contoh `0.3`. Harus **di bawah 0,7**; di atas itu klaim diblokir.
- **③ Nama laboratorium:** contoh *Laboratorium Uji Mutu …* (sebaiknya terakreditasi KAN / ISO 17025).
- **④ No. laporan lab:** nomor laporan hasil uji (LHU), contoh `LHU-2026-10-0142`. Unggah **Foto/scan laporan lab** di
  kolom sebelahnya (*Choose File*).
- **⑤ AJUKAN:** klik **Pratinjau** dulu untuk melihat hitungan removal dan pemblokir (bila ada). Tombol Ajukan baru aktif
  setelah pratinjau tanpa pemblokir; mengubah isian apa pun menonaktifkannya lagi (harus pratinjau ulang).

Tabel di bawah menampilkan klaim: **Klaim** (kode, mis. `CLM-2610-014`, pabrik, tanggal), **Periode**, **Biochar ke
lahan** (mis. 9.161 kg · 32 serah-terima), **Removal bersih** (mis. 9,632 tCO₂e), **Lab** (C-org 45 % · H/C 0,3 · nama
lab), dan **Status** (*diajukan*, *diverifikasi*, atau *ditolak* beserta catatan auditor, mis. "tolak agar kunci
dilepas").

> **🔧 Di Balik Layar (Sistem):** `app/services/carbon_claims.py` + `engines/green_scorecard.py`:
> `Removal = t biochar KERING yang diserahkan ke lahan × F_C × F̄_perm × 44/12`, dikurangi potongan ketidakpastian
> (`karbon.uncertainty_deduction_pct`). C-org lab menggantikan parameter F_C. F_perm (IPCC 2019 Ap.4) menurut suhu
> pirolisis: 350–<450 °C 0,65 · 450–<600 °C 0,80 · ≥ 600 °C 0,89; suhu tak tercatat → 0 (tidak boleh diklaim).
> Batas H/C-org = parameter `karbon.h_corg_max` (bawaan **0,7**). Anti hitung-ganda: satu serah-terima biochar hanya
> boleh terkunci di satu klaim aktif, periode klaim aktif tidak boleh tumpang-tindih, dan snapshot perhitungan dibekukan
> dengan SHA-256. Auditor tidak boleh memutus klaim yang ia ajukan sendiri; klaim ditolak melepas serah-terimanya agar
> dapat diajukan ulang.

### Layar 6.4e — Ledger Abu → Kelompok Tani (Uji Logam Berat)

**Tujuan Proses & Standar Terkait:** Mencatat abu boiler/pirolisis (silica ash, bottom ash, fly ash) dan menyalurkannya
ke kelompok tani **hanya bila lulus uji logam berat** sesuai Kepmentan No. 261/KPTS/SR.310/M/4/2019. Serah-terima wajib
foto dan titik lahan.

![Ledger abu dengan status uji logam berat dan penyaluran ke kelompok tani](./screenshots/41_pabrik_ledger_abu_kelompok_tani.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Tabel ledger abu:** kolom **Kode** (mis. `ASH-2610-054`), **Jenis** (silica ash / bottom ash / fly ash), **KG**,
  **Logam berat (mg/kg)** dengan lencana **LULUS** (mis. Pb 12 · Cd 0,8 · As 2,1) atau **GAGAL** (mis. Pb 80 → peringatan
  *PB 80 > 50 mg/kg*), **Poktan** (mis. Poktan Makmur Lestari Godean), dan **Status**:
  - *tersedia* → tombol **Lab** (input hasil uji) dan **Buang** (abu gagal dibuang dengan alasan);
  - *dialokasikan* → tombol **SERAHKAN** (serah-terima ke poktan dengan foto & titik lahan);
  - *diserahkan* → selesai.
  Tombol **+ Poktan** untuk mendaftarkan kelompok tani baru.
- **② + CATAT ABU:** isi **Jenis abu**, **Asal biomassa**, dan **Tonase (kg)**. Setelah itu klik **Lab** pada baris
  baru untuk mengisi Pb, Cd, As (wajib), Hg, Cr, Ni (opsional), **Laboratorium**, **No. laporan lab** (wajib), dan
  K₂O abu (opsional, untuk dosis).

> **🔧 Di Balik Layar (Sistem):** `app/routers/multibiomass.py` (`/factory/ash`, `/lab`, `/allocate`, `/handover`,
> `/dispose`). Abu **lulus hanya bila semua logam yang terukur ≤ batas** parameter `abu.limit_*_ppm`: As 10, Hg 1,
> Pb 50, Cd 2, Cr 180, Ni 50 mg/kg. Abu gagal tidak dapat dialokasikan ke lahan. Petani dapat melihat abu yang
> dialokasikan untuknya di menu petani (`/farmer/ash`).

### Layar 6.4f — Serah-terima Biochar ke Petani & Surat Jalan Muatan Balik

**Tujuan Proses & Standar Terkait:** Menyerahkan biochar dari "dompet biochar" petani (hasil penjualan biomassanya) dan
menerbitkan **surat jalan muatan balik** agar truk yang kembali ke pengepul tidak pulang kosong. Pengangkutan terlacak
lewat QR checkpoint sopir (Bab 5).

![Serah-terima biochar ke petani dan daftar surat jalan muatan balik biochar](./screenshots/42_pabrik_surat_jalan_biochar.png)

**Panduan Aksi Berdasarkan Nomor pada Gambar:**
- **① Serah-terima Biochar ke Petani:** daftar pengajuan petani untuk sawah — **#** (mis. 40, 2026-10-17), **Petani**
  (Pak Sugeng (Penggilingan Padi Godean)), **KG** (501), **Sawah** (0,51 ha), **Ambil di** (*pengepul* atau *pabrik*).
  Pada kolom **Aksi**, periksa kg yang benar-benar diserahkan (contoh `501`) lalu klik **SERAHKAN**. Dompet biochar
  petani baru berkurang saat karung diserahkan.
- **② + TERBITKAN SURAT JALAN BIOCHAR:** isi pengepul tujuan, driver/rute, plat armada, berat total, jumlah karung
  (opsional) dan instruksi muat. Surat jalan berstatus **DISPATCHED** dan memiliki QR.
- **③ Daftar surat jalan:** dikelompokkan per bulan (contoh *Oktober 2026 · 5 Surat Jalan · 2.600 kg (2,6 ton) · 104
  karung*). Kolom: **No. Surat Jalan** (mis. `DSP-A740A4A4`), **Pengepul** (Pak Ahmad (KUD Tani Makmur Sleman)),
  **Berat** (500 kg), **Karung** (20), **Plat Armada** (`AB 8888 XY`), **Status** (`DISPATCHED` → `DELIVERED_TO_FARMER`
  setelah sopir/pengepul memindai serah-terima), dan **Tampilkan QR**.

> **🔧 Di Balik Layar (Sistem):** Surat jalan dibuat oleh `POST /api/v1/factory/dispatch-biochar`
> (`app/routers/factory.py`): kode `DSP-xxxxxxxx`, token QR acak, volume = berat ÷ 300 kg/m³ (densitas biochar), jumlah
> karung bawaan = berat ÷ 25 kg. Status berubah menjadi `DELIVERED_TO_FARMER` melalui pemindaian QR di aplikasi driver
> (`app/routers/driver.py`). Serah-terima ke petani dicatat oleh `app/services/circular.py` (`handover`) dan menjadi
> dasar "biochar ke lahan" pada klaim removal karbon (Layar 6.4d) — satu serah-terima hanya dapat diklaim sekali.
