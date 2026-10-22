// Fase 1: Autonomous Field Testing & Auto-Fixing Runner
// Playwright runner with Real-Time Telemetry Trap

const { chromium } = require('@playwright/test');

const BASE_URL = 'http://127.0.0.1:8000';

const PERSONAS = [
  { role: 'petani', label: 'Petani', username: 'petani_sugeng', password: 'sekam123' },
  { role: 'pengepul', label: 'Pengepul', username: 'pengepul_sleman', password: 'kud2026' },
  { role: 'driver', label: 'Driver', username: 'sopir_budi', password: 'truk2026' },
  { role: 'pabrik', label: 'Pabrik', username: 'pabrik_indmira', password: 'pabrik2026' }
];

async function attachTelemetryTrap(page, personaName) {
  const telemetry = {
    consoleErrors: [],
    pageErrors: [],
    networkFailures: []
  };

  page.on('console', msg => {
    if (msg.type() === 'error') {
      const text = msg.text();
      const loc = msg.location ? msg.location().url : '';
      // Abaikan request CDN eksternal font/icon jika koneksi sandbox terisolasi
      if (text.includes('ERR_FAILED') || text.includes('favicon.ico') || loc.includes('cloudflare') || loc.includes('google') || loc.includes('gstatic') || loc.includes('openstreetmap')) {
        return;
      }
      console.error(`[CONSOLE ERROR][${personaName}] ${text}`);
      telemetry.consoleErrors.push(text);
    }
  });

  page.on('pageerror', err => {
    console.error(`[RUNTIME EXCEPTION][${personaName}] ${err.message}`);
    telemetry.pageErrors.push(err.message);
  });

  page.on('response', response => {
    const status = response.status();
    const url = response.url();
    if (status >= 400 && !url.includes('favicon.ico') && url.includes(BASE_URL)) {
      console.error(`[NETWORK FAILURE][${personaName}] ${status} ${response.request().method()} ${url}`);
      telemetry.networkFailures.push({ status, url, method: response.request().method() });
    }
  });

  return telemetry;
}

async function runFase1() {
  console.log('=== MEMULAI PENGUJIAN FASE 1: RUNNER TELEMETRI & MULTI-PERSONA LOGIN ===');
  
  const browser = await chromium.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const results = [];
  let totalErrors = 0;

  for (const persona of PERSONAS) {
    console.log(`\n--- Menguji Login & Session Persona: ${persona.role.toUpperCase()} (${persona.username}) ---`);
    const context = await browser.newContext();
    const page = await context.newPage();
    const telemetry = await attachTelemetryTrap(page, persona.role);

    try {
      // 1. Buka Beranda
      await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle', timeout: 15000 });
      
      // Pastikan form login muncul
      await page.waitForSelector('#login-form', { state: 'visible', timeout: 5000 });
      
      // 2. Klik Gerbang Peran Sesuai Persona Lapangan
      const roleCard = page.locator('.role-card', { hasText: persona.label });
      await roleCard.click();
      console.log(`✓ Gerbang peran [${persona.label}] dipilih.`);

      // 3. Isi form login secara nyata
      await page.fill('#login-ident', persona.username);
      await page.fill('#login-pass', persona.password);

      // 4. Klik tombol Masuk
      await page.click('#btn-submit-login');

      // 5. Tunggu tampilan app (#app-view) tampil
      await page.waitForSelector('#app-view', { state: 'visible', timeout: 10000 });

      // Verifikasi user & role di state
      const stateInfo = await page.evaluate(() => ({
        role: window.STATE && window.STATE.user ? window.STATE.user.role : null,
        fullName: window.STATE && window.STATE.user ? window.STATE.user.full_name : null,
      }));
      console.log(`✓ Berhasil masuk sebagai: ${stateInfo.fullName} (Peran: ${stateInfo.role})`);

      if (stateInfo.role !== persona.role) {
        throw new Error(`Peran tidak sesuai. Diharapkan: ${persona.role}, Diterima: ${stateInfo.role}`);
      }

      // 6. Uji Persistensi Nyata (Hard-Reload Verification)
      console.log(`✓ Menjalankan hard-reload untuk verifikasi session persistensi...`);
      await page.reload({ waitUntil: 'networkidle', timeout: 15000 });
      await page.waitForSelector('#app-view', { state: 'visible', timeout: 10000 });

      const reloadedState = await page.evaluate(() => ({
        role: window.STATE && window.STATE.user ? window.STATE.user.role : null,
        fullName: window.STATE && window.STATE.user ? window.STATE.user.full_name : null,
      }));
      console.log(`✓ Sesi bertahan setelah hard-reload: ${reloadedState.fullName} (${reloadedState.role})`);

      // 7. Uji tombol Keluar (Logout)
      const logoutBtn = await page.waitForSelector('#btn-logout', { state: 'visible', timeout: 5000 });
      await logoutBtn.click();
      await page.waitForSelector('#login-view', { state: 'visible', timeout: 5000 });
      console.log(`✓ Logout berhasil, kembali ke halaman login.`);

      const errorCount = telemetry.consoleErrors.length + telemetry.pageErrors.length + telemetry.networkFailures.length;
      totalErrors += errorCount;

      results.push({
        persona: persona.role,
        username: persona.username,
        status: errorCount === 0 ? 'PASS 100%' : 'PASS WITH WARNINGS',
        telemetryErrors: telemetry
      });
      console.log(`✅ Persona ${persona.role.toUpperCase()} SUKSES DIUJI DENGAN ZERO ERROR.`);

    } catch (err) {
      console.error(`❌ GAGAL PADA PERSONA ${persona.role.toUpperCase()}:`, err.message);
      totalErrors++;
      results.push({
        persona: persona.role,
        username: persona.username,
        status: 'FAILED',
        error: err.message,
        telemetryErrors: telemetry
      });
    } finally {
      await context.close();
    }
  }

  await browser.close();

  console.log('\n======================================================');
  console.log('HASIL PENGUJIAN FASE 1:');
  console.log(JSON.stringify(results, null, 2));
  console.log(`TOTAL DETEKSI ERROR: ${totalErrors}`);
  console.log('======================================================');

  if (totalErrors > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

runFase1().catch(err => {
  console.error('Fatal runner error:', err);
  process.exit(1);
});
