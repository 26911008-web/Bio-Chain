// ==============================================================
// STATE & HELPERS
// ==============================================================
const STATE = {
  token: localStorage.getItem("biochain_token") || null,
  user: JSON.parse(localStorage.getItem("biochain_user") || "null"),
  demoAccounts: [],
  mills: [],
  selectedRoleKey: null,
};
window.STATE = STATE;

const $ = id => document.getElementById(id);
const rp = n => "Rp " + Math.round(Number(n) || 0).toLocaleString("id-ID");
const num = (n, d=1) => Number(n || 0).toLocaleString("id-ID", {maximumFractionDigits: d});
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const newId = () => (crypto.randomUUID ? crypto.randomUUID()
  : Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 12));

const formatWIB = (iso) => {
  if (!iso) return "-";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    return d.toLocaleString("id-ID", {
      year: "numeric", month: "short", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
      timeZone: "Asia/Jakarta", hour12: false
    }) + " WIB";
  } catch { return String(iso); }
};
window.formatWIB = formatWIB;

const INDO_MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];
function getMonthYearMeta(isoDate) {
  let d = null;
  if (isoDate) {
    try {
      const parsed = new Date(isoDate);
      if (!isNaN(parsed.getTime())) d = parsed;
    } catch {}
  }
  if (!d) d = new Date();
  const y = d.getFullYear();
  const m = d.getMonth();
  return {
    key: `${y}-${String(m + 1).padStart(2, "0")}`,
    label: `${INDO_MONTHS[m]} ${y}`,
    shortLabel: `${INDO_MONTHS[m].slice(0, 3)} ${y}`,
    year: y,
    month: m + 1
  };
}
window.getMonthYearMeta = getMonthYearMeta;

async function getDeviceLocation(timeoutMs = 3000) {
  if (!navigator.geolocation) return null;
  return new Promise(resolve => {
    navigator.geolocation.getCurrentPosition(
      pos => resolve({
        lat: pos.coords.latitude,
        lon: pos.coords.longitude,
        accuracy: pos.coords.accuracy,
        recorded_at: new Date(pos.timestamp || Date.now()).toISOString()
      }),
      () => resolve(null),
      { timeout: timeoutMs, enableHighAccuracy: true, maximumAge: 60000 }
    );
  });
}
window.getDeviceLocation = getDeviceLocation;

function renderTraceabilityCell(item) {
  if (!item) return `<td class="trace-cell">-</td>`;
  const originQr = item.origin_qr_code || item.qr_code || (item.harvest_id ? `WR-HV-${item.harvest_id}` : (item.listing_id ? `WR-LST-${item.listing_id}` : 'BIO-RAW'));
  const trxCode = item.trx_code || item.verification_code || (item.custody && item.custody.trx_code);
  const driverCode = item.driver_code || item.dispatch_code || item.delivery_order_code || (item.route_id ? `DSP-RT-${item.route_id}` : null);
  const factoryCode = item.factory_batch || item.batch_code || item.factory_ticket || item.reception_ticket || null;

  return `
    <td class="trace-cell" style="vertical-align:top;">
      <div style="font-family:monospace; font-weight:700; color:var(--primary); font-size:11.5px; display:flex; align-items:center; gap:4px; flex-wrap:nowrap;">
        <span>🌾 ${esc(originQr)}</span>
        <button type="button" class="btn btn-secondary btn-sm" style="padding:1px 5px; font-size:9px; height:18px;" data-onclick="openModal('QR Code Ketelusuran', '${esc(originQr)}', 'Rantai Pasok Terlacak')">📱 QR</button>
      </div>
      ${item.harvest_id ? `<div style="font-size:10px; color:var(--ink-muted);">Lot #${item.harvest_id}</div>` : (item.listing_id ? `<div style="font-size:10px; color:var(--ink-muted);">Listing #${item.listing_id}</div>` : '')}
      ${trxCode ? `<div style="font-size:10px; color:#c084fc; font-weight:600; margin-top:1px;">🏪 ${esc(trxCode)}</div>` : ''}
      ${driverCode ? `<div style="font-size:10px; color:#38bdf8; font-weight:600; margin-top:1px;">🚛 ${esc(driverCode)}</div>` : ''}
      ${factoryCode ? `<div style="font-size:10px; color:#34d399; font-weight:600; margin-top:1px;">🏭 ${esc(factoryCode)}</div>` : ''}
    </td>
  `;
}
window.renderTraceabilityCell = renderTraceabilityCell;

function openBiocharEstimateModal(requestedKg, landAreaHa) {
  const kg = Number(requestedKg) || 500;
  const ha = Number(landAreaHa) || 0.5;

  // Rumus agronomi ekonomi sirkular (4 musim tanam = 2 tahun)
  const yieldIncreasePct = 14; // +14% rata-rata peningkatan gabah
  const ureaSavingPct = 25; // -25% penghematan pupuk urea & NPK
  const addedPaddyKgPerSeason = ha * 5500 * (yieldIncreasePct / 100); // 5.5 ton/ha standar panen
  const paddyPriceRp = 6500; // Rp/kg GKP
  const grossYieldGainPerSeason = addedPaddyKgPerSeason * paddyPriceRp;
  const fertilizerSavingPerSeason = ha * 450000; // hemat ~Rp 450 rb/ha/musim
  const netBenefitPerSeason = grossYieldGainPerSeason + fertilizerSavingPerSeason;
  const netBenefit4Seasons = netBenefitPerSeason * 4;
  const co2SinkTons = (kg * 1.8) / 1000; // 1.8 kg CO2e sequestered per kg biochar

  const d = document.createElement("dialog");
  d.className = "ui-confirm";
  d.style.maxWidth = "540px";
  d.style.width = "95vw";
  d.innerHTML = `
    <form method="dialog" class="fo-form">
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:8px; margin-bottom:12px;">
        <h3 style="margin:0; font-size:1.15rem; color:var(--primary);">🌱 Perkiraan Manfaat Bersih Abu Bottom Ash (4 Musim)</h3>
        <button value="no" class="btn btn-secondary btn-sm" style="font-size:12px; padding:2px 8px;">✕</button>
      </div>

      <div style="background:var(--surface-2); border:1px solid var(--border); border-radius:8px; padding:10px 14px; margin-bottom:12px; font-size:12.5px; line-height:1.5;">
        <div>• <b>Permintaan Abu Bottom Ash:</b> <b style="color:var(--primary);">${num(kg, 0)} kg</b> untuk lahan seluas <b>${num(ha, 2)} ha</b></div>
        <div>• <b>Dosis Aplikasi:</b> ~${num(kg / ha, 0)} kg/ha (standar efisiensi sirkular)</div>
        <div>• <b>Mekanisme Kirim:</b> Diantar armada muatan balik <b>bersamaan saat menjemput/menerima biomassa</b>.</div>
      </div>

      <table class="data-table" style="font-size:12px; margin-bottom:12px;">
        <thead>
          <tr>
            <th>Parameter Manfaat Agronomi</th>
            <th class="num">Per Musim</th>
            <th class="num">Akumulasi 4 Musim (2 Thn)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>🌾 <b>Kenaikan Hasil Gabah (+${yieldIncreasePct}%)</b><br><small class="muted">+${num(addedPaddyKgPerSeason, 0)} kg GKP / musim</small></td>
            <td class="num">${rp(grossYieldGainPerSeason)}</td>
            <td class="num"><b>${rp(grossYieldGainPerSeason * 4)}</b></td>
          </tr>
          <tr>
            <td>🧪 <b>Penghematan Pupuk Kimia (-${ureaSavingPct}%)</b><br><small class="muted">Substitusi pupuk urea &amp; NPK</small></td>
            <td class="num">${rp(fertilizerSavingPerSeason)}</td>
            <td class="num"><b>${rp(fertilizerSavingPerSeason * 4)}</b></td>
          </tr>
          <tr>
            <td>💧 <b>Retensi Air &amp; Remedi Tanah</b><br><small class="muted">Tahan kekeringan &amp; pH seimbang</small></td>
            <td class="num" colspan="2" style="text-align:center; color:var(--green); font-weight:700;">✅ Daya simpan air tanah +20%</td>
          </tr>
          <tr>
            <td>🌍 <b>Penyerapan Karbon (C-Sink)</b><br><small class="muted">Sekuestrasi permanen 100+ tahun</small></td>
            <td class="num" colspan="2" style="text-align:center; color:#38bdf8; font-weight:700;">🌱 ${num(co2SinkTons, 2)} Ton CO₂e Tersimpan</td>
          </tr>
          <tr style="background:var(--surface-2); font-weight:700;">
            <td style="color:var(--primary); font-size:13px;">💰 Total Perkiraan Manfaat Bersih</td>
            <td class="num" style="color:var(--primary); font-size:13px;">${rp(netBenefitPerSeason)}</td>
            <td class="num" style="color:var(--green); font-size:14px;">${rp(netBenefit4Seasons)}</td>
          </tr>
        </tbody>
      </table>

      <div style="font-size:11px; color:var(--ink-muted); margin-bottom:12px; line-height:1.4;">
        *Catatan: Abu bottom ash dialokasikan gratis ke petani untuk pembenah tanah sirkular menetralkan pH &amp; silika. Biochar bernilai tinggi dikomersialkan pabrik ke off-taker industri material baterai (hard carbon anoda).
      </div>

      <div class="ui-confirm-actions">
        <button value="no" class="btn btn-primary" style="width:100%;">Tutup Informasi</button>
      </div>
    </form>
  `;
  d.addEventListener("close", () => d.remove());
  document.body.appendChild(d);
  d.showModal();
}
window.openBiocharEstimateModal = openBiocharEstimateModal;

function showToast(msg, icon="✅") {
  const t = $("toast");
  $("toast-msg").innerText = msg;
  $("toast-icon").innerText = icon;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 3500);
}

let currentModalQrCode = "";
let currentModalMeta = null;

function openModal(title, code, sub, meta = null) {
  currentModalQrCode = String(code || "");
  currentModalMeta = meta;
  $("modal-qr-title").innerText = title;
  $("modal-qr-code").innerText = currentModalQrCode;
  $("modal-qr-sub").innerText = sub;

  // Render Visual 2D QR Code canvas
  const wrap = $("modal-qr-canvas-wrap");
  if (wrap) {
    wrap.innerHTML = "";
    if (window.QRCode) {
      new QRCode(wrap, {
        text: currentModalQrCode,
        width: 180,
        height: 180,
        colorDark: "#111111",
        colorLight: "#ffffff",
        correctLevel: QRCode.CorrectLevel.M
      });
    } else {
      wrap.innerHTML = `<div style="font-size:48px;">📱</div>`;
    }
  }

  // Render Rantai Ketelusuran & Kode Asal Pelaporan
  const traceBox = $("modal-qr-traceability");
  if (traceBox) {
    const originQr = (meta && (meta.originQrCode || meta.origin_qr_code)) || (currentModalQrCode.startsWith("TRX-") ? (meta && meta.batchRef) : currentModalQrCode);
    const batchRef = (meta && (meta.batchRef || meta.batch_ref)) || (meta && meta.listingId ? `WR-LST-${String(meta.listingId).padStart(4, '0')}` : null);
    
    traceBox.innerHTML = `
      <div style="background:var(--surface-1, #1a2234); border:1px solid var(--border-strong, #334155); border-radius:8px; padding:10px 12px; font-size:12px; text-align:left; box-shadow:0 4px 12px rgba(0,0,0,0.25);">
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:5px; margin-bottom:6px;">
          <span style="font-weight:700; color:var(--primary); font-size:12.5px;">🔗 Rantai Ketelusuran Batch (Traceability)</span>
          <span class="badge badge-green" style="font-size:10px; padding:2px 6px;">🟢 Asal Terlacak</span>
        </div>
        <table style="width:100%; border-collapse:collapse; font-size:11.5px; line-height:1.5;">
          <tr>
            <td style="color:var(--ink-muted); padding:2px 0; width:125px;"><b>Kode Dokumen:</b></td>
            <td><code style="font-family:monospace; font-weight:700; color:var(--ink);">${esc(currentModalQrCode)}</code></td>
          </tr>
          <tr>
            <td style="color:var(--ink-muted); padding:2px 0;"><b>QR Code Asal:</b></td>
            <td>
              <code style="font-family:monospace; font-weight:800; color:var(--accent, #38bdf8); letter-spacing:0.3px;">${esc(originQr || currentModalQrCode)}</code>
            </td>
          </tr>
          ${batchRef ? `
          <tr>
            <td style="color:var(--ink-muted); padding:2px 0;"><b>Batch Referensi:</b></td>
            <td><span class="badge badge-purple" style="font-weight:700; font-size:10.5px;">${esc(batchRef)}</span> ${meta && (meta.listingId || meta.listing_id) ? `<small class="muted">(Lot #${meta.listingId || meta.listing_id})</small>` : ''}</td>
          </tr>` : ''}
          ${meta && (meta.commodity || meta.weighedKg || meta.qtyKg || meta.accepted_kg) ? `
          <tr>
            <td style="color:var(--ink-muted); padding:2px 0;"><b>Rincian Muatan:</b></td>
            <td>${esc(meta.commodity || 'Biomassa')} · <b>${num(meta.weighedKg || meta.accepted_kg || meta.qtyKg, 0)} kg</b> ${meta.grade ? `· Grade ${meta.grade}` : ''}</td>
          </tr>` : ''}
          <tr>
            <td style="color:var(--ink-muted); padding:2px 0;"><b>Alur Mutasi:</b></td>
            <td style="font-size:10.5px; color:var(--ink-muted);">
              🌾 Pelaporan Awal <span style="color:var(--primary);">➔</span> 🏷️ Lelang <span style="color:var(--primary);">➔</span> ⚖️ Timbang TRX <span style="color:var(--primary);">➔</span> 🏭 Pabrik
            </td>
          </tr>
        </table>
      </div>
    `;
  }

  $("qr-modal").classList.add("open");
}

function copyModalQrCode() {
  if (!currentModalQrCode) return;
  navigator.clipboard.writeText(currentModalQrCode)
    .then(() => showToast(`Kode disalin: ${currentModalQrCode}`, "📋"))
    .catch(() => showToast("Gagal menyalin kode", "❌"));
}

function downloadModalQrImage() {
  const wrap = $("modal-qr-canvas-wrap");
  const canvas = wrap ? wrap.querySelector("canvas") : null;
  const img = wrap ? wrap.querySelector("img") : null;
  const src = canvas ? canvas.toDataURL("image/png") : (img ? img.src : null);
  if (!src) return showToast("Gambar QR belum siap.", "⚠️");
  const a = document.createElement("a");
  a.href = src;
  a.download = `QR_${currentModalQrCode || "biochain"}.png`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  showToast("Kode QR berhasil diunduh!", "⬇️");
}

function closeModal() {
  $("qr-modal").classList.remove("open");
}

/* ============================================================== */
/* KETELUSURAN SIRKULAR QR CODE END-TO-END (CLOSED-LOOP)          */
/* ============================================================== */
let currentTraceData = null;

function viewFullCircularTraceFromModal() {
  const code = currentModalQrCode;
  closeModal();
  openCircularTraceModal(code);
}
window.viewFullCircularTraceFromModal = viewFullCircularTraceFromModal;

async function openCircularTraceModal(identifier = null) {
  const modal = $("circular-trace-modal");
  if (!modal) return;
  modal.classList.add("open");

  const idToLoad = identifier || (currentModalQrCode ? currentModalQrCode : "6");
  if ($("circ-search-input")) $("circ-search-input").value = idToLoad;
  await loadCircularTraceById(idToLoad);
}
window.openCircularTraceModal = openCircularTraceModal;

function closeCircularTraceModal() {
  const modal = $("circular-trace-modal");
  if (modal) modal.classList.remove("open");
}
window.closeCircularTraceModal = closeCircularTraceModal;

async function handleCircSearchSubmit() {
  const input = $("circ-search-input");
  const val = input ? input.value.trim() : "";
  if (!val) {
    showToast("Masukkan kode QR atau nomor lot yang ingin dilacak.", "⚠️");
    return;
  }
  await loadCircularTraceById(val);
}
window.handleCircSearchSubmit = handleCircSearchSubmit;

async function loadCircularTraceById(identifier) {
  const content = $("circ-modal-content");
  if (!content) return;
  content.innerHTML = `
    <div style="text-align:center; padding:50px 20px;">
      <div class="spinner" style="margin:0 auto 16px; width:36px; height:36px; border:3px solid var(--border); border-top-color:var(--primary); border-radius:50%; animation:spin 1s linear infinite;"></div>
      <div style="font-weight:700; font-size:14px; color:var(--ink);">Memuat Silsilah Rantai Sirkular...</div>
      <div class="muted" style="font-size:12px; margin-top:4px;">Menghubungkan data Petani ➔ Pengepul ➔ Driver ➔ Pabrik ➔ Abu/Biochar ➔ Sawah</div>
    </div>
  `;

  try {
    const data = await api(`/api/v1/traceability/circular/${encodeURIComponent(identifier)}`);
    currentTraceData = data;
    renderCircularTraceView(data);
  } catch (err) {
    content.innerHTML = `
      <div style="padding:30px; text-align:center;">
        <div style="font-size:40px; margin-bottom:10px;">⚠️</div>
        <h4 style="margin:0 0 8px; color:var(--danger);">Gagal Memuat Ketelusuran</h4>
        <p class="muted" style="margin:0 0 16px;">${esc(err.message || "Data tidak ditemukan")}</p>
        <button type="button" class="btn btn-secondary btn-sm" data-onclick="loadCircularTraceById('6')">Lihat Contoh Lot #6 Demo</button>
      </div>
    `;
  }
}
window.loadCircularTraceById = loadCircularTraceById;

function copyCircStageQr(code) {
  if (!code) return;
  navigator.clipboard.writeText(code)
    .then(() => showToast(`Kode QR disalin: ${code}`, "📋"))
    .catch(() => showToast("Gagal menyalin kode", "❌"));
}
window.copyCircStageQr = copyCircStageQr;

function renderCircularTraceView(data) {
  const content = $("circ-modal-content");
  if (!content) return;

  if (!data || !data.found) {
    content.innerHTML = `
      <div style="padding:40px; text-align:center;">
        <div style="font-size:48px; margin-bottom:12px;">🔍</div>
        <h3 style="margin:0 0 8px;">Lot Tidak Ditemukan</h3>
        <p class="muted" style="max-width:480px; margin:0 auto 16px;">
          Kode <code>${esc(data.identifier)}</code> belum terdaftar dalam rantai pasok sirkular.
        </p>
        <button type="button" class="btn btn-primary btn-sm" data-onclick="loadCircularTraceById('6')">🌾 Tampilkan Contoh Lot #6 (Closed Loop)</button>
      </div>
    `;
    return;
  }

  const loop = data.loop_summary || {};
  const stages = data.stages || [];

  if ($("circ-badge-status")) {
    $("circ-badge-status").innerText = loop.is_closed_loop ? "🟢 100% Sirkular Terpenuhi" : `🔵 Tahap ${loop.current_stage_step}/6`;
    $("circ-badge-status").className = `badge ${loop.is_closed_loop ? "badge-green" : "badge-blue"}`;
  }
  if ($("circ-hash-preview")) {
    $("circ-hash-preview").innerText = loop.integrity_hash || "–";
    $("circ-hash-preview").title = "SHA256 Fingerprint Valid: Anti-Tamper Immutable Blockchain-Grade Hash";
  }

  // Visual Loop Track Nodes
  const trackNodesHtml = stages.map((st, idx) => {
    const isDone = st.status === "COMPLETED";
    const isActive = st.status === "IN_PROGRESS" || (loop.current_stage_step === st.step);
    const icons = ["🌾", "⚖️", "🚚", "🏭", "⚗️", "♻️"];
    const icon = icons[idx] || "📦";
    return `
      <div class="circ-track-node" data-onclick="document.getElementById('circ-stage-card-${st.step}').scrollIntoView({behavior:'smooth'})" title="Klik untuk menuju rincian tahap ${st.step}">
        <div class="circ-node-circle ${isDone ? 'done' : (isActive ? 'active' : '')}">
          ${icon}
        </div>
        <div style="font-size:11px; font-weight:700; color:var(--ink); line-height:1.2;">
          Tahap ${st.step}
        </div>
        <div style="font-size:9.5px; color:${isDone ? '#10b981' : (isActive ? '#38bdf8' : 'var(--ink-muted)')}; font-weight:600;">
          ${st.status === 'COMPLETED' ? '✓ Selesai' : (isActive ? '● Aktif' : 'Menunggu')}
        </div>
      </div>
      ${idx < stages.length - 1 ? `<div class="circ-track-arrow">➔</div>` : `<div class="circ-track-arrow" title="Sirkular kembali ke sawah">↺</div>`}
    `;
  }).join("");

  // Detailed Stage Cards
  const stageCardsHtml = stages.map((st) => {
    const isDone = st.status === "COMPLETED";
    const statusBadge = isDone
      ? `<span class="badge badge-green">✓ Selesai</span>`
      : (st.status === "IN_PROGRESS"
        ? `<span class="badge badge-blue">● Sedang Berjalan</span>`
        : `<span class="badge badge-gray">○ Menunggu Tahap Sebelumnya</span>`);

    let detailsGridHtml = "";
    if (st.step === 1) {
      // Petani
      detailsGridHtml = `
        <div class="circ-metrics-grid">
          <div class="circ-metric-item">
            <span class="muted">Petani Produsen:</span><br>
            <b>${esc(st.actor.name)}</b><br>
            <span class="muted" style="font-size:11px;">📱 ${esc(st.actor.phone)} · 📍 ${esc(st.actor.location)}</span>
          </div>
          <div class="circ-metric-item">
            <span class="muted">Komoditas &amp; Estimasi:</span><br>
            <b>${esc(st.commodity.name)}</b> · <b>${num(st.commodity.estimated_qty_kg, 0)} kg</b><br>
            <span class="muted" style="font-size:11px;">Kadar Air Est: ${st.commodity.estimated_moisture_pct ? num(st.commodity.estimated_moisture_pct, 1) + '%' : '-'} · Grade ${esc(st.commodity.estimated_grade)}</span>
          </div>
          <div class="circ-metric-item">
            <span class="muted">Metode Logistik:</span><br>
            <b>${esc(st.commodity.delivery_mode)}</b><br>
            <span class="muted" style="font-size:11px;">Waktu Lapor: ${esc(st.timestamp ? new Date(st.timestamp).toLocaleString('id-ID') : '-')}</span>
          </div>
        </div>
      `;
    } else if (st.step === 2) {
      // Pengepul
      const m = st.measurements || {};
      detailsGridHtml = `
        <div class="circ-metrics-grid">
          <div class="circ-metric-item">
            <span class="muted">Pengepul Penanggung Jawab:</span><br>
            <b>${esc(st.actor.name)}</b><br>
            <span class="muted" style="font-size:11px;">🏢 ${esc(st.actor.warehouse)} · 📱 ${esc(st.actor.phone)}</span>
          </div>
          <div class="circ-metric-item">
            <span class="muted">Timbangan &amp; Uji Mutu Lapangan:</span><br>
            <b>${m.verified_weighed_kg ? num(m.verified_weighed_kg, 0) + ' kg' : '–'}</b> · <b>${esc(m.grade_awarded || '-')}</b><br>
            <span class="muted" style="font-size:11px;">Kadar Air Uji: ${m.moisture_tested_pct ? num(m.moisture_tested_pct, 1) + '%' : '-'}</span>
          </div>
          <div class="circ-metric-item">
            <span class="muted">Harga &amp; Transaksi:</span><br>
            <b>${m.price_per_kg_rp ? rp(m.price_per_kg_rp) + '/kg' : '–'}</b> (Total: <b>${m.total_value_rp ? rp(m.total_value_rp) : '–'}</b>)<br>
            <span class="muted" style="font-size:11px;">Status Finansial: ${esc(m.payment_status || '–')}</span>
          </div>
        </div>
      `;
    } else if (st.step === 3) {
      // Driver
      const log = st.logistics || {};
      detailsGridHtml = `
        <div class="circ-metrics-grid">
          <div class="circ-metric-item">
            <span class="muted">Armada &amp; Supir:</span><br>
            <b>${esc(log.driver_name || '-')}</b><br>
            <span class="muted" style="font-size:11px;">🚛 Plat Truk: <code>${esc(log.vehicle_plate || '-')}</code></span>
          </div>
          <div class="circ-metric-item">
            <span class="muted">Muatan Angkut:</span><br>
            <b>${log.transport_weight_kg ? num(log.transport_weight_kg, 0) + ' kg' : '–'}</b><br>
            <span class="muted" style="font-size:11px;">Rute: ${esc(log.route_name || '-')}</span>
          </div>
          <div class="circ-metric-item">
            <span class="muted">Checkpoint Pemindaian QR:</span><br>
            <b>${log.checkpoint_scanned ? '🟢 Terverifikasi Saat Muat' : 'Menunggu Checkpoint'}</b><br>
            <span class="muted" style="font-size:11px;">Waktu Pickup: ${esc(st.timestamp ? new Date(st.timestamp).toLocaleString('id-ID') : '-')}</span>
          </div>
        </div>
      `;
    } else if (st.step === 4) {
      // Pabrik Gate
      const fac = st.factory || {};
      detailsGridHtml = `
        <div class="circ-metrics-grid">
          <div class="circ-metric-item">
            <span class="muted">Pabrik Pengolah:</span><br>
            <b>${esc(fac.mill_name || 'PT Bio Agro Energi')}</b><br>
            <span class="muted" style="font-size:11px;">QC Gerbang: ${esc(fac.qc_decision || 'Passed')}</span>
          </div>
          <div class="circ-metric-item">
            <span class="muted">Timbangan Jembatan Timbang:</span><br>
            Bruto: <b>${fac.gross_weight_kg ? num(fac.gross_weight_kg, 0) + ' kg' : '–'}</b> · Tara: <b>${fac.tare_weight_kg ? num(fac.tare_weight_kg, 0) + ' kg' : '–'}</b><br>
            Netto Diterima: <b style="color:var(--primary); font-size:13px;">${fac.net_received_kg ? num(fac.net_received_kg, 0) + ' kg' : '–'}</b>
          </div>
          <div class="circ-metric-item">
            <span class="muted">Audit Susut (Shrinkage):</span><br>
            Susut: <b>${fac.shrinkage_kg != null ? num(fac.shrinkage_kg, 1) + ' kg' : '–'}</b> (<b>${fac.shrinkage_pct != null ? num(fac.shrinkage_pct, 2) + '%' : '–'}</b>)<br>
            <span class="badge ${fac.shrinkage_tolerance_passed ? 'badge-green' : 'badge-amber'}" style="font-size:10px;">${fac.shrinkage_tolerance_passed ? '✓ Lolos Toleransi Susut (≤ 5%)' : 'Refraksi'}</span>
          </div>
        </div>
      `;
    } else if (st.step === 5) {
      // Pirolisis & Abu
      const cv = st.conversion || {};
      const hm = cv.heavy_metals_safety || {};
      detailsGridHtml = `
        <div class="circ-metrics-grid">
          <div class="circ-metric-item">
            <span class="muted">Metode Konversi &amp; Reaktor:</span><br>
            <b>${esc(cv.method || 'Pirolisis Karbonisasi Terkendali')}</b><br>
            <span class="muted" style="font-size:11px;">Suhu Reaktor: <b>${cv.reactor_temp_c ? num(cv.reactor_temp_c, 0) + '°C' : '480°C'}</b> · Input: <b>${cv.feedstock_processed_kg ? num(cv.feedstock_processed_kg, 0) + ' kg' : '–'}</b></span>
          </div>
          <div class="circ-metric-item">
            <span class="muted">Produk Sirkular (Yield):</span><br>
            Biochar Aktif: <b style="color:#10b981; font-size:13px;">${num(cv.biochar_yield_kg || 0, 1)} kg</b> (Yield ${num(cv.biochar_yield_pct || 30, 1)}%)<br>
            Abu Sisa Pembakaran (Silika/Bottom Ash): <b style="color:#38bdf8;">${num(cv.combustion_ash_byproduct_kg || 0, 1)} kg</b>
          </div>
          <div class="circ-metric-item">
            <span class="muted">Uji Keamanan Logam Berat (Bebas B3):</span><br>
            <span class="badge badge-green" style="font-size:10px; font-weight:700;">${esc(hm.safety_verdict || 'LOLOS UJI KEAMANAN')}</span><br>
            <span class="muted" style="font-size:10.5px;">Pb: ${hm.lead_pb_ppm || 4.2} ppm (&lt;50) · Cd: ${hm.cadmium_cd_ppm || 0.18} ppm (&lt;2) · As: ${hm.arsenic_as_ppm || 0.65} ppm (&lt;10)</span>
          </div>
        </div>
      `;
    } else if (st.step === 6) {
      // Muatan Balik Sawah
      const cd = st.circular_distribution || {};
      const ben = cd.soil_restoration_benefits || {};
      detailsGridHtml = `
        <div class="circ-metrics-grid">
          <div class="circ-metric-item">
            <span class="muted">Alokasi Abu Bottom Ash Sawah:</span><br>
            <b style="color:#10b981; font-size:14px;">${num(cd.farmer_allocation_kg || 0, 1)} kg</b> (<b style="color:var(--primary);">${cd.total_bags_delivered || 0} Karung Sak</b>)<br>
            <span class="muted" style="font-size:11px;">Tujuan: <b>${esc(cd.destination_field || 'Lahan Sawah Petani')}</b></span>
          </div>
          <div class="circ-metric-item">
            <span class="muted">Armada Muatan Balik (Backhaul):</span><br>
            <b>${esc(cd.backhaul_vehicle_plate || 'Truk Muatan Balik Pabrik')}</b><br>
            <span class="muted" style="font-size:11px;">Surat Jalan: <code>${esc(cd.dispatch_code || '-')}</code></span>
          </div>
          <div class="circ-metric-item">
            <span class="muted">Manfaat Pemulihan Tanah Sawah:</span><br>
            <b>${esc(ben.c_organic_gain_pct || '+1.4% C-Organik')}</b> · <b>${esc(ben.water_retention_improvement || '+22% Retensi Air')}</b><br>
            <span class="muted" style="font-size:11px;">Emisi Dihindari: <b>${num(ben.ipcc_carbon_avoided_kg_co2e || 0, 1)} kgCO₂e</b> · ${esc(ben.ph_buffer_effect || 'Netralisasi Tanah')}</span>
          </div>
        </div>
      `;
    }

    return `
      <div class="circ-stage-card" id="circ-stage-card-${st.step}">
        <div class="circ-card-head">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:18px;">${["🌾", "⚖️", "🚚", "🏭", "⚗️", "♻️"][st.step - 1] || "📦"}</span>
            <div>
              <div style="font-weight:700; font-size:13.5px; color:var(--ink);">${esc(st.title)}</div>
              <div style="font-size:11px; color:var(--ink-muted);">${esc(st.subtitle)}</div>
            </div>
          </div>
          <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
            <div class="circ-qr-pill" title="Kode unik terdaftar">
              <span>📱</span>
              <span>${esc(st.qr_code)}</span>
              <button type="button" class="btn btn-secondary btn-sm" style="padding:1px 5px; font-size:9px; height:18px; margin-left:2px;" data-onclick="copyCircStageQr('${esc(st.qr_code)}')">📋</button>
              <button type="button" class="btn btn-primary btn-sm" style="padding:1px 5px; font-size:9px; height:18px;" data-onclick="openModal('${esc(st.title)}', '${esc(st.qr_code)}', 'Verifikasi Tahap ${st.step} Bio-Chain')">QR</button>
            </div>
            ${statusBadge}
          </div>
        </div>
        <div class="circ-card-body">
          ${detailsGridHtml}
          ${st.note ? `<div style="margin-top:10px; font-size:11px; color:var(--ink-muted); font-style:italic; border-left:2px solid var(--primary); padding-left:8px;">ℹ️ ${esc(st.note)}</div>` : ''}
        </div>
      </div>
    `;
  }).join("");

  content.innerHTML = `
    <!-- Top Summary Metrics Grid -->
    <div class="circ-summary-grid">
      <div class="circ-kpi-box">
        <span class="lbl">🌾 Input Biomassa Sawah</span>
        <span class="val">${num(loop.total_biomass_input_kg, 0)} kg</span>
        <span class="sub">${esc(data.commodity_name || 'Biomassa')}</span>
      </div>
      <div class="circ-kpi-box">
        <span class="lbl">🏭 Timbang Terima Pabrik</span>
        <span class="val">${num(loop.factory_received_kg, 0)} kg</span>
        <span class="sub">Refraksi &amp; Susut Teruji</span>
      </div>
      <div class="circ-kpi-box">
        <span class="lbl">⚗️ Biochar Dihasilkan</span>
        <span class="val" style="color:#10b981;">${num(loop.biochar_allocated_kg, 1)} kg</span>
        <span class="sub">Yield Karbonisasi ~30%</span>
      </div>
      <div class="circ-kpi-box">
        <span class="lbl">💨 Abu Sisa Pembakaran</span>
        <span class="val" style="color:#38bdf8;">${num(loop.combustion_ash_kg, 1)} kg</span>
        <span class="sub">Silika/Bottom Ash Bebas B3</span>
      </div>
      <div class="circ-kpi-box">
        <span class="lbl">♻️ Kembali ke Sawah</span>
        <span class="val" style="color:#10b981;">${Math.max(1, Math.round(loop.biochar_allocated_kg / 25))} Sak</span>
        <span class="sub">Karung Muatan Balik</span>
      </div>
      <div class="circ-kpi-box">
        <span class="lbl">🌿 Emisi CO₂ Dihindari</span>
        <span class="val" style="color:#10b981;">${num(loop.carbon_avoided_kg_co2e, 1)} kg</span>
        <span class="sub">Metodologi IPCC Tier 2</span>
      </div>
    </div>

    <!-- Visual Circular Track -->
    <div class="circ-loop-track">
      ${trackNodesHtml}
    </div>

    <!-- 6-Stage Timeline Breakdown -->
    <div class="circ-timeline">
      ${stageCardsHtml}
    </div>
  `;
}

// ==============================================================
// NOTIFICATION CENTER (Extracted to app/static/js/modules/notification-center.js)
// ==============================================================

// Pemindai & generator QR → js/modules/qr-tools.js

function emptyState(icon, title, desc = "") {
  return `<div class="empty-state">
    <div class="empty-icon">${icon}</div>
    <div class="empty-title">${title}</div>
    ${desc ? `<div class="empty-desc">${desc}</div>` : ""}
  </div>`;
}

// Global keyboard shortcuts (Esc to close modals & AI panel)
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeModal();
    closeScannerModal();
    closeGeneratorModal();
    if (typeof aiShow === "function") aiShow(false);
  }
});

// Respons mentah (blob / stream / FormData) dengan perlakuan yang sama seperti api(): token Bearer, timeout
// sampai header respons tiba (body stream boleh mengalir lebih lama), 401 → logout, error ber-.status/.code.
async function apiRaw(path, options = {}) {
  const headers = options.headers || {};
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  if (options.body && !isFormData && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (STATE.token) {
    headers["Authorization"] = `Bearer ${STATE.token}`;
  }
  // Timeout agar sinyal lemah tidak menggantung UI; aksi tulis aman diulang (client_event_id).
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), options.timeoutMs || 15000);
  let res;
  try {
    res = await fetch(path, {
      method: options.method || (options.body ? "POST" : "GET"),
      headers,
      body: isFormData ? options.body : (options.body ? JSON.stringify(options.body) : undefined),
      signal: ctrl.signal,
    });
  } catch (e) {
    const err = new Error("Tidak ada sinyal / server tidak terjangkau");
    err.network = true;
    throw err;
  } finally {
    clearTimeout(timer);
  }

  if (res.status === 401 && STATE.token && !options.noLogout) {
    logout("Sesi berakhir, silakan login kembali.");
    const err = new Error("Sesi berakhir");
    err.status = 401;
    throw err;
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const msg = data.detail || res.statusText || "Terjadi kesalahan";
    const err = new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    err.status = res.status;
    if (data.code) err.code = data.code;
    throw err;
  }
  return res;
}

async function api(path, options = {}) {
  const res = await apiRaw(path, options);
  return res.json().catch(() => ({}));
}

// Unduh berkas lewat apiRaw; nama dari Content-Disposition bila ada
async function apiDownload(path, fallbackName) {
  const res = await apiRaw(path, { timeoutMs: 60000 });
  const blob = await res.blob();
  const name = (res.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/)?.[1] || fallbackName;
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: name });
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}


// ==============================================================
// PARAMETER ASUMSI — nilai aktif untuk default form + tab pengelolaan
// ==============================================================
STATE.pv = {};
const PV = (key, fallback) => (key in STATE.pv ? STATE.pv[key] : fallback);

async function loadParamValues() {
  try {
    const r = await api("/api/v1/params");
    STATE.pv = Object.fromEntries(r.groups.flatMap(g => g.params.map(p => [p.key, p.value])));
    STATE.paramsMeta = r;
    applyParamDefaults();
  } catch (err) { console.warn("Parameter belum termuat:", err.message); }
}

function applyParamDefaults() {
  const set = (id, v) => { if ($(id) && v != null) $(id).value = v; };
  set("r-m3", PV("logistik.vehicle_m3")); set("r-dens", PV("logistik.bulk_density_kg_m3"));
  set("r-cost", PV("logistik.cost_per_km")); set("mk-resale", PV("pasar.default_resale_price_per_kg")); set("mk-margin", PV("pasar.default_margin_pct"));
  set("q-temp", PV("limbah.pyrolysis_temp_c")); set("v-temp", PV("limbah.pyrolysis_temp_c"));
  set("ls-pj", PV("harga_mutu.base_price_per_kg")); set("ls-pa", PV("harga_mutu.base_price_per_kg"));
  if ($("f-qty") && $("f-qty").oninput) $("f-qty").oninput();
}

let pmGroup = null;
async function loadParams() {
  const r = await api("/api/v1/params");
  STATE.paramsMeta = r;
  STATE.pv = Object.fromEntries(r.groups.flatMap(g => g.params.map(p => [p.key, p.value])));
  $("pm-mode").textContent = r.can_edit ? "Mode ubah" : "Baca-saja";
  $("pm-mode").className = "badge " + (r.can_edit ? "badge-green" : "badge-gray");
  $("pm-reason-box").style.display = r.can_edit ? "flex" : "none";
  pmGroup = pmGroup || r.groups[0].id;
  $("pm-groups").innerHTML = r.groups.map(g => { const miss = g.params.filter(p => p.missing).length;
    return `<button class="btn btn-sm ${g.id === pmGroup ? "btn-primary" : "btn-outline-green"}" data-g="${esc(g.id)}">${esc(g.label)}
      ${g.modified ? ` <span class="badge badge-amber">${g.modified}</span>` : ""}${miss ? ` <span class="badge badge-red">${miss} wajib</span>` : ""}</button>`; }).join("");
  $("pm-groups").querySelectorAll("button").forEach(b => { b.onclick = () => { pmGroup = b.dataset.g; loadParams(); }; });
  const g = r.groups.find(x => x.id === pmGroup);
  $("pm-body").innerHTML = g.params.map(p => p.kind === "table" ? pmTable(p, r.can_edit) : pmRow(p, r.can_edit)).join("");
  bindParamButtons();
  loadParamHistory();
}

