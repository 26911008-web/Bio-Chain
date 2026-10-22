# Audit SOP Lapangan, Logistik Hijau & Revisi PETA_FLOW — Bio-Chain v2

Tanggal: 9 Oktober 2026 · Sumber SOP: `docs/PETA_FLOW_DAN_STEP_BY_STEP_BIOCHAIN.docx` (366 baris/tabel, terbaca utuh)
Basis kode: FastAPI + SQLAlchemy async + PostgreSQL 16 (RLS, PL/pgSQL) dengan cadangan SQLite, UI satu halaman `app/static/index.html`.

## 0. Ringkasan eksekutif

Protokol meminta Next.js + Supabase. Repo ini memakai **FastAPI + PostgreSQL self-hosted + SPA HTML**, jadi semua fase diterapkan pada stack yang sebenarnya, tanpa menulis ulang aplikasi. Padanannya:

- "RPC Supabase" menjadi fungsi PL/pgSQL `accept_bid_atomic`.
- "Next.js Service Worker" menjadi `app/static/sw.js` + IndexedDB di `index.html`.

| Fase | Hasil | Bukti |
|---|---|---|
| 1. Audit SOP | 14 celah SOP lapangan + 6 ketidaksesuaian SOP↔kode + audit metrik hijau | §1 |
| 2. Database | Migrasi `013_field_ops_green_logistics.sql` (+ rollback). Isinya: stop gagal/batal, jejak GPS, retur/karantina, BOM multi-output + stok produk jadi, fungsi PL/pgSQL `accept_bid_atomic` (SELECT … FOR UPDATE) | §2; idempoten diuji 2× di PostgreSQL |
| 3. Offline/UX | Antrean IndexedDB, service worker app-shell, GPS store-and-forward + Wake Lock, kontrol rute supir (mulai/gagal/selesai), perbaikan antrean yang dulu **membuang data** saat 5xx/401 | §3; uji Playwright di browser nyata |
| 4. API | CVRP armada **Google OR-Tools** (objektif gram CO₂e, kapasitas volume), engine emisi ISO 14083/GLEC v3.2 (B40), harga beli terikat kadar air (basis kering) | §4 |
| 5. E2E & SOP | `tests/test_field_ops.py` (26 skenario), `tests/test_required_functions.py`, `tests/e2e_offline_driver.spec.ts`, teks revisi SOP | §5, §6 |
| + Kesiapan lapangan | 19 temuan (F1–F19): semua ditutup/ditutup-dasar di kode (F11, F14, F18 ditutup 11 Okt 2026; OTP F6 opsional) | §7 |
| + 3 fungsi wajib | Feedstock/blending, limbah→energi, IKE/anomali: lulus uji penerimaan | §8 |
| + Green Scorecard | Endpoint baru: neraca karbon bersih, sirkularitas, E-factor silika | §9 |

## 1. FASE 1 — Celah SOP Lapangan & Matriks Hijau

### 1.1 Retur barang (sekam berjamur/basah)

| # | Celah di SOP | Dampak di lapangan | Perbaikan (sudah di kode) |
|---|---|---|---|
| R1 | SOP hanya mengenal status `REJECTED` yang final (§3.1). Tidak ada alur retur, karantina, atau disposisi. | Muatan ditolak secara fisik tetap teronggok di pabrik dan tidak jelas siapa yang menanggung biaya. | Tabel `return_cases` dibuka otomatis saat `/factory/reject` dan QC tolak. Disposisi: kembalikan, keringkan ulang, turun grade, bahan bakar boiler, atau musnahkan. Penanggung biaya dan biaya penanganan dicatat. Kasus yang sudah selesai terkunci oleh trigger. |
| R2 | QC lot bersifat semua-atau-tidak (B.8). | Satu karung berjamur membuat 15 ton ditolak, atau sebaliknya lolos tanpa dipisah. | QC menerima `rejected_kg` + `rejected_reason`. Karung disortir tidak dibayar, dikarantina sebagai kasus retur, dan sisanya dinilai normal. |
| R3 | Tidak ada kode alasan penolakan; hanya teks bebas. | Analisis penyebab (hujan, gudang bocor, pengepul nakal) tidak bisa dilakukan. | `reason_code`: basah, berjamur, kontaminan, selisih_berat, stok_tidak_ada, dibatalkan_pengepul, lainnya. |
| R4 | Tidak ada ambang **risiko jamur**. Batas tolak SOP 20% dan kode 25% sama-sama jauh di atas ambang jamur. | Sekam 16–20% lolos lalu berjamur di gudang dalam beberapa hari. | Parameter `harga_mutu.moisture_mold_risk_pct` = 15% (proksi FAO: jamur simpan naik pada 14,5–18,3%). Harga menampilkan peringatan "angkut ≤ 48 jam / keringkan". |
| R5 | Petani sudah dibayar pengepul saat verifikasi, tetapi pabrik menolak di gerbang. Siapa yang rugi? | Muncul sengketa di tiga pihak. | Kasus retur mencatat `cost_bearer`. Default rekomendasi: **pihak terakhir yang menimbang dan meloloskan mutu** (pengepul untuk jalur rute). |
| R6 | Mutu di bawah batas tolak tetap "terverifikasi" dengan harga Rp 0. | Data harga kacau dan petani bingung. | Verifikasi menolak (422) kecuali pengepul mencentang **"beli untuk dikeringkan"**. Pilihan ini sesuai praktik lapangan, yaitu sekam basah dibeli murah lalu dijemur. Harga dihitung berbasis kering dan risiko dicatat. |

