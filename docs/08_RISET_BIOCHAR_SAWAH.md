# 08 — Riset Biochar Sekam Padi di Sawah: Dasar Ilmiah Rumus Manfaat Ekonomi Petani ("Dompet Biochar")

Tanggal akses sumber: 2026-10-11 · Wilayah: Sleman (DIY) & Klaten (Jawa Tengah)

> Catatan metode: alat pencarian Firecrawl tidak tersedia di mesin ini, jadi riset memakai WebSearch/WebFetch, PubMed E-utilities, Crossref, Europe PMC, dan PDF resmi IPCC. Setiap angka di tabel dicek ke abstrak, PDF, atau rilis aslinya. Angka yang tidak bisa dicek ke sumber primer diberi tanda **[asumsi]** atau **[perlu verifikasi]**.

---

## 1. Ringkasan

- **Hasil panen.** Meta-analisis global untuk padi sawah konsisten menemukan **kenaikan hasil sekitar 10–16%**: Liu dkk. 2022 +10,73%; Bu dkk. 2022 +11,3% (tahun pertama); Awad dkk. 2018 +16%; Zhu dkk. 2026 +16,4%. Untuk tanah tropis (semua tanaman), Jeffery dkk. 2017 melaporkan rata-rata +25%. Namun dosis median dalam studi-studi ini **15–20 t/ha atau lebih**, jauh di atas jatah Dompet Biochar yang realistis (0,5–3 t/ha).
- **Pengaruh dosis.** Hubungan dosis–hasil **lemah dan cepat jenuh**. Yu dkk. 2023 melaporkan bahwa kenaikan hasil padi "mirip" di berbagai tingkat dosis karbon, sehingga dosis bisa dikurangi demi ekonomi. Iboko dkk. 2023 mencatat hasil tertinggi justru pada biochar dosis rendah (≤9 t/ha) yang dipadukan dengan N tinggi. Karena itu rumus memakai **kurva jenuh** (diminishing returns) dengan plafon konservatif 10%.
- **Efek sisa (residual).** Efek menurun dari tahun ke tahun. Yu dkk. 2023 mendapati efek **umumnya tidak signifikan lagi setelah 3 tahun**, dan Koyama & Hayashi 2019 melihat efek musim ke-2 sudah melemah. Rumus memakai peluruhan 50% per musim, dihitung maksimal 4 musim (sekitar 2 tahun).
- **Hemat pupuk.** Biochar meningkatkan efisiensi serapan N (NUE): Liu dkk. 2022 +12,04%; Yuan dkk. 2024 +26,1% di sawah. Uji lapang Xu dkk. 2022 menunjukkan bahwa **80% dosis N + 5 t/ha biochar** memberi hasil 10,22% lebih tinggi daripada 100% N tanpa biochar. Uji di Indonesia (Pratiwi dkk. 2021, sawah tadah hujan) merekomendasikan **5 t/ha biochar sekam + 50% urea CRF**. Rumus memakai penghematan urea konservatif **3% per t/ha, maksimal 15%**.
- **Karbon.** Rumus memakai metode IPCC 2019 Refinement. Kandungan C organik biochar sekam/jerami (pirolisis) adalah **0,49** (±41%), dan fraksi yang bertahan 100 tahun **0,80** untuk pirolisis 450–600 °C. Hasilnya **±1,44 t CO₂e per ton biochar**.
- **CH₄/N₂O.** Arahnya umumnya baik: N₂O turun sekitar 25% (Bu 2022), dan CH₄ di sawah cenderung turun (Jeffery 2016). Namun hasil CH₄ tidak konsisten antar meta-analisis, jadi **tidak dirupiahkan** di rumus.
- **Contoh hitung.** Petani 0,5 ha yang menerima 500 kg biochar (1 t/ha) mendapat tambahan sekitar **50 kg GKP** di musim pertama. Totalnya sekitar **Rp570 ribu bersih selama 2 tahun** (sekitar Rp285 ribu/tahun), ditambah sekitar **0,72 t CO₂e** karbon tersimpan. Nilai ini kecil tetapi nyata, dan sengaja dibuat konservatif.

