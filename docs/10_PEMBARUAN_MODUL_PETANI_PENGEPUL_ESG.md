# 10 — Pembaruan Modul Petani, Pengepul, Pabrik (ESG) & Register Penghematan

Tanggal: 11 Oktober 2026 · Status: selesai diuji (SQLite & PostgreSQL+RLS) · Migrasi: `015_farmer_feedback_circular.sql`

Dokumen ini mencatat permintaan pengguna, keputusan desain (rekomendasi terbaik yang diambil), file yang berubah, dan cara memakainya di lapangan.

---

## 1. Ringkasan permintaan → hasil

| # | Permintaan | Keputusan & hasil |
|---|---|---|
| Petani 1 | "Laporan stok" dan "Lelang" redundan | Digabung menjadi satu kartu **🌾 Lapor & Jual Sekam**: isi jumlah & penggilingan → pilih **cara jual**: *Jual ke pengepul* (harga standar, bisa offline) atau *Lelang* (pengepul menawar, perlu sinyal). Daftar lelang & tawaran tetap di kartu **🏷️ Stok Lelang & Tawaran Masuk**. |
| Petani 2 | Kadar air & grade opsional | Bagian **💧 Info mutu (opsional)** — boleh kosong. Hanya umpan balik; harga final tetap dari uji & timbangan pengepul. Grade D (basah) memberi peringatan "berisiko ditolak". |
| Petani 3 | Seperti apa menu pembayaran? | **💰 Pembayaran Saya**: alur 3 langkah (lapor → ditimbang & diuji = harga final → dibayar + kuitansi BYR), tiga keranjang **Sudah diterima · Menunggu dibayar (tanda terlambat > batas hari) · Belum ditimbang**, tabel lot menunggu, dan daftar kuitansi. |
| Petani 4 | Residu biochar untuk sawah + rumus ekonomi sirkular | Kartu **♻️ Biochar untuk Sawah**: saldo & bisa diambil, ajukan pengambilan (kg, luas sawah, titik ambil), **perkiraan manfaat** langsung (rumus §3), riwayat & batal. Pabrik menyerahkan karung → baru dompet berkurang. |
| Petani 5 | Laporan bulanan: kurva feedback QC + defect rate & penyebab | Seksi **🔬 Umpan Balik Mutu dari QC** di Laporan Bulanan petani: kurva skor QC pengepul & QC pabrik, batang defect rate, tabel **penyebab + saran perbaikan**. |
| Pengepul 1 | Margin dalam persen, bisa ± manual | Input **Margin %** dengan tombol − / + (langkah 0,5%), setara Rp/kg ditampilkan; default dari parameter `pasar.default_margin_pct`. |
| Pengepul 2 | Tombol telepon → langsung WhatsApp | Tombol **💬 WA** membuka `wa.me` dengan pesan otomatis (nama, lot). Akses nomor tetap tercatat (UU PDP). Petani tanpa HP ditandai **👵 Tanpa HP**. |
| Pengepul 3 | Data petani tanpa HP harus sama dengan modul petani | Pendaftaran: + kabupaten + lokasi GPS. Laporan: + penggilingan + info mutu opsional (field sama persis dengan petani). |
| Pabrik 1 | Laporan ESG | Kartu **🌍 Laporan ESG** (E/S/G, 29 KPI, rumus + sumber tabel + standar), unduh **CSV**, **Cetak/PDF**. Emisi bruto, removal, dan emisi dihindari **dilaporkan terpisah**. |
| Tambahan | Optimasi & efisiensi tiap proses + catat penghematan & dampak lingkungan | Kartu **💡 Optimasi & Penghematan Rantai Pasok**: terealisasi otomatis, register aksi (rencana → berjalan → terverifikasi, empat mata + bukti), potensi per proses + rekomendasi (§4). |