### 1.2 Pengepul membatalkan pembelian saat driver sudah di jalan

| # | Celah | Dampak | Perbaikan |
|---|---|---|---|
| C1 | Tidak ada pembatalan rute atau stop (`RouteStatus.CANCELLED` ada tetapi tidak pernah dipakai). | Rute macet selamanya. | `POST /factory/routes/{id}/cancel`: stop yang belum dijemput dibatalkan, sedangkan muatan yang sudah naik tetap diantar. |
| C2 | `/driver/complete-route` menolak bila ada stop belum dipindai. | Satu penggilingan yang kosong mengunci truk. | `POST /driver/stop-failed` (7 kode alasan). Rute bisa selesai bila semua stop sudah dijemput, gagal, atau batal. |
| C3 | Indeks unik `uq_route_stops_harvest` berlaku untuk **semua** stop. | Panen dari stop gagal tidak bisa dijadwalkan ulang selamanya. | Diganti `uq_route_stops_harvest_live`, yang hanya berlaku untuk stop `pending`/`picked_up`. |
| C4 | Pengepul tidak bisa membatalkan tawaran yang sudah diterima petani. | Stok petani terkunci padahal pembeli kabur. | `POST /collector/harvests/{id}/cancel-purchase`: tawaran berstatus `cancelled` dan stok listing petani dikembalikan, sehingga pengepul lain bisa menawar. |
| C5 | Tidak ada kompensasi km kosong (deadhead) bila batal saat truk sudah jalan. | Pabrik menanggung BBM sia-sia, dan pembatalan sembarangan jadi tanpa biaya. | Ongkos batal = 2 × km jalan depot→penggilingan × `logistik.cancel_fee_per_km`, **hanya bila truk sudah berangkat**. Batal sebelum berangkat gratis. Barang yang sudah di truk tidak bisa dibatalkan (409) dan harus lewat retur. |
| C6 | UI supir tidak pernah memanggil `start-route`. | **Scan QR di UI selalu ditolak 409.** Bug ini memblokir seluruh jalur A. | Tombol "Mulai Rute (aktifkan GPS)", dan `start-route` dibuat idempoten. |

### 1.3 Ketidaksesuaian SOP ↔ kode (harus dipilih salah satu)

| # | SOP menyatakan | Kode / parameter aktual | Rekomendasi |
|---|---|---|---|
| D1 | Pengali grade 1,10 / 1,00 / 0,85 (§8.2) | `harga_mutu.mult_A/B/C` = 1,15 / 1,05 / 1,00 | Pakai harga **basis kering** (default baru). Pengali grade hanya dipakai bila parameter `harga_mutu.pricing_method = pengali_grade`. SOP diperbarui. |
| D2 | Tolak bila kadar air > 20% | `harga_mutu.moisture_reject` = 25% | Turunkan ke **20%** via menu Parameter bila gudang pabrik tertutup. Ambang jamur 15% sekarang terpisah. |
| D3 | Penutupan neraca massa < 2% (§7.4) | `pabrik.closure_tolerance_pct` = 3% | Samakan. Rekomendasi 2% untuk audit karbon. |
| D4 | "Engine ⑤ CVRP dipakai saat dispatch" (A.3) | `/factory/dispatch` **tidak** memanggil solver | Sudah ditambah `/factory/dispatch/optimize` (OR-Tools). Dispatch manual kini menghitung km & CO₂e rencana. |
| D5 | Engine ⑦: baseline 1,28 tCO₂e/t, C_org 0,85, F_perm 0,80 (§8.6) | Engine ⑦ hanya menghitung substitusi batu bara; sekuestrasi tidak dihitung. | Angka SOP tidak bisa dipertahankan. CO₂ pembakaran biomassa biogenik, jadi baseline hanya CH₄+N₂O (≈ 0,06–0,09 tCO₂e/t). Biochar sekam berabu 35–45%, sehingga F_C ≈ 0,49 (default IPCC 2019), bukan 0,85. Lihat Green Scorecard §9. |
| D6 | "Resi kriptografis", "log GPS setiap kilogram", perangkat Scout Pro NIR/ESC-POS | Resi berurutan tanpa tanda tangan; GPS hanya titik saat pickup; tidak ada endpoint perangkat | Ubah kata-kata SOP atau implementasikan (F14, F9 di §7). |

### 1.4 Audit Green Metrics — jejak karbon angkut (kg CO₂e/ton sekam)