---

## 2. Tabel Koefisien

| # | Nama (kode) | Nilai default | Rentang wajar | Satuan | Sumber / dasar | Tingkat kepastian |
|---|---|---|---|---|---|---|
| 1 | Plafon respons hasil `R_max` | **0,10** | 0,05–0,16 (tropis hingga 0,25) | fraksi | Liu 2022 (+10,73%); Bu 2022 (+11,3%); Awad 2018 (+16%); Zhu 2026 (+16,4% padi); Jeffery 2017 (+25% tropis, semua tanaman) | Sedang. Default diambil di batas bawah sebaran meta-analisis |
| 2 | Laju kejenuhan dosis `k` | **0,20** | 0,10–0,35 | per (t/ha) | **[asumsi]** dikalibrasi agar 5 t/ha ≈ 63% dari R_max dan 10 t/ha ≈ 86%. Konsisten dengan Yu 2023 (respons padi mirip antar dosis) dan Iboko 2023 (dosis rendah tetap efektif) | **Rendah**. Belum ada kurva dosis–respons sekam padi yang dipublikasikan untuk dosis <5 t/ha |
| 3 | Batas dosis efektif `r_cap` | **10** | 5–20 | t/ha | Lee/Bu/Liu: dosis studi 2–48 t/ha; Liu 2022 menyarankan >20 t/ha untuk hasil maksimum. Plafon 10 dipilih agar manfaat tidak dilebih-lebihkan | Sedang |
| 4 | Peluruhan efek per musim `d` | **0,5** | 0,4–0,7 | fraksi/musim | Yu 2023 (efek umumnya tidak signifikan setelah 3 tahun); Koyama & Hayashi 2019 (efek sisa musim ke-2 melemah, saran aplikasi ulang tiap 1–3 tahun) | Rendah–sedang |
| 5 | Horizon musim `N` | **4** | 2–6 | musim (2 musim/tahun) | Idem #4 | Rendah–sedang |
| 6 | Hasil dasar `Y0` | **5,5** | 5,0–7,0 | t GKP/ha/musim | BPS: Jateng 2024 = 8,89 juta t GKG / ~1,55 juta ha ≈ 5,7 t GKG/ha; DIY 2024 (perkiraan) 454,27 ribu t GKG / 97,47 ribu ha ≈ 4,7 t GKG/ha. Konversi GKG→GKP ≈ ÷0,83–0,86 **[perlu verifikasi SKGB 2018]**. Default memakai angka DIY (lebih rendah) | Sedang. **Sebaiknya diganti dengan hasil riil petani** di aplikasi |
| 7 | Harga GKP `P_GKP` | **6.500** | 6.500–7.000 | Rp/kg | HPP GKP petani Rp6.500/kg (Kepbadan 2/2025 & 14/2025, berlaku 15 Jan 2025). Bapanas Juli 2026: rata-rata GKP ±Rp7.000/kg, HPP masih Rp6.500 | Tinggi (HPP); harga pasar berfluktuasi |
| 8 | Dosis urea `D_urea` | **250** | 200–300 | kg/ha/musim | Rekomendasi dalam uji Pratiwi dkk. 2021 (DIY): urea 266 kg/ha + SP36 125 + KCl 100. Praktik petani Jateng: urea 200 kg/ha + Phonska 300 kg/ha (studi Pucakwangi). Acuan resmi: Permentan 13/2022 (spesifik lokasi) | Sedang |
| 9 | Harga urea `P_urea` | **1.800** (subsidi) | 1.800–5.800+ | Rp/kg | HET subsidi turun 20% sejak 22 Okt 2025 (Kepmentan 1117/Kpts./SR.310/M/10/2025): urea Rp2.250 → Rp1.800, NPK Rp2.300 → Rp1.840. Nonsubsidi ±Rp5.800/kg (rujukan BPK Jateng 2023) **[perlu verifikasi harga 2026]** | Tinggi (subsidi); rendah (nonsubsidi) |
| 10 | Laju hemat urea `s_k` | **0,03** | 0,02–0,04 | fraksi per (t/ha) | Xu 2022 (90% N + 2,5 t/ha dan 80% N + 5 t/ha tetap ≥ hasil 100% N); NUE +12,04% (Liu 2022), +26,1% sawah (Yuan 2024); Pratiwi 2021 (5 t/ha + 50% urea CRF) | Rendah–sedang |
| 11 | Plafon hemat urea `s_max` | **0,15** | 0,10–0,20 | fraksi | Xu 2022 (pengurangan 20% N masih menaikkan hasil; pengurangan lebih besar menurunkan hasil) | Sedang |
| 12 | C organik biochar sekam `F_C` | **0,49** | 0,29–0,69 (±41%) | t C/t biochar | IPCC 2019 Refinement Vol.4 Ap.4, Tabel 4Ap.1 ("Rice husks and rice straw – Pyrolysis 0,49 ±41%"; gasifikasi 0,13). **Bisa diganti dengan hasil uji lab pabrik** | Sedang. Kadar abu silika sekam tinggi |
| 13 | Fraksi C stabil 100 th `F_perm` | **0,80** | 0,65–0,89 | fraksi | IPCC 2019 Tabel 4Ap.2: >600 °C 0,89 ±13%; 450–600 °C 0,80 ±11%; 350–450 °C 0,65 ±15%. **Pilih sesuai suhu reaktor pabrik** | Tinggi (metode); tergantung suhu proses |
| 14 | Faktor CO₂/C | **44/12 = 3,667** | — | t CO₂/t C | Stoikiometri | Pasti |
| 15 | Biaya tebar `c_s` | **100** | 50–250 | Rp/kg biochar | **[asumsi]** tenaga kerja ±1 HOK per 0,5–1 t biochar, termasuk angkut dari titik ambil. BPS: upah buruh tani nasional ±Rp58.760/hari (Sep 2022), DIY termasuk terendah | Rendah. Sebaiknya diisi dari survei lapangan |
| 16 | Harga karbon `P_C` | **0** (tidak dirupiahkan) | 0–? | Rp/t CO₂e | Petani belum punya akses pasar karbon. Hanya ditampilkan sebagai indikator | — |
| 17 | Perubahan CH₄/N₂O | **tidak dihitung** | CH₄: −28% s/d +14% (n.s.); N₂O: −25% s/d −41% | % | Bu 2022; Tran Sy 2021 (sekam 5–10 t/ha di Mekong: CH₄ −24,2 s/d −28,0%, N₂O −25,6 s/d −41,0%); Jeffery 2016; Iboko 2023 (tergantung dosis N) | Rendah, hasil tidak konsisten |
| 18 | Retensi air | **tidak dihitung** | — | — | Disebut di banyak tinjauan, tetapi tidak ditemukan angka kuantitatif yang terverifikasi untuk sawah tergenang | Rendah |

