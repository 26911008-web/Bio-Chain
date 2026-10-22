/**
 * Bio-Chain — Penangkap Screenshot Beranotasi untuk Manual Book
 *
 * Membuka aplikasi sungguhan per persona, mengisi data contoh realistis ("populate-before-snap"),
 * menyuntikkan kotak sorot merah/hijau + lencana ① ② ③ di atas elemen, lalu memotret layar.
 * Daftar layar ada di scripts/manual_shots_manifest.mts.
 *
 * Jalankan pada SALINAN database agar data demo tidak mengotori biochain.db utama:
 *   copy biochain.db manual_demo.db   (ikut salin -wal/-shm bila ada)
 *   set DATABASE_URL=sqlite+aiosqlite:///manual_demo.db && py -m uvicorn app.main:app --port 8765
 *   set BIOCHAIN_URL=http://127.0.0.1:8765 && node scripts/capture_annotated_manual.mts [filter]
 *
 * `filter` (opsional) = regex awalan nama file, mis. `0|1[0-2]` (bab petani) atau `14_` (satu layar).
 * Hasil: docs/manual/screenshots/*.png + _capture_report.json (selector yang tidak ketemu).
 */
import { chromium } from 'playwright';
import type { Browser, BrowserContext, Page } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { SHOTS, seedScenario } from './manual_shots_manifest.mts';
import type { Mark, Shot, Scenario } from './manual_shots_manifest.mts';

const BASE = process.env.BIOCHAIN_URL || 'http://127.0.0.1:8765';
const OUT_DIR = path.resolve(import.meta.dirname, '../docs/manual/screenshots');
const VIEWPORTS = {
  mobile: { width: 390, height: 844 },
  desktop: { width: 1440, height: 900 },
} as const;

/** ① … ⑳ (U+2460 dst). */
export const circled = (n: number): string => String.fromCodePoint(0x2460 + n - 1);

/**
 * Gambar kotak sorot + lencana nomor bulat di pojok kiri-atas elemen.
 * Selector: CSS biasa, atau `card:<teks judul>` → kartu terdekat dari h3/h4 yang memuat teks itu.
 * Lapisan anotasi `position:fixed` di atas viewport, jadi panggil setelah elemen di-scroll ke layar.
 * Mengembalikan false bila elemen tidak ditemukan / tidak terlihat.
 */
export async function highlightAndBadge(page: Page, selector: string, stepNumber: number,
  color: 'red' | 'green' = 'red'): Promise<boolean> {
  return page.evaluate(({ selector, badge, color }) => {
    const resolve = (sel: string): Element | null => {
      if (!sel.startsWith('card:')) return document.querySelector(sel);
      const needle = sel.slice(5).toLowerCase();
      const head = [...document.querySelectorAll('h3, h4')]
        .find(h => (h as HTMLElement).offsetParent !== null && h.textContent!.toLowerCase().includes(needle));
      return head ? (head.closest('.card') || head.parentElement) : null;
    };
    const el = resolve(selector);
    if (!el) return false;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return false;
    // Elemen di luar layar → laporkan hilang, jangan dijepit ke tepi (lencana palsu di header)
    if (r.bottom < 8 || r.top > window.innerHeight - 8 || r.right < 8 || r.left > window.innerWidth - 8) return false;

    // <dialog> showModal() ada di top layer browser (di atas z-index apa pun) → lapisan ikut masuk ke dialog
    const dialogs = [...document.querySelectorAll('dialog[open]')];
    const host = dialogs.length ? dialogs[dialogs.length - 1] : document.body;
    let layer = document.getElementById('manual-annot-layer');
    if (layer && layer.parentElement !== host) { layer.remove(); layer = null; }
    if (!layer) {
      layer = document.createElement('div');
      layer.id = 'manual-annot-layer';
      layer.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483647;';
      host.appendChild(layer);
    }
    const hex = color === 'green' ? '#22C55E' : '#EF4444';
    const glow = color === 'green' ? 'rgba(34,197,94,0.5)' : 'rgba(239,68,68,0.5)';
    const vw = window.innerWidth, vh = window.innerHeight;
    const top = Math.max(2, r.top - 4), left = Math.max(2, r.left - 4);
    const width = Math.min(vw - left - 2, r.width + 8), height = Math.min(vh - top - 2, r.height + 8);

    const box = document.createElement('div');
    box.style.cssText = `position:absolute;top:${top}px;left:${left}px;width:${width}px;height:${height}px;`
      + `border:3px solid ${hex};box-shadow:0 0 12px ${glow};border-radius:8px;box-sizing:border-box;`;
    const dot = document.createElement('div');
    dot.textContent = badge;
    dot.style.cssText = `position:absolute;top:${Math.max(2, top - 14)}px;left:${Math.max(2, left - 14)}px;`
      + `width:30px;height:30px;border-radius:50%;background:${hex};color:#fff;border:2px solid #fff;`
      + `font:700 20px/26px system-ui,sans-serif;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.45);`;
    layer.append(box, dot);
    return true;
  }, { selector, badge: circled(stepNumber), color });
}

export async function clearAnnotations(page: Page): Promise<void> {
  await page.evaluate(() => document.getElementById('manual-annot-layer')?.remove());
}