| Aspek | Sebelum | Sesudah |
|---|---|---|
| Ada di SOP? | Tidak ada kalkulasi kg CO₂e per ton sekam terangkut. Engine ⑦ memakai `ton × km × 0,062` dengan km diketik manual. | Engine ⑫ `app/engines/emission.py` (ISO 14083:2023 / GLEC v3.2) |
| Jarak | Diketik manual; tidak terkait rute | GPS nyata (store & forward) atau estimasi rute rencana; `distance_source` tercatat |
| Perjalanan kosong | Diabaikan | Dihitung dan dibebankan ke t·km bermuatan (wajib ISO 14083) |
| Faktor emisi | 0,062 kgCO₂/t·km tanpa sumber | Berbasis BBM. EF campuran B40 = 0,6·(2,68 + 0,81) + 0,4·1,16 = **2,56 kgCO₂e/L WTW** (TTW fosil 1,61) |
| Konsumsi BBM | — | Linear terhadap faktor muat (HBEFA/GLEC); **default 0,15/0,20 L/km = ASUMSI, wajib diganti data armada** |
| Keluaran | — | total km, km kosong, t·km, liter, kg CO₂e WTW/TTW, g/t·km, **kg CO₂e/ton sekam** per rute |

Contoh terhitung (parameter default): depot → 2 penggilingan (1 t + 1 t) → depot. Jarak GPS ±40 km menghasilkan **8,2 kg CO₂e/t sekam**. Bila memakai estimasi jalan (×1,3 = 52 km), hasilnya 10,7 kg CO₂e/t, setara ≈ 370 g CO₂e/t·km. Angka ini sebanding dengan default GLEC v3.2 untuk truk rigid 3,5–7,5 t (335 g/t·km), yang menjadi pemeriksaan kewajaran.

## 2. FASE 2 — Skema Pabrik Sirkular & Lelang Atomik (migrasi 013)

### 2.1 Bill of Materials multi-output (1 sekam → biochar + bio-silika + bio-pellet)

```
manufacturing_batches (1) ──< batch_inputs   (lot QC sekam, kg, kadar air)
                       (1) ──< batch_outputs  (product, quantity_kg, expected_kg, yield_pct, yield_variance_pct)  ← BARU: kolom BOM
                       (1) ──< batch_losses   (air | volatil_syngas | gas_pembakaran | residu_ekstraksi | susut_proses)
                       (1) ──< batch_costs    (variabel/tetap, biaya bersama vs terpisah, driver kWh)
                       (1) ──< finished_goods_movements  ← BARU: buku stok produk jadi (append-only)
                                 produksi(+) · alokasi_petani(−) · penjualan(−) · penyesuaian(±) · retur_pelanggan(+)
view finished_goods_stock = Σ mutasi per produk (saldo tidak pernah disimpan sebagai angka yang bisa diedit)
```

- **Yield loss** tercatat dua kali. Pertama sebagai rincian `batch_losses` per jenis. Kedua sebagai `yield_variance_pct` per produk terhadap model Engine ⑪ untuk mutu lot yang sama.
- Neraca massa: `closure_error_pct` = (input − Σ output − Σ loss) ÷ input.
- Penjualan yang membuat stok negatif ditolak (409). Penjualan serentak diserialkan dengan `pg_advisory_xact_lock` per produk.

### 2.2 Lelang atomik — `accept_bid_atomic` (PL/pgSQL, setara "RPC Supabase")

```sql
SELECT * INTO l FROM stock_listings WHERE id = p_listing AND farmer_id = p_farmer FOR UPDATE;   -- kunci 1
SELECT * INTO b FROM bids WHERE id = p_bid AND listing_id = p_listing FOR UPDATE;               -- kunci 2
-- validasi di bawah kunci: status tawaran, qty ≤ tawaran, stok cukup, listing terbuka & belum kedaluwarsa
UPDATE stock_listings SET remaining_kg = remaining_kg - p_qty, status = ... ;
UPDATE bids SET status = 'accepted' ... ;  -- bila stok habis: tawaran aktif lain → 'rejected'
```

- Urutan kunci tetap (listing → tawaran), sehingga bebas deadlock.
- Fungsi bersifat `SECURITY INVOKER`, sehingga RLS petani tetap berlaku.
- Aplikasi memanggil `public.accept_bid_atomic` di PostgreSQL dan memakai compare-and-swap berurutan di SQLite.
- Tes konkurensi `test_concurrent_accepts_never_oversell` lulus di PostgreSQL.

### 2.3 Tabel & kolom baru lainnya

| Objek | Fungsi | Pengaman |
|---|---|---|
| `route_stops.stop_status / fail_reason / fail_note / failed_at` | Siklus stop | CHECK status; CHECK `picked_up ⇔ qr_scanned` |
| `routes.optimizer, actual_km, fuel_l, co2e_wtw_kg, co2e_per_ton_kg, emission_detail, cancel_*` | Realisasi & pembatalan | — |
| `route_track_points` | Jejak GPS | `client_point_id` UNIQUE (idempoten); RLS per supir; trigger larang UPDATE |
| `return_cases` | Retur/karantina | RLS operator/auditor; trigger kunci kasus selesai; larang DELETE |
| `inbound_qc.rejected_kg` | Sortir sebagian | CHECK ≥ 0 |
| `bids.status = 'cancelled'` | Batal beli | CHECK diperbarui |