---

## 3. Rumus

Input: luas sawah `A` (ha), biochar diterima `B` (kg), hasil dasar `Y0` (opsional; default 5,5 t GKP/ha).

```
1) Dosis efektif
   r      = B / (A × 1000)                         [t/ha]
   r_eff  = min(r, r_cap)                          r_cap = 10

2) Respons hasil (kurva jenuh, diminishing returns)
   f(r)   = R_max × (1 − e^(−k × r_eff))           R_max = 0,10 ; k = 0,20

3) Manfaat musim pertama
   ΔY₁    = Y0 × A × f(r)                          [t GKP]
   Rp_Y₁  = ΔY₁ × 1000 × P_GKP                     [Rp]

   s(r)   = min(s_max, s_k × r_eff)                s_k = 0,03 ; s_max = 0,15
   Rp_F₁  = D_urea × A × s(r) × P_urea             [Rp]

4) Efek sisa beberapa musim (peluruhan geometrik)
   M      = Σ_{t=0}^{N−1} d^t = (1 − d^N)/(1 − d)  d = 0,5 ; N = 4  →  M = 1,875

5) Karbon tersimpan (dihitung sekali, tidak dikali M)
   CO2e   = (B/1000) × F_C × F_perm × 44/12        [t CO₂e]
          = (B/1000) × 0,49 × 0,80 × 3,667 ≈ 1,437 × (B/1000)

6) Manfaat bersih petani
   Bruto  = (Rp_Y₁ + Rp_F₁) × M
   Biaya  = B × c_s                                c_s = Rp100/kg
   Neto   = Bruto − Biaya  (+ CO2e × P_C, default P_C = 0)
```

