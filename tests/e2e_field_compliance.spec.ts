import { test, expect, request as pwRequest, Page } from '@playwright/test';

/**
 * E2E Kepatuhan Lapangan — F7 petani tanpa HP, F8 bukti bayar petani, F12 UU PDP (UI sungguhan).
 *
 *  1. Pengepul mendaftarkan petani tanpa HP (persetujuan lisan wajib dicentang) → lapor sekam atas namanya
 *     → nota QR → timbang & uji → resi TRX → "Bayar petani" → kuitansi BYR (Rupiah bulat).
 *  2. Nomor petani disamarkan di daftar; tombol 📞 membuka nomor lengkap. Petani membuka "🔒 Data saya" dan
 *     mengunduh datanya (JSON berisi profil & laporan).
 *
 *   set DATABASE_URL=sqlite+aiosqlite:///e2e_fc.db && py -m uvicorn app.main:app --port 8766
 *   set BIOCHAIN_URL=http://127.0.0.1:8766 && npx -y @playwright/test@1.64.0 test tests/e2e_field_compliance.spec.ts
 */
const BASE = process.env.BIOCHAIN_URL || 'http://127.0.0.1:8000';

async function openAs(page: Page, role: string) {
  await page.goto(`${BASE}/?role=${role}`);
  await expect(page.locator('html')).toHaveAttribute('data-role', role, { timeout: 30_000 });
}
const closeModal = (page: Page) => page.locator('#qr-modal.open .btn-icon').click();

test('petani tanpa HP: daftar → lapor → timbang → bayar → kuitansi BYR', async ({ browser }) => {
  test.setTimeout(150_000);
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  await openAs(page, 'pengepul');
  const name = `Mbah Uji ${Date.now() % 100000}`;

  // Daftarkan petani binaan — tanpa centang persetujuan form tidak terkirim
  await page.locator('#fo-proxy-new').click();
  const dlg = page.locator('dialog.ui-confirm[open]');
  await dlg.getByLabel('Nama petani').fill(name);
  await dlg.getByLabel('Desa / dusun').fill('Sidoarum');
  await dlg.locator('button[value="yes"]').click();
  await expect(dlg).toBeVisible();                                       // checkbox wajib belum dicentang
  await dlg.getByRole('checkbox').check();
  await dlg.locator('button[value="yes"]').click();
  await expect(page.locator('#toast-msg')).toContainText('Petani binaan terdaftar');

  // Lapor sekam atas namanya → nota QR
  await page.locator(`[data-fo-report][data-name^="${name}"]`).click();
  const rep = page.locator('dialog.ui-confirm[open]');
  await rep.getByLabel('Jumlah sekam (kg)').fill('1500');
  await rep.locator('button[value="yes"]').click();
  await expect(page.locator('#modal-qr-title')).toContainText('Nota sekam');
  const qr = (await page.locator('#modal-qr-code').innerText()).trim();
  expect(qr).toMatch(/^BIO-[0-9A-F]{8}$/);
  await closeModal(page);

  // Timbang & uji lot tersebut di antrean
  const api = await pwRequest.newContext();
  const tok = await page.evaluate(() => localStorage.getItem('biochain_token'));
  const avail = await (await api.get(`${BASE}/api/v1/collector/available-harvests`, { headers: { Authorization: `Bearer ${tok}` } })).json();
  const lot = (Array.isArray(avail) ? avail : avail.items).find((h: any) => h.qr_code === qr);
  expect(lot.farmer_without_phone).toBe(true);
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-role', 'pengepul', { timeout: 20_000 });
  await page.locator(`button[data-onclick="selectVerifyItem(${lot.id})"]`).click();
  await page.locator('#v-weight').fill('1480');
  await page.locator('#v-moisture').fill('11.5');                     // wajib: bacaan moisture meter (F9)
  await page.locator('#btn-submit-verify').click();
  await expect(page.locator('#modal-qr-title')).toHaveText('Resi Serah-Terima Sekam', { timeout: 20_000 });
  await closeModal(page);

  // Bayar petani → kuitansi
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-role', 'pengepul', { timeout: 20_000 });
  const pay = page.locator(`[data-fo-pay="${lot.id}"]`);
  await expect(pay).toBeVisible({ timeout: 15_000 });
  await pay.click();
  const pd = page.locator('dialog.ui-confirm[open]');
  await pd.getByLabel('Metode').selectOption('qris');
  await pd.locator('button[value="yes"]').click();
  await expect(pd.locator('.form-error')).toContainText('referensi');      // QRIS wajib nomor referensi
  await pd.getByLabel(/No. referensi/).fill('QRIS-889900');
  await pd.locator('button[value="yes"]').click();
  await expect(page.locator('#modal-qr-title')).toHaveText('Kuitansi bayar petani', { timeout: 15_000 });
  await expect(page.locator('#modal-qr-code')).toHaveText(/^\s*BYR-PGP\d{4}-PTN\d{4}-\d{4}-\d{5}\s*$/);
  await expect(page.locator('#modal-qr-sub')).toContainText('QRIS');
  await closeModal(page);
  await expect(page.locator(`[data-fo-pay="${lot.id}"]`)).toHaveCount(0);
  await ctx.close(); await api.dispose();
});

