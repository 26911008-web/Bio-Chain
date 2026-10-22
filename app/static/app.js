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

const $ = id => document.getElementById(id);
const rp = n => "Rp " + Math.round(Number(n) || 0).toLocaleString("id-ID");
const num = (n, d=1) => Number(n || 0).toLocaleString("id-ID", {maximumFractionDigits: d});
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const newId = () => (crypto.randomUUID ? crypto.randomUUID()
  : Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 12));

function showToast(msg, icon="✅") {
  const t = $("toast");
  $("toast-msg").innerText = msg;
  $("toast-icon").innerText = icon;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 3500);
}

let currentModalQrCode = "";

function openModal(title, code, sub) {
  currentModalQrCode = String(code || "");
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

// ==============================================================
// CAMERA QR SCANNER & AUDIO FEEDBACK
// ==============================================================
let html5QrScannerInstance = null;
let currentScannerCallback = null;
let currentCameraFacing = "environment"; // "environment" (rear) or "user" (front)

function playScanBeep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    gain.gain.setValueAtTime(0.2, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.16);
  } catch(e) {}
}

async function startCameraScanner(onSuccessCallback, title = "Pindai Kode QR Kamera") {
  currentScannerCallback = onSuccessCallback;
  $("scanner-modal-title").innerText = title;
  $("scanner-camera-error").style.display = "none";
  $("scanner-success-pill").style.display = "none";
  $("scanner-manual-input").value = "";
  $("scanner-laser").style.display = "block";
  $("scanner-modal").classList.add("open");

  if (!window.Html5Qrcode) {
    $("scanner-camera-error").style.display = "block";
    $("scanner-camera-error").innerText = "Modul kamera sedang dimuat... Harap tunggu beberapa detik atau gunakan input manual.";
    return;
  }

  try {
    if (html5QrScannerInstance) {
      try { await html5QrScannerInstance.stop(); } catch(e) {}
      html5QrScannerInstance = null;
    }

    html5QrScannerInstance = new Html5Qrcode("qr-camera-stream");
    const config = {
      fps: 12,
      qrbox: (viewfinderWidth, viewfinderHeight) => {
        const edge = Math.min(viewfinderWidth, viewfinderHeight) * 0.75;
        return { width: Math.floor(edge), height: Math.floor(edge) };
      },
      aspectRatio: 1.0
    };

    await html5QrScannerInstance.start(
      { facingMode: currentCameraFacing },
      config,
      (decodedText) => {
        onQrDetected(decodedText);
      },
      (error) => {}
    );
  } catch (err) {
    console.warn("Kamera tidak dapat dimulai:", err);
    $("scanner-laser").style.display = "none";
    $("scanner-camera-error").style.display = "block";
    $("scanner-camera-error").innerHTML = `⚠️ Kamera tidak dapat diakses (${esc(err)}).<br>Pastikan izin kamera diizinkan, atau gunakan opsi <strong>Upload Foto QR</strong> / input manual di bawah.`;
  }
}

async function toggleCameraFacing() {
  currentCameraFacing = currentCameraFacing === "environment" ? "user" : "environment";
  $("btn-switch-camera").innerText = currentCameraFacing === "environment" ? "🔄 Kamera Belakang" : "🔄 Kamera Depan";
  if (html5QrScannerInstance && html5QrScannerInstance.isScanning) {
    await startCameraScanner(currentScannerCallback, $("scanner-modal-title").innerText);
  }
}

function onQrDetected(codeText) {
  playScanBeep();
  if (navigator.vibrate) navigator.vibrate(100);

  const clean = String(codeText || "").trim();
  $("scanner-detected-code").innerText = clean;
  $("scanner-success-pill").style.display = "block";
  $("scanner-laser").style.display = "none";

  showToast(`QR Berhasil Dipindai: ${clean}`, "📷");

  setTimeout(async () => {
    await stopCameraScanner();
    if (typeof currentScannerCallback === "function") {
      currentScannerCallback(clean);
    }
  }, 600);
}

async function stopCameraScanner() {
  if (html5QrScannerInstance) {
    try {
      if (html5QrScannerInstance.isScanning) {
        await html5QrScannerInstance.stop();
      }
      html5QrScannerInstance.clear();
    } catch(e) {}
    html5QrScannerInstance = null;
  }
  $("scanner-modal").classList.remove("open");
}

function closeScannerModal() {
  stopCameraScanner();
}

function handleQrFileUpload(input) {
  if (!input.files || !input.files.length) return;
  const file = input.files[0];
  if (!window.Html5Qrcode) return showToast("Modul scan belum siap", "⚠️");

  const tempScanner = new Html5Qrcode("qr-camera-stream");
  tempScanner.scanFile(file, true)
    .then(decodedText => {
      onQrDetected(decodedText);
    })
    .catch(err => {
      showToast("Tidak dapat mendeteksi kode QR pada foto ini.", "❌");
    });
}

function submitManualScannedCode() {
  const code = ($("scanner-manual-input").value || "").trim();
  if (!code) return showToast("Masukkan kode terlebih dahulu.", "⚠️");
  onQrDetected(code);
}

function openGlobalScanner() {
  startCameraScanner((code) => {
    openModal("Hasil Pemindaian QR", code, "Kode QR berhasil dibaca dari kamera");
  }, "Pemindai QR Kamera Bio-Chain");
}

// ==============================================================
// STANDALONE QR GENERATOR TOOL
// ==============================================================
let currentGeneratedQrText = "";

function openQrGeneratorModal() {
  $("generator-modal").classList.add("open");
  generateCustomQr();
}

function closeGeneratorModal() {
  $("generator-modal").classList.remove("open");
}

function generateCustomQr() {
  const val = ($("gen-input-text")?.value || "").trim() || "BIO-SEKAM-2026";
  currentGeneratedQrText = val;
  const wrap = $("gen-qr-canvas-wrap");
  if (!wrap) return;
  wrap.innerHTML = "";
  if (window.QRCode) {
    new QRCode(wrap, {
      text: val,
      width: 170,
      height: 170,
      colorDark: "#111111",
      colorLight: "#ffffff",
      correctLevel: QRCode.CorrectLevel.H
    });
  } else {
    wrap.innerHTML = `<div style="font-size:40px;">📱</div>`;
  }
  $("gen-qr-text-preview").innerText = val;
}

function setPresetQr(type) {
  const input = $("gen-input-text");
  if (type === "petani") {
    input.value = `BIO-FARMER-${Date.now().toString(36).toUpperCase()}-1500KG`;
  } else if (type === "batch") {
    input.value = `BIO-BATCH-${new Date().toISOString().slice(0, 10).replace(/-/g, "")}-PABRIK`;
  } else if (type === "qc") {
    input.value = `BIO-QC-LOT-${Math.floor(Math.random() * 9000 + 1000)}-M12`;
  }
  generateCustomQr();
}

function downloadGeneratedQr() {
  const wrap = $("gen-qr-canvas-wrap");
  const canvas = wrap ? wrap.querySelector("canvas") : null;
  const img = wrap ? wrap.querySelector("img") : null;
  const src = canvas ? canvas.toDataURL("image/png") : (img ? img.src : null);
  if (!src) return showToast("QR belum digenerate.", "⚠️");
  const a = document.createElement("a");
  a.href = src;
  a.download = `QR_${currentGeneratedQrText.replace(/[^a-zA-Z0-9_-]/g, "_")}.png`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  showToast("Gambar QR berhasil diunduh!", "⬇️");
}

function copyGeneratedQrText() {
  if (!currentGeneratedQrText) return;
  navigator.clipboard.writeText(currentGeneratedQrText)
    .then(() => showToast(`Teks disalin: ${currentGeneratedQrText}`, "📋"))
    .catch(() => showToast("Gagal menyalin teks", "❌"));
}

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

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (options.body && !headers["Content-Type"]) {
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
      body: options.body ? JSON.stringify(options.body) : undefined,
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

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data.detail || res.statusText || "Terjadi kesalahan";
    const err = new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    err.status = res.status;
    if (data.code) err.code = data.code;
    throw err;
  }
  return data;
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
  try {
    const res = await fetch(`/api/reports/monthly${rpQuery("&format=csv")}`, { headers: { Authorization: `Bearer ${STATE.token}` } });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`);
    const blob = await res.blob();
    const name = (res.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/)?.[1] || "laporan.csv";
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: name });
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(a.href);
  } catch (err) { showToast(err.message, "❌"); }
}

async function downloadReportXlsx() {
  try {
    const res = await fetch(`/api/reports/monthly${rpQuery("&format=xlsx")}`, { headers: { Authorization: `Bearer ${STATE.token}` } });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`);
    const blob = await res.blob();
    const name = (res.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/)?.[1] || "laporan.xlsx";
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: name });
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(a.href);
  } catch (err) { showToast(err.message, "❌"); }
}
$("btn-rp") && ($("btn-rp").onclick = e => withBusy(e.currentTarget, loadReport));
$("btn-rp-csv") && ($("btn-rp-csv").onclick = e => withBusy(e.currentTarget, downloadReportCsv));
$("btn-rp-xlsx") && ($("btn-rp-xlsx").onclick = e => withBusy(e.currentTarget, downloadReportXlsx));

// ==============================================================
// ASISTEN AI — jawaban mengalir (streaming); konteks data dibatasi peran di server.
// Teks model dirender sebagai teks (esc) + markdown minimal; tidak ada HTML dari model yang dieksekusi.
// ==============================================================
const AI_SUGGEST = {
  petani: ["Bagaimana agar sekam saya naik ke Grade A?", "Kapan waktu terbaik melapor stok?", "Apa arti dompet biochar saya?"],
  pengepul: ["Antrean mana yang sebaiknya diverifikasi dulu?", "Cara cepat menilai kadar air di lapangan?", "Bagaimana menekan susut timbangan?"],
  driver: ["Tips muat sekam agar bak truk optimal?", "Apa yang harus dicek saat scan QR?", "Bagaimana jika sinyal hilang di jalan?"],
  pabrik: ["Saran optimasi pasokan minggu ini?", "Bagaimana menekan susut pengepul→pabrik?", "Strategi blending untuk sekam basah?"],
  auditor: ["Ringkas temuan neraca massa saat ini.", "Indikator kecurangan timbangan apa yang perlu dipantau?"],
  admin: ["Ringkas kondisi rantai pasok hari ini.", "Apa risiko operasional terbesar saat ini?"],
};
const AI = { history: [], providers: [], busy: false };

function aiFormat(text) {
  return esc(text)
    .replace(/(?:^|\n)###\s*(.+?)(?=\n|$)/g, "<h4>$1</h4>")
    .replace(/(?:^|\n)##\s*(.+?)(?=\n|$)/g, "<h3>$1</h3>")
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/(^|\n)\s*[-*]\s+/g, "$1• ")
    .replace(/\n/g, "<br>");
}

function aiStore(key, val) { try { val === undefined ? localStorage.removeItem(key) : localStorage.setItem(key, val); } catch {} }
function aiLoad(key) { try { return localStorage.getItem(key); } catch { return null; } }

function aiEnsureWidget() {
  if ($("ai-fab")) return;
  const fab = document.createElement("button");
  fab.id = "ai-fab";
  fab.type = "button";
  fab.innerHTML = '<span aria-hidden="true">🤖</span><span class="fab-label">Asisten</span>';
  fab.setAttribute("aria-label", "Asisten AI");
  fab.setAttribute("aria-controls", "ai-panel");
  document.body.appendChild(fab);

  const panel = document.createElement("div");
  panel.id = "ai-panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Asisten AI Bio-Chain");
  panel.innerHTML = `
    <div class="ai-head">
      <strong style="font-size:14px;">🤖 Asisten Bio-Chain</strong>
      <span style="flex:1"></span>
      <button type="button" class="btn btn-secondary btn-sm" id="ai-clear" title="Mulai percakapan baru">↺</button>
      <button type="button" class="btn btn-secondary btn-sm" id="ai-close" aria-label="Tutup">✕</button>
      <div style="display:flex; gap:8px; width:100%;">
        <select id="ai-provider" aria-label="Penyedia AI"></select>
        <select id="ai-model" aria-label="Model"></select>
      </div>
    </div>
    <div class="ai-log" id="ai-log" aria-live="polite"></div>
    <div class="ai-chips" id="ai-chips"></div>
    <div class="ai-meta" id="ai-meta"></div>
    <form class="ai-form" id="ai-form">
      <textarea id="ai-input" placeholder="Tanya atau minta saran optimasi…" maxlength="2000"></textarea>
      <button type="submit" class="btn btn-primary" id="ai-send">Kirim</button>
    </form>`;
  document.body.appendChild(panel);

  fab.onclick = () => { panel.classList.toggle("open"); if (panel.classList.contains("open")) { aiInitProviders(); $("ai-input").focus(); } };
  $("ai-close").onclick = () => panel.classList.remove("open");
  $("ai-clear").onclick = aiReset;
  $("ai-provider").onchange = () => { aiStore("ai_provider", $("ai-provider").value); aiLoadModels(); };
  $("ai-model").onchange = () => aiStore(`ai_model_${$("ai-provider").value}`, $("ai-model").value);
  $("ai-form").onsubmit = e => { e.preventDefault(); aiSend($("ai-input").value); };
  $("ai-input").onkeydown = e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); aiSend($("ai-input").value); } };
}