Cara menerapkan: `psql -f migrations/013_field_ops_green_logistics.sql` (sudah terdaftar di `migrations/README.md` dan `scripts/pg_setup.py`). Untuk SQLite/dev, `app/migrations.py` menambah kolom dan indeks otomatis. Migrasi 010 juga diperbaiki agar `pg_setup.py` bisa dijalankan ulang.

## 3. FASE 3 — Arsitektur Offline-First & Pelacakan Emisi

```
┌──────────────── HP supir / pengepul / petani (Android murah) ────────────────┐
│ index.html                                                                   │
│  apiMutation() ──online──► API (client_event_id + client_recorded_at)        │
│        │ gagal jaringan / 408 / 429 / 5xx                                    │
│        ▼                                                                     │
│  IndexedDB "biochain-offline"                                                │
│   ├─ kv:outbox    antrean aksi (pickup, verifikasi, stop gagal, mulai/selesai│
│   ├─ kv:deadbox   aksi ditolak aturan bisnis (409/422) → bisa ditinjau        │
│   └─ track        titik GPS (watchPosition, filter ≥25 m / ≤100 m akurasi)   │
│  Pemicu kirim: event online · visibilitychange · interval 30 s · ketuk pill   │
│               · Background Sync (Chrome/Edge) via sw.js                       │
│  Urutan: antrean aksi DULU → baru jejak GPS (rute harus "mulai" di server)   │
│  401 saat flush → antrean DISIMPAN, minta login ulang (dulu: terhapus semua) │
│  Screen Wake Lock selama rute: GPS berhenti bila layar terkunci              │
│ sw.js: app-shell network-first, pustaka CDN stale-while-revalidate,           │
│        /api TIDAK di-cache                                                    │
└──────────────────────────────────────────────────────────────────────────────┘
            ▼ batch ≤ 500 titik                       ▼ aksi idempoten
  POST /driver/track (ON CONFLICT DO NOTHING)    POST /driver/confirm-pickup | stop-failed | complete-route
            ▼
  complete-route / jejak terlambat → finalize_route_emissions():
  bersihkan jejak (akurasi, glitch > 110 km/jam, jitter < 15 m, celah > 5 menit × faktor jalan)
  → km nyata → BBM(muatan) → CO₂e WTW → routes.co2e_per_ton_kg
```

Keterbatasan yang jujur dan solusinya:

1. **Safari/iOS & Firefox tidak mendukung Background Sync.** Pemicu lain (online, buka aplikasi, interval) tetap bekerja. Data aman di IndexedDB.
2. **Browser menghentikan GPS saat layar terkunci atau aplikasi di latar belakang**, termasuk di service worker. Wake Lock membantu selama layar menyala. Untuk pelacakan penuh di latar belakang, solusinya membungkus aplikasi sebagai **Capacitor/TWA Android** dengan plugin background-geolocation, memakai API `/driver/track` yang sama tanpa perubahan server.
3. Tile peta OSM tidak di-cache (kebijakan OSM). Daftar stop tetap berfungsi offline. Untuk peta offline, pakai PMTiles self-host.

## 4. FASE 4 — Algoritma Rute Hijau & Kalkulator Harga Beli

### 4.1 CVRP armada dengan Google OR-Tools (`app/engines/routing_ortools.py`)

- Pustaka: `ortools>=9.15` (wheel resmi untuk cp312–cp314). Tidak ada algoritma routing yang ditulis dari nol.
- Model: `RoutingIndexManager` + `RoutingModel`, dimensi `Volume` dengan `AddDimensionWithVehicleCapacity` (m³ per truk, karena sekam terbatas volume), dan `AddDisjunction` agar titik yang tidak muat **dilaporkan, bukan dipaksakan**.
- Pencarian: `PATH_CHEAPEST_ARC` lalu `GUIDED_LOCAL_SEARCH`, berbatas waktu.
- Objektif dalam **gram CO₂e**: `biaya(i→j) = d_ij × [f₀ + (f₁−f₀)·kg_i/muatan_maks] × EF_B40`. Ini batas bawah load-aware karena OR-Tools tidak mendukung biaya bergantung muatan secara langsung (Pollution-Routing Problem, Bektaş & Laporte 2011). Emisi persis dihitung ulang setelah solusi didapat.
- Endpoint:
  - `POST /factory/dispatch/optimize` dengan `commit=false` untuk pratinjau dan `true` untuk membuat rute per supir.
  - `POST /labs/routes/optimize` dengan `mode=ortools`.
- Trade-off yang diukur: pada 36 penggilingan demo, OR-Tools (objektif CO₂e) menghasilkan 633 km, sedangkan heuristik internal (objektif km) 611 km. Mode objektif dipilih sesuai kebijakan pabrik.

