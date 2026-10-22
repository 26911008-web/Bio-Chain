/**
 * Manifest layar Manual Book Bio-Chain — dipakai scripts/capture_annotated_manual.mts.
 *
 * Setiap Shot = satu PNG di docs/manual/screenshots/. `prepare` mengisi form / membuka modal
 * dengan data contoh realistis sebelum dipotret; `marks` = elemen yang diberi kotak + nomor ①②③.
 * Selector `card:<teks>` menunjuk kartu yang judul h3/h4-nya memuat teks tersebut.
 * `height` = tinggi viewport khusus layar ini (form panjang di ponsel) agar semua nomor masuk gambar.
 */
import type { Page } from 'playwright';

export interface Mark { sel: string; n: number; color?: 'red' | 'green' }
export interface Scenario {
  harvestId: number; harvestQr: string; listingId: number; bidId: number | null;
  verifiedHarvestId: number | null; deliveryRequestId: number | null;
  petaniUser: string; pengepulUser: string;
}
export interface Shot {
  file: string;
  bab: string;                               // judul layar di Manual Book
  role: 'login' | 'petani' | 'pengepul' | 'driver' | 'pabrik';
  viewport: 'mobile' | 'desktop';
  height?: number;
  fresh?: boolean;                           // muat ulang halaman (sesi baru) sebelum layar ini
  anchor?: string;                           // elemen yang di-scroll ke atas viewport
  prepare?: (page: Page, sc: Scenario) => Promise<void>;
  cleanup?: (page: Page, sc: Scenario) => Promise<void>;
  marks: Mark[] | ((sc: Scenario) => Mark[]);
}

interface DemoAccount { username: string; password: string; role: string }
interface LoginResponse { access_token: string; user_id?: number; id?: number }

