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
      <div class="card-header"><div><h3 class="card-title" id="fx-br-title">♻️ Serah-terima Biochar ke Petani</h3>
        <p class="card-sub">Pengajuan petani untuk sawah. Dompet petani baru berkurang saat karung diserahkan.</p></div></div>
      <div id="fx-br"><p class="muted">Memuat…</p></div></section>` : ""}

    <section class="card" aria-labelledby="fx-ch-title">
      <div class="card-header"><div><h3 class="card-title" id="fx-ch-title">🚚 Potongan Logistik Pengepul</h3>
        <p class="card-sub">Ongkos jarak kosong (batal saat truk di jalan / stok tidak ada). Dipotong otomatis saat tagihan pengepul ditandai lunas.</p></div></div>
      <div id="fx-ch"><p class="muted">Memuat…</p></div></section>

    <section class="card" aria-labelledby="fx-eff-title">
      <div class="card-header"><div><h3 class="card-title" id="fx-eff-title">💡 Optimasi &amp; Penghematan Rantai Pasok</h3>
        <p class="card-sub">Per proses: penghematan terealisasi (otomatis dari data), aksi tercatat, dan potensi ke target — Rupiah &amp; emisi.</p></div>
        ${periodControls("fx-eff")}</div>
      <div id="fx-eff"><p class="muted">Memuat…</p></div></section>

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
          <td style="white-space:nowrap;"><input type="number" class="btn btn-secondary btn-sm" id="fx-br-kg-${r.id}" value="${r.kg}" min="0.1" max="${r.kg}" step="0.1" style="width:90px;" aria-label="kg diserahkan permintaan #${r.id}">
            <button type="button" class="btn btn-primary btn-sm" data-fx-handover="${Number(r.id)}">Serahkan</button></td></tr>`).join("")}
          </tbody></table></div>`
        : emptyState("♻️", "Tidak ada pengajuan", "Pengajuan biochar dari petani muncul di sini.");
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
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
          <div class="form-group"><label for="fx-a-base">Nilai sebelum</label><input id="fx-a-base" name="baseline_value" type="number" step="any" value="${p.actual ?? ""}"></div>
          <div class="form-group"><label for="fx-a-cur">Nilai sesudah / target</label><input id="fx-a-cur" name="current_value" type="number" step="any" value="${p.target ?? ""}"></div>
          <div class="form-group"><label for="fx-a-rp">Hemat (Rp/periode)</label><input id="fx-a-rp" name="saving_rp" type="number" min="0" step="1" value="${p.saving_rp ?? ""}"></div>
          <div class="form-group"><label for="fx-a-co2">Kurang emisi (kgCO₂e)</label><input id="fx-a-co2" name="saving_co2e_kg" type="number" step="any" value="${p.saving_co2e_kg ?? ""}"></div>
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

  // ---------------------------------------------------------------- sambungan ke dashboard
  window.renderFactoryExtras = function (container) {
    if (!container || !["pabrik", "admin", "auditor"].includes(role())) return;
    container.insertAdjacentHTML("beforeend", HTML());
    $("fx-eff-go").onclick = loadEfficiency;
    $("fx-esg-go").onclick = loadEsg;
    $("fx-esg-csv").onclick = downloadEsgCsv;
    $("fx-esg-print").onclick = () => { document.body.classList.add("print-esg"); window.print(); };
    window.addEventListener("afterprint", () => document.body.classList.remove("print-esg"), { once: false });
    if (canWrite()) loadRedemptions();
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
    const wv = e.target.closest("[data-fx-waive]");
    if (wv) return waiveCharge(Number(wv.dataset.fxWaive));
    const a = e.target.closest("[data-fx-adopt]");
    if (a) return actionDialog(a.dataset.fxAdopt);
    const s = e.target.closest("[data-fx-status]");
    if (s) return setStatus(Number(s.dataset.fxStatus), s.dataset.to);
  });
})();