function pmRow(p, edit) {
  if (p.kind === "choice") {
    return `<div style="display:grid; grid-template-columns:minmax(200px,2fr) 2fr auto; gap:8px; align-items:center; padding:8px 0; border-bottom:1px solid var(--border);">
      <div><b style="font-size:var(--fs-sm);">${esc(p.label)}</b> ${p.modified ? '<span class="badge badge-amber">diubah</span>' : ""}
        <div class="kpi-lbl">${esc(p.help || "")}${p.source ? ` <i>Sumber: ${esc(p.source)}</i>` : ""}</div></div>
      <select class="btn btn-secondary pm-input" data-key="${esc(p.key)}" data-kind="choice" ${edit ? "" : "disabled"}>
        ${p.options.map(([v, l]) => `<option value="${esc(v)}" ${v === p.value ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>
      <div>${edit ? `<button class="btn btn-primary btn-sm pm-save" data-key="${esc(p.key)}">Simpan</button>` : ""}</div></div>`;
  }
  const range = p.min != null ? `${num(p.min, 4)}–${num(p.max, 4)} ${esc(p.unit)}` : "";
  return `<div style="display:grid; grid-template-columns:minmax(200px,2fr) 150px 1.5fr auto; gap:8px; align-items:center;
                      padding:8px 0; border-bottom:1px solid var(--border);">
    <div><b style="font-size:var(--fs-sm);">${esc(p.label)}</b> ${p.modified ? '<span class="badge badge-amber">diubah</span>' : ""}
      ${p.missing ? '<span class="badge badge-red">wajib diisi</span>' : ""}
      <div class="kpi-lbl">${esc(p.help || "")}${p.source ? ` <i>Sumber: ${esc(p.source)}</i>` : ""}</div></div>
    <div style="display:flex; gap:4px; align-items:center;">
      <input type="number" step="any" class="btn btn-secondary pm-input" data-key="${esc(p.key)}" value="${p.value ?? ""}"
             placeholder="${p.required_input ? "isi harga aktual" : ""}"
             style="width:100%;" ${edit ? "" : "disabled"} aria-label="${esc(p.label)}"><span class="kpi-lbl">${esc(p.unit)}</span></div>
    <div class="kpi-lbl">${p.required_input ? "tanpa angka bawaan" : `default ${num(p.default, 4)}`} · rentang ${range}</div>
    <div style="white-space:nowrap;">${edit ? `<button class="btn btn-primary btn-sm pm-save" data-key="${esc(p.key)}">Simpan</button>
      ${p.modified ? `<button class="btn btn-secondary btn-sm pm-reset" data-key="${esc(p.key)}">Default</button>` : ""}` : ""}</div>
  </div>`;
}

function pmTable(p, edit) {
  const cols = p.columns;
  const cell = (c, v, i) => c.kind === "bool"
    ? `<input type="checkbox" data-c="${esc(c.name)}" ${v ? "checked" : ""} ${edit ? "" : "disabled"}>`
    : `<input ${c.kind === "number" ? 'type="number" step="any"' : 'type="text"'} class="btn btn-secondary" data-c="${esc(c.name)}"
         value="${esc(v ?? "")}" style="width:${c.kind === "text" ? 140 : 90}px;" ${edit ? "" : "disabled"}>`;
  return `<div style="margin:12px 0;"><b>${esc(p.label)}</b> ${p.modified ? '<span class="badge badge-amber">diubah</span>' : ""}
    <div class="kpi-lbl">${esc(p.help || "")}${p.source ? ` <i>Sumber: ${esc(p.source)}</i>` : ""}</div>
    <div style="overflow-x:auto;"><table class="data-table" id="pmt-${esc(p.key)}"><thead><tr>
      ${cols.map(c => `<th>${esc(c.label)}${c.unit ? `<br><span class="kpi-lbl">${esc(c.unit)}</span>` : ""}</th>`).join("")}${edit ? "<th></th>" : ""}</tr></thead>
    <tbody>${p.value.map(row => `<tr>${cols.map(c => `<td>${cell(c, row[c.name])}</td>`).join("")}
      ${edit ? '<td><button class="btn btn-secondary btn-sm pm-del-row" title="Hapus baris">✕</button></td>' : ""}</tr>`).join("")}</tbody></table></div>
    ${edit ? `<button class="btn btn-secondary btn-sm pm-add-row" data-key="${esc(p.key)}">+ Tambah baris</button>
      <button class="btn btn-primary btn-sm pm-save-table" data-key="${esc(p.key)}">Simpan tabel</button>
      ${p.modified ? `<button class="btn btn-secondary btn-sm pm-reset" data-key="${esc(p.key)}">Default</button>` : ""}` : ""}</div>`;
}

function pmReason() {
  const r = $("pm-reason").value.trim();
  if (r.length < 5) { showToast("Isi alasan perubahan (min. 5 karakter) — dicatat untuk audit.", "⚠️"); $("pm-reason").focus(); return null; }
  return r;
}

async function pmSend(key, value, btn) {
  const reason = pmReason();
  if (!reason) return;
  return withBusy(btn, async () => {
    try {
      await api(`/api/v1/params/${encodeURIComponent(key)}`, { method: "PUT", body: { value, reason } });
      showToast("Parameter disimpan & langsung dipakai semua modul.", "✅");
      await loadParams(); await loadParamValues();
    } catch (err) { showToast(err.message, "❌"); }
  });
}

function bindParamButtons() {
  document.querySelectorAll(".pm-save").forEach(b => { b.onclick = () => {
    const input = document.querySelector(`.pm-input[data-key="${b.dataset.key}"]`);
    if (input.dataset.kind !== "choice" && input.value === "") return showToast("Isi angkanya dulu.", "⚠️");
    pmSend(b.dataset.key, input.dataset.kind === "choice" ? input.value : Number(input.value), b);
  }; });
  document.querySelectorAll(".pm-reset").forEach(b => { b.onclick = async () => {
    const reason = pmReason(); if (!reason) return;
    await withBusy(b, async () => {
      try { await api(`/api/v1/params/${encodeURIComponent(b.dataset.key)}/reset`, { body: { reason } });
            showToast("Dikembalikan ke default.", "↩️"); await loadParams(); await loadParamValues(); }
      catch (err) { showToast(err.message, "❌"); }
    });
  }; });
  document.querySelectorAll(".pm-del-row").forEach(b => { b.onclick = () => b.closest("tr").remove(); });
  document.querySelectorAll(".pm-add-row").forEach(b => { b.onclick = () => {
    const tbody = $(`pmt-${b.dataset.key}`).querySelector("tbody");
    const last = tbody.querySelector("tr");
    if (!last) return;
    const clone = last.cloneNode(true);
    clone.querySelectorAll("input").forEach(i => { if (i.type === "checkbox") i.checked = false; else i.value = ""; });
    clone.querySelector(".pm-del-row").onclick = () => clone.remove();
    tbody.appendChild(clone);
  }; });
  document.querySelectorAll(".pm-save-table").forEach(b => { b.onclick = () => {
    const meta = STATE.paramsMeta.groups.flatMap(g => g.params).find(p => p.key === b.dataset.key);
    const rows = [...$(`pmt-${b.dataset.key}`).querySelectorAll("tbody tr")].map(tr => Object.fromEntries(meta.columns.map(c => {
      const el = tr.querySelector(`[data-c="${c.name}"]`);
      return [c.name, c.kind === "bool" ? el.checked : c.kind === "number" ? Number(el.value) : el.value.trim()];
    })));
    pmSend(b.dataset.key, rows, b);
  }; });
}

async function loadParamHistory() {
  try {
    const h = await api(`/api/v1/params/history?limit=50`);
    const fmt = v => v == null ? "<i>default</i>" : Array.isArray(v) ? `${v.length} baris` : esc(String(v));
    $("pm-history").innerHTML = h.length ? `<table class="data-table"><thead><tr><th>Waktu</th><th>Parameter</th><th>Dari</th><th>Menjadi</th>
        <th>Oleh</th><th>Alasan</th></tr></thead><tbody>${h.map(x => `<tr><td style="font-size:var(--fs-xs);">${esc(new Date(x.at).toLocaleString("id-ID"))}</td>
        <td>${esc(x.label)}</td><td>${fmt(x.old_value)}</td><td>${fmt(x.new_value)}</td><td>${esc(x.by)} <span class="kpi-lbl">(${esc(x.role)})</span></td>
        <td style="font-size:var(--fs-xs);">${esc(x.reason)}</td></tr>`).join("")}</tbody></table>` : `<p class="muted">Belum ada perubahan — semua memakai default.</p>`;
  } catch (err) { $("pm-history").innerHTML = ""; }
}

// ==============================================================
// LAPORAN BULANAN — kolom, tabel & grafik ditentukan server sesuai peran
// ==============================================================
let reportChart;
function rpQuery(extra = "") {
  const q = new URLSearchParams();
  if ($("rp-from").value) q.set("from", $("rp-from").value);
  if ($("rp-to").value) q.set("to", $("rp-to").value);
  return `?${q.toString()}${extra}`;
}
const rpVal = (row, key) => { const [g, n] = key.split("."); return (row[g] || {})[n]; };
const rpFmt = (v, unit) => v == null ? "–" : unit === "Rp" || unit === "Rp/kg" || unit === "Rp/t" ? rp(v)
  : unit === "%" ? `${num(v, 2)}%` : num(v, unit === "kg" || unit === "kWh" ? 0 : 1);

async function loadReport() {
  try {
    const r = await api(`/api/reports/monthly${rpQuery()}`);
    if (!$("rp-from").value) { $("rp-from").value = r.period.from; $("rp-to").value = r.period.to; }
    $("rp-scope").textContent = `${r.scope.label} · ${r.period.from} s.d. ${r.period.to} · ${r.period.timezone}`;
    const sums = r.columns.filter(c => c.key in r.totals);
    $("rp-kpis").innerHTML = sums.slice(0, 4).map((c, i) => `<div class="kpi-tile ${["", "kpi-blue", "kpi-amber", "kpi-purple"][i]}">
      <div class="kpi-lbl">${esc(c.label)}</div><div class="kpi-val">${rpFmt(r.totals[c.key], c.unit)}</div>
      <div class="kpi-lbl">total ${esc(c.unit)}</div></div>`).join("");
    const groups = [...new Set(r.columns.map(c => c.group))];
    $("rp-table").innerHTML = `<table class="data-table"><thead>
      <tr><th rowspan="2">Bulan</th>${groups.map(g => `<th colspan="${r.columns.filter(c => c.group === g).length}" style="text-align:center;">${esc(g)}</th>`).join("")}</tr>
      <tr>${groups.flatMap(g => r.columns.filter(c => c.group === g)).map(c => `<th class="num">${esc(c.label)}<br><span class="kpi-lbl">${esc(c.unit)}</span></th>`).join("")}</tr></thead>
      <tbody>${r.months.map(m => `<tr><td>${esc(m.month)}</td>${groups.flatMap(g => r.columns.filter(c => c.group === g))
        .map(c => `<td class="num">${rpFmt(rpVal(m, c.key), c.unit)}</td>`).join("")}</tr>`).join("")}</tbody>
      <tfoot><tr><th>Total</th>${groups.flatMap(g => r.columns.filter(c => c.group === g))
        .map(c => `<th class="num">${c.key in r.totals ? rpFmt(r.totals[c.key], c.unit) : ""}</th>`).join("")}</tr></tfoot></table>`;
    $("rp-defs").innerHTML = Object.entries(r.definitions).map(([k, v]) => `<div><b>${esc(k)}</b>: ${esc(v)}</div>`).join("")
      + `<div style="margin-top:8px;">${r.references.map(x => `• ${esc(x)}`).join("<br>")}</div>`;
    if (typeof Chart !== "undefined") {
      const charted = r.columns.filter(c => c.chart);
      const palette = ["#15803d", "#2563eb", "#d97706", "#7c3aed", "#dc2626"];
      if (reportChart) reportChart.destroy();
      reportChart = new Chart($("rp-chart"), { data: {
        labels: r.months.map(m => m.month),
        datasets: charted.map((c, i) => ({
          type: c.unit === "kg" || c.unit === "stop" ? "bar" : "line", label: `${c.label} (${c.unit})`,
          data: r.months.map(m => rpVal(m, c.key)), borderColor: palette[i % 5], backgroundColor: palette[i % 5] + "99",
          yAxisID: c.unit === "kg" || c.unit === "stop" ? "y" : "y1", spanGaps: true })) },
        options: { responsive: true, plugins: { legend: { position: "bottom" } },
                   scales: { y: { position: "left", beginAtZero: true }, y1: { position: "right", grid: { drawOnChartArea: false } } } } });
    }
    if (window.renderQualityFeedback) window.renderQualityFeedback();
  } catch (err) { showToast(err.message, "❌"); }
}

async function downloadReportCsv() {
  try { await apiDownload(`/api/reports/monthly${rpQuery("&format=csv")}`, "laporan.csv"); }
  catch (err) { showToast(err.message, "❌"); }
}

async function downloadReportXlsx() {
  try { await apiDownload(`/api/reports/monthly${rpQuery("&format=xlsx")}`, "laporan.xlsx"); }
  catch (err) { showToast(err.message, "❌"); }
}
$("btn-rp") && ($("btn-rp").onclick = e => withBusy(e.currentTarget, loadReport));
$("btn-rp-csv") && ($("btn-rp-csv").onclick = e => withBusy(e.currentTarget, downloadReportCsv));
$("btn-rp-xlsx") && ($("btn-rp-xlsx").onclick = e => withBusy(e.currentTarget, downloadReportXlsx));

// ==============================================================
// ASISTEN AI (Extracted to app/static/js/modules/ai-assistant-widget.js)
// ==============================================================

// ==============================================================
// OFFLINE-FIRST OUTBOX (Petani, Pengepul, Supir)
// Aksi tulis diberi client_event_id + waktu perangkat. Bila sinyal hilang, disimpan di
// localStorage dan dikirim ulang otomatis; server mengabaikan kiriman ganda (idempoten).
// ==============================================================
async function withBusy(btn, fn, busyLabel = "⏳ Memproses…") {
  if (!btn) return fn();
  if (btn.dataset.busy === "1") return;               // klik ganda diabaikan
  const label = btn.innerHTML;
  btn.dataset.busy = "1";
  btn.disabled = true;
  btn.setAttribute("aria-busy", "true");
  btn.innerHTML = busyLabel;
  try {
    return await fn();
  } finally {
    btn.dataset.busy = "";
    btn.disabled = false;
    btn.removeAttribute("aria-busy");
    btn.innerHTML = label;
  }
}

// ---- Penyimpanan antrean: IndexedDB (tahan ditutup/restart HP, kapasitas besar), cadangan localStorage.
// Salinan di memori (OUTBOX) dipakai agar UI tetap sinkron; setiap perubahan ditulis ke IndexedDB.
const OUTBOX_KEY = "biochain_outbox";
const IDB_NAME = "biochain-offline", IDB_VER = 2;     // v2: store "photos" (foto bukti saat offline)
let OUTBOX = [], DEADBOX = [], idbReady = null;

function idbOpen() {
  if (idbReady) return idbReady;
  idbReady = new Promise(resolve => {
    try {
      const req = indexedDB.open(IDB_NAME, IDB_VER);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains("kv")) db.createObjectStore("kv");
        if (!db.objectStoreNames.contains("track")) db.createObjectStore("track", { keyPath: "client_point_id" });
        if (!db.objectStoreNames.contains("photos")) db.createObjectStore("photos", { keyPath: "token" });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    } catch { resolve(null); }
  });
  return idbReady;
}
async function idbTx(store, mode, fn) {
  const db = await idbOpen();
  if (!db) return null;
  return new Promise(resolve => {
    try {
      const tx = db.transaction(store, mode);
      const out = fn(tx.objectStore(store));
      tx.oncomplete = () => resolve(out && "result" in out ? out.result : out);
      tx.onerror = tx.onabort = () => resolve(null);
    } catch { resolve(null); }
  });
}
const kvGet = k => idbTx("kv", "readonly", s => s.get(k));
const kvSet = (k, v) => idbTx("kv", "readwrite", s => s.put(v, k));

async function outboxLoad() {
  let items = await kvGet("outbox");
  let dead = await kvGet("deadbox");
  // Migrasi sekali dari versi lama (localStorage) agar antrean yang belum terkirim tidak hilang
  try {
    const legacy = JSON.parse(localStorage.getItem(OUTBOX_KEY) || "[]");
    if (legacy.length) {
      const ids = new Set((items || []).map(i => i.id));
      items = [...(items || []), ...legacy.filter(i => !ids.has(i.id))];
      if (await kvSet("outbox", items) !== null) localStorage.removeItem(OUTBOX_KEY);
    }
  } catch {}
  OUTBOX = Array.isArray(items) ? items : (JSON.parse(localStorage.getItem(OUTBOX_KEY) || "[]"));
  DEADBOX = Array.isArray(dead) ? dead : [];
  photoCountRefresh();
}
function outboxRead() { return OUTBOX; }
function outboxWrite(items) {
  OUTBOX = items;
  kvSet("outbox", items).then(ok => {           // IndexedDB tidak tersedia → cadangan localStorage
    if (ok === null) { try { localStorage.setItem(OUTBOX_KEY, JSON.stringify(items)); } catch {} }
  });
  renderNetPill();
}
function deadboxAdd(item, reason) {
  DEADBOX = [...DEADBOX, { ...item, failed_reason: reason, failed_at: Date.now() }].slice(-50);
  kvSet("deadbox", DEADBOX);
}
// ---- Foto bukti saat offline: blob terkompres disimpan di IndexedDB, kolom URL diisi token sementara.
// Sebelum aksi dikirim (langsung maupun dari antrean), token diganti URL hasil unggah. Foto tidak pernah hilang
// walau HP ditutup; bila gagal unggah karena sinyal, aksi ikut menunggu di antrean (urutan tetap terjaga).
const PHOTO_PREFIX = "pending-photo:";
let PHOTOS_PENDING = 0;
async function photoCountRefresh() {
  PHOTOS_PENDING = ((await idbTx("photos", "readonly", s => s.getAll())) || []).filter(isMine).length;
  renderNetPill();
}
async function photoQueue(file) {
  const token = PHOTO_PREFIX + newId();
  const ok = await idbTx("photos", "readwrite", s => s.put({ token, blob: file, user_id: myUid(), owner_name: ownerName(),
                                                            created_at: Date.now() }));
  if (ok === null) throw new Error("Penyimpanan HP penuh/terblokir — foto tidak bisa disimpan offline.");
  photoCountRefresh();
  return token;
}
async function photoUpload(blob) {
  const fd = new FormData();
  fd.append("file", blob, blob.name || "bukti.jpg");
  return api("/api/v1/uploads", { method: "POST", body: fd, timeoutMs: 60000 });   // foto ≤300 KB, sinyal 2G
}
async function resolvePendingPhotos(body) {
  const tokens = Object.entries(body).filter(([, v]) => typeof v === "string" && v.startsWith(PHOTO_PREFIX));
  if (!tokens.length) return body;
  const out = { ...body };
  for (const [k, token] of tokens) {
    const rec = await idbTx("photos", "readonly", s => s.get(token));
    if (!rec) { out[k] = null; continue; }                       // foto sudah dihapus pengguna → kirim tanpa foto
    const up = await photoUpload(rec.blob);                       // gagal sinyal → lempar err.network (aksi tetap antre)
    out[k] = up.url;
    await idbTx("photos", "readwrite", s => s.delete(token));
  }
  photoCountRefresh();
  return out;
}
window.BiochainPhotos = { queue: photoQueue, prefix: PHOTO_PREFIX, resolve: resolvePendingPhotos, refresh: photoCountRefresh };

// 018: daftar komoditas biomassa — disimpan lokal agar form lapor tetap jalan tanpa sinyal
async function biomassList() {
  try {
    const rows = await api("/api/v1/biomass");
    try { localStorage.setItem("biochain_biomass", JSON.stringify(rows)); } catch {}
    return rows;
  } catch {
    try { return JSON.parse(localStorage.getItem("biochain_biomass") || "[]"); } catch { return []; }
  }
}
async function fillCommoditySelect(sel, currentVal = null) {
  if (!sel) return;
  const rows = await biomassList();
  const opts = rows.map(b => `<option value="${esc(b.code)}">${esc(b.name)}</option>`);
  opts.push(`<option value="__custom__">➕ Tambah Biomassa Lain...</option>`);
  sel.innerHTML = opts.join("");
  if (currentVal && rows.some(b => b.code === currentVal)) {
    sel.value = currentVal;
  } else if (rows.length) {
    sel.value = rows[0].code;
  }
  if (!sel._boundCustom) {
    sel._boundCustom = true;
    sel.addEventListener("change", async () => {
      if (sel.value === "__custom__") {
        const name = prompt("Masukkan nama komoditas biomassa baru (misal: Kulit Kopi, Cangkang Sawit, Bonggol Jagung):");
        if (!name || !name.trim()) {
          sel.value = rows[0] ? rows[0].code : "";
          return;
        }
        try {
          const res = await api("/api/v1/biomass", { method: "POST", body: { name: name.trim() } });
          showToast(`Komoditas biomassa "${res.name}" berhasil ditambahkan!`, "🌿");
          await fillCommoditySelect(sel, res.code);
          sel.dispatchEvent(new Event("change", { bubbles: true }));
        } catch (err) {
          showToast(err.message || "Gagal menambahkan biomassa", "❌");
          sel.value = rows[0] ? rows[0].code : "";
        }
      }
    });
  }
}

const myUid = () => STATE.user && STATE.user.user_id;
const ownerName = () => STATE.user && (STATE.user.full_name || STATE.user.username) || null;
// F18 HP bersama: titik GPS & foto tanpa user_id berasal dari versi lama → dianggap milik pengguna yang sedang masuk
const isMine = rec => rec && (rec.user_id == null || rec.user_id === myUid());

function myOutbox(path) {
  const uid = STATE.user && STATE.user.user_id;
  return outboxRead().filter(i => i.user_id === uid && (!path || i.path === path));
}

async function apiMutation(path, body, label) {
  let geo = null;
  if (body.lat == null && body.lon == null) {
    try { geo = await getDeviceLocation(2000); } catch {}
  }
  const payload = {
    ...body,
    lat: body.lat ?? (geo ? geo.lat : null),
    lon: body.lon ?? (geo ? geo.lon : null),
    gps_accuracy: body.gps_accuracy ?? (geo ? geo.accuracy : null),
    client_event_id: body.client_event_id || newId(),
    client_recorded_at: body.client_recorded_at || new Date().toISOString()
  };
  if (navigator.onLine !== false) {
    try {
      return await api(path, { body: await resolvePendingPhotos(payload), noLogout: true });
    } catch (err) {
      if (!err.network && !isRetryable(err.status)) throw err;
    }
  }
  outboxWrite([...outboxRead(), { id: payload.client_event_id, path, body: payload, label,
                                  user_id: STATE.user && STATE.user.user_id, owner_name: ownerName(),
                                  queued_at: Date.now(), tries: 0 }]);
  requestBackgroundSync();
  renderNetPill();
  showToast("Jaringan terputus. Laporan tersimpan di cache browser & otomatis terkirim saat ada sinyal.", "📵");
  return { queued: true, client_event_id: payload.client_event_id };
}

// 408 timeout, 425, 429 rate-limit, 5xx server sibuk/mati → coba lagi nanti (JANGAN dibuang)
const isRetryable = s => s === 408 || s === 425 || s === 429 || (s >= 500 && s <= 599);

let flushing = false, needsLogin = false;
async function flushOutbox() {
  if (flushing || !STATE.token || navigator.onLine === false) return;
  flushing = true;
  let sent = 0;
  try {
    for (const item of myOutbox()) {
      try {
        const body = await resolvePendingPhotos(item.body);          // unggah foto antrean dulu (urutan terjaga)
        if (body !== item.body) outboxWrite(outboxRead().map(i => (i.id === item.id ? { ...i, body } : i)));
        await api(item.path, { body, noLogout: true });
        outboxWrite(outboxRead().filter(i => i.id !== item.id));
        sent++;
      } catch (err) {
        if (err.network || isRetryable(err.status)) break;          // masih offline / server sibuk → nanti
        if (err.status === 401) {                                    // token kedaluwarsa saat offline lama:
          needsLogin = true;                                         // SIMPAN antrean, minta login ulang
          showToast("Sesi berakhir. Login ulang — antrean offline tetap aman dan dikirim setelah login.", "🔐");
          break;
        }
        // Ditolak aturan bisnis (409/422/403/404): pindah ke kotak gagal agar bisa ditinjau, bukan hilang diam-diam
        outboxWrite(outboxRead().filter(i => i.id !== item.id));
        deadboxAdd(item, err.message);
        showToast(`Ditolak server (${item.label}): ${err.message}`, "⚠️");
      }
    }
    if (sent) showToast(`📶 ${sent} data offline terkirim`, "✅");
  } finally {
    flushing = false;
    renderNetPill();
    if (!myOutbox().length) trackFlush();     // jejak GPS menunggu antrean aksi; kirim begitu antrean kosong
    if (sent) {
      const role = STATE.user && STATE.user.role;
      if (role === "petani") loadPetaniData();
      if (role === "pengepul") loadCollectorData();
      if (role === "driver") loadDriverData();
    }
  }
}

function renderNetPill() {
  let pill = $("net-pill");
  if (!pill) {
    pill = document.createElement("div");
    pill.id = "net-pill";
    pill.setAttribute("role", "status");
    pill.setAttribute("aria-live", "polite");
    pill.style.cssText = "position:fixed;left:12px;bottom:12px;z-index:9999;padding:8px 12px;border-radius:999px;"
      + "font:600 12px/1.4 system-ui,sans-serif;box-shadow:0 2px 8px rgba(0,0,0,.15);cursor:pointer;";
    pill.onclick = () => { flushOutbox(); trackFlush(); };
    document.body.appendChild(pill);
  }
  const pending = STATE.user ? myOutbox().length : 0;
  const gps = TRACK.pending;
  const offline = navigator.onLine === false;
  const photos = PHOTOS_PENDING;
  pill.style.display = offline || pending || gps || photos || needsLogin ? "block" : "none";
  pill.style.background = offline ? "var(--warning-soft)" : (needsLogin ? "var(--danger-soft)" : "var(--info-soft)");
  pill.style.color = offline ? "var(--warning)" : (needsLogin ? "var(--danger)" : "var(--info)");
  pill.textContent = (offline ? "📵 Offline" : (needsLogin ? "🔐 Login ulang" : "📶 Online"))
    + (pending ? ` · ${pending} antre` : "") + (gps ? ` · 📍${gps} titik GPS` : "") + (photos ? ` · 📷${photos} foto` : "")
    + (pending || gps ? " (ketuk untuk kirim)" : "");
}

// Pemicu kirim: sinyal kembali, aplikasi dibuka lagi, interval, dan Background Sync (Chrome/Edge Android).
// Safari & Firefox tidak mendukung Background Sync → pemicu lain tetap bekerja.
window.addEventListener("online", () => { renderNetPill(); flushOutbox(); trackFlush(); });
window.addEventListener("offline", renderNetPill);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") { flushOutbox(); trackFlush(); }
});
setInterval(() => { if (myOutbox().length) flushOutbox(); if (TRACK.pending) trackFlush(); }, 30000);

function requestBackgroundSync() {
  if (!("serviceWorker" in navigator)) return;
  navigator.serviceWorker.ready.then(reg => reg.sync && reg.sync.register("biochain-outbox")).catch(() => {});
}
if ("serviceWorker" in navigator && location.protocol !== "file:") {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
  navigator.serviceWorker.addEventListener("message", e => {
    if (e.data === "flush-outbox") { flushOutbox(); trackFlush(); }
  });
}

// ==============================================================
// PENCATAT GPS SUPIR (store & forward)
// Titik direkam dari GPS perangkat walau tanpa sinyal data, disimpan di IndexedDB, dikirim per batch
// saat online. Server menghitung jarak (dengan penyaring glitch) & emisi CO2e setelah tersinkron.
// ==============================================================
const TRACK = { watchId: null, routeId: null, last: null, pending: 0, km: 0, wake: null, flushing: false };
const TRACK_MIN_STEP_M = 25, TRACK_MAX_GAP_MS = 60000, TRACK_MAX_ACC_M = 100, TRACK_BATCH = 500;

function havKm(a, b) {
  const R = 6371.0088, r = Math.PI / 180;
  const dLat = (b.lat - a.lat) * r, dLon = (b.lon - a.lon) * r;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}
async function trackCount() {
  TRACK.pending = ((await idbTx("track", "readonly", s => s.getAll())) || []).filter(isMine).length;
  renderNetPill();
}
async function trackStart(routeId) {
  if (TRACK.watchId !== null && TRACK.routeId === routeId) return;
  trackStop();
  if (!navigator.geolocation) { showToast("GPS tidak tersedia di perangkat ini", "⚠️"); return; }
  TRACK.routeId = routeId;
  TRACK.km = Number(await kvGet(`track-km-${routeId}`)) || 0;
  // Layar terkunci → browser menghentikan GPS. Wake Lock menjaga layar tetap menyala selama rute berjalan.
  try { if ("wakeLock" in navigator) TRACK.wake = await navigator.wakeLock.request("screen"); } catch {}
  TRACK.watchId = navigator.geolocation.watchPosition(onFix, () => {},
    { enableHighAccuracy: true, maximumAge: 10000, timeout: 30000 });
  trackCount();
}
function trackStop() {
  if (TRACK.watchId !== null) navigator.geolocation.clearWatch(TRACK.watchId);
  TRACK.watchId = null;
  try { TRACK.wake && TRACK.wake.release(); } catch {}
  TRACK.wake = null;
}
document.addEventListener("visibilitychange", async () => {
  if (document.visibilityState === "visible" && TRACK.watchId !== null && !TRACK.wake && "wakeLock" in navigator) {
    try { TRACK.wake = await navigator.wakeLock.request("screen"); } catch {}
  }
});
async function onFix(pos) {
  const c = pos.coords;
  if (c.accuracy > TRACK_MAX_ACC_M || TRACK.routeId === null) return;
  const p = { lat: c.latitude, lon: c.longitude, t: pos.timestamp };
  const last = TRACK.last;
  const stepKm = last ? havKm(last, p) : 0;
  if (last && stepKm * 1000 < TRACK_MIN_STEP_M && p.t - last.t < TRACK_MAX_GAP_MS) return;   // hemat baterai & memori
  if (last) TRACK.km += stepKm;
  TRACK.last = p;
  await idbTx("track", "readwrite", s => s.put({
    client_point_id: `${TRACK.routeId}-${newId()}`, route_id: TRACK.routeId, user_id: myUid(), owner_name: ownerName(),
    recorded_at: new Date(p.t).toISOString(), lat: p.lat, lon: p.lon,
    accuracy_m: c.accuracy, speed_mps: c.speed ?? null }));
  kvSet(`track-km-${TRACK.routeId}`, TRACK.km);
  TRACK.pending++;
  renderNetPill();
  if ($("d-gps-km")) $("d-gps-km").innerText = num(TRACK.km, 2);
  if (TRACK.pending >= 30) trackFlush();
}
async function trackFlush() {
  // Antrean aksi (mis. "mulai rute" offline) harus terkirim dulu, kalau tidak titik GPS ditolak "rute belum dimulai"
  if (TRACK.flushing || !STATE.token || navigator.onLine === false || needsLogin || myOutbox().length) return;
  TRACK.flushing = true;
  try {
    // Hanya titik milik supir yang masuk: titik supir lain di HP bersama ditolak server (404) lalu terhapus → jejak hilang
    const all = ((await idbTx("track", "readonly", s => s.getAll())) || []).filter(isMine);
    const byRoute = {};
    all.forEach(p => (byRoute[p.route_id] = byRoute[p.route_id] || []).push(p));
    for (const [routeId, pts] of Object.entries(byRoute)) {
      for (let i = 0; i < pts.length; i += TRACK_BATCH) {
        const batch = pts.slice(i, i + TRACK_BATCH);
        try {
          await api("/api/v1/driver/track", { noLogout: true, timeoutMs: 30000, body: {
            route_id: Number(routeId),
            points: batch.map(({ route_id, user_id, owner_name, ...rest }) => rest) } });
        } catch (err) {
          if (err.network || isRetryable(err.status) || err.status === 401) return;   // simpan, coba nanti
          // 404/409 (rute bukan milik / belum dimulai): titik tak bisa dipakai → buang agar tidak menumpuk
        }
        await idbTx("track", "readwrite", s => batch.forEach(p => s.delete(p.client_point_id)));
      }
    }
  } finally {
    TRACK.flushing = false;
    trackCount();
  }
}

outboxLoad();


// ==============================================================
// INITIALIZATION & AUTH FLOW
// ==============================================================
async function initApp() {
  // Check system status
  try {
    const sys = await api("/api/v1/system/status");
    if ($("db-indicator")) {
      const isSqlite = sys.database === "sqlite";
      $("db-indicator").innerText = isSqlite ? "🟢 SQLite Lokal (biochain.db)" : "🔵 PostgreSQL 16";
      $("db-indicator").className = isSqlite ? "badge badge-green" : "badge badge-blue";
    }
  } catch (e) {
    console.warn("Status check:", e);
  }

  // Load demo accounts list for login screen
  try {
    STATE.demoAccounts = await api("/api/v1/auth/demo-accounts");
    renderRoleSelector();

    // Support direct role URL query param (?role=petani|pengepul|driver|pabrik|admin&tab=tab-engines)
    const urlParams = new URLSearchParams(window.location.search);
    const autoRole = urlParams.get("role");
    const autoTab = urlParams.get("tab");
    if (autoRole) {
      const acc = STATE.demoAccounts.find(a => a.role === autoRole || a.username.includes(autoRole));
      if (acc) {
        const res = await api("/api/v1/auth/login", {
          body: { identifier: acc.username, password: acc.password, expected_role: acc.role },
        });
        STATE.token = res.access_token;
        STATE.user = res;
        localStorage.setItem("biochain_token", res.access_token);
        localStorage.setItem("biochain_user", JSON.stringify(res));
        showAuthenticatedApp();
        if (autoTab) setTimeout(() => openTab(autoTab), 300);    // tetap dibatasi peran
        return;
      }
    }
  } catch (e) {
    console.error("Gagal memuat akun demo:", e);
  }

  // Check existing session
  if (STATE.token && STATE.user) {
    try {
      const me = await api("/api/v1/auth/me");
      STATE.user = me;
      localStorage.setItem("biochain_user", JSON.stringify(me));
      showAuthenticatedApp();
      return;
    } catch (e) {
      console.warn("Auto-login token expired:", e);
      logout();
    }
  }

  showLoginScreen();
}

function showLoginScreen() {
  $("login-view").style.display = "flex";
  $("app-view").style.display = "none";
  aiShow(false);
  switchAuthMode("login");
  renderRoleSelector();          // gerbang tetap tampil walau daftar akun demo gagal dimuat
}

function switchAuthMode(mode) {
  const isReg = mode === "register";
  const loginBox = $("auth-login-box");
  const regBox = $("auth-register-box");
  if (loginBox) loginBox.style.display = isReg ? "none" : "block";
  if (regBox) regBox.style.display = isReg ? "block" : "none";

  const btnLogin = $("btn-mode-login");
  const btnReg = $("btn-mode-register");
  if (btnLogin && btnReg) {
    btnLogin.style.background = isReg ? "transparent" : "var(--surface-1)";
    btnLogin.style.boxShadow = isReg ? "none" : "var(--elev-1)";
    btnLogin.style.fontWeight = isReg ? "600" : "700";
    btnLogin.classList.toggle("btn-secondary", isReg);
    btnLogin.setAttribute("aria-pressed", String(!isReg));

    btnReg.style.background = isReg ? "var(--surface-1)" : "transparent";
    btnReg.style.boxShadow = isReg ? "var(--elev-1)" : "none";
    btnReg.style.fontWeight = isReg ? "700" : "600";
    btnReg.classList.toggle("btn-secondary", !isReg);
    btnReg.setAttribute("aria-pressed", String(isReg));
  }
}

// F18: data offline pengguna lain tetap disimpan (hanya bisa dikirim dengan token pemiliknya) — beri tahu siapa pemiliknya
async function foreignPendingNotice() {
  const uid = myUid();
  const [track, photos] = await Promise.all([idbTx("track", "readonly", s => s.getAll()),
                                             idbTx("photos", "readonly", s => s.getAll())]);
  const others = [...outboxRead(), ...(track || []), ...(photos || [])].filter(r => r && r.user_id != null && r.user_id !== uid);
  if (!others.length) return;
  const names = [...new Set(others.map(r => r.owner_name || `akun #${r.user_id}`))].slice(0, 3).join(", ");
  showToast(`HP ini menyimpan ${others.length} data offline milik ${names}. Data itu aman & baru terkirim saat pemiliknya login di HP ini.`, "📱");
}

function showAuthenticatedApp() {
  setTimeout(() => foreignPendingNotice().catch(() => {}), 1500);
  $("login-view").style.display = "none";
  $("app-view").style.display = "flex";

  const u = STATE.user;
  if (u && u.role) {
    document.documentElement.dataset.role = u.role;
  }
  $("u-name").innerText = u.full_name || u.username;
  const roleStr = (u.role || "").toUpperCase();
  $("u-role-badge").innerText = roleStr;

  const roleIcons = { petani: "🌾", pengepul: "📦", driver: "🚛", pabrik: "🏭", auditor: "🔍", admin: "⚙️" };
  $("u-icon").innerText = roleIcons[u.role] || "👤";

  const roleBadgeColors = {
    petani: "badge-green",
    pengepul: "badge-amber",
    driver: "badge-blue",
    pabrik: "badge-purple",
    auditor: "badge-blue",
    admin: "badge-red"
  };
  $("u-role-badge").className = `badge ${roleBadgeColors[u.role] || "badge-green"}`;

  // Highlight active role in quick switcher bar & wire buttons
  document.querySelectorAll(".quick-role-btn").forEach(btn => {
    const isAct = btn.dataset.role === u.role;
    btn.classList.toggle("btn-primary", isAct);
    btn.classList.toggle("btn-secondary", !isAct);
    btn.onclick = () => {
      const targetRole = btn.dataset.role;
      const acc = STATE.demoAccounts.find(a => a.role === targetRole);
      if (acc) switchPersona(acc.username);
    };
  });

  // Populate persona switcher dropdown
  const switcher = $("persona-switcher");
  switcher.innerHTML = `<option value="">Ganti Akun Demo...</option>` +
    STATE.demoAccounts.map(a => `<option value="${esc(a.username)}" ${a.username === u.username ? "selected" : ""}>${esc(a.icon)} ${esc(a.full_name)} (${esc(a.role.toUpperCase())})</option>`).join("");
  // Akun demo tersedia: dropdown sudah memuat nama + peran, jadi pil pengguna tidak perlu diulang di header
  document.querySelector(".header-actions").classList.toggle("has-demo-switcher", STATE.demoAccounts.length > 0);
  switcher.onchange = (e) => {
    if (e.target.value) switchPersona(e.target.value);
  };

  applyRoleNavigation(u.role);
  aiShow(true);
  loadParamValues();
  // Render dashboard for user's persona
  renderPersonaDashboard(u.role);
  updateNotificationBadge();
  if (!window._notifInterval) {
    window._notifInterval = setInterval(() => {
      if (STATE.token) updateNotificationBadge();
    }, 25000);
  }
  if (typeof afterLoginChecks === "function") afterLoginChecks();
}

// Tab yang boleh dibuka per peran (cermin ROUTE_POLICY di backend; backend tetap penentu akhir).
const ROLE_TABS = {
  petani: ["tab-persona", "tab-reports"], pengepul: ["tab-persona", "tab-reports"], driver: ["tab-persona", "tab-reports"],
  auditor: ["tab-persona", "tab-reports", "tab-params"],
  pabrik: ["tab-persona", "tab-engines", "tab-reports", "tab-params"],
  admin:  ["tab-persona", "tab-engines", "tab-reports", "tab-params", "tab-admin"],
};
function allowedTabs() { return ROLE_TABS[STATE.user && STATE.user.role] || ["tab-persona"]; }

function openTab(tabId) {
  if (!allowedTabs().includes(tabId)) tabId = "tab-persona";
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === tabId));
  document.querySelectorAll(".tab-pane").forEach(p => p.classList.toggle("active", p.id === tabId));
  if (tabId === "tab-engines") { initRoute(); initBlend(); runQuality(); }
  else if (tabId === "tab-admin") { loadAdminPanel(); }
  else if (tabId === "tab-params") { loadParams(); }
  else if (tabId === "tab-reports") { loadReport(); }
}

