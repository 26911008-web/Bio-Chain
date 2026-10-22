const { chromium } = require('@playwright/test');

const BASE_URL = 'http://127.0.0.1:8000';

const PERSONAS = [
  { role: 'petani', label: 'Petani', username: 'petani_sugeng', password: 'sekam123' },
  { role: 'pengepul', label: 'Pengepul', username: 'pengepul_sleman', password: 'kud2026' },
  { role: 'driver', label: 'Driver', username: 'sopir_budi', password: 'truk2026' },
  { role: 'pabrik', label: 'Pabrik', username: 'pabrik_indmira', password: 'pabrik2026' }
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  for (const p of PERSONAS) {
    console.log(`\nTesting login for: ${p.role.toUpperCase()} (${p.username})`);
    const page = await browser.newPage();
    await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' });

    // 1. Click the role gate card
    await page.locator('.role-card', { hasText: p.label }).click();
    console.log(`Clicked role card: ${p.label}`);

    // 2. Fill credentials
    await page.fill('#login-ident', p.username);
    await page.fill('#login-pass', p.password);

    // 3. Submit login
    await page.click('#btn-submit-login');

    // 4. Wait for #app-view to become visible
    await page.waitForSelector('#app-view', { state: 'visible', timeout: 10000 });
    console.log(`App view is visible!`);

    // 5. Verify user state and dashboard
    const userRole = await page.evaluate(() => STATE.user ? STATE.user.role : null);
    const userName = await page.evaluate(() => STATE.user ? STATE.user.full_name : null);
    console.log(`Logged in as: ${userName} (Role: ${userRole})`);

    // 6. Hard reload to verify session persistence
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForSelector('#app-view', { state: 'visible', timeout: 10000 });
    const reloadedRole = await page.evaluate(() => STATE.user ? STATE.user.role : null);
    console.log(`After reload: Role: ${reloadedRole}`);

    // 7. Test Logout
    await page.click('#btn-logout');
    await page.waitForSelector('#login-view', { state: 'visible', timeout: 10000 });
    console.log(`Logout successful!`);

    await page.close();
  }
  await browser.close();
  console.log('\nALL 4 PERSONAS PASSED LOGIN & SESSION TESTS!');
})();
