import { test, expect, request as pwRequest, APIRequestContext, Page } from '@playwright/test';

/**
 * E2E Ergonomi Lapangan (Fase 5) — dari sudut pandang pengguna, browser sungguhan.
 *
 *  1. Lelang → kontrak → resi bulanan:
 *     pengepul menawar di Bursa (dialog konfirmasi berisi ringkasan; klik ganda tidak menggandakan tawaran),
 *     petani menerima (konfirmasi → QR kontrak), pengepul menimbang memakai stepper ±kg lalu menerima
 *     resi serah-terima unik `TRX-<PTN0006>-<PGP0003>-<YYMM>-<urut 5 digit>` (app/services/trx_code.py).
 *  2. Mode Hemat Sinyal: jaringan dimatikan → banner tampil, laporan petani masuk antrean HP;
 *     jaringan kembali → terkirim otomatis TEPAT SATU kali, banner hilang.
 *
 * Jalankan (server demo SQLite bersih):
 *   set DATABASE_URL=sqlite+aiosqlite:///e2e_ux.db && py -m uvicorn app.main:app --port 8765
 *   set BIOCHAIN_URL=http://127.0.0.1:8765 && npx -y @playwright/test@1.64.0 test tests/e2e_field_ux.spec.ts --reporter=line
 */
const BASE = process.env.BIOCHAIN_URL || 'http://127.0.0.1:8000';
const auth = (t: string) => ({ Authorization: `Bearer ${t}` });

async function login(api: APIRequestContext, identifier: string, password: string) {
  const r = await api.post(`${BASE}/api/v1/auth/login`, { data: { identifier, password } });
  expect(r.status(), await r.text()).toBe(200);
  return r.json();
}

async function openAs(page: Page, role: string) {
  await page.goto(`${BASE}/?role=${role}`);
  await expect(page.locator('#app-view')).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('html')).toHaveAttribute('data-role', role, { timeout: 15_000 });
}

test('lelang: konfirmasi tawaran → terima → timbang dengan stepper → resi TRX bulanan', async ({ browser }) => {
  test.setTimeout(150_000);
  const api = await pwRequest.newContext();
  const petani = await login(api, 'petani_sugeng', 'sekam123');
  const pengepul = await login(api, 'pengepul_sleman', 'kud2026');

  // Setup data via API: petani memasang stok 3.000 kg skema jemput (batas Rp420/kg)
  const lr = await api.post(`${BASE}/api/v1/farmer/listings`, { headers: auth(petani.access_token),
    data: { quantity_kg: 3000, allow_jemput: true, ask_price_jemput: 420, allow_antar: false } });
  expect(lr.status(), await lr.text()).toBeLessThan(300);
  const listing = await lr.json();
  const listingId = listing.id ?? listing.listing_id;

  // --- Pengepul menawar lewat UI
  const ctxP = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const pg = await ctxP.newPage();
  await openAs(pg, 'pengepul');
  // Dashboard penawaran bertab: lot skema jemput masuk tab Lelang (default tab = Langsung)
  await pg.locator('#btn-tab-lelang').click();
  const price = pg.locator(`#bp-${listingId}`);
  await expect(price).toBeVisible({ timeout: 20_000 });
  await price.fill('460');
  await pg.locator(`button[data-onclick^="placeBid(${listingId},"]`).click();
  const dlg = pg.locator('dialog.ui-confirm');
  await expect(dlg).toBeVisible();
  await expect(dlg).toContainText('Kirim tawaran lelang');
  await expect(dlg).toContainText('Rp 460/kg');
  await expect(dlg).toContainText('Rp 1.380.000');        // 3.000 kg × Rp460
  await dlg.locator('button[value="yes"]').dblclick();   // klik ganda: dialog menutup pada klik pertama
  await expect(pg.locator('#toast-msg')).toContainText('Tawaran terkirim', { timeout: 15_000 });

  const bids = await (await api.get(`${BASE}/api/v1/farmer/listings/${listingId}/bids`,
    { headers: auth(petani.access_token) })).json();
  const mine = bids.bids.filter((b: any) => b.price_per_kg === 460);
  expect(mine.length, 'tepat satu tawaran walau tombol diklik ganda').toBe(1);

  // --- Petani menerima lewat UI (konfirmasi → kontrak QR)
  const ctxF = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const pf = await ctxF.newPage();
  await openAs(pf, 'petani');
  await pf.locator(`button[data-onclick="showBids(${listingId})"]`).click();
  const pick = pf.locator(`button[data-onclick^="acceptBid(${listingId}, ${mine[0].bid_id},"]`);
  await expect(pick).toBeVisible({ timeout: 15_000 });
  const box = await pick.boundingBox();
  expect(box!.height, 'target sentuh petani ≥ 36 px (btn-sm) / 48 px untuk aksi utama').toBeGreaterThanOrEqual(36);
  await pick.click();
  const dlgF = pf.locator('dialog.ui-confirm');
  await expect(dlgF).toContainText('Terima tawaran ini?');
  await dlgF.locator('button[value="yes"]').click();
  await expect(pf.locator('#qr-modal.open')).toBeVisible({ timeout: 15_000 });
  await expect(pf.locator('#modal-qr-title')).toHaveText('Kontrak Lelang');
  const contractQr = (await pf.locator('#modal-qr-code').innerText()).trim();

  // --- Pengepul menimbang kontrak memakai stepper → resi TRX
  const avail = await (await api.get(`${BASE}/api/v1/collector/available-harvests`,
    { headers: auth(pengepul.access_token) })).json();
  const contract = (Array.isArray(avail) ? avail : avail.items || []).find((h: any) => h.qr_code === contractQr);
  expect(contract, `panen kontrak ${contractQr} masuk antrean pengepul`).toBeTruthy();
  await pg.reload();
  await expect(pg.locator('html')).toHaveAttribute('data-role', 'pengepul', { timeout: 20_000 });
  await pg.locator(`button[data-onclick="selectVerifyItem(${contract.id})"]`).click();
  const weight = pg.locator('#v-weight');
  await weight.fill('2000');
  const stepper = pg.locator('#v-weight + .qty-stepper');
  await stepper.getByRole('button', { name: 'Tambah 1000 kg' }).click();
  await stepper.getByRole('button', { name: 'Kurangi 50 kg' }).click();
  await expect(weight).toHaveValue('2950');
  await pg.locator('#v-moisture').fill('11.2');                      // wajib; abu/VM/FC opsional (F9)
  await pg.locator('#btn-submit-verify').click();
  await expect(pg.locator('#qr-modal.open')).toBeVisible({ timeout: 20_000 });
  await expect(pg.locator('#modal-qr-title')).toHaveText('Resi Serah-Terima Sekam');
  const yymm = new Date().toLocaleString('sv-SE', { timeZone: 'Asia/Jakarta' }).slice(2, 7).replace('-', '');
  await expect(pg.locator('#modal-qr-code')).toHaveText(new RegExp(`^\\s*TRX-[A-Z]{3}\\d{4}-[A-Z]{3}\\d{4}-${yymm}-\\d{5}\\s*$`));

  await ctxP.close(); await ctxF.close(); await api.dispose();
});

