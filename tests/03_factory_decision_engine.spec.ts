import { test, expect, request as pwRequest, Browser } from '@playwright/test';

const BASE = process.env.BIOCHAIN_URL || 'http://127.0.0.1:8000';

function auth(token: string) {
  return { Authorization: `Bearer ${token}` };
}

async function login(api: any, username: string) {
  const res = await api.post(`${BASE}/api/v1/auth/login`, {
    data: { username, password: 'password123' },
  });
  if (!res.ok()) {
    throw new Error(`Login gagal untuk ${username}: HTTP ${res.status()} -> ${await res.text()}`);
  }
  return res.json();
}

test.describe('Fase 4: Factory Inventory, Refraction & Multi-Output Conversion', () => {

  // Test Case 3.1: Katalog Multi-Feedstock & QC Filter
  test('TC 3.1: Katalog Multi-Feedstock & QC Filter — Filter LHV, MC, dan Harga per kg', async () => {
    const api = await pwRequest.newContext();
    const pabrik1 = await login(api, 'pabrik_pelet_briket');
    const pabrik2 = await login(api, 'pabrik_biochar_silika');

    // 1. Ambil katalog master biomassa dari sudut pandang pabrik
    const bioRes = await api.get(`${BASE}/api/v1/biomass`, {
      headers: auth(pabrik1.access_token),
    });
    expect(bioRes.status()).toBe(200);
    const catalog = await bioRes.json();
    expect(Array.isArray(catalog)).toBeTruthy();
    expect(catalog.length).toBeGreaterThanOrEqual(4);

    const commodities = catalog.map((c: any) => c.code);
    expect(commodities).toContain('sekam_padi');
    expect(commodities).toContain('tongkol_jagung');
    expect(commodities).toContain('ampas_tebu');
    expect(commodities).toContain('serbuk_sengon');

    console.log(`[TC 3.1 Audit] Total komoditas master biomassa aktif: ${catalog.length}`);
    for (const c of catalog) {
      console.log(`   - ${c.code.padEnd(16)} | LHV: ${c.lhv_db_mj_kg} MJ/kg | MC Ref: ${c.moisture_ref_pct}% | Ash: ${c.ash_pct_db}% | Bulk: ${c.bulk_density_kg_m3} kg/m³`);
    }

    // 2. Filter QC Feedstock untuk Pabrik 1 (Fokus Pelet/Briket: LHV >= 16 MJ/kg, Ash <= 5%, MC <= 25%)
    const pelletFeeds = catalog.filter((c: any) => c.lhv_db_mj_kg >= 16.0 && c.ash_pct_db <= 5.0);
    expect(pelletFeeds.map((x: any) => x.code)).toContain('tongkol_jagung');
    expect(pelletFeeds.map((x: any) => x.code)).toContain('serbuk_sengon');
    console.log(`[TC 3.1 Audit] Feedstock lolos filter Pelet/Briket: ${pelletFeeds.map((x: any) => x.name).join(', ')}`);

    // 3. Filter QC Feedstock untuk Pabrik 2 (Fokus Bio-Silika & Biochar: SiO2 Abu >= 80%, Ash >= 10%)
    const silicaFeeds = catalog.filter((c: any) => (c.sio2_pct_ash || 0) >= 80.0 && c.ash_pct_db >= 10.0);
    expect(silicaFeeds.map((x: any) => x.code)).toContain('sekam_padi');
    console.log(`[TC 3.1 Audit] Feedstock lolos filter Bio-Silika/Biochar: ${silicaFeeds.map((x: any) => x.name).join(', ')}`);
  });

  // Test Case 3.2: Refraksi Kadar Air Timbangan Jembatan
  test('TC 3.2: Refraksi Kadar Air Timbangan Jembatan — 5 Ton Sekam Aktual 19% vs Kontrak 14%', async () => {
    const api = await pwRequest.newContext();
    const pabrik = await login(api, 'pabrik_pelet_briket');
    const pengepul = await login(api, 'pengepul_sekam');
    const petani = await login(api, 'petani_sekam');

    // 1. Buat panen 5.000 kg dan diverifikasi pengepul
    const h = await (await api.post(`${BASE}/api/v1/farmer/harvest`, {
      headers: auth(petani.access_token),
      data: { quantity_kg: 5000, commodity: 'sekam_padi', mill_id: 1 },
    })).json();

    await api.post(`${BASE}/api/v1/collector/verify`, {
      headers: auth(pengepul.access_token),
      data: { harvest_id: h.id, weighed_kg: 5000, moisture: 14.0 },
    });

    // 2. Pengepul mengajukan Delivery Request ke Pabrik
    const delReqRes = await api.post(`${BASE}/api/v1/collector/delivery-requests`, {
      headers: auth(pengepul.access_token),
      data: {
        harvest_ids: [h.id],
        quantity_kg: 5000.0,
        proposed_price_per_kg: 600.0,
        proposed_date: new Date().toISOString().split('T')[0],
        moisture_est: 14.0,
        note: 'Pengiriman 5 Ton Sekam Padi standar kontrak MC 14%',
      },
    });
    expect([200, 201]).toContain(delReqRes.status());
    const delReq = await delReqRes.json();

    // 3. Pabrik menerima (accept) ajuan delivery request
    const acceptRes = await api.post(`${BASE}/api/v1/factory/delivery-requests/${delReq.id}/respond`, {
      headers: auth(pabrik.access_token),
      data: { action: 'accept' },
    });
    expect([200, 201]).toContain(acceptRes.status());

    // 4. Truk tiba di jembatan timbang pabrik:
    //    Bruto 12.000 kg, Tara 7.000 kg -> Netto timbangan 5.000 kg
    //    Hasil uji lab MC aktual: 19% (kontrak 14%)
    const qcRes = await api.post(`${BASE}/api/v1/factory/qc`, {
      headers: auth(pabrik.access_token),
      data: {
        request_id: delReq.id,
        gross_kg: 12000.0,
        tare_kg: 7000.0,
        moisture: 19.0,
        ash: 18.0,
        volatile_matter: 66.0,
        fixed_carbon: 16.0,
        contamination: 0.0,
        note: 'Uji timbangan jembatan & moisture meter gate in',
      },
    });
    expect(qcRes.status()).toBe(201);
    const qc = await qcRes.json();

    console.log(`[TC 3.2 Audit] QC Jembatan Timbang Berhasil:`);
    console.log(`   - Netto Timbangan : ${qc.net_kg} kg`);
    console.log(`   - MC Aktual       : ${qc.moisture}% (Kontrak: 14%)`);
    console.log(`   - Refraksi Air    : ${qc.refraction_kg} kg`);
    console.log(`   - Basis Kering Net: ${qc.dry_basis_kg} kg`);
    console.log(`   - Keputusan QC    : ${qc.decision}`);
    console.log(`   - Harga Kontrak   : Rp ${delReq.proposed_price_per_kg} -> Harga Final: Rp ${qc.final_price_per_kg}`);
    console.log(`   - Total Pembayaran: Rp ${qc.total_payment_rp.toLocaleString('id-ID')}`);

    // Audit assertions:
    // Rumus refraksi pabrik: net * (1 - MC_akt/100) / (1 - MC_ref/100)
    // 5000 * (1 - 0.19) / (1 - 0.11) = 5000 * 0.81 / 0.89 = 4550.56 kg -> Refraksi 449.44 kg
    expect(qc.refraction_kg).toBeGreaterThan(250.0);
    expect(qc.refraction_kg).toBeLessThan(500.0);
    expect(qc.decision).toBe('terima_potongan');
    expect(qc.final_price_per_kg).toBeLessThan(600.0);
  });

  // Test Case 3.3: Validasi Pohon Keputusan Konversi Multi-Output
  test('TC 3.3: Pohon Keputusan Konversi — Biopellet/Briket (Pabrik 1) vs Pirolisis Biochar & Bio-Silika (Pabrik 2)', async () => {
    const api = await pwRequest.newContext();
    const pabrik1 = await login(api, 'pabrik_pelet_briket');
    const pabrik2 = await login(api, 'pabrik_biochar_silika');

    // 1. Rute Biopellet & Briket (Pabrik 1): Input Serbuk Sengon 100 Ton/Bulan
    const sengonAnalysisRes = await api.post(`${BASE}/api/v1/factory/conversion/analyse`, {
      headers: auth(pabrik1.access_token),
      data: {
        code: 'serbuk_sengon',
        ton_per_month: 100.0,
        moisture_pct: 15.0,
      },
    });
    expect(sengonAnalysisRes.status()).toBe(200);
    const sengonAnalysis = await sengonAnalysisRes.json();

    console.log(`[TC 3.3 Audit] Rute Konversi Serbuk Sengon (Pabrik 1):`);
    console.log(`   - LHV as-received       : ${sengonAnalysis.energy.lhv_ar_mj_kg} MJ/kg (${sengonAnalysis.energy.lhv_ar_kcal_kg} kcal/kg)`);
    console.log(`   - Energi Termal Total   : ${sengonAnalysis.energy.thermal_gj_per_month} GJ/bulan`);
    console.log(`   - Rekomendasi Rute      : ${sengonAnalysis.decision.label}`);
    console.log(`   - Estimasi Listrik PLTU : ${JSON.stringify(sengonAnalysis.energy.electricity_mwh_per_month)} MWh`);

    // Evaluasi optimasi pencampuran bahan bakar (Fuel Blending / Pelletizing)
    const blendRes = await api.post(`${BASE}/api/v1/factory/fuel-blend/optimize`, {
      headers: auth(pabrik1.access_token),
      data: {
        preset: 'pelet_4000_kcal',
        target_kg: 50000,
        feeds: [
          { code: 'serbuk_sengon', available_kg: 40000, min_share_pct: 20 },
          { code: 'tongkol_jagung', available_kg: 30000, min_share_pct: 20 },
        ],
      },
    });
    expect(blendRes.status()).toBe(200);
    const blendData = await blendRes.json();
    console.log(`[TC 3.3 Audit] Optimasi Pelet Pelet_4000_kcal: Feasible ${blendData.feasible}, Biaya Rp ${blendData.cost?.rp_per_kg_product}/kg`);
    expect(blendData.feasible).toBe(true);
    expect(blendData.cost.rp_per_kg_product).toBeGreaterThan(0);

    // 2. Rute Biochar & Bio-Silika (Pabrik 2): Input Sekam Padi 100 Ton/Bulan
    const sekamAnalysisRes = await api.post(`${BASE}/api/v1/factory/conversion/analyse`, {
      headers: auth(pabrik2.access_token),
      data: {
        code: 'sekam_padi',
        ton_per_month: 100.0,
        moisture_pct: 14.0,
      },
    });
    expect(sekamAnalysisRes.status()).toBe(200);
    const sekamAnalysis = await sekamAnalysisRes.json();

    console.log(`[TC 3.3 Audit] Pohon Keputusan Sekam Padi (Pabrik 2):`);
    console.log(`   - Rute Terpilih         : ${sekamAnalysis.decision.route} (${sekamAnalysis.decision.label})`);
    console.log(`   - Produk Utama          : ${sekamAnalysis.decision.best.product}`);
    console.log(`   - Rendemen Biochar      : ${sekamAnalysis.decision.best.biochar_yield_pct_db}% (~${sekamAnalysis.decision.best.biochar_t_per_month} Ton/bulan)`);
    console.log(`   - Potensi Bio-Silika    : ${sekamAnalysis.decision.best.bio_silica_potential_t_per_month} Ton/bulan`);

    // Audit assertion:
    // Pohon keputusan WAJIB memilih pirolisis lambat untuk sekam padi (karena SiO2 abu >= 85% dan abu >= 12%)
    expect(sekamAnalysis.decision.route).toBe('pirolisis');
    expect(sekamAnalysis.decision.best.product).toContain('biochar + bio-silika');
    // Rendemen biochar berkisar 25-50% (basis kering mengandung fraksi abu silika + fixed carbon)
    expect(sekamAnalysis.decision.best.biochar_yield_pct_db).toBeGreaterThanOrEqual(24.0);
    expect(sekamAnalysis.decision.best.biochar_yield_pct_db).toBeLessThanOrEqual(55.0);
    // Bio-Silika terekstraksi sekitar 10-18 Ton dari 100 Ton sekam padi
    expect(sekamAnalysis.decision.best.bio_silica_potential_t_per_month).toBeGreaterThan(10.0);
  });

  // Test Case 3.4: Agronomic Circular Ash Ledger & Logam Berat
  test('TC 3.4: Agronomic Circular Ash Ledger — Kepatuhan Uji Logam Berat (Pb, Cd, As) Sebelum Serah Terima Poktan', async () => {
    const api = await pwRequest.newContext();
    const pabrik2 = await login(api, 'pabrik_biochar_silika');
    const petani = await login(api, 'petani_sekam');

    // 1. Buat Kelompok Tani (Poktan) jika belum ada
    const poktanList = await (await api.get(`${BASE}/api/v1/factory/farmer-groups`, {
      headers: auth(pabrik2.access_token),
    })).json();
    let poktan = poktanList.find((g: any) => g.leader_name.includes('Slamet') || g.kecamatan === 'Godean');
    if (!poktan) {
      const pRes = await api.post(`${BASE}/api/v1/factory/farmer-groups`, {
        headers: auth(pabrik2.access_token),
        data: {
          name: 'Poktan Makmur Lestari Godean',
          desa: 'Sidomulyo',
          kecamatan: 'Godean',
          kabupaten: 'Sleman',
          leader_user_id: petani.user_id,
          leader_name: 'Pak Slamet',
          member_count: 25,
        },
      });
      expect([200, 201]).toContain(pRes.status());
      poktan = await pRes.json();
    }
    console.log(`[TC 3.4 Audit] Kelompok Tani: ${poktan.name} (ID: ${poktan.id})`);

    // 2. Pabrik mencatat timbulan sisa abu pirolisis (Silica Ash 2.000 kg)
    const ashRes = await api.post(`${BASE}/api/v1/factory/ash`, {
      headers: auth(pabrik2.access_token),
      data: {
        ash_type: 'silica_ash',
        source_commodity: 'sekam_padi',
        quantity_kg: 2000.0,
      },
    });
    expect(ashRes.status()).toBe(201);
    const ash = await ashRes.json();
    console.log(`[TC 3.4 Audit] Timbulan Abu Tercatat: ID #${ash.id} (Kode: ${ash.code}), Status: ${ash.status}, Logam Berat: ${ash.heavy_metal_status}`);

    // 3. NEGATIVE ASSERTION: Coba alokasikan abu ke Kelompok Tani SEBELUM lolos uji lab logam berat
    const prematureAllocRes = await api.post(`${BASE}/api/v1/factory/ash/${ash.id}/allocate`, {
      headers: auth(pabrik2.access_token),
      data: {
        farmer_group_id: poktan.id,
        land_area_ha: 3.5,
      },
    });
    console.log(`[TC 3.4 Audit] Respon alokasi prematur sebelum uji lab: HTTP ${prematureAllocRes.status()}`);
    // Sistem WAJIB menolak (HTTP 409) karena abu belum lulus uji logam berat (Kepmentan 261/2019)
    expect(prematureAllocRes.status()).toBe(409);
    const errorBody = await prematureAllocRes.text();
    expect(errorBody).toContain('logam berat');

    // 4. Petugas memasukkan hasil uji laboratorium sertifikasi aman:
    //    Pb: 12 ppm (Batas 100), Cd: 0.8 ppm (Batas 2), As: 2.1 ppm (Batas 20) -> LULUS
    const labRes = await api.post(`${BASE}/api/v1/factory/ash/${ash.id}/lab`, {
      headers: auth(pabrik2.access_token),
      data: {
        lab_name: 'Balai Pengujian Standar Instrumen Pertanian (BPSIP)',
        lab_report_no: 'LAB-BPSIP-2026-0891',
        pb_ppm: 12.0,
        cd_ppm: 0.8,
        as_ppm: 2.1,
        k2o_pct: 3.2,
        sio2_pct: 88.5,
        ph: 8.2,
      },
    });
    expect([200, 201]).toContain(labRes.status());
    const labData = await labRes.json();
    console.log(`[TC 3.4 Audit] Hasil Uji Lab Tersimpan: Status Logam Berat = ${labData.heavy_metal_status}`);
    expect(labData.heavy_metal_status).toBe('lulus');

    // 5. Alokasi abu ke Kelompok Tani setelah lulus uji
    const allocRes = await api.post(`${BASE}/api/v1/factory/ash/${ash.id}/allocate`, {
      headers: auth(pabrik2.access_token),
      data: {
        farmer_group_id: poktan.id,
        land_area_ha: 3.5,
      },
    });
    expect([200, 201]).toContain(allocRes.status());
    const allocData = await allocRes.json();
    expect(allocData.status).toBe('dialokasikan');
    console.log(`[TC 3.4 Audit] Abu ID #${ash.id} berhasil dialokasikan ke Poktan ${poktan.name}`);

    // 6. Serah terima abu di lahan kelompok tani (Handover)
    const handRes = await api.post(`${BASE}/api/v1/factory/ash/${ash.id}/handover`, {
      headers: auth(pabrik2.access_token),
      data: {
        photo_url: 'https://storage.biochain.test/evidence/handover_ash_sidomulyo.jpg',
        lat: -7.7680,
        lon: 110.2930,
        land_area_ha: 3.5,
      },
    });
    expect([200, 201]).toContain(handRes.status());
    const handData = await handRes.json();
    expect(handData.status).toBe('diserahkan');
    console.log(`[TC 3.4 Audit] Serah terima fisik abu berhasil di titik lahan (-7.7680, 110.2930)`);

    // 7. Verifikasi perspektif Petani / Ketua Poktan di Ledger Sirkular Agronomi
    const farmerAshListRes = await api.get(`${BASE}/api/v1/farmer/ash`, {
      headers: auth(petani.access_token),
    });
    expect(farmerAshListRes.status()).toBe(200);
    const farmerAshList = await farmerAshListRes.json();
    expect(Array.isArray(farmerAshList)).toBeTruthy();
    const myReceivedAsh = farmerAshList.find((x: any) => x.id === ash.id);
    expect(myReceivedAsh).toBeDefined();
    expect(myReceivedAsh.status).toBe('diserahkan');
    expect(myReceivedAsh.heavy_metal_status).toBe('lulus');
    console.log(`[TC 3.4 Audit] Verifikasi Selesai: Ketua Poktan melihat catatan abu #${ash.id} berstatus '${myReceivedAsh.status}' di ledger agronomi miliknya.`);
  });

});