Temuan & perbaikan tambahan selama pengerjaan:
- **Pengepul tidak punya tombol "Tolak lot"** di UI (endpoint ada) → ditambahkan dengan **kategori penyebab** (basah/berjamur/kontaminan/selisih berat/stok tidak ada/lainnya). Ini sumber data defect rate.
- **Bug crash halaman pabrik**: pemilih foto (`ui-enhance.js`) membuat dirinya sendiri tanpa henti → diperbaiki.
- **Angka palsu di dashboard** (admin 6/36/5/1, SiO₂ 7.2, skor mutu 88.5, stok terverifikasi 0) → kini dari data asli (`/admin/stats`, `/collector/daily-summary`, `estimated_sio2_ton`).
- Kalkulator harga pabrik tidak lagi memunculkan toast merah saat harga belum diisi — diganti banner dengan tombol **Buka Parameter**.
- `photo_url` laporan petani kini divalidasi `EvidenceUrl` (sebelumnya string bebas).

## 2. Data & API baru

Migrasi **015** (idempoten, ada rollback, RLS):
- `harvests.farmer_moisture_est`, `farmer_grade_est` (A–D), `reject_category` (+CHECK, indeks).
- `biochar_redemptions` — petani hanya bisa mengajukan/membatalkan miliknya; serah-terima (ledger) hanya operator.
- `efficiency_actions` — operator tulis, auditor baca.

| Endpoint | Peran | Fungsi |
|---|---|---|
| `GET /farmer/payments/overview` | petani | tiga keranjang pembayaran |
| `GET /farmer/quality-feedback?months=6` | petani | kurva QC, defect rate, penyebab + saran |
| `GET /farmer/biochar/estimate?kg&land_area_ha` | petani | rumus manfaat biochar |
| `POST /farmer/biochar/redeem` · `GET /farmer/biochar/redemptions` · `POST …/{id}/cancel` | petani | pengambilan biochar |
| `GET /factory/biochar-redemptions` · `POST …/{id}/handover` | pabrik/admin | serah-terima (FOR UPDATE, sekali saja) |
| `GET /factory/esg/report?from=YYYY-MM&to=YYYY-MM` · `…/report.csv` | pabrik/admin/auditor | laporan ESG |
| `GET /factory/efficiency` · `POST /factory/efficiency/actions` · `PATCH …/{id}` | baca: +auditor; tulis: pabrik/admin | register penghematan |
| `POST /collector/reject` (+`category`) · `POST /collector/bid-advisor` (+`margin_pct`) | pengepul | tolak berkategori, margin % |

Parameter baru: `pasar.default_margin_pct` (5%), `pasar.farmer_payment_due_days` (3 hari), grup **Biochar untuk Sawah** (`biochar_sawah.*`, 16 koefisien bersumber).

## 3. Rumus ekonomi sirkular biochar di sawah

Sumber koefisien: `docs/08_RISET_BIOCHAR_SAWAH.md` (meta-analisis Liu 2022, Bu 2022, Xu 2022, Yu 2023; IPCC 2019 Refinement; HPP Bapanas 2/2025; HET Kepmentan 1117/2025).

```
r      = kg / 1000 / luas_ha ;  r_eff = min(r, 10 t/ha)
f      = R_maks · (1 − e^(−k·r_eff))                 R_maks 10%, k 0,20
ΔY     = Y0 · luas · f                               Y0 5,5 t GKP/ha/musim
M      = (1 − d^N)/(1 − d)                           d 0,5 · N 4 musim → 1,875
Untung = (ΔY·1000·harga_GKP + dosis_urea·luas·harga_urea·min(0,15; 0,03·r_eff)) · M − 100 Rp/kg · kg
Karbon = kg · 0,49 · 0,80 · 44/12 / 1000  tCO₂e     (dicatat proyek pabrik, tidak dijual ganda)
```

Contoh 0,5 ha + 500 kg (1 t/ha): hasil padi +1,8% (±50 kg gabah/musim), manfaat bersih ±**Rp570 rb** selama 4 musim, karbon tersimpan ±0,72 tCO₂e. Dosis anjuran 1–2 t/ha. Koefisien *k* paling tidak pasti → kalibrasi dengan demplot desa.

## 4. Optimasi & penghematan per proses

