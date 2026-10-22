import { test, expect, request as pwRequest, APIRequestContext } from '@playwright/test';

/**
 * E2E multi-biomassa (migrasi 018) — browser sungguhan:
 *  1. Petani melapor tongkol jagung lewat pilihan komoditas.
 *  2. Pengepul membuat gudang, mencatat stok masuk dengan pratinjau refraksi kadar air/kotoran (online),
 *     lalu mencatat lagi saat OFFLINE → masuk antrean dan terkirim saat sinyal kembali (idempoten).
 *  3. Pabrik melihat master biomassa (indeks alkali) dan ledger abu: abu gagal uji tidak bisa ke Poktan.
 *
 *   set DATABASE_URL=sqlite+aiosqlite:///e2e_mb.db && py -m uvicorn app.main:app --port 8766
 *   set BIOCHAIN_URL=http://127.0.0.1:8766 && npx -y @playwright/test@1.64.0 test tests/e2e_multibiomass.spec.ts --reporter=line
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

test('petani lapor tongkol jagung via pilihan komoditas', async ({ browser }) => {
  const api = await pwRequest.newContext();
  const petani = await login(api, 'petani_sugeng', 'sekam123');
  const { context, page } = await openAs(browser, petani);
  const sel = page.locator('#f-commodity');
  await expect(sel.locator('option[value=tongkol_jagung]')).toHaveCount(1, { timeout: 20_000 });
  await sel.selectOption('tongkol_jagung');
  await page.fill('#f-qty', '750');
  const resp = page.waitForResponse(r => r.url().includes('/api/v1/farmer/harvest') && r.request().method() === 'POST');
  await page.locator('#form-lapor-sekam [type=submit]').click();
  const body = await (await resp).json();
  expect(body.commodity).toBe('tongkol_jagung');
  await expect(page.locator('#modal-qr-title')).toContainText('Tongkol jagung');
  await context.close();
});

test('pengepul: gudang, pratinjau refraksi, catat stok online & offline', async ({ browser }) => {
  test.setTimeout(90_000);
  const api = await pwRequest.newContext();
  const pabrik = await login(api, 'pabrik_indmira', 'pabrik2026');
  await api.put(`${BASE}/api/v1/biomass/sekam_padi`, { headers: auth(pabrik.access_token),
    data: { changes: { base_price_per_kg: 450 }, source: 'harga pasar uji e2e' } });
  const pengepul = await login(api, 'pengepul_sleman', 'kud2026');
  const { context, page } = await openAs(browser, pengepul, { permissions: ['geolocation'],
    geolocation: { latitude: -7.72, longitude: 110.33, accuracy: 10 } });
  await page.locator('#fo-wh-new').click();
  const whName = `Gudang E2E ${Date.now() % 100000}`;
  await page.fill('#fo-wh-name', whName);
  await page.locator('dialog[open] button[value=yes]').click();
  const card = page.locator('#fo-wh .card', { hasText: whName });
  const mvBtn = card.locator('[data-fo-mv]');
  await expect(mvBtn).toBeVisible({ timeout: 15_000 });

  await mvBtn.click();
  await page.fill('#fo-mv-kg', '1000');
  await page.fill('#fo-mv-mc', '18');
  await page.fill('#fo-mv-ct', '5');
  await expect(page.locator('#fo-mv-prev')).toContainText('903,9', { timeout: 10_000 });   // 1000 × 0,97 × 0,82/0,88
  await expect(page.locator('#fo-mv-prev')).toContainText('Rp');
  await page.locator('dialog[open] button[value=yes]').click();
  await expect(card).toContainText('904', { timeout: 10_000 });

  // ---- tanpa sinyal: mutasi masuk antrean
  await context.setOffline(true);
  await mvBtn.click();
  await page.selectOption('#fo-mv-com', 'tongkol_jagung');
  await page.fill('#fo-mv-kg', '400');
  await page.fill('#fo-mv-mc', '15');
  await page.locator('dialog[open] button[value=yes]').click();
  await expect.poll(async () => page.evaluate('myOutbox().length'), { timeout: 10_000 }).toBe(1);
  await context.setOffline(false);
  await page.evaluate('flushOutbox()');
  await expect.poll(async () => page.evaluate('myOutbox().length'), { timeout: 20_000 }).toBe(0);
  const whs = await (await api.get(`${BASE}/api/v1/collector/warehouses`, { headers: auth(pengepul.access_token) })).json();
  const stock = whs.find((w: any) => w.name === whName).stock;
  expect(stock.find((s: any) => s.commodity === 'tongkol_jagung').gross_kg).toBe(400);
  await context.close();
});

test('pabrik: master biomassa & abu gagal uji tidak bisa ke Poktan', async ({ browser }) => {
  test.setTimeout(90_000);
  const api = await pwRequest.newContext();
  const pabrik = await login(api, 'pabrik_indmira', 'pabrik2026');
  const h = auth(pabrik.access_token);
  await api.post(`${BASE}/api/v1/factory/farmer-groups`, { headers: h,
    data: { name: 'Poktan E2E', kecamatan: 'Sleman', kabupaten: 'Sleman', leader_name: 'Ketua' } });
  const bad = await (await api.post(`${BASE}/api/v1/factory/ash`, { headers: h, data: { ash_type: 'fly_ash', quantity_kg: 300 } })).json();
  await api.post(`${BASE}/api/v1/factory/ash/${bad.id}/lab`, { headers: h,
    data: { pb_ppm: 80, cd_ppm: 1, as_ppm: 2, lab_report_no: 'E2E-GAGAL' } });
  const good = await (await api.post(`${BASE}/api/v1/factory/ash`, { headers: h, data: { ash_type: 'bottom_ash', quantity_kg: 200 } })).json();
  await api.post(`${BASE}/api/v1/factory/ash/${good.id}/lab`, { headers: h,
    data: { pb_ppm: 5, cd_ppm: 0.2, as_ppm: 1, lab_report_no: 'E2E-LULUS' } });

  const { context, page } = await openAs(browser, pabrik);
  await expect(page.locator('#fx-bm')).toContainText('Tongkol jagung', { timeout: 20_000 });
  await expect(page.locator('#fx-bm')).toContainText('belum diisi');                  // harga tanpa bawaan
  const rowBad = page.locator('#fx-ash tr', { hasText: bad.code });
  await expect(rowBad).toContainText('gagal', { timeout: 15_000 });
  await expect(rowBad).toContainText('Pb 80');
  await expect(rowBad.locator('[data-fx-ash-alloc]')).toHaveCount(0);                 // tidak ada tombol → Poktan
  const rowGood = page.locator('#fx-ash tr', { hasText: good.code });
  await expect(rowGood.locator('[data-fx-ash-alloc]')).toHaveCount(1);
  await rowGood.locator('[data-fx-ash-alloc]').click();
  await page.locator('dialog[open] button[value=yes]').click();
  await expect(rowGood).toContainText('dialokasikan', { timeout: 10_000 });
  await context.close();
});

test('prototipe 1: optimasi blend + slider memicu peringatan terak', async ({ browser }) => {
  test.setTimeout(90_000);
  const api = await pwRequest.newContext();
  const pabrik = await login(api, 'pabrik_indmira', 'pabrik2026');
  for (const [code, price] of [['tongkol_jagung', 650], ['serbuk_sengon', 500]] as const) {
    await api.put(`${BASE}/api/v1/biomass/${code}`, { headers: auth(pabrik.access_token),
      data: { changes: { base_price_per_kg: price }, source: 'harga uji e2e' } });
  }
  const { context, page } = await openAs(browser, pabrik);
  await expect(page.locator('[data-fb-use=tongkol_jagung]')).toBeVisible({ timeout: 20_000 });
  for (const cb of await page.locator('[data-fb-use]').all()) await cb.uncheck();
  for (const code of ['tongkol_jagung', 'serbuk_sengon']) {
    await page.locator(`[data-fb-use=${code}]`).check();
    await page.locator(`[data-fb-kg=${code}]`).fill('20000');
  }
  await page.selectOption('#fx-fb-preset', 'pelet_4000_kcal');
  await page.click('#fx-fb-go');
  await expect(page.locator('#fx-fb-out')).toContainText('LAYAK', { timeout: 15_000 });
  await expect(page.locator('#fx-fb-radar')).toBeVisible();
  const corn = page.locator('[data-fb-slide=tongkol_jagung]');
  const wood = page.locator('[data-fb-slide=serbuk_sengon]');
  await wood.fill('0');
  await corn.fill('100');
  await expect(page.locator('#fx-fb-warn')).toContainText('Risiko Tinggi Terak/Slagging pada Boiler Industri', { timeout: 10_000 });
  await expect(page.locator('#fx-fb-warn')).toContainText('BAHAYA');
  await context.close();
});

test('prototipe 2: kartu energi riil & rute konversi', async ({ browser }) => {
  test.setTimeout(60_000);
  const api = await pwRequest.newContext();
  const pabrik = await login(api, 'pabrik_indmira', 'pabrik2026');
  const { context, page } = await openAs(browser, pabrik);
  await expect(page.locator('#fx-cv-com option[value=serbuk_sengon]')).toHaveCount(1, { timeout: 20_000 });
  await page.selectOption('#fx-cv-com', 'sekam_padi');
  await page.fill('#fx-cv-t', '1000');
  await page.click('#fx-cv-go');
  await expect(page.locator('#fx-cv-out')).toContainText('Pirolisis lambat', { timeout: 10_000 });
  await expect(page.locator('#fx-cv-out')).toContainText('MWh/bulan');
  await page.selectOption('#fx-cv-com', 'serbuk_sengon');
  await page.fill('#fx-cv-mc', '20');
  await page.fill('#fx-cv-km', '40');
  await page.click('#fx-cv-go');
  await expect(page.locator('#fx-cv-out .banner-info')).toContainText('Co-firing PLTU', { timeout: 10_000 });
  await context.close();
});