### 4.2 Harga beli terikat kadar air (`farmgate_price`, `/collector/price-quote`)

```
harga/kg = harga_dasar × (1 − M) / (1 − M_acuan)        M_acuan = harga_mutu.reference_moisture_pct (12%)
kg_bayar = timbangan × (1 − kontaminan)
total    = kg_bayar × harga/kg ;  TOLAK → tidak dibeli (atau "beli untuk dikeringkan" berbasis kering)
lelang   : harga kontrak hanya DIPOTONG bila lebih basah dari kadar air iklan petani (tanpa bonus kering)
```

- Rumus ini **sama** dengan rumus QC pabrik (jalur B), sehingga petani, pengepul, dan pabrik memakai satu logika.
- Harga turun kontinu sekitar Rp 4,5/kg per 1% air, tanpa "tebing harga" di batas grade (diuji).
- `/collector/price-quote` cukup memakai **berat + kadar air**. Abu/VM/FC bersifat opsional dan ditandai "estimasi", karena di lapangan pengepul umumnya hanya punya moisture meter.

## 5. FASE 5 — Simulasi E2E Kegagalan Jaringan

| Tes | Yang dibuktikan |
|---|---|
| `test_pickup_retry_after_lost_response_is_not_duplicated` | Server sudah commit tetapi respons hilang. Pengiriman ulang 3× dengan `client_event_id` sama menghasilkan **1** event custody. |
| `test_concurrent_replays_from_two_tabs_create_one_pickup` | 4 kiriman serentak menghasilkan 1 pickup. |
| `test_offline_gps_track_upload_is_idempotent_and_drives_emissions` | Batch GPS diunggah 2× tanpa duplikat. Glitch 200 km dan titik akurasi 900 m dibuang. Jejak yang tiba **setelah** rute selesai memicu hitung ulang emisi. |
| `test_failed_stop_unblocks_route_and_harvest_can_be_rescheduled` | Stop gagal tidak bisa dimuat dari antrean basi, rute bisa selesai, dan panen dijadwalkan ulang ke supir lain. |
| `test_collector_cancels_while_truck_on_the_road_pays_deadhead` dan 3 tes pembatalan lain | Ongkos km kosong, batal gratis sebelum berangkat, muatan yang sudah naik tetap diantar, stok lelang dikembalikan. |
| Retur / QC sortir / BOM / stok / OR-Tools / harga / geofence / jam HP / DEMO_MODE / rate-limit | 15 tes lain di `tests/test_field_ops.py`. |
| `tests/e2e_offline_driver.spec.ts` (Playwright, Chromium) | Browser **offline sungguhan**: GPS merekam, pickup masuk antrean. Lalu respons dari server dibuang di tengah jalan (`route.abort`). Hasilnya: tepat 1 `driver_pickup` per panen, jejak tersinkron, emisi `distance_source = gps`. |

## 6. TEKS REVISI SOP — untuk ditambahkan ke PETA_FLOW_DAN_STEP_BY_STEP_BIOCHAIN.docx

Isi lengkap ada di `docs/REVISI_SOP_BIOCHAIN.docx`, yang memuat instruksi "GANTI/TAMBAHKAN" per bab. Ringkasannya:

1. **BAB 2.3 Offline-first.** Tambahkan antrean IndexedDB, aturan 401 (antrean disimpan), kotak gagal, dan GPS store-and-forward dengan Wake Lock.
2. **BAB 3.1 Matriks transisi.** Tambahkan status stop (`pending/picked_up/failed/cancelled`), pembatalan rute, dan batal beli. Ganti status final `REJECTED` menjadi "REJECTED + kasus retur".
3. **BAB 5 (A.3–A.6).** Dispatch memakai OR-Tools. Supir wajib menekan "Mulai Rute" dan boleh melaporkan "Stop gagal". Pabrik menimbang dan, bila menolak, membuka kasus retur.
4. **BAB 6 (B.5, B.8).** Harga basis kering untuk lelang (potongan bila lebih basah). QC sortir sebagian (`rejected_kg`).
5. **BAB 7.** BOM per produk (`expected_kg`, `yield_pct`) dan buku stok produk jadi.
6. **BAB 8.2.** Ganti tabel pengali grade dengan rumus basis kering. Tambahkan ambang risiko jamur 15%. Samakan batas tolak 20%.
7. **BAB 8.6.** Ganti angka baseline 1,28 / C_org 0,85 dengan neraca Green Scorecard (CH₄+N₂O, F_C 0,49, F_perm per suhu).
8. **BAB BARU 8.12 Engine ⑫ Emisi Logistik.** Isinya ISO 14083, B40 2,56 kgCO₂e/L WTW, dan km kosong.
9. **BAB BARU 8.13 Green Scorecard.**
10. **BAB 10.** Tabel dan endpoint baru (daftar di §2.3 dan §4).

## 7. Audit kesiapan lapangan (F1–F19)

