# Hasil Pengujian Benchmark Engine Bio-Chain

- **Waktu Eksekusi**: 2026-10-05 02:04:53 UTC
- **Lingkungan Sistem**: Windows 11 (AMD64), Python 3.14.5
- **Mode Pengujian**: In-Memory Engine (Direct Call)
- **Ambang Batas SLO Latensi**: ≤ 500 ms (dinilai pada p95)

## Ringkasan Kinerja

| Engine | Skenario | Ukuran Input | N | p50 (ms) | p95 (ms) | Maks (ms) | SLO (ms) | Status |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Engine ⑤ Routing** | Route Optimizer CVRP (Clarke-Wright + Local Search) | 50 titik, cap=30 m³ | 3 | 249.89 | 250.18 | 250.21 | 500 | ✅ PASS |
| **Engine ⑤ Routing** | Route Optimizer CVRP (Clarke-Wright + Local Search) | 200 titik, cap=30 m³ | 3 | 252.49 | 252.52 | 252.52 | 500 | ✅ PASS |
| **Engine ⑤ Routing** | Route Optimizer CVRP (Clarke-Wright + Local Search) | 1000 titik, cap=300 m³ | 3 | 273.96 | 279.30 | 279.89 | 500 | ✅ PASS |
| **Engine ⑧ Feedstock** | Feedstock TOPSIS Multi-Criteria | 10 jenis feedstock | 3 | 0.21 | 0.21 | 0.22 | 500 | ✅ PASS |
| **Engine ⑧ Feedstock** | Feedstock TOPSIS Multi-Criteria | 100 jenis feedstock | 3 | 4.35 | 4.66 | 4.69 | 500 | ✅ PASS |
| **Engine ③ Blending** | Blending Optimizer (SciPy HiGHS LP) | 4 feedstock, target=100 ton | 3 | 1.84 | 1.89 | 1.89 | 500 | ✅ PASS |
| **Engine ② Quality** | Quality Scorer & Yield (10k evaluasi berturut-turut) | 10.000 sampel sekam | 3 | 131.65 | 133.09 | 133.24 | 500 | ✅ PASS |
| **Engine ⑩ Energy** | Energy Analytics (IKE, SEC, Baseline Regresi & CUSUM) | 24 bulan pencatatan | 3 | 0.46 | 0.47 | 0.48 | 500 | ✅ PASS |
| **Engine ⑩ Energy** | Energy Analytics (IKE, SEC, Baseline Regresi & CUSUM) | 120 bulan pencatatan | 3 | 0.92 | 0.92 | 0.92 | 500 | ✅ PASS |
| **Engine ① Forecaster** | Supply Forecaster (Model Cosinus Ganda Musim Jawa) | 15.000 ha, bulan ke-5 | 3 | 0.01 | 0.02 | 0.02 | 500 | ✅ PASS |
| **Engine ④ Carbon** | Carbon Reduction (IPCC Tier 2 LCA) | 1.000 ton sekam, 80 km | 3 | 0.01 | 0.02 | 0.02 | 500 | ✅ PASS |
| **Engine ⑥ Incentive** | Incentive Calculator (Tier Mutu + Karbon) | Grade A, 250 tCO2e | 3 | 0.01 | 0.02 | 0.02 | 500 | ✅ PASS |
| **Engine ⑦ Factory Econ** | Factory Economics Netback Pricing | Kadar air 12%, abu 18% | 3 | 0.12 | 0.13 | 0.13 | 500 | ✅ PASS |
| **Engine ⑨ Waste-to-Energy** | Waste-to-Energy Advisor (Biokimia vs Termokimia) | 50 ton/hari sekam | 3 | 0.03 | 0.04 | 0.05 | 500 | ✅ PASS |

**Status Keseluruhan**: ✅ SEMUA ENGINE MEMENUHI SLO

## Analisis Kinerja
- Algoritma **Route Optimizer (CVRP)** menggunakan heuristik Clarke-Wright yang dioptimalkan dengan matriks jarak vektorisasi NumPy, sehingga 1.000 titik dapat diselesaikan dalam hitungan puluhan hingga ratusan milidetik.
- Pengujian **Quality & Yield** mampu mengevaluasi 10.000 sampel secara beruntun jauh di bawah ambang batas SLO 500 ms.
- Algoritma **Linear Programming (HiGHS via SciPy)** untuk Blending menyelesaikan optimasi secara eksak dalam waktu < 5 ms.
- Algoritma analitik energi (regresi OLS + CUSUM anomali) dan TOPSIS multi-kriteria feedstock berskala linear terhadap jumlah titik data.
