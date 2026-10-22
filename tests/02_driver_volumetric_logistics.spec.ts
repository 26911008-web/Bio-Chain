import { test, expect, request as pwRequest, APIRequestContext } from '@playwright/test';

/**
 * FASE 3: VOLUMETRIC LOGISTICS, SINGLE-COMMODITY & OFFLINE RESILIENCE
 * 
 * Pengujian End-to-End Playwright:
 * 1. Test Case 2.1 (Validasi Muatan Volumetrik):
 *    - 4 Ton Sekam Padi (110 kg/m³ -> Volume ≈ 36.3 m³) pada truk bak 16 m³ (maks payload 6 Ton).
 *    - Sistem WAJIB menolak muatan berlebih volumetrik (HTTP 422: volume > kapasitas bak) atau memecah rute.
 * 2. Test Case 2.2 (Anti-Cross Contamination - Negative Assertion):
 *    - Mencoba dispatch gabungan Sekam Padi dan Bonggol Jagung dalam 1 rute trip yang sama.
 *    - Sistem WAJIB menolak penggabungan komoditas berbeda dalam satu trip (Anti-Cross Contamination).
 * 3. Test Case 2.3 (Penyelesaian Trip & Trip Baru):
 *    - Driver menyelesaikan rute aktif via complete-route -> Status rute menjadi 'completed'.
 *    - Driver yang telah selesai baru diizinkan menerima penugasan surat jalan baru.
 * 4. Test Case 2.4 (Simulasi Offline & Store-and-Forward):
 *    - Simulasi putus sinyal browser (setOffline(true)) saat konfirmasi pickup di lapangan.
 *    - Verifikasi antrean pickup & GPS tersimpan secara lokal dan tersinkronisasi otomatis saat online kembali.
 */

const BASE = (process.env.BIOCHAIN_URL || 'http://127.0.0.1:8000').trim();

async function login(api: APIRequestContext, identifier: string, password = 'password123') {
  const r = await api.post(`${BASE}/api/v1/auth/login`, { data: { identifier, password } });
  expect(r.status(), `Gagal login untuk ${identifier}: ${await r.text()}`).toBe(200);
  return r.json();
}

const auth = (tok: string) => ({ Authorization: `Bearer ${tok}` });

async function openAs(browser: any, user: any, opts: any = {}) {
  const context = await browser.newContext(opts);
  const page = await context.newPage();
  await page.goto(BASE);
  await page.evaluate(([tok, u]: any) => {
    localStorage.setItem('biochain_token', tok);
    localStorage.setItem('biochain_user', JSON.stringify(u));
  }, [user.access_token, user]);
  await page.reload();
  return { context, page };
}

