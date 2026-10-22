# 23 — Runbook Operasional Produksi Industrial-Grade Bio-Chain v2

**Standar:** ISO 50001:2018 (Energy Management), ISO 14083:2023 (Logistics GHG), Kepmentan 261/2019 (Pupuk Hayati & Pembenah Tanah), Zero-Trust Multi-Tenancy RLS (PostgreSQL 16).

---

## 1. Arsitektur & Topologi Produksi

* **Backend API:** FastAPI (Python 3.12/3.14) dijalankan via Gunicorn + UvicornWorker (`deploy/gunicorn.conf.py`) di belakang Nginx reverse proxy dengan HTTP/2 dan TLS 1.3.
* **Database Transaksional:** PostgreSQL 16 dengan Row-Level Security (RLS) dipaksakan (`FORCE ROW LEVEL SECURITY`) untuk isolasi multi-tenant (`organization_id`, `factory_id`, `collector_id`, `farmer_id`).
* **Connection Pooling:** PgBouncer (Transaction Pooling mode) di port 6432 dengan `DB_STATEMENT_TIMEOUT_MS = 5000` dan `set_config(..., true)` per transaksi.
* **PWA & Edge Sync:** Service Worker v13 (`sw.js`) dengan cache-first app shell, antrean IndexedDB (`biochain_rural_offline_db`) untuk transaksi offline supir & pengepul, kompresi foto Canvas max 300KB.

---

## 2. Pemeriksaan Rutin Operasional (Health Checks)

| Frekuensi | Komponen | Perintah / Indikator | Ambang Batas Wajar | Tindakan Mitigasi Jika Anomali |
|---|---|---|---|---|
| **Per Menit** | API Liveness & DB Connectivity | `GET /api/v1/system/status` | HTTP 200, `db_status: "connected"` | Auto-restart worker via systemd/supervisord |
| **Per Jam** | Antrean Offline Gantung | `SELECT count(*) FROM custody_events WHERE is_offline_replay = true AND created_at < now() - interval '24 hours'` | 0 baris | Hubungi supir/pengepul terkait, sinkronkan perangkat |
| **Shift 8 Jam** | Anomali IKE / SEC Boiler & Pelet | `GET /api/v1/analytics/energy/audit-sec-dynamic` | Residual EnPI $|Z| < 2.0$ | Cek keausan hammer mill screen atau kadar air umpan basah |
| **Harian** | Cadangan Database (WAL / Dump) | `ls -lh /var/backups/biochain/` | File dump utuh jam 02.15 WIB | Jalankan `scripts/backup_pg.sh` manual |
| **Mingguan** | Potongan Logistik & Sisa Retur | Menu Pabrik → Kasus Retur & Potongan Logistik | Kasus 'terbuka' < 5 | Eksekusi disposisi retur atau potong tagihan berikutnya |
| **Bulanan** | Simulasi Restore Cadangan | `scripts/test_pg_restore.sh` | Integritas baris identik 100% | Audit storage remote & enkripsi backup |

---

## 3. Prosedur Lelang Atomik & Rekonsiliasi Timbangan

### 3.1 Transaksi Lelang Bersamaan
* Semua transaksi penawaran stok dan kesepakatan wajib melalui RPC `place_bid_atomic` dan `accept_bid_atomic`.
* **Prosedur:**
  1. Sistem mengunci baris inventaris dengan `SELECT ... FOR UPDATE` pada `stock_listings`.
  2. Jika terjadi balapan penawaran serentak, transaksi yang tiba belakangan otomatis mendapatkan respon status `409 Conflict: Sisa stok tidak mencukupi atau lelang telah ditutup`.
  3. Tidak ada intervensi manual yang diperlukan; database menjamin tidak terjadi *double allocation*.

