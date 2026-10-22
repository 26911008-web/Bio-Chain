const { chromium } = require('@playwright/test');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:8000/');
  
  const before = await page.evaluate(() => window.STATE ? window.STATE.gate : 'no state');
  console.log('Before gate:', before);
  
  // Click Pengepul role card
  await page.locator('.role-card', { hasText: 'Pengepul' }).click();
  const after = await page.evaluate(() => window.STATE ? window.STATE.gate : 'no state');
  console.log('After clicking Pengepul card:', after);
  
  await browser.close();
})();
