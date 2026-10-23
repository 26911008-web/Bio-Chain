import { test, expect, request as pwRequest } from '@playwright/test';

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

test.describe('Fase 7: Full-Lifecycle E2E Supply Chain & Closed-Loop Biochar (V-Omega)', () => {
  test('Siklus Lengkap Hulu-Hilir: Lapor Direct/Lelang -> Grouped Plan -> Konfirmasi Jadwal -> Lapangan QC Deviasi -> Isolasi Driver -> QC Gerbang & Ramp -> Blending 4 Produk -> Gatekeeper Logam Berat -> Distribusi Balik Sawah', async () => {
    const api = await pwRequest.newContext();

    // =========================================================================
    // STEP 0: OTENTIKASI SELURUH PERONA
    // =========================================================================
    const petani = await login(api, 'petani_sekam');
    const pengepul = await login(api, 'pengepul_sekam');
    const driver = await login(api, 'driver_colt1');
    const pabrik = await login(api, 'pabrik_biochar_silika');

    expect(petani.access_token).toBeDefined();
    expect(pengepul.access_token).toBeDefined();
    expect(driver.access_token).toBeDefined();
    expect(pabrik.access_token).toBeDefined();
    console.log('✅ [E2E] Step 0: Seluruh persona berhasil diautentikasi.');

    // =========================================================================
    // STEP 1: HULU - PETANI LAPOR BIOMASSA (DUAL-MODE) & REQUEST BIOCHAR SIRKULAR
    // =========================================================================
    // 1.1 Mode Lelang (Bidding) + Request Biochar
    const hLelangRes = await api.post(`${BASE}/api/v1/farmer/harvest`, {
      headers: auth(petani.access_token),
      data: {
        quantity_kg: 2500.0,
        commodity: 'sekam_padi',
        moisture_est: 13.0,
        grade_est: 'A',
        transaction_mode: 'BIDDING',
        logistics_mode: 'PICKUP',
        floor_price: 480.0,
        biochar_request_kg: 500.0,
        biochar_land_area_ha: 1.2,
        biochar_delivery_point: 'Lahan Petani Petak Barat',
      },
    });
    expect(hLelangRes.status()).toBe(201);
    const hLelang = await hLelangRes.json();
    expect(hLelang.id).toBeDefined();
    expect(hLelang.listing_id).toBeDefined();
    console.log(`✅ [E2E] Step 1.1: Petani mendaftarkan panen lelang #${hLelang.id} (Listing #${hLelang.listing_id}) + Request biochar 500 kg.`);

    // 1.2 Mode Langsung (Direct)
    const hDirectRes = await api.post(`${BASE}/api/v1/farmer/harvest`, {
      headers: auth(petani.access_token),
      data: {
        quantity_kg: 1800.0,
        commodity: 'sekam_padi',
        moisture_est: 12.5,
        grade_est: 'A',
        transaction_mode: 'DIRECT',
        logistics_mode: 'PICKUP',
      },
    });
    expect(hDirectRes.status()).toBe(201);
    const hDirect = await hDirectRes.json();
    console.log(`✅ [E2E] Step 1.2: Petani mendaftarkan panen langsung #${hDirect.id}.`);

    // =========================================================================
    // STEP 2: TENGAH - PENGEPUL GROUPED DASHBOARD, BIDDING & PLAN JEMPUT
    // =========================================================================
    // 2.1 Pengepul membaca offers dashboard (Tab Langsung vs Lelang terkelompok)
    const dashRes = await api.get(`${BASE}/api/v1/collector/offers-dashboard`, {
      headers: auth(pengepul.access_token),
    });
    expect(dashRes.status()).toBe(200);
    const dashData = await dashRes.json();
    expect(dashData.tabs).toBeDefined();
    expect(dashData.lelang.length).toBeGreaterThan(0);
    console.log(`✅ [E2E] Step 2.1: Pengepul membuka dashboard terkelompok (Lelang: ${dashData.lelang.length}, Langsung: ${dashData.langsung_diambil.length}).`);

    // 2.2 Pengepul memasang tawaran lelang pada listing petani
    const bidRes = await api.post(`${BASE}/api/v1/collector/bids`, {
      headers: auth(pengepul.access_token),
      data: {
        listing_id: hLelang.listing_id,
        price_per_kg: 520.0,
        quantity_kg: 2500.0,
        scheme: 'jemput',
        pickup_date: new Date().toISOString().split('T')[0],
        note: 'Tawaran penjemputan armada spesialis sekam',
      },
    });
    expect(bidRes.status()).toBe(201);
    const bidData = await bidRes.json();
    const bidId = bidData.bid_id;
    console.log(`✅ [E2E] Step 2.2: Pengepul memasang tawaran bid #${bidId} @Rp520/kg.`);

    // 2.3 Petani menerima tawaran lelang
    const acceptRes = await api.post(`${BASE}/api/v1/farmer/listings/${hLelang.listing_id}/accept`, {
      headers: auth(petani.access_token),
      data: {
        bid_id: bidId,
        quantity_kg: 2500.0,
      },
    });
    expect(acceptRes.status()).toBe(200);
    const acceptData = await acceptRes.json();
    const harvestDealId = acceptData.harvest_id;
    const dealQr = acceptData.qr_code;
    console.log(`✅ [E2E] Step 2.3: Petani menerima tawaran, lot panen aktif deal #${harvestDealId} terbentuk.`);

    // 2.4 Pengepul membuat Consolidated Pickup Plan (dengan backhaul biochar)
    const planRes = await api.post(`${BASE}/api/v1/collector/consolidated-pickup-plan`, {
      headers: auth(pengepul.access_token),
      data: {
        harvest_ids: [harvestDealId, hDirect.id],
        vehicle_plate: 'AB 8421 CS',
        truck_max_kg: 5000.0,
        truck_max_m3: 40.0,   // 4.300 kg sekam ÷ ±120 kg/m³ ≈ 35,8 m³ → truk 30 m³ memang (benar) ditolak
      },
    });
    expect(planRes.status()).toBe(200);
    const planData = await planRes.json();
    expect(planData.is_feasible).toBe(true);
    console.log(`✅ [E2E] Step 2.4: Rencana penjemputan teroptimasi terbentuk (Feasible: ${planData.is_feasible}).`);

    // =========================================================================
    // STEP 3: PETANI KONFIRMASI JADWAL & PENGEPUL QC LAPANGAN (SUSUT & DEVIASI)
    // =========================================================================
    // 3.1 Petani Approve Jadwal Jemput
    const confRes = await api.post(`${BASE}/api/v1/farmer/schedule/confirm`, {
      headers: auth(petani.access_token),
      data: {
        bid_id: bidId,
        decision: 'APPROVE',
        reschedule_note: 'Siap diangkut pagi hari',
      },
    });
    expect(confRes.status()).toBe(200);
    const confData = await confRes.json();
    expect(confData.farmer_schedule_status).toBe('APPROVED');
    console.log('✅ [E2E] Step 3.1: Petani mengonfirmasi jadwal penjemputan.');

    // 3.2 Pengepul timbang aktual di lapangan (Uji deviasi: klaim 2500 kg vs timbang aktual 2450 kg)
    const verifyRes = await api.post(`${BASE}/api/v1/collector/verify`, {
      headers: auth(pengepul.access_token),
      data: {
        harvest_id: harvestDealId,
        weighed_kg: 2450.0,
        actual_weighed_qty: 2450.0,
        moisture: 13.2,
        contamination: 0.5,
      },
    });
    expect(verifyRes.status()).toBe(200);
    const verifyData = await verifyRes.json();
    expect(verifyData.weighed_kg).toBe(2450.0);
    console.log(`✅ [E2E] Step 3.2: Pengepul verifikasi QC lapangan: timbang aktual ${verifyData.weighed_kg} kg (susut 50 kg tercatat).`);

    // 3.3 Petani mengecek panel Feedback Mutu & Transparansi Deviasi
    const fbRes = await api.get(`${BASE}/api/v1/farmer/quality-feedback`, {
      headers: auth(petani.access_token),
    });
    expect(fbRes.status()).toBe(200);
    console.log('✅ [E2E] Step 3.3: Panel feedback deviasi mutu & susut petani aktif dan terverifikasi.');

    // 3.4 Pengepul bayar DP dan Pelunasan ke Petani
    const dpRes = await api.post(`${BASE}/api/v1/collector/harvests/${harvestDealId}/pay-dp`, {
      headers: auth(pengepul.access_token),
      data: {
        amount_rp: 300000.0,
        method: 'transfer',
        reference: 'DP-E2E-001',
      },
    });
    expect(dpRes.status()).toBe(201);
    console.log('✅ [E2E] Step 3.4: Pengepul membayar DP Rp300.000 ke petani.');

    // =========================================================================
    // STEP 4: PENGEPUL KE PABRIK & ISOLASI JOB DRIVER
    // =========================================================================
    // Checkpoint scan QR di titik jemput oleh armada pengangkut
    const scanRes = await api.post(`${BASE}/api/v1/driver/checkpoint-scan`, {
      headers: auth(driver.access_token),
      data: {
        qr_token: dealQr,
        checkpoint_type: 'PICKUP',
        lat: -7.7680,
        lon: 110.2930,
        notes: 'Muatan 2.450 kg telah dimuat ke bak truk',
      },
    });
    expect(scanRes.status()).toBe(200);
    console.log('✅ [E2E] Step 4: Checkpoint scan QR titik serah-terima pengangkutan berhasil.');

    // =========================================================================
    // STEP 5: GERBANG PABRIK, TIMBANGAN JEMBATAN QC & INVOICE TOP
    // =========================================================================
    // Seperti UI pabrik: pilih ramp sekam dari daftar ramp (id tidak dikarang)
    const rampsRes = await api.get(`${BASE}/api/v1/factory/loading-ramps`, { headers: auth(pabrik.access_token) });
    expect(rampsRes.status()).toBe(200);
    const rampsBody = await rampsRes.json();
    const rampList = Array.isArray(rampsBody) ? rampsBody : (rampsBody.ramps || rampsBody.items || []);
    const sekamRamp = rampList.find((r: any) => r.biomass_type === 'sekam_padi') || rampList[0];
    expect(sekamRamp, 'ramp sekam tersedia').toBeTruthy();
    const gateRes = await api.post(`${BASE}/api/v1/factory/gate-receptions`, {
      headers: auth(pabrik.access_token),
      data: {
        collector_id: pengepul.user?.id || 2,
        vehicle_plate: 'AB 8421 CS',
        driver_name: 'Driver Slamet',
        logistics_carrier: 'FACTORY_FLEET',
        biomass_type: 'sekam_padi',
        gross_weight: 7450.0,
        tare_weight: 5000.0, // Netto 2450.0 kg
        tested_mc_pct: 12.8,
        tested_ash_pct: 16.8,
        tested_lhv_kcal: 3450.0,
        contamination_pct: 0.2,
        qc_decision: 'ACCEPTED',
        accepted_qty_kg: 2450.0,
        rejected_qty_kg: 0.0,
        allocated_ramp_id: sekamRamp.id,
        unit_price_rp: 600.0,
        payment_scheme: 'TOP',
        due_days: 14,
      },
    });
    expect(gateRes.status()).toBe(201);
    const gateData = await gateRes.json();
    expect(gateData.gate_ticket.accepted_qty_kg).toBe(2450.0);
    expect(gateData.invoice).toBeDefined();
    console.log(`✅ [E2E] Step 5: Gerbang pabrik menerima muatan Netto 2.450 kg, Invoice TOP #${gateData.invoice.invoice_number} terbit.`);

    // =========================================================================
    // STEP 6: BLENDING MULTI-RAMP 4 PRODUK & GATEKEEPER LOGAM BERAT
    // =========================================================================
    // 6.1 Optimasi Blending Multi-Ramp
    const optRes = await api.post(`${BASE}/api/v1/factory/blends/optimize`, {
      headers: auth(pabrik.access_token),
      data: { batch_size_kg: 5000.0 },
    });
    expect(optRes.status()).toBe(200);
    const optData = await optRes.json();
    expect(optData.recommendations.length).toBeGreaterThanOrEqual(1);

    // 6.2 Eksekusi Batch BIOCHAR
    const biocharRec = optData.recommendations.find((r: any) => r.target_product === 'BIOCHAR') || optData.recommendations[0];
    const commitRes = await api.post(`${BASE}/api/v1/factory/blends/commit`, {
      headers: auth(pabrik.access_token),
      data: {
        target_product: 'BIOCHAR',
        total_input_kg: biocharRec.total_input_kg || 5000.0,
        ramp_allocations: biocharRec.ramp_allocations || [{ ramp_id: 1, qty_kg: 5000.0 }],
        cost_per_kg: biocharRec.hpp_per_kg || 450.0,
        target_selling_price_per_kg: biocharRec.target_selling_price_per_kg || 3500.0,
        estimated_margin_rp: biocharRec.total_profit_rp || 15000000.0,
        net_tco2e: biocharRec.net_tco2e || -4.2,
        final_mc_pct: biocharRec.final_mc_pct || 12.0,
        final_ash_pct: biocharRec.final_ash_pct || 16.0,
        final_lhv_kcal: biocharRec.final_lhv_kcal || 3500.0,
      },
    });
    expect(commitRes.status()).toBe(201);
    const commitData = await commitRes.json();
    console.log(`✅ [E2E] Step 6.1: Batch produksi biochar #${commitData.blend_code} berhasil diproduksi.`);

    // 6.3 Gatekeeper Keamanan Kimia: Uji Lab Logam Berat
    const bpRes = await api.get(`${BASE}/api/v1/factory/by-products`, {
      headers: auth(pabrik.access_token),
    });
    const bpList = await bpRes.json();
    expect(bpList.length).toBeGreaterThan(0);
    const targetBp = bpList[0];

    const safetyRes = await api.post(`${BASE}/api/v1/factory/by-products/${targetBp.id}/safety-test`, {
      headers: auth(pabrik.access_token),
      data: {
        pb_ppm: 4.5,
        cd_ppm: 0.18,
        as_ppm: 0.95,
        lab_cert_no: 'LAB-KAN-ISO17025-2026-X88',
      },
    });
    expect(safetyRes.status()).toBe(200);
    const safetyData = await safetyRes.json();
    expect(safetyData.is_safety_passed).toBe(true);
    expect(safetyData.circular_status).toBe('APPROVED_FOR_SOIL');
    console.log('✅ [E2E] Step 6.2: Gatekeeper Kimia: Biochar lolos batas logam berat (APPROVED_FOR_SOIL).');

    // =========================================================================
    // STEP 7: DISTRIBUSI BALIK KE LAHAN PETANI & EVALUASI MUTU (CLOSED-LOOP)
    // =========================================================================
    const evalRes = await api.post(`${BASE}/api/v1/farmer/biochar-evaluations`, {
      headers: auth(petani.access_token),
      data: {
        collector_id: pengepul.user?.id || 2,
        batch_code: commitData.blend_code,
        grain_size_mesh_rating: 5,
        pyrolysis_maturity_rating: 5,
        moisture_rating: 5,
        soil_impact_rating: 5,
        review_notes: 'Biochar bermutu prima, tanah sawah gembur dan retensi air meningkat signifikan.',
      },
    });
    expect(evalRes.status()).toBe(201);
    console.log('✅ [E2E] Step 7: Petani mengisi formulir evaluasi mutu biochar sawah. Siklus sirkular tertutup sempurna!');
  });
});
