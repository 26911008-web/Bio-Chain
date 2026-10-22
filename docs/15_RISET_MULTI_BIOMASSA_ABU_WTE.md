# 15 — Riset Multi-Biomassa, Abu Kembali ke Lahan & Waste-to-Energy (Jawa)

Tanggal: 11 Okt 2026 · Status: riset desain (bukan kode) · Cakupan: 9 pertanyaan riset untuk perluasan Bio-Chain menjadi *Multi-Biomass Circular Platform*.

## Cara membaca tingkat kepastian

Setiap angka diberi label:

- **[V]**: sudah dicek terhadap sumber (teks/abstrak/tabel) selama riset ini.
- **[L]**: nilai dari literatur yang dikenal luas dan dikutip dari ingatan peneliti. Rujukannya jelas, tetapi angkanya belum dibaca ulang di sesi ini. **Wajib diverifikasi sebelum dipakai sebagai konstanta produksi atau klaim audit.**
- **[D]**: usulan desain atau turunan hitungan. Bukan angka dari literatur.

Catatan jujur: banyak standar (ISO 17225-6, ISO 18125, Kepmentan 261/2019, PP 22/2021, Permen ESDM 12/2023) berbayar atau berupa PDF hasil pindai, sehingga teks lengkapnya tidak bisa dibaca di sesi ini. Angka yang hanya terkonfirmasi lewat sumber sekunder ditandai demikian.

---

## 1. Sifat bahan bakar biomassa (Jawa/Indonesia)

### 1a. Proksimat, nilai kalor, densitas

Basis: db = dry basis, ar = as received. LHV_db diturunkan dari HHV_db − 0,212·H_d (MJ/kg, H dalam %), dengan H ≈ 5–6 % db, sehingga **LHV_db ≈ HHV_db − 1,1 s/d 1,3 MJ/kg** [D, berdasar rumus ISO 18125, lihat §3].

| Biomassa | MC ar tipikal (%) | Ash db (%) | VM db (%) | FC db (%) | HHV_db (MJ/kg) | LHV_db (MJ/kg) | Bulk density (kg/m³, lepas) | S db (%) | Cl db (%) | Sumber |
|---|---|---|---|---|---|---|---|---|---|---|
| Sekam padi | 8–14 | 13–23 (umum 15–20) | 60–65 | 14–17 | 14,8–16,2 | **13,7–15,0** | 90–150 | 0,02–0,1 | 0,02–0,3 | [L] Jenkins dkk. 1998; Vassilev dkk. 2010; Phyllis2 |
| Tongkol jagung | 9–15 (pasca-pipil kering), bisa 20–30 saat panen basah | 1–3 (bisa 5–10 jika tercampur tanah) | 75–82 | 15–19 | 17,5–19,0 | **16,3–17,8** | 150–250 (utuh) | 0,02–0,1 | 0,05–0,3 | [L] Phyllis2; Vassilev 2010. Studi briket RI: MC 11 %, ash 9,8 %, VM 70 % [V, sekunder] |
| Ampas tebu (bagasse) | 45–55 keluar gilingan | 2–4 (bersih); 5–12 (tercampur tanah) | 78–86 | 10–15 | 18,0–19,5 | **16,8–18,2** | 80–160 | 0,02–0,1 | 0,01–0,1 | [L] Jenkins 1998; Vassilev 2010 |
| Tempurung kelapa | 8–12 (kering jemur) | 0,5–1,5 | 70–78 | 19–25 | 19,5–20,8 | **18,3–19,6** | 300–550 | 0,01–0,1 | 0,05–0,3 | [L] Phyllis2; VM 75,5 %, C 64,3 % [V, review T&F 2024, DOI 10.1080/23311916.2024.2307201] |
| Sabut/serat kelapa (coir) | 10–20 | 2–6 | 65–75 | 20–28 | 18,0–19,5 | **16,8–18,3** | 50–120 | 0,05–0,2 | **0,3–1,5 (tinggi)** | [L] Vassilev 2010; Phyllis2 (coconut husk/coir) |
| Serbuk gergaji sengon (*Falcataria moluccana*) | 30–55 segar dari sawmill, <15 setelah dikeringkan | 0,5–2 | 78–85 | 13–18 | 18,5–19,8 | **17,3–18,6** | 150–250 | <0,05 | <0,05 | [L] Phyllis2 (hardwood sawdust) |
| Serbuk kayu karet (*Hevea*) | 30–55 segar | 0,8–2,5 | 76–83 | 14–19 | 18,0–19,5 | **16,8–18,3** | 180–280 | <0,05 | <0,05 | [L] Phyllis2 |