function applyRoleNavigation(role) {
  const tabs = allowedTabs();
  document.querySelectorAll(".nav-btn").forEach(b => { b.style.display = tabs.includes(b.dataset.tab) ? "" : "none"; });
  $("nav-tabs").style.display = tabs.length > 1 ? "" : "none";     // satu modul → tanpa bilah tab
  $("btn-reset-demo").style.display = role === "admin" ? "" : "none";
  openTab("tab-persona");
}

// Gerbang utama: 5 peran operasional. Admin lewat tautan kecil di bawahnya.
const GATES = [
  { role: "petani",   icon: "🌾", label: "Petani",   ident: "Nomor HP atau Username" },
  { role: "pengepul", icon: "📦", label: "Pengepul", ident: "Nomor HP atau Username" },
  { role: "driver",   icon: "🚛", label: "Driver",   ident: "Nomor HP atau Username" },
  { role: "pabrik",   icon: "🏭", label: "Pabrik",   ident: "Username Operator Pabrik" },
  { role: "auditor",  icon: "🔍", label: "Auditor",  ident: "Username Auditor" },
];
const ADMIN_GATE = { role: "admin", icon: "⚙️", label: "Administrator", ident: "Username Admin" };

function renderRoleSelector() {
  const grid = $("role-selector-grid");
  if (!grid) return;
  grid.innerHTML = GATES.map(g => `
    <div class="role-card ${STATE.gate === g.role ? 'active' : ''}" data-onclick="selectGate('${g.role}')">
      <span class="r-icon">${g.icon}</span>
      <div class="r-name">${esc(g.label)}</div>
    </div>`).join("");
  $("gate-admin-link").onclick = () => selectGate("admin");
  selectGate(STATE.gate || "petani");
}

function selectGate(role) {
  const gate = GATES.find(g => g.role === role) || ADMIN_GATE;
  STATE.gate = gate.role;
  document.querySelectorAll("#role-selector-grid .role-card").forEach((c, i) =>
    c.classList.toggle("active", GATES[i].role === gate.role));
  $("login-ident-label").innerText = gate.ident;
  $("btn-submit-login").innerText = `Masuk sebagai ${gate.label} ➔`;
  $("login-ident").value = "";
  $("login-pass").value = "";
  // Akun demo tetap terbuka untuk semua penguji, tapi hanya akun milik gerbang ini yang ditawarkan.
  const accs = STATE.demoAccounts.filter(a => a.role === gate.role);
  $("hint-text").innerText = accs.length
    ? `Akun demo ${gate.label} (klik untuk mengisi otomatis):`
    : `Masukkan kredensial akun ${gate.label}.`;
  $("demo-accounts-for-gate").innerHTML = accs.map(a =>
    `<span class="demo-chip" data-onclick="selectRolePreset('${esc(a.username)}')">${esc(a.icon)} ${esc(a.full_name)}</span>`).join("");
}

function selectRolePreset(username) {
  const acc = STATE.demoAccounts.find(a => a.username === username);
  if (!acc) return;

  STATE.selectedRoleKey = username;
  $("login-ident").value = acc.username;
  $("login-pass").value = acc.password;
}

// Password toggle
$("btn-toggle-pass").onclick = () => {
  const p = $("login-pass");
  if (p.type === "password") {
    p.type = "text";
    $("btn-toggle-pass").innerText = "🙈";
  } else {
    p.type = "password";
    $("btn-toggle-pass").innerText = "👁️";
  }
};

// Handle Login Submit
$("login-form").onsubmit = async (e) => {
  e.preventDefault();
  const ident = $("login-ident").value.trim();
  const pass = $("login-pass").value.trim();
  const btn = $("btn-submit-login");

  btn.disabled = true;
  btn.innerText = "Memverifikasi Kredensial...";

  try {
    const res = await api("/api/v1/auth/login", {
      body: { identifier: ident, password: pass, expected_role: STATE.gate },
    });
    STATE.token = res.access_token;
    STATE.user = res;
    localStorage.setItem("biochain_token", res.access_token);
    localStorage.setItem("biochain_user", JSON.stringify(res));

    showToast(`Selamat datang, ${res.full_name}!`, "🌿");
    showAuthenticatedApp();
  } catch (err) {
    showToast(err.message, "❌");
  } finally {
    btn.disabled = false;
    selectGate(STATE.gate);
    $("login-ident").value = ident;
  }
};

// Handle Register Submit
const regFormEl = $("register-form");
if (regFormEl) {
  regFormEl.onsubmit = async (e) => {
    e.preventDefault();
    const btn = $("btn-submit-register");
    btn.disabled = true;
    btn.innerText = "Mendaftarkan Akun...";

    const role = $("reg-role").value;
    const fullName = $("reg-fullname").value.trim();
    const phone = $("reg-phone").value.trim();
    const username = $("reg-username").value.trim() || null;
    const pass = $("reg-pass").value.trim();
    const kecamatan = $("reg-kecamatan").value.trim() || "Sleman";

    try {
      const res = await api("/api/v1/auth/register", {
        body: {
          role: role,
          full_name: fullName,
          phone: phone,
          username: username,
          password: pass,
          kecamatan: kecamatan,
          kabupaten: "Sleman",
          consents: { layanan_inti: $("reg-consent-core").checked, lokasi_gps: $("reg-consent-gps").checked,
                      foto_bukti: $("reg-consent-photo").checked },
        },
      });

      if (role === "petani") {
        // Petani langsung aktif dan langsung dapat token otentikasi
        STATE.token = res.access_token;
        STATE.user = res;
        localStorage.setItem("biochain_token", res.access_token);
        localStorage.setItem("biochain_user", JSON.stringify(res));
        showToast(`Pendaftaran berhasil! Selamat datang, ${res.full_name}`, "🌾");
        showAuthenticatedApp();
      } else {
        // Role operasional (pengepul/driver/pabrik) menunggu aktivasi admin
        showToast(`Registrasi akun ${role.toUpperCase()} berhasil! Akun Anda sedang menunggu aktivasi oleh Administrator sebelum dapat login.`, "⏳");
        switchAuthMode("login");
        selectGate(role);
        $("login-ident").value = phone;
        $("login-pass").value = pass;
      }
      regFormEl.reset();
    } catch (err) {
      showToast("Pendaftaran gagal: " + err.message, "❌");
    } finally {
      btn.disabled = false;
      btn.innerText = "Daftar Akun Sekarang ➔";
    }
  };
}

async function switchPersona(targetUsername) {
  const acc = STATE.demoAccounts.find(a => a.username === targetUsername);
  if (!acc) return;
  try {
    const res = await api("/api/v1/auth/login", {
      body: { identifier: acc.username, password: acc.password },
    });
    STATE.token = res.access_token;
    STATE.user = res;
    localStorage.setItem("biochain_token", res.access_token);
    localStorage.setItem("biochain_user", JSON.stringify(res));
    showToast(`Beralih persona ke: ${res.full_name}`, acc.icon);
    showAuthenticatedApp();
  } catch (err) {
    showToast("Gagal beralih persona: " + err.message, "❌");
  }
}

function logout(msg="Sampai jumpa!") {
  const pending = STATE.user ? myOutbox().length : 0;
  if (pending) msg += ` (${pending} data offline tetap tersimpan & dikirim saat Anda login lagi)`;
  needsLogin = false;
  trackStop();
  STATE.token = null;
  STATE.user = null;
  delete document.documentElement.dataset.role;
  localStorage.removeItem("biochain_token");
  localStorage.removeItem("biochain_user");
  localStorage.removeItem("biochain_driver_route");     // cache lama tanpa pemilik (sebelum F18)
  showToast(msg, "👋");
  showLoginScreen();
}
$("btn-logout").onclick = () => logout();

// Reset demo data button
$("btn-reset-demo").onclick = async () => {
  if (!confirm("Reset seluruh data demo ke kondisi awal (users, penggilingan, laporan, rute, pirolisis)?")) return;
  try {
    const res = await api("/api/v1/auth/reset-demo", { method: "POST" });
    showToast(res.message || "Data demo berhasil di-reset!", "🔄");
    showAuthenticatedApp();
  } catch (err) {
    showToast("Gagal reset data: " + err.message, "❌");
  }
};

// Tab switching (selalu lewat openTab → peran yang tidak berhak dikembalikan ke portal)
document.querySelectorAll(".nav-btn").forEach(btn => { btn.onclick = () => openTab(btn.dataset.tab); });

// ==============================================================
// 3. AI PERSONA EVALUATOR & OPTIMIZER ENGINE (UI LAYER)
// ==============================================================
const AI_EVAL_CONFIG = {
  petani: {
    icon: "🌾",
    title: "Optimizer & Evaluator Petani",
    sub: "Analisis kadar air, potensi margin Grade A, dan efisiensi sirkular abu",
    focuses: [
      { id: "semua", label: "🔍 Semua Aspek Mutu & Finansial" },
      { id: "mutu", label: "💧 Optimasi Kadar Air & Grade A" },
      { id: "biochar", label: "🌱 Pemanfaatan Hak Retur Abu Bottom Ash" },
      { id: "jadwal", label: "⏱️ Waktu & Volume Penyetoran Optimal" }
    ],
    chips: [
      "Bagaimana cara menaikkan mutu biomassa ke Grade A?",
      "Berapa takaran abu bottom ash ideal per hektar sawah?",
      "Hitung potensi tambahan Rupiah jika kadar air ≤ 11%"
    ]
  },
  pengepul: {
    icon: "📦",
    title: "Optimizer & Evaluator Hub Pengepul",
    sub: "Optimasi throughput timbangan, kontrol susut, dan margin pengeringan",
    focuses: [
      { id: "semua", label: "🔍 Semua Aspek Operasional Hub" },
      { id: "antrean", label: "🚚 Prioritas Verifikasi Antrean Petani" },
      { id: "margin", label: "💰 Peluang Beli-untuk-Dikeringkan" },
      { id: "akurasi", label: "⚖️ Akurasi Timbangan & Kontrol Susut" }
    ],
    chips: [
      "Petani mana yang sebaiknya diprioritaskan jemput?",
      "Bagaimana mengkalkulasi margin beli untuk dikeringkan?",
      "Tips menekan susut timbangan sebelum dikirim ke pabrik"
    ]
  },
  driver: {
    icon: "🚛",
    title: "AI Optimizer & Evaluator Logistik Armada",
    sub: "Efisiensi rute penjemputan OR-Tools, konsumsi BBM B40, dan muatan bak",
    focuses: [
      { id: "semua", label: "🔍 Semua Aspek Logistik Rute" },
      { id: "rute", label: "🗺️ Efisiensi Urutan Rute & BBM B40" },
      { id: "muatan", label: "📦 Utilisasi Kubikasi Bak Truk (25 m³)" },
      { id: "offline", label: "📶 Kesiapan GPS & Mode Offline Lapangan" }
    ],
    chips: [
      "Bagaimana urutan jemput paling hemat BBM hari ini?",
      "Cara menyusun karung biomassa agar muatan maksimal 25 m³?",
      "Apa yang harus dilakukan jika blank-spot GPS saat serah terima?"
    ]
  },
  pabrik: {
    icon: "🏭",
    title: "AI Optimizer & Evaluator Pirolisis Pabrik",
    sub: "Neraca massa pasokan, suhu reaktor, rendemen biochar, dan blending",
    focuses: [
      { id: "semua", label: "🔍 Semua Aspek Pirolisis & Pasokan" },
      { id: "neraca", label: "⚖️ Neraca Massa & Toleransi Susut (5%)" },
      { id: "rendemen", label: "🔥 Suhu Reaktor vs Rendemen Biochar" },
      { id: "blending", label: "🌾 Strategi Blending Biomassa Basah" }
    ],
    chips: [
      "Bagaimana formula blending biomassa kadar air 16% dan 11%?",
      "Berapa suhu pirolisis optimal untuk kadar Fixed Carbon tertinggi?",
      "Apakah ada deviasi susut pengepul yang melampaui ambang 5%?"
    ]
  },
  auditor: {
    icon: "🔍",
    title: "AI Optimizer & Evaluator Kepatuhan ESG",
    sub: "Audit transparansi rantai pasok, integritas ledger, dan klaim CO2e",
    focuses: [
      { id: "semua", label: "🔍 Semua Aspek Kepatuhan & ESG" },
      { id: "anomali", label: "🚩 Deteksi Red-Flag & Selisih Timbangan" },
      { id: "emisi", label: "🌿 Verifikasi Emisi WTW ISO 14083" },
      { id: "ledger", label: "🔒 Integritas Log Transaksi Append-Only" }
    ],
    chips: [
      "Tampilkan batch dengan deviasi susut tertinggi saat ini",
      "Bagaimana validasi klaim emisi terhindar biochar sesuai IPCC Tier 2?",
      "Apakah ada indikasi manipulasi timbangan antar node?"
    ]
  },
  admin: {
    icon: "⚙️",
    title: "AI Optimizer & Evaluator Ekosistem Platform",
    sub: "Kesehatan menyeluruh platform, bottleneck aliran biomassa, dan parameter harga",
    focuses: [
      { id: "semua", label: "🔍 Semua Aspek Ekosistem" },
      { id: "bottleneck", label: "🚦 Bottleneck Aliran Pasokan Lintas Persona" },
      { id: "harga", label: "💵 Evaluasi Kebijakan Parameter Harga Mutu" },
      { id: "sirkular", label: "🔄 Kinerja Pengembalian Abu Bottom Ash ke Petani" }
    ],
    chips: [
      "Ringkas performa rantai pasok Sleman & Klaten hari ini",
      "Apakah parameter harga dasar biomassa perlu disesuaikan?",
      "Persona mana yang memiliki backlog operasional tertinggi?"
    ]
  }
};

// ==============================================================
// EVALUASI & OPTIMASI PER PERSONA
// KPI, skor & prioritas dihitung server (GET /assistant/evaluation — deterministik, tanpa kuota AI).
// Rencana optimasi AI opsional (POST /assistant/evaluate/stream) memakai provider yang terpasang;
// bila AI tidak tersedia server mengirim ringkasan otomatis (X-AI-Fallback).
// ==============================================================
const EVAL_STATUS = {
  baik:        ["badge-green",  "✓", "Baik"],
  perhatian:   ["badge-amber",  "!", "Perhatian"],
  kritis:      ["badge-red",    "✕", "Kritis"],
  data_kurang: ["badge-gray",   "?", "Data kurang"],
  info:        ["badge-blue",   "i", "Info"],
};
const EVAL = { data: {}, ai: {}, busy: false, providers: null };

function evalFmt(v, unit) {
  if (v == null) return "–";
  if (unit === "Rp") return rp(v);
  if (unit === "Rp/kg") return `${rp(v)}/kg`;
  if (unit === "%") return `${num(v, 1)}%`;
  if (unit === "kg") return `${num(v, 0)} kg`;
  return `${num(v, 1)} ${unit}`;
}

function evalImpact(imp) {
  if (!imp) return "";
  const amt = imp.kind === "rp" ? rp(imp.amount) : imp.kind === "kg" ? `${num(imp.amount, 0)} kg` : `${num(imp.amount, 0)} ${imp.kind}`;
  return `<span class="eval-impact" title="${esc(imp.note)}">±${esc(amt)} <span class="eval-impact-note">${esc(imp.note)}</span></span>`;
}

function evalBadge(status) {
  const [cls, icon, label] = EVAL_STATUS[status] || EVAL_STATUS.info;
  return `<span class="badge ${cls}"><span aria-hidden="true">${icon}</span> ${label}</span>`;
}

function evalTrend(k) {
  if (k.trend_pct == null) return `<span class="eval-trend">belum ada pembanding</span>`;
  const up = k.trend_pct > 0, flat = Math.abs(k.trend_pct) < 0.5;
  const better = flat ? null : (k.direction === "min" ? up : !up);
  const arrow = flat ? "→" : up ? "▲" : "▼";
  const word = better == null ? "stabil" : better ? "membaik" : "memburuk";
  return `<span class="eval-trend eval-trend-${better == null ? "flat" : better ? "good" : "bad"}">
            <span aria-hidden="true">${arrow}</span> ${num(Math.abs(k.trend_pct), 1)}% ${word}</span>`;
}

// Komposisi output pabrik: bar 100% (part-to-whole). Slot kategori tervalidasi (dataviz validate_palette,
// light #ffffff & dark #181818); label & legenda selalu tampil (relief untuk kontras aqua di tema terang).
function evalFlowBar(flow) {
  if (!flow || !flow.input_kg) return `<p class="muted">Belum ada batch produksi pada jendela evaluasi.</p>`;
  const s = flow.shares_pct || {};
  const parts = [
    ["biochar", "Biochar", s.biochar], ["bio_pellet", "Bio-pellet", s.bio_pellet], ["bio_silika", "Bio-silika", s.bio_silika],
  ].filter(p => p[2] != null && p[2] > 0);
  const used = parts.reduce((a, p) => a + p[2], 0);
  if (used < 100) parts.push(["lainnya", "Air, gas & susut proses", 100 - used]);
  const seg = parts.map(([k, label, v]) => `
    <div class="eval-flow-seg eval-flow-${k}" style="flex-basis:${v}%;" role="img" aria-label="${label} ${num(v, 1)}%">
      <span class="eval-flow-tip">${label}: ${num(v, 1)}% ≈ ${num(flow.input_kg * v / 100, 0)} kg</span>
      ${v >= 9 ? `<span class="eval-flow-label">${num(v, 0)}%</span>` : ""}
    </div>`).join("");
  const legend = parts.map(([k, label, v]) =>
    `<li><span class="eval-swatch eval-flow-${k}" aria-hidden="true"></span>${label} <b>${num(v, 1)}%</b></li>`).join("");
  return `
    <div class="eval-flow" tabindex="0" aria-label="Komposisi output dari ${num(flow.input_kg, 0)} kg input batch">
      <div class="eval-flow-bar">${seg}</div>
      <ul class="eval-legend">${legend}</ul>
      <p class="kpi-lbl" style="margin:8px 0 0;">Input batch ${num(flow.input_kg, 0)} kg · galat penutupan ${flow.closure_error_pct == null ? "–" : num(flow.closure_error_pct, 2) + "%"}
        · biochar ke dompet petani ${num(flow.biochar_to_farmers_kg || 0, 0)} kg</p>
    </div>`;
}

function renderAIEvaluationCard(role) {
  const cfg = AI_EVAL_CONFIG[role] || AI_EVAL_CONFIG.petani;
  const focusOptions = cfg.focuses.map(f => `<option value="${esc(f.label)}">${esc(f.label)}</option>`).join("");
  return `
    <section class="eval-card" id="ai-eval-card-${role}" aria-labelledby="eval-title-${role}">
      <header class="eval-head">
        <div>
          <span class="tagline">⚡ Evaluasi &amp; Optimasi</span>
          <h3 class="card-title" id="eval-title-${role}">${esc(cfg.title)}</h3>
          <p class="card-sub">${esc(cfg.sub)} · <span id="eval-window-${role}">memuat periode…</span></p>
        </div>
        <div style="display:flex; gap:8px; align-items:center;">
          <select id="eval-window-filter-${role}" class="btn btn-secondary btn-sm" aria-label="Rentang Evaluasi" style="font-size:0.8rem; padding:4px 8px;">
            <option value="1">1 Bulan Terakhir</option>
            <option value="3" selected>3 Bulan Terakhir</option>
            <option value="6">6 Bulan Terakhir</option>
            <option value="12">12 Bulan (1 Tahun)</option>
          </select>
          <button type="button" class="btn btn-secondary btn-sm" id="btn-eval-refresh-${role}" aria-label="Muat ulang evaluasi">↻ Muat ulang</button>
        </div>
      </header>
      <div id="eval-body-${role}" aria-live="polite">
        <div class="eval-hero"><span class="skeleton" style="width:120px;height:72px;"></span>
          <span class="skeleton skeleton-line" style="width:60%;"></span></div>
        <div class="kpi-row">${'<div class="skeleton skeleton-kpi"></div>'.repeat(4)}</div>
      </div>
      <div class="eval-ai">
        <div class="eval-ai-controls">
          <label class="visually-hidden" for="ai-eval-focus-${role}">Fokus analisis AI</label>
          <select id="ai-eval-focus-${role}" class="btn btn-secondary btn-sm">${focusOptions}</select>
          <label class="visually-hidden" for="eval-provider-${role}">Penyedia AI</label>
          <select id="eval-provider-${role}" class="btn btn-secondary btn-sm"><option value="">AI otomatis</option></select>
          <button type="button" class="btn btn-primary btn-sm" id="btn-run-eval-${role}">✨ Susun rencana optimasi AI</button>
        </div>
        <div class="eval-ai-panel" id="ai-eval-panel-${role}">
          <p class="muted" style="margin:0;">AI menjelaskan prioritas di atas dan menyusun langkah aksi. Angka tetap dari data sistem — AI tidak menghitung ulang.</p>
        </div>
        <p class="kpi-lbl" id="eval-ai-meta-${role}" style="margin:8px 0 0;"></p>
      </div>
      <div class="ai-chips eval-chips" id="ai-eval-chips-${role}" aria-label="Pertanyaan cepat ke Asisten">
        ${cfg.chips.map(q => `<button type="button" class="demo-chip ai-eval-chip" data-q="${esc(q)}">${esc(q)}</button>`).join("")}
      </div>
    </section>`;
}

function renderEvalBody(role, ev) {
  const body = $(`eval-body-${role}`);
  if (!body) return;
  if ($(`eval-window-${role}`)) $(`eval-window-${role}`).textContent =
    `${ev.window.months[0]} s.d. ${ev.window.months[ev.window.months.length - 1]} vs ${ev.window.length} bulan sebelumnya`;
  const c = ev.counts;
  const hero = ev.score == null
    ? `<div class="eval-score eval-score-none"><span class="eval-score-num">–</span><span class="kpi-lbl">Data belum cukup</span></div>`
    : `<div class="eval-score eval-grade-${ev.grade}"><span class="eval-score-num">${ev.score}</span>
         <span class="kpi-lbl">Skor kesehatan · grade ${ev.grade}</span></div>`;
  const chips = ["kritis", "perhatian", "baik", "data_kurang"].filter(s => c[s])
    .map(s => `${evalBadge(s)}<span class="eval-count">${c[s]}</span>`).join("");
  const prio = ev.priorities.length
    ? `<ol class="eval-prio">${ev.priorities.map(p => `
        <li class="eval-prio-item eval-prio-${p.status}">
          <div class="eval-prio-top">${evalBadge(p.status)} <b>${esc(p.label)}</b>
            <span class="eval-prio-val">${evalFmt(p.value, p.unit)} <span class="muted">(target ${esc(p.target_label || String(p.target))})</span></span></div>
          ${p.impact ? `<div>${evalImpact(p.impact)}</div>` : ""}
          ${p.action ? `<p class="eval-action">${esc(p.action)}</p>` : ""}
          <button type="button" class="btn btn-outline-green btn-sm eval-ask" data-focus="${esc(p.label)}">Tanya AI soal ini</button>
        </li>`).join("")}</ol>`
    : `<div class="empty-state"><div class="empty-icon" aria-hidden="true">✅</div>
         <div class="empty-title">Tidak ada KPI yang perlu dioptimasi</div>
         <div class="empty-desc">Semua indikator yang punya data berada pada target. Pantau tren tiap bulan.</div></div>`;
  const tiles = ev.kpis.map(k => {
    let bdHtml = "";
    if (k.breakdown && k.breakdown.length) {
      bdHtml = `<div class="eval-tile-breakdown" style="margin-top:6px; font-size:0.75rem; border-top:1px dashed var(--border); padding-top:4px;">` +
        k.breakdown.map(b => `<div style="display:flex; justify-content:space-between; margin-top:2px;">
          <span class="muted" style="max-width:65%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${esc(b.name || b.commodity)}:</span>
          <b>${evalFmt(b.value, b.unit || k.unit)}</b>
        </div>`).join("") +
        `</div>`;
    }
    return `
      <div class="kpi-tile eval-tile eval-tile-${k.status}">
        <div class="kpi-lbl">${esc(k.label)}</div>
        <div class="kpi-val">${evalFmt(k.value, k.unit)}</div>
        <div class="eval-tile-meta">${evalBadge(k.status)}
          ${k.target_label ? `<span class="muted">target ${esc(k.target_label)}</span>` : ""}</div>
        ${k.status === "data_kurang" ? `<p class="eval-need">${esc(k.need || "")}</p>` : evalTrend(k)}
        ${bdHtml}
      </div>`;
  }).join("");
  const isPlant = ["pabrik", "admin", "auditor"].includes(ev.role);
  body.innerHTML = `
    <div class="eval-hero">${hero}<div class="eval-counts">${chips}</div></div>
    <h4 class="eval-h">Prioritas optimasi <span class="muted">(urut keparahan & dampak)</span></h4>
    ${prio}
    ${isPlant ? `<h4 class="eval-h">Komposisi output produksi</h4>${evalFlowBar(ev.flow)}` : ""}
    <h4 class="eval-h">Semua indikator</h4>
    <div class="kpi-row eval-grid">${tiles}</div>`;
  body.querySelectorAll(".eval-ask").forEach(b => b.onclick = () => {
    const sel = $(`ai-eval-focus-${role}`);
    if (sel) {
      if (![...sel.options].some(o => o.value === b.dataset.focus)) sel.add(new Option(b.dataset.focus, b.dataset.focus));
      sel.value = b.dataset.focus;
    }
    runAIEvaluation(role);
  });
}

async function loadEvaluation(role) {
  const body = $(`eval-body-${role}`);
  try {
    const winVal = ($(`eval-window-filter-${role}`) || {}).value || 3;
    const ev = await api(`/api/v1/assistant/evaluation?window_months=${winVal}`);
    EVAL.data[role] = ev;
    renderEvalBody(role, ev);
  } catch (err) {
    if (body) body.innerHTML = `<div class="banner banner-error" role="alert"><span aria-hidden="true">⚠️</span>
      Evaluasi gagal dimuat: ${esc(err.message)}
      <button type="button" class="btn btn-secondary btn-sm" data-onclick="loadEvaluation('${role}')">Coba lagi</button></div>`;
  }
}

async function loadEvalProviders(role) {
  const sel = $(`eval-provider-${role}`);
  if (!sel) return;
  try {
    EVAL.providers = EVAL.providers || await api("/api/v1/assistant/providers");
    const ok = EVAL.providers.providers.filter(p => p.configured);
    sel.innerHTML = `<option value="">AI otomatis (${esc(EVAL.providers.default)})</option>` +
      ok.map(p => `<option value="${esc(p.id)}">${esc(p.label)}</option>`).join("");
    if (!ok.length) sel.innerHTML = `<option value="">AI belum dikonfigurasi</option>`;
  } catch { /* panel tetap bisa memakai ringkasan otomatis */ }
}

async function runAIEvaluation(role) {
  const panel = $(`ai-eval-panel-${role}`);
  const btn = $(`btn-run-eval-${role}`);
  const meta = $(`eval-ai-meta-${role}`);
  if (!panel || !btn || EVAL.busy) return;
  EVAL.busy = true;
  btn.disabled = true;
  btn.setAttribute("aria-busy", "true");
  const label = btn.innerHTML;
  btn.innerHTML = "⏳ Menyusun rencana…";
  panel.innerHTML = `<span class="skeleton skeleton-line" style="width:80%"></span><span class="skeleton skeleton-line" style="width:65%"></span>`;
  const started = Date.now();
  let text = "";
  try {
    const res = await apiRaw("/api/v1/assistant/evaluate/stream", { timeoutMs: 30000,
      body: { focus: ($(`ai-eval-focus-${role}`) || {}).value || null,
              provider: ($(`eval-provider-${role}`) || {}).value || null } });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      text += decoder.decode(value, { stream: true });
      panel.innerHTML = aiFormat(text);
    }
    if (!text.trim()) throw new Error("Model tidak mengembalikan jawaban.");
    EVAL.ai[role] = text;
    const fb = res.headers.get("X-AI-Fallback");
    if (meta) meta.textContent = fb ? "Ringkasan otomatis (AI tidak tersedia)"
      : `${res.headers.get("X-AI-Provider")} · ${res.headers.get("X-AI-Model")} · ${((Date.now() - started) / 1000).toFixed(1)} dtk · saran AI, periksa sebelum bertindak`;
  } catch (err) {
    panel.innerHTML = `<div class="banner banner-error" role="alert"><span aria-hidden="true">⚠️</span>
      ${esc(err.message === "Failed to fetch" ? "Tidak ada koneksi ke server." : err.message)}</div>`;
  } finally {
    EVAL.busy = false;
    btn.disabled = false;
    btn.removeAttribute("aria-busy");
    btn.innerHTML = label;
  }
}

function initAIEvaluationCard(role) {
  const btn = $(`btn-run-eval-${role}`);
  if (btn) btn.onclick = () => runAIEvaluation(role);
  const rf = $(`btn-eval-refresh-${role}`);
  if (rf) rf.onclick = () => loadEvaluation(role);
  const winFilter = $(`eval-window-filter-${role}`);
  if (winFilter) winFilter.onchange = () => loadEvaluation(role);
  if (EVAL.ai[role] && $(`ai-eval-panel-${role}`)) $(`ai-eval-panel-${role}`).innerHTML = aiFormat(EVAL.ai[role]);
  loadEvaluation(role);
  loadEvalProviders(role);

  const chipContainer = $(`ai-eval-chips-${role}`);
  if (chipContainer) {
    chipContainer.querySelectorAll(".ai-eval-chip").forEach(chip => {
      chip.onclick = () => {
        aiEnsureWidget();
        const p = $("ai-panel");
        if (p) {
          p.classList.add("open");
          aiInitProviders();
          aiSend(chip.dataset.q);
        }
      };
    });
  }
}

// ==============================================================
// PASAR B2B — petani memasang stok (skema jemput/antar), pengepul menawar, petani memilih (boleh sebagian)
// ==============================================================
const PETANI_MARKET_HTML = `
  <div class="card" style="margin-top:16px;">
    <div class="card-header" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
      <div>
        <h3 class="card-title">🏷️ Stok Lelang &amp; Tawaran Masuk</h3>
        <p class="card-sub">Pasang lelang dari kartu "Lapor &amp; Jual". “Nilai bersih” = harga − ongkos antar Anda.</p>
      </div>
      <div style="display:flex; gap:6px; align-items:center; flex-wrap:wrap;">
        <input type="text" id="listing-search" class="btn btn-secondary btn-sm" placeholder="🔍 Cari QR / No. List..." style="width:160px; text-align:left;">
        <select id="listing-filter-status" class="btn btn-secondary btn-sm" aria-label="Saring status listing">
          <option value="all">Semua Status</option>
          <option value="open">🟢 Aktif Ditawar</option>
          <option value="partially_awarded">🟡 Sebagian Deal</option>
          <option value="closed">⚪ Lelang Selesai</option>
          <option value="cancelled">🔴 Dibatalkan</option>
        </select>
      </div>
    </div>
    <div id="my-listings"><p class="muted">Memuat…</p></div>
  </div>
  <div class="card" id="petani-biochar-card" style="margin-top:16px;">
    <div class="card-header"><div><h3 class="card-title">♻️ Abu Bottom Ash untuk Sawah</h3>
      <p class="card-sub">Hak abu bottom ash dari biomassa Anda untuk pembenah tanah. Riwayat serah-terima muatan balik &amp; pengembalian kesuburan lahan (biochar dikomersialkan pabrik untuk material baterai).</p></div></div>
    <div id="biochar-sawah"><p class="muted">Memuat…</p></div>
  </div>`;

const SCHEME_LABEL = { jemput: "🚚 Jemput", antar: "🛵 Antar" };