**Pedoman tampilan di aplikasi:**
- Tampilkan **rentang**, bukan satu angka. Hitung skenario rendah (R_max 0,05; k 0,10; d 0,4; N 2) dan tinggi (R_max 0,16; k 0,35; d 0,7; N 6), dan pakai default sebagai nilai tengah.
- Tampilkan peringatan jika `r < 0,5 t/ha`: manfaat hasil sangat kecil, sarankan menumpuk jatah untuk lahan lebih sempit.
- Tampilkan peringatan jika `r > 10 t/ha`: biochar di atas batas ini tidak dihitung menambah manfaat.
- Hemat pupuk dan kenaikan hasil **boleh dijumlahkan** (Xu 2022 menunjukkan keduanya bisa terjadi bersamaan). Karena itu `s_k` dibuat kecil supaya tidak terjadi hitung ganda.
- Jika petani memasukkan hasil riilnya sendiri, `Y0` diganti dengan angka tersebut.

---

## 4. Contoh Hitung — 1 petani, 0,5 ha, 500 kg biochar

| Langkah | Perhitungan | Hasil |
|---|---|---|
| Dosis | 500 / (0,5 × 1000) | **1,0 t/ha** |
| f(r) | 0,10 × (1 − e^(−0,2)) = 0,10 × 0,1813 | **0,0181 (+1,81%)** |
| ΔY₁ | 5,5 × 0,5 × 0,0181 | **0,0499 t ≈ 50 kg GKP** |
| Rp_Y₁ | 49,9 kg × Rp6.500 | **Rp324.000** |
| s(r) | min(0,15; 0,03 × 1,0) | 0,03 |
| Rp_F₁ (subsidi) | 250 × 0,5 × 0,03 × Rp1.800 = 3,75 kg urea | **Rp6.750** (nonsubsidi Rp5.800: Rp21.750) |
| Musim-1 total | 324.000 + 6.750 | Rp330.750 |
| Faktor sisa M | (1 − 0,5⁴)/(1 − 0,5) | 1,875 |
| Bruto 4 musim | 330.750 × 1,875 | **Rp620.156** |
| Biaya tebar | 500 × Rp100 | Rp50.000 |
| **Neto (±2 tahun)** | 620.156 − 50.000 | **≈ Rp570.000** (≈ Rp285.000/tahun) |
| Karbon | 0,5 × 0,49 × 0,80 × 3,667 | **≈ 0,72 t CO₂e** (tidak dirupiahkan) |