function aiShow(loggedIn) {
  aiEnsureWidget();
  $("ai-fab").style.display = loggedIn ? "inline-flex" : "none";
  if (!loggedIn) $("ai-panel").classList.remove("open");
  aiReset();
  AI.providers = [];
}

function aiReset() {
  AI.history = [];
  if (!$("ai-log")) return;
  const role = STATE.user && STATE.user.role;
  $("ai-log").innerHTML = `<div class="ai-msg bot">Halo${STATE.user ? ", " + esc(STATE.user.full_name) : ""}! Saya bisa menjawab pertanyaan dan memberi saran optimasi berdasarkan data peran <b>${esc(role || "")}</b> Anda. Saya tidak bisa mengubah data.</div>`;
  $("ai-chips").innerHTML = (AI_SUGGEST[role] || []).map((q, i) =>
    `<span class="demo-chip" data-i="${i}">${esc(q)}</span>`).join("");
  $("ai-chips").querySelectorAll(".demo-chip").forEach(c => { c.onclick = () => aiSend(AI_SUGGEST[role][Number(c.dataset.i)]); });
}

async function aiInitProviders() {
  if (AI.providers.length) return;
  try {
    const r = await api("/api/v1/assistant/providers");
    AI.providers = r.providers;
    const saved = aiLoad("ai_provider");
    const pick = AI.providers.find(p => p.id === saved && p.configured) ? saved : r.default;
    $("ai-provider").innerHTML = AI.providers.map(p =>
      `<option value="${esc(p.id)}" ${p.configured ? "" : "disabled"} ${p.id === pick ? "selected" : ""}>${esc(p.label)}${p.configured ? "" : " (belum diatur)"}</option>`).join("");
    aiLoadModels();
  } catch (err) {
    $("ai-meta").textContent = "Gagal memuat daftar penyedia: " + err.message;
  }
}

async function aiLoadModels() {
  const pid = $("ai-provider").value;
  const prov = AI.providers.find(p => p.id === pid) || {};
  const saved = aiLoad(`ai_model_${pid}`) || prov.default_model;
  $("ai-model").innerHTML = saved ? `<option>${esc(saved)}</option>` : `<option value="">memuat model…</option>`;
  $("ai-meta").textContent = prov.note || "";
  try {
    const r = await api(`/api/v1/assistant/providers/${encodeURIComponent(pid)}/models`);
    const models = r.models.length ? r.models : (saved ? [saved] : []);
    $("ai-model").innerHTML = models.map(m => `<option ${m === saved ? "selected" : ""}>${esc(m)}</option>`).join("")
      || `<option value="">(tidak ada model)</option>`;
    if (saved && !models.includes(saved)) $("ai-meta").textContent = `Model ${saved} tidak ditemukan; pilih dari daftar.`;
  } catch (err) {
    $("ai-meta").textContent = err.message;          // mis. Ollama belum jalan / kunci ditolak
  }
}