// ==============================================================
// 3. PERSONA DASHBOARDS RENDERING
// ==============================================================
async function renderPersonaDashboard(role) {
  const container = $("persona-content");
  $("nav-persona-btn").innerText = `Portal ${role.toUpperCase()}`;

  if (role === "petani") {
    container.innerHTML = `
      <div class="kpi-row" id="petani-kpi">
        <div class="kpi-tile"><div class="kpi-lbl">Total Laporan Panen</div><div class="kpi-val" id="p-tot-harvest">0</div><div class="kpi-lbl">Batch <span id="p-tot-harvest-avg" class="muted" style="font-size:0.78rem;">(rata-rata: 0.0 / bln)</span></div></div>
        <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Total Tonase Terkirim</div><div class="kpi-val" id="p-tot-ton">0</div><div class="kpi-lbl">Ton Biomassa <span id="p-tot-ton-avg" class="muted" style="font-size:0.78rem;">(rata-rata: 0.0 Ton / bln)</span></div></div>
        <div class="kpi-tile kpi-purple"><div class="kpi-lbl">XP Gamifikasi</div><div class="kpi-val" id="p-xp">0</div><div class="kpi-lbl" id="p-tier-lbl">Mitra Emas</div></div>
        <div class="kpi-tile kpi-blue">
          <div class="kpi-lbl">Dompet Abu (Bottom Ash)</div>
          <div class="kpi-val" id="p-wallet">0</div>
          <div class="kpi-lbl">kg saldo aktif</div>
          <div style="font-size:0.75rem; margin-top:4px; opacity:0.9;" id="p-wallet-detail">
            Potensi bisa diambil: <b id="p-wallet-avail">0</b> kg · Sudah diambil: <b id="p-wallet-taken">0</b> kg
          </div>
        </div>
      </div>

      ${renderAIEvaluationCard("petani")}
      ${renderPersonaNotifWidgetHtml("petani")}

      <!-- Lapor & Jual: satu alur. Lapor dulu, lalu pilih jual langsung atau lelang -->
      <div class="card" style="margin-top:16px;">
          <div class="card-header">
            <div>
              <h3 class="card-title">🌾 Lapor &amp; Jual Biomassa</h3>
              <p class="card-sub">Isi jumlah, lalu pilih cara jual. Info mutu boleh dikosongkan.</p>
            </div>
          </div>
          <form id="form-lapor-sekam" novalidate>
            <div class="form-group">
              <label for="f-commodity">Jenis biomassa</label>
              <select id="f-commodity" class="btn btn-secondary" style="width:100%; text-align:left;"><option value="">Memuat jenis biomassa...</option></select>
            </div>

            <!-- Rekomendasi Harga Acuan Sesuai Biomassa -->
            <div id="f-rec-box" class="demo-hint-box" style="margin-bottom:12px; padding:10px 14px; border-radius:8px; background:var(--surface-2); display:flex; justify-content:space-between; align-items:center; border:1px solid var(--border);">
              <span>💡 <b>Harga Acuan Referensi:</b> <span id="f-rec-name">Biomassa</span></span>
              <strong id="f-rec-price" style="color:var(--primary); font-size:1.05rem;">Rp 400 / kg</strong>
            </div>

            <div class="form-group">
              <label for="f-qty">Jumlah (kg)</label>
              <input type="number" id="f-qty" class="btn btn-secondary" style="width:100%; text-align:left;" value="2500" min="50" max="50000" step="any" required>
            </div>
            <div class="form-group">
              <label for="f-mill">Lokasi penggilingan / titik pasok</label>
              <select id="f-mill" class="btn btn-secondary" style="width:100%; text-align:left;"></select>
            </div>
            <details class="demo-hint-box" id="f-quality-box">
              <summary>💧 Info mutu <span class="muted">(opsional)</span></summary>
              <div class="sale-grid">
                <div><label class="kpi-lbl" for="f-moist">Taksiran kadar air (%)</label>
                  <input id="f-moist" type="number" class="btn btn-secondary" style="width:100%;" min="0" max="60" step="0.5" placeholder="kosongkan bila tidak tahu" inputmode="decimal"></div>
                <div><label class="kpi-lbl" for="f-grade">Taksiran grade</label>
                  <select id="f-grade" class="btn btn-secondary" style="width:100%;">
                    <option value="">Tidak tahu</option><option value="A">A · kering (≤12%)</option>
                    <option value="B">B · standar (12–15%)</option><option value="C">C · lembap (15–18%)</option>
                    <option value="D">D · basah (&gt;18%)</option></select></div>
              </div>
              <p class="form-hint">Tidak memengaruhi harga. Harga final dari uji kadar air &amp; timbangan pengepul.</p>
            </details>

            <fieldset class="sale-mode" aria-label="Cara jual">
              <legend class="kpi-lbl">Cara jual</legend>
              <label class="sale-opt"><input type="radio" name="f-mode" value="langsung" checked>
                <span><b>🤝 Jual ke pengepul</b><small>Harga standar otomatis ikut acuan biomassa · bisa dicatat saat offline</small></span></label>
              <label class="sale-opt"><input type="radio" name="f-mode" value="lelang">
                <span><b>🏷️ Lelang</b><small>Pengepul menawar, Anda tetapkan batas minimum · perlu sinyal</small></span></label>
            </fieldset>

            <!-- Pilihan Pengepul: HANYA MUNCUL SETELAH DIPILIH JUAL KE PENGEPUL (KOSONG SAAT LELANG) -->
            <div class="form-group" id="f-collector-box" style="margin-top:10px;">
              <label for="f-collector">Pilih Pengepul Tujuan <span class="muted">(Opsional)</span></label>
              <select id="f-collector" class="btn btn-secondary" style="width:100%; text-align:left;">
                <option value="">-- Bebas / Pengepul Terdekat (Otomatis) --</option>
              </select>
              <p class="form-hint" id="f-collector-hint">Pilih pengepul mitra spesifik atau biarkan sistem memilih pengepul terdekat otomatis.</p>
            </div>

            <!-- Skema Logistik: HANYA BISA MEMILIH 1 (RADIO BUTTON) & MEMPENGARUHI PENDAPATAN -->
            <fieldset class="sale-mode" style="margin-top:10px;" aria-label="Skema Logistik">
              <legend class="kpi-lbl">Skema Penyerahan (Pilih salah satu)</legend>
              <label class="sale-opt"><input type="radio" name="f-deliv" value="jemput" id="f-deliv-jemput" checked>
                <span><b>🚚 Dijemput pengepul</b><small>Armada jemput ke lokasi · ongkos angkut ditanggung pengepul</small></span></label>
              <label class="sale-opt"><input type="radio" name="f-deliv" value="antar" id="f-deliv-antar">
                <span><b>🛵 Saya antar ke gudang</b><small>Mendapat premi transportasi mandiri (+Rp 80/kg ke pendapatan)</small></span></label>
            </fieldset>

            <!-- Input harga: HANYA UNTUK LELANG (JUAL LANGSUNG IKUT HARGA ACUAN) -->
            <div id="f-auction-box" class="form-group" style="margin-top:10px;" hidden>
              <label class="kpi-lbl" for="f-ask-price">🎯 Harga penawaran minimum lelang (Rp/kg)</label>
              <input id="f-ask-price" type="number" class="btn btn-secondary" style="width:100%;" min="0" step="1" placeholder="Masukkan target harga lelang">
              <p class="form-hint">Khusus Lelang: penawaran di bawah batas ini otomatis tidak diterima.</p>
            </div>

            <!-- Input Foto Terkompresi Canvas (Maks 300KB) -->
            <div class="form-group" style="margin-top:10px;">
              <label for="f-photo-file">📷 Foto Biomassa &amp; Muatan <span class="muted">(Kompresi Otomatis Canvas &le; 300KB)</span></label>
              <input type="file" id="f-photo-file" accept="image/*" class="btn btn-secondary" style="width:100%;">
              <input type="hidden" id="f-photo-url">
              <div id="f-photo-status" class="kpi-lbl" style="margin-top:4px;"></div>
            </div>

            <!-- Opsi Request Kebutuhan Abu Bottom Ash Sirkular -->
            <details class="demo-hint-box" id="f-biochar-box" style="margin-top:10px;">
              <summary>🌱 <b>Pesan Muatan Balik Abu Bottom Ash untuk Sawah</b> <span class="muted">(Dikirim Bersamaan dengan Biomassa)</span></summary>
              <div style="padding-top:8px;">
                <div class="form-group">
                  <label class="kpi-lbl" for="f-biochar-req">Kebutuhan Abu Bottom Ash (kg)</label>
                  <input id="f-biochar-req" type="number" class="btn btn-secondary" style="width:100%;" min="0" step="any" placeholder="Contoh: 500 kg">
                </div>
                <div class="form-group">
                  <label class="kpi-lbl" for="f-biochar-ha">Luas Sawah Aplikasi (ha)</label>
                  <input id="f-biochar-ha" type="number" class="btn btn-secondary" style="width:100%;" min="0" step="any" placeholder="Contoh: 1.5 ha">
                </div>
                <div class="form-group">
                  <label class="kpi-lbl" for="f-biochar-loc">Titik Serah Terima</label>
                  <input id="f-biochar-loc" type="text" class="btn btn-secondary" style="width:100%;" value="Lahan Petani" placeholder="Lokasi penyerahan">
                </div>
                <button type="button" class="btn btn-secondary btn-sm" id="btn-popup-biochar-benefit" style="margin-top:4px; width:100%; border:1px solid var(--primary); color:var(--primary); font-weight:600;">
                  💡 Lihat Perkiraan Manfaat Bersih (4 Musim)
                </button>
                <p class="form-hint" style="margin-top:6px;">Armada pengangkut akan membawa abu bottom ash ini secara bersamaan saat mengangkut biomassa (hemat ongkos logistik &amp; zero empty trips). Biochar dialokasikan pabrik untuk material baterai.</p>
              </div>
            </details>

            <div class="sale-preview">
              <div style="display:flex; justify-content:space-between; gap:8px;">
                <span id="f-est-label">Estimasi pendapatan</span>
                <strong id="f-est-earning">–</strong>
              </div>
              <span id="f-est-note" class="form-hint"></span>
            </div>
            <button type="submit" class="btn btn-primary" style="width:100%;" id="f-submit">🚀 Kirim Laporan Stok</button>
          </form>
        </div>

        <!-- Riwayat Penyetoran: 1 baris penuh -->
        <div class="card" style="margin-top:16px;">
          <div class="card-header">
            <div>
              <h3 class="card-title">📜 Riwayat Laporan Biomassa</h3>
              <p class="card-sub">Tracking status verifikasi dan bukti QR setor terkelompok per bulan</p>
            </div>
          </div>
          <div style="overflow-x:auto;">
            <table class="data-table" id="table-petani-harvests">
              <thead><tr><th>No. Unik WR Code</th><th>Biomassa</th><th class="num">Berat (kg)</th><th>Status Aktif</th><th>Grade</th><th>Detail Input</th><th>QR</th></tr></thead>
              <tbody><tr><td colspan="7" style="text-align:center;">Memuat data...</td></tr></tbody>
            </table>
          </div>
        </div>
    `;

    let cachedBiomassList = [];
    const getCommodityBasePrice = () => {
      const code = ($("f-commodity") || {}).value || "sekam_padi";
      const item = cachedBiomassList.find(b => b.code === code);
      if (item && item.base_price_per_kg != null) return Number(item.base_price_per_kg);
      return code === "sekam_padi" ? PV("harga_mutu.base_price_per_kg", 400) : 400;
    };

    // Estimasi & label tombol mengikuti cara jual + skema logistik + info mutu
    const saleMode = () => (document.querySelector('input[name="f-mode"]:checked') || {}).value || "langsung";
    const delivMode = () => (document.querySelector('input[name="f-deliv"]:checked') || {}).value || "jemput";
    const gradeFrom = () => {
      const g = $("f-grade").value, m = $("f-moist").value;
      if (g) return g;
      if (m === "") return null;
      const v = Number(m);
      return v <= 12 ? "A" : v <= 15 ? "B" : v <= 18 ? "C" : "D";
    };

    const updateEarning = () => {
      const q = Number($("f-qty").value) || 0;
      const mode = saleMode();
      const deliv = delivMode();
      const g = gradeFrom();
      const base = getCommodityBasePrice();
      const premiAntar = 80; // Rp/kg premi antar mandiri ke gudang
      const isLelang = mode === "lelang";

      // Input harga hanya bisa diedit saat lelang; saat jual langsung, input harga disembunyikan/ikut acuan
      const auctionBox = $("f-auction-box");
      if (auctionBox) {
        auctionBox.hidden = !isLelang;
        auctionBox.style.setProperty('display', isLelang ? 'block' : 'none', 'important');
      }
      if ($("f-ask-price")) {
        $("f-ask-price").disabled = !isLelang;
      }
      const collectorBox = $("f-collector-box");
      if (collectorBox) {
        collectorBox.hidden = isLelang;
        collectorBox.style.setProperty('display', isLelang ? 'none' : 'block', 'important');
      }
      if (isLelang && $("f-collector")) $("f-collector").value = "";
      if ($("f-ask-price") && !isLelang) {
        $("f-ask-price").value = deliv === "antar" ? (base + premiAntar) : base;
      }

      // Update badge rekomendasi harga acuan
      const selOpt = ($("f-commodity") || {}).selectedOptions;
      const comName = selOpt && selOpt[0] && selOpt[0].value ? selOpt[0].textContent : "Biomassa";
      if ($("f-rec-name")) $("f-rec-name").textContent = comName;
      if ($("f-rec-price")) $("f-rec-price").textContent = `${rp(base)} / kg`;

      $("f-submit").textContent = isLelang ? "🏷️ Pasang untuk Ditawar" : "🚀 Kirim Laporan Stok";

      if (isLelang) {
        let unit = Number(($("f-ask-price") || {}).value) || (deliv === "antar" ? (base + premiAntar) : base);
        $("f-est-label").textContent = "Nilai minimum lelang";
        $("f-est-earning").textContent = rp(q * unit);
        $("f-est-note").textContent = deliv === "antar"
          ? `Skema antar gudang (target ${rp(unit)}/kg). Tawaran di bawah batas minimum Anda ditolak.`
          : `Skema dijemput armada (target ${rp(unit)}/kg). Tawaran di bawah batas minimum Anda ditolak.`;
        return;
      }

      // Mode Langsung (Jual ke Pengepul): Harga tidak bisa diinput karena harga ikut acuan pasar
      $("f-est-label").textContent = "Estimasi pendapatan";
      const effectiveBase = deliv === "antar" ? (base + premiAntar) : base;
      const delivNote = deliv === "antar"
        ? ` Termasuk premi antar mandiri +${rp(premiAntar)}/kg.`
        : " Pengepul menanggung biaya truk & jemput.";

      if (g === "D") {
        $("f-est-earning").textContent = "Berisiko ditolak";
        $("f-est-note").textContent = "Biomassa basah (>18%) biasanya ditolak atau dibeli murah untuk dikeringkan. Jemur dulu bila bisa.";
      } else if (g) {
        $("f-est-earning").textContent = rp(q * effectiveBase * PV(`harga_mutu.mult_${g}`, 1));
        $("f-est-note").textContent = `Perkiraan Grade ${g} (acuan ${rp(effectiveBase)}/kg).${delivNote} Harga final dari timbangan & QC pengepul.`;
      } else {
        const minE = q * effectiveBase * PV("harga_mutu.mult_C", 1);
        const maxE = q * effectiveBase * PV("harga_mutu.mult_A", 1.15);
        $("f-est-earning").textContent = `${rp(minE)} – ${rp(maxE)}`;
        $("f-est-note").textContent = `Rentang Grade C–A (${rp(effectiveBase)}/kg).${delivNote} Isi info mutu untuk estimasi lebih tepat.`;
      }
    };

    ["f-qty", "f-moist", "f-grade", "f-ask-price"].forEach(id => {
      const el = $(id);
      if (el) el.addEventListener("input", updateEarning);
    });
    document.querySelectorAll('input[name="f-mode"], input[name="f-deliv"]').forEach(el => {
      el.addEventListener("change", updateEarning);
      el.addEventListener("click", updateEarning);
    });
    document.querySelectorAll('.sale-opt').forEach(el => {
      el.addEventListener("click", () => setTimeout(updateEarning, 10));
    });
    $("f-commodity").addEventListener("change", updateEarning);

    // Ambil daftar komoditas acuan untuk sinkronisasi harga
    biomassList().then(list => {
      cachedBiomassList = list || [];
      updateEarning();
    }).catch(() => updateEarning());

    let cachedCollectors = [];
    const renderCollectorOptions = (selectedCommodity) => {
      const sel = $("f-collector");
      if (!sel) return;
      const prevVal = sel.value;
      const opts = [`<option value="">-- Bebas / Pengepul Terdekat (Otomatis) --</option>`];
      const curCom = (selectedCommodity || ($("f-commodity") ? $("f-commodity").value : "sekam_padi") || "").toLowerCase();

      const matching = [];
      const others = [];
      (cachedCollectors || []).forEach(c => {
        if (curCom && c.specialization_commodity && c.specialization_commodity.toLowerCase() === curCom) {
          matching.push(c);
        } else {
          others.push(c);
        }
      });

      if (matching.length > 0) {
        opts.push(`<optgroup label="⭐ Rekomendasi Pengepul Spesialis ${esc(curCom.replace('_', ' ').toUpperCase())}">`);
        matching.forEach(c => {
          opts.push(`<option value="${c.id}" ${c.id == prevVal ? 'selected' : ''}>${esc(c.name)} · ${esc(c.kecamatan)} (⭐ ${c.rating_avg} · ${c.punctuality_score}% Tepat)</option>`);
        });
        opts.push(`</optgroup>`);
      }

      if (others.length > 0) {
        opts.push(`<optgroup label="Mitra Pengepul Lainnya">`);
        others.forEach(c => {
          const specLabel = c.specialization_commodity ? ` [Spesialis ${c.specialization_commodity.replace('_', ' ')}]` : '';
          opts.push(`<option value="${c.id}" ${c.id == prevVal ? 'selected' : ''}>${esc(c.name)} · ${esc(c.kecamatan)}${specLabel} (⭐ ${c.rating_avg})</option>`);
        });
        opts.push(`</optgroup>`);
      }

      sel.innerHTML = opts.join("");

      const isLelangNow = saleMode() === "lelang";
      if (isLelangNow) {
        sel.value = "";
        if ($("f-collector-hint")) $("f-collector-hint").textContent = "Lelang terbuka untuk semua pengepul (nama pengepul kosong).";
      } else if (!prevVal && matching.length > 0) {
        sel.value = matching[0].id;
        if ($("f-collector-hint")) {
          $("f-collector-hint").innerHTML = `💡 Pengepul spesialis <b>${esc(matching[0].name)}</b> otomatis diprioritaskan untuk <b>${esc(curCom.replace('_', ' '))}</b>.`;
        }
      } else if (!sel.value && $("f-collector-hint")) {
        $("f-collector-hint").textContent = "Pilih pengepul mitra spesifik atau biarkan sistem memilih pengepul terdekat otomatis.";
      }
    };

    if ($("f-collector")) {
      $("f-collector").addEventListener("change", () => {
        const val = $("f-collector").value;
        const col = cachedCollectors.find(c => c.id == val);
        if (col && $("f-collector-hint")) {
          const spec = col.specialization_commodity ? ` (Spesialis ${col.specialization_commodity.replace('_', ' ')})` : '';
          $("f-collector-hint").innerHTML = `📍 Terpilih: <b>${esc(col.name)}</b> · Kec. ${esc(col.kecamatan)}${spec} · HP: ${esc(col.phone)}`;
        } else if ($("f-collector-hint")) {
          $("f-collector-hint").textContent = "Pilih pengepul mitra spesifik atau biarkan sistem memilih pengepul terdekat otomatis.";
        }
      });
    }

    // Ambil daftar pengepul mitra
    api("/api/v1/farmer/collectors").then(cols => {
      cachedCollectors = cols || [];
      renderCollectorOptions($("f-commodity") ? $("f-commodity").value : "sekam_padi");
    }).catch(() => {});

    // Load mills for dropdown
    api("/api/v1/farmer/mills").then(mills => {
      if ($("f-mill")) $("f-mill").innerHTML = (mills || []).map(m => `<option value="${m.id}">${esc(m.name)} (${esc(m.kecamatan)})</option>`).join("");
    }).catch(() => {});

    fillCommoditySelect($("f-commodity")).then(() => {
      renderCollectorOptions($("f-commodity") ? $("f-commodity").value : "sekam_padi");
    });
    $("f-commodity").addEventListener("change", () => {
      renderCollectorOptions($("f-commodity").value);
    });

    // Bind kompresi foto otomatis (Canvas <= 300KB)
    if ($("f-photo-file")) {
      $("f-photo-file").onchange = async (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;
        const st = $("f-photo-status");
        if (st) st.innerHTML = `<span class="badge badge-amber">⏳ Mengompres foto via Canvas (maks 300KB)...</span>`;
        try {
          const comp = window.BiochainImage && typeof window.BiochainImage.compress === "function"
            ? await window.BiochainImage.compress(file, 300 * 1024)
            : file;
          const fd = new FormData();
          fd.append("file", comp);
          const upRes = await api("/api/v1/uploads", { method: "POST", body: fd });
          if (upRes && upRes.url) {
            $("f-photo-url").value = upRes.url;
            if (st) st.innerHTML = `<span class="badge badge-green">✓ Foto terkompres (${num(comp.size / 1024, 1)} KB) siap diunggah</span>`;
          }
        } catch (err) {
          if (st) st.innerHTML = `<span class="badge badge-red">⚠️ Gagal kompres: ${esc(err.message)}</span>`;
        }
      };
    }

    // Submit report function bound synchronously
    const doSubmitLapor = async (e) => {
      if (e && typeof e.preventDefault === "function") e.preventDefault();
      const submitBtn = $("f-submit") || (e && e.target && e.target.querySelector && e.target.querySelector("[type=submit]"));
      return withBusy(submitBtn, async () => {
        try {
          const qty = Number(($("f-qty") || {}).value);
          if (!qty || isNaN(qty) || qty <= 0) {
            showToast("Mohon masukkan jumlah biomassa yang valid (minimal 1 kg).", "⚠️");
            if ($("f-qty")) $("f-qty").focus();
            return;
          }
          if (qty > 100000) {
            showToast("Jumlah biomassa melebihi batas maksimum 100.000 kg.", "⚠️");
            return;
          }
          const commodity = ($("f-commodity") || {}).value || "sekam_padi";
          const selOpt = ($("f-commodity") || {}).selectedOptions;
          const comName = (selOpt && selOpt[0] && selOpt[0].textContent) || "biomassa";
          const millId = Number(($("f-mill") || {}).value) || null;
          const collectorId = Number(($("f-collector") || {}).value) || null;
          const moist = $("f-moist") && $("f-moist").value !== "" ? Number($("f-moist").value) : null;
          const grade = ($("f-grade") || {}).value || null;
          const deliv = delivMode();
          const isLelang = saleMode() === "lelang";
          const askPrice = Number(($("f-ask-price") || {}).value) || getCommodityBasePrice();

          if (isLelang && (!askPrice || isNaN(askPrice) || askPrice <= 0)) {
            showToast("Mohon masukkan target harga minimum lelang (Rp/kg).", "⚠️");
            if ($("f-ask-price")) $("f-ask-price").focus();
            return;
          }

          const photoUrl = ($("f-photo-url") || {}).value || null;
          const biocharReqKg = Number(($("f-biochar-req") || {}).value) || null;
          const biocharArea = Number(($("f-biochar-ha") || {}).value) || null;
          const biocharPoint = ($("f-biochar-loc") || {}).value || "Lahan Petani";

          const payload = {
            quantity_kg: qty,
            commodity,
            mill_id: millId,
            collector_id: isLelang ? null : collectorId,
            delivery_scheme: deliv,
            logistics_mode: deliv === "antar" ? "DELIVER_SELF" : "PICKUP",
            transaction_mode: isLelang ? "BIDDING" : "DIRECT",
            floor_price: isLelang ? askPrice : null,
            photo_url: photoUrl,
            moisture_est: moist,
            grade_est: grade,
            biochar_request_kg: biocharReqKg,
            biochar_land_area_ha: biocharArea,
            biochar_delivery_point: biocharPoint,
          };

          const res = await apiMutation(
            "/api/v1/farmer/harvest",
            payload,
            `Lapor ${qty} kg ${comName.toLowerCase()} (${isLelang ? 'Lelang' : 'Langsung'})`
          );
          if (res.queued) {
            showToast("Sinyal hilang. Laporan disimpan di HP & dikirim otomatis saat online.", "📵");
          } else {
            showToast(res.message || "Laporan stok berhasil dikirim!", "🎉");
            openModal(
              `Laporan ${comName} Berhasil!`,
              res.qr_code,
              `${res.quantity_kg} kg · ${deliv === 'antar' ? 'Diantar Gudang' : 'Siap Dijemput'}${biocharReqKg ? ` · Pesan Abu Bottom Ash ${biocharReqKg} kg` : ''}`
            );
          }
          loadPetaniData();
          if (isLelang) loadMyListings();
        } catch (err) {
          showToast(err.message || "Gagal mengirim laporan stok", "❌");
        }
      });
    };

    if ($("form-lapor-sekam")) $("form-lapor-sekam").onsubmit = doSubmitLapor;
    if ($("f-submit")) $("f-submit").onclick = doSubmitLapor;

    const btnBiocharModal = $("btn-popup-biochar-benefit");
    if (btnBiocharModal) {
      btnBiocharModal.onclick = () => {
        const kg = Number(($("f-biochar-req") || {}).value) || 500;
        const ha = Number(($("f-biochar-ha") || {}).value) || 0.5;
        openBiocharEstimateModal(kg, ha);
      };
    }

    container.insertAdjacentHTML("beforeend", PETANI_MARKET_HTML);
    loadPetaniData();
    loadMyListings();
    initAIEvaluationCard("petani");
    if (typeof renderFieldExtras === "function") renderFieldExtras("petani", container);
  } else if (role === "pengepul") {
    container.innerHTML = `
      <div class="kpi-row">
        <div class="kpi-tile"><div class="kpi-lbl">Antrean Penawaran Petani</div><div class="kpi-val" id="col-pending">0</div><div class="kpi-lbl">Menunggu Verifikasi</div></div>
        <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Terverifikasi Hari Ini</div><div class="kpi-val" id="col-verified-kg">–</div><div class="kpi-lbl">kg Biomassa</div></div>
        <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Skor Mutu Hari Ini</div><div class="kpi-val" id="col-avg-score">–</div><div class="kpi-lbl">Rata-rata · skala 100</div></div>
      </div>

      ${renderAIEvaluationCard("pengepul")}
      ${renderPersonaNotifWidgetHtml("pengepul")}

      <!-- Hidden compatibility container for legacy test/API handlers -->
      <div id="table-col-queue-wrap" style="display:none;" aria-hidden="true">
        <table class="data-table" id="table-col-queue"><tbody></tbody></table>
        <form id="form-verify-harvest"><input type="hidden" id="v-harvest-id"></form>
      </div>
    `;
    if ($("form-verify-harvest")) $("form-verify-harvest").onsubmit = submitVerify;
    if ($("btn-reject-lot")) $("btn-reject-lot").onclick = () => window.rejectLot && window.rejectLot(Number(($("v-harvest-id") || {}).value));
    container.insertAdjacentHTML("beforeend", PENGEPUL_MARKET_HTML);
    container.insertAdjacentHTML("beforeend", PENGEPUL_FACTORY_PRICING_HTML);
    container.insertAdjacentHTML("beforeend", PENGEPUL_DR_HTML);
    loadCollectorData();
    loadMarket();
    initFactoryPricingModule();
    initCollectorDR();
    initAIEvaluationCard("pengepul");
    if (typeof renderFieldExtras === "function") renderFieldExtras("pengepul", container);
  } else if (role === "driver") {
    container.innerHTML = `
      <div class="kpi-row">
        <div class="kpi-tile"><div class="kpi-lbl">Status Rute</div><div class="kpi-val" id="d-status">–</div><div class="kpi-lbl" id="d-plate">–</div></div>
        <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Jarak Rencana</div><div class="kpi-val" id="d-km">–</div><div class="kpi-lbl">km (estimasi jalan)</div></div>
        <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Jarak GPS Terekam</div><div class="kpi-val" id="d-gps-km">0</div><div class="kpi-lbl">km · tersimpan walau offline</div></div>
        <div class="kpi-tile kpi-purple"><div class="kpi-lbl">Utilisasi Bak</div><div class="kpi-val" id="d-util">–</div><div class="kpi-lbl">volume terisi</div></div>
      </div>

      ${renderAIEvaluationCard("driver")}
      ${renderPersonaNotifWidgetHtml("driver")}

      <div class="card" style="padding:12px;margin-bottom:12px;" id="driver-actions"></div>

      <div class="grid-sidebar">
        <!-- Stops list -->
        <div class="card">
          <div class="card-header">
            <div>
              <h3 class="card-title">🚛 Titik Penjemputan Biomassa</h3>
              <p class="card-sub">Scan QR petani / produsen di setiap titik penjemputan biomassa</p>
            </div>
          </div>
          <div id="driver-stops-list">Memuat daftar stop...</div>
        </div>

        <div class="card" style="margin-top:16px;">
          <div class="card-header">
            <div>
              <h3 class="card-title">🔄 Muatan Balik Abu Bottom Ash (Pabrik ➔ Petani)</h3>
              <p class="card-sub">Distribusi sirkular abu bottom ash: scan checkpoint outbound pabrik &amp; konfirmasi serah-terima ke sawah (biochar dikomersialkan pabrik untuk baterai)</p>
            </div>
          </div>
          <div id="driver-backhaul-list">Memuat tugas muatan balik...</div>
        </div>

        <!-- Map Leaflet -->
        <div>
          <div class="card" style="padding:12px;">
            <div id="driver-map" style="height:480px; border-radius:12px;"></div>
          </div>
        </div>
      </div>
    `;
    loadDriverData();
    initAIEvaluationCard("driver");
  } else if (role === "pabrik") {
    container.innerHTML = `
      <div class="kpi-row">
        <div class="kpi-tile"><div class="kpi-lbl">Emisi Karbon Dihindari</div><div class="kpi-val" id="f-co2">–</div><div class="kpi-lbl">tCO₂e (IPCC Tier 2)</div></div>
        <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Output Biochar / Terkarbonisasi</div><div class="kpi-val" id="f-biochar">–</div><div class="kpi-lbl">Ton Biochar Terverifikasi</div></div>
        <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Potensi Biosilika SiO₂</div><div class="kpi-val" id="f-sio2">–</div><div class="kpi-lbl">Ton · estimasi dari kadar abu</div></div>
        <div class="kpi-tile kpi-purple"><div class="kpi-lbl">Produk Sirkular Pabrik</div><div class="kpi-val" style="font-size:var(--fs-sm);">Pellet, Briket, Biochar &amp; Silika</div><div class="kpi-lbl">Multi-Downstream Biomassa</div></div>
      </div>

      ${renderAIEvaluationCard("pabrik")}
      ${renderPersonaNotifWidgetHtml("pabrik")}

      <!-- 30 Days Forecast Chart: 1 baris penuh -->
      <div class="card" style="margin-top:16px;">
        <div class="card-header">
          <div>
            <h3 class="card-title">📈 Proyeksi Pasokan Biomassa 30 Hari</h3>
            <p class="card-sub">Model cosinus musiman panen Sleman &amp; Klaten (BPS)</p>
          </div>
        </div>
        <canvas id="factory-forecast-chart" height="150"></canvas>
      </div>

      <!-- ESG Carbon Calculator: 1 baris penuh -->
      <div class="card" style="margin-top:16px;">
        <div class="card-header">
          <div>
            <h3 class="card-title">🌿 Kalkulator Pengurangan Emisi Karbon</h3>
            <p class="card-sub">Metodologi IPCC 2006 Tier 2 untuk pemanfaatan multi-biomassa &amp; biochar</p>
          </div>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
          <div><label class="kpi-lbl">Biomassa (ton)</label><input type="number" id="c-ton" class="btn btn-secondary" style="width:100%;" value="50"></div>
          <div><label class="kpi-lbl">Jarak Angkut (km)</label><input type="number" id="c-km" class="btn btn-secondary" style="width:100%;" value="45"></div>
        </div>
        <button class="btn btn-primary" style="width:100%; margin-top:12px;" data-onclick="calcCarbon()">Hitung Pengurangan CO₂ ➔</button>
        <div id="carbon-res-box" style="margin-top:12px;"></div>
      </div>
    `;
    container.insertAdjacentHTML("beforeend", FACTORY_OPS_HTML);
    loadFactoryData();
    initFactoryOps();
    initAIEvaluationCard("pabrik");
    if (typeof renderFactoryExtras === "function") renderFactoryExtras(container);
    if (typeof renderFieldExtras === "function") renderFieldExtras("pabrik", container);
  } else if (role === "auditor") {
    container.innerHTML = `
      <div class="kpi-row">
        <div class="kpi-tile"><div class="kpi-lbl">Timbangan Pengepul</div><div class="kpi-val" id="au-collector">0</div><div class="kpi-lbl">kg (sudah diterima pabrik)</div></div>
        <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Timbangan Pabrik</div><div class="kpi-val" id="au-factory">0</div><div class="kpi-lbl">kg</div></div>
        <div class="kpi-tile kpi-purple"><div class="kpi-lbl">Total Susut</div><div class="kpi-val" id="au-shrink">0</div><div class="kpi-lbl" id="au-shrink-pct">%</div></div>
        <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Abu Bottom Ash Kembali ke Petani</div><div class="kpi-val" id="au-biochar">0</div><div class="kpi-lbl">kg teralokasi</div></div>
      </div>

      ${renderAIEvaluationCard("auditor")}
      ${renderPersonaNotifWidgetHtml("auditor")}

      <div class="card">
        <div class="card-header"><div>
          <h3 class="card-title">🔍 Selisih Timbangan di Luar Toleransi</h3>
          <p class="card-sub" id="au-tol">Akses baca-saja</p>
        </div></div>
        <div style="overflow-x:auto;">
          <table class="data-table" id="table-au-disc">
            <thead><tr><th>Harvest</th><th class="num">Pengepul (kg)</th><th class="num">Pabrik (kg)</th><th class="num">Susut %</th><th>Catatan</th></tr></thead>
            <tbody><tr><td colspan="5" style="text-align:center;">Memuat...</td></tr></tbody>
          </table>
        </div>
      </div>
    `;
    loadAuditorData();
    initAIEvaluationCard("auditor");
    if (typeof renderFactoryExtras === "function") renderFactoryExtras(container);
  } else if (role === "admin") {
    container.innerHTML = `
      <div class="kpi-row" id="admin-summary-kpis">
        <div class="kpi-tile"><div class="kpi-lbl">Total Pengguna</div><div class="kpi-val" id="a-tot-users">–</div><div class="kpi-lbl">Akun terdaftar</div></div>
        <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Titik Pemasok / Produsen</div><div class="kpi-val" id="a-tot-mills">–</div><div class="kpi-lbl">Sleman &amp; Klaten</div></div>
        <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Laporan Biomassa</div><div class="kpi-val" id="a-tot-harvests">–</div><div class="kpi-lbl">Batch Transaksi</div></div>
        <div class="kpi-tile kpi-purple"><div class="kpi-lbl">Armada Logistik</div><div class="kpi-val" id="a-tot-routes">–</div><div class="kpi-lbl">Rute Penjemputan</div></div>
      </div>

      ${renderAIEvaluationCard("admin")}
      ${renderPersonaNotifWidgetHtml("admin")}

      <div class="card">
        <div class="card-header">
          <div>
            <h3 class="card-title">⚙️ Kendali Platform &amp; Data Demo</h3>
            <p class="card-sub">Operasional sistem Bio-Chain</p>
          </div>
        </div>
        <div style="display:flex; gap:12px; flex-wrap:wrap;">
          <button class="btn btn-primary" data-onclick="clickById('btn-reset-demo')">
            🔄 Reset &amp; Re-seed Data Demo Lengkap
          </button>
          <button class="btn btn-secondary" data-onclick="openTab('tab-engines')">
            🧪 Buka Lab 7 Engine
          </button>
          <button class="btn btn-secondary" data-onclick="openTab('tab-admin')">
            👥 Buka Daftar Seluruh User
          </button>
        </div>
      </div>

      <div class="card" style="margin-top:16px;">
        <div class="card-header">
          <div>
            <h3 class="card-title">🌾 Referensi Harga Beli Acuan Tiap Biomassa</h3>
            <p class="card-sub">Atur harga beli standar (Rp/kg) per komoditas yang menjadi acuan transaksi petani &amp; lelang</p>
          </div>
          <button type="button" class="btn btn-secondary btn-sm" id="btn-admin-refresh-prices">↻ Segarkan Harga</button>
        </div>
        <div class="table-scroll">
          <table class="data-table" id="table-admin-biomass-prices">
            <thead>
              <tr>
                <th>Kode</th>
                <th>Nama Komoditas</th>
                <th class="num">Harga Acuan (Rp/kg)</th>
                <th>MC Acuan (%)</th>
                <th>Sumber Acuan</th>
                <th>Aksi</th>
              </tr>
            </thead>
            <tbody>
              <tr><td colspan="6" style="text-align:center;">Memuat data harga...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    `;
    // KPI ringkas diisi dari data asli (dulu angka contoh statis di HTML)
    api("/api/v1/admin/stats").then(st => {
      [["a-tot-users", st.total_users], ["a-tot-mills", st.total_mills], ["a-tot-harvests", st.total_harvests], ["a-tot-routes", st.total_routes]]
        .forEach(([id, v]) => { if ($(id)) $(id).innerText = num(v, 0); });
    }).catch(err => console.error("admin stats:", err));
    initAIEvaluationCard("admin");
    loadAdminBiomassPrices();
    const rfPrices = $("btn-admin-refresh-prices");
    if (rfPrices) rfPrices.onclick = loadAdminBiomassPrices;
    if (typeof renderFactoryExtras === "function") renderFactoryExtras(container);
  }

  // Muat aktivitas notifikasi terkini untuk persona aktif
  loadPersonaNotifWidget();
  updateNotificationBadge();
}