test('PDP: nomor disamarkan + tombol hubungi; petani mengunduh data saya', async ({ browser }) => {
  test.setTimeout(120_000);
  const ctxP = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const pg = await ctxP.newPage();
  await openAs(pg, 'pengepul');
  await expect(pg.locator('#table-col-queue [data-fo-contact]').first()).toBeVisible({ timeout: 20_000 });
  const body = await pg.locator('#table-col-queue').innerText();
  expect(body).not.toMatch(/\b08\d{8,11}\b/);                               // tidak ada nomor lengkap di daftar
  // API daftar juga hanya memberi nomor tersamar; pilih lot yang petaninya punya HP lalu buka kontak
  const api = await pwRequest.newContext();
  const tok = await pg.evaluate(() => localStorage.getItem('biochain_token'));
  const list = await (await api.get(`${BASE}/api/v1/collector/available-harvests`, { headers: { Authorization: `Bearer ${tok}` } })).json();
  const withPhone = (Array.isArray(list) ? list : list.items).find((h: any) => h.farmer_phone);
  expect(withPhone.farmer_phone).toContain('*');
  // Tombol 💬 WA: nomor lengkap hanya dipakai untuk membuka wa.me (akses tercatat server, UU PDP)
  await ctxP.route('https://wa.me/**', route => route.fulfill({ status: 200, contentType: 'text/html', body: 'wa' }));
  const [popup] = await Promise.all([
    pg.waitForEvent('popup'),
    pg.locator(`[data-fo-contact="${withPhone.id}"]`).click(),
  ]);
  await popup.waitForURL(/^https:\/\/wa\.me\/628\d{7,11}\?text=/, { timeout: 15_000 });
  expect(decodeURIComponent(popup.url())).toContain(`lot #${withPhone.id}`);
  await expect(pg.locator('#toast-msg')).toContainText('tercatat');
  await ctxP.close(); await api.dispose();

  const ctxF = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, acceptDownloads: true });
  const pf = await ctxF.newPage();
  await openAs(pf, 'petani');
  await pf.locator('#btn-privacy').click();
  const dlg = pf.locator('dialog.ui-confirm[open]');
  await expect(dlg).toContainText('UU 27/2022');
  const [download] = await Promise.all([pf.waitForEvent('download'), dlg.locator('#fo-export').click()]);
  const path = await download.path();
  const data = JSON.parse(require('fs').readFileSync(path!, 'utf8'));
  expect(data.profile.role).toBe('petani');
  expect(Array.isArray(data.harvests)).toBe(true);
  expect(data.receipt_code).toMatch(/^PDP-EKS-/);
  await ctxF.close();
});
