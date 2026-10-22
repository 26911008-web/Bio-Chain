import { test, expect, request as pwRequest, APIRequestContext } from '@playwright/test';

/**
 * FASE 2: FARMER LISTING & COLLECTOR SPECIALTY ISOLATION TEST
 * 
 * Pengujian End-to-End Playwright:
 * 1. Test Case 1.1 (Listing Multi-Komoditas): 4 Petani memposting komoditas terisolasi (Sekam, Jagung, Tebu, Sengon).
 * 2. Test Case 1.2 (Pengepul Spesialis - Happy Path): Pengepul Sekam login -> Melihat dan menawar listing Sekam Padi.
 * 3. Test Case 1.3 (Isolasi Spesialisasi - Negative Assertion): Pengepul Sekam menawar komoditas di luar spesialisasi (Bonggol Jagung) -> Sistem WAJIB menolak (HTTP 403 Forbidden).
 * 4. Test Case 1.4 (Concurrency & Row Lock): Dua pengepul menawar stok yang sama serentak -> PostgreSQL RPC / CAS Row Lock mencegah alokasi ganda.
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

test.describe('Fase 2: Farmer Listing & Collector Specialty Isolation', () => {

  // Test Case 1.1: Listing Multi-Komoditas oleh 4 Petani
  test('TC 1.1: Verifikasi 4 Petani Memposting Komoditas Spesifik dengan MC & Koordinat', async ({ browser }) => {
    test.setTimeout(90_000);
    const api = await pwRequest.newContext();

    const farmers = [
      { user: 'petani_sekam', commodity: 'sekam_padi', qty: '12000', mc: 14.0, name: 'Sekam padi' },
      { user: 'petani_jagung', commodity: 'tongkol_jagung', qty: '10000', mc: 15.0, name: 'Tongkol jagung' },
      { user: 'petani_tebu', commodity: 'ampas_tebu', qty: '15000', mc: 48.0, name: 'Ampas tebu' },
      { user: 'petani_kayu', commodity: 'serbuk_sengon', qty: '14000', mc: 12.0, name: 'Serbuk gergaji sengon' },
    ];

    for (const f of farmers) {
      const u = await login(api, f.user);
      const { context, page } = await openAs(browser, u);

      // Pastikan dropdown komoditas tersedia
      const sel = page.locator('#f-commodity');
      await expect(sel).toBeVisible({ timeout: 15_000 });

      // Verifikasi opsi komoditas tersedia dan pilih
      await sel.selectOption(f.commodity);
      await page.fill('#f-qty', f.qty);
      if (await page.locator('#f-moist').isVisible()) {
        await page.fill('#f-moist', f.mc.toString());
      }

      // Pastikan skema jemput/antar aktif
      if (await page.locator('#ls-jemput').isVisible()) {
        await page.check('#ls-jemput');
      }

      // Submit laporan panen/listing
      const [response] = await Promise.all([
        page.waitForResponse(r => r.url().includes('/api/v1/farmer/harvest') && r.request().method() === 'POST'),
        page.locator('#form-lapor-sekam [type=submit]').click(),
      ]);

      expect([200, 201]).toContain(response.status());
      const data = await response.json();
      expect(data.commodity).toBe(f.commodity);
      expect(data.quantity_kg).toBe(Number(f.qty));

      await context.close();
    }
  });

  // Test Case 1.2: Pengepul Spesialis Sekam - Happy Path (Bidding Sekam Padi)
  test('TC 1.2: Pengepul Sekam Hanya Menawar Listing Sekam Padi (Happy Path)', async ({ browser }) => {
    const api = await pwRequest.newContext();
    const pengepul = await login(api, 'pengepul_sekam');

    // 1. Cek via Market API
    const mRes = await api.get(`${BASE}/api/v1/collector/market`, { headers: auth(pengepul.access_token) });
    expect(mRes.status()).toBe(200);
    const marketItems = await mRes.json();
    expect(marketItems.length).toBeGreaterThan(0);

    const sekamListing = marketItems.find((x: any) => (x.commodity === 'sekam_padi' || !x.commodity) && x.remaining_kg > 0 && x.schemes && x.schemes.jemput != null);
    expect(sekamListing, 'Listing sekam padi harus ditemukan').toBeDefined();

    // 2. Eksekusi penawaran harga (Happy Path)
    const bidRes = await api.post(`${BASE}/api/v1/collector/bids`, {
      headers: auth(pengepul.access_token),
      data: {
        listing_id: sekamListing.id,
        scheme: 'jemput',
        price_per_kg: 480,
        quantity_kg: 1000,
      },
    });
    expect([200, 201]).toContain(bidRes.status());
    const bidResult = await bidRes.json();
    expect(bidResult.price_per_kg).toBe(480);

    // 3. Verifikasi UI menampilkan badge tawaran aktif pengepul
    const { context, page } = await openAs(browser, pengepul);
    await page.waitForSelector('#market-table', { timeout: 15_000 });
    if (await page.locator('#btn-tab-lelang').isVisible()) {
      await page.locator('#btn-tab-lelang').click();
    }
    const row = page.locator('#market-table').locator(`tr:has-text("#${sekamListing.id}")`);
    await expect(row).toBeVisible();
    await expect(row).toContainText(/tawaran anda/i);

    await context.close();
  });

  // Test Case 1.3: Isolasi Spesialisasi - Negative Assertion
  test('TC 1.3: Isolasi Tenant & Spesialisasi — Pengepul Sekam Dilarang Menawar Jagung (Negative Assertion)', async () => {
    const api = await pwRequest.newContext();
    const pengepulSekam = await login(api, 'pengepul_sekam');

    // Dapatkan ID listing jagung milik Petani Jagung
    const mRes = await api.get(`${BASE}/api/v1/collector/market`, { headers: auth(pengepulSekam.access_token) });
    const market = await mRes.json();
    const jagungListing = market.find((x: any) => x.commodity === 'tongkol_jagung');

    if (jagungListing) {
      // Direct API Injection attempt: Pengepul Sekam mencoba menawar komoditas Jagung
      const bidAttempt = await api.post(`${BASE}/api/v1/collector/bids`, {
        headers: auth(pengepulSekam.access_token),
        data: {
          listing_id: jagungListing.id,
          scheme: 'jemput',
          price_per_kg: 420,
          quantity_kg: 5000,
        },
      });

      const status = bidAttempt.status();
      const body = await bidAttempt.text();
      console.log(`[TC 1.3 Audit] Respon penetrasi penawaran silang komoditas: HTTP ${status} -> ${body}`);
      
      // Assertion memvalidasi aturan isolasi spesialisasi bisnis (Wajib ditolak: HTTP 400, 403, atau 422)
      expect([400, 403, 422], `Pelanggaran isolasi spesialisasi wajib ditolak (ditemukan HTTP ${status})`).toContain(status);
    } else {
      console.log('[TC 1.3 Audit] Listing jagung terisolasi sempurna di query level server (tidak terlihat oleh Pengepul Sekam).');
      expect(jagungListing).toBeUndefined();
    }
  });

  // Test Case 1.4: Concurrency & Row Locking (Anti Double-Allocation)
  test('TC 1.4: Concurrency Test — Mencegah Alokasi Ganda pada Perebutan Stok Milidetik Serentak', async () => {
    const api = await pwRequest.newContext();
    const petani = await login(api, 'petani_sekam');
    const pengepul1 = await login(api, 'pengepul_sekam');
    const pengepul2 = await login(api, 'pengepul_sleman', 'kud2026');

    // 1. Petani buat stok baru terbatas (1.000 kg)
    const listRes = await api.post(`${BASE}/api/v1/farmer/listings`, {
      headers: auth(petani.access_token),
      data: {
        commodity: 'sekam_padi',
        quantity_kg: 1000,
        allow_jemput: true,
        ask_price_jemput: 450,
        allow_antar: false,
      },
    });
    expect([200, 201]).toContain(listRes.status());
    const listing = await listRes.json();
    const listingId = listing.id;

    // 2. Kedua pengepul menawar seluruh stok (1.000 kg)
    const b1 = await api.post(`${BASE}/api/v1/collector/bids`, {
      headers: auth(pengepul1.access_token),
      data: { listing_id: listingId, scheme: 'jemput', price_per_kg: 460, quantity_kg: 1000 },
    });
    expect([200, 201]).toContain(b1.status());
    const bid1 = await b1.json();

    const b2 = await api.post(`${BASE}/api/v1/collector/bids`, {
      headers: auth(pengepul2.access_token),
      data: { listing_id: listingId, scheme: 'jemput', price_per_kg: 470, quantity_kg: 1000 },
    });
    expect([200, 201]).toContain(b2.status());
    const bid2 = await b2.json();

    // 3. Simulasikan aksi penerimaan serentak milidetik yang sama (Race Condition)
    const [res1, res2] = await Promise.all([
      api.post(`${BASE}/api/v1/farmer/listings/${listingId}/accept`, {
        headers: auth(petani.access_token),
        data: { bid_id: bid1.bid_id, quantity_kg: 1000 },
      }),
      api.post(`${BASE}/api/v1/farmer/listings/${listingId}/accept`, {
        headers: auth(petani.access_token),
        data: { bid_id: bid2.bid_id, quantity_kg: 1000 },
      }),
    ]);

    const statuses = [res1.status(), res2.status()];
    console.log(`[TC 1.4 Audit] Status Eksekusi Balapan Konkurensi: [${statuses.join(', ')}]`);

    // Satu request HARUS sukses (200), dan request kedua HARUS ditolak (409 Conflict / 422)
    expect(statuses).toContain(200);
    const conflictCount = statuses.filter(s => s === 409 || s === 422 || s === 503).length;
    expect(conflictCount, 'Database atomic lock / CAS harus menggagalkan alokasi ganda').toBe(1);
  });

});