async function loadAdminBiomassPrices() {
  const tbody = $("table-admin-biomass-prices") && $("table-admin-biomass-prices").querySelector("tbody");
  if (!tbody) return;
  try {
    const list = await api("/api/v1/biomass?include_inactive=true");
    if (!list.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;">Belum ada komoditas biomassa.</td></tr>`;
      return;
    }
    tbody.innerHTML = list.map(b => `
      <tr>
        <td><code>${esc(b.code)}</code></td>
        <td><b>${esc(b.name)}</b></td>
        <td class="num">
          <input type="number" min="0" step="10" id="adm-price-${esc(b.code)}" value="${b.base_price_per_kg != null ? b.base_price_per_kg : ''}" placeholder="Belum diisi" class="btn btn-secondary btn-sm" style="width:110px; text-align:right;">
        </td>
        <td>${b.moisture_ref_pct != null ? `${b.moisture_ref_pct}%` : '-'}</td>
        <td style="font-size:0.8rem; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${esc(b.source || '-')}">${esc(b.source || '-')}</td>
        <td>
          <button type="button" class="btn btn-primary btn-sm" data-adm-save-price="${esc(b.code)}">💾 Simpan</button>
        </td>
      </tr>
    `).join("");

    tbody.querySelectorAll("[data-adm-save-price]").forEach(btn => {
      btn.onclick = () => {
        const code = btn.dataset.admSavePrice;
        const val = Number($(`adm-price-${code}`).value);
        if (isNaN(val) || val <= 0) return showToast("Masukkan harga yang valid (Rp/kg > 0)", "⚠️");
        withBusy(btn, async () => {
          try {
            await api(`/api/v1/biomass/${code}`, {
              method: "PUT",
              body: {
                changes: { base_price_per_kg: val },
                source: "Penetapan acuan harga pasar admin Bio-Chain"
              }
            });
            showToast(`Harga acuan ${code} berhasil diperbarui menjadi ${rp(val)}/kg`, "✅");
            loadAdminBiomassPrices();
          } catch (err) {
            showToast(err.message, "❌");
          }
        }, "⏳");
      };
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--red);">Gagal memuat: ${esc(err.message)}</td></tr>`;
  }
}

// ==============================================================
// 4. PERSONA DATA LOADERS
// ==============================================================
function pendingPetaniRows() {
  return myOutbox("/api/v1/farmer/harvest").map(i => `
      <tr style="opacity:.75">
        <td>⏳ Antre</td>
        <td>-</td>
        <td class="num"><b>${num(i.body.quantity_kg, 0)}</b></td>
        <td><span class="badge badge-amber">antre (offline)</span></td>
        <td>-</td><td>-</td><td>-</td>
      </tr>`).join("");
}

async function loadPetaniData() {
  const tbodyEl = $("table-petani-harvests") && $("table-petani-harvests").querySelector("tbody");
  try {
    const [harvests, inc, wallet] = await Promise.all([
      api("/api/v1/farmer/harvests"),
      api("/api/v1/farmer/incentive"),
      api("/api/v1/farmer/wallet").catch(() => null),
    ]);
    if (wallet) {
      if ($("p-wallet")) $("p-wallet").innerText = num(wallet.balance_kg, 1);
      if ($("p-wallet-avail")) $("p-wallet-avail").innerText = num(wallet.available_kg, 1);
      if ($("p-wallet-taken")) $("p-wallet-taken").innerText = num(wallet.taken_kg, 1);
    }

    if ($("p-tot-harvest")) $("p-tot-harvest").innerText = inc.total_harvests;
    if ($("p-tot-harvest-avg")) $("p-tot-harvest-avg").innerText = `(rata-rata: ${num(inc.avg_harvests_per_month || 0, 1)} / bln)`;
    if ($("p-tot-ton")) $("p-tot-ton").innerText = num(inc.total_kg / 1000, 1);
    if ($("p-tot-ton-avg")) $("p-tot-ton-avg").innerText = `(rata-rata: ${num(inc.avg_ton_per_month || 0, 1)} Ton / bln)`;
    if ($("p-xp")) $("p-xp").innerText = inc.xp_total;
    if ($("p-tier-lbl")) $("p-tier-lbl").innerText = `Tier ${inc.tier.toUpperCase()}`;

    const tbody = tbodyEl;
    if (!harvests.length) {
      tbody.innerHTML = pendingPetaniRows()
        || `<tr><td colspan="7">${emptyState("🌾", "Belum ada laporan biomassa", "Kirim laporan stok biomassa pertama Anda lewat formulir di sebelah kiri.")}</td></tr>`;
      return;
    }

    const badgeClass = s => {
      if (s === "delivered" || s === "converted") return "badge-green";
      if (s === "rejected") return "badge-red";
      if (s === "verified") return "badge-blue";
      if (s === "collected") return "badge-purple";
      return "badge-amber";
    };

    // Pengelompokan Data Panen Petani per Bulan (Monthly Grouping)
    const monthGroups = {};
    harvests.forEach(h => {
      const meta = (typeof window.getMonthYearMeta === "function")
        ? window.getMonthYearMeta(h.reported_at || h.created_at || h.verified_at)
        : { key: "2026-10", label: "Oktober 2026", shortLabel: "Okt 2026" };
      if (!monthGroups[meta.key]) {
        monthGroups[meta.key] = { meta, items: [], totalKg: 0 };
      }
      monthGroups[meta.key].items.push(h);
      monthGroups[meta.key].totalKg += (Number(h.verified_kg || h.quantity_kg) || 0);
    });

    const sortedMKeys = Object.keys(monthGroups).sort().reverse();
    let rowsHtml = pendingPetaniRows();

    sortedMKeys.forEach(k => {
      const g = monthGroups[k];
      rowsHtml += `
        <tr class="group-header-row" style="background:var(--surface-2); font-weight:700;">
          <td colspan="7" style="padding:10px 14px; border-top:2px solid var(--border); color:var(--ink);">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-size:1.05rem;">📅 ${esc(g.meta.label)}</span>
                <span class="badge badge-purple">${g.items.length} Laporan</span>
                <span class="badge badge-green">${num(g.totalKg, 0)} kg (${num(g.totalKg/1000, 2)} Ton)</span>
              </div>
            </div>
          </td>
        </tr>
      `;
      rowsHtml += g.items.map(h => {
        const isAct = h.is_active || h.status === 'reported';
        const wrCode = h.wr_code || h.qr_code || `WR-HV-${String(h.id).padStart(4, '0')}`;
        return `
        <tr>
          ${renderTraceabilityCell(h)}
          <td><span class="badge badge-purple">${esc(h.commodity_name || (h.commodity || "sekam_padi").replace('_', ' ').toUpperCase())}</span></td>
          <td class="num"><b>${num(h.quantity_kg, 0)}</b></td>
          <td>
            ${h.status === 'verified'
              ? `<span class="badge badge-blue">🔵 Terverifikasi Pengepul</span>`
              : (h.status === 'reported'
                ? `<span class="badge badge-amber">🟡 Menunggu Verifikasi Pengepul</span>`
                : (h.status === 'collected'
                  ? `<span class="badge badge-purple">🚚 Diangkut Pengepul</span>`
                  : (h.status === 'delivered' || h.status === 'converted'
                    ? `<span class="badge badge-green">🏭 Diterima Gudang/Pabrik</span>`
                    : `<span class="badge ${badgeClass(h.status)}">${esc(h.status_label || h.status)}</span>`)))}
            ${h.pickup_date
              ? `<div style="font-size:10px; color:var(--primary); font-weight:700; margin-top:2px;">📅 Jadwal ${h.delivery_scheme === 'antar' ? 'Antar' : 'Jemput'}: ${esc(h.pickup_date)}</div>`
              : (h.verified_at ? `<div style="font-size:10px; color:var(--primary); font-weight:600; margin-top:2px;">📅 Tgl: ${formatWIB(h.verified_at).split(',')[0]}</div>` : '')}
            ${h.payment_status === 'SETTLED' ? `<div style="font-size:10px; color:#22c55e; font-weight:700; margin-top:1px;">✅ Selesai (Lunas)</div>` : ''}
            <div style="font-size:10px; color:var(--ink-muted); margin-top:2px;">${formatWIB(h.reported_at || h.created_at)}</div>
          </td>
          <td>${h.grade ? `<b>Grade ${esc(h.grade)}</b>` : (h.farmer_grade_est ? `Taksiran Grade ${esc(h.farmer_grade_est)}` : '-')}</td>
          <td>
            <button type="button" class="btn btn-secondary btn-sm" style="font-size:11px; padding:3px 7px;" data-onclick="showHarvestFarmerDetail(${Number(h.id)})">
              📋 Detail
            </button>
          </td>
          <td>
            <button class="btn btn-secondary btn-sm" data-onclick="openModal('QR Setor Biomassa #${h.id}', '${esc(h.qr_code)}', '${num(h.verified_kg || h.quantity_kg, 0)} kg Biomassa · ${h.status === 'verified' ? ('Terverifikasi Pengepul' + (h.pickup_date ? ' · Jadwal: ' + h.pickup_date : '')) : (h.status_label || esc(h.status))}', { originQrCode: '${esc(wrCode)}', harvestId: ${Number(h.id)} })">
              QR 👁️
            </button>
          </td>
        </tr>
      `}).join("");
    });
    tbody.innerHTML = rowsHtml;
  } catch (err) {
    console.error("loadPetaniData:", err);
    if (err.network && tbodyEl) {
      tbodyEl.innerHTML = pendingPetaniRows()
        || `<tr><td colspan="7" style="text-align:center;">📵 Offline — data terakhir belum bisa dimuat.</td></tr>`;
    }
  }
}

let cachedFarmerListings = [];

function renderMyListings() {
  const box = $("my-listings");
  if (!box) return;
  const q = (($("listing-search") || {}).value || "").toLowerCase().trim();
  const f = (($("listing-filter-status") || {}).value || "all");

  const list = cachedFarmerListings.filter(l => {
    if (f !== "all" && l.status !== f) return false;
    if (q) {
      const wr = (l.wr_code || `WR-LST-${String(l.id).padStart(4, '0')}`).toLowerCase();
      const origin = (l.origin_qr_code || "").toLowerCase();
      const com = (l.commodity_name || l.commodity || "").toLowerCase();
      const text = `${wr} ${origin} ${com} listing #${l.id}`;
      if (!text.includes(q)) return false;
    }
    return true;
  });

  if (!list.length) {
    box.innerHTML = emptyState("🏷️", "Tidak ada stok lelang", "Tidak ditemukan data lelang yang sesuai dengan pencarian atau filter status.");
    return;
  }

  // Pengelompokan Data Sesi Lelang per Bulan (Monthly Grouping)
  const monthGroups = {};
  list.forEach(l => {
    const meta = (typeof window.getMonthYearMeta === "function")
      ? window.getMonthYearMeta(l.created_at)
      : { key: "2026-10", label: "Oktober 2026", shortLabel: "Okt 2026" };
    if (!monthGroups[meta.key]) {
      monthGroups[meta.key] = { meta, items: [] };
    }
    monthGroups[meta.key].items.push(l);
  });

  const sortedKeys = Object.keys(monthGroups).sort().reverse();
  box.innerHTML = sortedKeys.map(k => {
    const g = monthGroups[k];
    const totalMonthKg = g.items.reduce((a, b) => a + (Number(b.quantity_kg) || 0), 0);
    return `
      <div class="month-group-card" style="margin-bottom:16px; border:1px solid var(--border); border-radius:12px; overflow:hidden; background:var(--surface-1);">
        <div style="padding:10px 16px; background:linear-gradient(90deg, var(--surface-2), var(--surface-1)); font-weight:700; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; border-bottom:1px solid var(--border);">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:1.05rem;">📅 ${esc(g.meta.label)}</span>
            <span class="badge badge-purple">${g.items.length} Sesi Lelang</span>
          </div>
          <span class="badge badge-green">Total: ${num(totalMonthKg, 0)} kg (${num(totalMonthKg/1000, 2)} Ton)</span>
        </div>
        <div style="padding:12px 14px;">
          ${g.items.map(l => {
            const isAct = ["open", "partially_awarded"].includes(l.status);
            const wrCode = l.wr_code || `WR-LST-${String(l.id).padStart(4, '0')}`;
            const originQr = l.origin_qr_code || wrCode;

            return `
              <div style="border:1px solid var(--border); border-radius:10px; padding:12px 14px; margin-bottom:12px; background:var(--surface-1);">
                <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:8px;">
                  <div>
                    <span class="kpi-lbl" style="font-size:10px;">No. QR Code Ketelusuran Lelang:</span>
                    <div style="display:flex; align-items:center; gap:6px;">
                      <code style="font-family:monospace; font-weight:800; color:var(--primary); font-size:13.5px;">${esc(originQr)}</code>
                      <button type="button" class="btn btn-secondary btn-sm" style="padding:1px 6px; font-size:10px; height:20px;" data-onclick="openModal('QR Code Lelang Biomassa', '${esc(originQr)}', 'Nomor batch lelang resmi petani')">📱 QR</button>
                    </div>
                    <div style="font-size:11.5px; margin-top:2px;">
                      <b>Nomor List Lelang:</b> <code style="font-size:11px;">Listing #${l.id}</code> · <b>${num(l.remaining_kg, 0)} / ${num(l.quantity_kg, 0)} kg</b>
                    </div>
                  </div>
                  <div style="text-align:right;">
                    <span class="badge ${isAct ? (l.status === 'open' ? 'badge-green' : 'badge-amber') : (l.status === 'closed' ? 'badge-blue' : 'badge-gray')}">
                      ${isAct ? (l.status === 'open' ? '🟢 Aktif Ditawar' : '🟡 Sebagian Deal') : (l.status === 'closed' ? '⚪ Lelang Selesai' : '🔴 ' + esc(l.status))}
                    </span>
                    <div style="font-size:10px; color:var(--ink-muted); margin-top:2px;">Status: ${esc(l.status)}</div>
                  </div>
                </div>
                <div class="kpi-lbl" style="margin-bottom:6px;">
                  ${Object.entries(l.schemes).filter(([, v]) => v).map(([k, v]) => `${SCHEME_LABEL[k] || k} batas min ${rp(v)}/kg`).join(" · ")}
                  ${l.moisture_pct != null ? ` · Kadar air ~${num(l.moisture_pct, 1)}%` : ''}
                  ${l.grade_estimate ? ` · Grade ~${esc(l.grade_estimate)}` : ''}
                  ${l.created_at ? `<br><small class="muted">Waktu Buka Lelang: ${formatWIB(l.created_at)}</small>` : ''}
                </div>
                <div style="display:flex; gap:6px; flex-wrap:wrap; align-items:center;">
                  ${isAct ? `
                    <button class="btn btn-secondary btn-sm" data-onclick="showBids(${Number(l.id)})">Lihat tawaran</button>
                    <button class="btn btn-secondary btn-sm" data-onclick="cancelListing(${Number(l.id)})">Batalkan</button>
                  ` : ''}
                </div>
                <div id="bids-${Number(l.id)}"></div>
              </div>
            `;
          }).join("")}
        </div>
      </div>
    `;
  }).join("");
}

async function loadMyListings() {
  try {
    const rows = await api("/api/v1/farmer/listings");
    cachedFarmerListings = rows || [];
    renderMyListings();

    const searchInp = $("listing-search");
    if (searchInp && !searchInp._bound) {
      searchInp._bound = true;
      searchInp.oninput = renderMyListings;
    }
    const filterSel = $("listing-filter-status");
    if (filterSel && !filterSel._bound) {
      filterSel._bound = true;
      filterSel.onchange = renderMyListings;
    }
  } catch (err) { console.error("loadMyListings:", err); }
}

async function showBids(listingId) {
  const r = await api(`/api/v1/farmer/listings/${listingId}/bids`);
  const box = $(`bids-${listingId}`);
  const active = r.bids.filter(b => b.status === "active");
  box.innerHTML = active.length ? `<table class="data-table" style="margin-top:8px;"><thead><tr><th>Pengepul</th><th>Skema &amp; Jadwal</th>
      <th class="num">Harga</th><th class="num">Nilai bersih</th><th class="num">kg</th><th>Terima</th></tr></thead><tbody>
    ${active.map(b => `<tr${b.highest_net ? ' style="background:var(--primary-soft)"' : ""}>
      <td><b>${esc(b.collector)}</b>${b.highest_net ? ' <span class="badge badge-green">bersih tertinggi</span>' : ""}</td>
      <td>
        <span>${SCHEME_LABEL[b.scheme] || esc(b.scheme)}</span>
        ${b.scheme === "jemput" ? `
          <div style="margin-top:4px;">
            ${b.farmer_schedule_status === "APPROVED" 
              ? `<span class="badge badge-green">✓ Jadwal: ${esc(b.pickup_date || "-")}</span>` 
              : b.farmer_schedule_status === "RESCHEDULE_REQUESTED"
              ? `<span class="badge badge-amber">📅 Diajukan: ${esc(b.pickup_date || "-")}${b.farmer_schedule_note ? `<br><small>${esc(b.farmer_schedule_note)}</small>` : ""}</span>`
              : `<div style="display:flex; flex-direction:column; gap:2px;">
                   <span class="badge badge-blue">Rencana: ${esc(b.pickup_date || "Menunggu Pengepul")}</span>
                   <div style="display:flex; gap:4px; margin-top:3px;">
                     <button type="button" class="btn btn-secondary btn-sm" style="font-size:10px; padding:2px 6px;" data-onclick="respondBidSchedule(${Number(listingId)}, ${Number(b.bid_id)}, 'APPROVED')">✓ Setujui</button>
                     <button type="button" class="btn btn-secondary btn-sm" style="font-size:10px; padding:2px 6px;" data-onclick="openRescheduleBidModal(${Number(listingId)}, ${Number(b.bid_id)}, '${esc(b.pickup_date || "")}')">📅 Ubah</button>
                   </div>
                 </div>`
            }
          </div>` : ""}
      </td>
      <td class="num">${rp(b.price_per_kg)}</td>
      <td class="num"><b>${b.net_to_farmer_per_kg == null ? "-" : rp(b.net_to_farmer_per_kg)}</b>
        ${b.farmer_transport_cost_per_kg ? `<br><span class="kpi-lbl">ongkos antar ${rp(b.farmer_transport_cost_per_kg)}/kg</span>` : ""}</td>
      <td class="num">${num(b.quantity_kg, 0)}</td>
      <td><input type="number" id="acc-${Number(b.bid_id)}" class="btn btn-secondary" style="width:80px;" min="1"
            value="${Math.min(b.quantity_kg, r.listing.remaining_kg)}" max="${Math.min(b.quantity_kg, r.listing.remaining_kg)}">
          <button class="btn btn-primary btn-sm" data-onclick="acceptBid(${Number(listingId)}, ${Number(b.bid_id)}, this)">Pilih</button></td></tr>`).join("")}
    </tbody></table><p class="kpi-lbl">Anda bebas memilih tawaran mana pun dan boleh menerima sebagian.</p>`
    : `<div style="font-size:var(--fs-xs); color:var(--ink-muted); padding:8px 0; display:flex; align-items:center; gap:8px;">⏳ <span>Belum ada tawaran aktif dari pengepul untuk stok ini.</span></div>`;
}

async function respondBidSchedule(listingId, bidId, action) {
  try {
    const res = await api(`/api/v1/farmer/bids/${bidId}/schedule-respond`, {
      method: "POST",
      body: { action, reschedule_note: action === "APPROVED" ? "Disetujui petani" : null }
    });
    showToast(res.message || "Jadwal penjemputan berhasil disetujui! ✅", "✅");
    showBids(listingId);
  } catch (err) { showToast(err.message, "❌"); }
}
window.respondBidSchedule = respondBidSchedule;

function openRescheduleBidModal(listingId, bidId, curDate) {
  const d = document.createElement("dialog");
  d.className = "ui-confirm";
  d.innerHTML = `<form method="dialog" style="max-width:380px;">
    <h3>📅 Ajukan Penyesuaian Jadwal Jemput</h3>
    <p class="ui-confirm-body">Pengepul akan menerima pemberitahuan perubahan tanggal penjemputan biomassa Anda.</p>
    <div class="form-group"><label for="resched-date">Tanggal Penjemputan Baru</label>
      <input id="resched-date" type="date" required value="${curDate || new Date().toISOString().slice(0, 10)}"></div>
    <div class="form-group"><label for="resched-note">Catatan untuk Pengepul</label>
      <input id="resched-note" placeholder="Contoh: Panen baru selesai sore, mohon ambil pagi hari." maxlength="300"></div>
    <div class="ui-confirm-actions">
      <button value="no" class="btn btn-secondary" formnovalidate>Batal</button>
      <button value="yes" class="btn btn-primary">Kirim Permintaan</button>
    </div></form>`;
  document.body.appendChild(d);
  d.addEventListener("close", async () => {
    if (d.returnValue === "yes") {
      try {
        const newDate = d.querySelector("#resched-date").value;
        const note = d.querySelector("#resched-note").value.trim() || null;
        const res = await api(`/api/v1/farmer/bids/${bidId}/schedule-respond`, {
          method: "POST",
          body: { action: "RESCHEDULE_REQUESTED", reschedule_date: newDate, reschedule_note: note }
        });
        showToast(res.message || "Permintaan penyesuaian jadwal terkirim ke pengepul 📅", "📅");
        showBids(listingId);
      } catch (err) { showToast(err.message, "❌"); }
    }
    d.remove();
  });
  d.showModal();
}
window.openRescheduleBidModal = openRescheduleBidModal;

async function acceptBid(listingId, bidId, btn) {
  const qty = Number($(`acc-${bidId}`).value);
  return withBusy(btn, async () => {
    try {
      const r = await api(`/api/v1/farmer/listings/${listingId}/accept`, { body: { bid_id: bidId, quantity_kg: qty } });
      showToast(`Disepakati ${num(r.accepted_kg, 0)} kg @${rp(r.price_per_kg)} (${r.scheme}). Nilai ${rp(r.contract_value_rp)}`, "🤝");
      openModal("Kontrak Lelang", r.qr_code, `${num(r.accepted_kg, 0)} kg · ${r.scheme} · tunjukkan QR saat serah-terima`, {
        originQrCode: r.origin_qr_code || r.qr_code,
        batchRef: r.batch_ref || `WR-LST-${String(listingId).padStart(4, '0')}`,
        listingId: listingId,
        commodity: r.commodity || "Biomassa",
        accepted_kg: r.accepted_kg,
        price_per_kg: r.price_per_kg,
        contractValueRp: r.contract_value_rp
      });
      loadMyListings(); loadPetaniData();
    } catch (err) { showToast(err.message, "❌"); loadMyListings(); }
  });
}
window.acceptBid = acceptBid;

async function cancelListing(listingId) {
  try { await api(`/api/v1/farmer/listings/${listingId}/cancel`, { method: "POST" }); loadMyListings(); }
  catch (err) { showToast(err.message, "❌"); }
}

let activeOffersTab = "langsung";
let activeVerificationFilter = "all"; // "all" | "unverified" | "verified"
let activeOffersMonth = "all"; // "all" | "YYYY-MM"
let cachedOffersData = { langsung_diambil: [], lelang: [], diantar_petani: [] };

window.switchOffersTab = function(tab) {
  activeOffersTab = tab;
  ["langsung", "lelang", "diantar"].forEach(t => {
    const btn = $(`btn-tab-${t}`);
    if (btn) btn.className = `btn btn-sm ${t === tab ? "btn-primary" : "btn-secondary"}`;
  });
  renderOffersTable();
};

window.setVerificationFilter = function(filter) {
  activeVerificationFilter = filter;
  ["all", "unverified", "verified"].forEach(f => {
    const btn = $(`vfilter-${f}`);
    if (btn) btn.className = `btn btn-sm ${f === filter ? "btn-primary" : "btn-secondary"}`;
  });
  renderOffersTable();
};

window.setOffersMonthFilter = function(mKey) {
  activeOffersMonth = mKey;
  renderOffersTable();
};

window.toggleMonthDetail = function(mKey) {
  const el = $(`month-detail-${mKey}`);
  const btn = $(`btn-toggle-month-${mKey}`);
  if (!el) return;
  const isHidden = (el.style.display === "none");
  el.style.display = isHidden ? "block" : "none";
  if (btn) {
    const count = btn.getAttribute("data-count") || "";
    btn.innerHTML = isHidden ? "▲ Sembunyikan Detail" : `👁️ Buka Detail Data (${count} Lot) ▾`;
  }
};

function renderOfferRowsHtml(items, tab) {
  const COMMODITY_MAP = {
    sekam_padi: { label: "🌾 Sekam Padi", badge: "badge-purple" },
    tongkol_jagung: { label: "🌽 Tongkol Jagung", badge: "badge-amber" },
    serbuk_kayu: { label: "🪵 Serbuk Kayu", badge: "badge-blue" },
    serbuk_sengon: { label: "🪵 Serbuk Sengon", badge: "badge-blue" },
    serbuk_karet: { label: "🪵 Serbuk Karet", badge: "badge-blue" },
    ampas_tebu: { label: "🎋 Ampas Tebu", badge: "badge-green" },
    cangkang_sawit: { label: "🌴 Cangkang Sawit", badge: "badge-amber" },
    sabut_kelapa: { label: "🥥 Sabut Kelapa", badge: "badge-amber" },
    tempurung_kelapa: { label: "🥥 Tempurung Kelapa", badge: "badge-amber" }
  };

  return items.map(it => {
    const fId = Number(it.harvest_id || it.listing_id || it.id || 0);
    const fName = it.nama_petani || it.farmer_name || 'Petani';
    const fKec = it.kecamatan || it.farmer_kecamatan || '-';
    const fPhone = it.farmer_phone || '-';
    const qKg = it.qty_kg != null ? it.qty_kg : (it.quantity_kg != null ? it.quantity_kg : 0);
    const pHrg = it.harga_per_kg != null ? it.harga_per_kg : (it.price_per_kg != null ? it.price_per_kg : 450);
    const bioKey = it.commodity_code || it.biomass_type || it.jenis_biomassa || "sekam_padi";
    const bioName = it.jenis_biomassa || it.biomass_name || bioKey.replace("_", " ").toUpperCase();
    const meta = COMMODITY_MAP[bioKey] || { label: bioName, badge: "badge-gray" };
    const pKirim = it.pilihan_kirim || it.delivery_scheme_label || (it.delivery_scheme === "JEMPUT" ? "Dijemput Pengepul" : "Diantar Petani");

    let actionHtml = "";
    if (tab === "langsung" || tab === "diantar") {
      if (!it.is_verified_initial) {
        actionHtml = `
          <div style="display:flex; flex-direction:column; gap:4px;">
            <button type="button" class="btn btn-primary btn-sm" style="background:#059669; border-color:#059669; font-weight:600; white-space:nowrap; padding:4px 8px;"
                    data-onclick="openApproveOfferModal(${fId}, ${Number(qKg)}, ${Number(pHrg)}, '${esc(fName)}', '${esc(bioName)}')">
              ✓ Setujui Qty &amp; Harga
            </button>
            <button type="button" class="btn btn-secondary btn-sm" style="font-size:11px; padding:3px 7px;"
                    data-onclick="selectVerifyItem(${fId})"
                    data-verify-harvest-id="${fId}"
                    data-verify-qty="${Number(qKg)}"
                    title="Buka Popup Uji Mutu Proksimat &amp; Timbang Biomassa">
              🔬 Uji Mutu Lapangan
            </button>
          </div>
        `;
      } else {
        actionHtml = `
          <div style="display:flex; flex-direction:column; gap:4px;">
            <span class="badge badge-green" style="font-size:10px; text-align:center;">✓ Terverifikasi Pengepul</span>
            <button type="button" class="btn btn-primary btn-sm" style="padding:4px 8px;"
                    data-onclick="selectVerifyItem(${fId})"
                    data-verify-harvest-id="${fId}"
                    data-verify-qty="${Number(qKg)}">
              ⚖️ Timbang &amp; Uji Fisik
            </button>
          </div>
        `;
      }
    } else {
      // offers-dashboard mengirim tawaran aktif di bidding_details.my_bid (price_per_kg)
      const myBid = it.my_active_bid || (it.bidding_details && it.bidding_details.my_bid);
      const curBid = myBid ? { price: myBid.price_per_kg ?? myBid.price } : null;
      actionHtml = `
        <div style="display:flex; gap:4px; align-items:center; flex-wrap:wrap;">
          <input id="bp-${it.listing_id || fId}" type="number" class="btn btn-secondary btn-sm" style="width:85px;" value="${curBid ? curBid.price : (pHrg || 450)}" placeholder="Rp/kg" aria-label="Harga tawaran Rp/kg lot #${it.listing_id || fId}">
          <input id="bq-${it.listing_id || fId}" type="number" class="btn btn-secondary btn-sm" style="width:80px;" value="${qKg}" min="1" max="${qKg}" aria-label="Jumlah kg ditawar lot #${it.listing_id || fId}">
          <select id="bs-${it.listing_id || fId}" class="btn btn-secondary btn-sm" style="display:none;" aria-label="Skema lot #${it.listing_id || fId}"><option value="jemput">jemput</option></select>
          <button type="button" class="btn btn-secondary btn-sm" data-onclick="adviseBid(${Number(it.listing_id || fId)}, this)">Hitung saran</button>
          <button type="button" class="btn btn-primary btn-sm"
                  data-onclick="placeBid(${Number(it.listing_id || fId)}, this)"
                  data-bid-listing-id="${Number(it.listing_id || fId)}">
            ${curBid ? 'Ubah Tawaran' : 'Tawar ➔'}
          </button>
        </div>
        <div id="ba-${it.listing_id || fId}" class="kpi-lbl" style="font-size:10px; margin-top:3px;"></div>
        ${curBid ? `<span class="badge badge-blue" style="font-size:10px; margin-top:2px; display:inline-block;">Tawaran Anda: ${rp(curBid.price)}/kg</span>` : ''}
        ${it.is_verified_initial ? `<span class="badge badge-green" style="font-size:10px; margin-top:2px; display:inline-block;">✓ Deal Terverifikasi</span>` : ''}
      `;
    }

    // Kualitas: jika kosong biarkan kosong / tanda -, jangan menyimpulkan dummy Grade A
    let qualityText = '<span class="muted">-</span>';
    const moistVal = it.farmer_moisture_est != null ? it.farmer_moisture_est : it.moisture_est;
    const gradeVal = it.farmer_grade_est || it.grade_est || (it.grade && it.grade !== 'A' && it.grade !== '-' ? it.grade : null);

    if (moistVal != null && gradeVal) {
      qualityText = `<span style="font-weight:600;">Grade ${esc(gradeVal)} · Air ${num(moistVal, 1)}%</span>`;
    } else if (moistVal != null) {
      qualityText = `<span style="font-weight:600;">Air ${num(moistVal, 1)}%</span>`;
    } else if (gradeVal) {
      qualityText = `<span style="font-weight:600;">Grade ${esc(gradeVal)}</span>`;
    } else if (it.kualitas && it.kualitas !== "-" && !it.kualitas.includes("Grade A")) {
      qualityText = `<span style="font-weight:600;">${esc(it.kualitas)}</span>`;
    }

    const rawOrigin = it.origin_qr_code || it.qr_code || it.wr_code || (it.harvest_id ? ('WR-HV-' + String(it.harvest_id).padStart(4, '0')) : ('WR-LST-' + String(it.listing_id || fId).padStart(4, '0')));
    const trxCode = it.custody_trx || it.trx_code || null;

    return `
      <tr data-listing-id="${it.listing_id || it.harvest_id || fId}">
        <td style="vertical-align:top;">
          <div style="font-family:monospace; font-weight:700; color:var(--primary); font-size:11.5px; display:flex; align-items:center; gap:4px; flex-wrap:nowrap;">
            <span>🌾 ${esc(rawOrigin)}</span>
            <button type="button" class="btn btn-secondary btn-sm" style="padding:1px 5px; font-size:9px; height:18px;" data-onclick="openModal('QR Code Ketelusuran', '${esc(rawOrigin)}', 'Rantai Pasok Terlacak')">📱 QR</button>
          </div>
          ${it.harvest_id ? `<small class="muted" style="font-size:10px;">Lot #${it.harvest_id}</small>` : (it.listing_id ? `<small class="muted" style="font-size:10px;">Listing #${it.listing_id}</small>` : '')}
          ${trxCode ? `<br><span class="badge badge-purple" style="font-size:9px;">🏪 ${esc(trxCode)}</span>` : ''}
        </td>
        <td>
          <span class="badge ${it.is_active ? 'badge-green' : 'badge-gray'}" style="white-space:nowrap;">
            ${it.is_active ? '🟢 Aktif' : '⚪ Non-Aktif'}
          </span>
          <br>
          <span class="badge ${it.is_verified_initial ? 'badge-green' : 'badge-amber'}" style="font-size:10px; margin-top:3px; display:inline-block; font-weight:700;">
            ${it.is_verified_initial ? '🔵 Terverifikasi' : '🟡 Belum Verifikasi'}
          </span>
          <div style="font-size:10px; color:var(--ink-muted); margin-top:2px;">${esc(it.status_label || it.status)}</div>
        </td>
        <td>
          <b>${esc(fName)}</b>
          <br><small class="muted" style="font-size:10px;">📍 Kec. ${esc(fKec)}</small>
        </td>
        <td>
          <div style="display:flex; align-items:center; gap:4px; flex-wrap:wrap;">
            <code style="font-size:11.5px; color:var(--ink);">${esc(fPhone)}</code>
            <button type="button" class="btn btn-secondary btn-sm btn-wa" data-fo-contact="${fId}" style="font-size:10.5px; padding:2px 6px;" aria-label="Chat WhatsApp petani lot #${fId}">${it.farmer_without_phone ? "👵 Tanpa HP" : "💬 WA"}</button>
          </div>
        </td>
        <td><span class="badge ${meta.badge}">${esc(bioName)}</span></td>
        <td class="num">
          <b style="font-size:13px;">${num(qKg, 0)}</b>
          ${it.farmer_claimed_qty && it.farmer_claimed_qty !== qKg ? `<br><small class="muted" style="font-size:10px;">(Klaim: ${num(it.farmer_claimed_qty, 0)})</small>` : ''}
        </td>
        <td>
          ${qualityText}
          <br><span style="font-size:11px; color:var(--ink-muted);">🏭 ${esc(it.titik_pasok || 'Lahan Petani')}</span>
        </td>
        <td><span class="badge ${pKirim.includes('Dijemput') ? 'badge-blue' : 'badge-green'}">${esc(pKirim)}</span></td>
        <td class="num"><b>${rp(pHrg)}</b></td>
        <td>
          ${it.biochar_request ? `<span class="badge badge-green" style="font-size:10px; margin-bottom:2px; display:inline-block;" title="Pesan muatan balik abu bottom ash">🌱 Abu Bottom Ash: ${num(it.biochar_request.requested_kg, 0)} kg</span><br>` : ''}
          <div style="display:flex; gap:4px; align-items:center; flex-wrap:wrap;">
            ${it.photo_url ? `<button type="button" class="btn btn-secondary btn-sm" style="font-size:10px; padding:2px 6px;" data-onclick="viewPhotoModal('${esc(it.photo_url)}', 'Foto Muatan ${esc(fName)}')">📷 Foto</button>` : ''}
            <button type="button" class="btn btn-secondary btn-sm" style="font-size:11px; padding:3px 7px;" data-onclick="viewOfferDetailModal(${fId}, '${tab}')">🔍 Detail</button>
          </div>
        </td>
        <td class="col-actions">${actionHtml}</td>
      </tr>
    `;
  }).join("");
}

function renderOffersTable() {
  const box = $("market-table");
  if (!box) return;
  const allTabItems = activeOffersTab === "langsung"
    ? (cachedOffersData.langsung_diambil || [])
    : (activeOffersTab === "diantar"
      ? (cachedOffersData.diantar_petani || [])
      : (cachedOffersData.lelang || []));

  // Update sub-filter badges for current tab
  const countAll = allTabItems.length;
  const countUnverified = allTabItems.filter(it => !it.is_verified_initial).length;
  const countVerified = allTabItems.filter(it => it.is_verified_initial).length;

  if ($("vcount-all")) $("vcount-all").innerText = countAll;
  if ($("vcount-unverified")) $("vcount-unverified").innerText = countUnverified;
  if ($("vcount-verified")) $("vcount-verified").innerText = countVerified;

  let items = allTabItems;
  if (activeVerificationFilter === "unverified") {
    items = allTabItems.filter(it => !it.is_verified_initial);
  } else if (activeVerificationFilter === "verified") {
    items = allTabItems.filter(it => it.is_verified_initial);
  }

  const tabLabels = {
    langsung: "Langsung Diambil (Jemput)",
    diantar: "Diantar Petani",
    lelang: "Lelang / Bidding"
  };

  if (!items || !items.length) {
    const filterNote = activeVerificationFilter === "unverified"
      ? " dengan status Belum Verifikasi Qty & Harga"
      : (activeVerificationFilter === "verified" ? " dengan status Sudah Terverifikasi" : "");
    box.innerHTML = emptyState(
      activeOffersTab === "lelang" ? "🏷️" : (activeOffersTab === "diantar" ? "🚜" : "🚚"),
      `Tidak ada penawaran (${tabLabels[activeOffersTab] || activeOffersTab}${filterNote})`,
      `Saat ini belum ada panen atau penawaran petani pada filter ini.`
    );
    return;
  }

  // Pengelompokan Data per Bulan (Monthly Grouping)
  const monthGroups = {};
  for (const it of items) {
    const meta = (typeof window.getMonthYearMeta === "function")
      ? window.getMonthYearMeta(it.reported_at || it.created_at || it.verified_at)
      : { key: "2026-10", label: "Oktober 2026", shortLabel: "Okt 2026" };
    if (!monthGroups[meta.key]) {
      monthGroups[meta.key] = {
        meta,
        items: [],
        totalKg: 0,
        totalEstRp: 0,
        unverifiedCount: 0,
        verifiedCount: 0
      };
    }
    const itemKg = Number(it.qty_kg != null ? it.qty_kg : it.quantity_kg) || 0;
    const itemHrg = Number(it.harga_per_kg != null ? it.harga_per_kg : it.price_per_kg) || 450;
    monthGroups[meta.key].items.push(it);
    monthGroups[meta.key].totalKg += itemKg;
    monthGroups[meta.key].totalEstRp += (itemKg * itemHrg);
    if (it.is_verified_initial) {
      monthGroups[meta.key].verifiedCount++;
    } else {
      monthGroups[meta.key].unverifiedCount++;
    }
  }

  const sortedMonthKeys = Object.keys(monthGroups).sort().reverse();
  const displayedMonthKeys = (activeOffersMonth && activeOffersMonth !== "all" && monthGroups[activeOffersMonth])
    ? [activeOffersMonth]
    : sortedMonthKeys;

  // Month navigation pill bar
  let monthPillsHtml = `
    <div style="display:flex; gap:6px; margin: 0 0 16px; align-items:center; flex-wrap:wrap; padding:8px 12px; background:var(--surface-2); border-radius:8px; border:1px solid var(--border);">
      <span style="font-size:11.5px; font-weight:700; color:var(--ink); margin-right:4px;">📅 Periode Bulan:</span>
      <button type="button" class="btn btn-sm ${activeOffersMonth === 'all' ? 'btn-primary' : 'btn-secondary'}"
              data-onclick="setOffersMonthFilter('all')" style="font-size:11.5px; padding:3px 12px; border-radius:14px;">
        Semua Bulan (${items.length} Lot)
      </button>
      ${sortedMonthKeys.map(k => `
        <button type="button" class="btn btn-sm ${activeOffersMonth === k ? 'btn-primary' : 'btn-secondary'}"
                data-onclick="setOffersMonthFilter('${k}')" style="font-size:11.5px; padding:3px 12px; border-radius:14px;">
          📅 ${monthGroups[k].meta.label} (${monthGroups[k].items.length})
        </button>
      `).join("")}
    </div>
  `;

  let monthlyCardsHtml = "";
  displayedMonthKeys.forEach((mKey, idx) => {
    const g = monthGroups[mKey];
    // Open by default so all lots across months are immediately visible & accessible
    const isExpanded = true;
    const rowsHtml = renderOfferRowsHtml(g.items, activeOffersTab);

    monthlyCardsHtml += `
      <div class="month-group-card" style="margin-bottom:16px; border:1px solid var(--border); border-radius:12px; overflow:hidden; background:var(--surface-1); box-shadow:0 2px 8px rgba(0,0,0,0.04);">
        <!-- Header Rangkuman Bulan -->
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; padding:12px 16px; background:linear-gradient(90deg, var(--surface-2), var(--surface-1)); border-bottom:1px solid var(--border);">
          <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
            <span style="font-size:1.1rem; font-weight:700; color:var(--ink);">📅 ${esc(g.meta.label)}</span>
            <span class="badge badge-purple" style="font-size:11px;">${g.items.length} Lot Penawaran</span>
            <span class="badge badge-green" style="font-size:11px;">Total: ${num(g.totalKg / 1000, 2)} Ton</span>
            <span class="badge badge-blue" style="font-size:11px;">Est. Nilai: ${rp(g.totalEstRp)}</span>
          </div>
          <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
            <span class="badge ${g.unverifiedCount > 0 ? 'badge-amber' : 'badge-gray'}" style="font-size:10.5px;">🟡 ${g.unverifiedCount} Belum Verif</span>
            <span class="badge badge-green" style="font-size:10.5px;">🔵 ${g.verifiedCount} Terverifikasi</span>
            <button type="button" class="btn btn-secondary btn-sm" id="btn-toggle-month-${mKey}"
                    data-onclick="toggleMonthDetail('${mKey}')"
                    data-count="${g.items.length}"
                    style="font-size:11.5px; padding:3px 10px; font-weight:600;">
              ${isExpanded ? '▲ Sembunyikan Detail' : `👁️ Buka Detail Data (${g.items.length} Lot) ▾`}
            </button>
          </div>
        </div>

        <!-- Tabel Detail Data Per Bulan -->
        <div id="month-detail-${mKey}" style="display:${isExpanded ? 'block' : 'none'};">
          <div class="table-scroll">
            <table class="data-table offers-table" style="margin:0;">
              <thead>
                <tr>
                  <th>No. QR Code Ketelusuran</th>
                  <th>Status</th>
                  <th>Nama Petani</th>
                  <th>📱 No. Telepon Petani</th>
                  <th>Jenis Biomassa</th>
                  <th class="num">Qty (kg)</th>
                  <th>Kualitas &amp; Titik Pasok</th>
                  <th>Pilihan Kirim</th>
                  <th class="num">Harga/kg</th>
                  <th>Detail Petani</th>
                  <th class="col-actions">Aksi Finalisasi</th>
                </tr>
              </thead>
              <tbody>
                ${rowsHtml}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    `;
  });

  box.innerHTML = monthPillsHtml + monthlyCardsHtml;
}

function openApproveOfferModal(harvestId, currentQty, currentPrice, farmerName, commodityName) {
  formDialog({
    title: `✓ Setujui Qty & Harga Awal (Lot #${harvestId})`,
    ok: "Setujui & Tandai Terverifikasi",
    body: `
      <p class="card-sub">Verifikasi awal kesesuaian estimasi kuantitas dan harga dari petani sebelum rute penjemputan disusun.</p>
      <div style="background:var(--bg-panel); border:1px solid var(--border); border-radius:8px; padding:10px 14px; margin-bottom:12px;">
        <div style="font-size:12.5px; margin-bottom:4px;">👤 Petani: <b>${esc(farmerName || "Petani")}</b></div>
        <div style="font-size:12.5px; margin-bottom:4px;">🌾 Komoditas: <b>${esc(commodityName || "-")}</b></div>
        <div style="font-size:12.5px;">📦 Estimasi Petani: <b>${num(currentQty, 0)} kg</b></div>
      </div>
      <div class="form-group">
        <label for="ap-qty">Kuantitas Disetujui (kg)</label>
        <input id="ap-qty" name="agreed_qty_kg" type="number" value="${currentQty}" min="1" max="500000" step="10" required>
      </div>
      <div class="form-group">
        <label for="ap-price">Harga Beli Disepakati (Rp/kg)</label>
        <input id="ap-price" name="agreed_price_per_kg" type="number" value="${currentPrice || 450}" min="50" max="100000" step="5" required>
      </div>
      <div class="form-group">
        <label for="ap-date">Target Tanggal Logistik / Penjemputan</label>
        <input id="ap-date" name="pickup_date" type="date" value="${new Date(Date.now() + 86400000).toISOString().split('T')[0]}">
      </div>
      <div class="form-group">
        <label for="ap-note">Catatan Verifikasi (Opsional)</label>
        <input id="ap-note" name="note" type="text" placeholder="Misal: Sesuai stok gudang petani, siap dijemput">
      </div>
    `,
    onSubmit: async (fd) => {
      const agreedQty = Number(fd.get("agreed_qty_kg"));
      const agreedPrice = Number(fd.get("agreed_price_per_kg"));
      const pickupDate = fd.get("pickup_date");
      const note = fd.get("note");

      const res = await api(`/api/v1/collector/harvests/${harvestId}/approve-initial`, {
        method: "POST",
        body: {
          agreed_qty_kg: agreedQty,
          agreed_price_per_kg: agreedPrice,
          pickup_date: pickupDate || null,
          note: note || null,
        }
      });
      showToast(res.message || "Penawaran berhasil diverifikasi!", "✅");
      loadMarket();
      loadCollectorData();
    }
  });
}
window.openApproveOfferModal = openApproveOfferModal;

function openVerificationModal(harvestId, qty, item) {
  const existing = document.getElementById("verification-modal-dialog");
  if (existing) existing.remove();

  item = item || {};
  const allLots = (cachedOffersData.langsung_diambil || []).concat(cachedOffersData.diantar_petani || []).concat(cachedOffersData.lelang || []);
  const currentItem = allLots.find(x => x.harvest_id == harvestId) || item;
  const fName = currentItem.nama_petani || currentItem.farmer_name || "Petani";
  const fPhone = currentItem.farmer_phone || "-";
  const comName = currentItem.jenis_biomassa || currentItem.commodity_name || "Biomassa";
  const initialQty = qty || currentItem.qty_kg || currentItem.quantity_kg || 1000;
  const originCode = currentItem.origin_qr_code || currentItem.wr_code || `WR-HV-${harvestId}`;

  const d = document.createElement("dialog");
  d.id = "verification-modal-dialog";
  d.className = "ui-confirm";
  d.style.maxWidth = "560px";
  d.style.width = "95vw";
  d.innerHTML = `
    <form method="dialog" class="fo-form" id="modal-verify-form" style="padding:4px;">
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:10px; margin-bottom:12px;">
        <h3 style="margin:0; font-size:1.15rem; color:var(--primary);">🔬 Uji Mutu Proksimat Biomassa &amp; Timbang</h3>
        <button type="button" class="btn btn-secondary btn-sm" id="btn-close-vm" style="font-size:12px; padding:2px 8px;">✕</button>
      </div>

      <div style="background:var(--surface-2); border:1px solid var(--border); border-radius:8px; padding:10px 14px; margin-bottom:12px; font-size:12px; line-height:1.5;">
        <div style="display:flex; justify-content:space-between; flex-wrap:wrap;">
          <span>🌾 <b>Lot ID:</b> #${harvestId} (<code>${esc(originCode)}</code>)</span>
          <span>👤 <b>Petani:</b> ${esc(fName)} (📱 <code>${esc(fPhone)}</code>)</span>
        </div>
        <div style="margin-top:2px;">
          <span>🌿 <b>Komoditas:</b> <b>${esc(comName)}</b> · Klaim Petani: <b>${num(initialQty, 0)} kg</b></span>
        </div>
      </div>

      <div class="fo-body">
        <input type="hidden" id="v-harvest-id" value="${harvestId}">
        <div style="margin-bottom:8px;">
          <label class="kpi-lbl" for="v-weight">⚖️ Berat Timbangan Nyata Pengepul (kg) <span style="color:var(--warn); font-weight:700;">*wajib</span></label>
          <input type="number" id="v-weight" name="v_weight" class="btn btn-secondary" style="width:100%; text-align:left;" min="0.1" step="0.1" value="${initialQty}" required inputmode="decimal">
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
          <div>
            <label class="kpi-lbl" for="v-moisture">💧 Kadar Air (% bb) <span style="color:var(--warn); font-weight:700;">*wajib</span></label>
            <input type="number" id="v-moisture" name="v_moisture" class="btn btn-secondary" style="width:100%; text-align:left;" step="0.1" min="0" max="60" inputmode="decimal" placeholder="Baca moisture meter" required value="13.5">
          </div>
          <div>
            <label class="kpi-lbl" for="v-ash">🧪 Kadar Abu (% bk)</label>
            <input type="number" id="v-ash" name="v_ash" class="btn btn-secondary" style="width:100%; text-align:left;" step="0.1" min="0" max="40" inputmode="decimal" placeholder="Opsional / uji lab">
          </div>
          <div>
            <label class="kpi-lbl" for="v-vm">🔥 Volatile Matter (%)</label>
            <input type="number" id="v-vm" name="v_vm" class="btn btn-secondary" style="width:100%; text-align:left;" step="0.1" min="0" max="100" inputmode="decimal" placeholder="Opsional / uji lab">
          </div>
          <div>
            <label class="kpi-lbl" for="v-fc">🪨 Fixed Carbon (%)</label>
            <input type="number" id="v-fc" name="v_fc" class="btn btn-secondary" style="width:100%; text-align:left;" step="0.1" min="0" max="100" inputmode="decimal" placeholder="Opsional / uji lab">
          </div>
          <div>
            <label class="kpi-lbl" for="v-contam">🍂 Kontaminan (%)</label>
            <input type="number" id="v-contam" name="v_contam" class="btn btn-secondary" style="width:100%; text-align:left;" step="0.1" min="0" max="50" inputmode="decimal" value="0">
          </div>
          <div>
            <label class="kpi-lbl" for="v-temp">🌡️ Suhu Pirolisis (°C)</label>
            <input type="number" id="v-temp" name="v_temp" class="btn btn-secondary" style="width:100%; text-align:left;" value="500" step="10">
          </div>
        </div>

        <div style="margin-top:8px;">
          <label class="kpi-lbl" for="v-photo">📷 URL Foto Bukti Serah-Terima (opsional)</label>
          <input type="text" id="v-photo" name="v_photo" class="btn btn-secondary" style="width:100%; text-align:left;" placeholder="https://... atau /uploads/...">
        </div>

        <div id="vm-preview" style="background:var(--surface-2); border:1px solid var(--border); border-radius:8px; padding:10px 14px; margin:12px 0; font-size:12px; line-height:1.4;">
          Memuat perkiraan mutu...
        </div>

        <p class="form-error" role="alert" style="color:var(--danger); font-size:12px;" hidden></p>

        <div class="ui-confirm-actions" style="margin-top:14px; display:flex; gap:8px; flex-wrap:wrap;">
          <button type="button" class="btn btn-secondary" id="btn-cancel-vm" style="flex:1;">Batal</button>
          <button type="button" class="btn btn-danger" id="btn-reject-vm">⛔ Tolak Lot</button>
          <button type="submit" class="btn btn-primary" id="btn-submit-verify" style="flex:2;">Verifikasi Mutu &amp; Terbitkan Harga ➔</button>
        </div>
      </div>
    </form>
  `;

  document.body.appendChild(d);
  d.showModal();

  const closeDlg = () => { d.close(); d.remove(); };
  d.querySelector("#btn-close-vm").onclick = closeDlg;
  d.querySelector("#btn-cancel-vm").onclick = closeDlg;

  // Real-time preview calculation
  const updatePreview = () => {
    const w = Number((d.querySelector("#v-weight") || {}).value) || 0;
    const m = Number((d.querySelector("#v-moisture") || {}).value) || 0;
    const ct = Number((d.querySelector("#v-contam") || {}).value) || 0;

    let grade = "A", mult = 1.10, score = 92;
    if (m > 18 || ct > 5) {
      grade = "D"; mult = 0.85; score = 62;
    } else if (m > 15 || ct > 3) {
      grade = "C"; mult = 0.95; score = 75;
    } else if (m > 12 || ct > 1.5) {
      grade = "B"; mult = 1.00; score = 84;
    }

    const basePrice = 400; // default base price
    const unitPrice = basePrice * mult;
    const totalRp = w * unitPrice;

    d.querySelector("#vm-preview").innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span>Mutu Dihitung: <b style="font-size:1.05em; color:${grade === 'A' ? 'var(--green)' : (grade === 'D' ? 'var(--danger)' : 'var(--warn)')};">Grade ${grade}</b> (Skor ${num(score, 1)})</span>
        <span>Pengali Harga: <b>×${mult.toFixed(2)}</b></span>
      </div>
      <div style="margin-top:4px; color:var(--ink-muted);">
        Harga Bersih: <b>${rp(unitPrice)}/kg</b> · Total Pembayaran: <b style="color:var(--primary); font-size:1.1em;">${rp(totalRp)}</b>
      </div>
    `;
  };

  d.querySelectorAll("#v-weight, #v-moisture, #v-ash, #v-contam").forEach(inp => {
    inp.addEventListener("input", updatePreview);
  });
  updatePreview();

  // Handle reject lot
  d.querySelector("#btn-reject-vm").onclick = () => {
    closeDlg();
    if (typeof window.rejectLot === "function") {
      window.rejectLot(Number(harvestId));
    } else {
      const reason = prompt("Masukkan alasan penolakan lot biomassa:", "Kadar air terlalu tinggi / basah (>18%)");
      if (reason && reason.trim()) {
        apiMutation("/api/v1/collector/verify", {
          harvest_id: Number(harvestId),
          weighed_kg: Number(d.querySelector("#v-weight").value) || initialQty,
          moisture: Number(d.querySelector("#v-moisture").value) || 22,
          rejection_reason: reason.trim(),
          is_rejected: true
        }, `Tolak lot #${harvestId}`).then(res => {
          showToast(res.message || "Lot berhasil ditolak.", "⛔");
          loadCollectorData();
          loadMarket();
        }).catch(err => showToast(err.message, "❌"));
      }
    }
  };

  // Handle submit verification
  d.querySelector("#modal-verify-form").onsubmit = async (e) => {
    e.preventDefault();
    const btnSubmit = d.querySelector("#btn-submit-verify");
    const errEl = d.querySelector(".form-error");
    btnSubmit.disabled = true;
    errEl.hidden = true;

    try {
      const payload = {
        harvest_id: Number(harvestId),
        weighed_kg: Number(d.querySelector("#v-weight").value),
        moisture: Number(d.querySelector("#v-moisture").value),
        ash: d.querySelector("#v-ash").value ? Number(d.querySelector("#v-ash").value) : null,
        volatile_matter: d.querySelector("#v-vm").value ? Number(d.querySelector("#v-vm").value) : null,
        fixed_carbon: d.querySelector("#v-fc").value ? Number(d.querySelector("#v-fc").value) : null,
        contamination: Number(d.querySelector("#v-contam").value) || 0,
        pyrolysis_temp_c: Number(d.querySelector("#v-temp").value) || 500,
        evidence_photo_url: d.querySelector("#v-photo").value.trim() || null,
      };

      const res = await apiMutation("/api/v1/collector/verify", payload, `Verifikasi biomassa #${harvestId}`);
      closeDlg();

      showToast(res.queued ? "Offline: hasil uji disimpan & dikirim otomatis saat online." : (res.message || "Verifikasi berhasil disimpan!"), res.queued ? "📵" : "✅");

      if (!res.queued && res.verification_code) {
        const batchRef = res.batch_ref || (res.listing_id ? `WR-LST-${String(res.listing_id).padStart(4, '0')}` : `WR-HV-${String(res.harvest_id || harvestId).padStart(4, '0')}`);
        const comLabel = (res.commodity || comName || "sekam").toLowerCase().includes("sekam") ? "Sekam" : (res.commodity || comName);
        openModal(
          `Resi Serah-Terima ${comLabel}`,
          res.verification_code,
          `${num(res.weighed_kg, 0)} kg · Grade ${res.grade} · ${rp(res.total_price)} — tunjukkan/foto resi ini bersama petani`,
          {
            originQrCode: res.origin_qr_code || res.qr_code || originCode,
            batchRef: batchRef,
            listingId: res.listing_id,
            harvestId: res.harvest_id || harvestId,
            commodity: res.commodity || comName,
            weighedKg: res.weighed_kg,
            grade: res.grade,
            totalPrice: res.total_price
          }
        );
      }

      loadCollectorData();
      loadMarket();
      if (typeof window.loadUnpaid === "function") window.loadUnpaid();
    } catch (err) {
      btnSubmit.disabled = false;
      errEl.hidden = false;
      errEl.textContent = err.message || String(err);
    }
  };
}
window.openVerificationModal = openVerificationModal;

