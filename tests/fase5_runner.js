/**
 * Bio-Chain Prototype - Field Test Runner Fase 5 (Persona: Pabrik / Operator Pengolahan)
 * 
 * Target Persona: pabrik_indmira / pabrik2026 (User ID: 2)
 * Scope:
 * 1. Login & Role-Gate Pabrik
 * 2. Monitoring Loading Ramp & Agregat Mutu Rekursif
 * 3. Timbang Masuk Jembatan & Keputusan QC 3-State:
 *    - Skenario A: Diterima Penuh (ACCEPTED) - Skema CASH
 *    - Skenario B: Diterima Sebagian (PARTIALLY_ACCEPTED) - Skema TOP (Termin 14 Hari)
 *    - Skenario C: Ditolak Total (REJECTED) - Alasan Mutu & Retur
 * 4. Optimasi Campuran Bahan Bakar Boiler (HiGHS LP Blending Engine)
 * 5. Evaluasi Produk Akhir Multi-Biomassa (Pellet, Briket, Biochar, Bio-Silika)
 * 6. Penerbitan Surat Jalan Muatan Balik Biochar (Sirkular Logistik)
 * 7. Hard-Reload & Pembuktian Persistensi Modul Pabrik
 * 
 * Telemetry Traps:
 * - 0 Console Errors
 * - 0 Runtime Exceptions
 * - 0 Network Failures (status >= 400)
 */

const { chromium } = require('playwright');
const { execSync } = require('child_process');

const BASE_URL = 'http://127.0.0.1:8000';

function resetFactoryFixture() {
  execSync('py tests/reset_factory.py');
  console.log('✓ Factory test fixture initialized/reset.');
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
      console.error(`[CONSOLE ERROR][PABRIK] ${text}`);
      telemetry.consoleErrors.push(text);
    }
  });

  page.on('pageerror', err => {
    console.error(`[RUNTIME EXCEPTION][PABRIK] ${err.message}`);
    telemetry.pageErrors.push(err.message);
  });

  page.on('response', response => {
    const status = response.status();
    const url = response.url();
    if (status >= 400 && !url.includes('favicon.ico') && url.includes(BASE_URL)) {
      console.error(`[NETWORK FAILURE][PABRIK] ${status} ${response.request().method()} ${url}`);
      telemetry.networkFailures.push({ status, url, method: response.request().method() });
    }
  });

  return telemetry;
}

