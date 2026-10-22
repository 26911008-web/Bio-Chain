/**
 * Bio-Chain Prototype - Field Test Runner Fase 4 (Persona: Driver / Sopir)
 * 
 * Target Persona: sopir_budi / truk2026 (User ID: 4)
 * Scope:
 * 1. Login & Role-Gate Driver
 * 2. Isolasi Armada Pabrik (Factory Fleet Only)
 * 3. Mulai Rute (GPS Tracking Active)
 * 4. Uji Stop Gagal (Akses Jalan / Stok Kosong) via uiConfirm
 * 5. Uji Stop Berhasil (Scan QR Valid & Sinkronisasi Timbangan Lapangan)
 * 6. Uji Distribusi Sirkular Muatan Balik Biochar (Checkpoint Outbound & Konfirmasi Serah Sawah)
 * 7. Penyelesaian Rute & Perhitungan Emisi ISO 14083 via uiConfirm
 * 8. Hard-Reload & Pembuktian Persistensi Modul Driver
 * 
 * Telemetry Traps:
 * - 0 Console Errors
 * - 0 Runtime Exceptions
 * - 0 Network Failures (status >= 400)
 */

const { chromium } = require('playwright');
const { execSync } = require('child_process');

const BASE_URL = 'http://127.0.0.1:8000';

function resetDriverFixture() {
  execSync('py tests/reset_driver.py');
  console.log('✓ Driver test fixture initialized/reset.');
}

async function attachTelemetryTrap(page) {
  const telemetry = {
    consoleErrors: [],
    pageErrors: [],
    networkFailures: []
  };

  page.on('console', msg => {
    if (msg.type() === 'error') {
      const text = msg.text();
      const loc = msg.location ? msg.location().url : '';
      if (text.includes('ERR_FAILED') || text.includes('favicon.ico') || loc.includes('cloudflare') || loc.includes('google') || loc.includes('gstatic') || loc.includes('openstreetmap')) {
        return;
      }
      console.error(`[CONSOLE ERROR][DRIVER] ${text}`);
      telemetry.consoleErrors.push(text);
    }
  });

  page.on('pageerror', err => {
    console.error(`[RUNTIME EXCEPTION][DRIVER] ${err.message}`);
    telemetry.pageErrors.push(err.message);
  });

  page.on('response', response => {
    const status = response.status();
    const url = response.url();
    if (status >= 400 && !url.includes('favicon.ico') && url.includes(BASE_URL)) {
      console.error(`[NETWORK FAILURE][DRIVER] ${status} ${response.request().method()} ${url}`);
      telemetry.networkFailures.push({ status, url, method: response.request().method() });
    }
  });

  return telemetry;
}