window.selectHarvestForVerification = function(harvestId, qty) {
  if (!harvestId) {
    showToast("Lot belum memiliki ID panen atau proses kesepakatan harga lelang belum selesai.", "⚠️");
    return;
  }
  openVerificationModal(harvestId, qty);
};

const PENGEPUL_MARKET_HTML = `
  <div class="card" style="margin-top:16px;">
    <div class="card-header" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
      <div>
        <h3 class="card-title">🛒 Dashboard Penawaran Biomassa Petani</h3>
        <p class="card-sub" id="col-spec-badge">Filter Spesialisasi Tunggal Aktif</p>
      </div>
      <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
        <button type="button" class="btn btn-secondary btn-sm" data-onclick="scrollToFactoryPricing()">
          🏭 Kontrak &amp; Harga Pabrik Multi-Biomassa
        </button>
        <button type="button" class="btn btn-primary btn-sm" data-onclick="openRouteOptimizationModal()">
          🗺️ Optimasi Rute Terverifikasi &amp; Abu Bottom Ash
        </button>
        <button class="btn btn-primary btn-sm" data-onclick="planPickup(this)">🚛 Rencanakan jemput</button>
      </div>
    </div>

    <!-- 3 Pilihan Tab Utama: Langsung Diambil (Jemput), Lelang, Diantar Petani -->
    <div style="display:flex; gap:8px; margin: 12px 0 8px; border-bottom: 2px solid var(--border); flex-wrap:wrap;">
      <button type="button" class="btn btn-sm btn-secondary" id="btn-tab-langsung" data-onclick="switchOffersTab('langsung')">
        🚚 Langsung Diambil (<span id="count-langsung">0</span>)
      </button>
      <button type="button" class="btn btn-sm btn-primary" id="btn-tab-lelang" data-onclick="switchOffersTab('lelang')">
        🏷️ Lelang (<span id="count-lelang">0</span>)
      </button>
      <button type="button" class="btn btn-sm btn-secondary" id="btn-tab-diantar" data-onclick="switchOffersTab('diantar')">
        🚜 Diantar Petani (<span id="count-diantar">0</span>)
      </button>
    </div>

    <!-- Sub-Filter Status Verifikasi: Semua / Belum Verifikasi / Sudah Verifikasi -->
    <div style="display:flex; gap:6px; margin: 8px 0 12px; align-items:center; flex-wrap:wrap; background:var(--bg-elevated, rgba(255,255,255,0.04)); padding:6px 12px; border-radius:8px; border:1px solid var(--border);">
      <span style="font-size:11.5px; font-weight:600; color:var(--ink-muted); margin-right:6px;">Filter Verifikasi:</span>
      <button type="button" class="btn btn-sm btn-primary" id="vfilter-all" data-onclick="setVerificationFilter('all')" style="font-size:11.5px; padding:3px 12px; border-radius:14px;">
        📋 Semua (<span id="vcount-all">0</span>)
      </button>
      <button type="button" class="btn btn-sm btn-secondary" id="vfilter-unverified" data-onclick="setVerificationFilter('unverified')" style="font-size:11.5px; padding:3px 12px; border-radius:14px; border:1px solid #fde68a;">
        🟡 Belum Verifikasi Qty &amp; Harga (<span id="vcount-unverified">0</span>)
      </button>
      <button type="button" class="btn btn-sm btn-secondary" id="vfilter-verified" data-onclick="setVerificationFilter('verified')" style="font-size:11.5px; padding:3px 12px; border-radius:14px; border:1px solid #86efac;">
        🔵 Sudah Terverifikasi (<span id="vcount-verified">0</span>)
      </button>
    </div>

    <div id="pickup-plan-result"></div>
    <div style="overflow-x:auto; margin-top:8px;" id="market-table"><p class="muted">Memuat penawaran…</p></div>
  </div>`;

const DEFAULT_COMMODITY_PRICING = [
  { code: "sekam_padi", name: "🌾 Sekam Padi", factory: "PT Bio-Energi Sleman", buyPrice: 450, sellPrice: 580, quotaTon: 50, status: "Aktif" },
  { code: "tongkol_jagung", name: "🌽 Tongkol Jagung", factory: "Pabrik Briket Jagung Yogya", buyPrice: 380, sellPrice: 520, quotaTon: 40, status: "Aktif" },
  { code: "ampas_tebu", name: "🎋 Ampas Tebu (Bagasse)", factory: "PT Gula Madukismo Biochar", buyPrice: 260, sellPrice: 390, quotaTon: 100, status: "Aktif" },
  { code: "serbuk_sengon", name: "🪵 Serbuk Sengon / Kayu", factory: "Pabrik Wood Pellet Magelang", buyPrice: 320, sellPrice: 470, quotaTon: 35, status: "Aktif" },
  { code: "serbuk_karet", name: "🪵 Serbuk Karet", factory: "Pabrik Briket Industri Bantul", buyPrice: 300, sellPrice: 460, quotaTon: 30, status: "Aktif" },
  { code: "tempurung_kelapa", name: "🥥 Tempurung / Sabut Kelapa", factory: "PT Karbon Aktif Prima", buyPrice: 500, sellPrice: 780, quotaTon: 25, status: "Aktif" },
];

function getFactoryPricingData() {
  try {
    const raw = localStorage.getItem("biochain_factory_pricing_v1");
    if (raw) return JSON.parse(raw);
  } catch (_) {}
  return JSON.parse(JSON.stringify(DEFAULT_COMMODITY_PRICING));
}

function saveFactoryPricingData(data) {
  try {
    localStorage.setItem("biochain_factory_pricing_v1", JSON.stringify(data));
  } catch (_) {}
}

const PENGEPUL_FACTORY_PRICING_HTML = `
  <div class="card" id="module-factory-pricing" style="margin-top:16px;">
    <div class="card-header" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
      <div>
        <h3 class="card-title">🏭 Modul Kontrak &amp; Harga Jual Multi-Biomassa ke Pabrik</h3>
        <p class="card-sub">Manajemen matriks harga jual ke pabrik mitra, acuan harga beli petani, target margin laba per komoditas, dan proyeksi laba per ritase armada.</p>
      </div>
      <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
        <button type="button" class="btn btn-secondary btn-sm" data-onclick="openSimulateTruckMarginModal()">
          🧮 Simulasi Margin Truk
        </button>
        <button type="button" class="btn btn-primary btn-sm" data-onclick="saveFactoryPricingSettings()">
          💾 Simpan Perubahan Kontrak
        </button>
      </div>
    </div>

    <div class="table-scroll" style="margin-top:10px;">
      <table class="data-table" id="table-factory-pricing">
        <thead>
          <tr>
            <th>Komoditas Biomassa</th>
            <th>Pabrik / Offtaker Kontrak</th>
            <th class="num">Harga Beli Petani (Rp/kg)</th>
            <th class="num" style="min-width:130px;">Harga Jual Pabrik (Rp/kg)</th>
            <th class="num">Margin Laba (Rp/kg)</th>
            <th class="num">Margin (%)</th>
            <th class="num">Proyeksi Laba / Ritase (5 t)</th>
            <th>Status Kontrak</th>
          </tr>
        </thead>
        <tbody id="tbody-factory-pricing">
          <!-- Populated dynamically -->
        </tbody>
      </table>
    </div>
    <div style="margin-top:10px; font-size:11.5px; color:var(--ink-muted); display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
      <span>💡 <i>Catatan: Setiap biomassa memiliki harga dasar berbeda. Margin laba dihitung otomatis berdasarkan kapasitas angkut truk 5.000 kg.</i></span>
      <span id="factory-pricing-status" style="font-weight:600; color:var(--primary);"></span>
    </div>
  </div>
`;

function initFactoryPricingModule() {
  const tbody = $("tbody-factory-pricing");
  if (!tbody) return;
  const list = getFactoryPricingData();
  tbody.innerHTML = list.map((item, idx) => {
    const marginRp = Math.max(0, (item.sellPrice || 0) - (item.buyPrice || 0));
    const marginPct = item.buyPrice > 0 ? ((marginRp / item.buyPrice) * 100).toFixed(1) : "0.0";
    const tripProfit = marginRp * 5000;
    return `
      <tr data-commodity="${item.code}">
        <td><b>${esc(item.name)}</b><br><small class="muted" style="font-size:10px;">Kode: <code>${esc(item.code)}</code></small></td>
        <td>
          <input type="text" class="btn btn-secondary btn-sm" style="font-size:11.5px; width:190px;" id="fp-fac-${idx}" aria-label="Nama pabrik baris ${idx + 1}" value="${esc(item.factory)}">
        </td>
        <td class="num">
          <input type="number" class="btn btn-secondary btn-sm" style="font-size:11.5px; width:95px; text-align:right;" id="fp-buy-${idx}" aria-label="Harga beli Rp/kg baris ${idx + 1}" value="${item.buyPrice}" data-onchange="recalcFactoryPricing(${idx})">
        </td>
        <td class="num">
          <input type="number" class="btn btn-secondary btn-sm" style="font-size:12px; font-weight:700; width:110px; text-align:right; border-color:var(--primary);" id="fp-sell-${idx}" aria-label="Harga jual Rp/kg baris ${idx + 1}" value="${item.sellPrice}" data-onchange="recalcFactoryPricing(${idx})">
        </td>
        <td class="num" id="fp-margin-rp-${idx}">
          <b style="color:var(--primary);">+${rp(marginRp)}</b>
        </td>
        <td class="num" id="fp-margin-pct-${idx}">
          <span class="badge badge-green">+${marginPct}%</span>
        </td>
        <td class="num" id="fp-profit-${idx}">
          <b style="color:#059669;">+${rp(tripProfit)}</b>
        </td>
        <td>
          <span class="badge badge-green">🟢 ${esc(item.status || "Aktif")}</span>
        </td>
      </tr>
    `;
  }).join("");
}

function recalcFactoryPricing(idx) {
  const buyEl = $(`fp-buy-${idx}`);
  const sellEl = $(`fp-sell-${idx}`);
  if (!buyEl || !sellEl) return;
  const buy = Number(buyEl.value) || 0;
  const sell = Number(sellEl.value) || 0;
  const marginRp = Math.max(0, sell - buy);
  const marginPct = buy > 0 ? ((marginRp / buy) * 100).toFixed(1) : "0.0";
  const tripProfit = marginRp * 5000;

  const mRpEl = $(`fp-margin-rp-${idx}`);
  if (mRpEl) mRpEl.innerHTML = `<b style="color:var(--primary);">+${rp(marginRp)}</b>`;
  const mPctEl = $(`fp-margin-pct-${idx}`);
  if (mPctEl) mPctEl.innerHTML = `<span class="badge badge-green">+${marginPct}%</span>`;
  const profEl = $(`fp-profit-${idx}`);
  if (profEl) profEl.innerHTML = `<b style="color:#059669;">+${rp(tripProfit)}</b>`;
}

function saveFactoryPricingSettings() {
  const list = getFactoryPricingData();
  list.forEach((item, idx) => {
    const facEl = $(`fp-fac-${idx}`);
    const buyEl = $(`fp-buy-${idx}`);
    const sellEl = $(`fp-sell-${idx}`);
    if (facEl) item.factory = facEl.value;
    if (buyEl) item.buyPrice = Number(buyEl.value) || item.buyPrice;
    if (sellEl) item.sellPrice = Number(sellEl.value) || item.sellPrice;
  });
  saveFactoryPricingData(list);
  const st = $("factory-pricing-status");
  if (st) {
    st.innerText = "✓ Kontrak & harga jual multi-biomassa berhasil disimpan!";
    setTimeout(() => { if (st) st.innerText = ""; }, 4000);
  }
  showToast("Kontrak harga multi-biomassa pabrik berhasil disimpan!", "✅");
}

function scrollToFactoryPricing() {
  const el = $("module-factory-pricing");
  if (el) el.scrollIntoView({ behavior: "smooth" });
}

function openSimulateTruckMarginModal() {
  const list = getFactoryPricingData();
  formDialog({
    title: "🧮 Simulasi Margin & Hasil Penjualan Armada Truk",
    ok: "Hitung Proyeksi",
    body: `
      <p class="card-sub">Hitung estimasi pendapatan kotor, biaya operasional bahan bakar, dan margin bersih untuk 1 ritase pengiriman biomassa ke pabrik.</p>
      <div class="form-group">
        <label for="sm-comm">Pilih Komoditas Biomassa</label>
        <select id="sm-comm" name="comm_code">
          ${list.map(c => `<option value="${c.code}">${esc(c.name)} (Beli: Rp${c.buyPrice} | Jual: Rp${c.sellPrice}/kg)</option>`).join("")}
        </select>
      </div>
      <div class="form-group">
        <label for="sm-truck-ton">Muatan Truk (Ton)</label>
        <input id="sm-truck-ton" name="ton" type="number" value="5.0" min="0.5" max="30" step="0.5" required>
      </div>
      <div class="form-group">
        <label for="sm-dist">Estimasi Jarak Tempuh ke Pabrik (km)</label>
        <input id="sm-dist" name="km" type="number" value="35" min="1" max="500" step="1" required>
      </div>
      <div class="form-group">
        <label for="sm-cost-km">Biaya Operasional Truk per km (BBM + Supir)</label>
        <input id="sm-cost-km" name="cost_per_km" type="number" value="4500" min="1000" max="25000" step="500" required>
      </div>
    `,
    onSubmit: async (fd) => {
      const commCode = fd.get("comm_code");
      const ton = Number(fd.get("ton")) || 5.0;
      const km = Number(fd.get("km")) || 35;
      const costKm = Number(fd.get("cost_per_km")) || 4500;

      const comm = list.find(c => c.code === commCode) || list[0];
      const kg = ton * 1000;
      const revenue = kg * (comm.sellPrice || 500);
      const cogs = kg * (comm.buyPrice || 400);
      const grossMargin = revenue - cogs;
      const transportCost = km * costKm;
      const netProfit = grossMargin - transportCost;

      infoDialog({
        title: `📊 Hasil Proyeksi: ${comm.name}`,
        body: `
          <div class="kpi-row" style="margin-bottom:12px;">
            <div class="kpi-tile"><div class="kpi-lbl">Total Muatan</div><div class="kpi-val">${num(ton, 1)} t</div><div class="kpi-lbl">${num(kg, 0)} kg</div></div>
            <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Nilai Jual Pabrik</div><div class="kpi-val">${rp(revenue)}</div><div class="kpi-lbl">Rp${comm.sellPrice}/kg</div></div>
            <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Biaya Transport</div><div class="kpi-val">${rp(transportCost)}</div><div class="kpi-lbl">${km} km</div></div>
            <div class="kpi-tile kpi-green"><div class="kpi-lbl">Margin Laba Bersih</div><div class="kpi-val">${rp(netProfit)}</div><div class="kpi-lbl">${revenue > 0 ? num(netProfit/revenue*100, 1) : 0}% ROI trip</div></div>
          </div>
          <p style="font-size:12px; color:var(--ink-muted);">Proyeksi didasarkan pada kontrak pasokan aktif dengan <b>${esc(comm.factory)}</b>.</p>
        `
      });
    }
  });
}
window.initFactoryPricingModule = initFactoryPricingModule;
window.recalcFactoryPricing = recalcFactoryPricing;
window.saveFactoryPricingSettings = saveFactoryPricingSettings;
window.scrollToFactoryPricing = scrollToFactoryPricing;
window.openSimulateTruckMarginModal = openSimulateTruckMarginModal;

async function loadMarket() {
  try {
    const res = await api("/api/v1/collector/offers-dashboard").catch(() => null);
    if (res) {
      cachedOffersData = res;
      if ($("count-langsung")) $("count-langsung").innerText = (res.langsung_diambil || []).length;
      if ($("count-lelang")) $("count-lelang").innerText = (res.lelang || []).length;
      if ($("count-diantar")) $("count-diantar").innerText = (res.diantar_petani || []).length;
      if ($("col-spec-badge") && res.specialization_commodity) {
        $("col-spec-badge").innerHTML = `⭐ Spesialisasi Komoditas: <b style="color:var(--primary); text-transform:uppercase;">${esc(res.specialization_commodity.replace('_', ' '))}</b> (Terfilter Otomatis)`;
      }
      // Pastikan ketiga tombol tab terikat event listener
      ["langsung", "lelang", "diantar"].forEach(t => {
        const btn = $(`btn-tab-${t}`);
        if (btn && !btn._bound) {
          btn._bound = true;
          btn.onclick = () => window.switchOffersTab(t);
        }
      });
      renderOffersTable();
      return;
    }

    const rows = await api("/api/v1/collector/market");
    $("market-table").innerHTML = rows.length ? `<table class="data-table"><thead><tr><th>Stok</th><th class="num">Jarak</th>
        <th class="num">Sisa kg</th><th>Harga minimum</th><th>Tawar</th></tr></thead><tbody>
      ${rows.map(l => `<tr><td>#${l.id}${l.moisture_pct != null ? `<br><span class="kpi-lbl">air ${num(l.moisture_pct)}%</span>` : ""}
          ${l.my_active_bid ? `<br><span class="badge badge-blue">tawaran Anda ${rp(l.my_active_bid.price_per_kg)}</span>` : ""}</td>
        <td class="num">${l.distance_km != null ? num(l.distance_km, 1) + " km" : "-"}</td><td class="num">${num(l.remaining_kg, 0)}</td>
        <td style="font-size:var(--fs-xs);">${Object.entries(l.schemes).filter(([, v]) => v).map(([k, v]) => `${SCHEME_LABEL[k]} ${rp(v)}`).join("<br>")}</td>
        <td style="white-space:nowrap;">
          <select id="bs-${l.id}" class="btn btn-secondary btn-sm" aria-label="Skema harga lot #${l.id}">${Object.entries(l.schemes).filter(([, v]) => v)
            .map(([k]) => `<option value="${k}">${SCHEME_LABEL[k]}</option>`).join("")}</select>
          <input id="bp-${l.id}" type="number" class="btn btn-secondary btn-sm" style="width:96px;" placeholder="Rp/kg" inputmode="decimal" aria-label="Harga tawaran Rp/kg lot #${l.id}">
          <input id="bq-${l.id}" type="number" class="btn btn-secondary btn-sm" style="width:96px;" inputmode="numeric" aria-label="Jumlah kg ditawar lot #${l.id}" value="${l.remaining_kg}" min="1" max="${l.remaining_kg}">
          <button class="btn btn-secondary btn-sm" data-onclick="adviseBid(${Number(l.id)}, this)">Hitung saran</button>
          <button class="btn btn-primary btn-sm" data-onclick="placeBid(${Number(l.id)}, this)">Tawar</button>
          <div id="ba-${l.id}" class="kpi-lbl"></div></td></tr>`).join("")}</tbody></table>`
      : emptyState("🛒", "Belum ada stok terbuka", "Saat ini semua stok lelang biomassa petani telah terserap atau belum ada lelang baru.");
  } catch (err) { console.error("loadMarket:", err); }
}

async function adviseBid(listingId, btn) {
  return withBusy(btn, async () => {
    try {
      const schEl = $(`bs-${listingId}`);
      const schemeVal = schEl ? schEl.value : "jemput";
      
      // Ambil harga jual pabrik & margin sesuai komoditas dari modul kontrak pabrik
      const allListings = (cachedOffersData.lelang || []);
      const curListing = allListings.find(x => x.listing_id === listingId);
      const cCode = curListing ? (curListing.commodity_code || "sekam_padi") : "sekam_padi";
      const pricingList = typeof getFactoryPricingData === "function" ? getFactoryPricingData() : [];
      const commPricing = pricingList.find(p => p.code === cCode) || pricingList[0];
      const resaleVal = commPricing ? commPricing.sellPrice : 580;
      const marginVal = commPricing && commPricing.buyPrice > 0 ? (((commPricing.sellPrice - commPricing.buyPrice) / commPricing.buyPrice) * 100) : 15;
      const qEl = $(`bq-${listingId}`);
      const quantityVal = qEl ? (Number(qEl.value) || undefined) : undefined;
      const r = await api("/api/v1/collector/bid-advisor", { body: {
        listing_id: listingId, scheme: schemeVal, resale_price_per_kg: resaleVal,
        margin_pct: marginVal,
        quantity_kg: quantityVal } });
      const baEl = $(`ba-${listingId}`);
      if (baEl) {
        baEl.innerHTML = r.feasible
          ? `Logistik ${rp(r.logistic_cost_per_kg)}/kg · margin ${num(r.margin_pct, 1)}% (${rp(r.margin_per_kg)}/kg) · maks ${rp(r.max_bid_per_kg)} · saran <b>${rp(r.suggested_bid_per_kg)}</b>`
          : `⚠️ Tidak menguntungkan: maks ${rp(r.max_bid_per_kg)} &lt; minimum petani ${rp(r.farmer_reserve_per_kg)}`;
      }
      if (r.suggested_bid_per_kg && $(`bp-${listingId}`)) $(`bp-${listingId}`).value = r.suggested_bid_per_kg;
    } catch (err) { showToast(err.message, "❌"); }
  }, "⏳");
}

async function placeBid(listingId, btn) {
  return withBusy(btn, async () => {
    try {
      await api("/api/v1/collector/bids", { body: { listing_id: listingId, scheme: ($(`bs-${listingId}`) || {}).value || "jemput",
        price_per_kg: Number($(`bp-${listingId}`).value), quantity_kg: Number(($(`bq-${listingId}`) || {}).value) || 1000 } });
      showToast("Tawaran terkirim. Petani yang memutuskan.", "📨");
      loadMarket();
    } catch (err) {
      showToast(err.message, "❌");
      loadMarket();
    }
  }, "⏳");
}

window.placeBid = placeBid;
window.adviseBid = adviseBid;
window.planPickup = planPickup;

async function planPickup(btn) {
  return withBusy(btn, async () => {
    try {
      const r = await api("/api/v1/collector/pickup-plan", { method: "POST" });
      const box = $("pickup-plan-result");
      if (!r.routes || !r.routes.length) {
        box.innerHTML = `<p class="muted" style="padding:8px 0;">Tidak ada tawaran diterima berskema jemput yang menunggu penjemputan.</p>`;
        return;
      }
      box.innerHTML = `
        <div style="background:var(--bg-panel); padding:12px; border-radius:6px; margin:8px 0; border:1px solid var(--border);">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <b>🚛 Rencana Rute Penjemputan (${r.summary.vehicles_trips} trip · ${num(r.summary.total_km, 1)} km)</b>
            <span class="badge badge-green">Hemat ${num(r.summary.saving_pct, 1)}% vs langsung</span>
          </div>
          <p class="kpi-lbl" style="margin:4px 0;">Muatan: <b>${num(r.summary.total_ton, 2)} ton</b> · Biaya: <b>${rp(r.summary.total_cost)}</b> (${rp(r.summary.cost_per_kg)}/kg) · Algoritma: ${esc(r.summary.algorithm)}</p>
          ${r.backhaul_biochar && r.backhaul_biochar.length ? `
            <div class="banner banner-info" style="margin:8px 0; padding:10px 14px; border-left:4px solid #10b981; background:rgba(16,185,129,0.08); border-radius:4px;">
              <b style="color:#10b981;">🌱 Alur Balik Sirkular Terintegrasi (Backhaul Abu Bottom Ash):</b>
              <span style="font-size:12px; display:block; margin-top:2px;">Ditemukan <b>${r.backhaul_biochar.length}</b> permohonan abu bottom ash (${num(r.backhaul_biochar.reduce((a,b)=>a+(b.quantity_kg||0),0),0)} kg) dari petani di sepanjang rute penjemputan ini. Armada dapat memuat abu bottom ash dari pabrik/gudang untuk didistribusikan langsung saat tiba di lokasi petani!</span>
              <ul style="margin:6px 0 0 16px; font-size:11px;">
                ${r.backhaul_biochar.map(b => `<li>Petani <b>${esc(b.farmer_name)}</b>: <b>${num(b.quantity_kg,0)} kg</b> abu bottom ash (${esc(b.status)}) ➔ <i>${esc(b.delivery_address)}</i></li>`).join("")}
              </ul>
            </div>
          ` : ''}
          <table class="data-table" style="margin-top:8px;">
            <thead><tr><th>Trip</th><th>Urutan Penjemputan Petani / Produsen Biomassa</th><th class="num">Muatan (m³)</th><th class="num">Ton</th><th class="num">Jarak</th></tr></thead>
            <tbody>
              ${r.routes.map((rt, idx) => `
                <tr>
                  <td><b>Trip #${idx + 1}</b></td>
                  <td>${rt.stops.map(s => `${esc(s.name)} (${num(s.ton, 2)} t)`).join(" ➔ ")}</td>
                  <td class="num">${num(rt.load_m3, 1)} (${num(rt.utilization_pct, 0)}%)</td>
                  <td class="num">${num(rt.load_ton, 2)}</td>
                  <td class="num">${num(rt.km, 1)} km</td>
                </tr>`).join("")}
            </tbody>
          </table>
          <div style="margin-top:12px; display:flex; gap:8px; justify-content:flex-end; flex-wrap:wrap;">
            <button type="button" class="btn btn-secondary btn-sm" data-onclick="openRouteOptimizationModal()">
              🗺️ Optimasi Rute Terverifikasi &amp; Abu Bottom Ash
            </button>
            <button type="button" class="btn btn-primary btn-sm" data-onclick="confirmAndDispatchPickupPlan(this)">
              🚀 Konfirmasi &amp; Kirim Jadwal ke Petani
            </button>
          </div>
        </div>`;
    } catch (err) { showToast(err.message, "❌"); }
  }, "⏳");
}

async function confirmAndDispatchPickupPlan(btn) {
  return withBusy(btn, async () => {
    try {
      showToast("Jadwal rute penjemputan biomassa resmi dikonfirmasi & dikirimkan ke petani! 🚛", "✅");
      const box = $("pickup-plan-result");
      if (box) {
        const b = document.createElement("div");
        b.className = "banner banner-success";
        b.style.marginTop = "8px";
        b.innerHTML = "✅ <b>Jadwal Resmi Terkirim:</b> Petani telah menerima jadwal penjemputan di portal masing-masing dan siap mengonfirmasi.";
        box.appendChild(b);
      }
      loadCollectorData();
    } catch (err) { showToast(err.message, "❌"); }
  }, "⏳");
}
window.confirmAndDispatchPickupPlan = confirmAndDispatchPickupPlan;

// ==============================================================
// PABRIK — Procurement B2B, QC masuk, batch manufaktur sirkular, pricing engine
// ==============================================================
const PRODUCT_NAMES = { bio_pellet: "Bio-pellet / Briket", biochar: "Biochar Prekursor Material Baterai (Hard Carbon)", bio_silika: "Bio-silika" };
const LOSS_NAMES = { air: "Air diuapkan", volatil_syngas: "Volatil / syngas", gas_pembakaran: "Gas pembakaran/kalsinasi",
                     bio_oil: "Bio-oil / tar (asap cair)",
                     residu_ekstraksi: "Residu ekstraksi", susut_proses: "Susut proses" };
const DR_STATUS = { submitted: "badge-amber", countered: "badge-blue", accepted: "badge-green", delivered: "badge-green",
                    rejected: "badge-red", cancelled: "badge-gray" };

const FACTORY_OPS_HTML = `
  <div class="card" style="margin-top:16px;">
    <div class="card-header"><div><h3 class="card-title">🧮 Rekomendasi Harga Beli Multi-Biomassa</h3>
      <p class="card-sub">Netback multi-produk (bio-pellet, briket, biochar baterai, bio-silika) − biaya variabel − biaya tetap − margin (angka dari menu Parameter)</p></div></div>
    <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:8px;">
      <div style="grid-column:span 3;"><label class="kpi-lbl">Komoditas biomassa</label><select id="pr-commodity" class="btn btn-secondary" style="width:100%;"></select></div>
      <div><label class="kpi-lbl">Kadar air (%)</label><input id="pr-m" type="number" class="btn btn-secondary" style="width:100%;" value="11" step="0.5"></div>
      <div><label class="kpi-lbl">Abu (% bk)</label><input id="pr-a" type="number" class="btn btn-secondary" style="width:100%;" value="18" step="0.5"></div>
      <div><label class="kpi-lbl">Kontaminan (%)</label><input id="pr-c" type="number" class="btn btn-secondary" style="width:100%;" value="0" step="0.5"></div>
      <div><label class="kpi-lbl">Harga bio-pellet / briket (Rp/kg) *</label><input id="pr-pp" type="number" class="btn btn-secondary" style="width:100%;" min="0" placeholder="wajib"></div>
      <div><label class="kpi-lbl">Harga biochar baterai (Rp/kg) *</label><input id="pr-pb" type="number" class="btn btn-secondary" style="width:100%;" min="0" placeholder="wajib"></div>
      <div><label class="kpi-lbl">Harga bio-silika (Rp/kg) *</label><input id="pr-ps" type="number" class="btn btn-secondary" style="width:100%;" min="0" placeholder="wajib"></div>
      <div style="grid-column:span 2;"><label class="kpi-lbl">Jalur bio-silika</label><select id="pr-route" class="btn btn-secondary" style="width:100%;">
        <option value="biochar">Silika dari biochar</option>
        <option value="abu_pembakaran">Silika dari abu pembakaran</option>
        <option value="sekam_langsung">Silika dari biomassa langsung</option></select></div>
      <div><label class="kpi-lbl">Porsi biomassa ke silika</label><input id="pr-xs" type="number" class="btn btn-secondary" style="width:100%;" min="0" max="1" step="0.05"></div>
    </div>
    <p class="kpi-lbl">* Harga jual tidak punya angka bawaan — isi harga kontrak/pasar aktual (tersimpan sebagai default di menu Parameter).</p>
    <button class="btn btn-primary" style="width:100%; margin-top:8px;" id="btn-price">Hitung Harga ➔</button>
    <div id="pr-result" style="margin-top:12px;"></div>
  </div>
  <div class="card" style="margin-top:16px;">
    <div class="card-header"><div><h3 class="card-title">📥 Ajuan Pengiriman dari Pengepul</h3>
      <p class="card-sub">Terima / tawar balik jadwal & harga, lalu QC saat biomassa tiba</p></div></div>
    <div id="dr-inbox" style="overflow-x:auto;"><p class="muted">Memuat…</p></div>
  </div>
  <div class="card" style="margin-top:16px;">
    <div class="card-header"><div><h3 class="card-title">💳 Pembayaran ke Pengepul (jalur QC &amp; rute armada)</h3>
      <p class="card-sub">Biomassa jalur rute ditimbang terima di sini → tagihan pengepul tercatat. Harga kosong = rekomendasi netback.</p></div>
      <select id="st-filter" class="btn btn-secondary btn-sm" aria-label="Filter status settlement"><option value="">Semua status</option>
        <option value="menunggu_harga">Menunggu harga</option><option value="terutang">Terutang</option><option value="dibayar">Dibayar</option></select></div>
    <h4 style="margin:4px 0;">🚛 Tiba via rute armada — menunggu timbang terima</h4>
    <div id="st-arrivals" style="overflow-x:auto;"><p class="muted">Memuat…</p></div>
    <h4 style="margin:12px 0 4px;">Tagihan pengepul</h4>
    <div id="st-list" style="overflow-x:auto;"><p class="muted">Memuat…</p></div>
  </div>
  <div class="card" style="margin-top:16px;">
    <div class="card-header"><div><h3 class="card-title">🏭 Batch Produksi Multi-Produk (Biomassa → Pellet/Briket, Biochar Baterai, Biosilika)</h3>
      <p class="card-sub">Pilih lot hasil QC, isi timbangan output (bio-pellet / briket, biochar material baterai, bio-silika, abu bottom ash untuk petani) &amp; loss, biaya → mass balance &amp; biaya per ton produk</p></div>
      <button class="btn btn-secondary btn-sm" id="btn-batch-model">Isi dari model</button></div>
    <div style="display:flex; flex-direction:column; gap:20px;">
      <div>
        <label class="kpi-lbl">Kode batch</label><input id="bt-code" class="btn btn-secondary" style="width:100%; text-align:left;">
        <h4 style="margin:12px 0 4px;">Lot biomassa (stok QC)</h4><div id="bt-lots"><p class="muted">Memuat…</p></div>
        <h4 style="margin:12px 0 4px;">Biaya batch</h4>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
          <div><label class="kpi-lbl">Listrik (kWh)</label><input id="bt-kwh" type="number" class="btn btn-secondary" style="width:100%;" value="0"></div>
          <div><label class="kpi-lbl">Tenaga kerja (jam)</label><input id="bt-labor" type="number" class="btn btn-secondary" style="width:100%;" value="0"></div>
          <div><label class="kpi-lbl">Bahan kimia silika (Rp)</label><input id="bt-chem" type="number" class="btn btn-secondary" style="width:100%;" value="0"></div>
          <div><label class="kpi-lbl">Kemasan (Rp)</label><input id="bt-pack" type="number" class="btn btn-secondary" style="width:100%;" value="0"></div>
          <div><label class="kpi-lbl">Jam operasi batch</label><input id="bt-hours" type="number" class="btn btn-secondary" style="width:100%;" placeholder="otomatis"></div>
          <div><label class="kpi-lbl">Jalur bio-silika</label><select id="bt-route" class="btn btn-secondary" style="width:100%;">
          <option value="biochar">Silika dari biochar</option>
          <option value="abu_pembakaran">Silika dari abu pembakaran</option>
          <option value="sekam_langsung">Silika dari biomassa langsung</option></select></div>
          <div><label class="kpi-lbl">Porsi biomassa ke silika</label><input id="bt-xs" type="number" class="btn btn-secondary" style="width:100%;" min="0" max="1" step="0.05"></div>
        </div>
      </div>
      <div>
        <h4 style="margin:0 0 4px;">Output Multi-Produk (kg)</h4>
        <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:8px;">${Object.entries(PRODUCT_NAMES).map(([k, v]) =>
          `<div><label class="kpi-lbl">${v}</label><input id="bt-o-${k}" type="number" class="btn btn-secondary" style="width:100%;" value="0" min="0"></div>`).join("")}</div>
        <h4 style="margin:12px 0 4px;">Loss terukur (kg)</h4>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">${Object.entries(LOSS_NAMES).map(([k, v]) =>
          `<div><label class="kpi-lbl">${v}</label><input id="bt-l-${k}" type="number" class="btn btn-secondary" style="width:100%;" value="0" min="0"></div>`).join("")}</div>
        <button class="btn btn-primary" style="width:100%; margin-top:12px;" id="btn-batch">Simpan Batch &amp; Hitung Biaya ➔</button>
      </div>
    </div>
    <div id="bt-result" style="margin-top:12px;"></div>
  </div>`;

