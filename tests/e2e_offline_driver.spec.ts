import { test, expect, request as pwRequest, APIRequestContext } from '@playwright/test';

/**
 * E2E Offline-First Driver (Fase 5 audit SOP) — browser sungguhan, jaringan dimatikan.
 *
 * Skenario lapangan:
 *  1. Supir mulai rute saat masih ada sinyal (GPS mulai merekam).
 *  2. Sinyal hilang di jalan desa: GPS tetap merekam titik ke IndexedDB, scan QR pickup masuk antrean.
 *  3. Kasus terburuk: server SUDAH memproses pickup tetapi respons hilang di jalan (sinyal putus di tengah).
 *     Klien menganggap gagal → mengantre → mengirim ulang dengan client_event_id yang sama.
 *  4. Sinyal kembali → antrean & jejak GPS tersinkron otomatis.
 *  Bukti: tepat SATU event custody driver_pickup per panen, jejak GPS tersimpan, rute bisa diselesaikan
 *  dengan emisi berbasis GPS.
 *
 * Jalankan (server demo SQLite bersih di port 8000):
 *   set DATABASE_URL=sqlite+aiosqlite:///e2e_offline.db && py -m uvicorn app.main:app --port 8000
 *   npx -y @playwright/test@1.64.0 test tests/e2e_offline_driver.spec.ts --reporter=line
 */
const BASE = process.env.BIOCHAIN_URL || 'http://127.0.0.1:8000';

async function login(api: APIRequestContext, identifier: string, password: string) {
  const r = await api.post(`${BASE}/api/v1/auth/login`, { data: { identifier, password } });
  expect(r.status(), await r.text()).toBe(200);
  return r.json();
}
const auth = (t: string) => ({ Authorization: `Bearer ${t}` });