Sensitivitas cepat untuk kasus yang sama:
- Skenario rendah (R_max 0,05; k 0,10; d 0,4; N 2): f = 0,48%; ΔY₁ ≈ 13 kg; M = 1,4; neto ≈ Rp80 ribu.
- Skenario tinggi (R_max 0,16; k 0,35; d 0,7; N 6): f = 4,7%; ΔY₁ ≈ 130 kg; M = 2,94; neto ≈ Rp2,45 juta.
- Jika 500 kg yang sama dipusatkan ke 0,1 ha (r = 5 t/ha), f naik menjadi 6,3% per luas, tetapi total ΔY₁ ≈ 35 kg GKP, jadi total manfaat malah lebih kecil. Karena kurvanya jenuh, **menyebar tipis ke lahan lebih luas memberi total manfaat lebih besar** menurut model ini. Namun di bawah ±0,5 t/ha bukti lapangan nyaris tidak ada. Rekomendasi praktis: dosis **1–2 t/ha**.

---

## 5. Keterbatasan

1. **Dosis jauh di bawah dosis riset.** Hampir semua angka meta-analisis berasal dari dosis 10–40 t/ha. Untuk 1–2 t/ha, nilai `f(r)` adalah **ekstrapolasi kurva jenuh [asumsi]**, bukan hasil uji langsung. Ini koefisien paling tidak pasti dan perlu demplot lokal di Sleman/Klaten.
2. **Biochar sekam termasuk tipe "struktur" (miskin hara).** Jeffery 2017 dan Liu 2022 menemukan respons terbesar pada biochar kaya hara (pupuk kandang, 500–600 °C). Biochar sekam murni kemungkinan memberi respons di bawah rata-rata, dan itulah alasan R_max diambil di batas bawah. Mengompos biochar bersama pupuk kandang kemungkinan meningkatkan respons (Wang 2019, co-composted biochar), tetapi tidak dimodelkan.
3. **Tanah.** Respons terbesar terjadi di tanah masam atau miskin hara (Jeffery 2017; Yu 2023). Sawah vulkanik Sleman/Klaten relatif subur dan mendekati netral, sehingga respons bisa lebih kecil dari rata-rata tropis.
4. **Uji Indonesia tidak signifikan atau berupa campuran.** Uji Lombok (Hadiawati 2019) mendapat 5,80 → 6,11 → 6,47 t/ha tetapi tidak signifikan. Uji UGM di Klaten (arang sekam + kompos) dan Pratiwi 2021 tidak melaporkan persentase kenaikan hasil biochar tunggal secara langsung.
5. **CH₄ bisa naik** bila dosis N tinggi (Iboko 2023: kombinasi biochar rendah + N rendah memberi CH₄ +114%). Karena itu manfaat GRK tidak dirupiahkan.
6. **Data harga dan hasil.** HPP 2026 dirujuk dari pernyataan Bapanas (Juli 2026), bukan regulasi baru. Harga urea nonsubsidi 2026, konversi GKG→GKP, dan produktivitas tingkat kabupaten (Sleman, Klaten) 2024 belum terverifikasi dari tabel BPS primer, karena situs BPS memblokir akses otomatis.
7. **Karbon.** F_C IPCC punya ketidakpastian ±41%. Klaim karbon formal memerlukan uji lab (C organik, H/Corg) dan suhu reaktor terdokumentasi. Angka CO₂e di aplikasi hanya **indikatif**, bukan kredit karbon.
8. Faktor peluruhan `d` dan horizon `N` didasarkan pada pernyataan kualitatif ("tidak signifikan setelah 3 tahun", "melemah di musim ke-2"), bukan model kuantitatif.

---

## 6. Daftar Pustaka (diakses 2026-10-11)