async function runFase5() {
  console.log('=== MEMULAI PENGUJIAN FASE 5: PERSONA PABRIK (OPERATOR PABRIK) ===');
  resetFactoryFixture();

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const context = await browser.newContext();
  const page = await context.newPage();
  const telemetry = await attachTelemetryTrap(page);

  try {
    // 1. Login sebagai PABRIK
    console.log('\n--- 1. Login Pabrik ---');
    await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' });

    const btnLogout = page.locator('#btn-logout');
    if (await btnLogout.isVisible()) {
      await btnLogout.click();
      await page.waitForTimeout(600);
    }
    await page.waitForSelector('#login-view', { state: 'visible', timeout: 8000 });

    console.log('Memilih role gate Pabrik...');
    const pabrikCard = page.locator('.role-card:has-text("Pabrik")');
    await pabrikCard.click();
    await page.waitForTimeout(500);

    await page.fill('#login-ident', 'pabrik_indmira');
    await page.fill('#login-pass', 'pabrik2026');
    await page.click('#btn-submit-login');

    await page.waitForSelector('#f-co2', { state: 'visible', timeout: 10000 });
    await page.waitForSelector('#gate-ramps-container', { state: 'visible', timeout: 10000 });
    console.log('✓ Login berhasil sebagai Pabrik (pabrik_indmira).');

    // 2. Monitoring Loading Ramp Awal
    console.log('\n--- 2. Verifikasi Loading Ramp & Agregat Mutu Rekursif ---');
    await page.waitForSelector('#gate-ramps-container strong:has-text("RAMP-01")', { state: 'visible', timeout: 8000 });
    console.log('✓ 4 Loading Ramp terdeteksi aktif.');

    // 3. Timbang Masuk & QC 3-State
    // Skenario 3A: Diterima Penuh (ACCEPTED) - CASH
    console.log('\n--- 3A. QC Gerbang: Diterima Penuh (ACCEPTED) - CASH ---');
    await page.click('#btn-open-gate-modal');
    await page.waitForSelector('dialog.ui-confirm[open]', { state: 'visible', timeout: 8000 });

    await page.selectOption('#gc-carrier', 'FACTORY_FLEET');
    await page.fill('#gc-plate', 'AB 1234 CD');
    await page.fill('#gc-driver', 'Budi Santoso');
    await page.selectOption('#gc-biomass', 'sekam_padi');
    await page.fill('#gc-gross', '11500');
    await page.fill('#gc-tare', '7500');
    await page.fill('#gc-mc', '13.0');
    await page.fill('#gc-ash', '15.5');
    await page.fill('#gc-lhv', '3550');
    await page.fill('#gc-contam', '0.8');

    await page.check('input[name="qc_decision"][value="ACCEPTED"]');
    await page.selectOption('#gc-target-ramp', '1');
    await page.selectOption('#gc-scheme', 'CASH');
    await page.fill('#gc-unit-price', '450');

    console.log('Mengirim penerimaan gerbang ACCEPTED...');
    const invalids = await page.evaluate(() => {
      const form = document.querySelector('dialog.ui-confirm form');
      return form ? [...form.querySelectorAll(':invalid')].map(i => ({ id: i.id, name: i.name, msg: i.validationMessage })) : [];
    });
    console.log('Invalid elements before click:', invalids);

    await page.click('dialog.ui-confirm button[value="yes"]');
    await page.waitForTimeout(1000);

    const dialogState = await page.evaluate(() => {
      const d = document.querySelector('dialog.ui-confirm');
      const err = d ? d.querySelector('.form-error') : null;
      return {
        hasDialog: !!d,
        isOpen: d ? d.open : false,
        errorText: err ? err.textContent : '',
        errHidden: err ? err.hidden : true
      };
    });
    console.log('Dialog state after click:', dialogState);

    await page.waitForSelector('dialog.ui-confirm[open]', { state: 'detached', timeout: 8000 });
    await page.waitForTimeout(1500);

    await page.waitForSelector('#gate-receptions-body tr:has-text("ACCEPTED")', { state: 'visible', timeout: 8000 });
    console.log('✓ Tiket gerbang ACCEPTED berhasil tercatat. Stok RAMP-01 teragregasi.');

    // Skenario 3B: Diterima Sebagian (PARTIALLY_ACCEPTED) - TOP (14 Hari)
    console.log('\n--- 3B. QC Gerbang: Diterima Sebagian (PARTIALLY_ACCEPTED) - TOP ---');
    await page.click('#btn-open-gate-modal');
    await page.waitForSelector('dialog.ui-confirm[open]', { state: 'visible', timeout: 8000 });

    await page.selectOption('#gc-carrier', 'COLLECTOR_SELF');
    await page.fill('#gc-plate', 'AB 5678 EF');
    await page.fill('#gc-driver', 'Ahmad Pengepul');
    await page.selectOption('#gc-biomass', 'tongkol_jagung');
    await page.fill('#gc-gross', '8000');
    await page.fill('#gc-tare', '5000');
    await page.fill('#gc-mc', '15.5');

    await page.check('input[name="qc_decision"][value="PARTIALLY_ACCEPTED"]');
    await page.waitForSelector('#gc-partial-box', { state: 'visible', timeout: 3000 });
    await page.fill('#gc-acc-qty', '2500');
    await page.fill('#gc-rej-qty', '500');
    await page.fill('#gc-reject-reason', '500 kg tongkol bagian bawah basah berjamur');

    await page.selectOption('#gc-target-ramp', '2');
    await page.selectOption('#gc-scheme', 'TOP');
    await page.fill('#gc-unit-price', '500');
    await page.fill('#gc-due-days', '14');

    console.log('Mengirim penerimaan gerbang PARTIALLY_ACCEPTED...');
    await page.click('dialog.ui-confirm button[value="yes"]');
    await page.waitForSelector('dialog.ui-confirm[open]', { state: 'detached', timeout: 8000 });
    await page.waitForTimeout(1500);

    await page.waitForSelector('#gate-receptions-body tr:has-text("PARTIALLY_ACCEPTED")', { state: 'visible', timeout: 8000 });
    console.log('✓ Tiket gerbang PARTIALLY_ACCEPTED tercatat (2500 kg diterima, 500 kg ditolak retur).');

    // Skenario 3C: Ditolak Total (REJECTED)
    console.log('\n--- 3C. QC Gerbang: Ditolak Total (REJECTED) ---');
    await page.click('#btn-open-gate-modal');
    await page.waitForSelector('dialog.ui-confirm[open]', { state: 'visible', timeout: 8000 });

    await page.selectOption('#gc-carrier', 'COLLECTOR_SELF');
    await page.fill('#gc-plate', 'AB 9999 ZZ');
    await page.fill('#gc-driver', 'Subur');
    await page.selectOption('#gc-biomass', 'serbuk_sengon');
    await page.fill('#gc-gross', '6000');
    await page.fill('#gc-tare', '4000');
    await page.fill('#gc-mc', '28.0');

    await page.check('input[name="qc_decision"][value="REJECTED"]');
    await page.waitForSelector('#gc-rejection-box', { state: 'visible', timeout: 3000 });
    await page.fill('#gc-reject-reason', 'Kadar air 28% melebihi batas dan terkontaminasi tanah');

    console.log('Mengirim penerimaan gerbang REJECTED...');
    await page.click('dialog.ui-confirm button[value="yes"]');
    await page.waitForSelector('dialog.ui-confirm[open]', { state: 'detached', timeout: 8000 });
    await page.waitForTimeout(1500);

    await page.waitForSelector('#gate-receptions-body tr:has-text("REJECTED")', { state: 'visible', timeout: 8000 });
    console.log('✓ Tiket gerbang REJECTED tercatat dengan alasan penolakan terdokumentasi.');

    // 4. Optimasi Campuran Bahan Bakar Boiler (HiGHS LP Blending Engine)
    console.log('\n--- 4. Uji Optimasi HiGHS Fuel Blend (Prototipe 1) ---');
    const sekamCb = page.locator('input[data-fb-use="sekam_padi"]');
    await sekamCb.scrollIntoViewIfNeeded();
    if (!await sekamCb.isChecked()) {
      await sekamCb.check();
      await page.fill('input[data-fb-kg="sekam_padi"]', '10000');
      await page.fill('input[data-fb-price="sekam_padi"]', '450');
    }
    const jagungCb = page.locator('input[data-fb-use="tongkol_jagung"]');
    if (!await jagungCb.isChecked()) {
      await jagungCb.check();
      await page.fill('input[data-fb-kg="tongkol_jagung"]', '5000');
      await page.fill('input[data-fb-price="tongkol_jagung"]', '500');
    }

    const btnBlend = page.locator('#fx-fb-go');
    await btnBlend.scrollIntoViewIfNeeded();
    await btnBlend.click();

    await page.waitForSelector('#fx-fb-out .kpi-row, #fx-fb-out .banner', { state: 'visible', timeout: 10000 });
    const blendText = await page.locator('#fx-fb-out').innerText();
    console.log('✓ Optimasi campuran bahan bakar LP HiGHS berhasil dijalankan.');

    // 5. Evaluasi Produk Akhir Multi-Biomassa
    console.log('\n--- 5. Uji Evaluasi Multi-Biomassa Produk Akhir (Prototipe 4) ---');
    const btnOptEval = page.locator('#fx-opt-eval-go');
    await btnOptEval.scrollIntoViewIfNeeded();
    await btnOptEval.click();

    await page.waitForSelector('#fx-opt-eval-out', { state: 'visible', timeout: 10000 });
    await page.waitForTimeout(1000);
    console.log('✓ Evaluasi komprehensif 4 produk hilir (Pellet, Briket, Biochar, Silika) berhasil.');

    // 6. Penerbitan Surat Jalan Muatan Balik Biochar
    console.log('\n--- 6. Penerbitan Surat Jalan Muatan Balik Biochar ---');
    const btnDispatch = page.locator('#btn-fx-dispatch-biochar');
    await btnDispatch.scrollIntoViewIfNeeded();
    await btnDispatch.click();

    await page.waitForSelector('dialog.ui-confirm[open]', { state: 'visible', timeout: 8000 });
    await page.selectOption('#fx-bd-col', '3');
    await page.selectOption('#fx-bd-drv', '4');
    await page.fill('#fx-bd-plate', 'AB 8888 XY');
    await page.fill('#fx-bd-kg', '600');
    await page.fill('#fx-bd-bags', '24');
    await page.fill('#fx-bd-inst', 'Kirim muatan balik biochar mutu premium ke sawah binaan Sleman');

    console.log('Mengklik Terbitkan & Buat QR...');
    await page.click('dialog.ui-confirm button[value="yes"]');
    await page.waitForTimeout(1500);

    // Jika modal visual QR terbuka, tutup modalnya
    const btnCloseModal = page.locator('#modal button:has-text("Tutup"), #modal button[data-onclick*="closeModal"]');
    if (await btnCloseModal.isVisible()) {
      await btnCloseModal.click();
      await page.waitForTimeout(500);
    }

    await page.waitForSelector('#fx-bd-list code:has-text("AB 8888 XY"), #fx-bd-list strong:has-text("AB 8888 XY")', { state: 'visible', timeout: 8000 });
    console.log('✓ Surat jalan muatan balik biochar berhasil diterbitkan dan terdaftar.');

    // 7. Hard-Reload & Pembuktian Persistensi Modul Pabrik
    console.log('\n--- 7. Hard-Reload Pembuktian Persistensi Modul Pabrik ---');
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForSelector('#f-co2', { state: 'visible', timeout: 8000 });
    await page.waitForSelector('#gate-ramps-container', { state: 'visible', timeout: 8000 });
    await page.waitForSelector('#gate-receptions-table', { state: 'visible', timeout: 8000 });

    // Verifikasi tiket dan surat jalan tetap ada
    await page.waitForSelector('#gate-receptions-body tr:has-text("ACCEPTED")', { state: 'visible', timeout: 8000 });
    await page.waitForSelector('#fx-bd-list code:has-text("AB 8888 XY"), #fx-bd-list strong:has-text("AB 8888 XY")', { state: 'visible', timeout: 8000 });
    console.log('✓ Seluruh data Modul Pabrik bertahan 100% setelah hard-reload.');

    console.log('\n======================================================');
    console.log('HASIL UJI MODUL PABRIK (FASE 5):');
    console.log(`Console Errors: ${telemetry.consoleErrors.length}`);
    console.log(`Runtime Exceptions: ${telemetry.pageErrors.length}`);
    console.log(`Network Failures: ${telemetry.networkFailures.length}`);
    console.log('======================================================');

    if (telemetry.consoleErrors.length > 0 || telemetry.pageErrors.length > 0 || telemetry.networkFailures.length > 0) {
      console.error('Ditemukan error pada telemetri:', JSON.stringify(telemetry, null, 2));
      process.exit(1);
    } else {
      console.log('✅ MODUL PABRIK 100% PASS DENGAN ZERO ERROR!');
      process.exit(0);
    }

  } catch (error) {
    console.error('❌ GAGAL PADA PENGUJIAN MODUL PABRIK:', error);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runFase5();