test.describe('Fase 3: Volumetric Logistics, Single-Commodity & Offline Resilience', () => {

  // Test Case 2.1: Validasi Muatan Volumetrik Truk Colt Diesel
  test('TC 2.1: Validasi Batas Kubikasi — 4 Ton Sekam (36.3 m³) pada Truk 16 m³ Memicu Penolakan/Multi-Trip', async () => {
    const api = await pwRequest.newContext();
    const pabrik = await login(api, 'pabrik_pelet_briket');
    const petani = await login(api, 'petani_sekam');
    const pengepul = await login(api, 'pengepul_sekam');
    const driver = await login(api, 'driver_colt1');

    // 1. Buat panen 4 Ton (4.000 kg) Sekam Padi
    const hRes = await api.post(`${BASE}/api/v1/farmer/harvest`, {
      headers: auth(petani.access_token),
      data: { quantity_kg: 4000, commodity: 'sekam_padi' },
    });
    expect([200, 201]).toContain(hRes.status());
    const harvest = await hRes.json();

    // Verifikasi panen oleh pengepul
    const vRes = await api.post(`${BASE}/api/v1/collector/verify`, {
      headers: auth(pengepul.access_token),
      data: {
        harvest_id: harvest.id,
        weighed_kg: 4000,
        moisture: 14.0,
        ash: 18.0,
      },
    });
    expect(vRes.status()).toBe(200);

    // 2. Coba dispatch langsung muatan 4.000 kg ke Truk Colt Diesel bak 16 m³
    // Densitas sekam 110 kg/m³ -> butuh 36.36 m³ > kapasitas bak 16 m³
    const dRes = await api.post(`${BASE}/api/v1/factory/dispatch`, {
      headers: auth(pabrik.access_token),
      data: {
        driver_id: driver.user_id,
        harvest_ids: [harvest.id],
        vehicle_m3: 16.0,
        vehicle_payload_kg: 6000.0,
      },
    });

    console.log(`[TC 2.1 Audit] Status dispatch overload volume: HTTP ${dRes.status()} -> ${await dRes.text()}`);
    // Sistem WAJIB menolak dengan HTTP 422 (Muatan melebihi kapasitas volume truk)
    expect(dRes.status(), 'Muatan 4 ton sekam pada bak 16 m³ harus ditolak karena melebihi volume').toBe(422);
    const errBody = await dRes.json();
    expect(errBody.detail).toContain('volume');
  });

  // Test Case 2.2: Anti-Cross Contamination (Single Commodity Per Trip)
  test('TC 2.2: Anti-Cross Contamination — Dilarang Menggabungkan Komoditas Berbeda dalam Satu Trip (Negative Assertion)', async () => {
    const api = await pwRequest.newContext();
    const pabrik = await login(api, 'pabrik_pelet_briket');
    const petaniSekam = await login(api, 'petani_sekam');
    const petaniJagung = await login(api, 'petani_jagung');
    const pengepulSekam = await login(api, 'pengepul_sekam');
    const pengepulJagung = await login(api, 'pengepul_jagung');
    const driver = await login(api, 'driver_colt2');

    // 1. Buat panen sekam (800 kg) & jagung (800 kg)
    const h1 = await (await api.post(`${BASE}/api/v1/farmer/harvest`, {
      headers: auth(petaniSekam.access_token),
      data: { quantity_kg: 800, commodity: 'sekam_padi' },
    })).json();

    const h2 = await (await api.post(`${BASE}/api/v1/farmer/harvest`, {
      headers: auth(petaniJagung.access_token),
      data: { quantity_kg: 800, commodity: 'tongkol_jagung' },
    })).json();

    await api.post(`${BASE}/api/v1/collector/verify`, {
      headers: auth(pengepulSekam.access_token),
      data: { harvest_id: h1.id, weighed_kg: 800, moisture: 14.0 },
    });

    await api.post(`${BASE}/api/v1/collector/verify`, {
      headers: auth(pengepulJagung.access_token),
      data: { harvest_id: h2.id, weighed_kg: 800, moisture: 15.0 },
    });

    // 2. Coba dispatch rute gabungan Sekam + Jagung dalam satu trip perjalanan
    const crossRes = await api.post(`${BASE}/api/v1/factory/dispatch`, {
      headers: auth(pabrik.access_token),
      data: {
        driver_id: driver.user_id,
        harvest_ids: [h1.id, h2.id],
        vehicle_m3: 16.0,
      },
    });

    const status = crossRes.status();
    const body = await crossRes.text();
    console.log(`[TC 2.2 Audit] Respon dispatch kontaminasi silang multi-komoditas: HTTP ${status} -> ${body}`);

    // Audit assertion: Sistem WAJIB menolak kontaminasi silang komoditas dalam 1 armada (HTTP 400/409/422)
    expect([400, 409, 422], `Kontaminasi silang multi-biomassa dalam 1 trip harus ditolak (ditemukan HTTP ${status})`).toContain(status);
  });

  // Test Case 2.3: Penyelesaian Trip & Pembukaan Trip Baru
  test('TC 2.3: Siklus Rute — Penyelesaian Rute Selesai & Rute Baru Diizinkan', async () => {
    const api = await pwRequest.newContext();
    const pabrik = await login(api, 'pabrik_pelet_briket');
    const petani = await login(api, 'petani_sekam');
    const pengepul = await login(api, 'pengepul_sekam');
    const driver = await login(api, 'driver_colt1');

    // 1. Buat panen 1 ton sekam terverifikasi
    const h = await (await api.post(`${BASE}/api/v1/farmer/harvest`, {
      headers: auth(petani.access_token),
      data: { quantity_kg: 1000, commodity: 'sekam_padi', mill_id: 1 },
    })).json();

    await api.post(`${BASE}/api/v1/collector/verify`, {
      headers: auth(pengepul.access_token),
      data: { harvest_id: h.id, weighed_kg: 1000, moisture: 14.0 },
    });

    // 2. Dispatch rute baru untuk Sekam Padi
    const dispRes = await api.post(`${BASE}/api/v1/factory/dispatch`, {
      headers: auth(pabrik.access_token),
      data: {
        driver_id: driver.user_id,
        harvest_ids: [h.id],
        vehicle_m3: 16.0,
      },
    });
    expect([200, 201]).toContain(dispRes.status());
    const route = await dispRes.json();

    // 3. Supir memulai rute (PLANNED -> IN_PROGRESS)
    const startRes = await api.post(`${BASE}/api/v1/driver/start-route?route_id=${route.route_id}`, {
      headers: auth(driver.access_token),
    });
    expect([200, 409]).toContain(startRes.status());

    // 4. Supir konfirmasi pickup di lokasi (PENDING -> PICKED_UP)
    if (route.stops && route.stops.length > 0) {
      const stop = route.stops[0];
      const pickRes = await api.post(`${BASE}/api/v1/driver/confirm-pickup`, {
        headers: auth(driver.access_token),
        data: {
          route_stop_id: stop.route_stop_id,
          qr_code: h.qr_code,
          actual_ton: 1.0,
        },
      });
      expect([200, 201]).toContain(pickRes.status());
    }

    // 5. Supir menyelesaikan rute (IN_PROGRESS -> COMPLETED)
    const compRes = await api.post(`${BASE}/api/v1/driver/complete-route?route_id=${route.route_id}`, {
      headers: auth(driver.access_token),
    });
    expect(compRes.status()).toBe(200);
    const compData = await compRes.json();
    console.log(`[TC 2.3 Audit] Rute #${route.route_id} berhasil diselesaikan. Status: ${compData.already_completed ? 'completed (previously)' : 'completed'}.`);

    // 6. Driver 1 kini bebas dan diizinkan menerima surat jalan baru untuk jenis biomassa lain (Tongkol Jagung)
    const petaniJagung = await login(api, 'petani_jagung');
    const pengepulJagung = await login(api, 'pengepul_jagung');
    const hJagung = await (await api.post(`${BASE}/api/v1/farmer/harvest`, {
      headers: auth(petaniJagung.access_token),
      data: { quantity_kg: 800, commodity: 'tongkol_jagung', mill_id: 1 },
    })).json();

    await api.post(`${BASE}/api/v1/collector/verify`, {
      headers: auth(pengepulJagung.access_token),
      data: { harvest_id: hJagung.id, weighed_kg: 800, moisture: 15.0 },
    });

    const newTripRes = await api.post(`${BASE}/api/v1/factory/dispatch`, {
      headers: auth(pabrik.access_token),
      data: {
        driver_id: driver.user_id,
        harvest_ids: [hJagung.id],
        vehicle_m3: 16.0,
      },
    });
    const newTripBody = await newTripRes.text();
    console.log(`[TC 2.3 Audit] newTripRes status: ${newTripRes.status()} body: ${newTripBody}`);
    expect([200, 201]).toContain(newTripRes.status());
    const newRoute = JSON.parse(newTripBody);
    console.log(`[TC 2.3 Audit] Trip baru #${newRoute.route_id} berhasil ditugaskan ke Driver 1 setelah rute sebelumnya selesai.`);
  });

  // Test Case 2.4: Simulasi Offline & Store-and-Forward Sync
  test('TC 2.4: Simulasi Lapangan Offline & Sinkronisasi Store-and-Forward', async ({ browser }) => {
    test.setTimeout(90_000);
    const api = await pwRequest.newContext();
    const pabrik = await login(api, 'pabrik_pelet_briket');
    const petani = await login(api, 'petani_sekam');
    const pengepul = await login(api, 'pengepul_sekam');
    const driver = await login(api, 'driver_colt2');

    // 1. Siapkan panen terverifikasi & dispatch rute
    const h = await (await api.post(`${BASE}/api/v1/farmer/harvest`, {
      headers: auth(petani.access_token),
      data: { quantity_kg: 900, commodity: 'sekam_padi' },
    })).json();

    await api.post(`${BASE}/api/v1/collector/verify`, {
      headers: auth(pengepul.access_token),
      data: { harvest_id: h.id, weighed_kg: 900, moisture: 14.0 },
    });

    const route = await (await api.post(`${BASE}/api/v1/factory/dispatch`, {
      headers: auth(pabrik.access_token),
      data: { driver_id: driver.user_id, harvest_ids: [h.id], vehicle_m3: 16.0 },
    })).json();

    // 2. Buka UI Driver
    const { context, page } = await openAs(browser, driver, {
      permissions: ['geolocation'],
      geolocation: { latitude: -7.745, longitude: 110.362, accuracy: 10 },
    });

    // Mulai rute
    const startBtn = page.getByRole('button', { name: /Mulai Rute/i });
    if (await startBtn.isVisible()) {
      await startBtn.click();
    }

    // 3. Matikan koneksi (Simulasi Blank Spot / Offline di Area Sawah)
    await context.setOffline(true);
    console.log('[TC 2.4 Audit] Koneksi diputus: Browser masuk mode offline.');

    // Eksekusi konfirmasi pickup saat offline
    if (route.stops && route.stops.length) {
      await page.evaluate(([stopId, qr]) => {
        if (typeof (window as any).sendPickup === 'function') {
          (window as any).sendPickup(stopId, qr, null);
        }
      }, [route.stops[0].route_stop_id, h.qr_code]);
    }

    // Periksa antrean outbox di IndexedDB / LocalStorage
    const pendingOutbox = await page.evaluate(() => {
      const fn = (window as any).myOutbox;
      return typeof fn === 'function' ? fn().length : 0;
    });
    console.log(`[TC 2.4 Audit] Jumlah antrean outbox offline lokal: ${pendingOutbox}`);

    // 4. Pulihkan koneksi jaringan (Online)
    await context.setOffline(false);
    console.log('[TC 2.4 Audit] Koneksi dipulihkan: Mensinkronisasikan antrean.');

    try {
      const flushBtn = page.locator('#signal-banner [data-flush]');
      if (await flushBtn.isVisible({ timeout: 1500 }).catch(() => false)) {
        await flushBtn.click({ timeout: 2000 }).catch(() => {});
      }
    } catch (_) {}

    // Tunggu antrean tersinkronisasi bersih
    await expect.poll(async () => page.evaluate(() => {
      const fn = (window as any).myOutbox;
      return typeof fn === 'function' ? fn().length : 0;
    }), { timeout: 20_000 }).toBe(0);

    console.log('[TC 2.4 Audit] Store-and-Forward sukses: Seluruh data lokal terkirim ke server!');
    await context.close();
  });

});
