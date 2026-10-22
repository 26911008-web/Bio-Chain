import { test, expect } from '@playwright/test';

/**
 * E2E Lapangan Ekstrem — foto HP resolusi tinggi dikompres di browser sebelum diunggah (hemat kuota sinyal desa).
 * Foto 4000×3000 penuh noise (kasus terburuk JPEG) harus menjadi ≤ 300 KB, sisi terpanjang ≤ 1600 px, tanpa EXIF.
 *
 *   set BIOCHAIN_URL=http://127.0.0.1:8765 && npx -y @playwright/test@1.64.0 test tests/e2e_photo_compression.spec.ts
 */
const BASE = process.env.BIOCHAIN_URL || 'http://127.0.0.1:8000';

test('foto 12 MP dikompres ≤ 300 KB sebelum unggah', async ({ page }) => {
  await page.goto(`${BASE}/?role=petani`);
  await expect(page.locator('#app-view')).toBeVisible({ timeout: 30_000 });
  await page.waitForFunction(() => !!(window as any).BiochainImage);
  const r = await page.evaluate(async () => {
    const c = document.createElement('canvas');
    c.width = 4000; c.height = 3000;
    const ctx = c.getContext('2d')!;
    const img = ctx.createImageData(c.width, c.height);
    let seed = 12345;
    for (let i = 0; i < img.data.length; i += 4) {
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      const n = seed & 0xff;
      img.data[i] = (i / 4 % 4000) / 16 + n / 2; img.data[i + 1] = n; img.data[i + 2] = 255 - n / 2; img.data[i + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
    const big: Blob = await new Promise(res => c.toBlob(b => res(b!), 'image/jpeg', 0.95));
    const file = new File([big], 'kamera.jpg', { type: 'image/jpeg' });
    const out: File = await (window as any).BiochainImage.compress(file);
    const bmp = await createImageBitmap(out);
    return { before: big.size, after: out.size, w: bmp.width, h: bmp.height, type: out.type,
             max: (window as any).BiochainImage.MAX_PHOTO_BYTES };
  });
  console.log(`kompres ${Math.round(r.before / 1024)} KB → ${Math.round(r.after / 1024)} KB (${r.w}×${r.h})`);
  expect(r.before).toBeGreaterThan(1_000_000);
  expect(r.after).toBeLessThanOrEqual(r.max);
  expect(r.max).toBe(300 * 1024);
  expect(Math.max(r.w, r.h)).toBeLessThanOrEqual(1600);
  expect(r.type).toBe('image/jpeg');
});