### 3.2 Rekonsiliasi Selisih Timbangan Lapangan vs Jembatan Pabrik (Weighbridge)
* **Aturan Mutlak:** Timbangan jembatan pabrik (*Weighbridge*) bertindak sebagai *Single Source of Truth*.
* **Prosedur Lapangan:**
  1. Catatan tonase supir (`picked_up_kg`) disimpan sebagai data audit logistik, bukan dasar faktur pembayaran.
  2. Saat truk tiba di pos penimbangan pabrik, operator menimbang bruto dan tara (`InboundQC`).
  3. Jika kadar air aktual $MC_{aktual} > MC_{kontrak}$, sistem menghitung refraksi basis kering:
     $$Kg_{bayar} = Gross \times (1 - \text{kontaminan}) \times \frac{100 - MC_{aktual}}{100 - MC_{kontrak}}$$
  4. Selisih berat $> 5\%$ otomatis memicu bendera `discrepancy_flag = true` pada sistem untuk investigasi susut jalan (terpal basah/bocor atau pencurian sekam).

---

## 4. Standar Manajemen Bahan Bakar Blending & Abu Agronomi

### 4.1 Formulasi Blending Aman (Anti-Slagging)
* Operator pabrik dilarang memasukkan formulasi bahan bakar boiler dengan Indeks Alkali $AI > 0.34\text{ kg/GJ}$.
* Jika formulasi pelet/bakar biomassa mengandung Tongkol Jagung atau Sabut Kelapa berkadar $K_2O > 30\%$, rasio pencampuran wajib dibatasi maksimal $30\%$ bahan kering dan dicampur dengan biomassa tinggi kalsium/silika stabil (mis. serbuk gergaji sengon/kayu keras).
* Sistem secara otomatis menolak formulasi berbahaya dengan status **BAHAYA TERAK BOILER**.

### 4.2 Verifikasi Logam Berat Abu Sisa Bakar (Kepmentan 261/2019)
* Setiap lot abu boiler/pirolisis yang keluar ke penampungan wajib diinput hasil uji lab akreditasi (AAS/ICP-MS):
  * **Timbal ($Pb$):** Maksimal $50\text{ ppm}$
  * **Kadmium ($Cd$):** Maksimal $2\text{ ppm}$
  * **Arsen ($As$):** Maksimal $10\text{ ppm}$
* Jika parameter melampaui ambang batas:
  1. Sistem otomatis menetapkan status `heavy_metal_status = 'gagal'`.
  2. Database memblokir fungsi alokasi ke Kelompok Tani (Poktan) via konstrain `ck_cal_farmer_gate`.
  3. Status diubah menjadi `dibuang` dengan tujuan pengolahan limbah B3/non-B3 terdaftar dan nomor manifest DLH.
* Jika lulus uji lab:
  1. Status abu menjadi `lulus` $\rightarrow$ `dialokasikan` ke Poktan binaan.
  2. Serah terima wajib merekam titik GPS lahan pertanian dan foto BAST penyerahan.

---

## 5. Matriks Tanggap Darurat & Eskalasi Insiden (L1 - L3)

| Level | Kriteria Insiden | Contoh Kasus | Prosedur Penanganan |
|---|---|---|---|
| **L1 (Minor)** | Kesalahan klien lokal atau sinyal pedesaan hilang | Supir tidak bisa mengirim data pickup di blank-spot pegunungan | Data tersimpan di IndexedDB; supir melanjutkan rute; sinkronisasi otomatis berjalan saat mencapai area sinyal 4G. |
| **L2 (Major)** | Lonjakan anomali energi atau degradasi mutu bahan baku | Peringatan $Z > 3.0$ pada IKE hammer mill; muatan sekam kehujanan $MC > 20\%$ | 1. Buka Kasus Retur di gerbang pabrik.<br>2. Alihkan sekam basah ke lantai penjemuran/pengering.<br>3. Periksa saringan hammer mill dari keausan mekanis. |
| **L3 (Kritis)** | Kebocoran data tenant atau deadlock transaksi database | Pabrik A melihat order Pabrik B; PgBouncer connection pool starvation | 1. Segera aktifkan isolasi darurat `AUTO_MIGRATE=false`.<br>2. Validasi setting `set_config('app.organization_id')` pada pooling middleware.<br>3. Kill query menggantung: `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'active' AND query_start < now() - interval '30 seconds';`. |
