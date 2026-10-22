import { test, expect, request as pwRequest } from '@playwright/test';

/**
 * E2E Keamanan & Lapangan:
 *  1. CSP ketat — semua dashboard peran dimuat tanpa satu pun pelanggaran Content-Security-Policy
 *     (skrip inline/handler inline akan terblokir dan tercatat di sini).
 *  2. Foto offline — pengepul memotret bukti tanpa sinyal: foto disimpan di HP (IndexedDB), hasil uji masuk antrean;
 *     saat sinyal kembali foto diunggah DULU lalu hasil uji terkirim membawa URL foto asli (/uploads/…), tepat sekali.
 *
 *   set BIOCHAIN_URL=http://127.0.0.1:8765 && npx -y @playwright/test@1.64.0 test tests/e2e_csp_offline_photo.spec.ts
 */
const BASE = process.env.BIOCHAIN_URL || 'http://127.0.0.1:8000';

for (const role of ['petani', 'pengepul', 'driver', 'pabrik', 'auditor', 'admin']) {
  test(`CSP tanpa pelanggaran: ${role}`, async ({ page }) => {
    const violations: string[] = [];
    page.on('console', m => { if (/Content Security Policy|Refused to (execute|load|apply)/i.test(m.text())) violations.push(m.text()); });
    await page.addInitScript(() => document.addEventListener('securitypolicyviolation',
      e => console.error(`Refused to execute (CSP) ${e.violatedDirective} ${e.blockedURI}`)));
    await page.goto(`${BASE}/?role=${role}`);
    await expect(page.locator('#app-view')).toBeVisible({ timeout: 30_000 });
    await page.waitForTimeout(2500);
    // tombol deklaratif (data-onclick) tetap berfungsi: buka tab Laporan Bulanan bila ada
    const nav = page.locator('.nav-btn[data-tab="tab-reports"]');
    if (await nav.isVisible()) { await nav.click(); await expect(page.locator('#tab-reports')).toHaveClass(/active/); }
    expect(violations, violations.join('\n')).toEqual([]);
  });
}

test('foto bukti offline tersimpan di HP lalu terkirim bersama hasil uji saat online', async ({ browser }) => {
  test.setTimeout(120_000);
  const api = await pwRequest.newContext();
  const login = await (await api.post(`${BASE}/api/v1/auth/login`, { data: { identifier: 'petani_sugeng', password: 'sekam123' } })).json();
  const h = await (await api.post(`${BASE}/api/v1/farmer/harvest`, { headers: { Authorization: `Bearer ${login.access_token}` },
                                                                      data: { quantity_kg: 1300 } })).json();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const pg = await ctx.newPage();
  await pg.goto(`${BASE}/?role=pengepul`);
  await expect(pg.locator('#app-view')).toBeVisible({ timeout: 30_000 });
  await pg.locator(`button[data-onclick="selectVerifyItem(${h.id})"]`).click();

  await ctx.setOffline(true);
  // Kamera HP → file JPEG 3000×2000 (dibuat di browser), dipilih lewat input kamera pemilih foto
  await pg.evaluate(async () => {
    const c = document.createElement('canvas'); c.width = 3000; c.height = 2000;
    const g = c.getContext('2d')!; g.fillStyle = '#a0522d'; g.fillRect(0, 0, 3000, 2000);
    for (let i = 0; i < 4000; i++) { g.fillStyle = `hsl(${i % 360},60%,50%)`; g.fillRect((i * 37) % 3000, (i * 53) % 2000, 40, 40); }
    const blob: Blob = await new Promise(r => c.toBlob(b => r(b!), 'image/jpeg', 0.95));
    const input = document.getElementById('v-photo-cam') as HTMLInputElement;
    const dt = new DataTransfer(); dt.items.add(new File([blob], 'karung.jpg', { type: 'image/jpeg' }));
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await expect(pg.locator('#v-photo')).toHaveValue(/^pending-photo:/, { timeout: 15_000 });
  await expect(pg.locator('.photo-pick-status').first()).toContainText('disimpan di HP');
  await pg.locator('#v-weight').fill('1280');
  await pg.locator('#v-moisture').fill('11');
  await pg.locator('#btn-submit-verify').click();
  await expect(pg.locator('#toast-msg')).toContainText('Offline', { timeout: 10_000 });

  const uploads: string[] = [];
  pg.on('request', r => { if (r.url().includes('/api/v1/uploads') && r.method() === 'POST') uploads.push(r.url()); });
  const verifyReq = pg.waitForRequest(r => r.url().includes('/api/v1/collector/verify') && r.method() === 'POST', { timeout: 45_000 });
  await ctx.setOffline(false);
  const body = JSON.parse((await verifyReq).postData() || '{}');
  expect(body.harvest_id).toBe(h.id);
  expect(body.evidence_photo_url).toMatch(/^\/uploads\/[0-9a-f]{40}\.(jpg|jpeg|webp|png)$/);
  expect(uploads.length).toBe(1);                                     // foto diunggah tepat sekali, sebelum hasil uji
  await expect(pg.locator('#net-pill')).toBeHidden({ timeout: 20_000 });  // antrean & foto kosong
  const stored = await pg.evaluate(() => new Promise<number>(res => {
    const r = indexedDB.open('biochain-offline'); r.onsuccess = () => {
      const q = r.result.transaction('photos').objectStore('photos').count(); q.onsuccess = () => res(q.result); };
  }));
  expect(stored).toBe(0);
  await ctx.close(); await api.dispose();
});