Data lapangan PLN (penting untuk serbuk gergaji): pasokan serbuk gergaji ke PLTU Pelabuhan Ratu tercatat **MC 50–70 % dan 1.400–2.200 kcal/kg (5,9–9,2 MJ/kg ar)** [V, *J. Mat. Dev. Tech.* UGM, https://journal.ugm.ac.id/jmdt/article/download/114911/43179]. Asumsi "serbuk gergaji MC <12 %" **tidak realistis untuk bahan dari sawmill** tanpa pengering.

### 1b. Komposisi oksida abu (% massa abu)

| Oksida | Sekam padi | Tongkol jagung | Bagasse | Tempurung kelapa | Sabut kelapa | Kayu (sengon/karet, proxy hardwood) | Sumber |
|---|---|---|---|---|---|---|---|
| SiO₂ | **85–97** | 20–45 | 45–65 | 10–40 | 10–30 | 5–35 | [V] RHA XRF 90–97 % (Fernandes dkk. 2016, *Fuel* 165:351, doi:10.1016/j.fuel.2015.10.086); lainnya [L] Vassilev dkk. 2013 *Fuel* 105:40, doi:10.1016/j.fuel.2012.09.041 |
| K₂O | 1–5 | **25–45** | 3–12 | **20–45** | **25–40** | 5–20 | [L] Vassilev 2010/2013 |
| Na₂O | 0,1–1 | 0,5–3 | 0,5–2 | 1–10 | 2–15 | 0,5–3 | [L] |
| CaO | 0,5–3 | 2–10 | 2–8 | 3–15 | 2–10 | **20–45** | [L] |
| MgO | 0,2–1 | 2–8 | 1–5 | 2–8 | 2–6 | 3–10 | [L] |
| P₂O₅ | 0,3–1,5 | 3–10 | 1–5 | 1–5 | 1–4 | 1–5 | [L] |
| Fe₂O₃ | 0,1–0,5 | 0,5–3 | 2–15 (tanah) | 0,5–5 | 0,5–3 | 0,5–5 | [L] |
| Al₂O₃ | 0,1–1 | 0,5–5 | 5–18 (tanah) | 0,5–5 | 0,5–3 | 1–8 | [L] |

Catatan: Fe₂O₃ dan Al₂O₃ yang tinggi pada bagasse hampir selalu berasal dari kontaminasi tanah. Jenkins dkk. (1998) melaporkan bagasse dengan SiO₂ ≈ 47 %, Al₂O₃ ≈ 18 %, Fe₂O₃ ≈ 14 % [L]. Komposisi abu sangat bergantung pada lokasi, varietas, dan kebersihan bahan, jadi **platform wajib menyimpan hasil lab per lot, bukan memakai konstanta tetap**.

Rujukan utama tabel:
- Jenkins B.M., Baxter L.L., Miles T.R. Jr., Miles T.R. (1998). Combustion properties of biomass. *Fuel Processing Technology* 54:17–46. doi:10.1016/S0378-3820(97)00059-3 [L]
- Vassilev S.V. dkk. (2010). An overview of the chemical composition of biomass. *Fuel* 89(5):913–933. doi:10.1016/j.fuel.2009.10.022 [V: identitas]
- Vassilev S.V. dkk. (2013). An overview of the composition and application of biomass ash. Part 1. *Fuel* 105:40–76. doi:10.1016/j.fuel.2012.09.041 [L]
- TNO Phyllis2 database, https://phyllis.nl [L]

---

## 2. Indeks slagging/fouling

| Indeks | Rumus | Satuan | Ambang | Sumber |
|---|---|---|---|---|
| **Alkali Index (AI)** | AI = (kg K₂O + Na₂O dalam abu per kg bahan bakar) / HHV (GJ/kg). Dengan ash dan oksida dalam %: **AI = A_d[%] × (K₂O+Na₂O)[% abu] / (10 × HHV_d[MJ/kg])** (setara faktor 1/10⁴ ÷ HHV/1000) | kg/GJ (= g/MJ) | **0,17–0,34 slagging/fouling *probable*; >0,34 *certain*** | [V] Zhu dkk. 2014, *Front. Energy Res.* 2:7, doi:10.3389/fenrg.2014.00007 (Tabel 4); asal: Miles dkk. 1995/1996, NREL/TP-433-8142, doi:10.2172/251288 [V: identitas laporan, tahun cetak April 1995, rilis OSTI 1996] |
| Base/Acid (B/A) | (Fe₂O₃+CaO+MgO+Na₂O+K₂O)/(SiO₂+Al₂O₃+TiO₂) | – | <0,206 rendah; 0,206–0,4 sedang; >0,4 tinggi | [V] Zhu 2014 |
| Slagging index Rs | (B/A) × S_d (%) | – | <0,6 rendah; 0,6–2,0 sedang; 2,0–2,6 tinggi; >2,6 sangat tinggi | [V] Zhu 2014 |
| Fouling index Fu | (B/A) × (Na₂O+K₂O) (% abu) | – | <0,6 rendah; 0,6–40 tinggi; >40 sangat tinggi | [V] Zhu 2014 |
| Si/Al | SiO₂/Al₂O₃ | – | <1,87 rendah; 1,87–2,56 sedang; >2,56 tinggi | [V] Zhu 2014 |
| Slag viscosity G | SiO₂/(SiO₂+Fe₂O₃+CaO+MgO)×100 | – | 72–80 rendah; 65–72 sedang; 50–65 tinggi | [V] Zhu 2014 |
| Cl dalam bahan bakar | Cl (% ar) | % | <0,2 rendah; 0,2–0,3 sedang; 0,3–0,5 tinggi; >0,5 sangat tinggi | [V] Zhu 2014 |
| Molar 2S/Cl (korosi) | 2·(S/32)/(Cl/35,45) | mol/mol | <2 risiko korosi tinggi; >4 aman | [L] Salmenoja 2000; Garcia-Maraver dkk. 2017 |
| (K+Na)/(2S+Cl) dan Si/K (molar) | – | mol/mol | dipakai untuk aglomerasi bed FBC | [L] Lachman dkk. 2021 |

Contoh hitung AI [D], memakai nilai tengah tabel 1:
- Sekam padi: A = 18 %, alkali = 3 % → AI = 18×3/(10×15,5) = **0,35 kg/GJ** (secara formal "certain").
- Tongkol jagung: A = 2 %, alkali = 40 % → AI = 80/(10×18,5) = **0,43 kg/GJ** (tinggi meskipun abunya sedikit).
- Bagasse: A = 3 %, alkali = 6 % → AI ≈ **0,10** (rendah).
- Tempurung kelapa: A = 1 %, alkali = 40 % → AI ≈ **0,20** (probable).
- Kayu: A = 1 %, alkali = 12 % → AI ≈ **0,06**.

**Aditivitas untuk campuran [D, turunan aljabar]:**
- AI **tidak** aditif terhadap fraksi massa. Yang aditif adalah pembilang (kg alkali/kg) dan penyebut (GJ/kg) secara terpisah: AI_blend = Σxᵢ·Aᵢ·alkᵢ/10⁴ ÷ Σxᵢ·HHVᵢ/1000. Batasan AI ≤ AI_max bisa ditulis **linear** untuk LP: Σxᵢ·(Aᵢ·alkᵢ/10⁴ − AI_max·HHVᵢ/1000) ≤ 0.
- Indeks rasio (B/A, Si/Al, G, Fu) **tidak aditif**. Hitung dulu komposisi oksida abu campuran yang dibobot massa abu (oksida_j,blend = Σxᵢ·Aᵢ·oksida_ij / Σxᵢ·Aᵢ), lalu hitung indeksnya. Untuk LP, rasio dapat dilinearkan dengan cara serupa (pembilang − batas×penyebut ≤ 0).
- Interaksi kimia campuran (misalnya K dari tongkol jagung bereaksi dengan Si dari sekam membentuk K-silikat bertitik leleh rendah) **tidak tertangkap** oleh rata-rata linear apa pun.

**Kritik keandalan [V/L]:**
- Zhu dkk. (2014) menyatakan indeks-indeks ini berasal dari kriteria fusi abu **batu bara** dan tidak andal memprediksi slagging biomassa [V].
- Garcia-Maraver A. dkk. (2017). Critical review of predictive coefficients for biomass ash deposition tendency. *J. Energy Institute* 90(2):214–228, doi:10.1016/j.joei.2016.02.002 [L]: indeks empiris sering saling bertentangan untuk biomassa.
- Lachman J., Baláš M., Lisý M. dkk. (2021). An overview of slagging and fouling indicators and their applicability to biomass fuels. *Fuel Processing Technology* 217:106804, doi:10.1016/j.fuproc.2021.106804 [L, identitas via repositori VUT]: merekomendasikan indikator berbasis molar (Si/K, (K+Na)/(2S+Cl)) dan uji AFT dibanding B/A klasik.
- **Sekam padi:** AI formal "certain", tetapi K₂O-nya rendah dan SiO₂-nya sangat tinggi, sehingga abu cenderung tetap padat (titik leleh tinggi). Masalah utamanya volume abu, erosi, dan **kristalisasi silika (kristobalit) di atas ~800 °C**, bukan slagging klasik [L, Fernandes 2016]. B/A sekam ≈ 0,05 (rendah), bertentangan dengan AI. Ini contoh nyata ketidaksepakatan indeks.
- **AFT (ash fusion temperature, ISO 21404:2020)**: IDT/ST/HT/FT diukur langsung. Hasil ini lebih relevan daripada indeks hitung untuk keputusan desain tungku [L]. Rekomendasi: AFT wajib per pemasok baru atau per perubahan musim.

---

## 3. Konversi LHV as-received

| Item | Nilai | Sumber |
|---|---|---|
| Rumus ISO 18125:2017 (dalam J/g, M dalam %) | q_p,net,ar = [q_v,gr,d − 212,2·H_d − 0,8·(O_d + N_d)] × (1 − 0,01·M_ar) − 24,43·M_ar | [L] ISO 18125:2017 klausul perhitungan & Annex E. Teks berbayar; ruang lingkup dan Annex E [V] lewat pratinjau ANSI |
| Bentuk sederhana (MJ/kg, MC fraksi) | **LHV_ar = LHV_db × (1 − MC) − 2,443 × MC** | [D, setara aljabar] |
| Konstanta 2,443 vs 2,442 | ISO memakai **24,43 J/g per % air = 2,443 MJ/kg air** (entalpi penguapan air pada 25 °C, tekanan konstan, ≈ 44,01 kJ/mol ÷ 18,015 g/mol). Tabel uap memberi 2.441,7–2.442,3 kJ/kg. Selisihnya <0,05 %, jadi **pakai 2,443 agar konsisten dengan ISO 18125/ISO 16559** | [L] |
| Catatan | "LHV_db" harus berarti q_p,net,d (sudah dikoreksi H), bukan HHV. Mengalikan HHV dengan (1−MC) tanpa koreksi H menaksir terlalu tinggi sekitar 1,1–1,3 MJ/kg | [D] |

Contoh [D]: bagasse LHV_db 17,5, MC 0,50 → 17,5×0,5 − 2,443×0,5 = **7,53 MJ/kg ar**.

---

## 4. Efisiensi listrik biomassa & faktor emisi grid JAMALI

| Teknologi | Skala | Efisiensi listrik neto | Sumber |
|---|---|---|---|
| Stoker/grate + turbin uap kecil | 1–10 MWe | **15–25 %** (≤5 MWe cenderung 15–20 %) | [L] IRENA 2012, *Biomass for Power Generation* (RE Technologies Cost Analysis), https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2012/RE_Technologies_Cost_Analysis-BIOMASS.pdf; ERIA 2019 Ch.5: efisiensi termal PLTBm 20–30 % [V] https://www.eria.org/uploads/media/12_RPR_FY2018_09_Chapter_5.pdf |
| Gasifier + mesin gas | 0,1–2 MWe | **20–28 %** (tar dan MC umpan <15–20 % kritis) | [L] IRENA 2012; IEA Bioenergy Task 33 |
| ORC (dengan boiler oli termal) | 0,2–2 MWe | **15–20 %** (efisiensi CHP total 80–85 % bila panas dipakai) | [L] Obernberger dkk. (2002/2003), IEA Bioenergy / *Euroheat & Power* |
| Co-firing di PLTU | ratusan MWe | **36–44 %** (bergantung teknologi, ukuran, kualitas, porsi biomassa) | [V] IRENA-ETSAP Tech Brief E21 *Biomass Co-firing* (2013), https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2013/IRENA-ETSAP-Tech-Brief-E21-Biomass-Co-firing.pdf |
| Biaya modal (USD 2010) | – | stoker USD 1.880–4.260/kW; CFB 2.170–4.500/kW; gasifikasi 2.140–5.700/kW | [V] IRENA 2012 |

**Faktor emisi grid JAMALI:**

| Parameter | Nilai | Status | Sumber |
|---|---|---|---|
| EF grid JAMALI (combined margin, data 2019) | **0,87 tCO₂/MWh** | Nilai resmi terbaru yang bisa dikonfirmasi. Masih dipakai di dokumen aksi mitigasi SRN dengan proyeksi sampai 2024 | [V] Kepmen ESDM No. 163.K/HK.02/MEM.S/2021 (penetapan faktor emisi GRK sistem ketenagalistrikan, data inventarisasi DJK 2019). Dikutip di DRAM SRN-PPI (Add-On PLTGU Grati Blok 2): "EFgrid,y 0,87 tCO₂/MWh", https://asset.srnmenlh.id/srn-menlhk/files/3ff4297a-0300-4efd-9572-9eca8eb4ba30.pdf |
| Aturan pemilihan | nilai terendah antara ex-post dan ex-ante; metode CDM "Tool to calculate the emission factor for an electricity system" | [V] | Metodologi Gatrik ESDM, https://gatrik.esdm.go.id/assets/uploads/download_index/files/6a68f-2.-metodologi-pengoperasian-pembangkit-listrik-tenaga-bayu-pltb-yang-terhubung-ke-sistem-interkoneksi-tenaga-listrik-on-grid-.pdf |
| Rincian OM/BM terpisah JAMALI | **tidak ditemukan** di sumber terbuka sesi ini | – | Perlu unduh lampiran Kepmen 163.K/2021 dari JDIH ESDM |
| Nilai lain yang beredar | 0,79 tCO₂/MWh (data 2018, dikutip laporan keberlanjutan) | sekunder | PTSI SR 2023 hlm. 165 |
| **Jangan tertukar** | 0,911–1,297 tCO₂e/MWh adalah batas atas emisi (PTBAE) PLTU per Permen ESDM 16/2022, **bukan** EF grid | [V] | listrikindonesia.com |

Rekomendasi: simpan EF grid sebagai parameter bertanggal (`ef_grid_jamali = 0.87`, `source = "Kepmen ESDM 163.K/2021, data 2019"`) sehingga mudah diganti ketika ESDM menerbitkan pemutakhiran.

---

## 5. Kriteria pemilihan rute teknologi

| Kriteria | Pembakaran langsung (grate/stoker) | Co-firing PLTU (PC/CFB) | Gasifikasi (downdraft + mesin) | Pirolisis lambat (biochar/bio-silika) | Sumber |
|---|---|---|---|---|---|
| MC umpan | ≤50–55 % (grate toleran); optimal <35 % | woodchip TM ≤25 %, sawdust TM ≤45 % (spesifikasi Teluk Sirih); PLTU yang memakai TM <50 % berkinerja lebih baik | **<15–20 %** | **<15–20 %** (pengeringan internal makan energi) | [V] IGES 2025 / PT Indonesia Power Teluk Sirih; [V] UGM JMDT; [L] Basu 2018 *Biomass Gasification, Pyrolysis and Torrefaction* (3rd ed.) |
| Ash | toleran sampai ~20 % (grate bergerak) | prefer <5–10 %; abu tinggi menambah beban ESP dan FABA | **<5–6 %** untuk downdraft (risiko clinker, bridging) | toleran; abu tinggi menurunkan C biochar tetapi sekam cocok untuk bio-silika | [L] Basu 2018; Reed & Das 1988 |
| Alkali (AI) | <0,34 kg/GJ atau gunakan aditif/campuran | AI rendah lebih aman; porsi co-firing kecil (1–5 %) mengencerkan risiko | sensitif aglomerasi | tidak kritis (suhu 400–650 °C) | [V] Zhu 2014 |
| Cl | <0,2–0,3 % (korosi superheater) | <0,1–0,2 % disukai | <0,3 % | tidak kritis, tetapi Cl tertahan di biochar | [V] Zhu 2014 |
| Ukuran partikel | 5–50 mm | PC: perlu <1–3 mm (ikut ditumbuk di mill batu bara); CFB: 2,6–16 mm (Teluk Sirih) | 20–80 mm, fines <10 % (sekam lepas tidak cocok untuk downdraft tanpa pelet) | 2–20 mm (sekam langsung cocok untuk kiln/retort kontinu) | [V] Teluk Sirih; [L] Basu 2018 |
| Skala tipikal | 50–300 t/hari (1–10 MWe) | ≥10 t/hari per PLTU (porsi 1–5 % massa) | 2–25 t/hari (0,1–1 MWe) | 1–50 t/hari | [L] |
| Nilai kalor (PLN) | – | woodchip GCV 3.009–3.487 kcal/kg ar; sawdust ≥3.009 kcal/kg | – | – | [V] Teluk Sirih |

**Regulasi co-firing:** Permen ESDM No. 12/2023 tentang Pemanfaatan Bahan Bakar Biomassa sebagai Campuran Bahan Bakar pada PLTU (ditetapkan 27 Nov 2023, diundangkan 30 Nov 2023). Harga patokan tertinggi = harga batu bara × koefisien k (**≤1,2**) × faktor koreksi nilai kalor Fc (= kalori biomassa / kalori rata-rata batu bara). Target co-firing 2024 sebesar 2,83 juta t, 2025 sebesar 10,20 juta t [V, Bisnis.com 10 Des 2023; pasal.id]. **Batas spesifikasi teknis (MC, ash) dalam Permen 12/2023 tidak berhasil dikonfirmasi** dari sumber terbuka. Spesifikasi praktis ditentukan kontrak per PLTU (contoh Teluk Sirih di atas).

Rumus Fc menyiratkan bahwa **harga biomassa ditentukan oleh nilai kalor ar**. Karena itu, mengirim sekam/serbuk basah langsung merugikan pemasok. Ini argumen kuat untuk refraksi berbasis kadar air (§7).

---

## 6. Pengembalian abu ke lahan

### 6a. Batas logam berat pupuk organik (Kepmentan 261/KPTS/SR.310/M/4/2019)

| Logam | Batas maks (mg/kg) | Sumber |
|---|---|---|
| As | **10** | [V, sekunder] tabel pembanding di PMC9671718 (Tabel 4); konsisten dengan RSNI3 7763:2024 (https://bsn.go.id/uploads/attachment/rsni3_7763_2024_siap_jp.pdf) |
| Hg | **1** | idem |
| Pb | **50** | idem |
| Cd | **2** | idem |
| Cr | **180** | idem |
| Ni | **50** | idem |

Kepmentan 261/2019 juga mengatur **pembenah tanah** (organik dan anorganik) dengan tabel tersendiri. Abu biomassa lebih tepat diposisikan sebagai **pembenah tanah anorganik** atau bahan baku pupuk K/Si, bukan pupuk organik (C-organik abu rendah). Batas untuk kategori pembenah tanah anorganik **belum terverifikasi**. Cek lampiran asli di JDIH Kementan sebelum klaim pemasaran.

### 6b. Status hukum abu boiler biomassa (PP 22/2021)

| Fakta | Status | Sumber |
|---|---|---|
| Fly ash (N106) dan bottom ash (N107) dari **pembakaran batu bara di PLTU** (teknologi selain stoker/tungku industri) = **limbah non-B3 terdaftar**, Lampiran XIV | [V] | detik.com (penjelasan KLHK, 2021); Info Singkat DPR P3DI April 2021 |
| FABA batu bara dari **stoker boiler dan/atau tungku industri** tetap B3: fly ash **B409**, bottom ash **B410** | [V] | idem |
| Abu dari pembakaran **100 % biomassa** | **Tidak ditemukan entri eksplisit** dalam sumber yang bisa diakses. Entri B409/B410/N106/N107 menyebut batu bara | ketidakpastian |
| Implikasi | Abu biomassa murni **tidak otomatis B3**, tetapi juga tidak otomatis "non-B3 terdaftar". Penghasil wajib menetapkan karakteristik (uji TCLP/LD50/sifat B3 sesuai Lampiran PP 22/2021 dan Permen LHK 6/2021) atau berkonsultasi dengan DLH. **Abu co-firing (campuran batu bara) di PLTU ikut status FABA batu bara** | [D] |

### 6c. Agronomi

| Temuan | Nilai | Sumber |
|---|---|---|
| RHA + K pada padi (Myanmar, MH 2022–23 dan MH 2023) | RHA 5 dan 10 t/ha + 46 kg K/ha. Hasil tertinggi pada 10 t/ha RHA + 46 kg K/ha. Rekomendasi: K 46 kg/ha + RHA (mengurangi separuh dosis K 92 kg/ha) | [V] Yezin Agricultural Univ., core.ac.uk/outputs/618327733 |
| Sawah Indonesia: RHA vs digestat sekam (RHD) | hasil gabah 5,05–5,80 t/ha (RHA), 6,17–6,96 t/ha (RHD) vs kontrol 2,35–2,8 t/ha, 2 musim | [V] *Applied and Environmental Soil Science* (Jan 2024), doaj.org/article/576a463b7ad747acba2f2870e974f6b5 |
| Si untuk padi (tanah laterit ber-Fe tinggi, India) | RHA 125–250 kg/ha + silika halus 50 kg/ha → 6,14 t/ha | [V] Sandhya, krishikosh / ISSS India |
| Biochar sekam pot | 5 t/ha menaikkan hasil; 10 t/ha bisa menurunkan hasil (imobilisasi N) | [V, sekunder ringkasan pencarian] |
| Nilai pengapuran | Abu kayu: CCE ≈ 30–90 % CaCO₃-eq (kaya CaO). **Abu sekam: CCE rendah (<10–15 %)** karena CaO <3 %. Bukan kapur pengganti | [L] Vance 1996 *J. Environ. Qual.* 25:937; Pitman 2006 *Forestry* 79:563 |
| Ketersediaan Si | Silika **amorf** (pembakaran <700 °C) larut dan tersedia bagi tanaman. **Kristobalit** (>800–900 °C) hampir inert dan berbahaya bagi pernapasan (silika kristalin) | [L] Fernandes 2016; Della dkk. 2002 |
| Kalium | abu tongkol jagung/sabut/tempurung kaya K₂O (20–45 % abu) sehingga bernilai sebagai pupuk K. Abu sekam miskin K | [L] Vassilev 2013 |

---

## 7. Refraksi harga pengepul (kadar air & kotoran)

| Item | Nilai/praktik | Sumber |
|---|---|---|
| Analog resmi terdekat (gabah, bukan sekam) | HPP GKP Rp6.500/kg untuk KA ≤25 % dan hampa ≤10 %. Rafaksi: KA 26–30 %, hampa 11–15 % → Rp5.750/kg (Kepbadan Bapanas 2/2025 jo. 14/2025) | [V] IDXChannel; Detik; CNBC Indonesia (Jan 2025) |
| Standar refraksi sekam/tongkol jagung | **Tidak ada standar nasional** yang ditemukan. Praktik pasar: harga per karung/truk dengan potongan subjektif | [V: ketiadaan bukti di pencarian] |
| Referensi kadar air yang masuk akal | sekam 12 %; tongkol jagung 15 %; serbuk gergaji 30 % (bahan sawmill) atau 15 % (kering); bagasse 50 % | [D] selaras dengan rentang tabel §1 |

**Formula usulan [D]:** berat setara pada MC referensi, dengan potongan kontaminan.

```
W_bayar = W_timbang × (1 − f_kontam) × (1 − MC_aktual) / (1 − MC_ref)
```

- f_kontam = fraksi tanah/batu/plastik dari uji ayak sampel (misalnya ayakan 3 mm + sortir manual). Toleransi bebas (misalnya ≤2 %) boleh diberikan, lalu potong penuh di atasnya.
- Bonus tidak diberikan bila MC_aktual < MC_ref (opsional), untuk mencegah klaim alat ukur yang salah.
- Ukur MC dengan moisture meter yang dikalibrasi terhadap oven 105 °C (ISO 18134-2). Simpan foto layar alat dan geotag. Fitur offline GPS proyek ini sudah mendukung hal tersebut.
- Alternatif yang lebih adil untuk tujuan energi: bayar per **GJ ar** = W × LHV_ar (§3). Pendekatan ini sejalan dengan logika Fc pada Permen ESDM 12/2023.

---

## 8. Konsumsi energi spesifik (SEC/IKE) & pemantauan anomali

| Proses | SEC tipikal | Sumber |
|---|---|---|
| Hammer mill, residu herba MC ~10 %, saringan 3,2 mm | **22–35 kWh/t** (switchgrass/miscanthus 22; jerami/stover 32–35) | [V] Naimi & Sokhansanj 2018 (dikutip dalam review PMC6466356) |
| Hammer mill, saringan 6,4 mm | **13–20 kWh/t** | [V] idem |
| Hammer mill, rentang umum | 5–60 kWh/t | [V] review PMC6466356 |
| Pengaruh MC | Douglas-fir: saringan 3,18 mm 345 kJ/kg (≈96 kWh/t), SEC naik tajam saat MC 11 % → 17 % | [V] Liu dkk. 2016 (USDA FS Treesearch 53502) |
| Pengaruh MC + saringan | poplar 28 dan corn stover 22 kWh/t-dry pada MC 7 % dan saringan 5 mm; naik ~10× pada MC tinggi + saringan kecil | [V] Gil dkk. 2013 |
| Bagasse | 11 kJ/kg (MC rendah, saringan besar) s/d 750 kJ/kg (MC tinggi, saringan kecil, kecepatan tinggi) | [V] Kakolaki dkk. 2019, *CIGR Journal* |
| Pelletizer | 30–60 kWh/t (listrik) | [L] Thek & Obernberger 2004, *Biomass & Bioenergy* 27:671 |
| Pabrik pelet total (listrik) | 100–150 kWh/t pelet | [L] Thek & Obernberger 2004 |
| Pengering rotary/belt (termal) | 2,9–4,0 MJ per kg air diuapkan (≈ 0,8–1,1 kWh_th/kg air) | [L] Thek & Obernberger 2004; Basu 2018 |
| Pirolisis lambat kontinu (listrik bantu) | 50–150 kWh/t umpan (sangat bergantung desain) | [L, ketidakpastian tinggi] |

**ISO 50001/50006:**
- ISO 50006:2023 (edisi ke-2) mengatur EnPI dan Energy Baseline (EnB). Ada dua jenis faktor: *relevant variables* (produksi, cuaca, MC umpan) yang dinormalisasi secara rutin, dan *static factors* yang memerlukan penyesuaian non-rutin. Klausul 5.6.5 membahas outlier [V] (pratinjau ANSI/iTeh ISO 50006:2023).
- Model baseline regresi: **E = a + b·P (+ c·MC_umpan)**. EnPI = E_aktual / E_model [V, pola contoh DOE EnPI v4.0, https://www.energy.gov/eere/amo/articles/enpi-v40-tool-algorithm].
- Untuk hammer mill, MC umpan dan ukuran saringan **harus menjadi relevant variable**, karena keduanya pendorong utama SEC (lihat tabel).

**Deteksi anomali [L]:**
- Shewhart/moving average ±2σ (peringatan) dan ±3σ (aksi) pada residual model regresi, bukan pada energi mentah. Rujukan: Montgomery, *Introduction to Statistical Quality Control* (8th ed., 2019).
- **CUSUM** dari residual (Page 1954, *Biometrika* 41:100–115) mendeteksi pergeseran kecil dan persisten, misalnya pisau hammer mill aus atau die pelet aus. CUSUM untuk *monitoring & targeting* energi dipakai dalam panduan Carbon Trust (CTG008) [L]; slide Siemens EM Webinar 7 menyebut "cumulative deviation" untuk degradasi efisiensi [V].
- Rekomendasi [D]: residual = SEC_aktual − SEC_model(P, MC). Alarm bila |residual| > 2σ selama 3 dari 5 batch berturut-turut, atau bila CUSUM melewati h = 4–5σ (k = 0,5σ).

---

## 9. Least-cost blending & standar pelet

### 9a. Formulasi LP/MILP

| Item | Isi | Sumber |
|---|---|---|
| MILP least-cost blend dengan spesifikasi ash | Studi kasus Kansas: menambah batasan ash menaikkan biaya delivered sekitar **12 %** | [V] OSTI DOE PAGES 1476911, https://www.osti.gov/pages/biblio/1476911 |
| Pelet rendah-Cl dari campuran | maks 16,70 % jerami padi (hidrotermal), 1,50 % limbah RS, 4,76 % residu plastik dengan serbuk fir untuk memenuhi Cl | [V] *Energies* 2019, 12(22):4390 |
| Blending pelet (eksperimen) | 30 % OPT + 70 % *A. mangium*: ash 2,1 → 2,0 %, NCV 17,4 → 18,4 MJ/kg | [V] *J. Chem. Eng. Ind. Biotech.* UMP (2024/25) |

**Formulasi usulan [D]** (xᵢ = fraksi massa db, cᵢ = biaya delivered per t db, termasuk logistik dari modul OR-Tools yang sudah ada):

```
min  Σ cᵢ·xᵢ
s.t. Σ xᵢ = 1,   0 ≤ xᵢ ≤ stokᵢ/D
     Σ xᵢ·(LHV_dᵢ − LHV_min) ≥ 0
     Σ xᵢ·(Aᵢ − A_max) ≤ 0
     Σ xᵢ·(Clᵢ − Cl_max) ≤ 0 ;  Σ xᵢ·(Sᵢ − S_max) ≤ 0 ;  Σ xᵢ·(Nᵢ − N_max) ≤ 0
     Σ xᵢ·(Aᵢ·alkᵢ/10⁴ − AI_max·HHVᵢ/1000) ≤ 0
     (MILP) yᵢ ∈ {0,1}, xᵢ ≤ yᵢ, xᵢ ≥ x_minᵢ·yᵢ, Σ yᵢ ≤ K_maks_bahan
```

MC ditangani dengan mengonversi ke basis ar: LHV_ar campuran = Σ massa ar·LHV_arᵢ / Σ massa ar. Pendekatan alternatif: optimasi per basis db, lalu cek MC campuran sebagai batasan linear Σ wᵢ·(MCᵢ − MC_max) ≤ 0 dengan wᵢ = massa ar.

Sifat yang bukan rata-rata linear (AFT, durabilitas pelet) **tidak bisa** dimodelkan dengan andal. Gunakan sebagai pembatas porsi empiris (misalnya sekam ≤30 % untuk durabilitas) dan verifikasi lab.

### 9b. Standar pelet

| Parameter | ISO 17225-6 kelas A | ISO 17225-6 kelas B | ENplus A1 (kayu, ISO 17225-2) | Sumber |
|---|---|---|---|---|
| Ruang lingkup | pelet non-kayu (herba, buah, akuatik, campuran) | idem | **hanya kayu** | [V] ISO 17225-6:2021 klausul 1 |
| MC ar | ≤12 % | ≤15 % | ≤10 % | [L] |
| Ash db | **≤6 %** | **≤10 %** | ≤0,7 % | [L] |
| NCV ar (Q) | ≥14,5 MJ/kg | ≥14,5 MJ/kg | ≥16,5 MJ/kg | [L] |
| N db | ≤1,5 % | ≤2,0 % | ≤0,3 % | [L] |
| S db | ≤0,20 % | ≤0,30 % | ≤0,04 % | [L] |
| Cl db | ≤0,10 % | ≤0,30 % (edisi 2014; **diubah pada 2021**) | ≤0,02 % | [L]; perubahan Cl dan As kelas B [V] di kata pengantar ISO 17225-6:2021 |
| Durabilitas DU | ≥97,5 % | ≥96,0 % | ≥98,0 % | [L] |
| Perilaku leleh abu | informatif (baru di 2021) | idem | – | [V] |

Implikasi: pelet sekam murni (ash 15–20 %) **tidak memenuhi** ISO 17225-6 kelas B sekalipun. Agar ash ≤10 %, sekam harus dicampur dengan bahan rendah abu (serbuk kayu, tempurung) hingga porsi sekam ≲45–55 %. ENplus tidak relevan untuk pelet campuran non-kayu.

---

## Koreksi terhadap baseline pengguna

| Baseline pengguna | Penilaian | Koreksi usulan |
|---|---|---|
| Sekam: MC 12–14 % | wajar (kering dari RMU 8–14 %) | 10–14 % |
| Sekam: ash 15–20 % | wajar (literatur 13–23 %) | pertahankan, tetapi ukur per lot |
| **Sekam: LHV_db ~15,5** | **terlalu tinggi**. 15,5 lebih mendekati HHV_db | **LHV_db ≈ 14,0–14,8** (HHV_db 15–16) |
| Sekam: SiO₂ >90 % abu | wajar untuk RHA bersih (85–97 %) | ">85 %", karena kontaminasi tanah menurunkannya |
| Tongkol jagung: MC 12–15 % | wajar untuk tongkol kering pasca-pipil. Saat panen hujan bisa 20–30 % | tambahkan kondisi musim hujan |
| Tongkol jagung: ash 1,5–3 % | wajar untuk bahan bersih. Studi RI mencatat 9,8 % (kontaminasi) | 1,5–3 % bersih; tandai >5 % sebagai kotor |
| Tongkol jagung: LHV_db ~17,5 | sedikit tinggi | **16,5–17,5** |
| Tongkol jagung: VM >75 % | wajar (75–82 %) | – |
| **Tongkol jagung (tidak disebut)** | **AI tinggi (~0,4 kg/GJ) karena K₂O 25–45 % abu** | tambahkan peringatan alkali |
| Bagasse: MC 48–52 % | wajar | – |
| Bagasse: ash 2–4 % | wajar untuk bagasse bersih | sampai 10 % bila tercampur tanah |
| **Bagasse: LHV_db ~18,0** | **sedikit tinggi** (HHV_db 18–19,5) | **≈17,0–17,5** |
| **Kelapa "shell/fiber" digabung** | **keliru digabung**. Sabut punya ash 2–6 % dan **Cl 0,3–1,5 %** | pisahkan tempurung dan sabut |
| **Tempurung: LHV_db 19,5–20,5** | angka ini adalah **HHV_db** | **LHV_db ≈ 18,3–19,5** |
| Tempurung: FC >20 % | wajar (19–25 %) | – |
| Tempurung: ash <3 % | wajar (0,5–1,5 %) | – |
| **Serbuk gergaji: MC <12 %** | **tidak realistis** untuk serbuk sawmill (30–55 %; data PLN 50–70 %) | MC 30–55 % segar; <12 % hanya setelah pengering |
| Serbuk gergaji: ash <1,5 % | wajar untuk sengon. Kayu karet bisa sampai 2,5 % | <2,5 % |
| Serbuk gergaji: LHV_db ~18,5 | batas atas | **17,3–18,3** |
| AI tanpa faktor 1/10⁴ | rumus harus memakai faktor 1/10⁴ dan HHV dalam GJ/kg | AI = A%·alk%/(10·HHV_MJ/kg) |
| Konstanta 2,442/2,443 | – | **2,443 MJ/kg** (ISO 18125) |

---

## Rekomendasi desain

1. **Tabel `biomass_type` + `lab_result` per lot.** Nilai default (tabel §1) hanya dipakai sebagai *prior*. Kalkulasi energi, karbon, dan harga memakai hasil lab terakhir bila tersedia, dan wajib menyimpan basis (db/ar) secara eksplisit di setiap kolom.
2. **Satu fungsi konversi** `lhv_ar(lhv_db, mc)` = lhv_db·(1−mc) − 2,443·mc. Tolak input `mc > 1` (validasi persen vs fraksi). Bila hanya HHV yang tersedia: lhv_d = hhv_d − 0,2122·H_d − 0,0008·(O_d+N_d) (MJ/kg).
3. **Indeks abu sebagai *flag*, bukan keputusan.** Hitung AI, B/A, Rs, Fu, Si/Al, Cl, dan 2S/Cl. Tampilkan dengan label ketidakpastian. Untuk sekam, tampilkan catatan "AI formal tinggi, tetapi risiko utama volume abu dan silika kristalin". Wajibkan AFT (ISO 21404) untuk pemasok baru.
4. **Campuran:** hitung indeks dari komposisi oksida campuran yang dibobot abu (bukan rata-rata indeks). Batasan AI, LHV, ash, Cl, S, dan N dimasukkan ke LP dalam bentuk linear (§9a). OR-Tools (GLOP/CP-SAT) yang sudah ada di proyek dapat dipakai langsung.
5. **Router teknologi** berbasis aturan (§5): MC, ash, AI, Cl, ukuran partikel, dan t/hari menghasilkan rekomendasi + alasan. Contoh aturan: MC >20 % menyingkirkan gasifikasi dan pirolisis tanpa pengering; ash >6 % menyingkirkan downdraft; sekam dengan target bio-silika memerlukan suhu ≤700 °C.
6. **Refraksi pengepul:** terapkan formula berat setara MC_ref + potongan kontaminan (§7). Simpan bukti foto alat ukur dan geotag. Sediakan opsi harga per GJ ar untuk pembeli energi/PLTU.
7. **Abu ke lahan:** gerbang kepatuhan berupa uji logam berat per batch (As ≤10, Hg ≤1, Pb ≤50, Cd ≤2, Cr ≤180, Ni ≤50 mg/kg, rujukan sementara Kepmentan 261/2019) dan bukti karakterisasi non-B3. Abu co-firing batu bara diperlakukan sebagai FABA. Label produk: "pembenah tanah / sumber K-Si", bukan "kapur" untuk abu sekam.
8. **Grid EF bertanggal:** 0,87 tCO₂/MWh (Kepmen ESDM 163.K/2021, data 2019) sebagai parameter dengan tanggal berlaku. Tambahkan pengingat untuk memeriksa pemutakhiran ESDM.
9. **Energi pabrik:** EnB regresi (produksi + MC umpan + ukuran saringan) per mesin, EnPI = aktual/model, alarm ±2σ dan CUSUM pada residual (§8).
10. **Sebelum rilis produksi,** verifikasi semua angka [L] terhadap teks asli: ISO 17225-6:2021 Tabel 1 & 2, ISO 18125:2017, lampiran Kepmentan 261/2019 (terutama tabel pembenah tanah), Lampiran XIV PP 22/2021, lampiran Kepmen ESDM 163.K/2021 (OM/BM JAMALI), dan Phyllis2 per bahan.

---

## Daftar sumber yang dibuka/diverifikasi di sesi ini

- Zhu Y., Niu Y., Tan H., Wang X. (2014). Short review on the origin and countermeasure of biomass slagging in grate furnace. *Front. Energy Res.* 2:7. https://www.frontiersin.org/journals/energy-research/articles/10.3389/fenrg.2014.00007/full
- Miles T.R. dkk. (1995/1996). Alkali deposits found in biomass power plants, Vol. 1. NREL/TP-433-8142. https://www.osti.gov/biblio/251288
- DRAM SRN-PPI Add-On PLTGU Grati Blok 2 (EF grid JAMALI 0,87). https://asset.srnmenlh.id/srn-menlhk/files/3ff4297a-0300-4efd-9572-9eca8eb4ba30.pdf
- IRENA-ETSAP E21 (2013) Biomass Co-firing. https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2013/IRENA-ETSAP-Tech-Brief-E21-Biomass-Co-firing.pdf
- IRENA (2012) Biomass for Power Generation. https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2012/RE_Technologies_Cost_Analysis-BIOMASS.pdf
- PT Indonesia Power UBP Teluk Sirih (IGES 2025), Implementation of biomass cofiring in Teluk Sirih CFB. https://www.iges.or.jp/sites/default/files/2025-01/10.%20PT%20Indonesia%20Power%20UBP%20Teluk%20Sirih%20Padang_IMPLEMENTATION%20OF%20BIOMASS%20COFIRING%20IN%20TELUK%20SIRIH%20CFB%20POWER%20PLANT.pdf
- UGM JMDT (sawdust Pelabuhan Ratu). https://journal.ugm.ac.id/jmdt/article/download/114911/43179
- Permen ESDM 12/2023: https://pasal.id/peraturan/permen/permen-esdm-no-12-tahun-2023; Bisnis.com 10 Des 2023
- PMC9671718 Tabel 4 (Kepmentan 261/2019 logam berat); RSNI3 7763:2024 https://bsn.go.id/uploads/attachment/rsni3_7763_2024_siap_jp.pdf
- PP 22/2021 FABA: https://news.detik.com/berita/d-5491006/ ; https://berkas.dpr.go.id/pusaka/files/info_singkat/Info%20Singkat-XIII-7-I-P3DI-April-2021-223.pdf
- ISO 17225-6:2021 pratinjau: https://cdn.standards.iteh.ai/samples/76093/c1acbafdc9314492b149052aafd0e103/ISO-17225-6-2021.pdf
- ISO 18125:2017 pratinjau: https://webstore.ansi.org/preview-pages/ISO/preview_ISO+18125-2017.pdf
- ISO 50006:2023 pratinjau: https://webstore.ansi.org/preview-pages/ISO/preview_ISO+50006-2023.pdf; DOE EnPI v4.0 https://www.energy.gov/eere/amo/articles/enpi-v40-tool-algorithm
- Hammer mill review: https://pmc.ncbi.nlm.nih.gov/articles/PMC6466356 ; https://research.fs.usda.gov/treesearch/53502 ; https://cigrjournal.org/index.php/Ejounral/article/download/5067/3275/26393
- RHA agronomi: https://core.ac.uk/outputs/618327733 ; https://doaj.org/article/576a463b7ad747acba2f2870e974f6b5
- Gabah HPP/rafaksi 2025: https://www.idxchannel.com/economics/intip-harga-terbaru-gabah-dan-beras-berlaku-mulai-15-januari-2025/all ; https://finance.detik.com/berita-ekonomi-bisnis/d-7740273/
- Blending: https://www.osti.gov/pages/biblio/1476911 ; https://ideas.repec.org/a/gam/jeners/v12y2019i22p4390-d288420.html ; https://journal.ump.edu.my/jceib/article/view/10958
- Review biomassa RI (T&F 2024): https://doi.org/10.1080/23311916.2024.2307201