/** Login demo per peran lewat `/?role=` (app.js memakai akun demo peran itu). */
async function openAs(page: Page, role: string): Promise<void> {
  for (let attempt = 1; ; attempt++) {                      // dashboard pabrik berat: satu kali coba ulang
    await page.goto(`${BASE}/?role=${role}`);
    try { await page.waitForSelector(`html[data-role="${role}"]`, { timeout: 45_000 }); break; }
    catch (e) { if (attempt >= 2) throw e; }
  }
  await page.waitForTimeout(3_000);                         // tabel & KPI dimuat async
}

async function scrollToAnchor(page: Page, sel: string): Promise<void> {
  await page.evaluate((sel) => {
    let el: Element | null;
    if (sel.startsWith('card:')) {
      const needle = sel.slice(5).toLowerCase();
      el = [...document.querySelectorAll('h3, h4')]
        .find(h => (h as HTMLElement).offsetParent !== null && h.textContent!.toLowerCase().includes(needle)) || null;
      el = el ? (el.closest('.card') || el) : null;
    } else {
      el = document.querySelector(sel);
    }
    el?.scrollIntoView({ block: 'start', inline: 'nearest', behavior: 'instant' as ScrollBehavior });
    // Turunkan sejauh tinggi header/bar lengket di atas layar agar elemen tidak tertutup
    const header = [...document.querySelectorAll('body *')].filter((e) => {
      const s = getComputedStyle(e), r = e.getBoundingClientRect();
      return (s.position === 'sticky' || s.position === 'fixed') && r.top <= 1 && r.height < 320 && r.width > window.innerWidth * 0.8;
    }).reduce((m, e) => Math.max(m, e.getBoundingClientRect().bottom), 0);
    window.scrollBy(0, -(header + 16));
    window.scrollTo({ left: 0, top: window.scrollY, behavior: 'instant' as ScrollBehavior });  // cegah halaman tergeser ke samping
  }, sel);
  await page.waitForTimeout(400);
}

interface ShotResult { file: string; ok: boolean; missing: string[]; error?: string }

async function capture(page: Page, shot: Shot, sc: Scenario): Promise<ShotResult> {
  const missing: string[] = [];
  const base = page.viewportSize();
  try {
    if (shot.height && base) await page.setViewportSize({ width: base.width, height: shot.height });
    if (shot.prepare) await shot.prepare(page, sc);
    if (shot.anchor) await scrollToAnchor(page, shot.anchor);
    await clearAnnotations(page);
    await page.evaluate(() => {                              // tombol Asisten AI melayang menutupi isi layar
      const fab = document.getElementById('ai-fab'); if (fab) fab.style.visibility = 'hidden';
      (document.activeElement as HTMLElement | null)?.blur();
    });
    const marks: Mark[] = typeof shot.marks === 'function' ? shot.marks(sc) : shot.marks;
    for (const m of marks) {
      if (!(await highlightAndBadge(page, m.sel, m.n, m.color))) missing.push(`${circled(m.n)} ${m.sel}`);
    }
    await page.screenshot({ path: path.join(OUT_DIR, shot.file), fullPage: false });
    if (shot.cleanup) await shot.cleanup(page, sc);
    return { file: shot.file, ok: missing.length === 0, missing };
  } catch (e) {
    return { file: shot.file, ok: false, missing, error: (e as Error).message.split('\n')[0] };
  } finally {
    if (shot.height && base) await page.setViewportSize(base).catch(() => {});
  }
}

async function main(): Promise<void> {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const filter = process.argv[2] || '';
  const shots = SHOTS.filter(s => new RegExp(`^(${filter})`).test(s.file));
  console.log(`📸 ${shots.length} layar → ${OUT_DIR} (server ${BASE})`);

  const sc = await seedScenario(BASE);
  console.log(`🌱 Skenario: panen #${sc.harvestId} (${sc.harvestQr}), listing lelang #${sc.listingId}`);

  const browser: Browser = await chromium.launch({
    args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
  });
  const results: ShotResult[] = [];
  let ctx: BrowserContext | null = null;
  let page: Page | null = null;
  let session = '';
  for (const shot of shots) {
    const key = `${shot.role}/${shot.viewport}`;
    if (key !== session || shot.fresh) {                    // satu sesi browser per peran+viewport
      await ctx?.close();
      ctx = await browser.newContext({
        viewport: VIEWPORTS[shot.viewport], deviceScaleFactor: 2,
        isMobile: shot.viewport === 'mobile', hasTouch: shot.viewport === 'mobile',
        locale: 'id-ID', timezoneId: 'Asia/Jakarta',
        permissions: ['geolocation', 'camera'], geolocation: { latitude: -7.7203, longitude: 110.3541, accuracy: 10 },
      });
      page = await ctx.newPage();
      page.on('dialog', d => d.dismiss().catch(() => {}));  // jangan sampai prompt() memblok skrip
      if (shot.role === 'login') await page.goto(BASE); else await openAs(page, shot.role);
      session = key;
    }
    const res = await capture(page!, shot, sc);
    results.push(res);
    console.log(`${res.ok ? '✅' : '⚠️ '} ${shot.file}${res.missing.length ? '  tidak ketemu: ' + res.missing.join(', ') : ''}${res.error ? '  ERROR: ' + res.error : ''}`);
  }
  await ctx?.close();
  await browser.close();
  fs.writeFileSync(path.join(OUT_DIR, '_capture_report.json'), JSON.stringify({ base: BASE, at: new Date().toISOString(), scenario: sc, results }, null, 2));
  const bad = results.filter(r => !r.ok).length;
  console.log(`\nSelesai: ${results.length - bad}/${results.length} layar lengkap anotasinya.`);
}

main().catch((e) => { console.error(e); process.exit(1); });