async function aiSend(text) {
  text = (text || "").trim();
  if (!text || AI.busy) return;
  AI.busy = true;
  $("ai-send").disabled = true;
  $("ai-input").value = "";
  const log = $("ai-log");
  log.insertAdjacentHTML("beforeend", `<div class="ai-msg user">${esc(text)}</div>`);
  const bubble = document.createElement("div");
  bubble.className = "ai-msg bot";
  bubble.textContent = "⏳ Berpikir…";
  log.appendChild(bubble);
  log.scrollTop = log.scrollHeight;

  const started = Date.now();
  let answer = "";
  try {
    const res = await fetch("/api/v1/assistant/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${STATE.token}` },
      body: JSON.stringify({ message: text, history: AI.history.slice(-10),
                             provider: $("ai-provider").value || undefined, model: $("ai-model").value || undefined }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `HTTP ${res.status}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      answer += decoder.decode(value, { stream: true });
      bubble.innerHTML = aiFormat(answer);
      log.scrollTop = log.scrollHeight;
    }
    if (!answer.trim()) throw new Error("Model tidak mengembalikan jawaban.");
    AI.history.push({ role: "user", content: text }, { role: "assistant", content: answer.slice(0, 4000) });
    $("ai-meta").textContent = `${res.headers.get("X-AI-Provider")} · ${res.headers.get("X-AI-Model")} · ${((Date.now() - started) / 1000).toFixed(1)} s`;
  } catch (err) {
    bubble.className = "ai-msg err";
    bubble.textContent = err.message === "Failed to fetch" ? "Tidak ada koneksi ke server." : err.message;
  } finally {
    AI.busy = false;
    $("ai-send").disabled = false;
  }
}

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
  PHOTOS_PENDING = (await idbTx("photos", "readonly", s => s.count())) || 0;
  renderNetPill();
}
async function photoQueue(file) {
  const token = PHOTO_PREFIX + newId();
  const ok = await idbTx("photos", "readwrite", s => s.put({ token, blob: file, user_id: STATE.user && STATE.user.user_id,
                                                            created_at: Date.now() }));
  if (ok === null) throw new Error("Penyimpanan HP penuh/terblokir — foto tidak bisa disimpan offline.");
  photoCountRefresh();
  return token;
}
async function photoUpload(blob) {
  const fd = new FormData();
  fd.append("file", blob, blob.name || "bukti.jpg");
  let res;
  try {
    res = await fetch("/api/v1/uploads", { method: "POST", body: fd,
                                            headers: STATE.token ? { Authorization: `Bearer ${STATE.token}` } : {} });
  } catch { const e = new Error("Tidak ada sinyal"); e.network = true; throw e; }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) { const e = new Error(data.detail || `HTTP ${res.status}`); e.status = res.status; throw e; }
  return data;
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

function myOutbox(path) {
  const uid = STATE.user && STATE.user.user_id;
  return outboxRead().filter(i => i.user_id === uid && (!path || i.path === path));
}

async function apiMutation(path, body, label) {
  const payload = { ...body, client_event_id: body.client_event_id || newId(),
                    client_recorded_at: body.client_recorded_at || new Date().toISOString() };
  if (navigator.onLine !== false) {
    try {
      return await api(path, { body: await resolvePendingPhotos(payload), noLogout: true });
    } catch (err) {
      if (!err.network && !isRetryable(err.status)) throw err;
    }
  }
  outboxWrite([...outboxRead(), { id: payload.client_event_id, path, body: payload, label,
                                  user_id: STATE.user && STATE.user.user_id, queued_at: Date.now(), tries: 0 }]);
  requestBackgroundSync();
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
  const n = await idbTx("track", "readonly", s => s.count());
  TRACK.pending = n || 0;
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
    client_point_id: `${TRACK.routeId}-${newId()}`, route_id: TRACK.routeId,
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
    const all = (await idbTx("track", "readonly", s => s.getAll())) || [];
    const byRoute = {};
    all.forEach(p => (byRoute[p.route_id] = byRoute[p.route_id] || []).push(p));
    for (const [routeId, pts] of Object.entries(byRoute)) {
      for (let i = 0; i < pts.length; i += TRACK_BATCH) {
        const batch = pts.slice(i, i + TRACK_BATCH);
        try {
          await api("/api/v1/driver/track", { noLogout: true, timeoutMs: 30000, body: {
            route_id: Number(routeId),
            points: batch.map(({ route_id, ...rest }) => rest) } });
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

function showAuthenticatedApp() {
  $("login-view").style.display = "none";
  $("app-view").style.display = "flex";

  const u = STATE.user;
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
  localStorage.removeItem("biochain_token");
  localStorage.removeItem("biochain_user");
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
    title: "AI Optimizer & Evaluator Petani",
    sub: "Analisis kadar air, potensi margin Grade A, dan efisiensi biochar",
    focuses: [
      { id: "semua", label: "🔍 Semua Aspek Mutu & Finansial" },
      { id: "mutu", label: "💧 Optimasi Kadar Air & Grade A" },
      { id: "biochar", label: "🌱 Pemanfaatan Hak Retur Biochar" },
      { id: "jadwal", label: "⏱️ Waktu & Volume Penyetoran Optimal" }
    ],
    chips: [
      "Bagaimana cara menaikkan mutu sekam ke Grade A?",
      "Berapa takaran biochar ideal per hektar sawah?",
      "Hitung potensi tambahan Rupiah jika kadar air ≤ 11%"
    ]
  },
  pengepul: {
    icon: "📦",
    title: "AI Optimizer & Evaluator Hub Pengepul",
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
      "Cara menyusun karung sekam agar muatan maksimal 25 m³?",
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
      { id: "blending", label: "🌾 Strategi Blending Sekam Basah" }
    ],
    chips: [
      "Bagaimana formula blending sekam kadar air 16% dan 11%?",
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
    sub: "Kesehatan menyeluruh platform, bottleneck aliran sekam, dan parameter harga",
    focuses: [
      { id: "semua", label: "🔍 Semua Aspek Ekosistem" },
      { id: "bottleneck", label: "🚦 Bottleneck Aliran Pasokan Lintas Persona" },
      { id: "harga", label: "💵 Evaluasi Kebijakan Parameter Harga Mutu" },
      { id: "sirkular", label: "🔄 Kinerja Pengembalian Biochar ke Petani" }
    ],
    chips: [
      "Ringkas performa rantai pasok Sleman & Klaten hari ini",
      "Apakah parameter harga dasar sekam perlu disesuaikan?",
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
        <button type="button" class="btn btn-secondary btn-sm" id="btn-eval-refresh-${role}" aria-label="Muat ulang evaluasi">↻ Muat ulang</button>
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
  const tiles = ev.kpis.map(k => `
    <div class="kpi-tile eval-tile eval-tile-${k.status}">
      <div class="kpi-lbl">${esc(k.label)}</div>
      <div class="kpi-val">${evalFmt(k.value, k.unit)}</div>
      <div class="eval-tile-meta">${evalBadge(k.status)}
        ${k.target_label ? `<span class="muted">target ${esc(k.target_label)}</span>` : ""}</div>
      ${k.status === "data_kurang" ? `<p class="eval-need">${esc(k.need || "")}</p>` : evalTrend(k)}
    </div>`).join("");
  const isPlant = ["pabrik", "admin", "auditor"].includes(ev.role);
  body.innerHTML = `
    <div class="eval-hero">${hero}<div class="eval-counts">${chips}</div></div>
    <h4 class="eval-h">Prioritas optimasi <span class="muted">(urut keparahan & dampak)</span></h4>
    ${prio}
    ${isPlant ? `<h4 class="eval-h">Komposisi output produksi</h4>${evalFlowBar(ev.flow)}` : ""}
    <h4 class="eval-h">Semua indikator</h4>
    <div class="kpi-row eval-grid">${tiles}</div>
    <p class="kpi-lbl" style="margin:4px 0 0;">${esc(ev.params_hint)}</p>`;
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
    const ev = await api("/api/v1/assistant/evaluation");
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
    const res = await fetch("/api/v1/assistant/evaluate/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${STATE.token}` },
      body: JSON.stringify({ focus: ($(`ai-eval-focus-${role}`) || {}).value || null,
                             provider: ($(`eval-provider-${role}`) || {}).value || null }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `HTTP ${res.status}`);
    }
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
// 3. PERSONA DASHBOARDS RENDERING
// ==============================================================
async function renderPersonaDashboard(role) {
  const container = $("persona-content");
  $("nav-persona-btn").innerText = `Portal ${role.toUpperCase()}`;

  if (role === "petani") {
    container.innerHTML = `
      <div class="kpi-row" id="petani-kpi">
        <div class="kpi-tile"><div class="kpi-lbl">Total Laporan Sekam</div><div class="kpi-val" id="p-tot-harvest">0</div><div class="kpi-lbl">Batch</div></div>
        <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Total Tonase Terkirim</div><div class="kpi-val" id="p-tot-ton">0</div><div class="kpi-lbl">Ton Sekam</div></div>
        <div class="kpi-tile kpi-purple"><div class="kpi-lbl">XP Gamifikasi</div><div class="kpi-val" id="p-xp">0</div><div class="kpi-lbl" id="p-tier-lbl">Mitra Emas</div></div>
        <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Dompet Biochar</div><div class="kpi-val" id="p-wallet">0</div><div class="kpi-lbl">kg hak dari sekam terolah</div></div>
      </div>

      ${renderAIEvaluationCard("petani")}

      <div class="grid-2">
        <!-- Lapor & Jual: satu alur. Lapor dulu, lalu pilih jual langsung atau lelang -->
        <div class="card">
          <div class="card-header">
            <div>
              <h3 class="card-title">🌾 Lapor &amp; Jual Sekam</h3>
              <p class="card-sub">Isi jumlah, lalu pilih cara jual. Info mutu boleh dikosongkan.</p>
            </div>
          </div>
          <form id="form-lapor-sekam">
            <div class="form-group">
              <label for="f-qty">Jumlah sekam (kg)</label>
              <input type="number" id="f-qty" class="btn btn-secondary" style="width:100%; text-align:left;" value="2500" min="50" max="50000" step="50" required>
            </div>
            <div class="form-group">
              <label for="f-mill">Lokasi penggilingan</label>
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
                <span><b>🤝 Jual ke pengepul</b><small>Harga standar sesuai mutu · bisa dicatat saat offline</small></span></label>
              <label class="sale-opt"><input type="radio" name="f-mode" value="lelang">
                <span><b>🏷️ Lelang</b><small>Pengepul menawar, Anda yang memilih · perlu sinyal</small></span></label>
            </fieldset>

            <div id="f-auction" class="sale-grid" hidden>
              <label class="fo-check"><input type="checkbox" id="ls-jemput" checked> 🚚 Dijemput pengepul</label>
              <div><input id="ls-pj" type="number" class="btn btn-secondary" style="width:100%;" value="400" min="1" placeholder="Rp/kg di tempat" aria-label="Harga minimum dijemput (Rp/kg)"></div>
              <label class="fo-check"><input type="checkbox" id="ls-antar"> 🛵 Saya antar ke gudang</label>
              <div><input id="ls-pa" type="number" class="btn btn-secondary" style="width:100%;" value="480" min="1" placeholder="Rp/kg diantar" aria-label="Harga minimum diantar (Rp/kg)"></div>
            </div>

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

        <!-- Riwayat Penyetoran -->
        <div class="card">
          <div class="card-header">
            <div>
              <h3 class="card-title">📜 Riwayat Laporan Sekam</h3>
              <p class="card-sub">Tracking status verifikasi dan bukti QR setor</p>
            </div>
          </div>
          <div style="overflow-x:auto;">
            <table class="data-table" id="table-petani-harvests">
              <thead><tr><th>ID</th><th class="num">Berat (kg)</th><th>Status</th><th>Grade</th><th>QR</th></tr></thead>
              <tbody><tr><td colspan="5" style="text-align:center;">Memuat data...</td></tr></tbody>
            </table>
          </div>
        </div>
      </div>
    `;

    // Estimasi & label tombol mengikuti cara jual + info mutu (opsional)
    const saleMode = () => (document.querySelector('input[name="f-mode"]:checked') || {}).value || "langsung";
    const gradeFrom = () => {
      const g = $("f-grade").value, m = $("f-moist").value;
      if (g) return g;
      if (m === "") return null;
      const v = Number(m);
      return v <= 12 ? "A" : v <= 15 ? "B" : v <= 18 ? "C" : "D";
    };
    const updateEarning = () => {
      const q = Number($("f-qty").value) || 0, mode = saleMode(), g = gradeFrom();
      $("f-auction").hidden = mode !== "lelang";
      $("f-submit").textContent = mode === "lelang" ? "🏷️ Pasang untuk Ditawar" : "🚀 Kirim Laporan Stok";
      if (mode === "lelang") {
        const unit = $("ls-jemput").checked ? Number($("ls-pj").value) : $("ls-antar").checked ? Number($("ls-pa").value) : 0;
        $("f-est-label").textContent = "Nilai minimum lelang";
        $("f-est-earning").textContent = rp(q * unit);
        $("f-est-note").textContent = "Tawaran di bawah harga minimum Anda tidak akan diterima sistem.";
        return;
      }
      $("f-est-label").textContent = "Estimasi pendapatan";
      const base = PV("harga_mutu.base_price_per_kg", 400);
      if (g === "D") {
        $("f-est-earning").textContent = "Berisiko ditolak";
        $("f-est-note").textContent = "Sekam basah (>18%) biasanya ditolak atau dibeli murah untuk dikeringkan. Jemur dulu bila bisa.";
      } else if (g) {
        $("f-est-earning").textContent = rp(q * base * PV(`harga_mutu.mult_${g}`, 1));
        $("f-est-note").textContent = `Perkiraan Grade ${g}. Harga final setelah uji pengepul.`;
      } else {
        $("f-est-earning").textContent = `${rp(q * base * PV("harga_mutu.mult_C", 1))} – ${rp(q * base * PV("harga_mutu.mult_A", 1.15))}`;
        $("f-est-note").textContent = "Rentang Grade C–A. Isi info mutu untuk perkiraan lebih tepat.";
      }
    };
    ["f-qty", "f-moist", "f-grade", "ls-pj", "ls-pa", "ls-jemput", "ls-antar"].forEach(id => $(id).addEventListener("input", updateEarning));
    document.querySelectorAll('input[name="f-mode"]').forEach(el => el.addEventListener("change", updateEarning));
    updateEarning();

    // Load mills for dropdown
    const mills = await api("/api/v1/farmer/mills").catch(() => []);
    $("f-mill").innerHTML = mills.map(m => `<option value="${m.id}">${esc(m.name)} (${esc(m.kecamatan)})</option>`).join("");

    // Submit report
    $("form-lapor-sekam").onsubmit = (e) => {
      e.preventDefault();
      return withBusy(e.target.querySelector("[type=submit]"), async () => { try {
        const qty = Number($("f-qty").value);
        const millId = Number($("f-mill").value) || null;
        const moist = $("f-moist").value === "" ? null : Number($("f-moist").value);
        const grade = $("f-grade").value || null;
        if (saleMode() === "lelang") {
          if (!$("ls-jemput").checked && !$("ls-antar").checked) return showToast("Pilih minimal satu skema: dijemput atau diantar.", "⚠️");
          if (!navigator.onLine) return showToast("Lelang perlu sinyal. Pilih 'Jual ke pengepul' agar laporan tersimpan offline.", "📵");
          await api("/api/v1/farmer/listings", { body: {
            quantity_kg: qty, mill_id: millId, moisture_pct: moist, grade_estimate: grade,
            allow_jemput: $("ls-jemput").checked, ask_price_jemput: $("ls-jemput").checked ? Number($("ls-pj").value) : null,
            allow_antar: $("ls-antar").checked, ask_price_antar: $("ls-antar").checked ? Number($("ls-pa").value) : null } });
          showToast("Stok dipasang. Tunggu tawaran pengepul di 'Stok Lelang & Tawaran'.", "🏷️");
          loadMyListings();
          return;
        }
        const res = await apiMutation("/api/v1/farmer/harvest", { quantity_kg: qty, mill_id: millId, moisture_est: moist, grade_est: grade },
                                      `Lapor ${qty} kg sekam`);
        if (res.queued) {
          showToast("Sinyal hilang. Laporan disimpan di HP & dikirim otomatis saat online.", "📵");
        } else {
          showToast(res.message || "Laporan berhasil dikirim!", "🎉");
          openModal("Laporan Sekam Berhasil!", res.qr_code, `${res.quantity_kg} kg · Siap Diambil`);
        }
        loadPetaniData();
      } catch (err) {
        showToast(err.message, "❌");
      } });
    };

    container.insertAdjacentHTML("beforeend", PETANI_MARKET_HTML);
    loadPetaniData();
    loadMyListings();
    initAIEvaluationCard("petani");
    if (typeof renderFieldExtras === "function") renderFieldExtras("petani", container);
  } else if (role === "pengepul") {
    container.innerHTML = `
      <div class="kpi-row">
        <div class="kpi-tile"><div class="kpi-lbl">Antrian Verifikasi</div><div class="kpi-val" id="col-pending">0</div><div class="kpi-lbl">Laporan Petani</div></div>
        <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Terverifikasi Hari Ini</div><div class="kpi-val" id="col-verified-kg">–</div><div class="kpi-lbl">kg Sekam</div></div>
        <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Skor Mutu Hari Ini</div><div class="kpi-val" id="col-avg-score">–</div><div class="kpi-lbl">Rata-rata · skala 100</div></div>
      </div>

      ${renderAIEvaluationCard("pengepul")}

      <div class="grid-2">
        <!-- Antrian Verifikasi Sekam -->
        <div class="card">
          <div class="card-header">
            <div>
              <h3 class="card-title">📦 Antrian Sekam Masuk</h3>
              <p class="card-sub">Pilih batch untuk diverifikasi dengan hasil uji proksimat</p>
            </div>
          </div>
          <div style="overflow-x:auto;">
            <table class="data-table" id="table-col-queue">
              <thead><tr><th>ID</th><th>Petani</th><th class="num">kg</th><th>Aksi</th></tr></thead>
              <tbody><tr><td colspan="4" style="text-align:center;">Memuat antrian...</td></tr></tbody>
            </table>
          </div>
        </div>

        <!-- Form Verifikasi Proksimat -->
        <div class="card">
          <div class="card-header">
            <div>
              <h3 class="card-title">🔬 Uji Mutu Proksimat Sekam</h3>
              <p class="card-sub" id="col-verify-target">Pilih sekam dari tabel antrian di samping</p>
            </div>
          </div>
          <form id="form-verify-harvest">
            <input type="hidden" id="v-harvest-id">
            <div style="margin-bottom:8px;"><label class="kpi-lbl">⚖️ Berat Timbangan Pengepul (kg) — dasar harga ke petani</label><input type="number" id="v-weight" class="btn btn-secondary" style="width:100%;" min="0.1" step="0.1" required></div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
              <div><label class="kpi-lbl">Kadar Air (% bb) — wajib</label><input type="number" id="v-moisture" class="btn btn-secondary" style="width:100%;" step="0.1" min="0" max="60" inputmode="decimal" placeholder="baca moisture meter" required></div>
              <div><label class="kpi-lbl">Kadar Abu (% bk)</label><input type="number" id="v-ash" class="btn btn-secondary" style="width:100%;" step="0.1" min="0" max="40" inputmode="decimal" placeholder="opsional · uji lab"></div>
              <div><label class="kpi-lbl">Volatile Matter (%)</label><input type="number" id="v-vm" class="btn btn-secondary" style="width:100%;" step="0.1" min="0" max="100" inputmode="decimal" placeholder="opsional · uji lab"></div>
              <div><label class="kpi-lbl">Fixed Carbon (%)</label><input type="number" id="v-fc" class="btn btn-secondary" style="width:100%;" step="0.1" min="0" max="100" inputmode="decimal" placeholder="opsional · uji lab"></div>
              <div><label class="kpi-lbl">Kontaminan (%)</label><input type="number" id="v-contam" class="btn btn-secondary" style="width:100%;" step="0.1" min="0" max="50" inputmode="decimal" placeholder="0 bila bersih"></div>
              <div><label class="kpi-lbl">Suhu Pirolisis (°C)</label><input type="number" id="v-temp" class="btn btn-secondary" style="width:100%;" value="500" step="10"></div>
            </div>
            <div style="margin-top:8px;"><label class="kpi-lbl">📷 URL Foto Bukti Serah-Terima (opsional)</label><input type="text" id="v-photo" class="btn btn-secondary" style="width:100%; text-align:left;" placeholder="https://... atau /uploads/..."></div>
            <div id="v-preview" style="background:var(--surface-2); border:1px solid var(--border); border-radius:var(--radius-md); padding:12px; margin:12px 0; font-size:var(--fs-xs);">
              Preview Mutu: <b>Grade A</b> · Skor 91.2 · Pengali Harga: <b>×1.10</b>
            </div>
            <button type="submit" class="btn btn-primary" style="width:100%;" id="btn-submit-verify" disabled>
              Verifikasi Mutu &amp; Terbitkan Harga ➔
            </button>
            <button type="button" class="btn btn-secondary" style="width:100%; margin-top:8px;" id="btn-reject-lot" disabled>
              ⛔ Tolak lot (sebutkan penyebab)
            </button>
          </form>
        </div>
      </div>
    `;
    $("form-verify-harvest").onsubmit = submitVerify;
    $("btn-reject-lot").onclick = () => window.rejectLot && window.rejectLot(Number($("v-harvest-id").value));
    container.insertAdjacentHTML("beforeend", PENGEPUL_MARKET_HTML);
    container.insertAdjacentHTML("beforeend", PENGEPUL_DR_HTML);
    loadCollectorData();
    loadMarket();
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

      <div class="card" style="padding:12px;margin-bottom:12px;" id="driver-actions"></div>

      <div class="grid-sidebar">
        <!-- Stops list -->
        <div class="card">
          <div class="card-header">
            <div>
              <h3 class="card-title">🚛 Titik Penjemputan Sekam</h3>
              <p class="card-sub">Scan QR petani di setiap penggilingan</p>
            </div>
          </div>
          <div id="driver-stops-list">Memuat daftar stop...</div>
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
        <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Output Biochar</div><div class="kpi-val" id="f-biochar">–</div><div class="kpi-lbl">Ton Biochar Terverifikasi</div></div>
        <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Potensi Biosilika SiO₂</div><div class="kpi-val" id="f-sio2">–</div><div class="kpi-lbl">Ton · estimasi dari kadar abu</div></div>
        <div class="kpi-tile kpi-purple"><div class="kpi-lbl">Status Sertifikasi</div><div class="kpi-val" style="font-size:var(--fs-lg);">Pra-verifikasi</div><div class="kpi-lbl">Belum terdaftar SRN-PPI · Perpres 110/2025</div></div>
      </div>

      ${renderAIEvaluationCard("pabrik")}

      <div class="grid-2">
        <!-- 30 Days Forecast Chart -->
        <div class="card">
          <div class="card-header">
            <div>
              <h3 class="card-title">📈 Proyeksi Pasokan Sekam 30 Hari</h3>
              <p class="card-sub">Model cosinus musiman panen Sleman &amp; Klaten (BPS)</p>
            </div>
          </div>
          <canvas id="factory-forecast-chart" height="150"></canvas>
        </div>

        <!-- ESG Carbon Calculator -->
        <div class="card">
          <div class="card-header">
            <div>
              <h3 class="card-title">🌿 Kalkulator Pengurangan Emisi Karbon</h3>
              <p class="card-sub">Metodologi IPCC 2006 Tier 2 untuk pirolisis biochar</p>
            </div>
          </div>
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
            <div><label class="kpi-lbl">Biomassa Sekam (ton)</label><input type="number" id="c-ton" class="btn btn-secondary" style="width:100%;" value="50"></div>
            <div><label class="kpi-lbl">Jarak Angkut (km)</label><input type="number" id="c-km" class="btn btn-secondary" style="width:100%;" value="45"></div>
          </div>
          <button class="btn btn-primary" style="width:100%; margin-top:12px;" data-onclick="calcCarbon()">Hitung Pengurangan CO₂ ➔</button>
          <div id="carbon-res-box" style="margin-top:12px;"></div>
        </div>
      </div>
    `;
    container.insertAdjacentHTML("beforeend", FACTORY_OPS_HTML);
    loadFactoryData();
    initFactoryOps();
    initAIEvaluationCard("pabrik");
    if (typeof renderFactoryExtras === "function") renderFactoryExtras(container);
  } else if (role === "auditor") {
    container.innerHTML = `
      <div class="kpi-row">
        <div class="kpi-tile"><div class="kpi-lbl">Timbangan Pengepul</div><div class="kpi-val" id="au-collector">0</div><div class="kpi-lbl">kg (sudah diterima pabrik)</div></div>
        <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Timbangan Pabrik</div><div class="kpi-val" id="au-factory">0</div><div class="kpi-lbl">kg</div></div>
        <div class="kpi-tile kpi-purple"><div class="kpi-lbl">Total Susut</div><div class="kpi-val" id="au-shrink">0</div><div class="kpi-lbl" id="au-shrink-pct">%</div></div>
        <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Biochar Kembali ke Petani</div><div class="kpi-val" id="au-biochar">0</div><div class="kpi-lbl">kg teralokasi</div></div>
      </div>

      ${renderAIEvaluationCard("auditor")}

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
        <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Penggilingan Padi</div><div class="kpi-val" id="a-tot-mills">–</div><div class="kpi-lbl">Sleman &amp; Klaten</div></div>
        <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Laporan Sekam</div><div class="kpi-val" id="a-tot-harvests">–</div><div class="kpi-lbl">Batch Transaksi</div></div>
        <div class="kpi-tile kpi-purple"><div class="kpi-lbl">Armada Logistik</div><div class="kpi-val" id="a-tot-routes">–</div><div class="kpi-lbl">Rute Penjemputan</div></div>
      </div>

      ${renderAIEvaluationCard("admin")}

      <div class="card">
        <div class="card-header">
          <div>
            <h3 class="card-title">⚙️ Kendali Platform &amp; Data Demo</h3>
            <p class="card-sub">Operasional sistem Bio-Chain v2</p>
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
    `;
    // KPI ringkas diisi dari data asli (dulu angka contoh statis di HTML)
    api("/api/v1/admin/stats").then(st => {
      [["a-tot-users", st.total_users], ["a-tot-mills", st.total_mills], ["a-tot-harvests", st.total_harvests], ["a-tot-routes", st.total_routes]]
        .forEach(([id, v]) => { if ($(id)) $(id).innerText = num(v, 0); });
    }).catch(err => console.error("admin stats:", err));
    initAIEvaluationCard("admin");
    if (typeof renderFactoryExtras === "function") renderFactoryExtras(container);
  }
}

// ==============================================================
// 4. PERSONA DATA LOADERS
// ==============================================================
function pendingPetaniRows() {
  return myOutbox("/api/v1/farmer/harvest").map(i => `
      <tr style="opacity:.75">
        <td>⏳</td>
        <td class="num"><b>${num(i.body.quantity_kg, 0)}</b></td>
        <td><span class="badge badge-amber">antre (offline)</span></td>
        <td>-</td><td>-</td>
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
    if (wallet && $("p-wallet")) $("p-wallet").innerText = num(wallet.balance_kg, 2);

    if ($("p-tot-harvest")) $("p-tot-harvest").innerText = inc.total_harvests;
    if ($("p-tot-ton")) $("p-tot-ton").innerText = num(inc.total_kg / 1000, 1);
    if ($("p-xp")) $("p-xp").innerText = inc.xp_total;
    if ($("p-tier-lbl")) $("p-tier-lbl").innerText = `Tier ${inc.tier.toUpperCase()}`;

    const tbody = tbodyEl;
    if (!harvests.length) {
      tbody.innerHTML = pendingPetaniRows()
        || `<tr><td colspan="5">${emptyState("🌾", "Belum ada laporan sekam", "Kirim laporan stok sekam pertama Anda lewat formulir di sebelah kiri.")}</td></tr>`;
      return;
    }

    const badgeClass = s => {
      if (s === "delivered" || s === "converted") return "badge-green";
      if (s === "rejected") return "badge-red";
      if (s === "verified") return "badge-blue";
      if (s === "collected") return "badge-purple";
      return "badge-amber";
    };

    tbody.innerHTML = pendingPetaniRows() + harvests.map(h => `
      <tr>
        <td>#${h.id}</td>
        <td class="num"><b>${num(h.quantity_kg, 0)}</b></td>
        <td><span class="badge ${badgeClass(h.status)}">${esc(h.status)}</span></td>
        <td>${h.grade ? `<b>${esc(h.grade)}</b>` : '-'}</td>
        <td>
          <button class="btn btn-secondary btn-sm" data-onclick="openModal('QR Setor Sekam #${h.id}', '${esc(h.qr_code)}', '${num(h.verified_kg || h.quantity_kg, 0)} kg Sekam')">
            QR 👁️
          </button>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("loadPetaniData:", err);
    if (err.network && tbodyEl) {
      tbodyEl.innerHTML = pendingPetaniRows()
        || `<tr><td colspan="5" style="text-align:center;">📵 Offline — data terakhir belum bisa dimuat.</td></tr>`;
    }
  }
}

// ==============================================================
// PASAR B2B — petani memasang stok (skema jemput/antar), pengepul menawar, petani memilih (boleh sebagian)
// ==============================================================
const PETANI_MARKET_HTML = `
  <div class="grid-2" style="margin-top:16px;">
    <div class="card">
      <div class="card-header"><div><h3 class="card-title">🏷️ Stok Lelang &amp; Tawaran Masuk</h3>
        <p class="card-sub">Pasang lelang dari kartu "Lapor &amp; Jual". “Nilai bersih” = harga − ongkos antar Anda.</p></div></div>
      <div id="my-listings"><p class="muted">Memuat…</p></div>
    </div>
    <div class="card" id="petani-biochar-card">
      <div class="card-header"><div><h3 class="card-title">♻️ Biochar untuk Sawah</h3>
        <p class="card-sub">Hak biochar dari sekam Anda. Ajukan pengambilan &amp; lihat perkiraan manfaatnya.</p></div></div>
      <div id="biochar-sawah"><p class="muted">Memuat…</p></div>
    </div>
  </div>`;

const SCHEME_LABEL = { jemput: "🚚 Jemput", antar: "🛵 Antar" };

async function loadMyListings() {
  try {
    const rows = await api("/api/v1/farmer/listings");
    $("my-listings").innerHTML = rows.length ? rows.map(l => `
      <div style="border:1px solid var(--border); border-radius:10px; padding:8px 12px; margin-bottom:8px;">
        <div style="display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap;">
          <b>#${l.id} · ${num(l.remaining_kg, 0)} / ${num(l.quantity_kg, 0)} kg</b>
          <span class="badge ${l.status === "closed" ? "badge-green" : l.status === "cancelled" ? "badge-gray" : "badge-amber"}">${esc(l.status)}</span>
        </div>
        <div class="kpi-lbl">${Object.entries(l.schemes).filter(([, v]) => v).map(([k, v]) => `${SCHEME_LABEL[k]} min ${rp(v)}/kg`).join(" · ")}</div>
        ${["open", "partially_awarded"].includes(l.status) ? `<button class="btn btn-secondary btn-sm" data-onclick="showBids(${Number(l.id)})">Lihat tawaran</button>
          <button class="btn btn-secondary btn-sm" data-onclick="cancelListing(${Number(l.id)})">Batalkan</button>` : ""}
        <div id="bids-${Number(l.id)}"></div>
      </div>`).join("") : emptyState("🏷️", "Belum ada stok dipasang", "Gunakan formulir di sebelah kiri untuk membuka lelang sekam baru.");
  } catch (err) { console.error("loadMyListings:", err); }
}

async function showBids(listingId) {
  const r = await api(`/api/v1/farmer/listings/${listingId}/bids`);
  const box = $(`bids-${listingId}`);
  const active = r.bids.filter(b => b.status === "active");
  box.innerHTML = active.length ? `<table class="data-table" style="margin-top:8px;"><thead><tr><th>Pengepul</th><th>Skema</th>
      <th class="num">Harga</th><th class="num">Nilai bersih</th><th class="num">kg</th><th>Terima</th></tr></thead><tbody>
    ${active.map(b => `<tr${b.highest_net ? ' style="background:var(--primary-soft)"' : ""}>
      <td>${esc(b.collector)}${b.highest_net ? ' <span class="badge badge-green">bersih tertinggi</span>' : ""}</td>
      <td>${SCHEME_LABEL[b.scheme] || esc(b.scheme)}</td><td class="num">${rp(b.price_per_kg)}</td>
      <td class="num"><b>${b.net_to_farmer_per_kg == null ? "-" : rp(b.net_to_farmer_per_kg)}</b>
        ${b.farmer_transport_cost_per_kg ? `<br><span class="kpi-lbl">ongkos antar ${rp(b.farmer_transport_cost_per_kg)}/kg</span>` : ""}</td>
      <td class="num">${num(b.quantity_kg, 0)}</td>
      <td><input type="number" id="acc-${Number(b.bid_id)}" class="btn btn-secondary" style="width:80px;" min="1"
            value="${Math.min(b.quantity_kg, r.listing.remaining_kg)}" max="${Math.min(b.quantity_kg, r.listing.remaining_kg)}">
          <button class="btn btn-primary btn-sm" data-onclick="acceptBid(${Number(listingId)}, ${Number(b.bid_id)}, this)">Pilih</button></td></tr>`).join("")}
    </tbody></table><p class="kpi-lbl">Anda bebas memilih tawaran mana pun dan boleh menerima sebagian.</p>`
    : `<div style="font-size:var(--fs-xs); color:var(--ink-muted); padding:8px 0; display:flex; align-items:center; gap:8px;">⏳ <span>Belum ada tawaran aktif dari pengepul untuk stok ini.</span></div>`;
}

async function acceptBid(listingId, bidId, btn) {
  const qty = Number($(`acc-${bidId}`).value);
  return withBusy(btn, async () => {
    try {
      const r = await api(`/api/v1/farmer/listings/${listingId}/accept`, { body: { bid_id: bidId, quantity_kg: qty } });
      showToast(`Disepakati ${num(r.accepted_kg, 0)} kg @${rp(r.price_per_kg)} (${r.scheme}). Nilai ${rp(r.contract_value_rp)}`, "🤝");
      openModal("Kontrak Lelang", r.qr_code, `${num(r.accepted_kg, 0)} kg · ${r.scheme} · tunjukkan QR saat serah-terima`);
      loadMyListings(); loadPetaniData();
    } catch (err) { showToast(err.message, "❌"); loadMyListings(); }
  });
}

async function cancelListing(listingId) {
  try { await api(`/api/v1/farmer/listings/${listingId}/cancel`, { method: "POST" }); loadMyListings(); }
  catch (err) { showToast(err.message, "❌"); }
}

const PENGEPUL_MARKET_HTML = `
  <div class="card" style="margin-top:16px;">
    <div class="card-header"><div>
      <h3 class="card-title">🛒 Pasar Stok Petani</h3>
      <p class="card-sub">Urut jarak dari gudang Anda. Saran tawaran = harga jual − biaya logistik marginal (rute CVRP) − margin.</p>
    </div>
    <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;"><label class="kpi-lbl" for="mk-resale">Harga jual ke pabrik (Rp/kg)</label>
      <input id="mk-resale" type="number" class="btn btn-secondary" style="width:100px;" value="560" inputmode="numeric">
      <span class="pct-stepper" role="group" aria-label="Margin pengepul">
        <label class="kpi-lbl" for="mk-margin">Margin</label>
        <button type="button" class="btn btn-secondary btn-sm" data-pct="-0.5" aria-label="Kurangi margin 0,5%">−</button>
        <input id="mk-margin" type="number" class="btn btn-secondary btn-sm" style="width:72px;" value="5" min="0" max="50" step="0.5" inputmode="decimal">
        <span class="kpi-lbl">%</span>
        <button type="button" class="btn btn-secondary btn-sm" data-pct="0.5" aria-label="Tambah margin 0,5%">+</button>
        <span class="kpi-lbl" id="mk-margin-rp"></span>
      </span>
      <button class="btn btn-primary btn-sm" data-onclick="planPickup(this)">🚛 Rencanakan jemput</button></div></div>
    <div id="pickup-plan-result"></div>
    <div style="overflow-x:auto; margin-top:8px;" id="market-table"><p class="muted">Memuat…</p></div>
  </div>`;

async function loadMarket() {
  try {
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
      : emptyState("🛒", "Belum ada stok terbuka", "Saat ini semua stok lelang sekam petani telah terserap atau belum ada lelang baru.");
  } catch (err) { console.error("loadMarket:", err); }
}

async function adviseBid(listingId, btn) {
  return withBusy(btn, async () => {
    try {
      const r = await api("/api/v1/collector/bid-advisor", { body: {
        listing_id: listingId, scheme: $(`bs-${listingId}`).value, resale_price_per_kg: Number($("mk-resale").value),
        margin_pct: Number($("mk-margin").value) || 0,
        quantity_kg: Number($(`bq-${listingId}`).value) || undefined } });
      $(`ba-${listingId}`).innerHTML = r.feasible
        ? `Logistik ${rp(r.logistic_cost_per_kg)}/kg · margin ${num(r.margin_pct, 1)}% (${rp(r.margin_per_kg)}/kg) · maks ${rp(r.max_bid_per_kg)} · saran <b>${rp(r.suggested_bid_per_kg)}</b>`
        : `⚠️ Tidak menguntungkan: maks ${rp(r.max_bid_per_kg)} &lt; minimum petani ${rp(r.farmer_reserve_per_kg)}`;
      if (r.suggested_bid_per_kg) $(`bp-${listingId}`).value = r.suggested_bid_per_kg;
    } catch (err) { showToast(err.message, "❌"); }
  }, "⏳");
}

async function placeBid(listingId, btn) {
  return withBusy(btn, async () => {
    try {
      await api("/api/v1/collector/bids", { body: { listing_id: listingId, scheme: $(`bs-${listingId}`).value,
        price_per_kg: Number($(`bp-${listingId}`).value), quantity_kg: Number($(`bq-${listingId}`).value) } });
      showToast("Tawaran terkirim. Petani yang memutuskan.", "📨");
      loadMarket();
    } catch (err) {
      showToast(err.message, "❌");
      loadMarket();
    }
  }, "⏳");
}

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
          <table class="data-table" style="margin-top:8px;">
            <thead><tr><th>Trip</th><th>Urutan Penjemputan Petani</th><th class="num">Muatan (m³)</th><th class="num">Ton</th><th class="num">Jarak</th></tr></thead>
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
        </div>`;
    } catch (err) { showToast(err.message, "❌"); }
  }, "⏳");
}

// ==============================================================
// PABRIK — Procurement B2B, QC masuk, batch manufaktur sirkular, pricing engine
// ==============================================================
const PRODUCT_NAMES = { bio_pellet: "Bio-pellet", biochar: "Biochar", bio_silika: "Bio-silika" };
const LOSS_NAMES = { air: "Air diuapkan", volatil_syngas: "Volatil / syngas", gas_pembakaran: "Gas pembakaran/kalsinasi",
                     bio_oil: "Bio-oil / tar (asap cair)",
                     residu_ekstraksi: "Residu ekstraksi", susut_proses: "Susut proses" };
const DR_STATUS = { submitted: "badge-amber", countered: "badge-blue", accepted: "badge-green", delivered: "badge-green",
                    rejected: "badge-red", cancelled: "badge-gray" };

const FACTORY_OPS_HTML = `
  <div class="grid-2" style="margin-top:16px;">
    <div class="card">
      <div class="card-header"><div><h3 class="card-title">🧮 Rekomendasi Harga Beli Sekam</h3>
        <p class="card-sub">Netback 3 produk − biaya variabel − biaya tetap − margin (angka dari menu Parameter)</p></div></div>
      <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:8px;">
        <div><label class="kpi-lbl">Kadar air (%)</label><input id="pr-m" type="number" class="btn btn-secondary" style="width:100%;" value="11" step="0.5"></div>
        <div><label class="kpi-lbl">Abu (% bk)</label><input id="pr-a" type="number" class="btn btn-secondary" style="width:100%;" value="18" step="0.5"></div>
        <div><label class="kpi-lbl">Kontaminan (%)</label><input id="pr-c" type="number" class="btn btn-secondary" style="width:100%;" value="0" step="0.5"></div>
        <div><label class="kpi-lbl">Harga bio-pellet (Rp/kg) *</label><input id="pr-pp" type="number" class="btn btn-secondary" style="width:100%;" min="0" placeholder="wajib"></div>
        <div><label class="kpi-lbl">Harga biochar (Rp/kg) *</label><input id="pr-pb" type="number" class="btn btn-secondary" style="width:100%;" min="0" placeholder="wajib"></div>
        <div><label class="kpi-lbl">Harga bio-silika (Rp/kg) *</label><input id="pr-ps" type="number" class="btn btn-secondary" style="width:100%;" min="0" placeholder="wajib"></div>
        <div style="grid-column:span 2;"><label class="kpi-lbl">Jalur bio-silika</label><select id="pr-route" class="btn btn-secondary" style="width:100%;">
          <option value="biochar">Silika dari biochar</option>
          <option value="abu_pembakaran">Silika dari abu pembakaran</option>
          <option value="sekam_langsung">Silika dari sekam langsung</option></select></div>
        <div><label class="kpi-lbl">Porsi sekam ke silika</label><input id="pr-xs" type="number" class="btn btn-secondary" style="width:100%;" min="0" max="1" step="0.05"></div>
      </div>
      <p class="kpi-lbl">* Harga jual tidak punya angka bawaan — isi harga kontrak/pasar aktual (tersimpan sebagai default di menu Parameter).</p>
      <button class="btn btn-primary" style="width:100%; margin-top:8px;" id="btn-price">Hitung Harga ➔</button>
      <div id="pr-result" style="margin-top:12px;"></div>
    </div>
    <div class="card">
      <div class="card-header"><div><h3 class="card-title">📥 Ajuan Pengiriman dari Pengepul</h3>
        <p class="card-sub">Terima / tawar balik jadwal & harga, lalu QC saat sekam tiba</p></div></div>
      <div id="dr-inbox" style="overflow-x:auto;"><p class="muted">Memuat…</p></div>
    </div>
  </div>
  <div class="card" style="margin-top:16px;">
    <div class="card-header"><div><h3 class="card-title">💳 Pembayaran ke Pengepul (jalur QC &amp; rute armada)</h3>
      <p class="card-sub">Sekam jalur rute ditimbang terima di sini → tagihan pengepul tercatat. Harga kosong = rekomendasi netback.</p></div>
      <select id="st-filter" class="btn btn-secondary btn-sm" aria-label="Filter status settlement"><option value="">Semua status</option>
        <option value="menunggu_harga">Menunggu harga</option><option value="terutang">Terutang</option><option value="dibayar">Dibayar</option></select></div>
    <h4 style="margin:4px 0;">🚛 Tiba via rute armada — menunggu timbang terima</h4>
    <div id="st-arrivals" style="overflow-x:auto;"><p class="muted">Memuat…</p></div>
    <h4 style="margin:12px 0 4px;">Tagihan pengepul</h4>
    <div id="st-list" style="overflow-x:auto;"><p class="muted">Memuat…</p></div>
  </div>
  <div class="card" style="margin-top:16px;">
    <div class="card-header"><div><h3 class="card-title">🏭 Batch Produksi Sirkular (1 input → 3 output + loss)</h3>
      <p class="card-sub">Pilih lot hasil QC, isi timbangan output & loss, biaya → mass balance & biaya per ton produk</p></div>
      <button class="btn btn-secondary btn-sm" id="btn-batch-model">Isi dari model</button></div>
    <div class="grid-2">
      <div>
        <label class="kpi-lbl">Kode batch</label><input id="bt-code" class="btn btn-secondary" style="width:100%; text-align:left;">
        <h4 style="margin:12px 0 4px;">Lot sekam (stok QC)</h4><div id="bt-lots"><p class="muted">Memuat…</p></div>
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
          <option value="sekam_langsung">Silika dari sekam langsung</option></select></div>
          <div><label class="kpi-lbl">Porsi sekam ke silika</label><input id="bt-xs" type="number" class="btn btn-secondary" style="width:100%;" min="0" max="1" step="0.05"></div>
        </div>
      </div>
      <div>
        <h4 style="margin:0 0 4px;">Output (kg)</h4>
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
      : `<p class="muted">Tidak ada sekam jalur rute yang menunggu timbang terima.</p>`;
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
      <table class="data-table" style="margin-top:8px;"><thead><tr><th>Produk</th><th class="num">kg/kg sekam</th><th class="num">Nilai Rp/kg sekam</th></tr></thead>
      <tbody>${Object.entries(r.yields_kg_per_kg).map(([k, v]) => `<tr><td>${PRODUCT_NAMES[k]}</td><td class="num">${num(v, 3)}</td>
        <td class="num">${rp(r.revenue_per_kg[k])}</td></tr>`).join("")}</tbody></table>
      <p class="kpi-lbl">Biaya variabel ${rp(Object.values(r.variable_cost_per_kg).reduce((a, b) => a + b, 0))}/kg · tetap ${rp(r.fixed_cost_per_kg)}/kg ·
        loss ${Object.entries(r.losses_kg_per_kg).map(([k, v]) => `${LOSS_NAMES[k]} ${num(v * 100, 1)}%`).join(", ")}</p>
      <p class="kpi-lbl">Sensitivitas kadar air → target: ${r.sensitivity_moisture.map(x => `${x.moisture}%: ${rp(x.target_per_kg)}`).join(" · ")}</p>
      <p class="kpi-lbl">Jalur silika: ${esc(r.silica_route)}${r.heat_recovered_mj_per_kg ? ` · panas tungku ${num(r.heat_recovered_mj_per_kg, 2)} MJ/kg sekam menutup biaya pengering` : ""}</p>`;
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
      : emptyState("📦", "Belum ada lot hasil QC", "Lakukan verifikasi QC pada sekam masuk untuk memunculkan lot siap batch.");
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
      <div class="card" style="background:var(--primary-soft); margin-top:8px;"><b>🌾 Dompet biochar petani:</b>
        ${num(e.wallet.allocated_kg, 2)} kg dikreditkan ke ${e.wallet.farmers.length} petani
        (porsi ${num(e.wallet.return_share * 100, 0)}% biochar)${e.wallet.untraceable_kg ? ` · ${num(e.wallet.untraceable_kg, 2)} kg dari sekam yang tidak tertelusur ke petani` : ""}
        <div class="kpi-lbl">${esc(e.wallet.method || "")}</div></div>`;
    showToast(`Batch ${b.batch_code} tersimpan.`, "🏭");
    $("bt-code").value = `B-${new Date().toISOString().slice(0, 10).replaceAll("-", "")}-${Math.floor(Math.random() * 900 + 100)}`;
    loadLots();
  } catch (err) { showToast(err.message, "❌"); }
}

// ---------- Pengepul: ajukan pengiriman ke pabrik & jawab tawaran balik
const PENGEPUL_DR_HTML = `
  <div class="card" style="margin-top:16px;">
    <div class="card-header"><div><h3 class="card-title">🚚 Ajukan Pengiriman ke Pabrik</h3>
      <p class="card-sub">Harga rekomendasi pabrik dihitung dari kadar air — pabrik dapat menerima atau menawar balik</p></div></div>
    <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:8px;">
      <div><label class="kpi-lbl">Jumlah (kg)</label><input id="dr-qty" type="number" class="btn btn-secondary" style="width:100%;" value="5000" min="1"></div>
      <div><label class="kpi-lbl">Kadar air (%)</label><input id="dr-m" type="number" class="btn btn-secondary" style="width:100%;" value="11" step="0.5"></div>
      <div><label class="kpi-lbl">Tanggal kirim</label><input id="dr-date" type="date" class="btn btn-secondary" style="width:100%;"></div>
      <div><label class="kpi-lbl">Harga diajukan (Rp/kg)</label><input id="dr-price" type="number" class="btn btn-secondary" style="width:100%;"></div>
    </div>
    <p class="kpi-lbl" id="dr-reco"></p>
    <details style="margin:8px 0;"><summary class="kpi-lbl" style="cursor:pointer;">🌾 Lampirkan sekam petani (agar biochar masuk ke dompet mereka)</summary>
      <div id="dr-harvests" style="margin-top:8px;"></div></details>
    <button class="btn btn-primary" id="btn-dr">Ajukan ➔</button>
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
  $("btn-dr").onclick = e => withBusy(e.currentTarget, async () => {
    try {
      const harvest_ids = [...document.querySelectorAll(".dr-h:checked")].map(c => Number(c.value));
      await api("/api/v1/collector/delivery-requests", { body: { quantity_kg: Number($("dr-qty").value),
        moisture_est: Number($("dr-m").value), proposed_date: $("dr-date").value, proposed_price_per_kg: Number($("dr-price").value),
        harvest_ids } });
      showToast(`Ajuan terkirim ke pabrik${harvest_ids.length ? ` dengan ${harvest_ids.length} lot petani` : ""}.`, "📨");
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
      : `<p class="muted">Tidak ada sekam petani terverifikasi yang belum dikirim.</p>`;
  } catch (err) { console.error("loadAttachable:", err); }
}

async function loadMyDR() {
  try {
    const rows = await api("/api/v1/collector/delivery-requests");
    $("dr-mine").innerHTML = rows.length ? `<table class="data-table"><thead><tr><th>#</th><th class="num">kg</th><th>Tawaran di meja</th><th>Status</th><th>Aksi</th></tr></thead>
      <tbody>${rows.map(r => `<tr><td>${r.id}</td><td class="num">${num(r.quantity_kg, 0)}</td>
        <td>${rp((r.agreed || r.current_offer).price_per_kg)}/kg · ${esc((r.agreed || r.current_offer).date)}</td>
        <td><span class="badge ${DR_STATUS[r.status] || ""}">${esc(r.status)}</span>${r.pending_party ? `<br><span class="kpi-lbl">menunggu ${esc(r.pending_party)}</span>` : ""}</td>
        <td style="white-space:nowrap;">${r.pending_party === "pengepul" ? `
          <button class="btn btn-primary btn-sm" data-onclick="myDrRespond(${Number(r.id)}, 'accept', this)">Setuju</button>
          <input id="mdp-${r.id}" type="number" class="btn btn-secondary btn-sm" style="width:70px;" placeholder="Rp/kg">
          <button class="btn btn-secondary btn-sm" data-onclick="myDrRespond(${Number(r.id)}, 'counter', this, '${esc(r.current_offer.date)}')">Tawar</button>
          <button class="btn btn-secondary btn-sm" data-onclick="myDrRespond(${Number(r.id)}, 'reject', this)">Tolak</button>` :
          ["submitted", "countered"].includes(r.status) ? `<button class="btn btn-secondary btn-sm" data-onclick="myDrRespond(${Number(r.id)}, 'cancel', this)">Batalkan</button>` : ""}
        </td></tr>`).join("")}</tbody></table>` : "";
  } catch (err) { console.error("loadMyDR:", err); }
}

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
    const list = await api("/api/v1/collector/available-harvests");
    if ($("col-pending")) $("col-pending").innerText = list.length;
    // Ringkasan hari ini dari server (dulu angka contoh statis); belum ada verifikasi = "–", bukan 0 palsu
    api("/api/v1/collector/daily-summary").then(d => {
      if ($("col-verified-kg")) $("col-verified-kg").innerText = num(d.total_kg, 0);
      if ($("col-avg-score")) $("col-avg-score").innerText = d.total_pickups ? num(d.avg_quality_score, 1) : "–";
    }).catch(err => console.error("daily-summary:", err));

    const tbody = $("table-col-queue").querySelector("tbody");
    if (!list.length) {
      tbody.innerHTML = `<tr><td colspan="4">${emptyState("📦", "Tidak ada antrian sekam", "Semua laporan sekam petani telah diverifikasi atau belum ada laporan baru.")}</td></tr>`;
      return;
    }

    const queued = new Set(myOutbox("/api/v1/collector/verify").map(i => i.body.harvest_id));
    STATE.colQueue = Object.fromEntries(list.map(i => [i.id, i]));
    tbody.innerHTML = list.map(item => `
      <tr>
        <td>#${item.id}</td>
        <td><b>${esc(item.farmer_name || 'Petani')}</b><br><span style="font-size:var(--fs-xs); color:var(--ink-muted);">${esc(item.kecamatan || '-')}</span></td>
        <td class="num">${num(item.quantity_kg, 0)}</td>
        <td>
          ${queued.has(item.id) ? '<span class="badge badge-amber">antre (offline)</span>' : ''}
          <button type="button" class="btn btn-secondary btn-sm btn-wa" data-fo-contact="${Number(item.id)}" aria-label="Chat WhatsApp petani lot #${Number(item.id)}">${item.farmer_without_phone ? "👵 Tanpa HP" : "💬 WA"}</button>
          ${item.is_auction ? (item.dp ? `<span class="badge badge-blue" title="${esc(item.dp.receipt_code)}">DP ${rp(item.dp.amount_rp)}</span>`
            : `<button type="button" class="btn btn-secondary btn-sm" data-fo-dp="${Number(item.id)}" data-amount="${Math.round((item.agreed_price_per_kg || 0) * item.quantity_kg)}"
                 data-name="${esc(item.farmer_name || "Petani")}" title="Uang muka mengikat hasil lelang; dipotong saat pelunasan">🤝 DP</button>`) : ""}
          <button class="btn btn-primary btn-sm" data-onclick="selectVerifyItem(${Number(item.id)})">
            Uji 🔬
          </button>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("loadCollectorData:", err);
  }
}

function selectVerifyItem(id) {
  const item = (STATE.colQueue || {})[id] || {};
  $("v-harvest-id").value = id;
  $("v-weight").value = item.quantity_kg || "";
  const est = [item.farmer_moisture_est != null ? `air ±${num(item.farmer_moisture_est)}%` : "", item.farmer_grade_est ? `grade ${item.farmer_grade_est}` : ""]
    .filter(Boolean).join(", ");
  $("col-verify-target").innerText = `Memverifikasi Sekam #${id} dari ${item.farmer_name || "Petani"} (estimasi petani ${num(item.quantity_kg,0)} kg${est ? ` · ${est}` : ""})`;
  $("btn-submit-verify").disabled = false;
  $("btn-reject-lot").disabled = false;
  $("btn-submit-verify").innerText = `Verifikasi Mutu #${id} ➔`;
}

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
    }, `Verifikasi sekam #${id}`);
    showToast(res.queued ? "Offline: hasil uji disimpan & dikirim otomatis saat online." : res.message,
              res.queued ? "📵" : "✅");
    // Serah-terima: tampilkan resi bulanan unik (TRX-<pengirim>-<penerima>-<YYMM>-<urut>) untuk ditunjukkan ke petani
    if (!res.queued && res.verification_code) {
      openModal("Resi Serah-Terima Sekam", res.verification_code,
                `${num(res.weighed_kg, 0)} kg · Grade ${res.grade} · ${rp(res.total_price)} — tunjukkan/foto resi ini bersama petani`);
    }
    loadCollectorData();
    $("v-harvest-id").value = "";
    $("col-verify-target").innerText = `Pilih sekam dari tabel antrian di samping`;
  } catch (err) {
    showToast(err.message, "❌");
  } }).finally(() => { if (!$("v-harvest-id").value) $("btn-submit-verify").disabled = true; });
}