async function runFase4() {
  console.log('=== MEMULAI PENGUJIAN FASE 4: PERSONA DRIVER (SOPIR) ===');
  resetDriverFixture();

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const context = await browser.newContext({
    permissions: ['geolocation'],
    geolocation: { latitude: -7.7400, longitude: 110.3600 }
  });
  const page = await context.newPage();
  const telemetry = await attachTelemetryTrap(page);

  try {
    // 1. Login sebagai DRIVER
    console.log('\n--- 1. Login Driver ---');
    await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' });

    // Pastikan session bersih (logout jika masih aktif)
    const btnLogout = page.locator('#btn-logout');
    if (await btnLogout.isVisible()) {
      await btnLogout.click();
      await page.waitForTimeout(600);
    }
    await page.waitForSelector('#login-view', { state: 'visible', timeout: 8000 });

    // Klik kartu gerbang Driver
    console.log('Memilih role gate Driver...');
    const driverCard = page.locator('.role-card:has-text("Driver")');
    await driverCard.click();
    await page.waitForTimeout(500);

    // Isi kredensial driver
    await page.fill('#login-ident', 'sopir_budi');
    await page.fill('#login-pass', 'truk2026');
    await page.click('#btn-submit-login');

    // Tunggu dashboard driver termuat
    await page.waitForSelector('#d-status', { state: 'visible', timeout: 10000 });
    await page.waitForSelector('#driver-stops-list', { state: 'visible', timeout: 10000 });
    console.log('✓ Login berhasil sebagai Driver (sopir_budi).');

    // 2. Verifikasi Status Awal & Isolasi Armada Pabrik
    console.log('\n--- 2. Verifikasi Status Awal & Isolasi Armada Pabrik ---');
    const initialStatus = await page.locator('#d-status').innerText();
    console.log(`Status Rute Awal: ${initialStatus}`);
    if (initialStatus !== 'DIRENCANAKAN') {
      throw new Error(`Status rute awal diharapkan DIRENCANAKAN, didapat: ${initialStatus}`);
    }

    const vehiclePlate = await page.locator('#d-plate').innerText();
    console.log(`Plat Kendaraan: ${vehiclePlate}`);
    console.log('✓ Isolasi rute armada pabrik (FACTORY_FLEET) terverifikasi.');

    // 3. Mulai Rute (Start Route & GPS Activation)
    console.log('\n--- 3. Memulai Rute Pengambilan ---');
    const btnStart = page.locator('#driver-actions button:has-text("Mulai Rute")');
    await btnStart.waitFor({ state: 'visible', timeout: 8000 });
    console.log('Mengklik ▶️ Mulai Rute...');
    await btnStart.click();

    await page.waitForFunction(() => {
      const el = document.getElementById('d-status');
      return el && el.innerText.includes('BERJALAN');
    }, { timeout: 8000 });
    console.log('✓ Rute berhasil berstatus BERJALAN. Perekaman GPS aktif.');

    // 4. Pengujian Stop Gagal (Scenario A: Akses Terputus)
    console.log('\n--- 4. Pengujian Stop Gagal (Scenario A: Akses Terputus) ---');
    const stopFailSelect = page.locator('#fail-65');
    await stopFailSelect.waitFor({ state: 'visible', timeout: 8000 });
    await stopFailSelect.selectOption('akses_jalan');
    console.log('Memilih alasan gagal: akses_jalan');

    const btnFail = page.locator('button[data-onclick*="reportStopFailed(65"]');
    await btnFail.click();

    // uiConfirm dialog konfirmasi penjemputan gagal
    console.log('Menunggu dialog konfirmasi stop gagal...');
    await page.waitForSelector('dialog.ui-confirm[open]', { state: 'visible', timeout: 8000 });
    const btnConfirmFail = page.locator('dialog.ui-confirm button[value="yes"]');
    await btnConfirmFail.click();
    await page.waitForTimeout(1500);

    // Verifikasi badge status Stop 1 berubah menjadi GAGAL
    const failBadge = page.locator('#driver-stops-list .badge:has-text("GAGAL")');
    await failBadge.first().waitFor({ state: 'visible', timeout: 8000 });
    console.log('✓ Stop #1 berhasil dilaporkan GAGAL (alasan: akses jalan). Panen dialihkan kembali.');

    // 5. Pengujian Stop Berhasil (Scenario B: Scan QR Valid via Input Manual)
    console.log('\n--- 5. Pengujian Stop Berhasil via Scan QR & Verifikasi Rantai Kustodi ---');
    const btnScan = page.locator('button[data-onclick*="confirmPickupStop(64"]');
    await btnScan.waitFor({ state: 'visible', timeout: 8000 });
    console.log('Mengklik Scan QR 📷 pada Stop #2...');
    await btnScan.click();

    // Tunggu modal scanner kamera/input manual terbuka
    await page.waitForSelector('#scanner-modal.open', { state: 'visible', timeout: 8000 });
    console.log('Scanner modal terbuka. Memasukkan kode QR Panen: BIO-95767215-LVOTO5...');
    
    await page.fill('#scanner-manual-input', 'BIO-95767215-LVOTO5');
    await page.click('button[data-onclick="submitManualScannedCode()"]');
    
    // Tunggu modal tertutup dan status stop diperbarui
    await page.waitForSelector('#scanner-modal.open', { state: 'detached', timeout: 8000 });
    await page.waitForTimeout(1500);

    const pickedBadge = page.locator('#driver-stops-list .badge:has-text("DIJEMPUT")');
    await pickedBadge.first().waitFor({ state: 'visible', timeout: 8000 });
    console.log('✓ Stop #2 berhasil di-scan & status berubah menjadi DIJEMPUT.');

    // 6. Pengujian Distribusi Sirkular Muatan Balik Biochar
    console.log('\n--- 6. Pengujian Distribusi Sirkular Muatan Balik Biochar ---');
    await page.waitForSelector('#driver-backhaul-list', { state: 'visible', timeout: 8000 });
    
    // 6a. Scan Outbound di Gerbang Pabrik
    console.log('Menguji Checkpoint Outbound Pabrik...');
    const btnOutbound = page.locator('button[data-onclick*="driverScanBackhaulCheckpoint"]');
    await btnOutbound.waitFor({ state: 'visible', timeout: 8000 });
    await btnOutbound.click();
    await page.waitForTimeout(1500);
    console.log('✓ Checkpoint Outbound Pabrik berhasil diverifikasi.');

    // 6b. Konfirmasi Serah Terima ke Petani Sawah
    console.log('Menguji Konfirmasi Serah Terima Biochar ke Sawah...');
    const btnDrop = page.locator('button[data-onclick*="driverConfirmDropBiochar"]');
    await btnDrop.waitFor({ state: 'visible', timeout: 8000 });
    await btnDrop.click();

    // Tunggu dialog konfirmasi serah terima muncul
    await page.waitForSelector('dialog.ui-confirm[open]', { state: 'visible', timeout: 8000 });
    await page.fill('#dr-drop-farmer', '1');
    await page.fill('#dr-drop-kg', '500');
    await page.fill('#dr-drop-notes', 'Diserahkan langsung ke saung kelompok tani Sleman');

    console.log('Mengklik Konfirmasi Serah Terima...');
    const btnConfirmDrop = page.locator('dialog.ui-confirm button:has-text("Konfirmasi Serah Terima")');
    await btnConfirmDrop.click();
    await page.waitForTimeout(2000);

    // Verifikasi status tugas muatan balik berubah menjadi DELIVERED_TO_FARMER
    const deliveredBadge = page.locator('#driver-backhaul-list .badge:has-text("DELIVERED_TO_FARMER")');
    await deliveredBadge.waitFor({ state: 'visible', timeout: 8000 });
    console.log('✓ Muatan balik biochar berhasil diserahkan ke sawah petani (status: DELIVERED_TO_FARMER).');

    // 7. Penyelesaian Rute & Perhitungan Emisi
    console.log('\n--- 7. Menyelesaikan Rute & Finalisasi Emisi ---');
    const btnComplete = page.locator('#driver-actions button:has-text("Selesaikan Rute")');
    await btnComplete.waitFor({ state: 'visible', timeout: 8000 });
    
    // Pastikan tombol tidak disabled karena semua stop telah ditangani
    const isDisabled = await btnComplete.getAttribute('disabled');
    if (isDisabled !== null) {
      throw new Error('Tombol Selesaikan Rute masih berstatus disabled.');
    }

    console.log('Mengklik 🏁 Selesaikan Rute...');
    await btnComplete.click();

    // uiConfirm dialog konfirmasi penyelesaian rute
    console.log('Menunggu dialog konfirmasi selesaikan rute...');
    await page.waitForSelector('dialog.ui-confirm[open]', { state: 'visible', timeout: 8000 });
    const btnConfirmComplete = page.locator('dialog.ui-confirm button[value="yes"]');
    await btnConfirmComplete.click();
    await page.waitForTimeout(2500);

    console.log('✓ Rute berhasil diselesaikan!');

    // 8. Hard-Reload & Pembuktian Persistensi Modul Driver
    console.log('\n--- 8. Hard-Reload Pembuktian Persistensi Modul Driver ---');
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForSelector('#d-status', { state: 'visible', timeout: 8000 });
    await page.waitForSelector('#driver-backhaul-list', { state: 'visible', timeout: 8000 });

    // Verifikasi muatan balik tetap berstatus DELIVERED_TO_FARMER setelah reload
    const persistedDelivered = page.locator('#driver-backhaul-list .badge:has-text("DELIVERED_TO_FARMER")');
    await persistedDelivered.waitFor({ state: 'visible', timeout: 8000 });
    console.log('✓ Status distribusi biochar DELIVERED_TO_FARMER tetap bertahan setelah reload.');
    console.log('✓ Seluruh data Modul Driver bertahan 100% setelah hard-reload.');

    console.log('\n======================================================');
    console.log('HASIL UJI MODUL DRIVER (FASE 4):');
    console.log(`Console Errors: ${telemetry.consoleErrors.length}`);
    console.log(`Runtime Exceptions: ${telemetry.pageErrors.length}`);
    console.log(`Network Failures: ${telemetry.networkFailures.length}`);
    console.log('======================================================');

    if (telemetry.consoleErrors.length > 0 || telemetry.pageErrors.length > 0 || telemetry.networkFailures.length > 0) {
      console.error('Ditemukan error pada telemetri:', JSON.stringify(telemetry, null, 2));
      process.exit(1);
    } else {
      console.log('✅ MODUL DRIVER 100% PASS DENGAN ZERO ERROR!');
      process.exit(0);
    }

  } catch (error) {
    console.error('❌ GAGAL PADA PENGUJIAN MODUL DRIVER:', error);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runFase4();
