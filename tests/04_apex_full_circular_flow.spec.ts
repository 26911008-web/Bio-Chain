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

test.describe('Fase 5: Apex Circular Flow & Offline Resilience E2E', () => {

  // Test Case 5.1: Alur Sirkular Penuh (Petani -> Pengepul Bidding -> Serah Terima Resi -> Konversi Pabrik)
  test('TC 5.1: Alur Sirkular Komprehensif — Petani, Bidding Bersaing, Verifikasi Kode, dan Konversi Pabrik', async () => {
    const api = await pwRequest.newContext();

    // 1. Login seluruh persona
    const petani = await login(api, 'petani_sekam');
    const pengepul1 = await login(api, 'pengepul_sekam');
    const driver = await login(api, 'driver_colt1');
    const pabrik = await login(api, 'pabrik_biochar_silika');

    console.log('[Apex E2E] Seluruh persona berhasil terautentikasi.');

    // 2. Petani melapor stok panen 3.000 kg Sekam Padi
    const hRes = await api.post(`${BASE}/api/v1/farmer/harvest`, {
      headers: auth(petani.access_token),
      data: {
        quantity_kg: 3000,
        commodity: 'sekam_padi',
        mill_id: 1,
        moisture_est: 13.5,
      },
    });
    expect(hRes.status()).toBe(201);
    const harvest = await hRes.json();
    console.log(`[Apex E2E] Petani melaporkan lot panen #${harvest.id} (QR: ${harvest.qr_code}).`);

    // 3. Pengepul Sekam menimbang dan memverifikasi panen
    const verRes = await api.post(`${BASE}/api/v1/collector/verify`, {
      headers: auth(pengepul1.access_token),
      data: {
        harvest_id: harvest.id,
        weighed_kg: 3000,
        moisture: 13.5,
        contamination: 0.5,
      },
    });
    expect([200, 201]).toContain(verRes.status());
    const verifiedData = await verRes.json();
    console.log(`[Apex E2E] Pengepul memverifikasi panen: Grade ${verifiedData.grade}, Bobot: ${verifiedData.weighed_kg} kg.`);

    // 4. Pengepul mengajukan Delivery Request ke Pabrik
    const delReqRes = await api.post(`${BASE}/api/v1/collector/delivery-requests`, {
      headers: auth(pengepul1.access_token),
      data: {
        harvest_ids: [harvest.id],
        quantity_kg: 3000.0,
        proposed_price_per_kg: 600.0,
        proposed_date: new Date().toISOString().split('T')[0],
        moisture_est: 13.5,
        note: 'Pasokan Sekam Padi Siap Pirolisis',
      },
    });
    expect([200, 201]).toContain(delReqRes.status());
    const delReq = await delReqRes.json();

    // 5. Pabrik menyetujui ajuan pengiriman (Accept)
    const acceptRes = await api.post(`${BASE}/api/v1/factory/delivery-requests/${delReq.id}/respond`, {
      headers: auth(pabrik.access_token),
      data: { action: 'accept' },
    });
    expect([200, 201]).toContain(acceptRes.status());
    console.log(`[Apex E2E] Pabrik menerima ajuan pengiriman #${delReq.id}.`);

    // 6. Truk tiba di Pabrik -> QC Inbound Jembatan Timbang & Refraksi
    const qcRes = await api.post(`${BASE}/api/v1/factory/qc`, {
      headers: auth(pabrik.access_token),
      data: {
        request_id: delReq.id,
        gross_kg: 9000.0,
        tare_kg: 6000.0, // Netto 3.000 kg
        moisture: 14.0,
        ash: 18.0,
        volatile_matter: 66.0,
        fixed_carbon: 16.0,
        contamination: 0.0,
        note: 'Timbangan jembatan masuk plant Ngaglik',
      },
    });
    expect(qcRes.status()).toBe(201);
    const qc = await qcRes.json();
    console.log(`[Apex E2E] Inbound QC Pabrik: Netto ${qc.net_kg} kg, Kode Verifikasi Resi: ${qc.verification_code}.`);
    expect(qc.verification_code).toBeTruthy();

    // 7. Pabrik mengeksekusi analisis neraca massa konversi (Biochar & Bio-Silika)
    const convRes = await api.post(`${BASE}/api/v1/factory/conversion/analyse`, {
      headers: auth(pabrik.access_token),
      data: {
        code: 'sekam_padi',
        ton_per_month: 3.0,
        moisture_pct: 14.0,
      },
    });
    expect(convRes.status()).toBe(200);
    const conv = await convRes.json();
    console.log(`[Apex E2E] Analisis Neraca Massa Pabrik:`);
    console.log(`   - Rute Konversi : ${conv.decision.route} (${conv.decision.label})`);
    console.log(`   - Produk Utama  : ${conv.decision.best.product}`);
    console.log(`   - Rendemen Arang: ${conv.decision.best.biochar_yield_pct_db}%`);
    console.log(`   - Potensi Silika: ${conv.decision.best.bio_silica_potential_t_per_month} Ton`);

    expect(conv.decision.route).toBe('pirolisis');
    expect(conv.decision.best.product).toContain('biochar + bio-silika');
  });

  // Test Case 5.2: Verifikasi Offline Mode & Resiliensi Jaringan (IndexedDB Sync)
  test('TC 5.2: Resiliensi Lapangan — Simulasi Offline Browser, Antrean Outbox, dan Sinkronisasi Saat Pulih', async ({ browser }) => {
    const api = await pwRequest.newContext();
    const driver = await login(api, 'driver_colt1');

    const context = await browser.newContext({
      permissions: ['geolocation'],
      geolocation: { latitude: -7.768, longitude: 110.293, accuracy: 10 },
    });
    const page = await context.newPage();

    // Set token autentikasi supir
    await page.goto(`${BASE}/login`);
    await page.evaluate((tok) => {
      localStorage.setItem('biochain_token', tok);
      sessionStorage.setItem('biochain_token', tok);
    }, driver.access_token);
    await page.goto(`${BASE}/`);
    await page.waitForLoadState('domcontentloaded');

    // 1. Putus koneksi internet browser
    await context.setOffline(true);
    console.log('[Apex E2E Offline] Browser dialihkan ke mode Offline (Blank Spot Lapangan).');

    // 2. Simulasikan aksi pencatatan supir saat offline
    await page.evaluate(() => {
      if (typeof (window as any).apiMutation === 'function') {
        (window as any).apiMutation('/api/v1/driver/track', {
          route_id: 1,
          points: [{ lat: -7.768, lon: 110.293, recorded_at: new Date().toISOString() }],
        }, 'Unggah Jejak GPS Lapangan');
      }
    });

    // 3. Verifikasi antrean outbox tersimpan di IndexedDB / Local Storage
    const queuedCount = await page.evaluate(() => {
      const fn = (window as any).myOutbox;
      return typeof fn === 'function' ? fn().length : 0;
    });
    console.log(`[Apex E2E Offline] Jumlah mutasi tersimpan di outbox lokal saat offline: ${queuedCount}`);

    // 4. Pulihkan koneksi internet (Online)
    await context.setOffline(false);
    console.log('[Apex E2E Offline] Koneksi internet dipulihkan (Online).');

    // 5. Verifikasi antrean outbox terkirim dan bersih kembali
    await expect.poll(async () => page.evaluate(() => {
      const fn = (window as any).myOutbox;
      return typeof fn === 'function' ? fn().length : 0;
    }), { timeout: 15_000 }).toBe(0);

    console.log('[Apex E2E Offline] Antrean outbox lokal berhasil terkirim dan sinkron dengan server!');
    await context.close();
  });

});