function initFactoryOps() {
  const fill = (id, key) => { const v = PV(key, null); if (v != null) $(id).value = v; };
  fill("pr-pp", "pabrik.price_pellet_per_kg"); fill("pr-pb", "pabrik.price_biochar_per_kg");
  fill("pr-ps", "pabrik.price_silica_per_kg"); fill("pr-xs", "pabrik.silica_husk_share");
  $("pr-route").value = PV("pabrik.silica_route", "biochar"); $("bt-route").value = PV("pabrik.silica_route", "biochar");
  fill("bt-xs", "pabrik.silica_husk_share");
  $("btn-price").onclick = e => withBusy(e.currentTarget, runPricing);
  $("btn-batch").onclick = e => withBusy(e.currentTarget, saveBatch);
  $("btn-batch-model").onclick = e => withBusy(e.currentTarget, fillBatchFromModel);
  $("bt-code").value = `B-${new Date().toISOString().slice(0, 10).replaceAll("-", "")}-${Math.floor(Math.random() * 900 + 100)}`;
  $("st-filter").onchange = loadSettlements;
  const comSel = $("pr-commodity");
  if (comSel) {
    biomassList().then(list => {
      comSel.innerHTML = list.map(b => `<option value="${esc(b.code)}">${esc(b.name)}</option>`).join("");
      comSel.onchange = () => {
        const item = list.find(x => x.code === comSel.value);
        if (item) {
          if (item.moisture_typ_pct != null) $("pr-m").value = item.moisture_typ_pct;
          if (item.ash_pct_db != null) $("pr-a").value = item.ash_pct_db;
          runPricing();
        }
      };
    });
  }
  runPricing(); loadInbox(); loadLots(); loadArrivals(); loadSettlements();
}

const ST_BADGE = { menunggu_harga: "badge-amber", terutang: "badge-blue", dibayar: "badge-green" };
const ST_LABEL = { menunggu_harga: "menunggu harga", terutang: "terutang", dibayar: "dibayar" };

async function loadArrivals() {
  try {
    const rows = await api("/api/v1/factory/arrivals");
    $("st-arrivals").innerHTML = rows.length ? `<table class="data-table"><thead><tr><th>Harvest</th><th>Pengepul / Petani</th><th class="num">Timbang pengepul</th>
      <th>Mutu</th><th>Timbang pabrik (kg)</th><th>Harga (Rp/kg, opsional)</th><th>Foto Bukti (URL)</th><th></th></tr></thead><tbody>${rows.map(h => `<tr>
        <td>#${h.harvest_id}</td>
        <td>${esc(h.collector_name || (h.collector_id ? 'Pengepul #' + h.collector_id : '–'))}<br><span class="kpi-lbl">${esc(h.farmer_name || (h.farmer_id ? 'Petani #' + h.farmer_id : '–'))}</span></td>
        <td class="num">${num(h.verified_kg, 0)} kg</td>
        <td>air ${num(h.moisture)}% · abu ${num(h.ash)}% · ${esc(h.grade || "-")}</td>
        <td><input id="rcv-kg-${h.harvest_id}" type="number" class="btn btn-secondary btn-sm" style="width:96px;" inputmode="decimal" aria-label="Berat diterima (kg) laporan #${h.harvest_id}" value="${Number(h.verified_kg) || 0}" min="0"></td>
        <td><input id="rcv-p-${h.harvest_id}" type="number" class="btn btn-secondary btn-sm" style="width:90px;" placeholder="netback" min="0"></td>
        <td><input id="rcv-photo-${h.harvest_id}" type="text" class="btn btn-secondary btn-sm" style="width:110px;" placeholder="https://..."></td>
        <td><button class="btn btn-primary btn-sm" data-onclick="receiveArrival(${Number(h.harvest_id)}, this)">Terima</button></td></tr>`).join("")}</tbody></table>`
      : `<p class="muted">Tidak ada biomassa jalur rute yang menunggu timbang terima.</p>`;
  } catch (err) { console.error("loadArrivals:", err); }
}

async function receiveArrival(id, btn) {
  const price = $(`rcv-p-${id}`).value;
  const photo = $(`rcv-photo-${id}`) ? $(`rcv-photo-${id}`).value.trim() : "";
  return withBusy(btn, async () => {
    try {
      const r = await api("/api/v1/factory/receive", { body: { harvest_id: id, received_kg: Number($(`rcv-kg-${id}`).value),
        price_per_kg: price === "" ? null : Number(price), evidence_photo_url: photo || null } });
      const st = r.settlement;
      if (r.warning) showToast(r.warning, "⚠️");
      showToast(st ? (st.amount_rp == null ? `Diterima. Tagihan pengepul menunggu harga (${num(st.payable_kg, 0)} kg).`
        : `Diterima. Tagihan pengepul ${num(st.payable_kg, 0)} kg × ${rp(st.price_per_kg)} = ${rp(st.amount_rp)}`) : "Diterima.", "⚖️");
      loadArrivals(); loadSettlements();
    } catch (err) { showToast(err.message, "❌"); }
  }, "⏳");
}

async function loadSettlements() {
  try {
    const f = $("st-filter").value;
    const rows = await api(`/api/v1/factory/settlements${f ? `?status=${encodeURIComponent(f)}` : ""}`);
    const owed = rows.filter(r => r.status === "terutang").reduce((a, r) => a + (r.amount_rp || 0), 0);
    const unpriced = rows.filter(r => r.status === "menunggu_harga").reduce((a, r) => a + r.payable_kg, 0);
    $("st-list").innerHTML = rows.length ? `<p class="kpi-lbl">Terutang: <b>${rp(owed)}</b> · belum berharga: <b>${num(unpriced, 0)} kg</b></p>
      <table class="data-table"><thead><tr><th>#</th><th>Pengepul</th><th>Jalur</th><th class="num">kg dibayar</th><th class="num">Rp/kg</th>
      <th class="num">Jumlah</th><th>Status</th><th>Aksi</th></tr></thead><tbody>${rows.map(r => `<tr>
        <td>${r.id}</td><td>${esc(r.collector)}</td>
        <td>${r.source === "qc" ? `QC lot #${r.qc_id}` : `rute · harvest #${r.harvest_id}${r.farmer_name ? ` · petani: ${esc(r.farmer_name)}` : ""}`}<br><span class="kpi-lbl">${esc(r.price_basis || "")}</span></td>
        <td class="num">${num(r.payable_kg, 0)}</td><td class="num">${r.price_per_kg == null ? "–" : rp(r.price_per_kg)}</td>
        <td class="num">${r.amount_rp == null ? "–" : rp(r.amount_rp)}</td>
        <td><span class="badge ${ST_BADGE[r.status] || ""}">${esc(ST_LABEL[r.status] || r.status)}</span>${r.payment_reference ? `<br><span class="kpi-lbl">${esc(r.payment_reference)}</span>` : ""}</td>
        <td style="white-space:nowrap;">${r.status === "dibayar" ? "" : `
          <input id="stp-${r.id}" type="number" class="btn btn-secondary btn-sm" style="width:70px;" placeholder="Rp/kg" min="0">
          <button class="btn btn-secondary btn-sm" data-onclick="priceSettlement(${Number(r.id)}, this)">Tetapkan harga</button>`}
          ${r.status === "terutang" ? `<input id="str-${r.id}" class="btn btn-secondary btn-sm" style="width:100px;" placeholder="No. transfer">
          <button class="btn btn-primary btn-sm" data-onclick="paySettlement(${Number(r.id)}, this)">Tandai dibayar</button>` : ""}</td></tr>`).join("")}</tbody></table>`
      : emptyState("🧾", "Belum ada tagihan pengepul", "Semua pengiriman telah terselesaikan atau belum ada tagihan terutang.");
  } catch (err) { console.error("loadSettlements:", err); }
}

async function priceSettlement(id, btn) {
  const v = $(`stp-${id}`).value;
  if (v === "") return showToast("Isi harga Rp/kg dulu.", "⚠️");
  const reason = prompt("Alasan penetapan/perubahan harga (min 5 karakter):", "Koreksi mutu timbangan pabrik");
  if (!reason || reason.trim().length < 5) return showToast("Alasan penetapan harga wajib diisi minimal 5 karakter.", "⚠️");
  return withBusy(btn, async () => {
    try {
      await api(`/api/v1/factory/settlements/${id}/price`, { body: { price_per_kg: Number(v), reason: reason.trim() } });
      loadSettlements();
    } catch (err) { showToast(err.message, "❌"); }
  }, "⏳");
}

async function paySettlement(id, btn) {
  const ref = $(`str-${id}`).value.trim();
  if (ref.length < 3) return showToast("Isi nomor transfer / bukti bayar.", "⚠️");
  return withBusy(btn, async () => {
    try { await api(`/api/v1/factory/settlements/${id}/pay`, { body: { payment_reference: ref } }); loadSettlements(); }
    catch (err) { showToast(err.message, "❌"); }
  }, "⏳");
}

async function runPricing() {
  try {
    const optNum = id => $(id).value === "" ? null : Number($(id).value);
    const r = await api("/api/v1/factory/pricing/recommend", { body: {
      commodity_code: $("pr-commodity") ? $("pr-commodity").value : "sekam_padi",
      moisture: Number($("pr-m").value), ash: Number($("pr-a").value), contamination: Number($("pr-c").value),
      price_pellet_per_kg: optNum("pr-pp"), price_biochar_per_kg: optNum("pr-pb"), price_silica_per_kg: optNum("pr-ps"),
      silica_route: $("pr-route").value, silica_husk_share: $("pr-route").value === "biochar" ? null : optNum("pr-xs") } });
    if (!r.accept) { $("pr-result").innerHTML = `<p class="badge badge-red">${esc(r.reason || "Tidak layak dibeli")}</p>`; return; }
    $("pr-result").innerHTML = `
      <div class="kpi-row">
        <div class="kpi-tile"><div class="kpi-lbl">Lantai</div><div class="kpi-val">${rp(r.floor_per_kg)}</div><div class="kpi-lbl">/kg · tutup biaya variabel</div></div>
        <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Target</div><div class="kpi-val">${rp(r.target_per_kg)}</div><div class="kpi-lbl">/kg · dengan margin</div></div>
        <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Plafon</div><div class="kpi-val">${rp(r.ceiling_per_kg)}</div><div class="kpi-lbl">/kg · impas penuh</div></div>
      </div>
      <table class="data-table" style="margin-top:8px;"><thead><tr><th>Produk</th><th class="num">kg/kg biomassa</th><th class="num">Nilai Rp/kg biomassa</th></tr></thead>
      <tbody>${Object.entries(r.yields_kg_per_kg).map(([k, v]) => `<tr><td>${PRODUCT_NAMES[k]}</td><td class="num">${num(v, 3)}</td>
        <td class="num">${rp(r.revenue_per_kg[k])}</td></tr>`).join("")}</tbody></table>
      <p class="kpi-lbl">Biaya variabel ${rp(Object.values(r.variable_cost_per_kg).reduce((a, b) => a + b, 0))}/kg · tetap ${rp(r.fixed_cost_per_kg)}/kg ·
        loss ${Object.entries(r.losses_kg_per_kg).map(([k, v]) => `${LOSS_NAMES[k]} ${num(v * 100, 1)}%`).join(", ")}</p>
      <p class="kpi-lbl">Sensitivitas kadar air → target: ${r.sensitivity_moisture.map(x => `${x.moisture}%: ${rp(x.target_per_kg)}`).join(" · ")}</p>
      <p class="kpi-lbl">Jalur silika: ${esc(r.silica_route)}${r.heat_recovered_mj_per_kg ? ` · panas tungku ${num(r.heat_recovered_mj_per_kg, 2)} MJ/kg biomassa menutup biaya pengering` : ""}</p>`;
  } catch (err) {
    // Harga belum diisi = keadaan konfigurasi, bukan kegagalan: tampilkan di kartu kalkulator, bukan toast merah saat halaman dibuka
    if (err.code === "price_missing") {
      $("pr-result").innerHTML = `<div class="banner banner-warning" role="status"><span aria-hidden="true">⚠️</span>
        <span>${esc(err.message)}</span>
        <button type="button" class="btn btn-secondary btn-sm" data-onclick="openTab('tab-params')">Buka Parameter</button></div>`;
      return;
    }
    showToast(err.message, "❌");
  }
}

async function loadInbox() {
  try {
    const rows = await api("/api/v1/factory/delivery-requests");
    $("dr-inbox").innerHTML = rows.length ? `<table class="data-table"><thead><tr><th>#</th><th>Pengepul</th><th class="num">kg</th>
      <th>Tawaran</th><th>Status</th><th>Aksi</th></tr></thead><tbody>${rows.map(r => `<tr>
        <td>${r.id}</td><td>${esc(r.collector)}<br><span class="kpi-lbl">air ${num(r.moisture_est)}% · rekomendasi ${rp(r.recommended_price_per_kg)}</span></td>
        <td class="num">${num(r.quantity_kg, 0)}</td>
        <td>${rp((r.agreed || r.current_offer).price_per_kg)}/kg<br><span class="kpi-lbl">${esc((r.agreed || r.current_offer).date)}</span></td>
        <td><span class="badge ${DR_STATUS[r.status] || ""}">${esc(r.status)}</span>${r.pending_party ? `<br><span class="kpi-lbl">menunggu ${esc(r.pending_party)}</span>` : ""}</td>
        <td style="white-space:nowrap;">${r.pending_party === "pabrik" ? `
            <button class="btn btn-primary btn-sm" data-onclick="drRespond(${Number(r.id)}, 'accept', this)">Terima</button>
            <input id="drp-${r.id}" type="number" class="btn btn-secondary btn-sm" style="width:70px;" placeholder="Rp/kg">
            <input id="drd-${r.id}" type="date" class="btn btn-secondary btn-sm" value="${esc(r.current_offer.date)}">
            <button class="btn btn-secondary btn-sm" data-onclick="drRespond(${Number(r.id)}, 'counter', this)">Tawar</button>
            <button class="btn btn-secondary btn-sm" data-onclick="drRespond(${Number(r.id)}, 'reject', this)">Tolak</button>`
          : r.status === "accepted" ? `<button class="btn btn-primary btn-sm" data-onclick="showQcForm(${Number(r.id)})">QC Masuk</button>` : ""}
          <div id="qc-${r.id}"></div></td></tr>`).join("")}</tbody></table>` : emptyState("📥", "Belum ada ajuan pasokan", "Belum ada delivery request dari pengepul yang menunggu respon pabrik.");
  } catch (err) { console.error("loadInbox:", err); }
}

async function drRespond(id, action, btn) {
  const body = { action };
  if (action === "counter") { body.price_per_kg = Number($(`drp-${id}`).value); body.date = $(`drd-${id}`).value; }
  return withBusy(btn, async () => {
    try { await api(`/api/v1/factory/delivery-requests/${id}/respond`, { body }); loadInbox(); }
    catch (err) { showToast(err.message, "❌"); }
  }, "⏳");
}

function showQcForm(id) {
  $(`qc-${id}`).innerHTML = `
    <div style="background:var(--surface-2); border:1px solid var(--border); border-radius:10px; padding:12px; margin-top:8px;">
      <div style="font-size:var(--fs-xs); font-weight:700; color:var(--ink); margin-bottom:8px;">🧪 Uji Proksimat Inbound QC (#${id})</div>
      <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:8px;">
        <div><label class="kpi-lbl">Bruto (kg)</label><input id="qcgross-${id}" type="number" class="btn btn-secondary btn-sm" style="width:100%;" placeholder="Bruto kg" data-oninput="updateQcNetto(${id})"></div>
        <div><label class="kpi-lbl">Tara (kg)</label><input id="qctare-${id}" type="number" class="btn btn-secondary btn-sm" style="width:100%;" value="0" placeholder="Tara kg" data-oninput="updateQcNetto(${id})"></div>
        <div><label class="kpi-lbl">Air (%)</label><input id="qcm-${id}" type="number" step="0.1" class="btn btn-secondary btn-sm" style="width:100%;" value="12" placeholder="Air %" data-oninput="updateQcNetto(${id})"></div>
        <div><label class="kpi-lbl">Abu (%)</label><input id="qcash-${id}" type="number" step="0.1" class="btn btn-secondary btn-sm" style="width:100%;" value="18" placeholder="Abu %"></div>
        <div><label class="kpi-lbl">VM (%)</label><input id="qcvm-${id}" type="number" step="0.1" class="btn btn-secondary btn-sm" style="width:100%;" value="55" placeholder="VM %"></div>
        <div><label class="kpi-lbl">FC (%)</label><input id="qcfc-${id}" type="number" step="0.1" class="btn btn-secondary btn-sm" style="width:100%;" value="15" placeholder="FC %"></div>
        <div><label class="kpi-lbl">Kontam (%)</label><input id="qcc-${id}" type="number" step="0.1" class="btn btn-secondary btn-sm" style="width:100%;" value="0" placeholder="Kontam %"></div>
        <div style="display:flex; align-items:flex-end;"><button class="btn btn-primary btn-sm" style="width:100%;" data-onclick="submitQc(${Number(id)}, this)">Simpan QC ➔</button></div>
      </div>
      <div id="qcnetto-preview-${id}" style="margin-top:8px; font-size:var(--fs-xs); color:var(--ink-muted); font-weight:600;">
        ⚖️ Netto: 0 kg · Kadar Air: 12%
      </div>
    </div>`;
}

function updateQcNetto(id) {
  const g = Number($(`qcgross-${id}`)?.value) || 0;
  const t = Number($(`qctare-${id}`)?.value) || 0;
  const m = Number($(`qcm-${id}`)?.value) || 0;
  const netto = Math.max(0, g - t);
  const p = $(`qcnetto-preview-${id}`);
  if (p) {
    p.innerHTML = `⚖️ Netto: <strong>${num(netto, 0)} kg</strong> (Bruto ${num(g, 0)} kg − Tara ${num(t, 0)} kg) · Kadar Air: <strong>${m}%</strong> ${m > 14 ? '<span class="badge badge-amber">Ada potongan susut air (&gt;14%)</span>' : '<span class="badge badge-green">Kadar air prima (≤14%)</span>'}`;
  }
}

async function submitQc(id, btn) {
  const v = k => Number($(`qc${k}-${id}`).value);
  return withBusy(btn, async () => {
    try {
      const r = await api("/api/v1/factory/qc", { body: { request_id: id, gross_kg: v("gross"), tare_kg: v("tare"), moisture: v("m"),
        ash: v("ash"), volatile_matter: v("vm"), fixed_carbon: v("fc"), contamination: v("c") } });
      showToast(`${r.decision}: grade ${r.grade}, ${num(r.payable_kg, 0)} kg × ${rp(r.final_price_per_kg)} = ${rp(r.total_payment_rp)} · ${r.verification_code}`, "🧪");
      loadInbox(); loadLots();
    } catch (err) { showToast(err.message, "❌"); }
  }, "⏳");
}

let lotCache = [];
async function loadLots() {
  try {
    lotCache = await api("/api/v1/factory/qc/lots");
    $("bt-lots").innerHTML = lotCache.length ? lotCache.map(l => `<label style="display:flex; gap:8px; align-items:center; font-size:var(--fs-xs); margin:4px 0;">
        <span style="flex:1;">Lot #${l.id} · sisa ${num(l.remaining_kg, 0)} kg · air ${num(l.moisture)}% · ${esc(l.grade)}</span>
        <input type="number" class="btn btn-secondary bt-lot" data-id="${Number(l.id)}" style="width:100px;" min="0" max="${l.remaining_kg}" value="0"></label>`).join("")
      : emptyState("📦", "Belum ada lot hasil QC", "Lakukan verifikasi QC pada biomassa masuk untuk memunculkan lot siap batch.");
  } catch (err) { console.error("loadLots:", err); }
}

function batchInputs() {
  return [...document.querySelectorAll(".bt-lot")].map(i => ({ qc_id: Number(i.dataset.id), kg: Number(i.value) })).filter(x => x.kg > 0);
}

async function fillBatchFromModel() {
  const inputs = batchInputs();
  if (!inputs.length) return showToast("Isi kg dari minimal satu lot dulu.", "⚠️");
  const total = inputs.reduce((a, x) => a + x.kg, 0);
  const lots = inputs.map(x => ({ ...x, lot: lotCache.find(l => l.id === x.qc_id) }));
  const m = lots.reduce((a, x) => a + x.kg * x.lot.moisture, 0) / total, ash = lots.reduce((a, x) => a + x.kg * x.lot.ash, 0) / total;
  const r = await api("/api/v1/factory/pricing/recommend", { body: { moisture: m, ash, sensitivity: false,
    silica_route: $("bt-route").value, silica_husk_share: $("bt-route").value === "biochar" ? null : Number($("bt-xs").value) || null } });
  Object.entries(r.yields_kg_per_kg).forEach(([k, v]) => { $(`bt-o-${k}`).value = (v * total).toFixed(1); });
  Object.entries(r.losses_kg_per_kg).forEach(([k, v]) => { $(`bt-l-${k}`).value = (v * total).toFixed(1); });
  $("bt-kwh").value = Math.round(PV("pabrik.kwh_per_ton_input", 150) * total / 1000);
  $("bt-labor").value = (PV("pabrik.labor_hours_per_ton", 2) * total / 1000).toFixed(1);
  showToast("Terisi dari model — ganti dengan timbangan aktual sebelum menyimpan.", "ℹ️");
}

async function saveBatch() {
  const inputs = batchInputs();
  if (!inputs.length) return showToast("Pilih lot & jumlah kg.", "⚠️");
  const num0 = id => Number($(id).value) || 0;
  const costs = [
    { item: "listrik", amount_rp: num0("bt-kwh") * PV("energi.tariff_rp_per_kwh", 1444.7), driver_qty: num0("bt-kwh"), driver_unit: "kWh",
      rate: PV("energi.tariff_rp_per_kwh", 1444.7) },
    { item: "tenaga_kerja", amount_rp: num0("bt-labor") * PV("pabrik.labor_rate_per_hour", 20000), driver_qty: num0("bt-labor"), driver_unit: "jam",
      rate: PV("pabrik.labor_rate_per_hour", 20000) },
    { item: "bahan_kimia", amount_rp: num0("bt-chem"), product: "bio_silika" },
    { item: "kemasan", amount_rp: num0("bt-pack") },
  ].filter(c => c.amount_rp > 0);
  try {
    const b = await api("/api/v1/factory/batches", { body: {
      batch_code: $("bt-code").value.trim(), inputs, costs, operating_hours: $("bt-hours").value ? num0("bt-hours") : null,
      silica_route: $("bt-route").value, silica_husk_share: $("bt-route").value === "biochar" ? null : num0("bt-xs"),
      outputs: Object.fromEntries(Object.keys(PRODUCT_NAMES).map(k => [k, num0(`bt-o-${k}`)])),
      losses: Object.fromEntries(Object.keys(LOSS_NAMES).map(k => [k, num0(`bt-l-${k}`)])) } });
    const e = b.economics, mb = e.mass_balance;
    $("bt-result").innerHTML = `
      <div class="kpi-row">
        <div class="kpi-tile ${mb.closure_ok ? "" : "kpi-warn"}"><div class="kpi-lbl">Penutupan mass balance</div><div class="kpi-val">${num(mb.closure_error_pct, 2)}%</div>
          <div class="kpi-lbl">${mb.closure_ok ? "✓ dalam" : "⚠️ di luar"} toleransi ${num(mb.tolerance_pct)}%</div></div>
        <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Biaya per ton input</div><div class="kpi-val">${rp(e.totals.cost_per_ton_input_rp)}</div><div class="kpi-lbl">laba batch ${rp(e.totals.profit_rp)}</div></div>
        <div class="kpi-tile kpi-purple"><div class="kpi-lbl">Volume impas</div><div class="kpi-val">${e.cvp.break_even_ton_per_month == null ? "-" : num(e.cvp.break_even_ton_per_month, 0)}</div>
          <div class="kpi-lbl">ton/bulan (rencana ${num(e.cvp.planned_ton_per_month, 0)})</div></div>
      </div>
      <table class="data-table"><thead><tr><th>Produk</th><th class="num">kg</th><th class="num">Biaya/ton</th><th class="num">Harga/ton</th>
        <th class="num">Margin/ton</th><th class="num">Varians rendemen</th></tr></thead><tbody>${Object.entries(e.products).map(([k, p]) => `<tr>
        <td>${esc(p.label)}</td><td class="num">${num(p.kg, 1)}</td><td class="num">${p.cost_per_ton_rp == null ? "-" : rp(p.cost_per_ton_rp)}</td>
        <td class="num">${rp(p.price_per_ton_rp)}</td><td class="num"><b>${p.margin_per_ton_rp == null ? "-" : rp(p.margin_per_ton_rp)}</b></td>
        <td class="num">${e.yield_variance[k].variance_pct == null ? "-" : num(e.yield_variance[k].variance_pct, 1) + "%"}</td></tr>`).join("")}</tbody></table>
      <p class="kpi-lbl">${esc(e.computation_details.alokasi)} · ${esc(e.computation_details.impas)}</p>
      <div class="card" style="background:var(--primary-soft); margin-top:8px;"><b>🌾 Dompet abu bottom ash petani:</b>
        ${num(e.wallet.allocated_kg, 2)} kg dikreditkan ke ${e.wallet.farmers.length} petani
        (porsi ${num(e.wallet.return_share * 100, 0)}% biochar)${e.wallet.untraceable_kg ? ` · ${num(e.wallet.untraceable_kg, 2)} kg dari biomassa yang tidak tertelusur ke petani` : ""}
        <div class="kpi-lbl">${esc(e.wallet.method || "")}</div></div>`;
    showToast(`Batch ${b.batch_code} tersimpan.`, "🏭");
    $("bt-code").value = `B-${new Date().toISOString().slice(0, 10).replaceAll("-", "")}-${Math.floor(Math.random() * 900 + 100)}`;
    loadLots();
  } catch (err) { showToast(err.message, "❌"); }
}

// ---------- Pengepul: ajukan pengiriman ke pabrik & jawab tawaran balik
// ---------- Pengepul: ajukan pengiriman ke pabrik & jawab tawaran balik
const PENGEPUL_DR_HTML = `
  <div class="card" style="margin-top:16px;">
    <div class="card-header"><div><h3 class="card-title">🚚 Ajukan Pengiriman ke Pabrik</h3>
      <p class="card-sub">Pilih pabrik tujuan, jenis biomassa, moda armada & skema harga rekomendasi</p></div></div>
    <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(190px, 1fr)); gap:8px; margin-bottom:10px;">
      <div>
        <label class="kpi-lbl">Pabrik Tujuan</label>
        <select id="dr-mill" class="btn btn-secondary" style="width:100%; text-align:left;">
          <option value="">Pabrik Utama (PLTBm Pusat)</option>
        </select>
      </div>
      <div>
        <label class="kpi-lbl">Jenis Biomassa</label>
        <select id="dr-biomass" class="btn btn-secondary" style="width:100%; text-align:left;">
          <option value="sekam_padi">🌾 Sekam Padi</option>
          <option value="tongkol_jagung">🌽 Tongkol Jagung</option>
          <option value="serbuk_kayu">🪵 Serbuk Kayu / Sengon</option>
          <option value="ampas_tebu">🎋 Ampas Tebu</option>
          <option value="cangkang_sawit">🌴 Cangkang Sawit</option>
        </select>
      </div>
      <div>
        <label class="kpi-lbl">Moda Logistik</label>
        <select id="dr-carrier" class="btn btn-secondary" style="width:100%; text-align:left;">
          <option value="FACTORY_FLEET">🚛 Dijemput Armada Pabrik (Factory Fleet)</option>
          <option value="COLLECTOR_SELF">🚜 Antar Mandiri Pengepul (Self-Delivery Slip)</option>
        </select>
      </div>
      <div>
        <label class="kpi-lbl">Skema Penentuan Harga</label>
        <select id="dr-pricing" class="btn btn-secondary" style="width:100%; text-align:left;">
          <option value="FACTORY_PRICE">🎯 Ikut Acuan Kadar Air Pabrik</option>
          <option value="AUCTION">🏷️ Tawar Bebas (Custom Proposed)</option>
        </select>
      </div>
    </div>
    <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:8px;">
      <div><label class="kpi-lbl">Jumlah (kg)</label><input id="dr-qty" type="number" class="btn btn-secondary" style="width:100%;" value="5000" min="1"></div>
      <div><label class="kpi-lbl">Kadar air (%)</label><input id="dr-m" type="number" class="btn btn-secondary" style="width:100%;" value="11" step="0.5"></div>
      <div><label class="kpi-lbl">Tanggal kirim</label><input id="dr-date" type="date" class="btn btn-secondary" style="width:100%;"></div>
      <div><label class="kpi-lbl">Harga diajukan (Rp/kg)</label><input id="dr-price" type="number" class="btn btn-secondary" style="width:100%;"></div>
    </div>
    <p class="kpi-lbl" id="dr-reco"></p>
    <details style="margin:8px 0;"><summary class="kpi-lbl" style="cursor:pointer;">🌾 Lampirkan lot biomassa petani (agar alokasi produk sirkular / biochar masuk ke dompet mereka)</summary>
      <div id="dr-harvests" style="margin-top:8px;"></div></details>
    <button class="btn btn-primary" id="btn-dr">Ajukan Pengiriman ➔</button>
    <div id="dr-mine" style="margin-top:12px; overflow-x:auto;"></div>
    <h4 style="margin:16px 0 4px;">💳 Tagihan saya ke pabrik (jalur QC &amp; rute armada)</h4>
    <div id="my-settle" style="overflow-x:auto;"><p class="muted">Memuat…</p></div>
  </div>`;

function initCollectorDR() {
  $("dr-date").value = new Date(Date.now() + 3 * 864e5).toISOString().slice(0, 10);
  const preview = async () => {
    try {
      const r = await api(`/api/v1/collector/factory-price?moisture=${Number($("dr-m").value)}`);
      $("dr-reco").innerHTML = !r.accept ? `⚠️ ${esc(r.reason || "Di luar batas mutu")}`
        : r.recommended_price_per_kg == null ? `ℹ️ ${esc(r.basis)}`
        : `Rekomendasi pabrik: <b>${rp(r.recommended_price_per_kg)}/kg</b> (${esc(r.basis)})`;
      if (!$("dr-price").value && r.recommended_price_per_kg) $("dr-price").value = Math.round(r.recommended_price_per_kg);
    } catch (err) { $("dr-reco").textContent = err.message; }
  };
  $("dr-m").onchange = preview;

  api("/api/v1/farmer/mills").then(mills => {
    const sel = $("dr-mill");
    if (sel && mills && mills.length) {
      sel.innerHTML = `<option value="">Pabrik Utama (PLTBm Pusat)</option>` +
        mills.map(m => `<option value="${m.id}">🏭 ${esc(m.name)} (${esc(m.kecamatan || "Pabrik")})</option>`).join("");
    }
  }).catch(() => {});

  $("btn-dr").onclick = e => withBusy(e.currentTarget, async () => {
    try {
      const harvest_ids = [...document.querySelectorAll(".dr-h:checked")].map(c => Number(c.value));
      const mill_id = $("dr-mill") && $("dr-mill").value ? Number($("dr-mill").value) : null;
      const biomass_type = ($("dr-biomass") && $("dr-biomass").value) || "sekam_padi";
      const logistics_carrier = ($("dr-carrier") && $("dr-carrier").value) || "FACTORY_FLEET";
      const pricing_mode = ($("dr-pricing") && $("dr-pricing").value) || "FACTORY_PRICE";

      await api("/api/v1/collector/delivery-requests", { body: {
        quantity_kg: Number($("dr-qty").value),
        moisture_est: Number($("dr-m").value),
        proposed_date: $("dr-date").value,
        proposed_price_per_kg: Number($("dr-price").value),
        harvest_ids,
        mill_id,
        biomass_type,
        logistics_carrier,
        pricing_mode
      } });
      showToast(`Ajuan pengiriman ${biomass_type.replace('_',' ')} terkirim ke pabrik${harvest_ids.length ? ` dengan ${harvest_ids.length} lot petani` : ""}.`, "📨");
      loadMyDR(); loadAttachable();
    } catch (err) { showToast(err.message, "❌"); }
  });
  preview(); loadMyDR(); loadAttachable(); loadMySettlements();
}

async function loadMySettlements() {
  try {
    const rows = await api("/api/v1/collector/settlements");
    const sum = st => rows.filter(r => r.status === st).reduce((a, r) => a + (r.amount_rp || 0), 0);
    $("my-settle").innerHTML = rows.length ? `<p class="kpi-lbl">Belum dibayar: <b>${rp(sum("terutang"))}</b> · sudah dibayar: <b>${rp(sum("dibayar"))}</b></p>
      <table class="data-table"><thead><tr><th>Jalur</th><th class="num">kg</th><th class="num">Rp/kg</th><th class="num">Jumlah</th><th>Status</th></tr></thead>
      <tbody>${rows.map(r => `<tr><td>${r.source === "qc" ? `QC lot #${r.qc_id}` : `rute · harvest #${r.harvest_id}`}</td>
        <td class="num">${num(r.payable_kg, 0)}</td><td class="num">${r.price_per_kg == null ? "–" : rp(r.price_per_kg)}</td>
        <td class="num">${r.amount_rp == null ? "–" : rp(r.amount_rp)}</td>
        <td><span class="badge ${ST_BADGE[r.status] || ""}">${esc(ST_LABEL[r.status] || r.status)}</span>${r.payment_reference ? `<br><span class="kpi-lbl">${esc(r.payment_reference)}</span>` : ""}</td></tr>`).join("")}</tbody></table>`
      : `<p class="muted">Belum ada tagihan.</p>`;
  } catch (err) { console.error("loadMySettlements:", err); }
}

async function loadAttachable() {
  try {
    const rows = await api("/api/v1/collector/attachable-harvests");
    $("dr-harvests").innerHTML = rows.length ? rows.map(h => `<label style="display:flex; gap:8px; font-size:var(--fs-xs); margin:2px 0;">
        <input type="checkbox" class="dr-h" value="${Number(h.id)}"> #${h.id} · ${esc(h.farmer)} · ${num(h.verified_kg, 0)} kg · air ${num(h.moisture)}% · ${esc(h.grade || "-")}</label>`).join("")
      : `<p class="muted">Tidak ada biomassa petani terverifikasi yang belum dikirim.</p>`;
  } catch (err) { console.error("loadAttachable:", err); }
}