| Lapis | Isi | Sumber |
|---|---|---|
| Terealisasi otomatis | R1 km dihemat optimasi rute vs baseline (Rp, L solar, kgCO₂e WTW B40) · R2 biochar diserahkan ke sawah (manfaat petani + karbon) · R3 pembakaran terbuka dihindari | routes, biochar_redemptions, green scorecard |
| Tercatat | aksi manusia + bukti; dihitung bila berjalan/terverifikasi; verifikasi wajib bukti & bukan oleh pencatat | efficiency_actions |
| Potensi | P1 utilisasi bak · P2 deviasi GPS · P3 stop gagal · P4 lot ditolak · P5 susut > toleransi · P6 listrik per ton · P7 valorisasi massa · P8 bayar petani terlambat — masing-masing dengan rekomendasi | parameter target `evaluasi.*`, `pabrik.*` |

Penghematan otomatis tidak disimpan di register → tidak terhitung ganda.

## 5. Struktur Laporan ESG

Mengacu `docs/09_RISET_STANDAR_ESG_BIOCHAR.md`: POJK 51/2017 Lampiran II (struktur; pabrik kecil tidak wajib), PSPK 1 & 2 (IFRS S1/S2, berlaku 1 Jan 2027), GRI 2021 (+102/103 efektif 2027), GHG Protocol Scope 3 & Land Sector and Removals, Perpres 110/2025, Puro 2025 v2, IPCC 2019.
- **E1–E16**: sekam diterima/diolah, valorisasi, listrik & intensitas, Scope 2, Scope 3 kat.4, intensitas per t, karbon bruto, removal tahan lama, removal bersih, emisi dihindari (terpisah), kredit internal, residu, retur, biochar ke petani.
- **S1–S7**: petani aktif, pembayaran, tepat waktu, median hari bayar, defect rate + penyebab, susut timbang, biochar ke sawah.
- **G1–G6**: persetujuan PDP, permintaan hak data, insiden data (belum ada log), keterlacakan custody, perubahan parameter teraudit, status verifikasi karbon.
Keterbatasan dicetak di laporan: Scope 1 BBM pabrik & CO₂ biogenik belum dicatat, C-organik dari parameter (bukan lab), karbon belum diverifikasi pihak ketiga.

## 6. Pengujian

- `tests/test_farmer_feedback.py` — 9 tes (taksiran opsional, pembayaran, defect rate, rumus biochar, pengambilan & serah-terima sekali, margin %, proxy setara, ESG + RBAC, register empat mata). Lulus di SQLite dan **PostgreSQL dengan RLS**.
- Playwright: screenshot petani/pengepul/pabrik/auditor tanpa error JS; 11 screenshot persona termasuk pabrik HP.

## 7. Cara pakai singkat

- **Petani**: Lapor & Jual → isi kg → (opsional) info mutu → pilih cara jual → kirim. Cek **Pembayaran Saya**; ajukan biochar di **Biochar untuk Sawah**; buka **Laporan Bulanan** untuk melihat mutu & penyebab tolak.
- **Pengepul**: atur **Margin %** dengan −/+ lalu "Hitung saran"; tekan **💬 WA** untuk chat petani; pilih lot → uji → **Verifikasi** atau **⛔ Tolak lot** (pilih penyebab).
- **Pabrik**: serahkan biochar di **Serah-terima Biochar**; buka **Optimasi & Penghematan** → "Jadikan aksi" dari peluang → Mulai → Verifikasi (oleh orang lain, dengan bukti); **Laporan ESG** → pilih periode → CSV / Cetak.

## 8. Sisa pekerjaan yang direkomendasikan

1. Log insiden data (G3) & kecelakaan kerja.
2. Catat BBM pabrik (Scope 1) & kg bahan kimia silika per batch.
3. Input hasil lab C-organik per batch (wajib sebelum klaim karbon publik).
4. Demplot biochar di 2–3 desa untuk mengkalibrasi koefisien *k* rumus sawah.
5. Cek manual data BPS 2024 per kabupaten (Sleman, Klaten) & harga urea non-subsidi 2026.

## 9. Penguatan hasil audit 5 fase (migrasi 016)

Prompt "Forensic Omni-Audit" (Next.js/Supabase) diterapkan pada stack nyata (FastAPI + PostgreSQL RLS + PWA). Analisis selisih: 10 butir sudah ada, 9 sebagian, 3 belum → dikerjakan:

