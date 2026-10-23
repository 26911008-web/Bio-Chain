/* Engine Lab — kalkulator engine mandiri (tab "Engines" pabrik/admin).
 *
 * Bergantung pada global app.js: $, api, showToast, withBusy, esc, num, rp.
 *
 * Dipindah dari app.js (audit 23 Okt 2026, CLAUDE.md §3.1). Skrip klasik dimuat SETELAH app.js: fungsi
 * deklarasi tetap global (window.*) sehingga handler deklaratif data-onclick & pemanggil lain tidak berubah.
 */

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
  if (subId === "eng-opt") initLabProductOptimization();
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
    <div class="kpi-tile kpi-blue"><div class="kpi-lbl">SEC proses</div><div class="kpi-val">${num(s.sec_kwh_per_ton_avg, 0)}</div><div class="kpi-lbl">kWh/ton biomassa</div></div>
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

    if (typeof Chart !== "undefined") {
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
  if (job.status === "done") return job.result;     // backend inline (serverless): hasil langsung di respons
  if (job.status === "failed") throw new Error(job.error || "Perhitungan gagal");
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
