# 18 — Prototipe 2: Energi Riil Basis Kadar Air Lapangan & Pohon Keputusan Teknologi (Fase 3)

**Tanggal:** 12 Oktober 2026 · **Engine:** `app/engines/conversion_energy.py` (Engine ⑨b, pelengkap Engine ⑨ WtE generik) · **Riset:** `docs/15` §3–5

## 1. Rumus

| Besaran | Rumus | Sumber |
|---|---|---|
| Nilai kalor as-received | LHV_ar = LHV_db·(1 − MC) − **2,443**·MC (MJ/kg, MC fraksi) | ISO 18125:2017 (24,43 J/g per % air). Protokol menulis 2,442; selisihnya < 0,05 %, dan 2,443 dipakai agar konsisten dengan ISO |
| Energi termal | E_th [GJ] = massa [kg] × LHV_ar / 1000 | — |
| Listrik | E_el [MWh] = massa [kg] × LHV_ar × η / 3600 | protokol |
| η | turbin uap kecil **22 %**; sistem terintegrasi **28 %**; co-firing PLTU **36 %** (parameter) | IRENA 2012; IRENA-ETSAP E21 (co-firing 36–44 %) |
| CO₂ dihindari | E_el × EF grid JAMALI **0,87 tCO₂/MWh** | Kepmen ESDM 163.K/2021 (CM, data 2019); bukan batas PTBAE 0,911–1,297 |
| Pengeringan | air diuapkan ke MC kerja rute × 3,0 MJ/kg (≈ 1,2 × panas laten) dikurangkan dari energi rute | `limbah.drying_mj_per_kg_water` |

## 2. Pohon keputusan

1. **Produk karbon/silika bernilai tinggi?**
   - SiO₂ abu ≥ 85 % dan abu ≥ 12 % → pirolisis lambat: **biochar + bio-silika** (sekam).
   - FC ≥ 20 % dan abu ≤ 3 % → pirolisis: **arang/karbon aktif** (tempurung). Di Indonesia keduanya bernilai jauh di atas listrik.
2. **Lolos spesifikasi co-firing dan dekat PLTU?**
   - Syarat: GCV ar ≥ 3.009 kcal/kg, MC ≤ 25 %, Cl ≤ 0,2 %, indeks alkali ≤ 0,34, jarak ≤ 150 km (parameter). Spesifikasi mengacu pada woodchip PLTU Teluk Sirih.
   - → **Co-firing PLTU**, rute dengan η tertinggi.
3. **Skala ≥ 50 t/hari, MC ≤ 55 %, abu ≤ 20 %?** → **pembakaran langsung + turbin uap**, misalnya boiler ampas tebu di pabrik gula.
4. **Abu ≤ 6 %, MC dapat dikeringkan, skala 2–25 t/hari?** → **gasifikasi + mesin gas**.
5. Selain itu → **pembakaran skala kecil** untuk panas proses.

Setiap rute menampilkan daftar cek ✅/⛔ beserta angkanya, jadi pengguna melihat alasan rute lain tidak dipilih.

## 3. Hasil uji (data master literatur)

| Kasus | Rute | Catatan |
|---|---|---|
| Sekam 1.000 t/bln, MC 12 % | Pirolisis (biochar + bio-silika) | LHV_ar 12,3 MJ/kg; setara ±751 MWh/bln pada η 22 % bila dibakar |
| Serbuk sengon kering (MC 20 %) 40 km dari PLTU | Co-firing | Gagal co-firing bila MC 45 % atau jarak 400 km |
| Ampas tebu 3.000 t/bln (MC 50 %) | Pembakaran langsung | LHV_ar hanya 7,5 MJ/kg; energi pengeringan besar |
| Tongkol jagung 300 t/bln | Gasifikasi | Peringatan: indeks alkali > 0,34 → campur dengan bahan rendah alkali (Prototipe 1) |

## 4. API & UI

- `POST /api/v1/factory/conversion/analyse` (pabrik/admin; auditor baca): input komoditas, tonase per bulan, MC aktual (kosong = tipikal master), jarak ke PLTU.
- **UI pabrik:**
  - kartu LHV ar (MJ dan kcal), energi termal GJ/bulan, listrik pada η 22/28/36 %, dan CO₂ dihindari;
  - jejak pohon keputusan;
  - tabel semua rute beserta syarat dan hasilnya (MWh, tCO₂, GJ pengeringan, biochar/bio-silika, atau panas).
- **Parameter baru (`limbah.*`):** `eta_el_steam_small`, `eta_el_integrated`, `eta_el_cofiring`, `cofiring_gcv_min_kcal`, `cofiring_mc_max`, `cofiring_max_km`. Sumber EF grid dipertegas.

## 5. Uji

- `tests/test_conversion_energy.py` (4): rumus protokol (LHV_ar, E_el, CO₂), bahan basah dan biaya pengeringan, pohon keputusan sesuai praktik lapangan, endpoint dan hak akses.
- `tests/e2e_multibiomass.spec.ts`: sekam → pirolisis; serbuk kering dekat PLTU → co-firing.

## 6. Keterbatasan

- Emisi dihindari ≠ removal karbon. Keduanya dilaporkan terpisah (GHG Protocol LSR); karbon biochar diklaim lewat alur F11.
- Biaya modal (IRENA: stoker USD 1.880–4.260/kW) belum masuk ke keputusan. Ini kandidat lanjutan untuk analisis NPV.
- Rincian OM/BM terpisah untuk JAMALI belum tersedia di sumber terbuka. Perbarui parameter EF bila ESDM menerbitkan nilai baru.