/** Data skenario lewat API (akun demo yang sama dengan yang dipakai `/?role=`). */
export async function seedScenario(base: string): Promise<Scenario> {
  const j = async <T>(r: Response): Promise<T> => {
    if (!r.ok) throw new Error(`${r.url} → HTTP ${r.status}: ${(await r.text()).slice(0, 200)}`);
    return r.json() as Promise<T>;
  };
  const accounts = await j<DemoAccount[]>(await fetch(`${base}/api/v1/auth/demo-accounts`));
  const login = async (role: string): Promise<LoginResponse & { username: string }> => {
    const a = accounts.find(x => x.role === role);
    if (!a) throw new Error(`akun demo peran ${role} tidak ada`);
    const res = await j<LoginResponse>(await fetch(`${base}/api/v1/auth/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier: a.username, password: a.password, expected_role: role }),
    }));
    return { ...res, username: a.username };
  };
  const petani = await login('petani');
  const pengepul = await login('pengepul');
  const post = <T>(tok: string, url: string, body: object): Promise<T> => fetch(`${base}${url}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tok}` },
    body: JSON.stringify(body),
  }).then(r => j<T>(r));
  const collectorId = pengepul.user_id ?? pengepul.id;
  const report = (kg: number, mc: number) => post<{ id: number; qr_code: string }>(petani.access_token, '/api/v1/farmer/harvest', {
    quantity_kg: kg, commodity: 'sekam_padi', mill_id: 1, moisture_est: mc, collector_id: collectorId,
    delivery_scheme: 'jemput', transaction_mode: 'DIRECT', logistics_mode: 'PICKUP',
    biochar_request_kg: 500, biochar_land_area_ha: 1.5, biochar_delivery_point: 'Lahan Petani Dusun Ngepas',
  });

  // Lot jual langsung: 5.000 kg sekam, taksiran MC 13,2 % → masuk antrean uji mutu pengepul (layar 18–19)
  const harvest = await report(5000, 13.2);
  // Stok lelang 3.000 kg, batas minimum Rp450/kg (dijemput) + satu tawaran pengepul Rp470/kg
  const listing = await post<{ id?: number; listing_id?: number }>(petani.access_token, '/api/v1/farmer/listings', {
    quantity_kg: 3000, allow_jemput: true, ask_price_jemput: 450, allow_antar: false,
  });
  const listingId = (listing.id ?? listing.listing_id)!;
  const soft = async <T>(label: string, fn: () => Promise<T>): Promise<T | null> => {
    try { return await fn(); } catch (e) { console.warn(`⚠️  ${label} gagal:`, (e as Error).message); return null; }
  };
  const bid = await soft('tawaran contoh', () => post<{ bid_id: number }>(pengepul.access_token, '/api/v1/collector/bids', {
    listing_id: listingId, scheme: 'jemput', price_per_kg: 470, quantity_kg: 3000, payment_term: 'DP',
  }));
  // Lot kedua sudah diverifikasi → belum dibayar (layar 20) + ajuan kirim pending ke pabrik (layar 30)
  const second = await report(3000, 12.5);
  const verified = await soft('verifikasi lot kedua', () => post<object>(pengepul.access_token, '/api/v1/collector/verify', {
    harvest_id: second.id, weighed_kg: 2950, moisture: 12.5, contamination: 0.3,
  }));
  const dr = verified && await soft('ajuan pengiriman', () => post<{ id: number }>(pengepul.access_token, '/api/v1/collector/delivery-requests', {
    harvest_ids: [second.id], quantity_kg: 2950, proposed_price_per_kg: 1350,
    proposed_date: new Date().toISOString().slice(0, 10), moisture_est: 12.5, note: 'Sekam kering siap pirolisis',
  }));
  return { harvestId: harvest.id, harvestQr: harvest.qr_code, listingId, bidId: bid?.bid_id ?? null,
    verifiedHarvestId: verified ? second.id : null, deliveryRequestId: dr?.id ?? null,
    petaniUser: petani.username, pengepulUser: pengepul.username };
}

const wait = (p: Page, ms = 1200): Promise<void> => p.waitForTimeout(ms);
const openDetails = (p: Page, sel: string): Promise<void> =>
  p.evaluate((s) => { const d = document.querySelector(s); if (d) (d as HTMLDetailsElement).open = true; }, sel);
const closeModals = async (p: Page): Promise<void> => {
  await p.keyboard.press('Escape').catch(() => {});
  await p.evaluate(() => document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open')));
};
/** Gulir elemen ke tengah layar (untuk baris tabel dinamis yang tak cocok jadi anchor statis). */
const centerOn = (p: Page, sel: string): Promise<void> => p.evaluate((s) => {
  document.querySelector(s)?.scrollIntoView({ block: 'center', behavior: 'instant' as ScrollBehavior });
}, sel);
/** Tunggu angka KPI selesai dimuat (bukan 0 / "–" / kosong). */
const waitKpi = (p: Page, sel: string): Promise<void> => p.waitForFunction((s) => {
  const t = (document.querySelector(s)?.textContent || '').trim();
  return t !== '' && t !== '0' && t !== '–' && t !== '—';
}, sel, { timeout: 20_000 }).then(() => undefined).catch(() => {});
/** Form lapor petani: Sekam Padi 5.000 kg, kadar air 13,2 %, pengepul spesialis sekam. */
async function fillPetaniReport(p: Page): Promise<void> {
  await p.waitForSelector('#f-commodity option[value="sekam_padi"]', { state: 'attached', timeout: 15_000 }).catch(() => {});
  await p.selectOption('#f-commodity', 'sekam_padi').catch(() => {});
  await p.dispatchEvent('#f-commodity', 'change');
  await wait(p, 500);
  await p.evaluate(() => {
    const sel = document.getElementById('f-collector') as HTMLSelectElement | null;
    const opt = sel && [...sel.options].find(o => /sekam/i.test(o.textContent || '') && o.value);
    if (sel && opt) { sel.value = opt.value; sel.dispatchEvent(new Event('change', { bubbles: true })); }
  });
  await p.fill('#f-qty', '5000');
  await openDetails(p, '#f-quality-box');
  await p.fill('#f-moist', '13.2');
  await p.dispatchEvent('#f-moist', 'input');
}
const pickMode = async (p: Page, mode: 'langsung' | 'lelang', deliv: 'jemput' | 'antar'): Promise<void> => {
  await p.check(`input[name="f-mode"][value="${mode}"]`, { force: true });
  await p.check(`#f-deliv-${deliv}`, { force: true });
  await wait(p, 300);
};
/** HiGHS blend: beri stok & harga semua komoditas, lalu coba preset sampai solver menemukan campuran layak. */
async function runFeasibleFuelBlend(p: Page): Promise<void> {
  await p.waitForSelector('[data-fb-use]', { state: 'attached', timeout: 15_000 });
  await p.evaluate(() => {
    const prices: Record<string, number> = { sekam_padi: 450, serbuk_kayu: 700, tempurung_kelapa: 1200, tongkol_jagung: 500, bagasse_tebu: 400 };
    document.querySelectorAll<HTMLInputElement>('[data-fb-use]').forEach((cb) => {
      const c = cb.dataset.fbUse!;
      cb.checked = true;
      const set = (k: string, v: string) => {
        const el = document.querySelector<HTMLInputElement>(`[data-fb-${k}="${CSS.escape(c)}"]`);
        if (el && (el.value === '' || el.value === '0' || k === 'kg')) el.value = v;
      };
      set('kg', '20000'); set('price', String(prices[c] ?? 600)); set('max', '100');
    });
  });
  await p.fill('#fx-fb-target', '10000');
  const presets = await p.$$eval('#fx-fb-preset option', os => os.map(o => (o as HTMLOptionElement).value));
  for (const preset of presets) {
    await p.selectOption('#fx-fb-preset', preset);
    await p.fill('#fx-fb-kcal', '');
    await p.click('#fx-fb-go');
    await wait(p, 3000);
    if (await p.locator('#fx-fb-out .kpi-row').count()) return;
  }
}

export const SHOTS: Shot[] = [
  // ───────────── Bab 3 · Petani / Penggilingan (mobile 390×844; tabel lebar → desktop) ─────────────
  { file: '00_login_pilih_peran.png', bab: '3.1 Login aman', role: 'login', viewport: 'mobile',
    prepare: async (p) => { await p.waitForSelector('#login-form'); await p.fill('#login-ident', 'petani_sugeng'); await p.fill('#login-pass', 'contohsandi'); },
    anchor: '#auth-login-box',
    marks: [{ sel: '#role-selector-grid', n: 1 }, { sel: '#login-ident', n: 2 }, { sel: '#login-pass', n: 3 }, { sel: '#btn-submit-login', n: 4, color: 'green' }] },
  { file: '01_petani_dashboard.png', bab: '3.1 Dashboard utama petani', role: 'petani', viewport: 'mobile',
    prepare: async (p) => { await waitKpi(p, '#p-tot-harvest'); await wait(p, 1500); },
    anchor: '#petani-kpi',
    marks: [{ sel: '#p-tot-harvest', n: 1 }, { sel: '#p-tot-ton', n: 2 }, { sel: '#p-xp', n: 3 }, { sel: '#p-wallet', n: 4, color: 'green' }] },
  { file: '02_petani_lapor_biomassa.png', bab: '3.2 Form lapor biomassa', role: 'petani', viewport: 'mobile',
    prepare: fillPetaniReport, anchor: '#form-lapor-sekam',
    marks: [{ sel: '#f-commodity', n: 1 }, { sel: '#f-rec-box', n: 2, color: 'green' }, { sel: '#f-qty', n: 3 }, { sel: '#f-mill', n: 4 }] },
  { file: '03_petani_estimasi_mutu.png', bab: '3.2 Estimasi mutu (kadar air & grade)', role: 'petani', viewport: 'mobile', height: 1500,
    prepare: fillPetaniReport, anchor: '#f-quality-box',
    marks: [{ sel: '#f-moist', n: 1 }, { sel: '#f-grade', n: 2 }, { sel: '#f-photo-file', n: 3 }] },
  { file: '04_petani_jual_langsung_dijemput.png', bab: '3.3 Jual Langsung + Dijemput Armada', role: 'petani', viewport: 'mobile', height: 1700,
    prepare: async (p) => { await fillPetaniReport(p); await pickMode(p, 'langsung', 'jemput'); },
    anchor: 'input[name="f-mode"]',
    marks: [{ sel: 'label.sale-opt:has(input[name="f-mode"][value="langsung"])', n: 1 }, { sel: '#f-collector', n: 2 }, { sel: 'label.sale-opt:has(#f-deliv-jemput)', n: 3 }, { sel: '#f-est-earning', n: 4, color: 'green' }] },
  { file: '05_petani_bursa_lelang_diantar.png', bab: '3.3 Bursa Lelang + Diantar Mandiri', role: 'petani', viewport: 'mobile', height: 1900,
    prepare: async (p) => { await fillPetaniReport(p); await pickMode(p, 'lelang', 'antar'); await p.fill('#f-ask-price', '480'); await p.dispatchEvent('#f-ask-price', 'input'); },
    anchor: 'input[name="f-mode"]',
    marks: [{ sel: 'label.sale-opt:has(input[name="f-mode"][value="lelang"])', n: 1 }, { sel: 'label.sale-opt:has(#f-deliv-antar)', n: 2 }, { sel: '#f-ask-price', n: 3 }, { sel: '#f-submit', n: 4, color: 'green' }] },
  { file: '06_petani_permintaan_biochar.png', bab: '3.4 Permintaan abu / biochar sirkular', role: 'petani', viewport: 'mobile', height: 1100,
    prepare: async (p) => {
      await pickMode(p, 'langsung', 'jemput');
      await openDetails(p, '#f-biochar-box');
      await p.fill('#f-biochar-req', '500'); await p.fill('#f-biochar-ha', '1.5'); await p.fill('#f-biochar-loc', 'Lahan Petani Dusun Ngepas');
    },
    anchor: '#f-biochar-box',
    marks: [{ sel: '#f-biochar-req', n: 1 }, { sel: '#f-biochar-ha', n: 2 }, { sel: '#f-biochar-loc', n: 3 }, { sel: '#btn-popup-biochar-benefit', n: 4, color: 'green' }] },
  { file: '07_petani_riwayat_grade_qr.png', bab: '3.5 Riwayat laporan, grade & QR', role: 'petani', viewport: 'desktop',
    anchor: '#table-petani-harvests',
    marks: [{ sel: '#table-petani-harvests thead', n: 1 }, { sel: '#table-petani-harvests tbody tr:not(.group-header-row)', n: 2 }, { sel: '#table-petani-harvests button[data-onclick^="openModal"]', n: 3, color: 'green' }] },
  { file: '08_petani_tawaran_lelang_masuk.png', bab: '3.3 Stok lelang & tawaran masuk', role: 'petani', viewport: 'mobile', height: 1200,
    prepare: async (p, sc) => {
      await p.click(`button[data-onclick="showBids(${sc.listingId})"]`); await wait(p, 2000);
      await centerOn(p, sc.bidId ? `#acc-${sc.bidId}` : `button[data-onclick="showBids(${sc.listingId})"]`); await wait(p, 400);
    },
    marks: (sc) => [{ sel: `button[data-onclick="showBids(${sc.listingId})"]`, n: 1 },
      { sel: sc.bidId ? `#acc-${sc.bidId}` : 'button[data-onclick^="acceptBid("]', n: 2, color: 'green' },
      { sel: `button[data-onclick^="cancelListing(${sc.listingId}"]`, n: 3 }] },
  { file: '09_petani_pembayaran_kuitansi_sla.png', bab: '3.5 Pelacakan pembayaran (DP / lunas) & kuitansi', role: 'petani', viewport: 'desktop',
    anchor: '#fo-mypay-title',
    marks: [{ sel: '#fo-pay-filter', n: 1 }, { sel: '#fo-mypay-unified', n: 2 }, { sel: '#fo-mypay-unified button[data-onclick^="openModal"]', n: 3, color: 'green' }] },
  { file: '10_petani_deviasi_refraksi.png', bab: '3.5 Hasil uji mutu, deviasi & refraksi', role: 'petani', viewport: 'desktop', height: 1200,
    anchor: '#fo-qc-dev-title',
    marks: [{ sel: '#fo-qc-deviations', n: 1 }, { sel: '#fo-col-rep-title', n: 2 }, { sel: '#btn-open-rate-collector', n: 3, color: 'green' }] },
  { file: '11_petani_lacak_qr_sirkular.png', bab: '3.5 Ketertelusuran ISO 22095 (lacak QR)', role: 'petani', viewport: 'mobile', height: 1100,
    prepare: async (p, sc) => {
      await p.click('#btn-header-trace'); await wait(p, 800);
      await p.fill('#circ-search-input', sc.harvestQr);
      await p.click('button[data-onclick="handleCircSearchSubmit()"]');
      await p.waitForFunction((qr) => (document.getElementById('circ-modal-content')?.textContent || '').includes(qr),
        sc.harvestQr, { timeout: 15_000 }).catch(() => {});
      await wait(p, 1000);
    },
    cleanup: closeModals,
    marks: [{ sel: '#circ-search-input', n: 1 }, { sel: '#circ-badge-status', n: 2, color: 'green' }, { sel: '#circ-modal-content', n: 3 }] },
  { file: '12_petani_alokasi_abu_evaluasi.png', bab: '3.4 Alokasi abu & evaluasi biochar', role: 'petani', viewport: 'desktop', height: 1300,
    anchor: '#fo-soil-amendment-title',
    marks: [{ sel: '#fo-ash-container', n: 1 }, { sel: '#btn-open-eval-biochar', n: 2, color: 'green' }, { sel: '#fo-biochar-evaluations', n: 3 }] },

  // ───────────── Bab 4 · Pengepul / Agregator (desktop 1440×900) ─────────────
  { file: '13_pengepul_dashboard_penawaran.png', bab: '4.1 Dashboard konsolidasi: Langsung / Lelang / Diantar', role: 'pengepul', viewport: 'desktop',
    prepare: async (p) => { await p.click('#btn-tab-langsung'); await wait(p); },
    anchor: 'card:Dashboard Penawaran',
    marks: [{ sel: '#btn-tab-langsung', n: 1 }, { sel: '#btn-tab-lelang', n: 2 }, { sel: '#btn-tab-diantar', n: 3 }, { sel: '#vfilter-unverified', n: 4 }] },
  { file: '14_pengepul_bursa_lelang_tawar.png', bab: '4.1 Tab Bursa Lelang: kirim tawaran', role: 'pengepul', viewport: 'desktop',
    prepare: async (p) => {                  // listing skenario sudah ditawar pengepul ini → pakai listing lelang terbuka lain
      await p.click('#btn-tab-lelang'); await wait(p);
      await centerOn(p, 'input[id^="bp-"]'); await p.fill('input[id^="bp-"] >> nth=0', '470').catch(() => {});
    },
    marks: [{ sel: '#btn-tab-lelang', n: 1 }, { sel: 'input[id^="bp-"]', n: 2 }, { sel: 'button[data-onclick^="placeBid("]', n: 3, color: 'green' }] },
  { file: '15_pengepul_margin_kontrak_pabrik.png', bab: '4.1 Margin kompensasi proporsional agregator', role: 'pengepul', viewport: 'desktop',
    anchor: 'card:Modul Kontrak',
    marks: [{ sel: '#fp-buy-0', n: 1 }, { sel: '#fp-sell-0', n: 2 }, { sel: '#table-factory-pricing tbody tr:first-child', n: 3, color: 'green' }, { sel: 'button[data-onclick^="openSimulateTruckMarginModal"]', n: 4 }] },
  { file: '16_pengepul_rute_clarke_wright.png', bab: '4.2 Optimasi rute volume (Clarke-Wright vs OR-Tools)', role: 'pengepul', viewport: 'desktop',
    prepare: async (p) => {
      await p.click('#fo-plan-route-btn'); await wait(p, 1500);
      await p.selectOption('#ro-vehicle-select', 'cdd_budi').catch(() => {});
      await p.click('#btn-run-ro-sim'); await wait(p, 5000);
    },
    anchor: '#ro-vehicle-select',
    marks: [{ sel: '#ro-vehicle-select', n: 1 }, { sel: 'div:has(> #ro-truck-max-m3)', n: 2 }, { sel: '#ro-harvests-checklist-container', n: 3 }, { sel: '#btn-run-ro-sim', n: 4, color: 'green' }] },
  { file: '17_pengepul_rute_hasil_backhaul.png', bab: '4.2 Hasil rute: KPI volume, peta & muatan balik', role: 'pengepul', viewport: 'desktop', height: 1200,
    anchor: '#ro-feasibility-banner', cleanup: closeModals,
    marks: [{ sel: '#ro-feasibility-banner', n: 1 }, { sel: '#ro-kpi-row', n: 2, color: 'green' }, { sel: '#ro-leaflet-map', n: 3 }] },
  { file: '18_pengepul_uji_cepat_grade.png', bab: '4.3 Uji cepat lapangan, timbang aktual & grade otomatis', role: 'pengepul', viewport: 'desktop', fresh: true,
    prepare: async (p, sc) => {
      await p.click(`button[data-onclick="selectVerifyItem(${sc.harvestId})"]`); await wait(p, 800);
      await p.fill('#v-weight', '4950'); await p.fill('#v-moisture', '13.2'); await p.fill('#v-contam', '0.5');
      await p.dispatchEvent('#v-contam', 'input'); await wait(p, 800);
    },
    anchor: '#form-verify-harvest',
    marks: [{ sel: '#v-weight', n: 1 }, { sel: '#v-moisture', n: 2 }, { sel: '#v-contam', n: 3 }, { sel: '#v-preview', n: 4, color: 'green' }, { sel: '#btn-submit-verify', n: 5 }] },
  { file: '19_pengepul_resi_serah_terima.png', bab: '4.3 Resi serah-terima TRX & QR (Chain of Custody)', role: 'pengepul', viewport: 'desktop',
    prepare: async (p) => { await p.click('#btn-submit-verify'); await p.waitForSelector('#qr-modal.open', { timeout: 20_000 }); await wait(p, 800); },
    cleanup: closeModals,
    marks: [{ sel: '#modal-qr-title', n: 1 }, { sel: '#modal-qr-code', n: 2, color: 'green' }] },
  { file: '20_pengepul_bayar_petani_dp.png', bab: '4.3 Instruksi pembayaran ke petani (DP / lunas)', role: 'pengepul', viewport: 'desktop', height: 1100, fresh: true,
    prepare: async (p) => { await p.waitForSelector('#fo-unpaid table', { timeout: 20_000 }).catch(() => {}); await wait(p, 800); },
    anchor: '#fo-pay-title',
    marks: [{ sel: '#fo-pay-title', n: 1 }, { sel: '#fo-unpaid', n: 2 }, { sel: '#fo-unpaid button', n: 3, color: 'green' }] },
  { file: '21_pengepul_ajukan_kirim_pabrik.png', bab: '4.4 Ajukan pengiriman ke pabrik (dijemput / diantar)', role: 'pengepul', viewport: 'desktop',
    prepare: async (p) => { await p.selectOption('#dr-carrier', 'FACTORY_FLEET'); await p.fill('#dr-qty', '4950'); },
    anchor: 'card:Ajukan Pengiriman',
    marks: [{ sel: '#dr-biomass', n: 1 }, { sel: '#dr-carrier', n: 2 }, { sel: '#dr-qty', n: 3 }, { sel: '#dr-price', n: 4 }, { sel: '#btn-dr', n: 5, color: 'green' }] },
  { file: '22_pengepul_backhaul_piutang.png', bab: '4.4 Muatan balik biochar & piutang pabrik', role: 'pengepul', viewport: 'desktop', height: 1400,
    anchor: '#fo-backhaul-title',
    marks: [{ sel: '#fo-backhaul-status', n: 1 }, { sel: '#fo-factory-receivables', n: 2 }, { sel: '#fo-charges', n: 3 }] },
  { file: '23_pengepul_umpan_balik_qc_pabrik.png', bab: '4.4 Umpan balik QC gerbang pabrik', role: 'pengepul', viewport: 'desktop',
    anchor: '#fo-feedback-title',
    marks: [{ sel: 'card:Transparansi Mutu', n: 1 }, { sel: '#btn-refresh-feedback', n: 2, color: 'green' }] },

  // ───────────── Bab 5 · Driver (mobile 390×844) ─────────────
  { file: '24_driver_daftar_job_kapasitas.png', bab: '5.1 Daftar job & utilisasi volume bak', role: 'driver', viewport: 'mobile', height: 1100,
    anchor: '#d-status',
    marks: [{ sel: '#d-status', n: 1 }, { sel: '#d-util', n: 2 }, { sel: '#driver-actions', n: 3, color: 'green' }] },
  { file: '25_driver_titik_jemput_scan.png', bab: '5.2 Titik jemput: scan QR / laporkan gagal', role: 'driver', viewport: 'mobile', height: 1100,
    prepare: async (p) => {                  // tombol Scan QR baru muncul setelah rute dimulai
      const start = p.locator('button[data-onclick^="driverStart"]');
      if (await start.count()) {
        await start.first().click(); await wait(p, 800);
        const yes = p.locator('dialog.ui-confirm[open] button[value="yes"]');
        if (await yes.count()) await yes.click();
        await wait(p, 3000);
      }
    },
    anchor: '#driver-stops-list',
    marks: [{ sel: '#driver-stops-list', n: 1 }, { sel: 'button[data-onclick^="confirmPickupStop"]', n: 2, color: 'green' }, { sel: 'select[id^="fail-"]', n: 3 }] },
  { file: '26_driver_scanner_qr_checkpoint.png', bab: '5.2 Pemindai QR checkpoint (ISO 22095)', role: 'driver', viewport: 'mobile',
    prepare: async (p) => { await p.click('#btn-header-scanner'); await wait(p, 1500); },
    cleanup: closeModals,
    marks: [{ sel: '#scanner-modal-title', n: 1 }, { sel: '#scanner-modal video, #scanner-modal #qr-reader, #scanner-modal .modal-body', n: 2 }, { sel: '#scanner-modal input[type="text"]', n: 3, color: 'green' }] },
  { file: '27_driver_muatan_balik_biochar.png', bab: '5.1 Instruksi muatan balik abu/biochar', role: 'driver', viewport: 'mobile', height: 1100,
    anchor: '#driver-backhaul-list',
    marks: [{ sel: '#driver-backhaul-list', n: 1 }, { sel: 'button[data-onclick^="driverScanBackhaulCheckpoint"]', n: 2 }, { sel: 'button[data-onclick^="driverConfirmDropBiochar"]', n: 3, color: 'green' }] },
  { file: '28_driver_mode_offline.png', bab: '5.2 Mode Hemat Sinyal (offline sync)', role: 'driver', viewport: 'mobile',
    prepare: async (p) => { await p.context().setOffline(true); await p.waitForSelector('#signal-banner:not(.is-hidden)', { timeout: 15_000 }); },
    cleanup: async (p) => { await p.context().setOffline(false); },
    anchor: '#signal-banner',
    marks: [{ sel: '#signal-banner', n: 1 }] },

  // ───────────── Bab 6 · Pabrik (desktop 1440×900) ─────────────
  { file: '29_pabrik_dashboard_esg_kpi.png', bab: '6.4 Dashboard KPI karbon & output', role: 'pabrik', viewport: 'desktop', height: 1300,
    prepare: async (p) => { await waitKpi(p, '#f-co2'); await wait(p, 1500); },
    anchor: '.kpi-row:has(#f-co2)',
    marks: [{ sel: '#f-co2', n: 1, color: 'green' }, { sel: '#f-biochar', n: 2 }, { sel: '#f-sio2', n: 3 }] },
  { file: '30_pabrik_ajuan_pengiriman.png', bab: '6.1 Ajuan pengiriman dari pengepul', role: 'pabrik', viewport: 'desktop',
    prepare: async (p, sc) => { if (sc.deliveryRequestId) await centerOn(p, `#drp-${sc.deliveryRequestId}`); await wait(p, 400); },
    marks: (sc) => {
      const row = sc.deliveryRequestId ? `[data-onclick^="drRespond(${sc.deliveryRequestId},"]` : '[data-onclick^="drRespond("]';
      return [{ sel: sc.deliveryRequestId ? `#drp-${sc.deliveryRequestId}` : 'input[id^="drp-"]', n: 1 },
        { sel: `button${row}[data-onclick*="accept"]`, n: 2, color: 'green' },
        { sel: `button${row}[data-onclick*="counter"]`, n: 3 },
        { sel: `button${row}[data-onclick*="reject"]`, n: 4 }];
    } },
  { file: '31_pabrik_gerbang_timbang_qc.png', bab: '6.1 Gerbang timbang (Gross/Tare/Net) & QC 3 keputusan', role: 'pabrik', viewport: 'desktop', height: 1300,
    prepare: async (p) => {
      await p.click('#btn-open-gate-modal'); await wait(p, 800);
      await p.fill('#gc-plate', 'AB 8421 CS'); await p.fill('#gc-gross', '10950'); await p.fill('#gc-tare', '6000');
      await p.dispatchEvent('#gc-tare', 'input');
      await p.fill('#gc-mc', '13.2'); await p.fill('#gc-ash', '17.5'); await p.fill('#gc-lhv', '3450'); await p.fill('#gc-contam', '0.5');
      await p.check('input[name="qc_decision"][value="PARTIALLY_ACCEPTED"]', { force: true });
      await p.fill('#gc-acc-qty', '4800').catch(() => {}); await p.fill('#gc-rej-qty', '150').catch(() => {});
      await p.selectOption('#gc-scheme', 'DP').catch(() => {}); await p.dispatchEvent('#gc-scheme', 'change').catch(() => {});
      await p.fill('#gc-dp-val', '2000000').catch(() => {}); await p.fill('#gc-due-days', '14').catch(() => {});
    },
    anchor: '#gc-carrier',
    marks: [{ sel: '#gc-gross', n: 1 }, { sel: '#gc-tare', n: 2 }, { sel: '#gc-net-display', n: 3, color: 'green' }, { sel: '#gc-mc', n: 4 }, { sel: 'label:has(input[name="qc_decision"][value="PARTIALLY_ACCEPTED"])', n: 5 }, { sel: '#gc-target-ramp', n: 6 }] },
  { file: '32_pabrik_skema_bayar_invoice.png', bab: '6.2 Skema bayar Cash / DP / TOP & invoice otomatis', role: 'pabrik', viewport: 'desktop', height: 1300,
    anchor: '#gc-partial-box', cleanup: closeModals,
    marks: [{ sel: '#gc-partial-box', n: 1 }, { sel: '#gc-scheme', n: 2 }, { sel: '#gc-dp-val', n: 3 }, { sel: '#gc-due-days', n: 4, color: 'green' }] },
  { file: '33_pabrik_pembayaran_pengepul.png', bab: '6.2 Penyelesaian pembayaran & pengawasan jatuh tempo', role: 'pabrik', viewport: 'desktop', height: 1600, fresh: true,
    prepare: async (p) => { await centerOn(p, 'button[data-onclick^="priceSettlement"]'); await wait(p, 400); },  // daftar tagihan panjang
    marks: [{ sel: 'input[id^="stp-"]', n: 1 }, { sel: 'button[data-onclick^="priceSettlement"]', n: 2, color: 'green' }] },
  { file: '34_pabrik_loading_ramp_status.png', bab: '6.3 Status real-time loading ramp', role: 'pabrik', viewport: 'desktop',
    anchor: '#fo-gate-title',
    marks: [{ sel: '#gate-ramps-container', n: 1, color: 'green' }, { sel: '#gate-receptions-table', n: 2 }, { sel: '#btn-open-gate-modal', n: 3 }] },
  { file: '35_pabrik_blend_highs_biaya_terendah.png', bab: '6.3 Solver HiGHS: blend bahan bakar biaya terendah & risiko terak', role: 'pabrik', viewport: 'desktop', height: 1600,
    prepare: runFeasibleFuelBlend,
    anchor: '#fx-fb-title',
    marks: [{ sel: '#fx-fb-preset', n: 1 }, { sel: '#fx-fb-feeds', n: 2 }, { sel: '#fx-fb-target', n: 3 }, { sel: '#fx-fb-go', n: 4 }, { sel: '#fx-fb-out', n: 5, color: 'green' }] },
  { file: '36_pabrik_blending_multiramp_4produk.png', bab: '6.3 Rekomendasi blending multi-ramp 4 produk (heuristik)', role: 'pabrik', viewport: 'desktop',
    prepare: async (p) => { await p.fill('#blend-batch-size', '10000'); await p.click('#btn-run-blending'); await wait(p, 3000); },
    anchor: '#fo-blending-title',
    marks: [{ sel: '#blend-batch-size', n: 1 }, { sel: '#btn-run-blending', n: 2 }, { sel: '#blending-cards-container', n: 3, color: 'green' }] },
  { file: '37_pabrik_optimasi_produk_akhir.png', bab: '6.3 Optimasi multi-biomassa ke produk akhir (HiGHS)', role: 'pabrik', viewport: 'desktop', height: 1400,
    prepare: async (p) => {
      await p.selectOption('#fx-opt-com', 'sekam_padi').catch(() => {});
      await p.fill('#fx-opt-kg', '5000'); await p.fill('#fx-opt-mc', '13.2');
      await p.click('#fx-opt-eval-go'); await wait(p, 3500);
    },
    anchor: '#fx-opt-title',
    marks: [{ sel: '#fx-opt-com', n: 1 }, { sel: '#fx-opt-kg', n: 2 }, { sel: '#fx-opt-mc', n: 3 }, { sel: '#fx-opt-eval-go', n: 4 }, { sel: '#fx-opt-eval-out', n: 5, color: 'green' }] },
  { file: '38_pabrik_batch_produksi_output.png', bab: '6.4 Batch produksi: produk utama & hasil samping', role: 'pabrik', viewport: 'desktop', height: 1200,
    prepare: async (p) => {
      await p.fill('.bt-lot >> nth=0', '2450').catch(() => {}); await p.dispatchEvent('.bt-lot >> nth=0', 'input').catch(() => {});
      await p.click('#btn-batch-model').catch(() => {}); await wait(p, 1500);
    },
    anchor: '#bt-o-bio_pellet',                // kartu output berada di bawah daftar lot QC yang panjang
    marks: [{ sel: '#bt-o-biochar', n: 1 }, { sel: '#bt-o-bio_silika', n: 2 }, { sel: '#bt-l-susut_proses', n: 3 }, { sel: '#btn-batch', n: 4, color: 'green' }] },
  { file: '39_pabrik_laporan_esg.png', bab: '6.4 Laporan ESG (E · S · G)', role: 'pabrik', viewport: 'desktop',
    anchor: '#fx-esg-title',
    marks: [{ sel: '#fx-esg-from', n: 1 }, { sel: '#fx-esg-card', n: 2, color: 'green' }, { sel: '#fx-esg-csv', n: 3 }] },
  { file: '40_pabrik_klaim_karbon_ebc.png', bab: '6.4 Klaim removal karbon & uji lab (H/Corg, EBC/IBI)', role: 'pabrik', viewport: 'desktop', height: 1200,
    prepare: async (p) => {
      await p.fill('#fx-cc-corg', '45'); await p.fill('#fx-cc-hc', '0.3');
      await p.fill('#fx-cc-lab', 'Laboratorium Uji Mutu Mitra (terakreditasi KAN)'); await p.fill('#fx-cc-no', 'LHU-2026-10-0142');
      await p.click('#fx-cc-form button[data-mode="preview"]').catch(() => {}); await wait(p, 2000);  // Ajukan aktif setelah pratinjau
    },
    anchor: '#fx-cc-title',
    marks: [{ sel: '#fx-cc-corg', n: 1 }, { sel: '#fx-cc-hc', n: 2 }, { sel: '#fx-cc-lab', n: 3 }, { sel: '#fx-cc-no', n: 4 }, { sel: '#fx-cc-submit', n: 5, color: 'green' }] },
  { file: '41_pabrik_ledger_abu_kelompok_tani.png', bab: '6.4 Ledger abu → kelompok tani (uji logam berat)', role: 'pabrik', viewport: 'desktop',
    anchor: '#fx-ash-title',
    marks: [{ sel: 'card:Ledger Abu', n: 1 }, { sel: '#fx-ash-new', n: 2, color: 'green' }] },
  { file: '42_pabrik_surat_jalan_biochar.png', bab: '6.4 Surat jalan muatan balik biochar & serah-terima petani', role: 'pabrik', viewport: 'desktop',
    anchor: '#fx-br-title',
    marks: [{ sel: 'card:Serah-terima Biochar', n: 1 }, { sel: '#btn-fx-dispatch-biochar', n: 2, color: 'green' }, { sel: '#fx-bd-list', n: 3 }] },
];