test('driver offline: pickup & GPS tersimpan, respons hilang tidak menggandakan data', async ({ browser }) => {
  test.setTimeout(120_000);
  const api = await pwRequest.newContext();
  const petani = await login(api, 'petani_sugeng', 'sekam123');
  const pengepul = await login(api, 'pengepul_sleman', 'kud2026');
  const pabrik = await login(api, 'pabrik_indmira', 'pabrik2026');
  const supir = await login(api, 'sopir_budi', 'truk2026');

  // Siapkan dua panen terverifikasi di dua penggilingan → satu rute untuk supir
  const mills = await (await api.get(`${BASE}/api/v1/farmer/mills`, { headers: auth(petani.access_token) })).json();
  const harvests = [];
  for (const mill of mills.slice(0, 2)) {
    const h = await (await api.post(`${BASE}/api/v1/farmer/harvest`, { headers: auth(petani.access_token),
      data: { quantity_kg: 800, mill_id: mill.id } })).json();
    const v = await api.post(`${BASE}/api/v1/collector/verify`, { headers: auth(pengepul.access_token),
      data: { harvest_id: h.id, weighed_kg: 800, moisture: 11, ash: 18, volatile_matter: 66, fixed_carbon: 16 } });
    expect(v.status(), await v.text()).toBe(200);
    harvests.push(h);
  }
  // Rute aktif lama milik supir demo (seed) dibatalkan agar rute uji yang tampil
  const old = await (await api.get(`${BASE}/api/v1/factory/routes?limit=200`, { headers: auth(pabrik.access_token) })).json();
  for (const r of old.filter((x: any) => x.driver_id === supir.user_id && ['planned', 'in_progress'].includes(x.status))) {
    await api.post(`${BASE}/api/v1/factory/routes/${r.route_id}/cancel`, { headers: auth(pabrik.access_token),
      data: { reason: 'persiapan uji e2e offline' } });
    for (const st of r.stops.filter((s: any) => s.status === 'picked_up')) {
      await api.post(`${BASE}/api/v1/driver/complete-route?route_id=${r.route_id}`, { headers: auth(supir.access_token) });
    }
    await api.post(`${BASE}/api/v1/driver/complete-route?route_id=${r.route_id}`, { headers: auth(supir.access_token) });
  }
  const route = await (await api.post(`${BASE}/api/v1/factory/dispatch`, { headers: auth(pabrik.access_token),
    data: { driver_id: supir.user_id, harvest_ids: harvests.map(h => h.id) } })).json();
  expect(route.route_id).toBeTruthy();

  // Browser supir: geolokasi diizinkan, posisi awal di pabrik
  const context = await browser.newContext({ permissions: ['geolocation'],
    geolocation: { latitude: -7.745, longitude: 110.362, accuracy: 10 } });
  const page = await context.newPage();
  await page.goto(BASE);
  await page.evaluate(([tok, user]) => {
    localStorage.setItem('biochain_token', tok);
    localStorage.setItem('biochain_user', JSON.stringify(user));
  }, [supir.access_token, supir]);
  await page.reload();
  await page.getByRole('button', { name: /Mulai Rute/ }).click();
  await expect(page.locator('#driver-actions')).toContainText('GPS merekam', { timeout: 15_000 });

  // ---- Sinyal hilang. GPS tetap jalan: truk bergerak ke penggilingan pertama.
  await context.setOffline(true);
  // Gerak realistis ±33 m tiap 1,2 detik (≈100 km/jam): lompatan tak wajar dibuang penyaring glitch server
  for (let i = 1; i <= 14; i++) {
    await context.setGeolocation({ latitude: -7.745 - 0.0003 * i, longitude: 110.362, accuracy: 8 });
    await page.waitForTimeout(1200);
  }
  // Pickup stop 1 saat offline → masuk antrean (scanner kamera digantikan pemanggilan langsung hasil scan)
  await page.evaluate(([stopId, qr]) => (window as any).sendPickup(stopId, qr, null),
    [route.stops[0].route_stop_id, harvests[0].qr_code]);
  // Banner sinyal (menggantikan pill lama): Mode Hemat Sinyal + jumlah antrean & titik GPS
  await expect(page.locator('#signal-banner')).toContainText('Mode Hemat Sinyal');
  await expect(page.locator('#signal-banner')).toContainText('antre');
  await expect(page.locator('#signal-banner')).toContainText('titik GPS');

  // ---- Sinyal setengah-hidup: request stop 2 SAMPAI ke server, respons hilang di jalan.
  await context.setOffline(false);
  let lostOnce = false;
  await page.route('**/api/v1/driver/confirm-pickup', async r => {
    const body = r.request().postDataJSON();
    if (!lostOnce && body.route_stop_id === route.stops[1].route_stop_id) {
      lostOnce = true;
      await r.fetch();          // server memproses & commit…
      return r.abort('connectionreset');   // …tetapi respons tidak pernah sampai ke HP
    }
    return r.continue();
  });
  await page.evaluate(([stopId, qr]) => (window as any).sendPickup(stopId, qr, null),
    [route.stops[1].route_stop_id, harvests[1].qr_code]);
  expect(lostOnce).toBe(true);

  // ---- Sinyal pulih: antrean & GPS tersinkron (event 'online' / tombol "Kirim sekarang" di banner sinyal)
  const flush = page.locator('#signal-banner [data-flush]');
  if (await flush.isVisible().catch(() => false)) await flush.click();
  await expect.poll(async () => page.evaluate('myOutbox().length'), { timeout: 20_000 }).toBe(0);
  await expect.poll(async () => page.evaluate('TRACK.pending'), { timeout: 20_000 }).toBe(0);

  // Bukti tidak ganda: tepat satu driver_pickup per panen
  for (const h of harvests) {
    const mb = await (await api.get(`${BASE}/api/v1/factory/mass-balance/${h.id}`,
      { headers: auth(pabrik.access_token) })).json();
    const pickups = mb.custody_trail.filter((e: any) => e.stage === 'driver_pickup');
    expect(pickups.length, JSON.stringify(mb.custody_trail)).toBe(1);
    expect(mb.status).toBe('collected');
  }
  // Rute bisa diselesaikan; jarak dari GPS yang direkam saat offline
  const done = await (await api.post(`${BASE}/api/v1/driver/complete-route?route_id=${route.route_id}`,
    { headers: auth(supir.access_token) })).json();
  expect(done.emissions.distance_source).toBe('gps');
  expect(done.emissions.total_km).toBeGreaterThan(0.2);   // ±0,4 km terekam saat offline
  expect(done.emissions.co2e_wtw_kg).toBeGreaterThan(0);
  await context.close();
});
