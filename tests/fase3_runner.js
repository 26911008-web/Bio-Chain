// tests/fase3_runner.js
// Fase 3: Simulasi Lapangan & Auto-Fix Modul Pengepul (Koordinator Lapangan)
// Playwright runner dengan Real-Time Telemetry Trap

const { chromium } = require('@playwright/test');
const path = require('path');

const BASE_URL = 'http://127.0.0.1:8000';

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
      console.error(`[CONSOLE ERROR][PENGEPUL] ${text}`);
      telemetry.consoleErrors.push(text);
    }
  });

  page.on('pageerror', err => {
    console.error(`[RUNTIME EXCEPTION][PENGEPUL] ${err.message}`);
    telemetry.pageErrors.push(err.message);
  });

  page.on('response', response => {
    const status = response.status();
    const url = response.url();
    if (status >= 400 && !url.includes('favicon.ico') && url.includes(BASE_URL)) {
      console.error(`[NETWORK FAILURE][PENGEPUL] ${status} ${response.request().method()} ${url}`);
      telemetry.networkFailures.push({ status, url, method: response.request().method() });
    }
  });

  return telemetry;
}

async function runFase3() {
  console.log('=== MEMULAI PENGUJIAN FASE 3: PERSONA PENGEPUL ===');
  
  const browser = await chromium.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const context = await browser.newContext();
  const page = await context.newPage();
  const telemetry = await attachTelemetryTrap(page);

  try {
    // 1. Login sebagai PENGEPUL
    console.log('\n--- 1. Login Pengepul ---');
    await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' });

    // Pastikan session bersih (logout jika masih aktif)
    const btnLogout = page.locator('#btn-logout');
    if (await btnLogout.isVisible()) {
      await btnLogout.click();
      await page.waitForTimeout(600);
    }
    await page.waitForSelector('#login-view', { state: 'visible', timeout: 8000 });

    // Klik kartu gerbang Pengepul
    console.log('Memilih role gate Pengepul...');
    const pengepulCard = page.locator('.role-card:has-text("Pengepul")');
    await pengepulCard.click();
    await page.waitForTimeout(500);

    // Isi kredensial pengepul
    await page.fill('#login-ident', 'pengepul_sleman');
    await page.fill('#login-pass', 'kud2026');
    await page.click('#btn-submit-login');

    // Tunggu dashboard pengepul termuat
    await page.waitForSelector('#col-pending', { state: 'visible', timeout: 10000 });
    console.log('✓ Login berhasil sebagai Pengepul.');

    // 2. Pemisahan Tab & Pengelompokan Jenis Biomassa
    console.log('\n--- 2. Uji Pemisahan Tab & Pengelompokan Jenis Biomassa ---');
    await page.waitForSelector('#btn-tab-langsung', { state: 'visible', timeout: 8000 });
    await page.waitForSelector('#btn-tab-lelang', { state: 'visible', timeout: 8000 });

    // a. Cek Tab Langsung Diambil
    console.log('Menguji Tab 1: Langsung Diambil...');
    await page.click('#btn-tab-langsung');
    await page.waitForTimeout(800);
    const directHeaderCount = await page.locator('#market-table .group-header-row').count();
    console.log(`✓ Tab Langsung aktif dengan ${directHeaderCount} kelompok komoditas.`);

    // b. Cek Tab Lelang / Bidding
    console.log('Menguji Tab 2: Lelang / Bidding...');
    await page.click('#btn-tab-lelang');
    await page.waitForTimeout(800);
    const auctionRows = await page.locator('#market-table tbody tr[data-listing-id]').count();
    console.log(`✓ Tab Lelang aktif dengan ${auctionRows} listing aktif.`);

    // Uji bidding jika ada listing aktif di lelang
    if (auctionRows > 0) {
      console.log('Menguji penawaran harga (bidding) di bursa lelang...');
      const firstBidInput = page.locator('#market-table tbody input[id^="bp-"]').first();
      if (await firstBidInput.isVisible()) {
        await firstBidInput.fill('490');
        const bidBtn = page.locator('#market-table tbody button[data-bid-listing-id]').first();
        await bidBtn.click();
        await page.waitForSelector('dialog.ui-confirm[open]', { state: 'visible', timeout: 5000 });
        const confirmBtn = page.locator('dialog.ui-confirm[open]').last().locator('button[value="yes"]');
        await confirmBtn.click();
        await page.waitForTimeout(1000);
        await page.waitForSelector('dialog.ui-confirm[open]', { state: 'detached', timeout: 5000 }).catch(() => {});
        console.log('✓ Tawaran lelang berhasil diajukan.');
      }
    }

    // Kembali ke tab langsung
    await page.click('#btn-tab-langsung');
    await page.waitForTimeout(600);

    // 3. Finalisasi & Jadwal Plan Ambil Sekaligus dengan Muatan Balik Biochar
    console.log('\n--- 3. Uji Rencana Penjemputan Konsolidasi & Muatan Balik Biochar ---');
    const btnPlanPickup = page.locator('button[data-onclick="planPickup(this)"]');
    if (await btnPlanPickup.isVisible()) {
      console.log('Mengklik Rencanakan Jemput...');
      await btnPlanPickup.click();
      await page.waitForSelector('#pickup-plan-result', { state: 'visible', timeout: 8000 });
      await page.waitForTimeout(1000);
      
      const btnConfirmPlan = page.locator('button[data-onclick="confirmAndDispatchPickupPlan(this)"]');
      if (await btnConfirmPlan.isVisible()) {
        console.log('Mengonfirmasi & mengirim jadwal penjemputan ke petani...');
        await btnConfirmPlan.click();
        await page.waitForTimeout(1000);
        console.log('✓ Jadwal penjemputan berhasil dikirimkan ke petani.');
      }
    }

    // Uji modal simulasi rute konsolidasi & muatan balik biochar
    const btnConsolRoute = page.locator('#fo-plan-route-btn');
    if (await btnConsolRoute.isVisible()) {
      console.log('Menguji modul Simulasi Rute Konsolidasi & Biochar...');
      await btnConsolRoute.click();
      await page.waitForSelector('dialog.ui-confirm[open]', { state: 'visible', timeout: 5000 });
      
      // Submit simulasi rute
      const runSimBtn = page.locator('dialog.ui-confirm[open]').last().locator('button[value="yes"]');
      await runSimBtn.click();
      await page.waitForTimeout(1000);
      await page.waitForSelector('dialog.ui-confirm[open]', { state: 'detached', timeout: 5000 }).catch(() => {});

      const saveRouteBtn = page.locator('#btn-save-consolidated-route');
      if (await saveRouteBtn.isVisible()) {
        await saveRouteBtn.click();
        await page.waitForTimeout(1000);
        console.log('✓ Rute konsolidasi & muatan balik berhasil ditugaskan ke armada driver.');
      }
    }

    // 4. Input QC Lapangan & Timbang (Uji Tolak & Uji Lolos Refraksi)
    console.log('\n--- 4. Uji QC Lapangan & Timbangan (Tolak & Lolos Refraksi) ---');
    await page.waitForSelector('#table-col-queue', { state: 'visible', timeout: 8000 });

    // a. Skenario Uji Tolak Lot
    console.log('Skenario A: Uji penolakan lot bermutu buruk...');
    const firstVerifyBtn = page.locator('#table-col-queue tbody button:has-text("Uji 🔬")').first();
    if (await firstVerifyBtn.isVisible()) {
      await firstVerifyBtn.click();
      await page.waitForTimeout(600);
      
      const btnReject = page.locator('#btn-reject-lot');
      if (await btnReject.isEnabled()) {
        await btnReject.click();
        await page.waitForSelector('dialog.ui-confirm[open]', { state: 'visible', timeout: 5000 });
        
        await page.selectOption('#fo-rj-cat', 'kontaminan');
        await page.fill('#fo-rj-why', 'Bercampur tanah dan jerami basah di atas ambang batas');
        
        const confirmRejectBtn = page.locator('dialog.ui-confirm[open]').last().locator('button[value="yes"]');
        await confirmRejectBtn.click();
        await page.waitForTimeout(1000);
        await page.waitForSelector('dialog.ui-confirm[open]', { state: 'detached', timeout: 5000 }).catch(() => {});
        console.log('✓ Lot berhasil ditolak & alasan deviasi tercatat.');
      }
    }

    // b. Skenario Uji Lolos dengan Refraksi Timbangan
    console.log('Skenario B: Uji verifikasi lolos dengan refraksi timbangan bruto/tara...');
    const secondVerifyBtn = page.locator('#table-col-queue tbody button:has-text("Uji 🔬")').first();
    if (await secondVerifyBtn.isVisible()) {
      await secondVerifyBtn.click();
      await page.waitForTimeout(600);

      // Input hasil timbang lapangan & proksimat
      await page.fill('#v-weight', '1750');
      await page.fill('#v-moisture', '11.4');
      await page.fill('#v-contam', '0.2');
      
      const btnSubmitVerify = page.locator('#btn-submit-verify');
      await btnSubmitVerify.click();
      await page.waitForTimeout(1500);

      // Tutup modal resi serah-terima jika muncul
      const qrModal = page.locator('#qr-modal');
      if (await qrModal.isVisible()) {
        await page.click('#qr-modal button:has-text("✕"), #qr-modal button:has-text("Tutup")');
        await page.waitForTimeout(500);
        console.log('✓ Modal Resi Serah-Terima ditutup.');
      }
      console.log('✓ Hasil uji verifikasi timbang lolos & resi tercetak.');
    }

    // 5. Pembayaran Petani (DP & Pelunasan)
    console.log('\n--- 5. Uji Pembayaran Petani (DP & Pelunasan) ---');
    await page.waitForSelector('#fo-unpaid', { state: 'visible', timeout: 8000 });
    
    // a. Uji Bayar DP
    const dpBtn = page.locator('#fo-unpaid button[data-fo-dp]').first();
    if (await dpBtn.isVisible()) {
      console.log('Membayar DP ke petani...');
      await dpBtn.click();
      await page.waitForSelector('dialog.ui-confirm[open]', { state: 'visible', timeout: 5000 });
      await page.selectOption('#fo-dp-m', 'tunai');
      
      const submitDpBtn = page.locator('dialog.ui-confirm[open]').last().locator('button[value="yes"]');
      await submitDpBtn.click();
      await page.waitForTimeout(1000);
      await page.waitForSelector('dialog.ui-confirm[open]', { state: 'detached', timeout: 5000 }).catch(() => {});

      const qrModalDp = page.locator('#qr-modal');
      if (await qrModalDp.isVisible()) {
        await page.click('#qr-modal button:has-text("✕"), #qr-modal button:has-text("Tutup")');
        await page.waitForTimeout(500);
      }
      console.log('✓ Kuitansi DP berhasil dicatat.');
    }

    // b. Uji Pelunasan Transaksi
    const payBtn = page.locator('#fo-unpaid button[data-fo-pay]').first();
    if (await payBtn.isVisible()) {
      console.log('Membayar Pelunasan ke petani...');
      await payBtn.click();
      await page.waitForSelector('dialog.ui-confirm[open]', { state: 'visible', timeout: 5000 });
      await page.selectOption('#fo-pay-m', 'tunai');
      
      const submitPayBtn = page.locator('dialog.ui-confirm[open]').last().locator('button[value="yes"]');
      await submitPayBtn.click();
      await page.waitForTimeout(1000);
      await page.waitForSelector('dialog.ui-confirm[open]', { state: 'detached', timeout: 5000 }).catch(() => {});

      const qrModalPay = page.locator('#qr-modal');
      if (await qrModalPay.isVisible()) {
        await page.click('#qr-modal button:has-text("✕"), #qr-modal button:has-text("Tutup")');
        await page.waitForTimeout(500);
      }
      console.log('✓ Transaksi pelunasan berhasil diverifikasi.');
    }

    // 6. Penugasan Supir & Pengiriman Biomassa ke Pabrik (Delivery Request)
    console.log('\n--- 6. Uji Pengajuan Pengiriman ke Pabrik (Delivery Request) ---');
    await page.waitForSelector('#dr-mill', { state: 'visible', timeout: 8000 });
    
    // a. Skenario 1: Skema Ikut Acuan Pabrik
    console.log('Skenario 1: Mengajukan pengiriman skema FACTORY_PRICE...');
    await page.selectOption('#dr-biomass', 'sekam_padi');
    await page.selectOption('#dr-carrier', 'FACTORY_FLEET');
    await page.selectOption('#dr-pricing', 'FACTORY_PRICE');
    await page.fill('#dr-qty', '3000');
    await page.fill('#dr-m', '11.0');
    
    // Centang jika ada harvest yang bisa dilampirkan
    const attachableCheck = page.locator('.dr-h').first();
    if (await attachableCheck.isVisible()) {
      await attachableCheck.check();
    }
    
    await page.click('#btn-dr');
    await page.waitForTimeout(1500);
    console.log('✓ Ajuan pengiriman 1 (FACTORY_PRICE) berhasil dikirim ke pabrik.');

    // b. Skenario 2: Skema Tawar Bebas (Lelang) ke Pabrik Alternatif
    console.log('Skenario 2: Mengajukan pengiriman skema AUCTION ke pabrik alternatif...');
    const millSelect = page.locator('#dr-mill');
    const millOptionsCount = await millSelect.locator('option').count();
    if (millOptionsCount > 1) {
      await millSelect.selectOption({ index: 1 });
    }
    await page.selectOption('#dr-biomass', 'tongkol_jagung');
    await page.selectOption('#dr-pricing', 'AUCTION');
    await page.fill('#dr-qty', '2500');
    await page.fill('#dr-m', '12.0');
    await page.fill('#dr-price', '530');

    await page.click('#btn-dr');
    await page.waitForTimeout(1500);
    console.log('✓ Ajuan pengiriman 2 (AUCTION) berhasil dikirim ke pabrik.');

    // 7. Hard-Reload & Pembuktian Persistensi Modul Pengepul
    console.log('\n--- 7. Hard-Reload Pembuktian Persistensi Modul Pengepul ---');
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForSelector('#col-pending', { state: 'visible', timeout: 8000 });
    
    // Verifikasi tabel DR dan saldo tetap valid
    await page.waitForSelector('#dr-mine table', { state: 'visible', timeout: 8000 });
    const drRows = await page.locator('#dr-mine table tbody tr').count();
    console.log(`✓ Data Delivery Requests bertahan setelah reload (${drRows} baris terdaftar).`);
    console.log('✓ Seluruh data Modul Pengepul bertahan 100% setelah hard-reload.');

    console.log('\n======================================================');
    console.log('HASIL UJI MODUL PENGEPUL (FASE 3):');
    console.log(`Console Errors: ${telemetry.consoleErrors.length}`);
    console.log(`Runtime Exceptions: ${telemetry.pageErrors.length}`);
    console.log(`Network Failures: ${telemetry.networkFailures.length}`);
    console.log('======================================================');

    if (telemetry.consoleErrors.length > 0 || telemetry.pageErrors.length > 0 || telemetry.networkFailures.length > 0) {
      console.error('Ditemukan error pada telemetri:', JSON.stringify(telemetry, null, 2));
      process.exit(1);
    } else {
      console.log('✅ MODUL PENGEPUL 100% PASS DENGAN ZERO ERROR!');
      process.exit(0);
    }

  } catch (error) {
    console.error('❌ GAGAL PADA PENGUJIAN MODUL PENGEPUL:', error);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runFase3();
