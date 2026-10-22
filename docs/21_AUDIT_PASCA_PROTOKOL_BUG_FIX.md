# 21 — Audit Pasca-Protokol: Bug yang Ditemukan & Diperbaiki

**Tanggal:** 12 Oktober 2026

**Metode:** tiga auditor independen bekerja paralel dalam mode baca-saja: (A) backend multi-biomassa, (B) matematika engine analitik, (C) race condition & injeksi frontend. Setiap temuan direproduksi dulu, lalu diperbaiki dan dikunci dengan tes regresi di `tests/test_audit_postprotocol.py` (13 tes) dan tes yang ada.

## A. Backend multi-biomassa

| # | Tingkat | Bug | Perbaikan |
|---|---|---|---|
| A1 | Tinggi | Harga kontrak lelang komoditas basah terpotong ±43 %. Iklan tanpa kadar air memakai acuan **sekam 12 %**, sehingga bagasse MC 50 % dibayar Rp170 ribu, bukan Rp300 ribu. | Acuan = MC iklan, bila kosong MC acuan komoditas. Nilai 0 % tidak lagi dibuang. |
| A2 | Tinggi | Satu lot bisa dibukukan masuk gudang berkali-kali dengan berat berapa pun (100 kg → 15.000 kg). | Lot harus sudah diverifikasi; berat ≤ timbangan verifikasi + 2 %; **indeks unik parsial** `uq_wsm_harvest_in` (migrasi 020 + SQLite). |
| A3 | Sedang | Pratinjau ke petani (Rp650 ribu) lebih tinggi dari harga verifikasi (Rp637 ribu): kotoran dalam toleransi tetap dipotong saat verifikasi. | Verifikasi non-sekam hanya memotong kotoran di atas toleransi komoditas, sama dengan pratinjau. |
| A4 | Sedang | Kunci `client_event_id` milik pengepul lain mengembalikan catatan gudang mereka (catatan, lot) di SQLite. | Replay hanya untuk pemilik; selain itu 409. |
| A5 | Sedang | Kebocoran yang sama di laporan proxy (QR & id lot petani lain). | Idem. |
| A6 | Sedang | Menonaktifkan komoditas membuat stok dan lot lama terjebak (tidak bisa keluar/diverifikasi). | `get_biomass(allow_inactive=True)` untuk stok/lot yang sudah ada; komoditas nonaktif hanya menutup transaksi **baru**. |
| A7 | Rendah | Verifikasi menolak kadar air > 60 %, sehingga serbuk/bagasse segar 62–70 % tidak bisa "dibeli untuk dikeringkan". | Batas validasi dinaikkan ke 95 %. |

## B. Engine analitik

| # | Tingkat | Bug | Perbaikan |
|---|---|---|---|
| B1 | Tinggi | Analisis SEC **error 500**: model energi ≤ 0 menghasilkan NaN yang tidak bisa dikirim sebagai JSON. Pemicunya pengering tenaga surya/tungku sekam yang bahan bakarnya tidak dicatat. | β_t dibatasi ≥ 0. Bila energi tercatat < kebutuhan pengeringan, pengering dikeluarkan dari model (β_w = 0) dengan catatan. Model nol memberi 422. NaN diubah menjadi `null`. |
| B2 | Tinggi | Log tanpa kadar air dianggap "0 air", sehingga σ 26 %, R² negatif, dan **lonjakan +25 % tidak terdeteksi**. | Kadar air kosong diisi median log acuan dan ditandai `feed_moisture_imputed`. |
| B3 | Sedang | Energi pengeringan terhitung dua kali di Prototipe 2: listrik gasifikasi bagasse kurang 14 %. | Energi bersih = E_th(ar) + 2,443·air diuapkan − energi pengering. |
| B4 | Sedang | Kode komoditas ganda di optimizer memberi error 500 (evaluate diam-diam salah). | 422 dengan pesan jelas. |
| B5 | Sedang | K₂O/Na₂O kosong dianggap 0, sehingga indeks alkali "aman" (**gagal-terbuka**). | Indeks = "tidak diketahui" (status WASPADA). Bahan tanpa K₂O tidak boleh dipakai optimizer saat batas terak aktif. |
| B6 | Rendah | Kartu kelayakan memakai 0,34 tetap walau batas parameter diubah: optimizer bilang layak, kartu bilang tidak. | Kartu memakai batas yang sama dengan optimizer (+ cek sulfur). Risiko terak tetap ditampilkan tegas. |
| B7 | Rendah | Pohon keputusan menyarankan pembakaran/gasifikasi untuk bahan Cl tinggi (sabut 0,8 %) atau alkali tinggi. | Cek Cl ≤ 0,3 % & indeks alkali ≤ 0,34 di rute pembakaran & gasifikasi, plus peringatan klorin. |

## C. Race condition (SQLite mengabaikan `FOR UPDATE`) & frontend

| # | Tingkat | Bug | Perbaikan |
|---|---|---|---|
| C1 | **Tinggi (juga PostgreSQL)** | DP dan pelunasan dikirim bersamaan: petani menerima DP **plus** pelunasan penuh (DP tidak dipotong). | Helper `lock_row` (`app/services/locks.py`): UPDATE kosong sebagai pernyataan pertama, mengunci baris harvest di PG & SQLite. |
| C2 | Tinggi (SQLite) | Dompet biochar petani bisa minus (−140 kg) lewat pengajuan/serah-terima serentak. | `lock_row(User)` di pengajuan & serah-terima. |
| C3 | Tinggi (SQLite) | Stok produk jadi bisa terjual melebihi saldo (−1.100 kg). | Cek saldo ulang setelah tulis + rollback (PG tetap advisory lock). |
| C4 | Sedang (SQLite) | Potongan logistik bisa "dibebaskan" sekaligus dipotong pada pelunasan tagihan. | CAS `WHERE status='terbuka'`. |
| C5 | Sedang (SQLite) | Batal vs serah-terima biochar: permintaan tertanda batal padahal dompet sudah terpotong. | CAS `WHERE status='diajukan'`. |
| — | — | Frontend: **tidak ada jalur injeksi**. Semua nilai server sudah di-escape (`H()`/`esc()`/`Number()`), URL bukti hanya http(s)//uploads, dan toast memakai `innerText`. | — |

Sebelumnya, di Fase 5, juga sudah diperbaiki: alokasi abu ganda, serah-terima biochar ganda, dan putusan klaim karbon tertimpa (CAS).

## Catatan operasional

- Saat uji stres, worker uvicorn `--workers 2` yang tertinggal memegang 42 koneksi PostgreSQL ("too many clients"). Setelah uji multi-worker, hentikan juga proses anak `multiprocessing spawn_main`.
- Mode SQLite produksi memakai `SQLITE_POOL_SIZE=1`, sehingga sebagian race di atas jarang terjadi dengan satu proses. Perbaikan tetap diterapkan agar aman bila pool/worker ditambah.

## Hasil uji setelah perbaikan

| Suite | Hasil |
|---|---|
| pytest SQLite penuh | 525 lulus + tes pembulatan diperbaiki (lulus) |
| pytest skema PostgreSQL (fitur baru + audit + fase 5) | lulus |
| pytest PostgreSQL + RLS (`test_postgres`, `test_farmer_feedback`, `test_audit_hardening`) | 36 lulus |
| Playwright e2e (22 spec) | 22 lulus |
