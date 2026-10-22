import { test, expect } from '@playwright/test';

const BASE = process.env.BIOCHAIN_URL || 'http://127.0.0.1:8000';

test('Table pagination, 10/20/semua filter, and horizontal scroll navigation', async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto(`${BASE}/?role=petani`);
  await expect(page.locator('html')).toHaveAttribute('data-role', 'petani', { timeout: 20_000 });

  // 1. Check Petani harvests table toolbar
  const table = page.locator('#table-petani-harvests');
  await expect(table).toBeVisible({ timeout: 15_000 });
  const toolbar = page.locator('.table-pagination-toolbar[data-for="table-petani-harvests"]');
  await expect(toolbar).toBeVisible();

  // Verify options include 10, 20, 50, 100, and all
  const select = toolbar.locator('.tpt-select');
  await expect(select).toBeVisible();
  const optionTexts = await select.locator('option').allInnerTexts();
  expect(optionTexts).toContain('10 baris');
  expect(optionTexts).toContain('20 baris');
  expect(optionTexts).toContain('Semua baris data');

  // Verify scroll navigation buttons exist in toolbar
  const btnScrollLeft = toolbar.locator('.tpt-scroll-left');
  const btnScrollRight = toolbar.locator('.tpt-scroll-right');
  await expect(btnScrollLeft).toBeVisible();
  await expect(btnScrollRight).toBeVisible();

  // Test selecting 10 baris
  await select.selectOption('10');
  await page.waitForTimeout(300);

  const pageNum = toolbar.locator('.tpt-page-num');
  await expect(pageNum).toHaveText(/Hal 1 \/ \d+/);

  const btnNext = toolbar.locator('.tpt-next');
  const btnPrev = toolbar.locator('.tpt-prev');
  await expect(btnPrev).toBeDisabled();

  // If there are multiple pages, click Next ▶
  const totalPagesText = await pageNum.innerText();
  const match = totalPagesText.match(/Hal 1 \/ (\d+)/);
  const totalPages = match ? parseInt(match[1], 10) : 1;

  if (totalPages > 1) {
    await expect(btnNext).toBeEnabled();
    // Get visible row on page 1
    const firstRowTextPage1 = await table.locator('tbody tr:not(.group-header-row):visible').first().innerText();

    // Click Next
    await btnNext.click();
    await page.waitForTimeout(300);
    await expect(pageNum).toHaveText(/Hal 2 \/ \d+/);
    await expect(btnPrev).toBeEnabled();

    // Verify row on page 2 is different
    const firstRowTextPage2 = await table.locator('tbody tr:not(.group-header-row):visible').first().innerText();
    expect(firstRowTextPage2).not.toEqual(firstRowTextPage1);

    // Click Prev
    await btnPrev.click();
    await page.waitForTimeout(300);
    await expect(pageNum).toHaveText(/Hal 1 \/ \d+/);
    await expect(btnPrev).toBeDisabled();
    const firstRowTextBack = await table.locator('tbody tr:not(.group-header-row):visible').first().innerText();
    expect(firstRowTextBack).toEqual(firstRowTextPage1);
  }

  // Test selecting 20 baris
  await select.selectOption('20');
  await page.waitForTimeout(300);
  const visibleRows20 = await table.locator('tbody tr:visible').count();
  expect(visibleRows20).toBeGreaterThanOrEqual(1);

  // Test selecting Semua baris data
  await select.selectOption('all');
  await page.waitForTimeout(300);
  await expect(pageNum).toHaveText('Semua Baris');
  await expect(btnPrev).toBeDisabled();
  await expect(btnNext).toBeDisabled();

  // 2. Check Pengepul persona tables
  await page.goto(`${BASE}/?role=pengepul`);
  await expect(page.locator('html')).toHaveAttribute('data-role', 'pengepul', { timeout: 20_000 });

  // Verify toolbars are rendered on pengepul tables
  const pengepulToolbars = page.locator('.table-pagination-toolbar');
  await expect(pengepulToolbars.first()).toBeVisible({ timeout: 15_000 });
  const count = await pengepulToolbars.count();
  expect(count).toBeGreaterThanOrEqual(1);

  // 3. Test horizontal scroll navigation on a wide table (Market Table)
  const marketTable = page.locator('#market-table table.data-table').first();
  if (await marketTable.count() > 0) {
    const marketToolbar = page.locator('.table-pagination-toolbar').first();
    const marketScrollRight = marketToolbar.locator('.tpt-scroll-right');
    const marketScrollLeft = marketToolbar.locator('.tpt-scroll-left');
    await expect(marketScrollRight).toBeVisible();
    await expect(marketScrollLeft).toBeVisible();
  }
});