**Meta-analisis dan studi lapang (peer-reviewed)**
1. Liu Y, Li H, Hu T, dkk. (2022). A quantitative review of the effects of biochar application on rice yield and nitrogen use efficiency in paddy fields: A meta-analysis. *Sci. Total Environ.* 830:154792. https://doi.org/10.1016/j.scitotenv.2022.154792 — yield +10,73%, NUE +12,04%; disarankan >20 t/ha dan N 150–250 kg/ha.
2. Bu X, Nan Q, Li S, Bolan N, Sarkar B, Meng J, dkk. (2022). Meta-Analysis for Quantifying Carbon Sequestration and Greenhouse Gas Emission in Paddy Soils One Year after Biochar Application. *Agronomy* 12(12):3065. https://doi.org/10.3390/agronomy12123065 — C tanah +27,2%, hasil +11,3%, CH₄ +13,6% (n.s.), N₂O −25,1%.
3. Awad YM, Wang J, Igalavithana AD, Tsang DCW, Kim KH, Lee SS, Ok YS (2018). Biochar Effects on Rice Paddy: Meta-analysis. *Adv. Agron.* 148:1–32. https://doi.org/10.1016/bs.agron.2017.11.005 — hasil +16%, pH +11,8%, N₂O turun; terbaik 41–50 t/ha.
4. Jeffery S, Abalos D, Prodana M, Bastos AC, van Groenigen JW, Hungate BA, Verheijen F (2017). Biochar boosts tropical but not temperate crop yields. *Environ. Res. Lett.* 12:053001. https://doi.org/10.1088/1748-9326/aa67bd — tropis +25% (median dosis 15 t/ha).
5. Jeffery S, Verheijen FGA, Kammann C, Abalos D (2016). Biochar effects on methane emissions from soils: A meta-analysis. *Soil Biol. Biochem.* 101:251–258. https://doi.org/10.1016/j.soilbio.2016.07.021 — sawah tergenang Hedges' d = −0,87; tanah masam −1,56.
6. Yuan X, Gu X, Liang R, dkk. (2024). Comparing combined application of biochar and nitrogen fertilizer in paddy and upland soils. *Sci. Total Environ.* 933:173160. https://doi.org/10.1016/j.scitotenv.2024.173160 — NUE sawah +26,1%, serapan N +15,0%.
7. Yu BH, Ji JM, Wang LX, dkk. (2023). [Meta Analysis on Yield Effect of Biochar for Staple Crops in China]. *Huan Jing Ke Xue* 44(1):520–530. https://doi.org/10.13227/j.hjkx.202203102 — rata-rata +8,77%; padi mirip antar dosis; efek umumnya tidak signifikan setelah 3 tahun.
8. Zhu YH, Li S, Yin J, dkk. (2026). [Yield Response of Three Major Staple Crops to Biochar Application]. *Huan Jing Ke Xue* 47(1):543–552. https://doi.org/10.13227/j.hjkx.202412321 — padi +16,4%.
9. Iboko MP, Dossou-Yovo ER, Obalum SE, dkk. (2023). Paddy rice yield and greenhouse gas emissions: Any trade-off due to co-application of biochar and nitrogen fertilizer? A systematic review. *Heliyon* 9(11):e22132. https://doi.org/10.1016/j.heliyon.2023.e22132
10. Lee J, Jeong S, Gwon H, dkk. (2023). Effects of Biochar on Methane Emissions and Crop Yields in East Asian Paddy Fields: A Regional Scale Meta-Analysis. *Sustainability* 15(12):9200. https://doi.org/10.3390/su15129200
11. Xu B, Wang XL, Meng RX, dkk. (2022). Effects of Nitrogen Fertilizer Reduction Accompanied by Biochar Application on Yield and Nitrogen Accumulation of Rice. *Fujian J. Agric. Sci.* 37(12):1528–1535. https://doi.org/10.19303/j.issn.1008-0384.2022.012.003 — 80% N + 5 t/ha: hasil +10,22% vs 100% N.
12. Tran Sy N, Huynh Van T, Nguyen Huu C, dkk. (2021/2022). Rice husk and melaleuca biochar additions reduce soil CH₄ and N₂O emissions and increase soil physicochemical properties. *F1000Research* 10:1128. https://doi.org/10.12688/f1000research.74041.2
13. Koyama S, Hayashi H (2019). Effects of single and successive applications of rice husk charcoal on paddy soil carbon content and rice productivity during two cropping seasons. *Soil Sci. Plant Nutr.* https://doi.org/10.1080/00380768.2019.1579042 (abstrak dibaca melalui ringkasan sekunder; teks penuh tidak dapat diakses)
14. Pratiwi ES, Hanudin E, Purwanto BH, Sulistyaningsih E, Hayashi H (2021). Rice growth response to CRF fertilizer and biochar in rainfed land under two continuous seasons. *IOP Conf. Ser.: Earth Environ. Sci.* 752:012018. https://doi.org/10.1088/1755-1315/752/1/012018
15. Hadiawati L, Sugianti T, Triguna (2019). Rice-husk biochar for better yield of lowland rainfed rice in Lombok, Indonesia. *AIP Conf. Proc.* 2199:040001. https://doi.org/10.1063/1.5141288 (angka hasil dari ringkasan penerbit; teks penuh tidak dapat diakses)
16. Wang Y, Villamil MB, Davidson PC, Akdeniz N (2019). A quantitative understanding of the role of co-composted biochar in plant growth using meta-analysis. *Sci. Total Environ.* 685:741–752. https://doi.org/10.1016/j.scitotenv.2019.06.244

