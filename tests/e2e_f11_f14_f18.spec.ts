import { test, expect, request as pwRequest, APIRequestContext } from '@playwright/test';

/**
 * E2E celah F11 / F14 / F18 (browser sungguhan):
 *  F14  QR bertanda tangan: HP supir mencocokkan QR di lokasi TANPA sinyal (digest rute), QR salah langsung ditolak.
 *  F18  HP bersama: titik GPS milik supir lain tidak dikirim/dihapus oleh supir yang sedang masuk, dan ada pemberitahuan.
 *  F11  Klaim karbon: pabrik melihat pratinjau + penghalang; auditor melihat kartu klaim tanpa formulir pengajuan.
 *
 * Jalankan (server demo SQLite bersih):
 *   set DATABASE_URL=sqlite+aiosqlite:///e2e_f.db && py -m uvicorn app.main:app --port 8766
 *   set BIOCHAIN_URL=http://127.0.0.1:8766 && npx -y @playwright/test@1.64.0 test tests/e2e_f11_f14_f18.spec.ts --reporter=line
 */
const BASE = process.env.BIOCHAIN_URL || 'http://127.0.0.1:8000';

async function login(api: APIRequestContext, identifier: string, password: string) {
  const r = await api.post(`${BASE}/api/v1/auth/login`, { data: { identifier, password } });
  expect(r.status(), await r.text()).toBe(200);
  return r.json();
}
const auth = (t: string) => ({ Authorization: `Bearer ${t}` });

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

test('F14 + F18: cek QR offline di HP supir & data supir lain di HP bersama tetap aman', async ({ browser }) => {
  test.setTimeout(120_000);
  const api = await pwRequest.newContext();
  const petani = await login(api, 'petani_sugeng', 'sekam123');
  const pengepul = await login(api, 'pengepul_sleman', 'kud2026');
  const pabrik = await login(api, 'pabrik_indmira', 'pabrik2026');
  const supir = await login(api, 'sopir_budi', 'truk2026');

  const mills = await (await api.get(`${BASE}/api/v1/farmer/mills`, { headers: auth(petani.access_token) })).json();
  const h = await (await api.post(`${BASE}/api/v1/farmer/harvest`, { headers: auth(petani.access_token),
    data: { quantity_kg: 700, mill_id: mills[0].id } })).json();
  expect(h.qr_code).toMatch(/^BIO-[0-9A-F]{8}-[A-Z2-7]{6}$/);                 // format bertanda tangan
  const v = await api.post(`${BASE}/api/v1/collector/verify`, { headers: auth(pengepul.access_token),
    data: { harvest_id: h.id, weighed_kg: 700, moisture: 11 } });
  expect(v.status(), await v.text()).toBe(200);
  const old = await (await api.get(`${BASE}/api/v1/factory/routes?limit=200`, { headers: auth(pabrik.access_token) })).json();
  for (const r of old.filter((x: any) => x.driver_id === supir.user_id && ['planned', 'in_progress'].includes(x.status))) {
    await api.post(`${BASE}/api/v1/factory/routes/${r.route_id}/cancel`, { headers: auth(pabrik.access_token),
      data: { reason: 'persiapan uji e2e F14' } });
    await api.post(`${BASE}/api/v1/driver/complete-route?route_id=${r.route_id}`, { headers: auth(supir.access_token) });
  }
  const route = await (await api.post(`${BASE}/api/v1/factory/dispatch`, { headers: auth(pabrik.access_token),
    data: { driver_id: supir.user_id, harvest_ids: [h.id] } })).json();
  const stopId = route.stops[0].route_stop_id;

  const { context, page } = await openAs(browser, supir, { permissions: ['geolocation'],
    geolocation: { latitude: -7.745, longitude: 110.362, accuracy: 10 } });
  // Rute tersimpan per pengguna (F18), memuat digest QR tetapi tidak kodenya (F14)
  await expect.poll(() => page.evaluate((uid: number) => localStorage.getItem(`biochain_driver_route:${uid}`), supir.user_id),
    { timeout: 15_000 }).not.toBeNull();
  const cached = await page.evaluate((uid: number) => localStorage.getItem(`biochain_driver_route:${uid}`), supir.user_id);
  expect(cached).not.toContain(h.qr_code);

  // ---- Tanpa sinyal di penggilingan
  await context.setOffline(true);
  const wrong = h.qr_code.slice(0, -1) + (h.qr_code.endsWith('A') ? 'B' : 'A');
  expect(await page.evaluate(([s, c]: any) => (window as any).qrMatchesStop(s, c), [stopId, wrong])).toBe(false);
  expect(await page.evaluate(([s, c]: any) => (window as any).qrMatchesStop(s, c), [stopId, ` ${h.qr_code.toLowerCase()} `])).toBe(true);

  // ---- F18: titik GPS supir lain (HP bersama) ada di IndexedDB
  await page.evaluate(() => (window as any).idbTx('track', 'readwrite', (s: any) => s.put({
    client_point_id: 'lain-1', route_id: 999999, user_id: 424242, owner_name: 'Supir Lain',
    recorded_at: new Date().toISOString(), lat: -7.7, lon: 110.3, accuracy_m: 5, speed_mps: null })));
  await context.setOffline(false);
  await page.evaluate(() => (window as any).trackFlush());
  const kept = await page.evaluate(() => (window as any).idbTx('track', 'readonly', (s: any) => s.get('lain-1')));
  expect(kept, 'titik supir lain tidak boleh dikirim/dihapus').toBeTruthy();
  await page.evaluate(() => (window as any).trackCount());
  expect(await page.evaluate('TRACK.pending')).toBe(0);                          // tidak dihitung sebagai milik saya
  await page.evaluate(() => (window as any).foreignPendingNotice());
  await expect(page.locator('#toast-msg')).toContainText('Supir Lain');
  await context.close();
});

test('F11: pabrik pratinjau klaim dengan penghalang; auditor melihat daftar klaim', async ({ browser }) => {
  test.setTimeout(90_000);
  const api = await pwRequest.newContext();
  const pabrik = await login(api, 'pabrik_indmira', 'pabrik2026');
  const auditor = await login(api, 'auditor_esg', 'audit2026');

  const { context, page } = await openAs(browser, pabrik);
  const form = page.locator('#fx-cc-form');
  await expect(form).toBeVisible({ timeout: 20_000 });
  await page.fill('#fx-cc-corg', '42');
  await page.fill('#fx-cc-hc', '0.85');                                          // di atas batas Puro 0,7
  await page.fill('#fx-cc-lab', 'Lab Tanah Uji');
  await page.fill('#fx-cc-no', 'LT-E2E-1');
  await page.setInputFiles('#fx-cc-photo', { name: 'lab.png', mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64') });
  await page.click('#fx-cc-form button[data-mode=preview]');
  await expect(page.locator('#fx-cc-preview')).toContainText('H/C-org', { timeout: 15_000 });
  await expect(page.locator('#fx-cc-submit')).toBeDisabled();
  await context.close();

  const a = await openAs(browser, auditor);
  await expect(a.page.locator('#fx-cc-title')).toBeVisible({ timeout: 20_000 });
  await expect(a.page.locator('#fx-cc-form')).toHaveCount(0);                    // auditor tidak mengajukan
  await expect(a.page.locator('#fx-cc')).not.toContainText('Memuat', { timeout: 15_000 });
  await a.context.close();
});