| ID | Sev. | Temuan | Status |
|---|---|---|---|
| F1 | Kritis | `/auth/demo-accounts` publik membocorkan password admin; reset-demo bisa menghapus semua data | **Ditutup.** `DEMO_MODE` (wajib False bila `DEBUG=False`, divalidasi saat start). Endpoint demo/seed/reset memberi 404, dan DB produksi tidak di-seed. |
| F2 | Kritis | Offline lebih dari 8 jam membuat JWT kedaluwarsa, flush menerima 401, dan **seluruh antrean terhapus** | **Ditutup.** 401 menyimpan antrean dan meminta login ulang; 5xx/429/408 dicoba lagi; 409/422 masuk kotak gagal. Rekomendasi lanjut: refresh token 30 hari. |
| F3 | Kritis | Diam-diam pindah ke SQLite per worker (split-brain), sehingga RLS dan trigger audit hilang | **Ditutup.** `ALLOW_SQLITE_FALLBACK` dihormati saat inisialisasi (tunggu PG hingga 30 s) dan wajib False di produksi. |
| F4 | Kritis | Nginx tanpa TLS, padahal kamera QR, GPS, dan `crypto.randomUUID` butuh HTTPS | **Ditutup (konfigurasi).** `deploy/nginx.conf`: 443 TLS 1.2/1.3 + certbot webroot, redirect 80→443, HSTS, Permissions-Policy kamera/GPS, `no-cache` untuk `/sw.js`. Validator produksi menolak `CORS_ORIGINS` non-HTTPS. Tinggal: ganti domain & jalankan certbot di server. |
| F5 | Tinggi | Rate limit per IP padahal satu wifi KUD/CGNAT dipakai puluhan petani, sehingga semua terkena 429 | **Ditutup.** Request bertoken dihitung per pengguna (`u:<id>`); login tetap per IP. |
| F6 | Tinggi | Tidak ada reset password/OTP; nomor HP tidak dinormalisasi | **Ditutup (tanpa OTP).** Nomor HP dinormalisasi (`+62/62/spasi/strip → 08…`) di register, admin & login; admin **reset password** → password sementara + `must_change_password` → pengguna wajib ganti saat masuk (`POST /auth/change-password`). Opsional: OTP WhatsApp bila ada penyedia (butuh biaya & izin). |
| F7 | Tinggi | Petani tanpa smartphone tidak terlayani | **Ditutup.** Pengepul mendaftarkan **petani tanpa HP** (persetujuan lisan wajib dicentang & dicatat `lisan_via_pengepul`), melapor atas namanya (`POST /collector/proxy-harvest`, idempoten) dan memberi **nota QR**. Hanya pengepul pembina yang bisa melapor; akun tidak bisa login sampai admin memberi nomor HP. |
| F8 | Tinggi | Tidak ada bukti bayar ke petani; Rupiah disimpan sebagai float; tidak ada pajak | **Ditutup.** Tabel `farmer_payments` (Rupiah **NUMERIC(14,0)** + `Decimal`, CHECK bersih = bruto − pajak), kuitansi `BYR-PGP…-PTN…-YYMM-NNNNN`, metode tunai/transfer/QRIS/e-wallet (non-tunai wajib referensi), idempoten offline, satu lot = satu bayar. Parameter `pajak.pph22_farmer_pct` (default 0). Petani melihat di "Pembayaran saya". Kolom harga lama tetap Double (konversi di batas layanan). |
| F9 | Tinggi | Verifikasi mewajibkan abu/VM/FC yang tidak bisa diukur di lapangan; UI mengisi default | **Ditutup.** Hanya kadar air (dan kontaminan) yang wajib; abu/VM/FC **opsional** di `/verify` dan `/collector/price-quote`. Bobot skor dinormalisasi ulang atas komponen yang benar-benar diukur, rendemen memakai abu referensi parameter `rendemen.ref_ash` bila abu kosong, dan hasil memuat `proximate_measured` agar auditor tahu mana yang diukur. UI tidak lagi mengisi nilai default (kolom kosong dikirim `null`). |
| F10 | Tinggi | Foto bukti hanya input URL; `/uploads` publik; EXIF tidak dihapus; disk container | **Ditutup.** Klien mengompres & membuang EXIF; server **encode ulang** setiap foto (Pillow): tolak berkas palsu, buang EXIF/GPS, perkecil ≤2048 px, cegah *decompression bomb*; PDF divalidasi tanda tangan berkas. Nama berkas acak 128-bit. Untuk skala besar: pindah ke object storage + URL bertanda tangan. |
| F11 | Tinggi | Klaim karbon ESG berasal dari data seed dan berpotensi hitung ganda | **Ditutup.** Alur klaim removal (migrasi 017): pabrik mengajukan per periode dengan hasil lab C-org & H/C-org (wajib; H/C-org > `karbon.h_corg_max` 0,7 ditolak) → snapshot hitungan + parameter dibekukan SHA-256 → auditor (bukan pengaju, bukan admin) memverifikasi/menolak dengan alasan. Serah-terima biochar dikunci UNIQUE ke satu klaim aktif; periode klaim aktif tidak boleh tumpang-tindih. Status tetap "verifikasi internal, bukan kredit" sampai VVB & SRN-PPI. |
| F12 | Tinggi | UU PDP 27/2022: tidak ada persetujuan/ekspor/hapus data; HP petani terlihat semua pengepul | **Ditutup (dasar).** Persetujuan per tujuan (wajib/GPS/foto) saat daftar & menu **🔒 Data saya**; unduh data (JSON) & **hapus akun = anonimisasi** (identitas dihapus, catatan transaksi disimpan tanpa identitas untuk audit/pajak); bukti `data_requests`; nomor petani **disamarkan** di daftar pengepul, nomor lengkap via "Hubungi" yang dicatat log audit. Lanjutan: DPO & kebijakan privasi tertulis, retensi terjadwal. |
| F13 | Sedang | Jam HP salah menggeser laporan bulanan | **Ditutup.** Jendela −72 jam / +10 menit; di luar itu dipakai jam server dan dicatat di custody. |
| F14 | Sedang | Pickup bisa dikonfirmasi dari rumah (tanpa geofence); QR 32-bit | **Ditutup.** Geofence 500 m ditandai untuk auditor. QR baru `BIO-XXXXXXXX-TTTTTT` bertanda tangan HMAC (`QR_HMAC_KEY`); rute supir membawa digest satu arah sehingga QR dicocokkan di lokasi **tanpa sinyal** tanpa membocorkan kode. QR lama tercetak tetap diterima & ditandai `QR_LAMA` selama `logistik.qr_legacy_policy` = terima_tandai. |
| F15 | Sedang | index.html 211 KB tanpa gzip; CDN dimuat sinkron | **Ditutup.** Semua skrip CDN dimuat `defer` dengan SRI (`integrity` sha384/sha512 sesuai cdnjs) + `crossorigin`; service worker meng-cache CDN (sw v7); gzip di nginx (`gzip_types` css/js/json). Opsional: vendor lokal bila CDN diblokir jaringan. |
| F16 | Sedang | Job & limiter in-memory saat multi-worker | **Ditutup.** Produksi (`DEBUG=false`) menolak start bila `JOB_BACKEND` bukan `arq`, kecuali `ALLOW_LOCAL_JOBS_IN_PROD=true` untuk server satu worker. |
| F17 | Sedang | Tanpa logging terstruktur, versi migrasi, atau backup | **Ditutup (dasar).** Log JSON terstruktur (`LOG_FORMAT=json`) + **X-Request-ID** di setiap respons & baris log; log akses tanpa query string; `scripts/backup_pg.sh` (pg_dump harian, rotasi 14 hari, uji `pg_restore --list`, sha256, rsync opsional). Lanjutan: Sentry/OTel & pgBackRest PITR. |
| F18 | Rendah | HP bersama: antrean pengguna lain tersisa | **Ditutup.** Antrean, foto & titik GPS terikat `user_id` + nama pemilik; supir lain tidak lagi mengirim (lalu menghapus) jejak GPS pemilik; cache rute per pengguna; saat login muncul pemberitahuan "N data offline milik … menunggu". |
| F19 | Rendah | CORS di-hardcode localhost | **Ditutup.** `CORS_ORIGINS` dari env (dipisah koma); default origin lokal hanya saat DEBUG; produksi wajib domain HTTPS eksplisit tanpa `*`. |

