# 17 — Prototipe 1: Least-Cost Fuel Blending & Indeks Risiko Terak (Fase 2)

**Tanggal:** 11 Oktober 2026 · **Engine:** `app/engines/fuel_blend.py` (Engine ③b, melengkapi Engine ③ blending biochar) · **Riset:** `docs/15` §2, §3, §9

## 1. Formulasi

Variabel xᵢ adalah **kg bahan kering**, sehingga semua batas menjadi linear. Solver: HiGHS via SciPy.

```
min  Σ xᵢ·[harga_arᵢ/(1−MCᵢ) + (air diuapkan per kg kering)ᵢ × biaya pengeringan]
s.t. Σ xᵢ = target × (1 − MC_produk)
     kalori:  NCV ar → Σ xᵢ·(LHV_d,min − LHV_dᵢ) ≤ 0,  LHV_d,min = (target + 2,443·MC)/(1 − MC)   (ISO 18125)
              GCV ar → Σ xᵢ·(target/(1 − MC) − HHV_dᵢ) ≤ 0
     abu, Cl, S:  Σ xᵢ·(nilaiᵢ − batas) ≤ 0
     indeks alkali:  Σ xᵢ·(Aᵢ·(K₂O+Na₂O)ᵢ/10⁴ − AI_max·HHVᵢ/1000) ≤ 0               (Miles 1996)
     0 ≤ xᵢ ≤ stokᵢ·(1−MCᵢ),  porsi min/maks per bahan (mis. sekam ≤ 30 % untuk durabilitas pelet)
```

Bila tidak ada campuran yang layak, sistem menyebut batas mana yang, bila dilonggarkan sendirian, membuat campuran menjadi layak (`relax_one_of`).

## 2. Indeks keamanan abu

| Indeks | Rumus | Ambang | Sumber |
|---|---|---|---|
| Alkali Index | A% × (K₂O+Na₂O)% / (10 × HHV MJ/kg), kg/GJ | > 0,34 → **"Risiko Tinggi Terak/Slagging pada Boiler Industri"** (ditolak optimizer); 0,17–0,34 → peringatan | Miles 1996; Zhu 2014 |
| B/A, Rs, Fu, Si/Al, G | dari komposisi oksida campuran **berbobot massa abu** (rasio tidak aditif) | Zhu 2014 Tabel 4 | docs/15 §2 |
| Cl | % bk | > 0,3 tinggi (korosi HCl/KCl) | Zhu 2014 |

Peringatan kontekstual:
- Sekam > 30 %: silika mengkristal (kristobalit) di atas ±800 °C.
- Campuran kaya K₂O + SiO₂: risiko K-silikat bertitik leleh rendah; interaksi ini tidak tertangkap oleh rata-rata linear, jadi perlu **uji AFT ISO 21404**.

## 3. Temuan penting dari pengujian

- **"4.000 kcal/kg" harus jelas basisnya.**
  - Bila basisnya NCV as-received pada MC 10 %, dibutuhkan LHV_db ≥ 18,9 MJ/kg. Hampir tidak ada bahan Jawa yang mencapainya selain tempurung.
  - Pasar pelet RI dan spesifikasi PLN memakai **GCV ar**, jadi preset "4.000 kcal" dan "co-firing PLN" memakai GCV ar. ISO 17225-6 tetap NCV.
- **Tongkol jagung murni:** AI sekitar 0,40, berstatus BAHAYA. Optimizer otomatis mengencerkannya dengan serbuk kayu (AI sekitar 0,09).
- **Pelet sekam murni:** gagal ISO 17225-6 kelas B, karena abu 17,5 % dan NCV terlalu rendah sekaligus.
- **Biaya pengeringan menentukan:** ampas tebu (MC 50 %) tampak paling murah bila biaya pengeringan nol. Karena itu parameter "Biaya pengeringan per kg air diuapkan" dibuat **wajib diisi** (tanpa nilai bawaan), dan hasil optimasi memberi catatan bila belum diisi.

## 4. API & UI

- `GET /api/v1/factory/fuel-blend/presets`: preset (ISO 17225-6 A/B, 4.000 kcal GCV, co-firing PLN), ambang indeks, dan stok bahan di pabrik (lot diterima yang belum diolah) per komoditas.
- `POST /api/v1/factory/fuel-blend/optimize`: properti diambil dari master biomassa (hasil lab menang). Harga dan MC per baris boleh ditimpa.
- `POST /api/v1/factory/fuel-blend/evaluate`: untuk slider manual (porsi % bk).
- **UI pabrik:**
  - pilih bahan, stok, harga, MC aktual, porsi maksimum;
  - kartu kelayakan (LAYAK/TIDAK LAYAK + daftar cek), biaya per kg dan per GJ;
  - **radar chart** (setiap sumbu = nilai ÷ batas; > 1 berarti melewati batas);
  - **slider proporsi** yang menghitung ulang indeks terak secara langsung.
- **Parameter baru:** `blending.drying_cost_rp_per_kg_water` (wajib isi), `blending.ai_max_kg_gj` (0,34).

## 5. Uji

- `tests/test_fuel_blend.py` (6): LHV_ar ISO 18125, klasifikasi terak, kendala alkali memaksa pengenceran, biaya pengeringan mengubah komposisi, preset ISO B menolak sekam murni, endpoint slider & hak akses.
- `tests/e2e_multibiomass.spec.ts`: optimasi via UI → LAYAK + radar; slider ke 100 % tongkol jagung → peringatan "Risiko Tinggi Terak/Slagging pada Boiler Industri".

## 6. Keterbatasan

- Rata-rata linear tidak menangkap interaksi kimia abu maupun durabilitas pelet.
- Indeks abu turunan batu bara hanya penyaring awal (Garcia-Maraver 2017; Lachman 2021).
- Nilai ISO 17225-6 bertanda [L] karena standarnya berbayar. Verifikasi dengan dokumen resmi sebelum klaim mutu ke pembeli.