test('mode hemat sinyal: banner, antrean di HP, terkirim sekali saat online', async ({ browser }) => {
  test.setTimeout(120_000);
  const api = await pwRequest.newContext();
  const petani = await login(api, 'petani_sugeng', 'sekam123');
  const QTY = 4350;                                       // kelipatan 50 (step input) & unik → bukti tepat satu kiriman
  const listHarvests = async () => {
    const r = await (await api.get(`${BASE}/api/v1/farmer/harvests?limit=100`, { headers: auth(petani.access_token) })).json();
    return (Array.isArray(r) ? r : r.items || []).filter((h: any) => h.quantity_kg === QTY);
  };
  const before = (await listHarvests()).length;            // seed bisa saja sudah punya lot sebesar ini

  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  await openAs(page, 'petani');
  const banner = page.locator('#signal-banner');
  await expect(banner).toHaveClass(/is-hidden/);

  await ctx.setOffline(true);
  await expect(banner).toContainText('Mode Hemat Sinyal', { timeout: 10_000 });
  await expect(banner).toHaveAttribute('role', 'status');

  const qty = page.locator('#f-qty');
  await qty.fill('3850');
  await page.locator('#f-qty + .qty-stepper').getByRole('button', { name: 'Tambah 500 kg' }).click();
  await expect(qty).toHaveValue('4350');
  const submit = page.locator('#form-lapor-sekam [type=submit]');
  const sbox = await submit.boundingBox();
  expect(sbox!.height, 'tombol aksi utama petani ≥ 48 px').toBeGreaterThanOrEqual(48);
  await submit.click();
  await expect(page.locator('#toast-msg')).toContainText('disimpan di HP', { timeout: 10_000 });
  await expect(banner).toContainText('1 data antre', { timeout: 10_000 });

  await ctx.setOffline(false);
  await expect(banner).toHaveClass(/is-hidden/, { timeout: 40_000 });

  await expect.poll(async () => (await listHarvests()).length, { timeout: 15_000,
    message: 'laporan offline terkirim tepat satu kali' }).toBe(before + 1);
  await ctx.close(); await api.dispose();
});
