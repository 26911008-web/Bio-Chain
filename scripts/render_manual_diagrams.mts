/**
 * Render blok ```mermaid di docs/manual/parts/*.md → docs/manual/diagrams/diagram_NN.png
 * (dipakai scripts/build_manual_docx.py; Word tidak bisa merender mermaid).
 *
 *   node scripts/render_manual_diagrams.mts
 */
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const MANUAL = path.resolve(import.meta.dirname, '../docs/manual');
const PARTS = ['bab1_bab2.md', 'bab3_petani.md', 'bab4_bab5.md', 'bab6_pabrik.md', 'storyboard_video.md', 'troubleshooting.md'];
const MERMAID = 'https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js';
const SRI = 'sha384-WmdflGW9aGfoBdHc4rRyWzYuAjEmDwMdGdiPNacbwfGKxBW/SO6guzuQ76qjnSlr';

const blocks: string[] = [];
for (const p of PARTS) {
  const md = fs.readFileSync(path.join(MANUAL, 'parts', p), 'utf8');
  for (const m of md.matchAll(/```mermaid\r?\n([\s\S]*?)```/g)) blocks.push(m[1]);
}
const outDir = path.join(MANUAL, 'diagrams');
fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2 });
for (const [i, code] of blocks.entries()) {
  const esc = code.replace(/&/g, '&amp;').replace(/</g, '&lt;');
  await page.setContent(`<!doctype html><html><body style="margin:0;background:#fff">
    <pre class="mermaid" id="d">${esc}</pre>
    <script src="${MERMAID}" integrity="${SRI}" crossorigin="anonymous"></script>
    <script>mermaid.initialize({ startOnLoad: true, theme: 'neutral' });</script></body></html>`);
  await page.waitForSelector('#d svg', { timeout: 30_000 });
  const file = path.join(outDir, `diagram_${String(i + 1).padStart(2, '0')}.png`);
  await page.locator('#d svg').screenshot({ path: file });
  console.log(`🖼️  ${file}`);
}
await browser.close();
console.log(`${blocks.length} diagram dirender.`);