Status 2026-10-11: **19 dari 19 temuan ditutup atau ditutup-dasar** (F11, F14, F18 ditutup — rincian `docs/14_PENUTUPAN_F11_F14_F18.md`; OTP F6 opsional). Uji: 486 lulus di SQLite (+6 SLO latensi dijalankan terpisah), uji PG+RLS lulus, 16 spec e2e lulus. Sebelum pilot tinggal langkah server: jalankan certbot (F4), isi `.env` produksi (`CORS_ORIGINS`, `JOB_BACKEND=arq`), pasang cron `backup_pg.sh`, dan terapkan migrasi 014 di PostgreSQL produksi.

Setelah itu, sebelum klaim karbon publik: klaim F11 terverifikasi auditor internal + uji lab C_org per periode, lalu VVB & SRN-PPI. Isi `QR_HMAC_KEY` sebelum mencetak QR baru.

## 8. Tiga fungsi wajib — status uji penerimaan (`tests/test_required_functions.py`)

| Fungsi | Endpoint | Hasil |
|---|---|---|
| Parameter feedstock → perbandingan + rekomendasi pemilihan/blending | `POST /labs/feedstock/compare` (TOPSIS + HHV Parikh), `POST /labs/blend/recommend` (LP HiGHS) | Lulus: peringkat 1–3, kalimat rekomendasi, campuran biaya minimum |
| Karakteristik/volume limbah → teknologi konversi + potensi energi | `POST /labs/waste-energy/advise` | Lulus. Diperbaiki: limbah basah dulu tampil "0 GJ"; kini ringkasan memuat **listrik teknologi terbaik** (mis. biogas kotoran sapi 15 t/hari ≈ 413 MWh/tahun) |
| Data historis energi → IKE, anomali/pemborosan, rekomendasi efisiensi | `POST /labs/energy/analyze`, `/factory/energy/*` | Lulus: IKE (Permen ESDM 13/2012), anomali robust-Z dan CUSUM menemukan 2 bulan boros yang disuntikkan, rekomendasi berprioritas |