**Pedoman resmi dan data Indonesia**
17. IPCC (2019). 2019 Refinement to the 2006 IPCC Guidelines, Vol. 4, Ch. 2, Appendix 4: Method for estimating the change in mineral soil organic carbon stocks from biochar amendments. Tabel 4Ap.1 & 4Ap.2. https://www.ipcc-nggip.iges.or.jp/public/2019rf/pdf/4_Volume4/19R_V4_Ch02_Ap4_Biochar.pdf
18. BPS Provinsi Jawa Tengah (2025). Luas Panen dan Produksi Padi 2024 (Angka Tetap) — 8,89 juta t GKG; ±1,55 juta ha. https://jateng.bps.go.id/id/pressrelease/2025/03/03/1558/
19. BPS Provinsi DI Yogyakarta (2024). Luas Panen Padi DIY Tahun 2024 Menurun — perkiraan 97,47 ribu ha; 454,27 ribu t GKG. https://yogyakarta.bps.go.id/en/news/2024/11/05/290/luas-panen-padi-diy-tahun-2024-menurun.html
20. Bisnis.com (13 Jan 2025). HPP gabah naik menjadi Rp6.500/kg mulai 15 Januari (Kepbadan No. 2/2025). https://ekonomi.bisnis.com/read/20250113/12/1831012/ ; pencabutan rafaksi (Kepbadan 14/2025): https://ekonomi.bisnis.com/read/20250131/12/1835699/
21. Bisnis.com (16 Jul 2026). Indeks Harga Petani Padi Tembus Rekor — GKP ±Rp7.000/kg, HPP Rp6.500. https://ekonomi.bisnis.com/read/20260716/12/1988570/
22. Bisnis.com (31 Okt 2025). Daftar Harga Pupuk Subsidi Terbaru usai Pemerintah Pangkas HET 20% (Kepmentan 1117/Kpts./SR.310/M/10/2025). https://ekonomi.bisnis.com/read/20251031/99/1925023/ ; Republika (22 Okt 2025): https://ekonomi.republika.co.id/berita/t4ikai423/resmi-harga-pupuk-subsidi-turun-mulai-hari-ini
23. Permentan No. 13 Tahun 2022 tentang penggunaan dosis pupuk N, P, K untuk padi, jagung, kedelai pada lahan sawah. https://peraturan.go.id/files/bn745-2022.pdf
24. BPK Perwakilan Jawa Tengah (2023). Harga urea nonsubsidi ±Rp5.800/kg (rujukan sekunder). https://jateng.bpk.go.id/wp-content/uploads/2023/05/PDF-49.pdf
25. Republika (3 Okt 2022). Upah nominal harian buruh tani Rp58.760 (BPS). https://ekonomi.republika.co.id/berita/rj69o7383/