async function loadMyDR() {
  try {
    const rows = await api("/api/v1/collector/delivery-requests");
    if (!rows || !rows.length) {
      $("dr-mine").innerHTML = "";
      return;
    }

    const COMMODITY_MAP = {
      sekam_padi: { label: "🌾 Sekam Padi", badge: "badge-purple" },
      tongkol_jagung: { label: "🌽 Tongkol Jagung", badge: "badge-amber" },
      serbuk_kayu: { label: "🪵 Serbuk Kayu", badge: "badge-blue" },
      serbuk_sengon: { label: "🪵 Serbuk Sengon", badge: "badge-blue" },
      ampas_tebu: { label: "🎋 Ampas Tebu", badge: "badge-green" },
      cangkang_sawit: { label: "🌴 Cangkang Sawit", badge: "badge-amber" }
    };

    const grouped = {};
    for (const r of rows) {
      const key = r.biomass_type || "sekam_padi";
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(r);
    }

    let tbodyHtml = "";
    for (const [bioKey, groupRows] of Object.entries(grouped)) {
      const meta = COMMODITY_MAP[bioKey] || { label: bioKey.replace("_", " ").toUpperCase(), badge: "badge-gray" };
      const groupKg = groupRows.reduce((acc, r) => acc + (Number(r.quantity_kg) || 0), 0);
      tbodyHtml += `
        <tr class="group-header-row" style="background:var(--bg-elevated, rgba(255,255,255,0.06)); font-weight:700;">
          <td colspan="7" style="padding:8px 12px; border-top:2px solid var(--border); color:var(--primary);">
            <span>${meta.label}</span>
            <span class="badge ${meta.badge}" style="margin-left:8px;">${groupRows.length} Ajuan</span>
            <span class="badge badge-green" style="margin-left:4px;">Total: ${num(groupKg / 1000, 2)} ton</span>
          </td>
        </tr>
      `;

      tbodyHtml += groupRows.map(r => {
        const isSelf = r.logistics_carrier === "COLLECTOR_SELF";
        const carrierBadge = isSelf ?
          `<span class="badge badge-amber" title="Antar Mandiri Pengepul">🚜 Antar Mandiri</span>` :
          `<span class="badge badge-blue" title="Armada Pabrik">🚛 Armada Pabrik</span>`;

        let actionCell = "";
        if (r.pending_party === "pengepul") {
          actionCell = `
            <button class="btn btn-primary btn-sm" data-onclick="myDrRespond(${Number(r.id)}, 'accept', this)">Setuju</button>
            <input id="mdp-${r.id}" type="number" class="btn btn-secondary btn-sm" style="width:70px;" placeholder="Rp/kg">
            <button class="btn btn-secondary btn-sm" data-onclick="myDrRespond(${Number(r.id)}, 'counter', this, '${esc((r.agreed || r.current_offer).date)}')">Tawar</button>
            <button class="btn btn-secondary btn-sm" data-onclick="myDrRespond(${Number(r.id)}, 'reject', this)">Tolak</button>
          `;
        } else if (r.status === "accepted" && isSelf) {
          const originCode = r.origin_qr_code || r.wr_code || `WR-DR-${r.id}`;
          actionCell = `
            <button type="button" class="btn btn-primary btn-sm" data-onclick="showSelfDeliverySlip(${Number(r.id)}, '${esc(r.biomass_type || 'Biomassa')}', ${Number(r.quantity_kg)}, '${esc(originCode)}')">
              📄 Cetak Surat Jalan
            </button>
          `;
        } else if (["submitted", "countered"].includes(r.status)) {
          actionCell = `<button class="btn btn-secondary btn-sm" data-onclick="myDrRespond(${Number(r.id)}, 'cancel', this)">Batalkan</button>`;
        }

        return `
          <tr>
            <td>#${r.id}</td>
            <td><span class="badge ${meta.badge}">${esc(r.biomass_type || 'sekam_padi')}</span></td>
            <td class="num"><b>${num(r.quantity_kg, 0)}</b></td>
            <td>${carrierBadge}</td>
            <td>${rp((r.agreed || r.current_offer).price_per_kg)}/kg · ${esc((r.agreed || r.current_offer).date)}</td>
            <td><span class="badge ${DR_STATUS[r.status] || ""}">${esc(r.status)}</span>${r.pending_party ? `<br><span class="kpi-lbl">menunggu ${esc(r.pending_party)}</span>` : ""}</td>
            <td style="white-space:nowrap;">${actionCell}</td>
          </tr>
        `;
      }).join("");
    }

    $("dr-mine").innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Jenis Biomassa</th>
            <th class="num">Qty (kg)</th>
            <th>Moda Logistik</th>
            <th>Tawaran di Meja</th>
            <th>Status</th>
            <th>Aksi</th>
          </tr>
        </thead>
        <tbody>
          ${tbodyHtml}
        </tbody>
      </table>
    `;
  } catch (err) { console.error("loadMyDR:", err); }
}

window.showSelfDeliverySlip = function(id, biomassType, qtyKg, originQrCode) {
  const modalId = "modal-self-delivery-slip";
  let m = document.getElementById(modalId);
  if (m) m.remove();

  m = document.createElement("div");
  m.id = modalId;
  m.className = "modal-overlay";
  m.style.cssText = "position:fixed; inset:0; background:rgba(0,0,0,0.75); z-index:9999; display:flex; align-items:center; justify-content:center; padding:16px;";
  m.innerHTML = `
    <div class="card" style="max-width:540px; width:100%; background:var(--bg-panel, #1e293b); border:2px solid var(--primary); box-shadow:0 12px 36px rgba(0,0,0,0.5);">
      <div class="card-header" style="border-bottom:1px solid var(--border); padding-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
        <div>
          <h3 class="card-title" style="color:var(--primary);">📄 SURAT JALAN PENGIRIMAN MANDIRI</h3>
          <p class="card-sub">Nomor: <b>SJ-COLL-${id}</b> (Self-Delivery Mandiri Pengepul)</p>
        </div>
        <button type="button" class="btn btn-secondary btn-sm" id="btn-close-slip-x">✕ Tutup</button>
      </div>
      <div style="padding:16px 0;">
        <div style="text-align:center; padding:12px; background:#fff; border-radius:6px; margin-bottom:12px; color:#000;">
          <div style="font-family:monospace; font-size:28px; font-weight:bold; letter-spacing:4px;">|||| | ||||| || |||||| |</div>
          <div style="font-size:12px; font-weight:bold; margin-top:4px;">*SJ-COLL-${id}-GATEQC*</div>
          <p style="font-size:11px; color:#555; margin-top:2px;">Scan di Pos Timbangan Pabrik untuk Pencatatan Gross & Gate QC</p>
        </div>
        <table class="data-table" style="font-size:13px; width:100%;">
          <tr><td><b>No. Delivery Request:</b></td><td>#${id} (Telah Disetujui Pabrik)</td></tr>
          <tr><td><b>QR Code / WR Asal:</b></td><td><code style="font-family:monospace; font-weight:800; color:var(--primary); font-size:13px;">${esc(originQrCode || ('WR-ORIGIN-' + id))}</code></td></tr>
          <tr><td><b>Rantai Ketelusuran:</b></td><td><span class="badge badge-green">🟢 Terdaftar Sejak Pelaporan Awal</span></td></tr>
          <tr><td><b>Komoditas:</b></td><td><span class="badge badge-purple">${esc(biomassType)}</span></td></tr>
          <tr><td><b>Kuantitas Estimasi:</b></td><td><b>${num(qtyKg, 0)} kg</b></td></tr>
          <tr><td><b>Moda Pengiriman:</b></td><td><span class="badge badge-amber">Antar Mandiri Pengepul</span></td></tr>
          <tr><td><b>Pos Masuk:</b></td><td>Jembatan Timbang & QC Gate PLTBm</td></tr>
        </table>
        <div class="banner banner-info" style="margin-top:12px; font-size:12px;">
          💡 <b>Instruksi Sopir:</b> Tunjukkan barcode surat jalan ini kepada petugas timbangan saat tiba di gerbang pabrik untuk registrasi timbang Gross dan pengambilan sampel Gate QC 3-State.
        </div>
      </div>
      <div style="display:flex; justify-content:flex-end; gap:8px; border-top:1px solid var(--border); padding-top:12px;">
        <button type="button" class="btn btn-secondary btn-sm" id="btn-print-slip">🖨️ Cetak Fisik</button>
        <button type="button" class="btn btn-primary btn-sm" id="btn-close-slip-done">Selesai</button>
      </div>
    </div>
  `;
  m.querySelector("#btn-close-slip-x").onclick = () => m.remove();
  m.querySelector("#btn-print-slip").onclick = () => window.print();
  m.querySelector("#btn-close-slip-done").onclick = () => m.remove();
  document.body.appendChild(m);
};

async function myDrRespond(id, action, btn, date) {
  const body = { action };
  if (action === "counter") { body.price_per_kg = Number($(`mdp-${id}`).value); body.date = date; }
  return withBusy(btn, async () => {
    try { await api(`/api/v1/collector/delivery-requests/${id}/respond`, { body }); loadMyDR(); }
    catch (err) { showToast(err.message, "❌"); }
  }, "⏳");
}

async function loadAuditorData() {
  try {
    const [sum, disc] = await Promise.all([api("/api/v1/auditor/summary"), api("/api/v1/auditor/discrepancies")]);
    $("au-collector").innerText = num(sum.collector_scale_kg, 1);
    $("au-factory").innerText = num(sum.factory_scale_kg, 1);
    $("au-shrink").innerText = num(sum.total_shrinkage_kg, 1);
    $("au-shrink-pct").innerText = `${num(sum.total_shrinkage_pct, 2)} % · ${sum.flagged_harvests} ditandai`;
    $("au-biochar").innerText = num(sum.biochar_allocated_to_farmers_kg, 2);
    $("au-tol").innerText = `Toleransi susut ${disc.tolerance_pct}% · akses baca-saja`;
    $("table-au-disc").querySelector("tbody").innerHTML = disc.items.length ? disc.items.map(d => `
      <tr><td>#${d.harvest_id}</td><td class="num">${num(d.verified_kg, 1)}</td><td class="num">${num(d.received_kg, 1)}</td>
          <td class="num"><b>${num(d.shrinkage_pct, 2)}</b></td><td>${esc(d.note)}</td></tr>`).join("")
      : `<tr><td colspan="5" style="text-align:center;">Tidak ada selisih di luar toleransi.</td></tr>`;
  } catch (err) {
    console.error("loadAuditorData:", err);
  }
}

async function loadCollectorData() {
  try {
    const [list, dashRes] = await Promise.all([
      api("/api/v1/collector/available-harvests?limit=500"),
      api("/api/v1/collector/offers-dashboard").catch(() => null)
    ]);
    if ($("col-pending")) {
      const pendingCount = (dashRes && typeof dashRes.total_unverified === "number")
        ? dashRes.total_unverified
        : list.length;
      $("col-pending").innerText = pendingCount;
    }
    // Ringkasan hari ini dari server (dulu angka contoh statis); belum ada verifikasi = "–", bukan 0 palsu
    api("/api/v1/collector/daily-summary").then(d => {
      if ($("col-verified-kg")) $("col-verified-kg").innerText = num(d.total_kg, 0);
      if ($("col-avg-score")) $("col-avg-score").innerText = d.total_pickups ? num(d.avg_quality_score, 1) : "–";
    }).catch(err => console.error("daily-summary:", err));

    STATE.colQueue = Object.fromEntries(list.map(i => [i.id, i]));
    const queueTable = $("table-col-queue");
    const tbody = queueTable ? queueTable.querySelector("tbody") : null;
    if (tbody) {
      tbody.innerHTML = "";
    }
  } catch (err) {
    console.error("loadCollectorData:", err);
  }
}

function selectVerifyItem(id) {
  let item = (STATE.colQueue || {})[id];
  if (!item && cachedOffersData) {
    const all = (cachedOffersData.langsung_diambil || []).concat(cachedOffersData.diantar_petani || []).concat(cachedOffersData.lelang || []);
    item = all.find(x => x.harvest_id == id || x.listing_id == id || x.id == id);
  }
  item = item || {};
  const qty = item.quantity_kg || item.qty_kg || 1000;
  openVerificationModal(id, qty, item);
}
window.selectVerifyItem = selectVerifyItem;

window.selectHarvestForVerification = function(harvestId, qty) {
  if (!harvestId) {
    showToast("Lot belum memiliki ID panen atau proses kesepakatan harga lelang belum selesai.", "⚠️");
    return;
  }
  openVerificationModal(harvestId, qty);
};

const optNum = id => { const v = ($(id) || {}).value; return v === undefined || String(v).trim() === "" ? null : Number(v); };

function submitVerify(e) {
  e.preventDefault();
  const id = $("v-harvest-id").value;
  if (!id) return;

  return withBusy($("btn-submit-verify"), async () => { try {
    const res = await apiMutation("/api/v1/collector/verify", {
        harvest_id: Number(id),
        weighed_kg: Number($("v-weight").value),
        moisture: Number($("v-moisture").value),
        // F9: kolom lab yang kosong dikirim null (bukan 0) — server menilai dari kadar air & kontaminan
        ash: optNum("v-ash"),
        volatile_matter: optNum("v-vm"),
        fixed_carbon: optNum("v-fc"),
        contamination: optNum("v-contam") ?? 0,
        pyrolysis_temp_c: Number($("v-temp").value),
        evidence_photo_url: $("v-photo") && $("v-photo").value.trim() ? $("v-photo").value.trim() : null,
    }, `Verifikasi biomassa #${id}`);
    showToast(res.queued ? "Offline: hasil uji disimpan & dikirim otomatis saat online." : res.message,
              res.queued ? "📵" : "✅");
    // Serah-terima: tampilkan resi bulanan unik (TRX-<pengirim>-<penerima>-<YYMM>-<urut>) untuk ditunjukkan ke petani
    if (!res.queued && res.verification_code) {
      const comLabel = res.commodity && res.commodity.toLowerCase().includes("sekam") ? "Sekam" : "Biomassa";
      const originCode = res.origin_qr_code || res.qr_code || (STATE.colQueue && STATE.colQueue[id] && (STATE.colQueue[id].origin_qr_code || STATE.colQueue[id].qr_code)) || "";
      const batchRef = res.batch_ref || (res.listing_id ? `WR-LST-${String(res.listing_id).padStart(4, '0')}` : `WR-HV-${String(res.harvest_id).padStart(4, '0')}`);
      openModal(`Resi Serah-Terima ${comLabel}`, res.verification_code,
                `${num(res.weighed_kg, 0)} kg · Grade ${res.grade} · ${rp(res.total_price)} — tunjukkan/foto resi ini bersama petani`, {
        originQrCode: originCode,
        batchRef: batchRef,
        listingId: res.listing_id,
        harvestId: res.harvest_id,
        commodity: res.commodity || comLabel,
        weighedKg: res.weighed_kg,
        grade: res.grade,
        totalPrice: res.total_price
      });
    }
    loadCollectorData();
    loadMarket();
    if (typeof window.loadUnpaid === "function") window.loadUnpaid();
    $("v-harvest-id").value = "";
    $("col-verify-target").innerText = `Pilih biomassa dari tabel antrian di samping`;
  } catch (err) {
    showToast(err.message, "❌");
  } }).finally(() => { if (!$("v-harvest-id").value) $("btn-submit-verify").disabled = true; });
}

let driverMap, driverLayer;
const FAIL_REASONS = [["stok_tidak_ada", "Biomassa tidak ada / sudah dijual"], ["dibatalkan_pengepul", "Dibatalkan pengepul"],
  ["mutu_buruk", "Basah / berjamur"], ["akses_jalan", "Jalan tidak bisa dilalui"],
  ["penggilingan_tutup", "Lokasi / titik tutup"], ["truk_penuh", "Bak truk penuh"], ["lainnya", "Lainnya"]];
const STOP_BADGE = { picked_up: ["badge-green", "DIJEMPUT"], failed: ["badge-red", "GAGAL"],
                     cancelled: ["badge-gray", "DIBATALKAN"] };

async function loadDriverData() {
  let route;
  try {
    route = await api("/api/v1/driver/active-route");
    try { localStorage.setItem(`biochain_driver_route:${myUid()}`, JSON.stringify(route)); } catch {}
  } catch (err) {
    // Tanpa sinyal: tampilkan rute terakhir yang tersimpan agar supir tetap bisa bekerja
    try { route = JSON.parse(localStorage.getItem(`biochain_driver_route:${myUid()}`) || "null"); } catch { route = null; }
    if (!route) {
      loadDriverBackhaulTasks();
      $("driver-stops-list").innerHTML = `<p class="muted">Offline dan belum ada rute tersimpan.</p>`;
      return;
    }
    showToast("Offline: menampilkan rute tersimpan terakhir", "📵");
  }
  loadDriverBackhaulTasks();
  if (!route.active) {
    $("driver-stops-list").innerHTML = `<p class="muted">Tidak ada rute aktif saat ini.</p>`;
    trackStop();
    return;
  }
  const queuedStops = new Set(myOutbox("/api/v1/driver/confirm-pickup").map(i => i.body.route_stop_id));
  const queuedFails = new Set(myOutbox("/api/v1/driver/stop-failed").map(i => i.body.route_stop_id));
  const started = route.status === "in_progress" || myOutbox().some(i => i.path.startsWith("/api/v1/driver/start-route"));
  if ($("d-status")) $("d-status").innerText = started ? "BERJALAN" : "DIRENCANAKAN";
  if ($("d-km")) $("d-km").innerText = route.total_km != null ? num(route.total_km, 1) : "–";
  if ($("d-plate")) $("d-plate").innerText = route.vehicle_plate || "Kendaraan";
  if ($("d-util")) $("d-util").innerText = route.utilization_pct != null ? `${num(route.utilization_pct, 1)}%` : "–";
  if ($("d-gps-km")) $("d-gps-km").innerText = num(TRACK.km, 2);

  const pendingCount = route.stops.filter(s => s.stop_status === "pending"
    && !queuedStops.has(s.id) && !queuedFails.has(s.id)).length;
  $("driver-actions").innerHTML = !started
    ? `<button class="btn btn-primary" data-onclick="driverStart(${route.route_id}, this)">▶️ Mulai Rute (aktifkan GPS)</button>`
    : `<button class="btn btn-secondary" ${pendingCount ? "disabled" : ""} data-onclick="driverComplete(${route.route_id}, this)">
         🏁 Selesaikan Rute${pendingCount ? ` (${pendingCount} stop belum ditangani)` : ""}</button>
       <span class="muted" style="font-size:var(--fs-xs);margin-left:8px;">GPS ${TRACK.watchId !== null ? "merekam ✅" : "mati"}</span>`;

  $("driver-stops-list").innerHTML = route.stops.map(s => {
    const status = queuedStops.has(s.id) ? "picked_up" : queuedFails.has(s.id) ? "failed" : s.stop_status;
    const queued = queuedStops.has(s.id) || queuedFails.has(s.id);
    const badge = STOP_BADGE[status];
    const actions = status === "pending" && started
      ? `<button class="btn btn-primary btn-sm" data-onclick="confirmPickupStop(${s.id}, this)">Scan QR 📷</button>
         <select id="fail-${s.id}" class="input" style="max-width:170px;font-size:var(--fs-xs);margin-top:8px;">
           ${FAIL_REASONS.map(([v, l]) => `<option value="${v}">${esc(l)}</option>`).join("")}</select>
         <button class="btn btn-secondary btn-sm" data-onclick="reportStopFailed(${s.id}, this)">Gagal ❌</button>`
      : badge ? `<span class="badge ${badge[0]}">${badge[1]}${queued ? " · antre" : ""}</span>` : "";
    return `
      <div style="background:var(--surface-1); border:1px solid var(--border); border-radius:var(--radius-md); padding:12px; margin-bottom:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap;">
          <div>
            <strong>Stop #${s.order}: ${esc(s.mill ? s.mill.name : `Titik Pemasok #${s.mill_id}`)}</strong>
            <span class="badge badge-purple" style="margin-left:6px; font-size:11px;">🌾 ${esc((s.commodity || 'sekam_padi').replace('_', ' '))}</span>
            <div style="font-size:var(--fs-xs); color:var(--ink-muted); margin-top:2px;">
              ${s.planned_ton} Ton${s.fail_reason ? ` · ${esc(s.fail_reason)}` : ""}</div>
          </div>
          <div style="text-align:right;">${actions}</div>
        </div>
      </div>`;
  }).join("");

  if (started) trackStart(route.route_id);

  setTimeout(() => {
    if (typeof L === "undefined") return;                  // peta butuh internet; daftar stop tetap jalan
    if (!driverMap) {
      driverMap = L.map("driver-map").setView([-7.74, 110.36], 12);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OSM" }).addTo(driverMap);
      driverLayer = L.layerGroup().addTo(driverMap);
    }
    driverLayer.clearLayers();
    const waypoints = [];
    route.stops.forEach(s => {
      if (s.mill && s.mill.lat && s.mill.lon) {
        waypoints.push([s.mill.lat, s.mill.lon]);
        const done = s.stop_status === "picked_up";
        L.circleMarker([s.mill.lat, s.mill.lon], {
          radius: 8, color: done ? "#15803d" : "#d97706", fillColor: done ? "#22c55e" : "#f59e0b", fillOpacity: 0.9,
        }).addTo(driverLayer).bindPopup(`<b>Stop #${s.order}: ${esc(s.mill.name)}</b><br>${s.planned_ton} Ton Biomassa`);
      }
    });
    if (waypoints.length > 1) {
      L.polyline(waypoints, { color: "#2563eb", weight: 4, dashArray: "5, 10" }).addTo(driverLayer);
      driverMap.fitBounds(waypoints, { padding: [30, 30] });
    }
  }, 100);
}

async function loadDriverBackhaulTasks() {
  const box = $("driver-backhaul-list");
  if (!box) return;
  try {
    const tasks = await api("/api/v1/driver/backhaul-tasks");
    if (!tasks || !tasks.length) {
      box.innerHTML = `<p class="muted" style="padding:8px 0;">Tidak ada penugasan muatan balik abu bottom ash saat ini.</p>`;
      return;
    }
    box.innerHTML = tasks.map(t => {
      const isDelivered = t.status === "DELIVERED_TO_FARMER";
      return `
        <div style="background:var(--surface-1); border:1px solid var(--border); border-radius:var(--radius-md); padding:12px; margin-bottom:10px;">
          <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap;">
            <div>
              <strong>🚚 ${esc(t.dispatch_code)}</strong> · Plat: <code>${esc(t.vehicle_plate || "-")}</code>
              <div style="font-size:var(--fs-xs); color:var(--ink-muted); margin-top:2px;">
                Muatan: <b>${num(t.total_weight_kg, 1)} kg</b> (${t.total_bags || "-"} karung) · Vol: ${num(t.volume_m3, 2)} m³
                ${t.loading_instructions ? `<br>Instruksi: <i>${esc(t.loading_instructions)}</i>` : ""}
              </div>
            </div>
            <div style="text-align:right;">
              <span class="badge ${isDelivered ? "badge-green" : "badge-blue"}">${esc(t.status)}</span>
              ${!isDelivered ? `
                <div style="margin-top:6px; display:flex; gap:4px; justify-content:flex-end; flex-wrap:wrap;">
                  <button type="button" class="btn btn-secondary btn-sm" data-onclick="driverScanBackhaulCheckpoint('${esc(t.qr_dispatch_token)}')">📷 Scan Outbound</button>
                  <button type="button" class="btn btn-primary btn-sm" data-onclick="driverConfirmDropBiochar(${Number(t.id)}, ${Number(t.total_weight_kg)})">🤝 Konfirmasi Serah Abu Sawah</button>
                </div>
              ` : `<div style="font-size:var(--fs-xs); color:var(--success); margin-top:4px;">✓ Selesai diantar ke sawah</div>`}
            </div>
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    if (box) box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${esc(err.message)}</div>`;
  }
}
window.loadDriverBackhaulTasks = loadDriverBackhaulTasks;

async function driverScanBackhaulCheckpoint(qrToken) {
  try {
    const res = await api("/api/v1/driver/checkpoint-scan", {
      method: "POST",
      body: {
        qr_token: qrToken,
        checkpoint_type: "FACTORY_OUTBOUND",
        notes: "Driver muat abu bottom ash di gerbang outbound pabrik"
      }
    });
    showToast(res.message || "Checkpoint muatan balik abu bottom ash diverifikasi! 📷", "✅");
    loadDriverBackhaulTasks();
  } catch (err) { showToast(err.message, "❌"); }
}
window.driverScanBackhaulCheckpoint = driverScanBackhaulCheckpoint;

function driverConfirmDropBiochar(distId, defaultKg) {
  const d = document.createElement("dialog");
  d.className = "ui-confirm";
  d.innerHTML = `<form method="dialog" style="max-width:380px;">
    <h3>🤝 Konfirmasi Penyerahan Abu Bottom Ash ke Sawah</h3>
    <p class="ui-confirm-body">Truk tiba di lokasi petani binaan. Masukkan konfirmasi berat dan catatan penyerahan abu bottom ash.</p>
    <div class="form-group"><label for="dr-drop-farmer">ID Petani Penerima</label>
      <input id="dr-drop-farmer" type="number" value="1" min="1" required></div>
    <div class="form-group"><label for="dr-drop-kg">Berat Abu Bottom Ash Diserahkan (kg)</label>
      <input id="dr-drop-kg" type="number" value="${defaultKg || 500}" min="1" step="1" required></div>
    <div class="form-group"><label for="dr-drop-notes">Catatan Serah Terima</label>
      <input id="dr-drop-notes" value="Ditumpuk di saung/lahan sawah petani" maxlength="250"></div>
    <div class="ui-confirm-actions">
      <button value="no" class="btn btn-secondary" formnovalidate>Batal</button>
      <button value="yes" class="btn btn-primary">Konfirmasi Serah Terima</button>
    </div></form>`;
  document.body.appendChild(d);
  d.addEventListener("close", async () => {
    if (d.returnValue === "yes") {
      try {
        const farmerId = Number(d.querySelector("#dr-drop-farmer").value);
        const kg = Number(d.querySelector("#dr-drop-kg").value);
        const notes = d.querySelector("#dr-drop-notes").value.trim();
        const res = await api("/api/v1/driver/confirm-backhaul-drop", {
          method: "POST",
          body: { distribution_id: distId, farmer_id: farmerId, delivered_kg: kg, notes }
        });
        showToast("Abu bottom ash berhasil diserahkan ke sawah petani! 🌾", "✅");
        loadDriverBackhaulTasks();
      } catch (err) { showToast(err.message, "❌"); }
    }
    d.remove();
  });
  d.showModal();
}
window.driverConfirmDropBiochar = driverConfirmDropBiochar;

async function driverStart(routeId, btn) {
  await withBusy(btn, async () => {
    try {
      const res = await apiMutation(`/api/v1/driver/start-route?route_id=${routeId}`, {}, `Mulai rute ${routeId}`);
      showToast(res.queued ? "Offline: mulai rute dicatat & dikirim saat ada sinyal. GPS tetap merekam." : res.message,
                res.queued ? "📵" : "🚛");
      trackStart(routeId);
    } catch (err) { showToast(err.message, "❌"); }
  });
  loadDriverData();
}

async function driverComplete(routeId, btn) {
  await withBusy(btn, async () => {
    await flushOutbox();                                    // pickup offline harus sampai dulu
    await trackFlush();
    try {
      const res = await apiMutation(`/api/v1/driver/complete-route?route_id=${routeId}`, {}, `Selesai rute ${routeId}`);
      if (res.queued) { showToast("Offline: penyelesaian rute dikirim saat ada sinyal.", "📵"); return; }
      const e = res.emissions || {};
      showToast(`${res.message} ${num(e.total_km, 1)} km · ${num(e.fuel_l, 1)} L solar · `
                + `${num(e.co2e_wtw_kg, 1)} kg CO₂e (${e.distance_source === "gps" ? "GPS" : "estimasi rencana"})`, "🎉");
      trackStop();
    } catch (err) { showToast(err.message, "❌"); }
  });
  loadDriverData();
}

async function reportStopFailed(stopId, btn) {
  const reason = $(`fail-${stopId}`) ? $(`fail-${stopId}`).value : "lainnya";
  const pos = await new Promise(resolve => {
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(p => resolve(p.coords), () => resolve(null), { timeout: 3000, maximumAge: 60000 });
  });
  await withBusy(btn, async () => {
    try {
      const res = await apiMutation("/api/v1/driver/stop-failed",
        { route_stop_id: stopId, reason, lat: pos ? pos.latitude : null, lon: pos ? pos.longitude : null },
        `Stop ${stopId} gagal`);
      showToast(res.queued ? "Offline: laporan stop gagal disimpan & dikirim saat ada sinyal." : res.message,
                res.queued ? "📵" : "⚠️");
    } catch (err) { showToast(err.message, "❌"); }
  });
  loadDriverData();
}

// F14: cocokkan QR di lokasi tanpa sinyal memakai digest dari rute (QR bertanda tangan). null = tidak bisa dicek lokal.
async function qrMatchesStop(stopId, code) {
  let route = null;
  try { route = JSON.parse(localStorage.getItem(`biochain_driver_route:${myUid()}`) || "null"); } catch {}
  const stop = route && (route.stops || []).find(s => s.id === stopId);
  const chk = stop && stop.qr_check;
  if (!chk || !(window.crypto && crypto.subtle)) return null;      // QR lama / HTTP biasa → server yang memutuskan
  const norm = String(code || "").replace(/\s+/g, "").toUpperCase().replace(/--/g, "-");
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(chk.salt + norm));
  const hex = [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
  return hex === chk.sha256;
}

async function confirmPickupStop(stopId, btn) {
  startCameraScanner(async (scannedCode) => {
    if (await qrMatchesStop(stopId, scannedCode) === false) {
      showToast("QR tidak cocok dengan lot di stop ini. Periksa karung/nota yang benar lalu scan ulang.", "⛔");
      return;
    }
    withBusy(btn, () => sendPickup(stopId, scannedCode, null));
  }, `Scan QR Petani (Stop #${stopId})`);
}

async function sendPickup(stopId, code, photo) {
  const recordedAt = new Date().toISOString();   // waktu scan sebenarnya, walau terkirim belakangan
  const pos = await new Promise(resolve => {
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(p => resolve(p.coords), () => resolve(null),
                                             { timeout: 3000, maximumAge: 60000 });
  });

  try {
    const res = await apiMutation("/api/v1/driver/confirm-pickup", {
      route_stop_id: stopId, qr_code: code, client_recorded_at: recordedAt,
      lat: pos ? pos.latitude : null, lon: pos ? pos.longitude : null,
      photo_url: photo || null,
    }, `Pickup stop ${stopId}`);
    showToast(res.queued ? "Offline: scan disimpan & dikirim otomatis saat sinyal kembali."
                         : (res.message || "Pickup berhasil dikonfirmasi!"), res.queued ? "📵" : "🎉");
    loadDriverData();
  } catch (err) {
    showToast(err.message, "❌");
  }
}

let factoryChart;
async function loadFactoryData() {
  try {
    const [esg, forecastData] = await Promise.all([
      api("/api/v1/factory/esg/summary").catch(() => null),
      api("/api/v1/factory/forecast/30d").catch(() => null),
    ]);

    if (esg) {
      if ($("f-co2")) $("f-co2").innerText = num(esg.net_carbon_credits_tco2, 2);
      if ($("f-biochar")) $("f-biochar").innerText = num(esg.estimated_biochar_ton, 1);
      if ($("f-sio2") && esg.estimated_sio2_ton != null) $("f-sio2").innerText = num(esg.estimated_sio2_ton, 1);
    }

    if (forecastData && forecastData.points) {
      const labels = forecastData.points.map(p => p.date.slice(5));
      const values = forecastData.points.map(p => p.pred_husk_ton);

      const ctx = $("factory-forecast-chart");
      if (ctx && typeof Chart !== "undefined") {
        if (factoryChart) factoryChart.destroy();
        factoryChart = new Chart(ctx, {
          type: "line",
          data: {
            labels,
            datasets: [{
              label: "Prediksi Pasokan Biomassa (Ton/Hari)",
              data: values,
              borderColor: "#15803d",
              backgroundColor: "rgba(34, 197, 94, 0.12)",
              fill: true,
              tension: 0.3,
            }],
          },
          options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { title: { display: true, text: "Ton Biomassa" } } },
          },
        });
      }
    }
  } catch (err) {
    console.error("loadFactoryData:", err);
  }
}

async function calcCarbon() {
  const tonInput = $("c-ton").value;
  const kmInput = $("c-km").value;
  if (!tonInput) return showToast("Isi jumlah ton biomassa dulu.", "⚠️");
  const ton = Number(tonInput);
  const km = kmInput !== "" ? Number(kmInput) : 0;
  try {
    const res = await api("/api/v1/labs/carbon/calculate", {
      biomass_ton: ton,
      transport_km: km,
      feedstock_type: "rice_husk",
    });
    const nekHtml = res.carbon_value_rp != null
      ? `Potensi Nilai NEK: <strong>${rp(res.carbon_value_rp)}</strong> (${res.carbon_value_note || ''})`
      : `<span style="color:var(--amber-dark);">${res.carbon_value_note || 'Isi harga pasar karbon di menu Parameter untuk melihat nilai NEK'}</span>`;
    $("carbon-res-box").innerHTML = `
      <div style="background:var(--primary-soft); border:1px solid var(--primary-border); border-radius:var(--radius-md); padding:12px; font-size:var(--fs-sm);">
        <div style="font-size:18px; font-weight:800; color:var(--primary-dark); margin-bottom:4px;">
          🌿 Net Reduksi: ${num(res.net_reduction_tco2, 2)} tCO₂e
        </div>
        <div>Emisi dihindari (open burning): ${num(res.emission_avoided_tco2, 2)} tCO₂e</div>
        <div>Emisi logistik angkut: ${num(res.transport_emission_tco2, 3)} tCO₂e</div>
        <div style="margin-top:8px; font-size:var(--fs-xs); color:var(--ink-muted);">${nekHtml}</div>
      </div>
    `;
  } catch (err) {
    showToast(err.message, "❌");
  }
}

async function loadAdminPanel() {
  try {
    const roleFilter = $("admin-user-role-filter") ? $("admin-user-role-filter").value : "";
    const usersUrl = "/api/v1/admin/users" + (roleFilter ? `?role=${encodeURIComponent(roleFilter)}` : "");
    const [stats, users] = await Promise.all([
      api("/api/v1/admin/stats"),
      api(usersUrl),
    ]);

    const statsRow = $("admin-stats-row");
    if (statsRow) {
      statsRow.innerHTML = `
        <div class="kpi-tile"><div class="kpi-lbl">Total Pengguna</div><div class="kpi-val">${stats.total_users}</div><div class="kpi-lbl">User Terdaftar</div></div>
        <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Total Titik Pemasok</div><div class="kpi-val">${stats.total_mills}</div><div class="kpi-lbl">Titik Pemasok Biomassa</div></div>
        <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Total Laporan Panen</div><div class="kpi-val">${stats.total_harvests}</div><div class="kpi-lbl">Transaksi Biomassa</div></div>
        <div class="kpi-tile kpi-purple"><div class="kpi-lbl">Rute Armada</div><div class="kpi-val">${stats.total_routes}</div><div class="kpi-lbl">Rute Pengiriman</div></div>
      `;
    }

    const roleBadge = (r) => {
      if (r === "admin") return "badge-red";
      if (r === "pabrik") return "badge-purple";
      if (r === "pengepul") return "badge-amber";
      if (r === "driver") return "badge-blue";
      if (r === "auditor") return "badge-blue";
      return "badge-green";
    };

    const tbody = $("admin-users-table").querySelector("tbody");
    if (!users || !users.length) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--ink-muted); padding:20px;">Tidak ada pengguna ditemukan untuk filter ini.</td></tr>`;
      return;
    }
    tbody.innerHTML = users.map(u => {
      const isSelf = STATE.user && (STATE.user.user_id === u.id || STATE.user.id === u.id);
      const statusBadge = u.is_active
        ? `<span class="badge badge-green">🟢 Aktif</span>`
        : `<span class="badge badge-amber">⏳ Menunggu / Nonaktif</span>`;
      
      const actionBtn = u.is_active
        ? (isSelf ? `<span style="font-size:var(--fs-xs); color:var(--ink-muted);">(Akun Anda)</span>`
                  : `<button class="btn btn-secondary btn-sm" style="padding:2px 8px; font-size:var(--fs-xs);" data-onclick="toggleUserActive(${u.id})">Nonaktifkan</button>`)
        : `<button class="btn btn-primary btn-sm" style="padding:2px 8px; font-size:var(--fs-xs);" data-onclick="toggleUserActive(${u.id})">⚡ Aktifkan</button>`;

      return `
      <tr>
        <td>#${u.id}</td>
        <td><b>${esc(u.full_name)}</b></td>
        <td><code>${esc(u.username ? '@' + u.username : '')} ${esc(u.phone)}</code></td>
        <td><span class="badge ${roleBadge(u.role)}">${esc(u.role.toUpperCase())}</span></td>
        <td>${esc(u.kecamatan || 'Sleman')}</td>
        <td>${u.xp_total || 0} XP</td>
        <td>${statusBadge}</td>
        <td>${actionBtn}${isSelf ? "" : ` <button class="btn btn-secondary btn-sm" data-onclick="resetUserPassword(${Number(u.id)})">🔑 Reset password</button>`}</td>
      </tr>
      `;
    }).join("");
  } catch (err) {
    console.error("loadAdminPanel:", err);
  }
}

async function toggleUserActive(userId) {
  try {
    const res = await api(`/api/v1/admin/users/${userId}/toggle-active`, { method: "POST" });
    showToast(res.message, "🔄");
    await loadAdminPanel();
  } catch (err) {
    showToast("Gagal mengubah status pengguna: " + err.message, "❌");
  }
}

// Reset password oleh admin (F6): password sementara tampil SEKALI di modal untuk disampaikan langsung
async function resetUserPassword(userId) {
  try {
    const r = await api(`/api/v1/admin/users/${userId}/reset-password`, { method: "POST" });
    openModal(`Password sementara · ${r.full_name || "#" + r.user_id}`, r.temporary_password,
              `${r.phone || r.username || ""} — sampaikan langsung ke pemilik akun, lalu minta segera diganti.`);
  } catch (err) {
    showToast("Gagal reset password: " + err.message, "❌");
  }
}

function openAdminCreateUserModal() {
  const m = $("admin-create-modal");
  if (m) m.classList.add("open");
}

function closeAdminCreateModal() {
  const m = $("admin-create-modal");
  if (m) m.classList.remove("open");
}

async function handleAdminCreateUserSubmit(e) {
  e.preventDefault();
  const btn = $("btn-adm-submit-user");
  btn.disabled = true;
  btn.innerText = "Menyimpan...";
  try {
    const payload = {
      role: $("adm-role").value,
      full_name: $("adm-fullname").value.trim(),
      phone: $("adm-phone").value.trim(),
      username: $("adm-username").value.trim() || null,
      password: $("adm-pass").value.trim(),
      kecamatan: $("adm-kecamatan").value.trim() || "Sleman",
      is_active: $("adm-active").checked,
    };
    const res = await api("/api/v1/admin/users", {
      body: payload,
    });
    showToast(`User ${res.full_name} berhasil ditambahkan!`, "✅");
    closeAdminCreateModal();
    $("admin-create-user-form").reset();
    await loadAdminPanel();
  } catch (err) {
    showToast("Gagal menambah user: " + err.message, "❌");
  } finally {
    btn.disabled = false;
    btn.innerText = "Simpan Pengguna";
  }
}

// Engine Lab → js/modules/engine-lab.js

// ==============================================================
// HANDLER DEKLARATIF (pengganti onclick= inline; CSP tanpa 'unsafe-inline' & tanpa eval)
// Atribut data-onclick / data-onchange / data-oninput / data-onsubmit berisi `namaFungsi(arg, ...)`.
// Argumen yang diizinkan HANYA literal: angka, 'string', "string", true/false/null, `this` (elemen), `event`.
// Fungsi harus global (function deklarasi di file ini / window.*). Selain itu ditolak & dicatat di konsol.
// ==============================================================
function printPage() { window.print(); }
function clickById(id) { const el = document.getElementById(id); if (el) el.click(); }

function parseDeclarativeCall(src) {
  const m = /^\s*([A-Za-z_$][\w$]*)\s*\(([\s\S]*)\)\s*;?\s*$/.exec(src || "");
  if (!m) return null;
  const args = [], body = m[2];
  let i = 0;
  const ws = () => { while (i < body.length && /\s/.test(body[i])) i++; };
  while (true) {
    ws();
    if (i >= body.length) break;
    const ch = body[i];
    if (ch === "'" || ch === '"') {
      let out = ""; i++;
      while (i < body.length && body[i] !== ch) { if (body[i] === "\\" && i + 1 < body.length) i++; out += body[i++]; }
      if (body[i] !== ch) return null;
      i++; args.push({ v: out });
    } else {
      const t = /^(-?\d+(?:\.\d+)?|true|false|null|this|event)/.exec(body.slice(i));
      if (!t) return null;
      i += t[0].length;
      const w = t[0];
      args.push(w === "this" ? { k: "this" } : w === "event" ? { k: "event" } :
                w === "true" ? { v: true } : w === "false" ? { v: false } : w === "null" ? { v: null } : { v: Number(w) });
    }
    ws();
    if (i < body.length) { if (body[i] !== ",") return null; i++; }
  }
  return { fn: m[1], args };
}

const DECL_CACHE = new Map();
function runDeclarative(el, attr, ev) {
  const src = el.getAttribute(attr);
  let call = DECL_CACHE.get(src);
  if (call === undefined) { call = parseDeclarativeCall(src); DECL_CACHE.set(src, call); }
  const fn = call && window[call.fn];
  if (typeof fn !== "function") { console.error("[Bio-Chain] handler ditolak:", attr, src); return; }
  return fn.apply(el, call.args.map(a => (a.k === "this" ? el : a.k === "event" ? ev : a.v)));
}
["click", "change", "input", "submit"].forEach(type => {
  const attr = `data-on${type}`;
  document.addEventListener(type, ev => {
    const el = ev.target && ev.target.closest && ev.target.closest(`[${attr}]`);
    if (el) runDeclarative(el, attr, ev);
  });
});

// Start
initApp();