## 9. Rekomendasi green chemistry, jejak karbon, ekonomi sirkular, green supply chain

Sudah dibangun: **`GET /factory/green-scorecard`** (pabrik/admin/auditor).

- **Karbon (tCO₂e).** Dihitung sebagai: +pembakaran terbuka dihindari (CH₄+N₂O, IPCC 2006) + sekuestrasi biochar (F_C × F_perm(T) × 44/12, IPCC 2019) − emisi angkut (Engine ⑫) − listrik proses (kWh × EF grid). Hasilnya juga dinyatakan per ton sekam. Bio-pellet yang dibakar tidak dihitung sebagai sekuestrasi.
- **Sirkularitas.** Valorisasi massa, porsi biochar kembali ke petani, laju retur, dan porsi retur yang dipulihkan.
- **Green chemistry.** E-factor padat silika (Sheldon) dan efisiensi ekstraksi SiO₂ terhadap teori.

Rekomendasi lanjutan, diurutkan dari dampak terbesar:

1. **Catat bahan kimia per batch dalam kg** (NaOH, HCl/H₂SO₄, air) agar Process Mass Intensity dan emisi hulu bahan kimia bisa dihitung. Saat ini hanya tercatat dalam Rupiah.
2. **Presipitasi silika dengan CO₂ gas buang (karbonasi)**, menggantikan asam mineral, dan **daur ulang larutan induk NaOH**. Kedua langkah menurunkan E-factor dan biaya.
3. **Syngas pirolisis untuk pengering & kalsinasi.** Catat energi yang dipulihkan sebagai kredit di scorecard.
4. **Uji lab C organik & H/C_org per batch** (Puro.earth mensyaratkan < 0,7), lalu verifikasi pihak ketiga (Verra VM0044 / Puro) sebelum menjual kredit.
5. **Data primer BBM armada** (liter per rute dari nota SPBU) menggantikan default 0,15/0,20 L/km.
6. **Pemadatan/baling sekam di penggilingan.** Densitas curah 110 kg/m³ adalah pemborosan volume terbesar.
7. **Indikator sirkularitas MCI (Ellen MacArthur)** per produk setelah data pemakaian biochar petani (redemption) tercatat.

## 10. Cara menjalankan pengujian

```bash
# SQLite (cepat)
DATABASE_URL="sqlite+aiosqlite:///biochain_test.db" py -m pytest -q -p no:cacheprovider
# PostgreSQL (RLS, trigger, PL/pgSQL)
docker start biochain-postgres && py scripts/pg_setup.py
DATABASE_URL=postgresql+asyncpg://biochain_app:biochain_app_dev@localhost:5433/biochain AUTO_MIGRATE=false \
BIOCHAIN_TEST_PG_OWNER_URL=postgresql+asyncpg://biochain:biochain_dev_2026@localhost:5433/biochain \
py -m pytest -q -p no:cacheprovider
# E2E browser offline (server demo SQLite bersih di port 8765)
DATABASE_URL="sqlite+aiosqlite:///e2e_offline.db" py -m uvicorn app.main:app --port 8765
BIOCHAIN_URL=http://127.0.0.1:8765 npx -y @playwright/test@1.64.0 test tests/e2e_offline_driver.spec.ts
```

## 11. Rujukan

- ISO 14083:2023; Smart Freight Centre, *GLEC Framework v3.2* (2025).
- Kepmen ESDM 341.K/EK.01/MEM.E/2024 (B40).
- IPCC 2006 Guidelines Vol.4 Ch.2; IPCC 2019 Refinement Vol.4 Ch.2 Appendix 4 (biochar).
- Bektaş & Laporte (2011) *Transportation Research Part B* 45(8):1232-1250 (Pollution-Routing Problem).
- Google OR-Tools 9.15, dokumentasi CVRP.
- Sheldon (2017) *Green Chemistry* 19:18-43 (E-factor).
- Chen et al. (2023) *Energy* 285:129391 (pemanasan diri biomassa basah).
- FAO X5036E dan T1838E (pengeringan & mikotoksin).
- Mansaray & Ghaly (1997) *Energy Sources* 19(9) (densitas sekam).
- Puro.earth Biochar Methodology Edition 2025; Verra VM0044 v1.1.

Nilai yang **belum terverifikasi** dan wajib diganti data lokal:

- ambang jamur khusus sekam (proksi gabah 14,5–18,3%)
- konsumsi BBM kosong/penuh truk Indonesia
- EF B40 berbasis sawit (bisa lebih tinggi bila alih guna lahan diperhitungkan)
- F_C biochar sekam per batch
- porsi pembakaran terbuka di wilayah layanan