let driverMap, driverLayer;
const FAIL_REASONS = [["stok_tidak_ada", "Sekam tidak ada / sudah dijual"], ["dibatalkan_pengepul", "Dibatalkan pengepul"],
  ["mutu_buruk", "Basah / berjamur"], ["akses_jalan", "Jalan tidak bisa dilalui"],
  ["penggilingan_tutup", "Penggilingan tutup"], ["truk_penuh", "Bak truk penuh"], ["lainnya", "Lainnya"]];
const STOP_BADGE = { picked_up: ["badge-green", "DIJEMPUT"], failed: ["badge-red", "GAGAL"],
                     cancelled: ["badge-gray", "DIBATALKAN"] };

async function loadDriverData() {
  let route;
  try {
    route = await api("/api/v1/driver/active-route");
    try { localStorage.setItem("biochain_driver_route", JSON.stringify(route)); } catch {}
  } catch (err) {
    // Tanpa sinyal: tampilkan rute terakhir yang tersimpan agar supir tetap bisa bekerja
    try { route = JSON.parse(localStorage.getItem("biochain_driver_route") || "null"); } catch { route = null; }
    if (!route) { $("driver-stops-list").innerHTML = `<p class="muted">Offline dan belum ada rute tersimpan.</p>`; return; }
    showToast("Offline: menampilkan rute tersimpan terakhir", "📵");
  }
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
            <strong>Stop #${s.order}: ${esc(s.mill ? s.mill.name : `Penggilingan #${s.mill_id}`)}</strong>
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
        }).addTo(driverLayer).bindPopup(`<b>Stop #${s.order}: ${esc(s.mill.name)}</b><br>${s.planned_ton} Ton Sekam`);
      }
    });
    if (waypoints.length > 1) {
      L.polyline(waypoints, { color: "#2563eb", weight: 4, dashArray: "5, 10" }).addTo(driverLayer);
      driverMap.fitBounds(waypoints, { padding: [30, 30] });
    }
  }, 100);
}

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