| # | Temuan | Perbaikan |
|---|---|---|
| 1 kritis | Token lama tetap berlaku setelah ganti/reset password; `must_change_password` hanya di UI | `users.token_version` (klaim `tv`): ganti/reset password mencabut semua sesi lama; server menolak semua endpoint kecuali ganti password selama wajib ganti |
| 2 kritis | Dispatch manual tanpa cek kapasitas | Tolak 422 bila **volume (m³ = kg ÷ densitas)** atau **berat** melebihi truk |
| 3 tinggi | OR-Tools hanya dimensi volume | Dimensi kedua **Weight** (muatan maks per truk) |
| 4 tinggi | Tanpa CSP; header hilang di `/sw.js`; CORS kredensial | CSP + header via include (juga di `/sw.js`); CORS tanpa kredensial, metode/header eksplisit |
| 5 tinggi | Tidak ada uang muka (DP) | `farmer_down_payments` (kuitansi DP-…, maks % parameter), dipotong otomatis saat pelunasan; **hangus untuk petani** bila pengepul batal sepihak; **wajib dikembalikan** bila stok tidak ada |
| 6 tinggi | Ongkos jarak kosong hanya teks | `logistics_charges`: dibuat saat batal ketika truk di jalan / stok tidak ada saat truk tiba; **dipotong otomatis** dari tagihan pengepul saat lunas; pabrik bisa membebaskan (alasan wajib) |
| 7 tinggi | Tidak ada uji balapan 20 tawaran | `test_twenty_concurrent_accepts_never_double_allocate` (20 koneksi PostgreSQL serentak) — lulus |
| 8 sedang | Kompres foto tidak menjamin 300 KB; tanpa "+1 truk" | Kompres bertahap mutu→resolusi **dijamin ≤ 300 KB** + orientasi EXIF; tombol **+1 truk** (m³ × densitas); uji e2e 12 MP: 9,4 MB → 270 KB |
| 9 sedang | Celah XSS kecil & validasi longgar | escape di 8 titik; validasi admin (role, email, password ≥ 6, koordinat), `str_strip_whitespace`, batas panjang field |
| 10 sedang | Refraksi hanya harga; BOM tanpa bio-oil; foto bisa dipakai ulang | `inbound_qc.refraction_kg` & `dry_basis_kg` di nota QC; aliran **bio-oil/tar** di neraca massa; nama file foto = sha256 → **foto ganda terdeteksi** |
| Runbook | Belum ada | `docs/11_RUNBOOK_OPERASIONAL.md/.docx` |

Uji baru: `tests/test_audit_hardening.py` (7), tambahan di `test_field_ops.py` (potongan & pemotongan tagihan), `test_factory_ops.py` (refraksi), `test_postgres.py` (balapan 20), `tests/e2e_photo_compression.spec.ts`.

## 10. Penyempurnaan lanjutan (sisa audit ditutup)

| Butir | Sebelum | Sesudah |
|---|---|---|
| Foto bukti tanpa sinyal | Gagal unggah, transaksi tanpa foto | Foto terkompres disimpan di **IndexedDB HP** (token `pending-photo:`); saat laporan dikirim / antrean offline diputar ulang, foto **diunggah dulu** lalu token diganti URL asli. Tidak hilang walau HP ditutup; indikator sinyal menampilkan "📷N foto". Uji e2e: offline → foto + hasil uji antre → online → 1× unggah foto, hasil uji membawa `/uploads/<sha256>.jpg`, antrean kosong |
| DP setelah lelang | Hanya dari daftar "Bayar petani" (lot sudah ditimbang) | Tombol **🤝 DP** langsung di antrean pada lot hasil lelang (harga kesepakatan × kg, maks % parameter); badge DP tampil setelah dibayar; batal sepihak → DP hak petani |
| CSP | `script-src 'unsafe-inline'` (75 handler `onclick`, 3.600 baris skrip inline) | Seluruh skrip dipindah ke **`/static/app.js`**; 75 handler → `data-onclick/onchange/oninput/onsubmit` dengan dispatcher **tanpa eval** (hanya argumen literal); CSP dari aplikasi (`app/security/headers.py`) **tanpa `'unsafe-inline'`**, hash importmap otomatis. Uji e2e: 6 dashboard peran tanpa satu pun pelanggaran CSP |

`index.html` turun dari 4.318 menjadi ±710 baris (markup saja). Service worker v10 (cache `app.js`).

