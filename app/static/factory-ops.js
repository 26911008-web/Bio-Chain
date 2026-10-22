/* Bio-Chain factory-ops UI — Pabrik/Admin/Auditor:
 *  ♻️ Serah-terima biochar ke sawah petani (pabrik/admin)
 *  💡 Optimasi & penghematan per proses rantai pasok: terealisasi · tercatat · potensi (Rp & kgCO₂e)
 *  🌍 Laporan ESG (E/S/G, karbon dilaporkan terpisah) + unduh CSV + cetak
 * Memakai helper global dari index.html (api, $, esc, num, rp, showToast, withBusy, emptyState, STATE).
 */
(() => {
  "use strict";
  const H = (s) => esc(s == null ? "" : String(s));
  const role = () => (STATE.user || {}).role;
  const canWrite = () => ["pabrik", "admin"].includes(role());
  const ym = (d) => d.toISOString().slice(0, 7);
  const kg2t = (kg) => `${num((kg || 0) / 1000, 2)} t`;
  const co2 = (kg) => (Math.abs(kg || 0) >= 1000 ? `${num(kg / 1000, 2)} tCO₂e` : `${num(kg || 0, 0)} kgCO₂e`);
  const STATUS_BADGE = { baik: "badge-green", perhatian: "badge-amber", kritis: "badge-red", info: "badge-gray" };
  const ACT_BADGE = { rencana: "badge-gray", berjalan: "badge-amber", terverifikasi: "badge-green", batal: "badge-gray" };
  let lastEff = null;

  function periodControls(prefix) {
    const now = new Date(), from = new Date(now.getFullYear(), now.getMonth() - 11, 1);
    return `<div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
      <label class="kpi-lbl" for="${prefix}-from">Dari</label><input id="${prefix}-from" type="month" class="btn btn-secondary btn-sm" value="${ym(from)}">
      <label class="kpi-lbl" for="${prefix}-to">s.d.</label><input id="${prefix}-to" type="month" class="btn btn-secondary btn-sm" value="${ym(now)}">
      <button type="button" class="btn btn-primary btn-sm" id="${prefix}-go">Tampilkan</button></div>`;
  }
  const q = (prefix) => `?from=${$(`${prefix}-from`).value}&to=${$(`${prefix}-to`).value}`;

  const HTML = () => `
    ${canWrite() ? `<section class="card" aria-labelledby="fx-br-title">
      <div class="card-header"><div><h3 class="card-title" id="fx-br-title">♻️ Serah-terima Abu Bottom Ash ke Petani</h3>
        <p class="card-sub">Pengajuan abu bottom ash petani untuk sawah. Dompet abu petani baru berkurang saat karung diserahkan.</p></div></div>
      <div id="fx-br"><p class="muted">Memuat…</p></div></section>

    <section class="card" aria-labelledby="fx-bd-title">
      <div class="card-header"><div><h3 class="card-title" id="fx-bd-title">🚚 Surat Jalan Muatan Balik Abu Bottom Ash (Pabrik ➔ Pengepul / Driver)</h3>
        <p class="card-sub">Pabrik menerbitkan surat jalan abu bottom ash muatan balik agar armada tidak pulang kosong. Pengangkutan terlacak via QR checkpoint supir.</p></div>
        <button type="button" class="btn btn-primary btn-sm" id="btn-fx-dispatch-biochar">➕ Terbitkan Surat Jalan Abu Bottom Ash</button>
      </div>
      <div id="fx-bd-list"><p class="muted">Memuat riwayat surat jalan…</p></div></section>` : ""}

    <section class="card" aria-labelledby="fx-bm-title">
      <div class="card-header"><div><h3 class="card-title" id="fx-bm-title">🌾 Master Multi-Biomassa</h3>
        <p class="card-sub">Nilai awal = titik tengah literatur (docs/15). Ganti dengan hasil lab per lot; harga dasar beli WAJIB diisi pabrik (tanpa angka bawaan).</p></div>
        ${canWrite() ? `<button type="button" class="btn btn-primary btn-sm" id="btn-add-biomass">➕ Tambah Komoditas</button>` : ""}
      </div>
      <div id="fx-bm"><p class="muted">Memuat…</p></div></section>

    ${canWrite() ? `<section class="card" aria-labelledby="fx-fb-title">
      <div class="card-header"><div><h3 class="card-title" id="fx-fb-title">⚗️ Prototipe 1 — Blend Bahan Bakar &amp; Briket Biaya Terendah &amp; Risiko Terak</h3>
        <p class="card-sub">LP HiGHS: campuran termurah (pellet / briket / co-firing) yang memenuhi kalori, abu, klorin dan indeks alkali (anti-slagging boiler). Geser slider untuk uji campuran manual.</p></div></div>
      <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:8px;">
        <div class="form-group"><label for="fx-fb-preset">Spesifikasi produk</label><select id="fx-fb-preset"></select></div>
        <div class="form-group"><label for="fx-fb-target">Target produk (kg)</label><input id="fx-fb-target" type="number" min="1" step="100" value="10000"></div>
        <div class="form-group"><label for="fx-fb-kcal">Target kalori (kcal/kg, opsional)</label><input id="fx-fb-kcal" type="number" min="1000" max="6000" step="50"></div>
      </div>
      <div id="fx-fb-feeds" class="table-scroll"><p class="muted">Memuat…</p></div>
      <button type="button" class="btn btn-primary btn-sm" id="fx-fb-go">⚙️ Optimasi campuran</button>
      <div id="fx-fb-out" style="margin-top:12px;"></div>
      <div id="fx-fb-sliders" style="margin-top:12px;"></div>
      <div style="max-width:420px; margin:12px auto;"><canvas id="fx-fb-radar" aria-label="Radar mutu campuran terhadap batas spesifikasi" role="img"></canvas></div>
    </section>` : ""}

    <section class="card" aria-labelledby="fx-cv-title">
      <div class="card-header"><div><h3 class="card-title" id="fx-cv-title">⚡ Prototipe 2 — Energi Riil &amp; Rute Konversi Multi-Biomassa</h3>
        <p class="card-sub">Nilai kalor basis kadar air lapangan (ISO 18125), potensi listrik η 22/28/36 %, CO₂ dihindari (grid JAMALI) dan pohon keputusan teknologi (pellet, briket, biochar, bio-silika, daya termal).</p></div></div>
      <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:8px;">
        <div class="form-group"><label for="fx-cv-com">Komoditas</label><select id="fx-cv-com"></select></div>
        <div class="form-group"><label for="fx-cv-t">Tonase / bulan (as received)</label><input id="fx-cv-t" type="number" min="1" step="10" value="500"></div>
        <div class="form-group"><label for="fx-cv-mc">MC aktual (%)</label><input id="fx-cv-mc" type="number" min="0" max="94" step="0.5" placeholder="tipikal"></div>
        <div class="form-group"><label for="fx-cv-km">Jarak ke PLTU (km, opsional)</label><input id="fx-cv-km" type="number" min="0" step="1"></div>
      </div>
      <button type="button" class="btn btn-primary btn-sm" id="fx-cv-go">⚡ Hitung</button>
      <div id="fx-cv-out" style="margin-top:12px;"></div></section>

    <section class="card" aria-labelledby="fx-opt-title" id="fx-opt-card">
      <div class="card-header"><div><h3 class="card-title" id="fx-opt-title">🎯 Prototipe 4 — Optimasi Multi-Biomassa ke Produk Akhir</h3>
        <p class="card-sub">Evaluasi komprehensif &amp; alokasi LP stok pabrik: konversi aneka biomassa menjadi <b>Bio-Pellet, Briket, Biochar, dan Bio-Silika</b> (neraca massa, SEC/IKE, margin Rp, karbon tCO₂e, kepatuhan SNI/ISO).</p></div>
        <div style="display:flex; gap:6px;">
          <button type="button" class="btn btn-primary btn-sm" id="fx-opt-tab-eval">🔍 Evaluasi Lot</button>
          <button type="button" class="btn btn-secondary btn-sm" id="fx-opt-tab-alloc">⚙️ Alokasi Stok Pabrik</button>
        </div>
      </div>

      <!-- Mode 1: Evaluasi Umpan Spesifik -->
      <div id="fx-opt-view-eval" style="margin-top:8px;">
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:8px;">
          <div class="form-group"><label for="fx-opt-com">Komoditas biomassa</label><select id="fx-opt-com"></select></div>
          <div class="form-group"><label for="fx-opt-kg">Jumlah umpan (kg)</label><input id="fx-opt-kg" type="number" min="100" step="500" value="10000"></div>
          <div class="form-group"><label for="fx-opt-mc">MC aktual (%)</label><input id="fx-opt-mc" type="number" min="0" max="90" step="0.5" placeholder="tipikal"></div>
          <div class="form-group"><label for="fx-opt-price">Harga beli (Rp/kg)</label><input id="fx-opt-price" type="number" min="0" step="10" placeholder="dasar komoditas"></div>
        </div>
        <button type="button" class="btn btn-primary btn-sm" id="fx-opt-eval-go" style="margin-top:6px;">⚡ Evaluasi 4 Produk Akhir</button>
        <div id="fx-opt-eval-out" style="margin-top:12px;"></div>
      </div>

      <!-- Mode 2: Solver Alokasi Stok Pabrik -->
      <div id="fx-opt-view-alloc" style="display:none; margin-top:8px;">
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:8px;">
          <div class="form-group"><label for="fx-opt-obj">Tujuan optimasi (LP Objective)</label>
            <select id="fx-opt-obj">
              <option value="max_profit">💰 Maksimal Keuntungan / Margin (Rp)</option>
              <option value="max_energy">⚡ Maksimal Output Energi Bersih (GJ)</option>
              <option value="max_carbon">🌱 Maksimal Net Carbon Sink (tCO₂e)</option>
              <option value="balanced">⚖️ Seimbang (Multi-Kriteria)</option>
            </select>
          </div>
          <div class="form-group" style="grid-column:span 2;"><label class="kpi-lbl">Batas Kapasitas Mesin Pabrik (kg produk/bulan)</label>
            <div style="display:flex; gap:8px; flex-wrap:wrap; font-size:12px; margin-top:4px;" id="fx-opt-caps-inputs">
              <!-- diisi dari config -->
            </div>
          </div>
        </div>
        <h4 style="margin:12px 0 4px;">Inventori Stok Biomassa Pabrik</h4>
        <div id="fx-opt-alloc-stocks" class="table-scroll"><p class="muted">Memuat stok...</p></div>
        <button type="button" class="btn btn-primary btn-sm" id="fx-opt-alloc-go" style="margin-top:8px;">🎯 Jalankan Solver Alokasi HiGHS</button>
        <div id="fx-opt-alloc-out" style="margin-top:12px;"></div>
      </div>
    </section>

    <section class="card" aria-labelledby="fx-sec-title">
      <div class="card-header"><div><h3 class="card-title" id="fx-sec-title">📈 Prototipe 3 — Pemantauan SEC/IKE &amp; Deteksi Anomali</h3>
        <p class="card-sub">SEC = energi (listrik + solar + biomassa) ÷ ton produk, dinormalisasi jam operasi, beban &amp; kadar air umpan (ISO 50006). Batas bergerak ±2σ/±3σ + CUSUM.</p></div></div>
      ${canWrite() ? `<details><summary class="kpi-lbl">➕ Input log energi</summary>
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:8px; margin-top:8px;">
          <div class="form-group"><label for="fx-sec-fac">Fasilitas</label><input id="fx-sec-fac" value="Pabrik Utama" maxlength="100"></div>
          <div class="form-group"><label for="fx-sec-date">Tanggal</label><input id="fx-sec-date" type="date"></div>
          <div class="form-group"><label for="fx-sec-kwh">kWh total</label><input id="fx-sec-kwh" type="number" min="0" step="0.1"></div>
          <div class="form-group"><label for="fx-sec-hm">kWh hammer mill</label><input id="fx-sec-hm" type="number" min="0" step="0.1"></div>
          <div class="form-group"><label for="fx-sec-dsl">Solar (L)</label><input id="fx-sec-dsl" type="number" min="0" step="0.1" value="0"></div>
          <div class="form-group"><label for="fx-sec-bio">Bahan bakar biomassa (kg)</label><input id="fx-sec-bio" type="number" min="0" step="1" value="0"></div>
          <div class="form-group"><label for="fx-sec-h">Jam operasi</label><input id="fx-sec-h" type="number" min="0.5" max="24" step="0.5"></div>
          <div class="form-group"><label for="fx-sec-t">Produk (ton)</label><input id="fx-sec-t" type="number" min="0.01" step="0.01"></div>
          <div class="form-group"><label for="fx-sec-mc">MC umpan (%)</label><input id="fx-sec-mc" type="number" min="0" max="94" step="0.5"></div>
          <div class="form-group"><label for="fx-sec-cap">Kapasitas (t/jam)</label><input id="fx-sec-cap" type="number" min="0.01" step="0.1"></div>
        </div>
        <button type="button" class="btn btn-primary btn-sm" id="fx-sec-add">Simpan log</button>
        <div class="form-group" style="margin-top:8px;"><label for="fx-sec-csv">Atau tempel CSV: tanggal,kwh_total,kwh_hammer_mill,solar_l,biomassa_kg,jam,ton,mc_umpan,kapasitas_t_jam</label>
          <textarea id="fx-sec-csv" rows="3" placeholder="2026-10-01,1650,260,0,0,8,14.4,14,2"></textarea></div>
        <button type="button" class="btn btn-secondary btn-sm" id="fx-sec-import">Impor CSV</button></details>` : ""}
      <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:8px; margin-top:8px;">
        <div class="form-group"><label for="fx-sec-sel">Fasilitas dianalisis</label><select id="fx-sec-sel"></select></div>
        <div class="form-group"><label for="fx-sec-idle">Daya idle terukur (kW, opsional)</label><input id="fx-sec-idle" type="number" min="0" step="0.1"></div>
        <div class="form-group"><label for="fx-sec-feed">Bahan umpan (acuan MC)</label><select id="fx-sec-feed"><option value="">—</option></select></div>
      </div>
      <button type="button" class="btn btn-primary btn-sm" id="fx-sec-go">📈 Analisis</button>
      <div id="fx-sec-out" style="margin-top:12px;"></div>
      <div style="height:280px;"><canvas id="fx-sec-chart" aria-label="Residual energi terhadap batas bergerak" role="img"></canvas></div>
    </section>

    <section class="card" aria-labelledby="fx-ash-title">
      <div class="card-header"><div><h3 class="card-title" id="fx-ash-title">🪨 Ledger Abu → Kelompok Tani</h3>
        <p class="card-sub">Abu boiler/pirolisis hanya boleh ke lahan bila lulus uji logam berat (Kepmentan 261/2019). Serah-terima wajib foto &amp; titik lahan.</p></div>
        ${canWrite() ? `<div style="display:flex; gap:8px; flex-wrap:wrap;"><button type="button" class="btn btn-secondary btn-sm" id="fx-grp-new">➕ Poktan</button>
          <button type="button" class="btn btn-primary btn-sm" id="fx-ash-new">➕ Catat abu</button></div>` : ""}</div>
      <div id="fx-ash"><p class="muted">Memuat…</p></div></section>

    <section class="card" aria-labelledby="fx-ch-title">
      <div class="card-header"><div><h3 class="card-title" id="fx-ch-title">🚚 Potongan Logistik Pengepul</h3>
        <p class="card-sub">Ongkos jarak kosong (batal saat truk di jalan / stok tidak ada). Dipotong otomatis saat tagihan pengepul ditandai lunas.</p></div></div>
      <div id="fx-ch"><p class="muted">Memuat…</p></div></section>

    <section class="card" aria-labelledby="fx-eff-title">
      <div class="card-header"><div><h3 class="card-title" id="fx-eff-title">💡 Optimasi &amp; Penghematan Rantai Pasok</h3>
        <p class="card-sub">Per proses: penghematan terealisasi (otomatis dari data), aksi tercatat, dan potensi ke target — Rupiah &amp; emisi.</p></div>
        ${periodControls("fx-eff")}</div>
      <div id="fx-eff"><p class="muted">Memuat…</p></div></section>

    <section class="card" aria-labelledby="fx-cc-title">
      <div class="card-header"><div><h3 class="card-title" id="fx-cc-title">🧾 Klaim Removal Karbon</h3>
        <p class="card-sub">Pabrik mengajukan dengan hasil lab; auditor (orang lain) memverifikasi. Serah-terima biochar dikunci
          ke satu klaim, jadi tidak terhitung dua kali. Terverifikasi = verifikasi internal, <b>bukan kredit karbon</b>.</p></div></div>
      ${role() === "pabrik" ? `<form id="fx-cc-form" style="display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:8px;">
        <div class="form-group"><label for="fx-cc-from">Bulan awal</label><input id="fx-cc-from" type="month" required value="${ym(new Date())}"></div>
        <div class="form-group"><label for="fx-cc-to">Bulan akhir</label><input id="fx-cc-to" type="month" required value="${ym(new Date())}"></div>
        <div class="form-group"><label for="fx-cc-corg">C-organik lab (% bk)</label><input id="fx-cc-corg" type="number" step="0.1" min="0.1" max="100" required inputmode="decimal"></div>
        <div class="form-group"><label for="fx-cc-hc">Rasio H/C-org (molar)</label><input id="fx-cc-hc" type="number" step="0.01" min="0.01" max="2" required inputmode="decimal"></div>
        <div class="form-group"><label for="fx-cc-lab">Nama laboratorium</label><input id="fx-cc-lab" required minlength="3" maxlength="120"></div>
        <div class="form-group"><label for="fx-cc-no">No. laporan lab</label><input id="fx-cc-no" required minlength="2" maxlength="80"></div>
        <div class="form-group"><label for="fx-cc-photo">Foto/scan laporan lab</label><input id="fx-cc-photo" type="file" accept="image/*" required></div>
        <div class="form-group" style="align-self:end; display:flex; gap:8px;">
          <button type="submit" class="btn btn-secondary btn-sm" data-mode="preview">🔎 Pratinjau</button>
          <button type="submit" class="btn btn-primary btn-sm" data-mode="submit" id="fx-cc-submit" disabled>📤 Ajukan</button></div>
      </form><div id="fx-cc-preview"></div>` : ""}
      <div id="fx-cc"><p class="muted">Memuat…</p></div></section>

    <section class="card" aria-labelledby="fx-esg-title" id="fx-esg-card">
      <div class="card-header"><div><h3 class="card-title" id="fx-esg-title">🌍 Laporan ESG</h3>
        <p class="card-sub">Lingkungan · Sosial · Tata kelola dari data operasional. Emisi, penyimpanan karbon &amp; emisi dihindari dilaporkan terpisah.</p></div>
        <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">${periodControls("fx-esg")}
          <button type="button" class="btn btn-secondary btn-sm" id="fx-esg-csv">⬇️ CSV</button>
          <button type="button" class="btn btn-secondary btn-sm" id="fx-esg-print">🖨️ Cetak / PDF</button></div></div>
      <div id="fx-esg"><p class="muted">Memuat…</p></div></section>`;

  // ---------------------------------------------------------------- serah-terima biochar
  async function loadRedemptions() {
    const box = $("fx-br");
    if (!box) return;
    try {
      const rows = await api("/api/v1/factory/biochar-redemptions");
      box.innerHTML = rows.length ? `<div class="table-scroll"><table class="data-table"><thead><tr><th>#</th><th>Petani</th>
          <th class="num">kg</th><th>Sawah</th><th>Ambil di</th><th>Aksi</th></tr></thead><tbody>${rows.map(r => `<tr>
          <td>${Number(r.id)}<br><span class="kpi-lbl">${H((r.created_at || "").slice(0, 10))}</span></td><td>${H(r.farmer_name)}</td>
          <td class="num">${num(r.kg, 1)}</td><td>${r.land_area_ha ? `${num(r.land_area_ha, 2)} ha` : "-"}</td><td>${H(r.pickup_point)}</td>
          <td style="white-space:nowrap;"><input type="number" class="btn btn-secondary btn-sm" id="fx-br-kg-${r.id}" value="${Number(r.kg)}" min="0.1" max="${Number(r.kg)}" step="0.1" style="width:90px;" aria-label="kg diserahkan permintaan #${r.id}">
            <button type="button" class="btn btn-primary btn-sm" data-fx-handover="${Number(r.id)}">Serahkan</button></td></tr>`).join("")}
          </tbody></table></div>`
        : emptyState("♻️", "Tidak ada pengajuan", "Pengajuan abu bottom ash dari petani muncul di sini.");
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  async function loadBiocharDispatches() {
    const box = $("fx-bd-list");
    if (!box) return;
    try {
      const rows = await api("/api/v1/factory/biochar-dispatches");
      if (!rows.length) {
        box.innerHTML = emptyState("🚚", "Belum ada surat jalan abu bottom ash", "Pabrik dapat menerbitkan muatan balik abu bottom ash untuk diantar armada ke sawah petani.");
        return;
      }
      const groups = {};
      rows.forEach(r => {
        const meta = (typeof window.getMonthYearMeta === "function")
          ? window.getMonthYearMeta(r.created_at)
          : { key: "2026-10", label: "Oktober 2026" };
        if (!groups[meta.key]) groups[meta.key] = { meta, items: [], totalKg: 0, totalBags: 0 };
        groups[meta.key].items.push(r);
        groups[meta.key].totalKg += (Number(r.total_weight_kg) || 0);
        groups[meta.key].totalBags += (Number(r.total_bags) || 0);
      });
      const sortedKeys = Object.keys(groups).sort().reverse();
      box.innerHTML = `<div class="table-scroll"><table class="data-table"><thead><tr><th>No. Surat Jalan</th><th>Pengepul</th>
          <th class="num">Berat (kg)</th><th class="num">Karung</th><th>Plat Armada</th><th>Status</th><th>QR Checkpoint</th></tr></thead><tbody>
          ${sortedKeys.map(k => {
            const g = groups[k];
            return `
              <tr class="group-header-row" style="background:var(--surface-2); font-weight:700;">
                <td colspan="7" style="padding:10px 14px; border-top:2px solid var(--border); color:var(--ink);">
                  <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                      <span style="font-size:1.05rem;">📅 ${H(g.meta.label)}</span>
                      <span class="badge badge-purple">${g.items.length} Surat Jalan</span>
                      <span class="badge badge-green">${num(g.totalKg, 0)} kg (${num(g.totalKg/1000, 2)} Ton)</span>
                      <span class="badge badge-blue">${num(g.totalBags, 0)} Karung</span>
                    </div>
                  </div>
                </td>
              </tr>
              ${g.items.map(r => `<tr>
                <td><b>${H(r.dispatch_code)}</b><br><span class="kpi-lbl">${H((r.created_at || "").slice(0, 10))}</span></td>
                <td>${H(r.collector_name)}</td>
                <td class="num"><b>${num(r.total_weight_kg, 1)}</b></td>
                <td class="num">${Number(r.total_bags || 0)}</td>
                <td><code>${H(r.vehicle_plate || "-")}</code></td>
                <td><span class="badge ${r.status === "DELIVERED_TO_FARMER" ? "badge-green" : "badge-blue"}">${H(r.status)}</span></td>
                <td><button type="button" class="btn btn-secondary btn-sm" data-fx-dsp-qr="${H(r.qr_dispatch_token)}" data-fx-dsp-code="${H(r.dispatch_code)}" data-fx-dsp-kg="${num(r.total_weight_kg, 0)}">Tampilkan QR</button></td>
              </tr>`).join("")}
            `;
          }).join("")}
          </tbody></table></div>`;
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  function openBiocharDispatchModal() {
    if (window.FactoryQcModal && window.FactoryQcModal.openBiocharDispatchModal) {
      return window.FactoryQcModal.openBiocharDispatchModal({ onCreated: loadBiocharDispatches });
    }
  }


  async function loadCharges() {
    const box = $("fx-ch");
    if (!box) return;
    try {
      const rows = await api("/api/v1/factory/charges?status=semua");
      box.innerHTML = rows.length ? `<div class="table-scroll"><table class="data-table"><thead><tr><th>#</th><th>Kejadian</th>
          <th class="num">Ongkos</th><th>Status</th>${canWrite() ? "<th></th>" : ""}</tr></thead><tbody>${rows.map(c => `<tr>
          <td>${Number(c.id)}<br><span class="kpi-lbl">pengepul #${Number(c.collector_id)}</span></td>
          <td>${H(c.kind)} · lot #${Number(c.harvest_id)}<br><span class="kpi-lbl">${H(c.reason || "")}</span></td>
          <td class="num">${rp(c.amount_rp)}<br><span class="kpi-lbl">${num(c.km, 1)} km</span></td>
          <td><span class="badge ${c.status === "terbuka" ? "badge-amber" : c.status === "dibebaskan" ? "badge-green" : "badge-gray"}">${H(c.status)}</span>
            ${c.settlement_id ? `<br><span class="kpi-lbl">tagihan #${Number(c.settlement_id)}</span>` : ""}</td>
          ${canWrite() ? `<td>${c.status === "terbuka" ? `<button type="button" class="btn btn-secondary btn-sm" data-fx-waive="${Number(c.id)}">Bebaskan</button>` : ""}</td>` : ""}
          </tr>`).join("")}</tbody></table></div>`
        : emptyState("🚚", "Belum ada potongan", "Potongan muncul bila pengepul membatalkan saat truk sudah berangkat.");
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  function waiveCharge(id) {
    const d = document.createElement("dialog");
    d.className = "ui-confirm";
    d.innerHTML = `<form method="dialog"><h3>Bebaskan potongan #${Number(id)}</h3>
      <p class="ui-confirm-body">Gunakan hanya bila bukan kesalahan pengepul (jalan putus, banjir, truk rusak). Alasan tercatat untuk audit.</p>
      <div class="form-group"><label for="fx-wv">Alasan</label><input id="fx-wv" required minlength="3" maxlength="300"></div>
      <div class="ui-confirm-actions"><button value="no" class="btn btn-secondary" formnovalidate>Batal</button>
        <button value="yes" class="btn btn-primary">Bebaskan</button></div></form>`;
    document.body.appendChild(d);
    d.addEventListener("close", async () => {
      const reason = d.querySelector("#fx-wv").value.trim();
      const yes = d.returnValue === "yes";
      d.remove();
      if (!yes || reason.length < 3) return;
      try { await api(`/api/v1/factory/charges/${id}/waive`, { body: { reason } }); showToast("Potongan dibebaskan.", "✅"); loadCharges(); }
      catch (e) { showToast(e.message, "❌"); }
    });
    d.showModal();
  }

  // ---------------------------------------------------------------- optimasi & penghematan
  async function loadEfficiency() {
    const box = $("fx-eff");
    if (!box) return;
    try {
      const o = lastEff = await api(`/api/v1/factory/efficiency${q("fx-eff")}`);
      const P = o.processes;
      box.innerHTML = `
        <div class="kpi-row">
          <div class="kpi-tile"><div class="kpi-lbl">Terealisasi (otomatis)</div><div class="kpi-val">${rp(o.realized_totals.saving_rp)}</div>
            <div class="kpi-lbl">${co2(o.realized_totals.saving_co2e_kg)} dikurangi/dihindari</div></div>
          <div class="kpi-tile"><div class="kpi-lbl">Aksi tercatat</div><div class="kpi-val">${rp(o.recorded_totals.saving_rp)}</div>
            <div class="kpi-lbl">${co2(o.recorded_totals.saving_co2e_kg)} · ${o.recorded_totals.verified}/${o.recorded_totals.count} terverifikasi</div></div>
          <div class="kpi-tile kpi-warn"><div class="kpi-lbl">Potensi ke target</div><div class="kpi-val">${rp(o.potential_totals.saving_rp)}</div>
            <div class="kpi-lbl">${co2(o.potential_totals.saving_co2e_kg)} bila semua gap ditutup</div></div>
        </div>
        <h4 style="margin:16px 0 8px;">✅ Terealisasi dari data</h4>
        <div class="table-scroll"><table class="data-table"><thead><tr><th>Proses</th><th>Penghematan</th><th class="num">Jumlah</th>
          <th class="num">Rp</th><th class="num">Emisi</th></tr></thead><tbody>${o.realized.map(r => `<tr>
          <td>${H(P[r.process] || r.process)}</td><td>${H(r.title)}<br><span class="kpi-lbl">${H(r.basis)}</span></td>
          <td class="num">${num(r.quantity, 1)} ${H(r.unit)}</td><td class="num">${rp(r.saving_rp)}</td><td class="num">${co2(r.saving_co2e_kg)}</td></tr>`).join("")}
          </tbody></table></div>
        <h4 style="margin:16px 0 8px;">🎯 Peluang per proses &amp; rekomendasi</h4>
        <div class="table-scroll"><table class="data-table"><thead><tr><th>Proses / KPI</th><th class="num">Aktual</th><th class="num">Target</th>
          <th class="num">Potensi</th><th>Rekomendasi</th>${canWrite() ? "<th></th>" : ""}</tr></thead><tbody>${o.potential.map(p => `<tr>
          <td><b>${H(P[p.process] || p.process)}</b><br>${H(p.kpi)} <span class="badge ${STATUS_BADGE[p.status] || ""}">${H(p.status)}</span></td>
          <td class="num">${p.actual == null ? "–" : num(p.actual, 1)} <span class="kpi-lbl">${H(p.unit)}</span></td>
          <td class="num">${p.target == null ? "–" : num(p.target, 1)}</td>
          <td class="num">${p.saving_rp == null ? "–" : rp(p.saving_rp)}<br><span class="kpi-lbl">${p.saving_co2e_kg == null ? "" : co2(p.saving_co2e_kg)}</span></td>
          <td>${H(p.recommendation)}</td>
          ${canWrite() ? `<td><button type="button" class="btn btn-secondary btn-sm" data-fx-adopt="${H(p.code)}">Jadikan aksi</button></td>` : ""}</tr>`).join("")}
          </tbody></table></div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin:16px 0 8px; gap:8px; flex-wrap:wrap;">
          <h4 style="margin:0;">📒 Register aksi penghematan</h4>
          ${canWrite() ? `<button type="button" class="btn btn-primary btn-sm" data-fx-adopt="">➕ Catat aksi</button>` : ""}</div>
        ${o.actions.length ? `<div class="table-scroll"><table class="data-table"><thead><tr><th>Aksi</th><th>Proses</th><th class="num">Sebelum → sesudah</th>
          <th class="num">Hemat</th><th>Status</th>${canWrite() ? "<th></th>" : ""}</tr></thead><tbody>${o.actions.map(a => `<tr>
          <td><b>${H(a.title)}</b>${a.period ? `<br><span class="kpi-lbl">${H(a.period)}</span>` : ""}${a.evidence ? `<br><span class="kpi-lbl">bukti: ${H(a.evidence)}</span>` : ""}</td>
          <td>${H(a.process_label)}</td>
          <td class="num">${a.baseline_value == null ? "–" : num(a.baseline_value, 1)} → ${a.current_value == null ? "–" : num(a.current_value, 1)} <span class="kpi-lbl">${H(a.metric || "")}</span></td>
          <td class="num">${a.saving_rp == null ? "–" : rp(a.saving_rp)}<br><span class="kpi-lbl">${a.saving_co2e_kg == null ? "" : co2(a.saving_co2e_kg)}</span></td>
          <td><span class="badge ${ACT_BADGE[a.status] || ""}">${H(a.status)}</span></td>
          ${canWrite() ? `<td style="white-space:nowrap;">${a.status === "rencana" ? `<button type="button" class="btn btn-secondary btn-sm" data-fx-status="${a.id}" data-to="berjalan">Mulai</button>` : ""}
            ${a.status === "berjalan" ? `<button type="button" class="btn btn-secondary btn-sm" data-fx-status="${a.id}" data-to="terverifikasi">Verifikasi</button>` : ""}
            ${["rencana", "berjalan"].includes(a.status) ? `<button type="button" class="btn btn-secondary btn-sm" data-fx-status="${a.id}" data-to="batal">Batal</button>` : ""}</td>` : ""}
          </tr>`).join("")}</tbody></table></div>`
          : `<p class="muted">Belum ada aksi tercatat. Pilih peluang di atas lalu "Jadikan aksi".</p>`}
        <p class="kpi-lbl">${o.notes.map(H).join(" · ")}</p>`;
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  function actionDialog(code) {
    const p = (lastEff && lastEff.potential.find(x => x.code === code)) || {};
    const procs = (lastEff && lastEff.processes) || {};
    const d = document.createElement("dialog");
    d.className = "ui-confirm";
    d.innerHTML = `<form method="dialog" class="fo-form">
      <h3>${p.code ? `Aksi untuk ${H(p.kpi)}` : "Catat aksi penghematan"}</h3>
      <div class="fo-body">
        <div class="form-group"><label for="fx-a-title">Aksi</label>
          <input id="fx-a-title" name="title" required minlength="3" maxlength="160" value="${H(p.recommendation ? p.recommendation.split(";")[0].slice(0, 150) : "")}"></div>
        <div class="grid-2" style="gap:10px;">
          <div class="form-group"><label for="fx-a-proc">Proses</label><select id="fx-a-proc" name="process">
            ${Object.entries(procs).map(([k, v]) => `<option value="${k}" ${k === p.process ? "selected" : ""}>${H(v)}</option>`).join("")}</select></div>
          <div class="form-group"><label for="fx-a-metric">Satuan KPI</label><input id="fx-a-metric" name="metric" maxlength="60" value="${H(p.unit || "")}"></div>
          <div class="form-group"><label for="fx-a-base">Nilai sebelum</label><input id="fx-a-base" name="baseline_value" type="number" step="any" value="${p.actual == null ? "" : Number(p.actual)}"></div>
          <div class="form-group"><label for="fx-a-cur">Nilai sesudah / target</label><input id="fx-a-cur" name="current_value" type="number" step="any" value="${p.target == null ? "" : Number(p.target)}"></div>
          <div class="form-group"><label for="fx-a-rp">Hemat (Rp/periode)</label><input id="fx-a-rp" name="saving_rp" type="number" min="0" step="1" value="${p.saving_rp == null ? "" : Number(p.saving_rp)}"></div>
          <div class="form-group"><label for="fx-a-co2">Kurang emisi (kgCO₂e)</label><input id="fx-a-co2" name="saving_co2e_kg" type="number" step="any" value="${p.saving_co2e_kg == null ? "" : Number(p.saving_co2e_kg)}"></div>
        </div>
        <div class="form-group"><label for="fx-a-ev">Bukti (opsional)</label><input id="fx-a-ev" name="evidence" maxlength="1000" placeholder="link foto meter, nota BBM, laporan rute"></div>
      </div>
      <p class="form-error" role="alert" hidden></p>
      <div class="ui-confirm-actions"><button value="no" class="btn btn-secondary" formnovalidate>Batal</button>
        <button value="yes" class="btn btn-primary">Simpan aksi</button></div></form>`;
    document.body.appendChild(d);
    const f = d.querySelector("form"), err = d.querySelector(".form-error");
    const n = (k) => (f[k].value === "" ? null : Number(f[k].value));
    f.addEventListener("submit", async (e) => {
      if (e.submitter && e.submitter.value === "no") return;
      e.preventDefault();
      try {
        await api("/api/v1/factory/efficiency/actions", { body: {
          title: f.title.value, process: f.process.value, metric: f.metric.value || null, baseline_value: n("baseline_value"),
          current_value: n("current_value"), saving_rp: n("saving_rp"), saving_co2e_kg: n("saving_co2e_kg"),
          evidence: f.evidence.value || null, period: ym(new Date()), status: "rencana", source_opportunity: p.code || null } });
        d.close(); showToast("Aksi penghematan dicatat.", "📒"); loadEfficiency();
      } catch (ex) { err.hidden = false; err.textContent = ex.message; }
    });
    d.addEventListener("close", () => d.remove());
    d.showModal();
  }

  function askEvidence() {
    return new Promise(resolve => {
      const d = document.createElement("dialog");
      d.className = "ui-confirm";
      d.innerHTML = `<form method="dialog"><h3>Verifikasi aksi penghematan</h3>
        <p class="ui-confirm-body">Verifikasi harus oleh orang lain dari pencatat (empat mata) dan wajib bukti.</p>
        <div class="form-group"><label for="fx-ev">Bukti</label>
          <input id="fx-ev" name="ev" required maxlength="1000" placeholder="link foto meter / nota BBM / laporan rute"></div>
        <div class="ui-confirm-actions"><button value="no" class="btn btn-secondary" formnovalidate>Batal</button>
          <button value="yes" class="btn btn-primary">Verifikasi</button></div></form>`;
      document.body.appendChild(d);
      d.addEventListener("close", () => { resolve(d.returnValue === "yes" ? d.querySelector("#fx-ev").value.trim() : null); d.remove(); });
      d.showModal();
    });
  }

  async function setStatus(id, to) {
    let evidence = null;
    if (to === "terverifikasi") {
      evidence = await askEvidence();
      if (!evidence) return;
    }
    try {
      await api(`/api/v1/factory/efficiency/actions/${id}`, { method: "PATCH", body: { status: to, evidence } });
      showToast(`Status aksi: ${to}`, "✅"); loadEfficiency();
    } catch (e) { showToast(e.message, "❌"); }
  }

  // ---------------------------------------------------------------- laporan ESG
  const fmtVal = (k) => (k.value == null ? "–" : typeof k.value === "number" ? `${num(k.value, k.unit === "Rp" ? 0 : 2)}` : H(k.value));
  const pillar = (title, rows) => `<h4 style="margin:16px 0 8px;">${title}</h4>
    <div class="table-scroll"><table class="data-table esg-table"><thead><tr><th>Kode</th><th>KPI</th><th class="num">Nilai</th>
      <th>Rumus &amp; sumber</th><th>Standar</th></tr></thead><tbody>${rows.map(k => `<tr>
      <td>${H(k.code)}</td><td><b>${H(k.name)}</b>${k.note ? `<br><span class="kpi-lbl">${H(k.note)}</span>` : ""}</td>
      <td class="num">${k.unit === "Rp" && typeof k.value === "number" ? rp(k.value) : `${fmtVal(k)} <span class="kpi-lbl">${H(k.unit)}</span>`}</td>
      <td class="kpi-lbl">${H(k.formula)}<br>📂 ${H(k.source)}</td><td class="kpi-lbl">${H(k.standard)}</td></tr>`).join("")}</tbody></table></div>`;

  async function loadEsg() {
    const box = $("fx-esg");
    if (!box) return;
    try {
      const r = await api(`/api/v1/factory/esg/report${q("fx-esg")}`);
      const c = r.carbon_presentation;
      box.innerHTML = `
        <p class="kpi-lbl">Periode ${H(r.period)} · dibuat ${H(r.generated_at.slice(0, 16).replace("T", " "))} UTC</p>
        <div class="kpi-row">
          <div class="kpi-tile"><div class="kpi-lbl">Emisi bruto proyek</div><div class="kpi-val">${num(c.gross_emissions_tco2e, 2)}</div><div class="kpi-lbl">tCO₂e (Scope 2 + angkut)</div></div>
          <div class="kpi-tile"><div class="kpi-lbl">Karbon tersimpan tahan lama</div><div class="kpi-val">${num(c.removals_durable_tco2e, 2)}</div><div class="kpi-lbl">tCO₂e removal (estimasi)</div></div>
          <div class="kpi-tile"><div class="kpi-lbl">Emisi dihindari</div><div class="kpi-val">${num(c.avoided_tco2e, 2)}</div><div class="kpi-lbl">tCO₂e · tidak dikurangkan</div></div>
          <div class="kpi-tile"><div class="kpi-lbl">Penghematan terealisasi</div><div class="kpi-val">${rp(r.efficiency.realized.saving_rp + r.efficiency.recorded.saving_rp)}</div>
            <div class="kpi-lbl">${co2(r.efficiency.realized.saving_co2e_kg + r.efficiency.recorded.saving_co2e_kg)}</div></div>
        </div>
        <div class="banner banner-info" role="note"><span aria-hidden="true">ℹ️</span><span>${H(c.rule)}</span></div>
        ${pillar("🌱 Lingkungan (E)", r.environment)}
        ${pillar("🤝 Sosial (S)", r.social)}
        ${pillar("🏛️ Tata kelola (G)", r.governance)}
        <details style="margin-top:12px;"><summary class="kpi-lbl">Keterbatasan data &amp; standar rujukan</summary>
          <ul class="kpi-lbl">${r.limitations.map(x => `<li>${H(x)}</li>`).join("")}</ul>
          <p class="kpi-lbl">${r.standards.map(H).join(" · ")}</p></details>`;
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  async function downloadEsgCsv() {
    try {
      const res = await fetch(`/api/v1/factory/esg/report.csv${q("fx-esg")}`, { headers: { Authorization: `Bearer ${STATE.token}` } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(await res.blob());
      a.download = `laporan-esg-${$("fx-esg-from").value}-${$("fx-esg-to").value}.csv`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    } catch (e) { showToast("Gagal mengunduh: " + e.message, "❌"); }
  }

  // ---------------------------------------------------------------- multi-biomassa & abu (018)
  const ASH_BADGE = { tersedia: "badge-gray", dialokasikan: "badge-blue", diserahkan: "badge-green", dibuang: "badge-red" };
  const HM_BADGE = { belum_uji: "badge-gray", lulus: "badge-green", gagal: "badge-red" };
  let bmCache = [], grpCache = [];
  const alkali = (b) => (b.hhv_db_mj_kg && b.k2o_pct_ash != null
    ? b.ash_pct_db * ((b.k2o_pct_ash || 0) + (b.na2o_pct_ash || 0)) / (10 * b.hhv_db_mj_kg) : null);

  function dlg(title, body, onOk) {
    const d = document.createElement("dialog");
    d.className = "ui-confirm";
    d.innerHTML = `<form method="dialog"><h3>${H(title)}</h3><div>${body}</div><p class="form-error" role="alert" hidden></p>
      <div class="ui-confirm-actions"><button value="no" class="btn btn-secondary" formnovalidate>Batal</button>
      <button value="yes" class="btn btn-primary">Simpan</button></div></form>`;
    document.body.appendChild(d);
    const f = d.querySelector("form"), err = d.querySelector(".form-error");
    f.addEventListener("submit", async (e) => {
      if (e.submitter && e.submitter.value === "no") return;
      e.preventDefault();
      if (!f.reportValidity()) return;
      try { await onOk(new FormData(f)); d.close(); } catch (ex) { err.hidden = false; err.textContent = ex.message; }
    });
    d.addEventListener("close", () => d.remove());
    d.showModal();
  }
  const numOrNull = (v) => (v === "" || v == null ? null : Number(v));

  async function loadBiomass() {
    const box = $("fx-bm");
    if (!box) return;
    try {
      bmCache = await api("/api/v1/biomass");
      box.innerHTML = `<div class="table-scroll"><table class="data-table"><thead><tr><th>Komoditas</th><th class="num">MC tipikal / acuan / tolak (%)</th>
        <th class="num">Abu (% bk)</th><th class="num">LHV bk (MJ/kg)</th><th class="num">Indeks alkali (kg/GJ)</th><th class="num">Harga dasar</th><th></th></tr></thead>
        <tbody>${bmCache.map(b => { const ai = alkali(b); return `<tr>
          <td><b>${H(b.name)}</b><br><span class="kpi-lbl" title="${H(b.source)}">${H(b.code)}</span></td>
          <td class="num">${num(b.moisture_typ_pct, 0)} / ${num(b.moisture_ref_pct, 0)} / ${num(b.moisture_reject_pct, 0)}</td>
          <td class="num">${num(b.ash_pct_db, 1)}</td><td class="num">${num(b.lhv_db_mj_kg, 1)}</td>
          <td class="num">${ai == null ? "–" : `<span class="badge ${ai > 0.34 ? "badge-red" : ai > 0.17 ? "badge-amber" : "badge-green"}" title="Miles 1996: >0,17 mungkin terak, >0,34 hampir pasti">${num(ai, 2)}</span>`}</td>
          <td class="num">${b.base_price_per_kg == null ? '<span class="badge badge-amber">belum diisi</span>' : rp(b.base_price_per_kg) + "/kg"}</td>
          <td>${canWrite() ? `<button type="button" class="btn btn-secondary btn-sm" data-fx-bm="${H(b.code)}">Ubah</button>` : ""}</td></tr>`; }).join("")}</tbody></table></div>`;
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  function editBiomass(code) {
    const b = bmCache.find(x => x.code === code);
    if (!b) return;
    const f = (k, label, step = "0.1") => `<div class="form-group"><label for="fx-bm-${k}">${label}</label>
      <input id="fx-bm-${k}" name="${k}" type="number" step="${step}" min="0" value="${H(b[k] ?? "")}" inputmode="decimal"></div>`;
    dlg(`Ubah ${b.name}`, `${f("base_price_per_kg", "Harga dasar beli (Rp/kg)", "1")}${f("moisture_ref_pct", "Kadar air acuan harga (%)")}
      ${f("moisture_reject_pct", "Kadar air tolak (%)")}${f("contaminant_tol_pct", "Toleransi kotoran (%)")}
      ${f("ash_pct_db", "Abu hasil lab (% bk)")}${f("lhv_db_mj_kg", "LHV bk hasil lab (MJ/kg)")}${f("k2o_pct_ash", "K₂O dalam abu (%)")}
      <div class="form-group"><label for="fx-bm-src">Dasar perubahan (no. laporan lab / sumber harga)</label>
        <input id="fx-bm-src" name="source" required minlength="5" maxlength="500"></div>`, async (fd) => {
      const changes = {};
      for (const k of ["base_price_per_kg", "moisture_ref_pct", "moisture_reject_pct", "contaminant_tol_pct", "ash_pct_db", "lhv_db_mj_kg", "k2o_pct_ash"]) {
        const v = numOrNull(fd.get(k));
        if (v !== (b[k] ?? null)) changes[k] = v;
      }
      if (!Object.keys(changes).length) throw new Error("Tidak ada perubahan.");
      await api(`/api/v1/biomass/${code}`, { method: "PUT", body: { changes, source: fd.get("source") } });
      showToast(`${b.name} diperbarui`, "🌾"); loadBiomass();
    });
  }

  function newBiomass() {
    const f = (k, label, defVal = "", step = "0.1") => `<div class="form-group"><label for="fx-nbm-${k}">${label}</label>
      <input id="fx-nbm-${k}" name="${k}" type="number" step="${step}" min="0" value="${defVal}" inputmode="decimal"></div>`;
    dlg("Tambah Komoditas Biomassa Baru", `
      <div class="form-group"><label for="fx-nbm-name">Nama komoditas</label>
        <input id="fx-nbm-name" name="name" required minlength="2" maxlength="80" placeholder="Misal: Cangkang Kelapa Sawit"></div>
      <div class="form-group"><label for="fx-nbm-code">Kode unik (opsional, kosong = otomatis)</label>
        <input id="fx-nbm-code" name="code" maxlength="24" placeholder="Misal: cangkang_sawit"></div>
      ${f("base_price_per_kg", "Harga beli dasar (Rp/kg)", "600", "1")}
      ${f("moisture_ref_pct", "Kadar air acuan (%)", "14")}
      ${f("moisture_reject_pct", "Kadar air tolak (%)", "22")}
      ${f("contaminant_tol_pct", "Toleransi kotoran (%)", "2")}
      ${f("ash_pct_db", "Kadar abu (% bk)", "3")}
      ${f("lhv_db_mj_kg", "Nilai kalor LHV bk (MJ/kg)", "16")}
      <div class="form-group"><label for="fx-nbm-src">Sumber data / acuan</label>
        <input id="fx-nbm-src" name="source" maxlength="500" value="Input operator pabrik"></div>
    `, async (fd) => {
      const body = {
        name: fd.get("name").trim(),
        code: fd.get("code") ? fd.get("code").trim() : undefined,
        base_price_per_kg: numOrNull(fd.get("base_price_per_kg")),
        moisture_ref_pct: numOrNull(fd.get("moisture_ref_pct")) ?? 14,
        moisture_reject_pct: numOrNull(fd.get("moisture_reject_pct")) ?? 22,
        contaminant_tol_pct: numOrNull(fd.get("contaminant_tol_pct")) ?? 2,
        ash_pct_db: numOrNull(fd.get("ash_pct_db")) ?? 3,
        lhv_db_mj_kg: numOrNull(fd.get("lhv_db_mj_kg")) ?? 16,
        source: fd.get("source") || "Input operator pabrik"
      };
      const res = await api("/api/v1/biomass", { method: "POST", body });
      showToast(`Komoditas ${res.name} berhasil didaftarkan`, "🌿");
      loadBiomass();
    });
  }

  async function loadAsh() {
    const box = $("fx-ash");
    if (!box) return;
    try {
      const [rows, groups] = await Promise.all([api("/api/v1/factory/ash"), api("/api/v1/factory/farmer-groups")]);
      grpCache = groups;
      const act = (a) => !canWrite() ? "" : a.status === "tersedia"
        ? `<button type="button" class="btn btn-secondary btn-sm" data-fx-ash-lab="${a.id}">🧪 Lab</button>
           ${a.heavy_metal_status === "lulus" ? `<button type="button" class="btn btn-primary btn-sm" data-fx-ash-alloc="${a.id}">→ Poktan</button>` : ""}
           <button type="button" class="btn btn-secondary btn-sm" data-fx-ash-dispose="${a.id}">Buang</button>`
        : a.status === "dialokasikan" ? `<button type="button" class="btn btn-primary btn-sm" data-fx-ash-hand="${a.id}">📸 Serahkan</button>` : "";
      box.innerHTML = rows.length ? `<div class="table-scroll"><table class="data-table"><thead><tr><th>Kode</th><th>Jenis</th><th class="num">kg</th>
        <th>Logam berat (mg/kg)</th><th>Poktan</th><th>Status</th><th></th></tr></thead><tbody>${rows.map(a => `<tr>
        <td><b>${H(a.code)}</b></td><td>${H(a.ash_type.replace("_", " "))}</td><td class="num">${num(a.quantity_kg, 0)}</td>
        <td class="kpi-lbl"><span class="badge ${HM_BADGE[a.heavy_metal_status]}">${H(a.heavy_metal_status.replace("_", " "))}</span>
          Pb ${a.metals_ppm.pb ?? "–"} · Cd ${a.metals_ppm.cd ?? "–"} · As ${a.metals_ppm.as ?? "–"}
          ${(a.limits_snapshot?.notes || []).map(n => `<br>⚠️ ${H(n)}`).join("")}</td>
        <td>${H(a.farmer_group || "–")}</td><td><span class="badge ${ASH_BADGE[a.status]}">${H(a.status)}</span></td>
        <td style="white-space:nowrap;">${act(a)}</td></tr>`).join("")}</tbody></table></div>`
        : emptyState("🪨", "Belum ada catatan abu", "Catat abu sisa boiler/pirolisis, uji logam berat, lalu alokasikan ke Poktan.");
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  function newGroup() {
    dlg("Kelompok tani baru", `<div class="form-group"><label for="fx-g-n">Nama Poktan</label><input id="fx-g-n" name="name" required minlength="3"></div>
      <div class="form-group"><label for="fx-g-l">Nama ketua</label><input id="fx-g-l" name="leader_name" required minlength="2"></div>
      <div class="form-group"><label for="fx-g-d">Desa</label><input id="fx-g-d" name="desa"></div>
      <div class="form-group"><label for="fx-g-k">Kecamatan</label><input id="fx-g-k" name="kecamatan" required minlength="2"></div>
      <div class="form-group"><label for="fx-g-b">Kabupaten</label><input id="fx-g-b" name="kabupaten" required minlength="2"></div>
      <div class="form-group"><label for="fx-g-s">No. Simluhtan (opsional)</label><input id="fx-g-s" name="simluhtan_id"></div>`, async (fd) => {
      await api("/api/v1/factory/farmer-groups", { body: { name: fd.get("name"), leader_name: fd.get("leader_name"),
        desa: fd.get("desa") || null, kecamatan: fd.get("kecamatan"), kabupaten: fd.get("kabupaten"),
        simluhtan_id: fd.get("simluhtan_id") || null } });
      showToast("Poktan ditambahkan", "👥"); loadAsh();
    });
  }

  function newAsh() {
    dlg("Catat abu", `<div class="form-group"><label for="fx-a-t">Jenis abu</label><select id="fx-a-t" name="ash_type">
        <option value="bottom_ash">Bottom ash</option><option value="fly_ash">Fly ash</option><option value="silica_ash">Abu silika</option></select></div>
      <div class="form-group"><label for="fx-a-c">Asal biomassa</label><select id="fx-a-c" name="source_commodity"><option value="">—</option>
        ${bmCache.map(b => `<option value="${H(b.code)}">${H(b.name)}</option>`).join("")}</select></div>
      <div class="form-group"><label for="fx-a-q">Tonase (kg)</label><input id="fx-a-q" name="quantity_kg" type="number" min="1" step="1" required></div>`, async (fd) => {
      await api("/api/v1/factory/ash", { body: { ash_type: fd.get("ash_type"), source_commodity: fd.get("source_commodity") || null,
        quantity_kg: Number(fd.get("quantity_kg")) } });
      showToast("Abu dicatat — lanjutkan uji logam berat", "🪨"); loadAsh();
    });
  }

  function ashLab(id) {
    const m = (k, l) => `<div class="form-group"><label for="fx-l-${k}">${l} (mg/kg)</label><input id="fx-l-${k}" name="${k}_ppm" type="number" min="0" step="0.01" inputmode="decimal" ${["pb", "cd", "as"].includes(k) ? "required" : ""}></div>`;
    dlg("Hasil uji logam berat", `${m("pb", "Pb")}${m("cd", "Cd")}${m("as", "As")}${m("hg", "Hg")}${m("cr", "Cr")}${m("ni", "Ni")}
      <div class="form-group"><label for="fx-l-lab">Laboratorium</label><input id="fx-l-lab" name="lab_name"></div>
      <div class="form-group"><label for="fx-l-no">No. laporan lab</label><input id="fx-l-no" name="lab_report_no" required minlength="2"></div>
      <div class="form-group"><label for="fx-l-k">K₂O abu (%) — opsional, untuk dosis</label><input id="fx-l-k" name="k2o_pct" type="number" min="0" max="100" step="0.1"></div>`, async (fd) => {
      const body = { lab_name: fd.get("lab_name") || null, lab_report_no: fd.get("lab_report_no"), k2o_pct: numOrNull(fd.get("k2o_pct")) };
      for (const k of ["pb", "cd", "as", "hg", "cr", "ni"]) body[`${k}_ppm`] = numOrNull(fd.get(`${k}_ppm`));
      const r = await api(`/api/v1/factory/ash/${id}/lab`, { body });
      showToast(`Status uji: ${r.heavy_metal_status}`, r.heavy_metal_status === "lulus" ? "✅" : "⛔"); loadAsh();
    });
  }

  function ashAllocate(id) {
    if (!grpCache.length) return showToast("Tambahkan Poktan dulu.", "👥");
    dlg("Alokasikan ke kelompok tani", `<div class="form-group"><label for="fx-al-g">Poktan</label><select id="fx-al-g" name="g">
        ${grpCache.map(g => `<option value="${g.id}">${H(g.name)} · ${H(g.kecamatan)}</option>`).join("")}</select></div>
      <div class="form-group"><label for="fx-al-ha">Luas lahan (ha)</label><input id="fx-al-ha" name="ha" type="number" min="0.01" step="0.01"></div>`, async (fd) => {
      await api(`/api/v1/factory/ash/${id}/allocate`, { body: { farmer_group_id: Number(fd.get("g")), land_area_ha: numOrNull(fd.get("ha")) } });
      showToast("Abu dialokasikan", "👥"); loadAsh();
    });
  }

  function ashHandover(id) {
    dlg("Serah-terima abu di lahan", `<div class="form-group"><label for="fx-h-p">Foto serah-terima</label><input id="fx-h-p" name="photo" type="file" accept="image/*" capture="environment" required></div>
      <p class="kpi-lbl">Titik lahan diambil dari GPS HP saat menyimpan.</p>`, async (fd) => {
      const pos = await new Promise((ok, no) => navigator.geolocation.getCurrentPosition(p => ok(p.coords),
        () => no(new Error("GPS tidak tersedia — aktifkan lokasi untuk merekam titik lahan.")), { timeout: 8000, enableHighAccuracy: true }));
      const f = fd.get("photo");
      const up = await photoUpload(window.BiochainImage ? await BiochainImage.compress(f) : f);
      await api(`/api/v1/factory/ash/${id}/handover`, { body: { photo_url: up.url, lat: pos.latitude, lon: pos.longitude } });
      showToast("Abu diserahkan & terekam", "📸"); loadAsh();
    });
  }

  function ashDispose(id) {
    dlg("Buang / manfaatkan lain", `<div class="form-group"><label for="fx-d-n">Tujuan (pengolah berizin / pemanfaatan non-lahan)</label>
      <textarea id="fx-d-n" name="note" required minlength="10" rows="3"></textarea></div>`, async (fd) => {
      await api(`/api/v1/factory/ash/${id}/dispose`, { body: { note: fd.get("note") } });
      showToast("Tercatat", "🗑️"); loadAsh();
    });
  }

  // ---------------------------------------------------------------- Prototipe 1: blend bahan bakar
  let fbPresets = null, fbRadar = null, fbTimer = null;
  const VERDICT_BADGE = { AMAN: "badge-green", WASPADA: "badge-amber", BAHAYA: "badge-red", LAYAK: "badge-green", "TIDAK LAYAK": "badge-red" };

  async function initFuelBlend() {
    if (!$("fx-fb-feeds")) return;
    try {
      fbPresets = await api("/api/v1/factory/fuel-blend/presets");
      if (!bmCache.length) bmCache = await api("/api/v1/biomass");
      $("fx-fb-preset").innerHTML = Object.entries(fbPresets.presets).map(([k, v]) => `<option value="${H(k)}">${H(v.label)}</option>`).join("");
      $("fx-fb-feeds").innerHTML = `<table class="data-table"><thead><tr><th>Pakai</th><th>Komoditas</th><th class="num">Stok (kg)</th>
        <th class="num">Harga (Rp/kg)</th><th class="num">MC aktual (%)</th><th class="num">Porsi maks (%)</th></tr></thead><tbody>${bmCache.map(b => `<tr>
        <td><input type="checkbox" data-fb-use="${H(b.code)}" ${fbPresets.factory_stock_kg[b.code] ? "checked" : ""} aria-label="Pakai ${H(b.name)}"></td>
        <td>${H(b.name)}</td>
        <td class="num"><input type="number" min="0" step="100" data-fb-kg="${H(b.code)}" value="${Number(Math.round(fbPresets.factory_stock_kg[b.code] || 0))}" style="width:100px;"></td>
        <td class="num"><input type="number" min="0" step="10" data-fb-price="${H(b.code)}" value="${H(b.base_price_per_kg ?? "")}" placeholder="wajib" style="width:90px;"></td>
        <td class="num"><input type="number" min="0" max="94" step="0.5" data-fb-mc="${H(b.code)}" placeholder="${H(num(b.moisture_typ_pct, 0))}" style="width:70px;"></td>
        <td class="num"><input type="number" min="0" max="100" step="5" data-fb-max="${H(b.code)}" value="100" style="width:70px;"></td></tr>`).join("")}</tbody></table>
        ${fbPresets.drying_cost_rp_per_kg_water == null ? `<p class="kpi-lbl">⚠️ Biaya pengeringan belum diisi di menu Parameter — bahan basah (ampas tebu) akan tampak lebih murah dari kenyataan.</p>` : ""}`;
      $("fx-fb-go").onclick = runFuelBlend;
    } catch (e) { $("fx-fb-feeds").innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  function fbFeeds() {
    return [...document.querySelectorAll("[data-fb-use]:checked")].map(cb => {
      const c = cb.dataset.fbUse, v = (k) => document.querySelector(`[data-fb-${k}="${CSS.escape(c)}"]`).value;
      return { code: c, available_kg: Number(v("kg")) || 0, price_per_kg: v("price") === "" ? null : Number(v("price")),
               moisture_pct: v("mc") === "" ? null : Number(v("mc")), max_share_pct: Number(v("max")) || 100 };
    });
  }

  async function runFuelBlend() {
    const out = $("fx-fb-out"), feeds = fbFeeds();
    if (!feeds.length) return showToast("Pilih minimal satu komoditas.", "⚠️");
    return withBusy($("fx-fb-go"), async () => {
      try {
        const r = await api("/api/v1/factory/fuel-blend/optimize", { body: { preset: $("fx-fb-preset").value,
          target_kg: Number($("fx-fb-target").value), lhv_ar_min_kcal: Number($("fx-fb-kcal").value) || null, feeds } });
        if (!r.feasible) {
          out.innerHTML = `<div class="banner banner-error" role="alert">⛔ ${H(r.message)}</div>`;
          $("fx-fb-sliders").innerHTML = "";
          return;
        }
        const card = r.feasibility_card;
        out.innerHTML = `<div class="kpi-row">
            <div class="kpi-tile"><div class="kpi-lbl">Kelayakan</div><div class="kpi-val"><span class="badge ${VERDICT_BADGE[card.verdict]}">${H(card.verdict)}</span></div><div class="kpi-lbl">Terak: ${H(card.slagging)}</div></div>
            <div class="kpi-tile"><div class="kpi-lbl">Biaya total</div><div class="kpi-val">${rp(r.cost.total_rp)}</div><div class="kpi-lbl">${rp(r.cost.rp_per_kg_product)}/kg produk</div></div>
            <div class="kpi-tile"><div class="kpi-lbl">Kalori</div><div class="kpi-val">${num(r.properties.gcv_ar_kcal_kg, 0)}</div><div class="kpi-lbl">kcal/kg GCV ar · NCV ${num(r.properties.lhv_ar_kcal_kg, 0)}</div></div>
            <div class="kpi-tile"><div class="kpi-lbl">Indeks alkali</div><div class="kpi-val">${num(r.properties.indices.alkali_index, 3)}</div><div class="kpi-lbl">kg/GJ · ${H(r.properties.risk_levels.alkali_index)}</div></div></div>
          <div class="table-scroll"><table class="data-table"><thead><tr><th>Komoditas</th><th class="num">Porsi (% bk)</th><th class="num">Pakai (kg basah)</th>
            <th class="num">Air diuapkan (kg)</th><th class="num">Biaya</th></tr></thead><tbody>${r.composition.map(c => `<tr><td>${H(c.name)}</td>
            <td class="num"><b>${num(c.share_dry_pct, 1)}</b></td><td class="num">${num(c.wet_kg_to_use, 0)}</td><td class="num">${num(c.water_to_evaporate_kg, 0)}</td>
            <td class="num">${rp(c.purchase_rp + c.drying_rp)}</td></tr>`).join("")}</tbody></table></div>
          <ul class="kpi-lbl">${card.checks.map(c => `<li>${c.ok ? "✅" : "⛔"} ${H(c.check)}: ${H(c.detail)}</li>`).join("")}</ul>
          ${(r.notes || []).map(n => `<p class="kpi-lbl">ℹ️ ${H(n)}</p>`).join("")}
          <p class="kpi-lbl">${H(card.recommendation)}</p>`;
        fbRenderProps(r.properties, r.spec);
        fbSliders(r.composition, r.spec);
      } catch (e) { out.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
    }, "⏳");
  }

  function fbRenderProps(p, spec) {
    const warn = $("fx-fb-warn") || Object.assign(document.createElement("div"), { id: "fx-fb-warn" });
    $("fx-fb-sliders").before(warn);
    warn.innerHTML = `<p><span class="badge ${VERDICT_BADGE[p.slagging_verdict]}">Risiko terak: ${H(p.slagging_verdict)}</span>
      B/A ${num(p.indices.base_acid, 3)} · Rs ${num(p.indices.slagging_rs, 3)} · Fu ${num(p.indices.fouling_fu, 2)} · Cl ${num(p.chlorine_pct_db, 3)} %</p>
      ${p.warnings.map(w => `<div class="banner ${/Tinggi Terak/.test(w) ? "banner-error" : "banner-warning"}" role="alert">⚠️ ${H(w)}</div>`).join("")}`;
    if (typeof Chart === "undefined" || !$("fx-fb-radar")) return;
    const ratio = (v, lim) => (v == null || !lim ? 0 : Math.min(2, v / lim));
    const kcalTarget = spec.lhv_ar_min_mj ? spec.lhv_ar_min_mj * 238.846 : null;
    const cal = spec.calorific_basis === "gcv_ar" ? p.gcv_ar_kcal_kg : p.lhv_ar_kcal_kg;
    const data = [ratio(p.ash_pct_db, spec.ash_max_pct), ratio(p.chlorine_pct_db, spec.cl_max_pct), ratio(p.indices.alkali_index, 0.34),
                  ratio(p.indices.base_acid, 0.4), ratio(p.sulfur_pct_db, spec.s_max_pct), kcalTarget ? Math.min(2, kcalTarget / cal) : 0];
    const cfg = { type: "radar", data: { labels: ["Abu", "Klorin", "Indeks alkali", "B/A", "Sulfur", "Kekurangan kalori"],
      datasets: [{ label: "Campuran (÷ batas)", data, fill: true }, { label: "Batas = 1", data: data.map(() => 1), fill: false, borderDash: [4, 4] }] },
      options: { scales: { r: { min: 0, max: 2, ticks: { stepSize: 0.5 } } }, plugins: { legend: { position: "bottom" } } } };
    if (fbRadar) { fbRadar.data = cfg.data; fbRadar.update(); } else fbRadar = new Chart($("fx-fb-radar"), cfg);
  }

  function fbSliders(comp, spec) {
    $("fx-fb-sliders").innerHTML = `<h4>🎚️ Uji campuran manual (porsi % basis kering)</h4>` + comp.map(c => `
      <label style="display:grid; grid-template-columns:160px 1fr 60px; gap:8px; align-items:center;">${H(c.name)}
        <input type="range" min="0" max="100" step="1" value="${Math.round(c.share_dry_pct)}" data-fb-slide="${H(c.code)}" aria-label="Porsi ${H(c.name)}">
        <span data-fb-val="${H(c.code)}">${Math.round(c.share_dry_pct)}%</span></label>`).join("");
    $("fx-fb-sliders").oninput = (e) => {
      const el = e.target.closest("[data-fb-slide]");
      if (!el) return;
      $("fx-fb-sliders").querySelector(`[data-fb-val="${CSS.escape(el.dataset.fbSlide)}"]`).textContent = `${el.value}%`;
      clearTimeout(fbTimer);
      fbTimer = setTimeout(async () => {
        const shares = Object.fromEntries([...document.querySelectorAll("[data-fb-slide]")].map(s => [s.dataset.fbSlide, Number(s.value)]));
        try {
          const p = await api("/api/v1/factory/fuel-blend/evaluate", { body: { feeds: fbFeeds().filter(f => f.code in shares),
            shares_pct: shares, product_moisture_pct: spec.product_moisture_pct } });
          fbRenderProps(p, spec);
        } catch (err) { showToast(err.message, "❌"); }
      }, 300);
    };
  }

  // ---------------------------------------------------------------- Prototipe 2: energi riil & rute konversi
  function initConversion() {
    if (!$("fx-cv-com")) return;
    $("fx-cv-com").innerHTML = bmCache.map(b => `<option value="${H(b.code)}">${H(b.name)}</option>`).join("");
    $("fx-cv-go").onclick = runConversion;
  }

  async function runConversion() {
    const out = $("fx-cv-out");
    return withBusy($("fx-cv-go"), async () => {
      try {
        const r = await api("/api/v1/factory/conversion/analyse", { body: { code: $("fx-cv-com").value,
          ton_per_month: Number($("fx-cv-t").value), moisture_pct: numOrNull($("fx-cv-mc").value),
          distance_to_pltu_km: numOrNull($("fx-cv-km").value) } });
        const e = r.energy, el = e.electricity_mwh_per_month, co2 = e.co2_avoided_t_per_month;
        out.innerHTML = `<div class="kpi-row">
            <div class="kpi-tile"><div class="kpi-lbl">LHV as-received</div><div class="kpi-val">${num(e.lhv_ar_mj_kg, 2)}</div><div class="kpi-lbl">MJ/kg · ${num(e.lhv_ar_kcal_kg, 0)} kcal/kg (bk ${num(e.lhv_db_mj_kg, 1)})</div></div>
            <div class="kpi-tile"><div class="kpi-lbl">Energi termal</div><div class="kpi-val">${num(e.thermal_gj_per_month, 0)}</div><div class="kpi-lbl">GJ/bulan</div></div>
            <div class="kpi-tile"><div class="kpi-lbl">Listrik (η 22 % · 28 % · co-firing 36 %)</div><div class="kpi-val">${num(el.turbin_uap_kecil, 0)}</div>
              <div class="kpi-lbl">· ${num(el.terintegrasi, 0)} · ${num(el.cofiring_pltu, 0)} MWh/bulan</div></div>
            <div class="kpi-tile"><div class="kpi-lbl">CO₂ dihindari (η 22 %)</div><div class="kpi-val">${num(co2.turbin_uap_kecil, 0)}</div><div class="kpi-lbl">t/bulan · EF ${num(e.grid_ef_t_per_mwh, 2)} t/MWh</div></div></div>
          <div class="banner banner-info" role="note">🧭 Rute terbaik: <b>${H(r.decision.label)}</b></div>
          <ol class="kpi-lbl">${r.decision.path.map(p => `<li>${H(p.question)} → <b>${H(p.answer)}</b></li>`).join("")}</ol>
          ${r.warnings.map(w => `<div class="banner banner-warning" role="alert">⚠️ ${H(w)}</div>`).join("")}
          <div class="table-scroll"><table class="data-table"><thead><tr><th>Rute</th><th>Layak</th><th>Syarat</th><th class="num">Hasil / bulan</th></tr></thead>
          <tbody>${r.routes.map(rt => `<tr><td><b>${H(rt.label)}</b></td><td>${rt.feasible ? "✅" : "—"}</td>
            <td class="kpi-lbl">${rt.checks.map(c => `${c.ok ? "✅" : "⛔"} ${H(c.check)}: ${H(c.detail)}`).join("<br>")}</td>
            <td class="num">${rt.electricity_mwh_per_month != null ? `${num(rt.electricity_mwh_per_month, 0)} MWh<br><span class="kpi-lbl">${num(rt.co2_avoided_t_per_month, 0)} tCO₂ · pengering ${num(rt.drying_gj_per_month, 0)} GJ</span>`
              : rt.biochar_t_per_month != null ? `${num(rt.biochar_t_per_month, 1)} t ${H(rt.product)}${rt.bio_silica_potential_t_per_month ? `<br><span class="kpi-lbl">bio-silika ${num(rt.bio_silica_potential_t_per_month, 1)} t</span>` : ""}`
              : `${num(rt.process_heat_gj_per_month, 0)} GJ panas`}</td></tr>`).join("")}</tbody></table></div>
          <p class="kpi-lbl">${H(r.computation_details.note)}</p>`;
      } catch (err) { out.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(err.message)}</div>`; }
    }, "⏳");
  }

  // ---------------------------------------------------------------- Prototipe 4: Optimasi Multi-Biomassa ke Produk Akhir
  let optConfig = null;
  const GRADE_BADGE = { S: "badge-green", A: "badge-green", B: "badge-blue", C: "badge-amber", D: "badge-red" };
  const PROD_ICONS = { bio_pellet: "🪵", briket: "⬛", biochar: "🔋", bio_silika: "🧪" };

  async function initProductOptimization() {
    if (!$("fx-opt-card")) return;
    try {
      optConfig = await api("/api/v1/factory/optimization/config");
      if (!bmCache.length) bmCache = await api("/api/v1/biomass");

      const tabEval = $("fx-opt-tab-eval"), tabAlloc = $("fx-opt-tab-alloc");
      const viewEval = $("fx-opt-view-eval"), viewAlloc = $("fx-opt-view-alloc");
      if (tabEval && tabAlloc && viewEval && viewAlloc) {
        tabEval.onclick = () => {
          tabEval.className = "btn btn-primary btn-sm"; tabAlloc.className = "btn btn-secondary btn-sm";
          viewEval.style.display = "block"; viewAlloc.style.display = "none";
        };
        tabAlloc.onclick = () => {
          tabAlloc.className = "btn btn-primary btn-sm"; tabEval.className = "btn btn-secondary btn-sm";
          viewAlloc.style.display = "block"; viewEval.style.display = "none";
        };
      }

      if ($("fx-opt-com")) {
        $("fx-opt-com").innerHTML = bmCache.map(b => `<option value="${H(b.code)}">${H(b.name)}</option>`).join("");
        $("fx-opt-com").onchange = () => {
          const item = bmCache.find(x => x.code === $("fx-opt-com").value);
          if (item) {
            if (item.moisture_typ_pct != null) $("fx-opt-mc").value = item.moisture_typ_pct;
            if (item.base_price_per_kg != null) $("fx-opt-price").value = item.base_price_per_kg;
          }
        };
        const first = bmCache[0];
        if (first) {
          if (first.moisture_typ_pct != null) $("fx-opt-mc").value = first.moisture_typ_pct;
          if (first.base_price_per_kg != null) $("fx-opt-price").value = first.base_price_per_kg;
        }
      }
      if ($("fx-opt-eval-go")) $("fx-opt-eval-go").onclick = runProductEvaluation;

      const capsBox = $("fx-opt-caps-inputs");
      if (capsBox && optConfig && optConfig.capacities) {
        capsBox.innerHTML = Object.entries(optConfig.capacities).map(([p, cap]) => {
          const pInfo = (optConfig.products || {})[p] || {};
          return `<div style="display:inline-flex; align-items:center; gap:4px; margin-right:8px;">
            <span>${PROD_ICONS[p] || ""} <b>${H(pInfo.name || p)}</b>:</span>
            <input type="number" min="0" step="5000" id="fx-opt-cap-${H(p)}" value="${Number(cap)}" style="width:90px;" class="btn btn-secondary btn-sm"> kg
          </div>`;
        }).join("");
      }

      renderAllocStocks();
      if ($("fx-opt-alloc-go")) $("fx-opt-alloc-go").onclick = runProductAllocation;

      runProductEvaluation();
    } catch (e) {
      console.warn("Product optimization init error:", e);
    }
  }

  function renderAllocStocks() {
    if (window.FactoryPyrolysisCalc) return window.FactoryPyrolysisCalc.renderAllocStocks(bmCache, H, num);
  }

  function getSelectedAllocStocks() {
    if (window.FactoryPyrolysisCalc) return window.FactoryPyrolysisCalc.getSelectedAllocStocks();
    return [];
  }

  async function runProductEvaluation() {
    if (window.FactoryPyrolysisCalc) return window.FactoryPyrolysisCalc.runProductEvaluation(H, num, rp);
  }

  async function runProductAllocation() {
    if (window.FactoryPyrolysisCalc) return window.FactoryPyrolysisCalc.runProductAllocation(optConfig, H, num, rp);
  }


  // ---------------------------------------------------------------- Prototipe 3: SEC/IKE & anomali
  let secChart = null;
  const today = () => new Date().toISOString().slice(0, 10);

  async function initSec() {
    if (!$("fx-sec-sel")) return;
    if ($("fx-sec-date")) $("fx-sec-date").value = today();
    $("fx-sec-feed").innerHTML = `<option value="">—</option>` + bmCache.map(b => `<option value="${H(b.code)}">${H(b.name)}</option>`).join("");
    await loadSecFacilities();
    if ($("fx-sec-go")) $("fx-sec-go").onclick = runSec;
    if ($("fx-sec-add")) $("fx-sec-add").onclick = addSecLog;
    if ($("fx-sec-import")) $("fx-sec-import").onclick = importSecCsv;
  }

  async function loadSecFacilities() {
    try {
      const f = await api("/api/v1/factory/energy/ops-facilities");
      $("fx-sec-sel").innerHTML = f.length ? f.map(x => `<option value="${H(x.facility)}">${H(x.facility)} (${Number(x.logs)} log)</option>`).join("")
        : `<option value="">Belum ada log</option>`;
    } catch { /* auditor tanpa data */ }
  }

  async function postSecLogs(facility, logs) {
    const r = await apiMutation("/api/v1/factory/energy/ops-logs", { facility, logs }, `Log energi ${logs.length}`);
    showToast(r.queued ? "Offline: log disimpan & dikirim saat ada sinyal." : `Tersimpan ${r.created} log${r.skipped.length ? ` · ${r.skipped.length} sudah ada` : ""}`, "📈");
    loadSecFacilities();
  }

  function addSecLog() {
    const v = (id) => numOrNull($(id).value);
    if (!v("fx-sec-kwh") || !v("fx-sec-h") || !v("fx-sec-t")) return showToast("Isi kWh, jam operasi dan ton produk.", "⚠️");
    return postSecLogs($("fx-sec-fac").value.trim(), [{ log_date: $("fx-sec-date").value, kwh_total: v("fx-sec-kwh"),
      kwh_hammer_mill: v("fx-sec-hm"), diesel_l: v("fx-sec-dsl") || 0, biomass_fuel_kg: v("fx-sec-bio") || 0,
      operating_hours: v("fx-sec-h"), product_ton: v("fx-sec-t"), feed_moisture_pct: v("fx-sec-mc"),
      rated_capacity_t_h: v("fx-sec-cap"), client_event_id: `${$("fx-sec-fac").value.trim()}|${$("fx-sec-date").value}|H` }]);
  }

  function importSecCsv() {
    const fac = $("fx-sec-fac").value.trim(), logs = [];
    for (const line of $("fx-sec-csv").value.split(/\r?\n/).map(l => l.trim()).filter(Boolean)) {
      const c = line.split(/[;,]/).map(x => x.trim());
      if (!/^\d{4}-\d{2}-\d{2}$/.test(c[0])) continue;                 // lewati header / baris rusak
      const n = (i) => (c[i] === undefined || c[i] === "" ? null : Number(c[i]));
      logs.push({ log_date: c[0], kwh_total: n(1), kwh_hammer_mill: n(2), diesel_l: n(3) || 0, biomass_fuel_kg: n(4) || 0,
                  operating_hours: n(5), product_ton: n(6), feed_moisture_pct: n(7), rated_capacity_t_h: n(8),
                  client_event_id: `${fac}|${c[0]}|H` });
    }
    if (!logs.length) return showToast("Tidak ada baris CSV yang valid.", "⚠️");
    return postSecLogs(fac, logs);
  }

  async function runSec() {
    const out = $("fx-sec-out"), fac = $("fx-sec-sel").value;
    if (!fac) return showToast("Belum ada fasilitas dengan log.", "⚠️");
    return withBusy($("fx-sec-go"), async () => {
      try {
        const qs = new URLSearchParams({ facility: fac });
        if ($("fx-sec-idle").value) qs.set("idle_kw", $("fx-sec-idle").value);
        if ($("fx-sec-feed").value) qs.set("feed_code", $("fx-sec-feed").value);
        const r = await api(`/api/v1/factory/energy/ops-analysis?${qs}`);
        const b = r.baseline, sm = r.summary;
        out.innerHTML = `<div class="kpi-row">
            <div class="kpi-tile"><div class="kpi-lbl">SEC mentah (median)</div><div class="kpi-val">${num(sm.sec_raw_mj_per_t_median, 0)}</div><div class="kpi-lbl">MJ/t produk</div></div>
            <div class="kpi-tile"><div class="kpi-lbl">EnPI terakhir</div><div class="kpi-val">${num(sm.enpi_last, 3)}</div><div class="kpi-lbl">1 = sesuai baseline</div></div>
            <div class="kpi-tile ${sm.alerts_action ? "kpi-danger" : sm.alerts_warning ? "kpi-warn" : ""}"><div class="kpi-lbl">Alarm</div><div class="kpi-val">${Number(sm.alerts_action)} · ${Number(sm.alerts_warning)}</div><div class="kpi-lbl">aksi · peringatan</div></div>
            <div class="kpi-tile"><div class="kpi-lbl">Energi akibat bahan basah</div><div class="kpi-val">${num(sm.wet_feed_mj_total / 1000, 1)}</div><div class="kpi-lbl">GJ (dapat dikendalikan di hulu)</div></div></div>
          <p class="kpi-lbl">Baseline: ${H(b.model)} · β jam ${num(b.beta_mj_per_hour, 0)} MJ/jam (${H(b.fixed_load_basis)}) · β ton ${num(b.beta_mj_per_ton, 0)} MJ/t · R² ${num(b.r2, 2)} · ${Number(b.n)} log acuan</p>
          ${b.notes.map(n => `<div class="banner banner-warning" role="note">⚠️ ${H(n)}</div>`).join("")}
          ${r.alerts.length ? `<div class="table-scroll"><table class="data-table"><thead><tr><th>Log</th><th>Tingkat</th><th>Indikasi</th></tr></thead><tbody>
            ${r.alerts.map(a => `<tr><td>${H(a.label)}</td><td><span class="badge ${a.level === "aksi" ? "badge-red" : a.level === "peringatan" ? "badge-amber" : "badge-blue"}">${H(a.level)}</span></td>
              <td class="kpi-lbl">${H(a.detail)}</td></tr>`).join("")}</tbody></table></div>` : `<p class="kpi-lbl">✅ Tidak ada anomali.</p>`}
          <h4>🧭 Rekomendasi audit energi (ISO 50001)</h4>
          ${r.recommendations.map(x => `<div class="card" style="padding:10px; margin:6px 0;"><b>${H(x.title)}</b> <span class="kpi-lbl">· ${H(x.iso50001)}</span>
            <p style="margin:4px 0;">${H(x.action)}</p><span class="kpi-lbl">KPI: ${H(x.kpi)}</span></div>`).join("")}`;
        if (typeof Chart === "undefined") return;
        const labels = r.rows.map(x => x.label);
        const cfg = { type: "line", data: { labels, datasets: [
            { label: "Residual energi (%)", data: r.rows.map(x => x.residual_pct), yAxisID: "y", pointRadius: r.rows.map(x => (x.alert ? 5 : 2)) },
            { label: "Batas peringatan +2σ", data: r.rows.map(x => x.band_warn_pct), yAxisID: "y", borderDash: [4, 4], pointRadius: 0 },
            { label: "Batas aksi +3σ", data: r.rows.map(x => x.band_action_pct), yAxisID: "y", borderDash: [8, 4], pointRadius: 0 },
            { label: "SEC mentah (MJ/t)", data: r.rows.map(x => x.sec_mj_per_t), yAxisID: "y2", pointRadius: 0 },
            { label: "SEC ternormalisasi (MJ/t)", data: r.rows.map(x => x.sec_expected_mj_per_t), yAxisID: "y2", pointRadius: 0, borderDash: [2, 2] }] },
          options: { maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
            scales: { y: { title: { display: true, text: "% di atas model" } }, y2: { position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "MJ/t" } } },
            plugins: { legend: { position: "bottom" } } } };
        if (secChart) { secChart.data = cfg.data; secChart.update(); } else secChart = new Chart($("fx-sec-chart"), cfg);
      } catch (e) { out.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
    }, "⏳");
  }

  // ---------------------------------------------------------------- klaim removal karbon (F11)
  const CC_BADGE = { diajukan: "badge-amber", diverifikasi: "badge-green", ditolak: "badge-red" };
  let ccPhotoUrl = null;

  async function ccBody() {
    const f = $("fx-cc-photo").files[0];
    if (!ccPhotoUrl && f) {                                     // unggah sekali; dipakai ulang saat ajukan
      const blob = window.BiochainImage ? await BiochainImage.compress(f) : f;
      ccPhotoUrl = (await photoUpload(blob)).url;
    }
    return { from: $("fx-cc-from").value, to: $("fx-cc-to").value, lab_c_org_pct: Number($("fx-cc-corg").value),
             lab_h_corg_ratio: Number($("fx-cc-hc").value), lab_name: $("fx-cc-lab").value.trim(),
             lab_report_no: $("fx-cc-no").value.trim(), lab_report_url: ccPhotoUrl };
  }

  async function ccSubmit(e) {
    e.preventDefault();
    const btn = e.submitter || $("fx-cc-form").querySelector("[data-mode=preview]");
    const mode = btn.dataset.mode;
    const box = $("fx-cc-preview");
    return withBusy(btn, async () => {
      try {
        const body = await ccBody();
        if (mode === "submit") {
          const c = await api("/api/v1/factory/carbon-claims", { body });
          showToast(`Klaim ${c.code} diajukan · ${num(c.net_removal_tco2e, 3)} tCO₂e menunggu auditor`, "🧾");
          $("fx-cc-form").reset(); ccPhotoUrl = null; box.innerHTML = ""; $("fx-cc-submit").disabled = true;
          return loadClaims();
        }
        const p = await api("/api/v1/factory/carbon-claims/preview", { body });
        $("fx-cc-submit").disabled = p.blocking.length > 0;
        box.innerHTML = `<div class="kpi-row">
            <div class="kpi-tile"><div class="kpi-lbl">Biochar sampai lahan</div><div class="kpi-val">${num(p.end_use_kg, 0)}</div><div class="kpi-lbl">kg · ${p.redemption_count} serah-terima</div></div>
            <div class="kpi-tile"><div class="kpi-lbl">Removal bruto</div><div class="kpi-val">${num(p.carbon_tco2e.biochar_sequestration, 3)}</div><div class="kpi-lbl">tCO₂e (C-org lab)</div></div>
            <div class="kpi-tile"><div class="kpi-lbl">Removal bersih</div><div class="kpi-val">${num(p.net_tco2e, 3)}</div><div class="kpi-lbl">tCO₂e setelah emisi &amp; potongan</div></div></div>
          ${p.blocking.map(b => `<div class="banner banner-error" role="alert">⛔ ${H(b)}</div>`).join("")}
          ${p.warnings.map(w => `<div class="banner banner-warning" role="note">⚠️ ${H(w)}</div>`).join("")}
          ${p.blocking.length ? "" : `<p class="kpi-lbl">Siap diajukan. Setelah diajukan, angka dibekukan &amp; serah-terima dikunci.</p>`}`;
      } catch (err) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(err.message)}</div>`; }
    }, "⏳");
  }

  async function loadClaims() {
    const box = $("fx-cc");
    if (!box) return;
    try {
      const rows = await api(role() === "auditor" ? "/api/v1/auditor/carbon-claims" : "/api/v1/factory/carbon-claims");
      box.innerHTML = rows.length ? `<div class="table-scroll"><table class="data-table"><thead><tr><th>Klaim</th><th>Periode</th>
          <th class="num">Biochar ke lahan</th><th class="num">Removal bersih</th><th>Lab</th><th>Status</th></tr></thead><tbody>${rows.map(c => `<tr>
          <td><b>${H(c.code)}</b><br><span class="kpi-lbl">${H(c.submitted_by)} · ${H(c.submitted_at.slice(0, 10))}</span></td>
          <td>${H(c.period_start.slice(0, 7))} – ${H(c.period_end.slice(0, 10))}</td>
          <td class="num">${num(c.end_use_kg, 0)} kg<br><span class="kpi-lbl">${Number(c.redemption_count)} serah-terima</span></td>
          <td class="num"><b>${num(c.net_removal_tco2e, 3)}</b> tCO₂e</td>
          <td class="kpi-lbl">C-org ${num(c.lab_c_org_pct, 1)}% · H/C ${num(c.lab_h_corg_ratio, 2)}<br>${H(c.lab_name)} · ${H(c.lab_report_no)}
            <a href="${H(c.lab_report_url)}" target="_blank" rel="noopener" aria-label="Laporan lab ${H(c.code)}">📄</a></td>
          <td><span class="badge ${CC_BADGE[c.status] || "badge-gray"}" title="${H(c.status_label)}">${H(c.status)}</span>
            ${c.integrity.ok ? "" : `<br><span class="badge badge-red" title="Snapshot/kunci berubah setelah diajukan">integritas gagal</span>`}
            ${c.decision_note ? `<br><span class="kpi-lbl">${H(c.verified_by)}: ${H(c.decision_note)}</span>` : ""}
            ${role() === "auditor" && c.status === "diajukan" ? `<div style="display:flex; gap:4px; margin-top:4px;">
              <button type="button" class="btn btn-primary btn-sm" data-fx-claim="${Number(c.id)}" data-to="diverifikasi" ${c.integrity.ok ? "" : "disabled"}>✅ Verifikasi</button>
              <button type="button" class="btn btn-secondary btn-sm" data-fx-claim="${Number(c.id)}" data-to="ditolak">✖ Tolak</button></div>` : ""}
          </td></tr>`).join("")}</tbody></table></div>
          <p class="kpi-lbl">Celah metodologi tiap klaim tampil saat pratinjau dan tersimpan di snapshot (SHA-256).</p>`
        : emptyState("🧾", "Belum ada klaim", "Klaim dibuat pabrik setelah ada serah-terima biochar ke lahan dan hasil lab C-org.");
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  function askClaimNote(to) {
    return new Promise(resolve => {
      const d = document.createElement("dialog");
      d.className = "ui-confirm";
      d.innerHTML = `<form method="dialog"><h3>${to === "diverifikasi" ? "Verifikasi klaim" : "Tolak klaim"}</h3>
        <p class="ui-confirm-body">${to === "diverifikasi" ? "Tulis apa yang Anda periksa (laporan lab, foto serah-terima, suhu batch)."
          : "Tulis alasan penolakan. Serah-terima dilepas dan pabrik bisa mengajukan klaim perbaikan."}</p>
        <div class="form-group"><label for="fx-cc-note">Catatan auditor</label>
          <textarea id="fx-cc-note" required minlength="10" maxlength="2000" rows="3"></textarea></div>
        <div class="ui-confirm-actions"><button value="no" class="btn btn-secondary" formnovalidate>Batal</button>
          <button value="yes" class="btn btn-primary">Simpan putusan</button></div></form>`;
      document.body.appendChild(d);
      d.addEventListener("close", () => { resolve(d.returnValue === "yes" ? d.querySelector("#fx-cc-note").value.trim() : null); d.remove(); });
      d.showModal();
    });
  }

  async function decideClaim(id, to) {
    const note = await askClaimNote(to);
    if (!note) return;
    try {
      const c = await api(`/api/v1/auditor/carbon-claims/${id}/decision`, { body: { decision: to, note } });
      showToast(`${c.code}: ${c.status}`, to === "diverifikasi" ? "✅" : "✖"); loadClaims();
    } catch (e) { showToast(e.message, "❌"); }
  }

  // ---------------------------------------------------------------- sambungan ke dashboard
  window.renderFactoryExtras = function (container) {
    if (!container || !["pabrik", "admin", "auditor"].includes(role())) return;
    container.insertAdjacentHTML("beforeend", HTML());
    if ($("fx-eff-go")) $("fx-eff-go").onclick = loadEfficiency;
    if ($("fx-esg-go")) $("fx-esg-go").onclick = loadEsg;
    if ($("fx-esg-csv")) $("fx-esg-csv").onclick = downloadEsgCsv;
    if ($("fx-esg-print")) $("fx-esg-print").onclick = () => { document.body.classList.add("print-esg"); window.print(); };
    window.addEventListener("afterprint", () => document.body.classList.remove("print-esg"), { once: false });
    if (canWrite()) {
      loadRedemptions();
      loadBiocharDispatches();
      if ($("btn-fx-dispatch-biochar")) $("btn-fx-dispatch-biochar").onclick = openBiocharDispatchModal;
    }
    if ($("fx-cc-form")) {
      $("fx-cc-form").addEventListener("submit", ccSubmit);
      $("fx-cc-form").addEventListener("input", () => { $("fx-cc-submit").disabled = true; });   // ubah isian → pratinjau ulang
      $("fx-cc-photo").addEventListener("change", () => { ccPhotoUrl = null; });
    }
    loadClaims();
    loadBiomass().then(() => { initFuelBlend(); initConversion(); initSec(); initProductOptimization(); }); loadAsh();
    if ($("fx-grp-new")) $("fx-grp-new").onclick = newGroup;
    if ($("fx-ash-new")) $("fx-ash-new").onclick = newAsh;
    loadCharges();
    loadEfficiency(); loadEsg();
  };

  document.addEventListener("click", (e) => {
    const h = e.target.closest("[data-fx-handover]");
    if (h) {
      const id = Number(h.dataset.fxHandover), kg = Number(($(`fx-br-kg-${id}`) || {}).value) || null;
      return withBusy(h, async () => {
        try {
          const r = await api(`/api/v1/factory/biochar-redemptions/${id}/handover`, { body: { kg } });
          showToast(`Diserahkan ${num(r.kg, 1)} kg · saldo petani ${num(r.balance_kg, 1)} kg`, "♻️");
          loadRedemptions(); loadEfficiency();
        } catch (err) { showToast(err.message, "❌"); }
      }, "⏳");
    }
    const newBmBtn = e.target.closest("#btn-add-biomass");
    if (newBmBtn) return newBiomass();
    const bm = e.target.closest("[data-fx-bm]");
    if (bm) return editBiomass(bm.dataset.fxBm);
    for (const [attr, fn] of [["fxAshLab", ashLab], ["fxAshAlloc", ashAllocate], ["fxAshHand", ashHandover], ["fxAshDispose", ashDispose]]) {
      const el = e.target.closest(`[data-${attr.replace(/[A-Z]/g, c => "-" + c.toLowerCase())}]`);
      if (el) return fn(Number(el.dataset[attr]));
    }
    const cc = e.target.closest("[data-fx-claim]");
    if (cc) return decideClaim(Number(cc.dataset.fxClaim), cc.dataset.to);
    const wv = e.target.closest("[data-fx-waive]");
    if (wv) return waiveCharge(Number(wv.dataset.fxWaive));
    const a = e.target.closest("[data-fx-adopt]");
    if (a) return actionDialog(a.dataset.fxAdopt);
    const s = e.target.closest("[data-fx-status]");
    if (s) return setStatus(Number(s.dataset.fxStatus), s.dataset.to);
    const dspQr = e.target.closest("[data-fx-dsp-qr]");
    if (dspQr) return openModal("Surat Jalan Biochar", dspQr.dataset.fxDspQr, `${dspQr.dataset.fxDspCode} · ${dspQr.dataset.fxDspKg} kg biochar`);
  });
})();