async function confirmPickupStop(stopId, btn) {
  startCameraScanner((scannedCode) => {
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
      if (ctx) {
        if (factoryChart) factoryChart.destroy();
        factoryChart = new Chart(ctx, {
          type: "line",
          data: {
            labels,
            datasets: [{
              label: "Prediksi Pasokan Sekam (Ton/Hari)",
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
            scales: { y: { title: { display: true, text: "Ton Sekam" } } },
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
        <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Total Penggilingan</div><div class="kpi-val">${stats.total_mills}</div><div class="kpi-lbl">Titik Pemasok</div></div>
        <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Total Laporan Panen</div><div class="kpi-val">${stats.total_harvests}</div><div class="kpi-lbl">Transaksi Sekam</div></div>
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

// ==============================================================
// 5. ENGINE LAB STANDALONE LOGIC
// ==============================================================
function switchEngineSub(subId) {
  document.querySelectorAll(".eng-sub").forEach(e => e.style.display = "none");
  const el = $(subId);
  if (el) el.style.display = "block";
  if (subId === "eng-route") setTimeout(() => map && map.invalidateSize(), 60);
  if (["eng-feedstock", "eng-waste"].includes(subId)) initBiomassForms();
  if (subId === "eng-energy") initEnergy();
}

// ---------- ⑧ & ⑨: preset biomassa (nilai tipikal literatur)
let biomassPresets = null;
async function initBiomassForms() {
  if (biomassPresets && STATE.presetsVersion === JSON.stringify(PV("biomassa.presets"))) return;
  STATE.presetsVersion = JSON.stringify(PV("biomassa.presets"));
  biomassPresets = await api("/api/v1/labs/biomass/presets");
  const dry = new Set(["sekam_padi", "tongkol_jagung", "tempurung_kelapa", "serbuk_gergaji"]);
  $("fs-list").innerHTML = biomassPresets.map(p => `
    <label style="display:flex; gap:8px; align-items:center; font-size:var(--fs-xs); margin:4px 0;">
      <input type="checkbox" class="fs-check" value="${esc(p.id)}" ${dry.has(p.id) ? "checked" : ""}>
      <span style="flex:1;">${esc(p.name)} <span class="muted">(air ${p.moisture}%, abu ${p.ash}%)</span></span>
      <input type="number" class="btn btn-secondary fs-cost" data-id="${esc(p.id)}" value="${Number(p.price_rp_per_ton) || 0}" style="width:110px;" min="0" step="10000">
    </label>`).join("");
  $("we-preset").innerHTML = biomassPresets.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("");
}

async function runFeedstock() {
  const ids = [...document.querySelectorAll(".fs-check:checked")].map(c => c.value);
  if (ids.length < 2) return showToast("Pilih minimal dua feedstock.", "⚠️");
  const cost = id => Number(document.querySelector(`.fs-cost[data-id="${id}"]`).value) || 0;
  const r = await api("/api/v1/labs/feedstock/compare", { body: {
    purpose: $("fs-purpose").value, feedstocks: ids.map(id => ({ id, preset: id, cost_per_ton: cost(id), stock_ton: 50 })) } });
  $("fs-result").innerHTML = `
    <div class="card" style="background:var(--primary-soft); margin-bottom:12px;"><b>Rekomendasi:</b> ${esc(r.recommendation)}</div>
    <div style="overflow-x:auto;"><table class="data-table"><thead><tr><th>#</th><th>Feedstock</th><th class="num">HHV bk</th>
      <th class="num">LHV diterima</th><th class="num">Rendemen biochar</th><th class="num">Rp/GJ</th><th class="num">Rp/t biochar</th><th class="num">Skor</th></tr></thead>
    <tbody>${r.ranking.map(x => `<tr><td>${x.rank}</td><td><b>${esc(x.name)}</b><br><span class="muted" style="font-size:var(--fs-xs);">
      ${x.strengths.length ? "＋ " + esc(x.strengths.join(", ")) : ""} ${x.weaknesses.length ? "− " + esc(x.weaknesses.join(", ")) : ""}</span></td>
      <td class="num">${num(x.hhv_db_mj_kg, 1)}</td><td class="num">${num(x.lhv_ar_mj_kg, 1)}</td><td class="num">${num(x.biochar_yield_pct_db, 1)}%</td>
      <td class="num">${rp(x.cost_per_gj)}</td><td class="num">${rp(x.cost_per_ton_biochar)}</td><td class="num"><b>${num(x.topsis_score, 2)}</b></td></tr>`).join("")}</tbody></table></div>
    ${r.warnings.length ? `<ul style="font-size:var(--fs-xs); color:var(--warning);">${r.warnings.map(w => `<li>${esc(w)}</li>`).join("")}</ul>` : ""}
    <p class="kpi-lbl">MJ/kg · Metode: ${esc(r.computation_details.formulas.TOPSIS)}; HHV ${esc(r.computation_details.formulas.HHV_db)}</p>`;
}

async function runWaste() {
  const val = id => $(id).value === "" ? undefined : Number($(id).value);
  const r = await api("/api/v1/labs/waste-energy/advise", { body: {
    preset: $("we-preset").value, ton_per_day: Number($("we-tpd").value), operating_days: Number($("we-days").value),
    moisture: val("we-m"), ash: val("we-ash"), cn_ratio: val("we-cn") } });
  const c = r.characteristics, e = r.energy_potential;
  const outputs = o => Object.entries(o).map(([k, v]) => `${esc(k.replaceAll("_", " "))}: <b>${num(v, 0)}</b>`).join("<br>");
  $("we-result").innerHTML = `
    <div class="kpi-row">
      <div class="kpi-tile"><div class="kpi-lbl">Limbah</div><div class="kpi-val">${num(c.ton_per_tahun, 0)}</div><div class="kpi-lbl">ton/tahun · air ${num(c.kadar_air_pct)}%</div></div>
      <div class="kpi-tile kpi-amber"><div class="kpi-lbl">LHV diterima</div><div class="kpi-val">${num(c.lhv_diterima_mj_kg, 1)}</div><div class="kpi-lbl">MJ/kg (HHV bk ${num(c.hhv_bk_mj_kg, 1)})</div></div>
      <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Energi primer</div><div class="kpi-val">${num(e.energi_primer_gj_per_tahun, 0)}</div><div class="kpi-lbl">GJ/tahun ≈ ${num(e.setara_listrik_mwh_teoritis, 0)} MWh</div></div>
    </div>
    <div class="card" style="background:var(--primary-soft); margin:12px 0;"><b>Rekomendasi:</b> ${esc(r.recommendation)}</div>
    <table class="data-table"><thead><tr><th>Teknologi</th><th class="num">Skor</th><th>Keluaran / tahun</th><th>Catatan</th></tr></thead>
    <tbody>${r.technologies.map(t => `<tr style="${t.feasible ? "" : "opacity:.55"}"><td><b>${esc(t.technology)}</b></td>
      <td class="num">${num(t.score, 0)}</td><td style="font-size:var(--fs-xs);">${outputs(t.outputs)}</td>
      <td style="font-size:var(--fs-xs);">${esc(t.notes.join("; ")) || "—"}</td></tr>`).join("")}</tbody></table>`;
}

// ---------- ⑩ Energi dari histori database
let energyChart;
async function initEnergy() {
  if ($("en-facility").options.length) return;
  const fac = await api("/api/v1/factory/energy/facilities");
  $("en-facility").innerHTML = fac.map(f => `<option value="${esc(f.facility)}">${esc(f.facility)} (${f.months} bln)</option>`).join("");
  if (fac.length) runEnergy();
}

async function runEnergy() {
  const f = $("en-facility").value;
  const r = await api(`/api/v1/factory/energy/analysis?facility=${encodeURIComponent(f)}`);
  const s = r.summary, b = r.baseline;
  $("en-source").textContent = `Sumber: tabel ${r.data_source.table}, ${r.data_source.rows} bulan` +
    (r.data_source.demo_rows ? ` (${r.data_source.demo_rows} baris DEMO)` : "");
  $("en-kpis").innerHTML = `
    <div class="kpi-tile"><div class="kpi-lbl">IKE gedung (12 bln)</div><div class="kpi-val">${num(s.ike_kwh_m2_month_avg_12m, 1)}</div><div class="kpi-lbl">kWh/m²/bln · <b>${esc(s.ike_category)}</b></div></div>
    <div class="kpi-tile kpi-blue"><div class="kpi-lbl">SEC proses</div><div class="kpi-val">${num(s.sec_kwh_per_ton_avg, 0)}</div><div class="kpi-lbl">kWh/ton sekam</div></div>
    <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Bulan anomali</div><div class="kpi-val">${s.anomaly_months}</div><div class="kpi-lbl">pemborosan ${num(s.waste_kwh, 0)} kWh</div></div>
    <div class="kpi-tile kpi-purple"><div class="kpi-lbl">Biaya pemborosan</div><div class="kpi-val">${rp(s.waste_rp)}</div><div class="kpi-lbl">baseline R² ${num(b.r2, 2)} · beban dasar ${num(b.base_load_kwh_per_month, 0)} kWh</div></div>`;
  if (typeof Chart !== "undefined") {
    if (energyChart) energyChart.destroy();
    energyChart = new Chart($("en-chart"), { type: "line", data: {
      labels: r.series.map(p => p.period),
      datasets: [
        { label: "kWh aktual", data: r.series.map(p => p.kwh), borderColor: "#15803d", tension: 0.2,
          pointRadius: r.series.map(p => p.is_anomaly ? 6 : 2), pointBackgroundColor: r.series.map(p => p.is_anomaly ? "#dc2626" : "#15803d") },
        { label: "Baseline (ISO 50006)", data: r.series.map(p => p.expected_kwh), borderColor: "#64748b", borderDash: [6, 4], pointRadius: 0 },
      ] }, options: { responsive: true, plugins: { legend: { position: "bottom" } } } });
  }
  $("en-anom").innerHTML = r.anomalies.length ? `<table class="data-table"><thead><tr><th>Periode</th><th class="num">Kelebihan kWh</th><th class="num">Rp</th><th class="num">z</th><th>Catatan</th></tr></thead>
    <tbody>${r.anomalies.map(a => `<tr><td>${esc(a.period)}</td><td class="num">${num(a.excess_kwh, 0)}</td><td class="num">${rp(a.excess_rp)}</td>
      <td class="num">${num(a.robust_z, 1)}</td><td style="font-size:var(--fs-xs);">${esc(r.data_source.notes[a.period] || a.type || "")}</td></tr>`).join("")}</tbody></table>`
    : `<p class="muted">Tidak ada anomali signifikan.</p>`;
  $("en-recs").innerHTML = r.recommendations.map(x => `<div style="margin-bottom:8px; font-size:var(--fs-sm);"><b>${esc(x.title)}</b>
    ${x.potential_kwh_per_year ? `<span class="badge badge-green">±${num(x.potential_kwh_per_year, 0)} kWh/thn</span>` : ""}<br>${esc(x.detail)}</div>`).join("");
}

$("btn-run-feedstock") && ($("btn-run-feedstock").onclick = e => withBusy(e.currentTarget, () => runFeedstock().catch(err => showToast(err.message, "❌"))));
$("btn-run-waste") && ($("btn-run-waste").onclick = e => withBusy(e.currentTarget, () => runWaste().catch(err => showToast(err.message, "❌"))));
$("btn-run-energy") && ($("btn-run-energy").onclick = e => withBusy(e.currentTarget, () => runEnergy().catch(err => showToast(err.message, "❌"))));

let qChart;
async function runQuality() {
  const body = {
    moisture: +$("q-moisture").value,
    contamination: +$("q-contam").value,
    ash: +$("q-ash").value,
    volatile_matter: +$("q-vm").value,
    fixed_carbon: +$("q-fc").value,
    pyrolysis_temp_c: +$("q-temp").value,
  };
  try {
    const [r, curve] = await Promise.all([
      api("/api/v1/labs/quality/score", { body }),
      api(`/api/v1/labs/quality/yield-curve?ash=${body.ash}`),
    ]);

    $("q-result-box").innerHTML = `
      <div style="background:var(--primary-soft); border:1px solid var(--primary-border); border-radius:var(--radius-md); padding:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <div><strong style="font-size:18px;">Grade ${r.grade}</strong> (Skor: ${num(r.score)}/100)</div>
          <span class="badge badge-green">Pengali: ×${r.price_multiplier.toFixed(2)}</span>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:var(--fs-xs);">
          <div>Rendemen Biochar: <b>${num(r.pred_biochar_yield_pct_db)}%</b></div>
          <div>Biochar per Ton: <b>${num(r.biochar_kg_per_ton_received,0)} kg</b></div>
          <div>Estimasi SiO₂: <b>${num(r.pred_sio2_in_biochar_pct)}%</b></div>
          <div>Biosilika per Ton: <b>${num(r.sio2_kg_per_ton_received,0)} kg</b></div>
        </div>
      </div>
    `;

    const data = {
      labels: curve.map(p => p.temp_c + "°C"),
      datasets: [{
        label: "Rendemen biochar (%)",
        data: curve.map(p => p.yield_pct),
        borderColor: "#15803d",
        backgroundColor: "rgba(22, 163, 74, 0.15)",
        fill: true,
        tension: 0.3,
        pointRadius: curve.map(p => p.temp_c === Math.round(body.pyrolysis_temp_c/25)*25 ? 6 : 0),
      }],
    };

    if (qChart) {
      qChart.data = data;
      qChart.update();
    } else {
      qChart = new Chart($("q-chart"), {
        type: "line",
        data,
        options: { plugins: { legend: { display: false } }, scales: { y: { title: { display: true, text: "% bk" } } } },
      });
    }
  } catch (err) {
    $("q-result-box").innerHTML = `<div class="badge" style="background:var(--danger-soft); color:var(--danger);">${esc(err.message)}</div>`;
  }
}
$("btn-run-quality") && ($("btn-run-quality").onclick = runQuality);

let blendDefaults;
async function initBlend() {
  if (blendDefaults) return;
  blendDefaults = await api("/api/v1/labs/blend/defaults");
  $("b-product").innerHTML = Object.entries(blendDefaults.products).map(([k,v]) => `<option value="${k}">${v.label}</option>`).join("");
  $("b-product").onchange = fillBlendSpec;
  fillBlendSpec();

  $("b-table").querySelector("tbody").innerHTML = blendDefaults.feedstocks.map(f => `
    <tr data-id="${esc(f.id)}" data-name="${esc(f.name)}">
      <td><b>${esc(f.name)}</b></td>
      <td class="num">${rp(f.cost_per_ton)}</td>
      <td class="num">${f.stock_ton} t</td>
      <td class="num">${f.moisture}%</td>
      <td class="num">${f.ash}%</td>
      <td class="num">${f.fixed_carbon}%</td>
    </tr>
  `).join("");
}

function fillBlendSpec() {
  if (!blendDefaults) return;
  const p = blendDefaults.products[$("b-product").value];
  if (!p) return;
  const s = p.spec;
  $("b-mmax").value = s.moisture_max ?? "";
  $("b-amax").value = s.ash_max ?? "";
  $("b-fcmin").value = s.fixed_carbon_min ?? "";
}

async function runBlend() {
  if (!blendDefaults) await initBlend();
  const opt = v => v === "" ? null : +v;
  const body = {
    feedstocks: blendDefaults.feedstocks,
    target_ton: +$("b-target").value,
    pyrolysis_temp_c: 500,
    spec: {
      moisture_max: opt($("b-mmax").value),
      ash_max: opt($("b-amax").value),
      fixed_carbon_min: opt($("b-fcmin").value),
    },
  };
  try {
    const r = await api("/api/v1/labs/blend/recommend", { body });
    if (!r.feasible) {
      $("b-result-box").innerHTML = `<div style="background:var(--danger-soft); color:var(--danger); padding:12px; border-radius:8px;">${esc(r.message)}</div>`;
      return;
    }
    $("b-result-box").innerHTML = `
      <div style="background:var(--primary-soft); border:1px solid var(--primary-border); border-radius:var(--radius-md); padding:12px; font-size:var(--fs-sm);">
        <div style="font-size:16px; font-weight:800; color:var(--primary-dark); margin-bottom:4px;">
          Biaya Campuran: ${rp(r.cost_per_ton)} / ton
        </div>
        <div>Output Biochar: <b>${num(r.pred_biochar_output_ton)} Ton</b> · Potensi SiO₂: <b>${num(r.pred_sio2_ton)} Ton</b></div>
        <div style="margin-top:8px;">Komposisi: ${r.composition.map(c => `<b>${c.name}</b> (${num(c.share_pct)}%)`).join(", ")}</div>
      </div>
    `;
  } catch (err) {
    showToast(err.message, "❌");
  }
}
$("btn-run-blend") && ($("btn-run-blend").onclick = runBlend);

let map, routeLayer;
const COLORS = ["#15803d","#b45309","#1d4ed8","#b91c1c","#047857","#7c3aed","#0f766e"];
async function initRoute() {
  if (map) return;
  map = L.map("map").setView([-7.71, 110.46], 11);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OSM" }).addTo(map);
  routeLayer = L.layerGroup().addTo(map);

  const { depot, mills } = await api("/api/v1/labs/supply/mills");
  L.marker([depot.lat, depot.lon]).addTo(map).bindPopup(`<b>🏭 ${esc(depot.name)}</b>`);
  mills.forEach(m => {
    L.circleMarker([m.lat, m.lon], { radius: 5 + m.stock_ton * 2, color: "#166534", fillColor: "#86efac", fillOpacity: 0.85 })
      .addTo(map).bindPopup(`<b>${esc(m.name)}</b><br>Stok: ${esc(m.stock_ton)} t · Grade ${esc(m.grade)}`);
  });
}

async function runRoute() {
  const body = {
    vehicle_m3: +$("r-m3").value,
    bulk_density_kg_m3: +$("r-dens").value,
    cost_per_km: +$("r-cost").value,
  };
  const progress = msg => {
    $("r-kpis").innerHTML = `<div class="kpi-tile"><div class="kpi-lbl">Optimasi rute</div>
      <div class="kpi-val">⏳</div><div class="kpi-lbl" aria-live="polite">${esc(msg)}</div></div>`;
  };
  try {
    const r = await runJob("/api/v1/jobs/routes/optimize", body, progress);
    const s = r.summary;
    $("r-kpis").innerHTML = `
      <div class="kpi-tile"><div class="kpi-lbl">Penghematan Jarak</div><div class="kpi-val">${num(s.saving_pct)}%</div><div class="kpi-lbl">vs jemput satu per satu</div></div>
      <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Total Jarak</div><div class="kpi-val">${num(s.total_km)} km</div><div class="kpi-lbl">baseline ${num(s.baseline_km)} km</div></div>
      <div class="kpi-tile kpi-amber"><div class="kpi-lbl">Biaya per Ton</div><div class="kpi-val">${rp(s.cost_per_ton)}</div><div class="kpi-lbl">${s.vehicles_trips} trip logistik</div></div>
    `;

    routeLayer.clearLayers();
    r.routes.forEach((rt, i) => {
      L.polyline(rt.path, { color: COLORS[i % COLORS.length], weight: 4, opacity: 0.85 }).addTo(routeLayer)
        .bindPopup(`<b>Trip ${i+1}</b><br>${rt.km} km · ${rt.load_ton} Ton · Utilisasi: ${num(rt.utilization_pct)}%`);
    });

    $("r-route-list").innerHTML = `
      <table class="data-table"><thead><tr><th>Trip</th><th class="num">Titik</th><th class="num">km</th><th class="num">Isi</th></tr></thead>
      <tbody>${r.routes.map((rt,i) => `
        <tr><td><span style="color:${COLORS[i % COLORS.length]}">■</span> Trip ${i+1}</td><td class="num">${rt.stops.length}</td><td class="num">${num(rt.km)}</td><td class="num">${num(rt.utilization_pct,0)}%</td></tr>
      `).join("")}</tbody></table>
    `;
  } catch (err) {
    showToast(err.message, "❌");
  }
}
$("btn-run-route") && ($("btn-run-route").onclick = e => withBusy(e.currentTarget, runRoute, "⏳ Menghitung…"));

// Job asinkron: server membalas 202 + job_id seketika; UI memantau status dengan backoff
// sehingga layar tetap bisa dipakai selama perhitungan berat berjalan di worker.
async function runJob(path, body, onStatus) {
  const job = await api(path, { body });
  const started = Date.now();
  let delay = 250;
  onStatus("Dalam antrean…");
  for (;;) {
    await new Promise(res => setTimeout(res, delay));
    const st = await api(`/api/v1/jobs/${job.job_id}`);
    if (st.status === "done") return st.result;
    if (st.status === "failed") throw new Error(st.error || "Perhitungan gagal");
    const secs = ((Date.now() - started) / 1000).toFixed(1);
    onStatus(st.status === "running" ? `Proses sedang berjalan… ${secs} s` : `Dalam antrean… ${secs} s`);
    if (Date.now() - started > 120000) throw new Error("Perhitungan terlalu lama; coba lagi.");
    delay = Math.min(delay * 1.5, 2000);
  }
}

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
