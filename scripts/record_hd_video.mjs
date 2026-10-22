/**
 * ==============================================================================
 * BIO-CHAIN v2 — HD VIDEO GENERATOR (VERSI 3 MENIT PRESISI)
 * Full HD 1080p (1920x1080) Broadcast-Quality Application Recording
 * Durasi Target: Tepat ~3 Menit (180 Detik)
 * Features:
 *   - Glassmorphic Presenter Subtitle HUD with Live Standard Badges
 *   - Smooth Animated Virtual Mouse Cursor & Click Ripple FX
 *   - Complete End-to-End Circular Lifecycle Across All Personas
 *   - Highlights: ISO 17225, EBC/IBI, ISO 22095, ISO 27001, HiGHS Solver,
 *     Clarke-Wright vs OR-Tools, 14-Day Payment Guarantee, Closed-Loop Biochar
 * ==============================================================================
 */

import { chromium } from '@playwright/test';
import path from 'path';
import fs from 'fs';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8000';
const RAW_DIR = path.resolve(__dirname, '../videos/raw');
const FINAL_OUTPUT_3MIN = path.resolve(__dirname, '../videos/video_aplikasi_biochain_hd_3menit.mp4');
const FINAL_OUTPUT_DEFAULT = path.resolve(__dirname, '../videos/video_aplikasi_biochain_hd.mp4');

if (!fs.existsSync(RAW_DIR)) {
  fs.mkdirSync(RAW_DIR, { recursive: true });
}

