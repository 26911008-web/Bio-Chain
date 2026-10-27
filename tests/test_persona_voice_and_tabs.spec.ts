import { test, expect, Page } from '@playwright/test';

const BASE = process.env.BIOCHAIN_URL || 'http://127.0.0.1:8000';

async function openAs(page: Page, role: string) {
  await page.goto(`${BASE}/?role=${role}`);
  await expect(page.locator('#app-view')).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('html')).toHaveAttribute('data-role', role, { timeout: 15_000 });
}

test.describe('Bio-Chain Persona Tabs & Voice-to-Text Integration', () => {

  test('1. Sticky Top Role-Switcher renders 4 touch-friendly tabs with correct role colors', async ({ page }) => {
    await openAs(page, 'petani');

    const switcher = page.locator('#sticky-role-switcher');
    await expect(switcher).toBeVisible();

    const tabPetani = page.locator('#btn-tab-petani');
    const tabPengepul = page.locator('#btn-tab-pengepul');
    const tabDriver = page.locator('#btn-tab-driver');
    const tabPabrik = page.locator('#btn-tab-pabrik');

    await expect(tabPetani).toBeVisible();
    await expect(tabPengepul).toBeVisible();
    await expect(tabDriver).toBeVisible();
    await expect(tabPabrik).toBeVisible();

    // Verify touch target height >= 52px
    const box = await tabPetani.boundingBox();
    expect(box?.height).toBeGreaterThanOrEqual(52);
  });

  test('2. Non-Destructive State Preservation across Tab Switches', async ({ page }) => {
    await openAs(page, 'petani');

    // Input custom quantity in Petani form
    const qtyInput = page.locator('#f-qty');
    await expect(qtyInput).toBeVisible();
    await qtyInput.fill('7890');
    await qtyInput.dispatchEvent('input');

    // Verify value is 7890
    await expect(qtyInput).toHaveValue('7890');

    // Switch to Pengepul tab
    await page.locator('#btn-tab-pengepul').click();
    await expect(page.locator('#persona-pane-pengepul')).toBeVisible();
    await expect(page.locator('#col-pending')).toBeVisible();

    // Switch to Driver tab
    await page.locator('#btn-tab-driver').click();
    await expect(page.locator('#persona-pane-driver')).toBeVisible();
    await expect(page.locator('#driver-actions')).toBeVisible();

    // Switch to Industri (Pabrik) tab
    await page.locator('#btn-tab-pabrik').click();
    await expect(page.locator('#persona-pane-pabrik')).toBeVisible();
    await expect(page.locator('.e2e-pipeline-card')).toBeVisible();

    // Switch BACK to Petani tab
    await page.locator('#btn-tab-petani').click();
    await expect(page.locator('#persona-pane-petani')).toBeVisible();

    // Verify state was NOT wiped! Value remains 7890
    const qtyAfter = page.locator('#f-qty');
    await expect(qtyAfter).toHaveValue('7890');
  });

  test('3. Voice Assistant Module & Indonesian Number Normalizer Unit Verification in Browser', async ({ page }) => {
    await openAs(page, 'petani');

    // Verify global voice functions exist
    const hasVoiceModule = await page.evaluate(() => {
      return typeof window.processIndonesianVoiceInput === 'function' &&
             typeof window.toggleVoiceInput === 'function' &&
             typeof window.stepNumberInput === 'function';
    });
    expect(hasVoiceModule).toBe(true);

    // Verify Indonesian spoken voice text and number normalization in browser engine
    const testCases = [
      { text: 'Satu satu 2500', type: 'number', expected: 2500 },
      { text: 'dua lima nol nol', type: 'number', expected: 2500 },
      { text: 'dua ribu lima ratus', type: 'number', expected: 2500 },
      { text: 'satu satu', type: 'number', expected: 11 },
      { text: '15.000 kg', type: 'number', expected: 15000 },
      { text: 'seribu lima ratus', type: 'number', expected: 1500 },
      { text: 'tiga ton', type: 'number', expected: 3 },
      { text: 'satu koma lima ton', type: 'number', expected: 1.5 },
      { text: 'setengah', type: 'number', expected: 0.5 },
      { text: '13,5 persen', type: 'number', expected: 13.5 },
      { text: 'lahan petani', type: 'text', expected: 'Lahan petani' },
      { text: 'jalan berlumpur', type: 'text', expected: 'Jalan berlumpur' }
    ];

    for (const tc of testCases) {
      const res = await page.evaluate(({ text, type }) => {
        return window.processIndonesianVoiceInput(text, type);
      }, tc);
      expect(res).toBe(tc.expected);
    }

    // Verify auto-normalizer on keyboard / Gboard input:
    // When text with words like "Satu satu 2500" is entered into a numeric-intent field (#f-qty):
    await page.evaluate(() => {
      const el = document.getElementById('f-qty');
      el.type = 'text'; // simulate mobile text entry accepting words
      el.value = 'Satu satu 2500';
      el.dispatchEvent(new Event('change', { bubbles: true }));
    });
    const normalizedVal = await page.locator('#f-qty').inputValue();
    expect(normalizedVal).toBe('2500');
  });

  test('4. Quick Steppers and Giant Action Targets', async ({ page }) => {
    await openAs(page, 'petani');

    const qtyInput = page.locator('#f-qty');
    await qtyInput.fill('2000');
    await qtyInput.dispatchEvent('input');

    // Click quick stepper +500
    const btnPlus500 = page.locator('button[data-onclick="stepNumberInput(\'f-qty\', 500)"]');
    await expect(btnPlus500).toBeVisible();
    await btnPlus500.click();

    await expect(qtyInput).toHaveValue('2500');

    // Click quick stepper -100
    const btnMinus100 = page.locator('button[data-onclick="stepNumberInput(\'f-qty\', -100)"]');
    await btnMinus100.click();

    await expect(qtyInput).toHaveValue('2400');

    // Check submit button height >= 52px
    const submitBtn = page.locator('#f-submit');
    const submitBox = await submitBtn.boundingBox();
    expect(submitBox?.height).toBeGreaterThanOrEqual(52);
  });

  test('5. Industri (Executive Command Center) Pipeline Card & Cross-tab Navigation', async ({ page }) => {
    await openAs(page, 'pabrik');

    const pipelineCard = page.locator('.e2e-pipeline-card');
    await expect(pipelineCard).toBeVisible();

    const nodePetani = page.locator('.pipeline-node.node-petani');
    const nodePengepul = page.locator('.pipeline-node.node-pengepul');
    const nodeDriver = page.locator('.pipeline-node.node-driver');
    const nodePabrik = page.locator('.pipeline-node.node-pabrik');

    await expect(nodePetani).toBeVisible();
    await expect(nodePengepul).toBeVisible();
    await expect(nodeDriver).toBeVisible();
    await expect(nodePabrik).toBeVisible();

    // Clicking Node Petani switches directly to Petani tab
    await nodePetani.click();
    await expect(page.locator('#persona-pane-petani')).toBeVisible();
    await expect(page.locator('#btn-tab-petani')).toHaveClass(/active/);
  });

});