// Clean old files in RAW_DIR
for (const f of fs.readdirSync(RAW_DIR)) {
  try { fs.unlinkSync(path.join(RAW_DIR, f)); } catch {}
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function main() {
  console.log('🎬 Memulai Perekaman Video HD Bio-Chain v2 (Versi 3 Menit)...');
  console.log(`🌐 Base URL: ${BASE_URL}`);

  const browser = await chromium.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--force-device-scale-factor=1',
      '--window-size=1920,1080',
    ],
  });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: {
      dir: RAW_DIR,
      size: { width: 1920, height: 1080 },
    },
  });

  const page = await context.newPage();

  // Helper untuk menyuntikkan Virtual Cursor dan HUD Subtitle
  await page.addInitScript(() => {
    window.__initVideoOverlay = () => {
      if (document.getElementById('biochain-hud-root')) return;

      const style = document.createElement('style');
      style.id = 'biochain-video-styles';
      style.innerHTML = `
        /* Virtual Pointer */
        #virtual-cursor {
          position: fixed;
          top: 0; left: 0;
          width: 26px; height: 26px;
          background: rgba(16, 185, 129, 0.95);
          border: 2.5px solid #ffffff;
          box-shadow: 0 0 16px rgba(16, 185, 129, 1), 0 0 35px rgba(16, 185, 129, 0.7);
          border-radius: 50%;
          pointer-events: none;
          z-index: 2147483647;
          transform: translate(-100px, -100px);
          transition: transform 0.35s cubic-bezier(0.22, 1, 0.36, 1), background-color 0.15s ease;
        }
        #virtual-cursor.clicking {
          transform: translate(var(--cx), var(--cy)) scale(0.65) !important;
          background-color: #f43f5e !important;
          box-shadow: 0 0 25px rgba(244, 63, 94, 1), 0 0 45px rgba(244, 63, 94, 0.8) !important;
        }
        .click-ripple {
          position: fixed;
          width: 36px; height: 36px;
          border-radius: 50%;
          border: 3px solid rgba(16, 185, 129, 0.95);
          pointer-events: none;
          z-index: 2147483646;
          transform: translate(-50%, -50%) scale(0.2);
          animation: click-ripple-anim 0.55s cubic-bezier(0.1, 0.8, 0.3, 1) forwards;
        }
        @keyframes click-ripple-anim {
          0% { transform: translate(-50%, -50%) scale(0.2); opacity: 1; }
          100% { transform: translate(-50%, -50%) scale(2.8); opacity: 0; }
        }

        /* Glassmorphic Presenter Subtitle HUD */
        #biochain-hud-root {
          position: fixed;
          bottom: 24px;
          left: 50%;
          transform: translateX(-50%);
          width: 92%;
          max-width: 1360px;
          background: rgba(10, 15, 29, 0.94);
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
          border: 1.5px solid rgba(16, 185, 129, 0.45);
          box-shadow: 0 20px 50px rgba(0, 0, 0, 0.85), 0 0 35px rgba(16, 185, 129, 0.25);
          border-radius: 18px;
          padding: 16px 28px;
          z-index: 2147483640;
          color: #ffffff;
          font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
          pointer-events: none;
          transition: all 0.3s ease;
        }
        .hud-top-bar {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 6px;
        }
        .hud-tag {
          font-size: 13px;
          font-weight: 800;
          letter-spacing: 1.5px;
          text-transform: uppercase;
          color: #34d399;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .hud-badges {
          display: flex;
          gap: 8px;
        }
        .hud-badge {
          font-size: 11px;
          font-weight: 700;
          padding: 3px 12px;
          border-radius: 999px;
          background: rgba(52, 211, 153, 0.15);
          border: 1px solid rgba(52, 211, 153, 0.4);
          color: #6ee7b7;
          letter-spacing: 0.5px;
        }
        .hud-title {
          font-size: 20px;
          font-weight: 800;
          color: #f8fafc;
          margin-bottom: 4px;
          letter-spacing: -0.3px;
          line-height: 1.25;
        }
        .hud-desc {
          font-size: 14.5px;
          font-weight: 400;
          color: #cbd5e1;
          line-height: 1.45;
        }
        .hud-desc b, .hud-desc strong {
          color: #6ee7b7;
          font-weight: 600;
        }
      `;
      document.head.appendChild(style);

      const hud = document.createElement('div');
      hud.id = 'biochain-hud-root';
      hud.innerHTML = `
        <div class="hud-top-bar">
          <div class="hud-tag" id="hud-tag">🌿 BIO-CHAIN v2 · EKOSISTEM SIRKULAR</div>
          <div class="hud-badges" id="hud-badges"></div>
        </div>
        <div class="hud-title" id="hud-title">Platform Rantai Pasok Multi-Biomassa Terpadu</div>
        <div class="hud-desc" id="hud-desc">Menghubungkan Petani, Pengepul, dan Pabrik dalam satu siklus tertutup sirkular berkelanjutan.</div>
      `;
      document.body.appendChild(hud);

      const cursor = document.createElement('div');
      cursor.id = 'virtual-cursor';
      document.body.appendChild(cursor);
    };

    window.__setHud = (tag, title, desc, badges = []) => {
      window.__initVideoOverlay();
      const elTag = document.getElementById('hud-tag');
      const elTitle = document.getElementById('hud-title');
      const elDesc = document.getElementById('hud-desc');
      const elBadges = document.getElementById('hud-badges');
      if (elTag) elTag.innerHTML = tag;
      if (elTitle) elTitle.innerText = title;
      if (elDesc) elDesc.innerHTML = desc;
      if (elBadges) {
        elBadges.innerHTML = badges.map(b => `<span class="hud-badge">${b}</span>`).join('');
      }
    };

    window.__moveCursor = async (target, offsetY = 0) => {
      window.__initVideoOverlay();
      let targetX = 960, targetY = 540;
      if (typeof target === 'string') {
        const el = document.querySelector(target);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          await new Promise(r => setTimeout(r, 300));
          const rect = el.getBoundingClientRect();
          targetX = rect.left + rect.width / 2;
          targetY = rect.top + rect.height / 2 + offsetY;
        }
      } else if (Array.isArray(target)) {
        [targetX, targetY] = target;
      }
      const cursor = document.getElementById('virtual-cursor');
      if (cursor) {
        cursor.style.setProperty('--cx', targetX + 'px');
        cursor.style.setProperty('--cy', targetY + 'px');
        cursor.style.transform = `translate(${targetX - 13}px, ${targetY - 13}px)`;
      }
      await new Promise(r => setTimeout(r, 250));
    };

    window.__animateRipple = async (target, offsetY = 0) => {
      const cursor = document.getElementById('virtual-cursor');
      if (cursor) cursor.classList.add('clicking');

      let x = 960, y = 540;
      if (typeof target === 'string') {
        const el = document.querySelector(target);
        if (el) {
          const rect = el.getBoundingClientRect();
          x = rect.left + rect.width / 2;
          y = rect.top + rect.height / 2 + offsetY;
        }
      } else if (Array.isArray(target)) {
        [x, y] = target;
      }

      const ripple = document.createElement('div');
      ripple.className = 'click-ripple';
      ripple.style.left = x + 'px';
      ripple.style.top = y + 'px';
      document.body.appendChild(ripple);
      setTimeout(() => ripple.remove(), 600);

      await new Promise(r => setTimeout(r, 160));
      if (cursor) cursor.classList.remove('clicking');
      await new Promise(r => setTimeout(r, 120));
    };
  });

  // Action Helpers yang menggabungkan Virtual Pointer + Playwright Click/Type
  async function userClick(selector, textFilter = null) {
    if (textFilter) {
      const loc = page.locator(selector, { hasText: textFilter });
      await loc.scrollIntoViewIfNeeded();
      const box = await loc.boundingBox();
      if (box) {
        await page.evaluate(([x, y]) => window.__moveCursor([x, y]), [box.x + box.width / 2, box.y + box.height / 2]);
        await page.evaluate(([x, y]) => window.__animateRipple([x, y]), [box.x + box.width / 2, box.y + box.height / 2]);
      }
      await loc.click();
    } else {
      await page.evaluate((sel) => window.__moveCursor(sel), selector);
      await page.evaluate((sel) => window.__animateRipple(sel), selector);
      await page.click(selector);
    }
    await sleep(300);
  }

  async function userType(selector, text) {
    await page.evaluate((sel) => window.__moveCursor(sel), selector);
    await page.evaluate((sel) => window.__animateRipple(sel), selector);
    await page.fill(selector, text);
    await sleep(250);
  }

  async function userSelect(selector, value) {
    await page.evaluate((sel) => window.__moveCursor(sel), selector);
    await page.evaluate((sel) => window.__animateRipple(sel), selector);
    await page.selectOption(selector, value);
    await sleep(350);
  }

  async function setHud(tag, title, desc, badges = []) {
    await page.evaluate(([tag, title, desc, badges]) => {
      window.__setHud(tag, title, desc, badges);
    }, [tag, title, desc, badges]);
  }

  async function loginAs(roleText, username, password) {
    console.log(`🔑 Login sebagai: ${roleText} (${username})...`);
    await page.waitForSelector('#login-view', { state: 'visible', timeout: 10000 });
    await page.waitForFunction(() => window.STATE && window.STATE.demoAccounts && window.STATE.demoAccounts.length > 0);
    await sleep(300);

    await userClick('.role-card', roleText);
    await sleep(300);
    await page.fill('#login-ident', username);
    await page.fill('#login-pass', password);
    await sleep(200);
    await userClick('#btn-submit-login');
    await page.waitForSelector('#app-view', { state: 'visible', timeout: 15000 });
    await sleep(1000);
  }

  async function logout() {
    console.log(`🚪 Melakukan logout...`);
    await page.evaluate(() => {
      document.querySelectorAll('.modal-overlay').forEach(m => {
        m.classList.remove('open');
        m.removeAttribute('data-ui-open');
        m.style.display = 'none';
      });
    });
    await sleep(300);
    await page.click('#btn-logout');
    await page.waitForSelector('#login-view', { state: 'visible', timeout: 10000 });
    await page.waitForFunction(() => window.STATE && window.STATE.demoAccounts && window.STATE.demoAccounts.length > 0);
    await sleep(500);
  }

  // =========================================================================
  // SCENE 1: INTRO & LOGIN SCREEN — ARSITEKTUR MULTI-PERSONA (0:00 - 0:15)
  // =========================================================================
  console.log('📍 [Scene 1] Intro & Login Screen');
  await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => window.STATE && window.STATE.demoAccounts && window.STATE.demoAccounts.length > 0);

  await setHud(
    '🌿 BIO-CHAIN v2 · EKOSISTEM SIRKULAR TERPADU',
    'Digitalisasi Rantai Pasok Biomassa Hulu-Hilir & Sirkular Bio-Ekonomi',
    'Platform cerdas yang menghubungkan <b>Petani, Pengepul, dan Pabrik</b> dalam satu kesatuan sirkular tertutup. Dilindungi tata kelola data berstandar <b>ISO 27001</b> dan sistem ketertelusuran material berbasis <b>ISO 22095</b>.',
    ['ISO 27001', 'ISO 22095', 'ANGEL Hackathon 2026', 'Zero Waste']
  );
  await sleep(1800);

  // Gerakkan mouse ke Hero Brand & Indikator Database
  await page.evaluate(() => window.__moveCursor('.login-brand h1'));
  await sleep(1000);

  await page.evaluate(() => window.__moveCursor('#db-indicator'));
  await sleep(1000);

  // Tunjukkan 4 Gerbang Peran Utama (Petani, Pengepul, Driver, Pabrik)
  await userClick('.role-card', 'Petani');
  await sleep(500);
  await userClick('.role-card', 'Pengepul');
  await sleep(500);
  await userClick('.role-card', 'Pabrik');
  await sleep(800);

  // =========================================================================
  // SCENE 2: PERSONA PETANI — LAPOR PANEN, JUAL LANGSUNG vs LELANG, LOGISTIK (0:15 - 0:45)
  // =========================================================================
  console.log('📍 [Scene 2] Persona Petani: Jual Langsung vs Lelang & Skema Logistik');
  await setHud(
    '🌾 PERSONA 1 · PETANI & PENGGILINGAN PADI',
    'Fleksibilitas Transaksi: Jual Langsung vs Lelang & Opsi Antar / Jemput',
    'Petani memiliki kebebasan memilih transaksi: <b>Jual Langsung</b> (harga acuan otomatis) atau <b>Lelang</b> (bidding terbuka), serta opsi <b>Dijemput Pengepul</b> atau <b>Diantar Mandiri (+Premi Rp 80/kg)</b>.',
    ['Jual Langsung', 'Lelang Terbuka', 'Premi Antar Mandiri', 'QR Code Lot']
  );

  // Login Petani
  await loginAs('Petani', 'petani_sugeng', 'sekam123');

  // Dashboard Petani: Highlight KPI Tiles & Dompet Biochar
  await setHud(
    '🌾 DASHBOARD PETANI · KELAYAKAN & DOMPET BIOCHAR',
    'Transparansi Tonase, XP Gamifikasi, dan Saldo Muatan Balik Biochar',
    'Menampilkan ringkasan total laporan panen, tonase terkirim, serta saldo <b>Dompet Biochar</b> aktif yang siap diambil untuk menyuburkan lahan sawah.',
    ['Dompet Biochar', 'Gamifikasi Mitra', 'Ketertelusuran Lot']
  );
  await page.evaluate(() => window.__moveCursor('#p-wallet'));
  await sleep(1600);

  // Scroll ke Form Lapor & Jual Biomassa
  await page.evaluate(() => window.__moveCursor('#form-lapor-sekam'));
  await sleep(1000);

  // Pilih Komoditas Sekam Padi
  await userSelect('#f-commodity', 'sekam_padi');
  await sleep(600);

  // Sorot Harga Acuan Referensi Pasar
  await page.evaluate(() => window.__moveCursor('#f-rec-box'));
  await sleep(1200);

  // Masukkan Kuantitas 2.500 kg
  await userType('#f-qty', '2500');
  await sleep(800);

  // Tunjukkan Opsi Cara Jual: Toggle Lelang vs Jual Langsung
  await setHud(
    '🏷️ DUAL TRANSACTION MODE · MODEL TRANSAKSI FLEKSIBEL',
    'Pilihan Skema Penjualan: Jual Langsung vs Lelang Kompetitif',
    'Mode <b>Jual Langsung</b> mengunci harga sesuai acuan biomassa tanpa perlu menunggu penawaran. Mode <b>Lelang</b> mengizinkan petani menetapkan harga dasar minimum bagi para pengepul.',
    ['Harga Acuan Pasar', 'Lelang Terbuka', 'Fair Compensation']
  );
  await userClick('input[name="f-mode"][value="lelang"]');
  await sleep(1200);

  // Beralih kembali ke Jual Langsung
  await userClick('input[name="f-mode"][value="langsung"]');
  await sleep(1000);

  // Tunjukkan Skema Penyerahan: Diantar (+Premi Rp 80/kg) vs Dijemput Pengepul
  await setHud(
    '🚚 FLEKSIBILITAS LOGISTIK · OPSI DIANTAR ATAU DIJEMPUT',
    'Efisiensi Logistik Hulu: Premi Antar Mandiri vs Penjemputan Armada',
    'Petani dapat mengantar langsung ke gudang pengepul untuk meraih <b>premi transportasi mandiri (+Rp 80/kg)</b>, atau meminta <b>dijemput oleh armada pengepul</b>.',
    ['Premi Antar Mandiri', 'Dijemput Armada', 'Optimalisasi Logistik']
  );
  await userClick('#f-deliv-antar');
  await sleep(1200);
  await userClick('#f-deliv-jemput');
  await sleep(1000);

  // Buka Pesan Muatan Balik Biochar Sirkular
  await setHud(
    '🌱 INTEGRASI SIRKULAR · PESAN MUATAN BALIK BIOCHAR KE SAWAH',
    'Logistik Zero Empty Trips: Armada Membawa Biochar Balik ke Sawah',
    'Petani memesan muatan balik <b>500 kg biochar</b> untuk diaplikasikan ke lahan sawah 1.2 ha. Armada pengangkut membawanya bersamaan sehingga menghemat biaya distribusi.',
    ['Closed-Loop Farming', 'Zero Empty Trips', 'Soil Conditioner']
  );
  await userClick('#f-biochar-box summary');
  await sleep(600);
  await userType('#f-biochar-req', '500');
  await userType('#f-biochar-ha', '1.2');
  await sleep(1200);

  // Submit Lapor Panen
  await userClick('button[type="submit"]#btn-submit-harvest, #form-lapor-sekam button[type="submit"]');
  
  // Tunggu sejenak hingga modal QR muncul
  await page.waitForSelector('#qr-modal.open', { timeout: 8000 }).catch(() => {});
  await sleep(800);

  // Sorot Modal QR Ketertelusuran (ISO 22095) yang muncul
  await setHud(
    '📱 BUKTI SETOR DIGITAL · KETERTELUSURAN MATERIAL ISO 22095',
    'Tiket Digital Lot Panen & Kode QR Rantai Pasok Terverifikasi',
    'Tiket setor dan kode QR 2D diterbitkan seketika mengacu pada <b>ISO 22095 (Chain of Custody)</b> untuk dipindai oleh sopir armada pengangkut di titik jemput, menjamin integritas ketertelusuran.',
    ['ISO 22095 Chain of Custody', 'QR Code 2D', 'Verifikasi Titik Jemput', 'Anti Pemalsuan']
  );
  await page.evaluate(() => window.__moveCursor('#qr-modal .qr-frame'));
  await sleep(2200);

  // Tutup Modal QR secara tuntas
  await page.evaluate(() => {
    document.querySelectorAll('.modal-overlay').forEach(m => {
      m.classList.remove('open');
      m.removeAttribute('data-ui-open');
      m.style.display = 'none';
    });
  });
  await sleep(800);

  // =========================================================================
  // SCENE 3: PERSONA PENGEPUL (AGREGATOR & VERIFIKASI LAPANGAN) (0:45 - 1:05)
  // =========================================================================
  console.log('📍 [Scene 3] Persona Pengepul: Dashboard Terkelompok & Verifikasi Lapangan 15 Menit');
  await setHud(
    '🚚 PERSONA 2 · PENGEPUL (AGREGATOR LOGISTIK & VERIFIKASI CEPAT)',
    'Dashboard Penawaran Terkelompok & Verifikasi Mutu Lapangan 15 Menit',
    'Pengepul bertindak sebagai agregator yang menerima pasokan melalui dashboard terkelompok (Lelang vs Langsung Diambil). Melakukan uji cepat lapangan 15 menit untuk penimbangan aktual, deteksi susut, dan penerbitan DP.',
    ['Agregator Logistik', 'Lelang vs Langsung', 'Uji Cepat Lapangan', 'Kompensasi Proporsional']
  );

  // Logout dari Petani & Login sebagai Pengepul
  await logout();
  await loginAs('Pengepul', 'pengepul_sleman', 'kud2026');

  // Tunjukkan Dashboard Offers Pengepul
  await page.evaluate(() => window.__moveCursor('#persona-content'));
  await sleep(2200);

  // =========================================================================
  // SCENE 4: PERSONA PABRIK & PROTOKOL UJI MUTU DUA TAHAP (ISO 17225 & EBC/IBI) (1:05 - 1:30)
  // =========================================================================
  console.log('📍 [Scene 4] Persona Pabrik: Protokol Uji Mutu Dua Tahap & Grade Otomatis');
  await setHud(
    '🏭 PERSONA 3 · PABRIK BIOMASSA · PROTOKOL UJI MUTU DUA TAHAP',
    'Uji Cepat 15 Menit Lapangan & Uji Lab Proksimat Bulanan Otomatisasi Grade',
    'Sistem menjamin standar bahan baku melalui <b>protokol uji mutu dua tahap</b>: uji cepat 15 menit di lapangan dan uji laboratorium proksimat bulanan, yang secara otomatis menentukan <b>grade biomassa (ISO 17225 dan EBC/IBI)</b> serta skema harga insentifnya.',
    ['ISO 17225 Standar Pelet', 'EBC / IBI Biochar', 'Uji Cepat 15 Menit', 'Insentif Mutu Prima']
  );

  // Logout dari Pengepul & Login sebagai Pabrik
  await logout();
  await loginAs('Pabrik', 'pabrik_indmira', 'pabrik2026');

  // Buka Lab Engine Workbench -> Skor Mutu
  await userClick('button[data-tab="tab-engines"]');
  await sleep(1000);
  await userClick('button[data-onclick="switchEngineSub(\'eng-quality\')"]');
  await sleep(1000);

  // Masukkan parameter Uji Mutu Proksimat
  await userType('#q-moisture', '11.0');
  await userType('#q-contam', '1.2');
  await userType('#q-ash', '16.5');
  await userType('#q-vm', '66.0');
  await userType('#q-fc', '16.5');

  // Eksekusi Hitung Skor & Rendemen
  await userClick('#btn-run-quality');
  await sleep(2000);

  // Sorot Hasil Grade dan Insentif Harga
  await page.evaluate(() => window.__moveCursor('#q-result-box'));
  await sleep(2200);

  // =========================================================================
  // SCENE 5: OPTIMASI RUTE VRP (CLARKE-WRIGHT vs GOOGLE OR-TOOLS) (1:30 - 1:55)
  // =========================================================================
  console.log('📍 [Scene 5] Vehicle Routing Problem (VRP) Berbasis Volume: Clarke-Wright vs OR-Tools');
  await setHud(
    '🚚 EFISIENSI OPERASIONAL · VEHICLE ROUTING PROBLEM (VRP)',
    'Optimasi Rute Angkut Berbasis Volume: Clarke-Wright di-benchmark terhadap Google OR-Tools',
    'Bio-Chain mengoptimalkan rute angkut berbasis volume melalui <b>Vehicle Routing Problem (VRP) dengan algoritma Clarke-Wright yang di-benchmark terhadap Google OR-Tools</b>, memangkas biaya BBM solar hingga 32% dan menjamin kompensasi proporsional bagi pengepul.',
    ['Clarke-Wright Savings', 'Google OR-Tools', 'VRP Volume m³', 'Efisiensi BBM 32%']
  );

  // Buka Sub-Engine Rute Optimal (VRP)
  await userClick('button[data-onclick="switchEngineSub(\'eng-route\')"]');
  await sleep(1200);

  // Set Parameter Volume Bak Truk & Densitas Curah
  await userType('#r-m3', '30');
  await userType('#r-dens', '110');
  await userType('#r-cost', '4000');

  // Klik Hitung Rute Optimal
  await userClick('#btn-run-route');
  await sleep(2200);

  // Sorot Peta Leaflet & Efisiensi Rute Sleman-Klaten
  await page.evaluate(() => window.__moveCursor('#map'));
  await sleep(2000);
  await page.evaluate(() => window.__moveCursor('#r-kpis'));
  await sleep(1800);

  // =========================================================================
  // SCENE 6: PEMROGRAMAN LINEAR (SOLVER HiGHS) & DIVERSIFIKASI 4 PRODUK HILIR (1:55 - 2:20)
  // =========================================================================
  console.log('📍 [Scene 6] Pemrograman Linear (Solver HiGHS) & 4 Produk Hilir');
  await setHud(
    '⚙️ PEMROGRAMAN LINEAR (SOLVER HiGHS) · LEAST-COST FEED FORMULATION',
    'Solver HiGHS Merumuskan Komposisi Bahan Baku Termurah & Multi-Produk',
    'Bio-Chain mengintegrasikan <b>pemrograman linear (solver HiGHS)</b> untuk merumuskan komposisi bahan baku termurah yang memenuhi spesifikasi pembakaran boiler dan pirolisis, memaksimalkan efisiensi biaya pabrik.',
    ['Solver HiGHS (LP)', 'Least-Cost Blending', 'ISO 22095 Chain of Custody', 'Multi-Feedstock']
  );

  // Buka Sub-Engine Blending HiGHS
  await userClick('button[data-onclick="switchEngineSub(\'eng-blend\')"]');
  await sleep(1200);

  // Set Target Ton 50 ton & Eksekusi Solver HiGHS
  await userType('#b-target', '50');
  await userClick('#btn-run-blend');
  await sleep(2000);

  // Sorot Hasil Blending HiGHS
  await page.evaluate(() => window.__moveCursor('#b-result-box'));
  await sleep(1800);

  // Pindah ke Engine ⑫: Optimasi Multi-Produk
  await setHud(
    '🎯 ENGINE ⑫ · OPTIMASI KONVERSI 4 PRODUK HILIR BERNILAI TINGGI',
    'Evaluasi Komprehensif Produk Hilir Sesuai Standar Mutu Internasional',
    'Memetakan konversi biomassa ke <b>Bio-Pellet (ISO 17225)</b>, <b>Briket (SNI 01-6235)</b>, <b>Biochar (EBC/IBI)</b>, dan <b>Bio-Silika Amorf (SNI 15-0086)</b> dengan margin keuntungan maksimal.',
    ['ISO 17225', 'SNI 01-6235', 'EBC / IBI', 'SNI 15-0086 Silika']
  );
  await userClick('button[data-onclick="switchEngineSub(\'eng-opt\')"]');
  await sleep(1200);
  await userClick('#lab-opt-eval-go');
  await sleep(2200);
  await page.evaluate(() => window.__moveCursor('#lab-opt-eval-out'));
  await sleep(1800);

  // =========================================================================
  // SCENE 7: ANALISA ESG REAL-TIME & DEKARBONISASI INDUSTRI (2:20 - 2:38)
  // =========================================================================
  console.log('📍 [Scene 7] Analisa ESG: Scope 1, 2, 3 & Carbon Credit Verification');
  await setHud(
    '🌱 ANALISA ESG REAL-TIME · AKUNTANSI KARBON SKOP 1, 2, & 3',
    'Verifikasi Dekarbonisasi Industri & Penghasil Kredit Karbon Berkualitas',
    'Menghitung emisi avoided dan permanensi net carbon sink (tCO₂e) dari konversi biochar. Dilengkapi kepatuhan audit-ready untuk klaim sertifikat karbon (Puro.earth / IDXCarbon).',
    ['Scope 1, 2, 3', 'Net Carbon Sink tCO₂e', 'Puro.earth Standard', 'Audit-Ready ESG']
  );

  // Buka Tab Laporan Bulanan & ESG
  await userClick('button[data-tab="tab-reports"]');
  await sleep(1200);
  await userClick('#btn-rp');
  await sleep(2000);

  // Sorot Grafik Laporan dan Umpan Balik Mutu QC
  await page.evaluate(() => window.__moveCursor('#rp-chart'));
  await sleep(1600);
  await page.evaluate(() => window.__moveCursor('#rp-kpis'));
  await sleep(1800);

  // =========================================================================
  // SCENE 8: INTEGRASI SIRKULAR SISA ABU & KEPASTIAN BAYAR 14 HARI (ISO 27001) (2:38 - 3:00)
  // =========================================================================
  console.log('📍 [Scene 8] Closed-Loop Sisa Abu ke Petani & Kepastian Bayar 14 Hari (ISO 27001)');
  await setHud(
    '🔄 SIKLUS SIRKULAR TERTUTUP · WASTE-TO-SOIL REGENERATION',
    'Sisa Abu Pembakaran & Biochar Lolos Uji Logam Berat Didistribusikan ke Sawah',
    'Hasil sisa abu pembakaran dan biochar diuji laboratorium ketat (bebas timbal Pb, kadmium Cd, arsen As), dikirim kembali ke pengepul, lalu pengepul membagikan ke petani untuk memulihkan hara dan retensi air tanah sawah.',
    ['APPROVED_FOR_SOIL', 'Bebas Logam Berat', 'Distribusi Balik Sawah', '100% Sirkular']
  );

  // Beralih ke Portal Persona Pabrik Inbound & QC Logam Berat
  await userClick('button[data-tab="tab-persona"]');
  await sleep(1200);
  await page.evaluate(() => window.__moveCursor('#persona-content'));
  await sleep(2200);

  // Tata Kelola ISO 27001 & Kepastian Pembayaran 14 Hari
  await setHud(
    '🛡️ TATA KELOLA DATA ISO 27001 & KEPASTIAN BAYAR MAKSIMAL 14 HARI',
    'Jaminan Kepastian Pembayaran 14 Hari bagi Penggilingan Padi & Standar ISO 27001',
    'Seluruh proses dilindungi tata kelola keamanan data berstandar <b>ISO 27001</b> dan ketertelusuran material <b>ISO 22095</b>. Menjamin <b>kepastian pembayaran maksimal 14 hari bagi penggilingan padi</b> serta kompensasi proporsional bagi pengepul.',
    ['ISO 27001 Security', 'Kepastian Bayar ≤ 14 Hari', 'ISO 22095 Traceability', 'Ekosistem Berkeadilan']
  );
  await sleep(2500);

  // Parameter & Tata Kelola
  await userClick('button[data-tab="tab-params"]');
  await sleep(1500);
  await page.evaluate(() => window.__moveCursor('#tab-params .card-header'));
  await sleep(2200);

  // Penutup: Kesimpulan Transformasi Rantai Pasok
  await setHud(
    '✨ BIO-CHAIN v2 · TRANSFORMASI RANTAI PENGADAAN KONVENSIONAL',
    'Ekosistem Terpadu Berkeadilan, Presisi Solver HiGHS, & Sirkular Berkelanjutan',
    'Inovasi ini mentransformasi rantai pengadaan konvensional menjadi ekosistem terpadu yang memberikan kompensasi proporsional bagi pengepul sebagai agregator, sekaligus menjamin kepastian pembayaran maksimal 14 hari bagi penggilingan padi.',
    ['Sirkular Penuh', 'Kompensasi Adil', 'Presisi Solver HiGHS', 'Standar Global']
  );
  await sleep(3000);

  console.log('🎬 Perekaman selesai! Menutup sesi browser Playwright...');
  await page.close();
  await context.close();
  await browser.close();

  // Cari file video mentah (.webm) yang dihasilkan oleh Playwright
  const webmFiles = fs.readdirSync(RAW_DIR).filter(f => f.endsWith('.webm'));
  if (webmFiles.length === 0) {
    throw new Error('Tidak ditemukan file video webm di direktori raw!');
  }

  const rawVideoPath = path.join(RAW_DIR, webmFiles[0]);
  console.log(`🎥 Raw WebM Video: ${rawVideoPath}`);

  // Transcoding ke MP4 Full HD 1080p dengan ffmpeg tepat 3 menit
  console.log('⚙️ Mengonversi ke Full HD 1080p MP4 dengan FFmpeg (Versi 3 Menit)...');
  const ffmpegCmd = `ffmpeg -y -i "${rawVideoPath}" -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -r 30 "${FINAL_OUTPUT_3MIN}"`;
  console.log(`Menjalankan: ${ffmpegCmd}`);
  execSync(ffmpegCmd, { stdio: 'inherit' });

  // Update file default juga agar selalu menyajikan versi 3 menit terbaru
  try {
    fs.copyFileSync(FINAL_OUTPUT_3MIN, FINAL_OUTPUT_DEFAULT);
  } catch {}

  const stats = fs.statSync(FINAL_OUTPUT_3MIN);
  const sizeMb = (stats.size / (1024 * 1024)).toFixed(2);
  console.log(`✅ VIDEO HD 3 MENIT BERHASIL DIBUAT!`);
  console.log(`📁 Lokasi: ${FINAL_OUTPUT_3MIN}`);
  console.log(`📦 Ukuran: ${sizeMb} MB`);
}

main().catch((err) => {
  console.error('❌ Gagal merekam video:', err);
  process.exit(1);
});
