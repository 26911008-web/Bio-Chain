/**
 * Module: Factory Pyrolysis & Multi-Biomass Product Optimization
 * Handles multi-product evaluation (Bio-Pellet, Briket, Biochar, Bio-Silika)
 * and LP allocation solver UI.
 */
(() => {
  "use strict";

  const GRADE_BADGE = { S: "badge-green", A: "badge-green", B: "badge-blue", C: "badge-amber", D: "badge-red" };
  const PROD_ICONS = { bio_pellet: "🪵", briket: "⬛", biochar: "🔋", bio_silika: "🧪" };
  const numOrNull = (v) => (v === "" || v == null ? null : Number(v));

  function renderAllocStocks(bmCache, H, num) {
    const box = $("fx-opt-alloc-stocks");
    if (!box) return;
    const defaults = { sekam_padi: 25000, serbuk_kayu: 20000, tempurung_kelapa: 15000, tongkol_jagung: 10000, bagasse_tebu: 10000 };
    box.innerHTML = `<table class="data-table"><thead><tr>
      <th>Pakai</th><th>Komoditas Biomassa</th><th class="num">Stok Umpan (kg)</th>
      <th class="num">MC (%)</th><th class="num">Harga Beli (Rp/kg)</th><th class="num">Abu (% bk)</th>
    </tr></thead><tbody>${bmCache.map(b => {
      const defKg = defaults[b.code] || 5000;
      return `<tr>
        <td><input type="checkbox" data-opt-stk-use="${H(b.code)}" ${defaults[b.code] ? "checked" : ""} aria-label="Gunakan stok ${H(b.name)}"></td>
        <td><b>${H(b.name)}</b><br><span class="kpi-lbl">${H(b.code)}</span></td>
        <td class="num"><input type="number" min="0" step="500" data-opt-stk-kg="${H(b.code)}" value="${defKg}" style="width:110px;" class="btn btn-secondary btn-sm"></td>
        <td class="num"><input type="number" min="0" max="90" step="0.5" data-opt-stk-mc="${H(b.code)}" value="${Number(b.moisture_typ_pct || 14)}" style="width:75px;" class="btn btn-secondary btn-sm"></td>
        <td class="num"><input type="number" min="0" step="10" data-opt-stk-price="${H(b.code)}" value="${H(b.base_price_per_kg ?? 350)}" style="width:85px;" class="btn btn-secondary btn-sm"></td>
        <td class="num">${num(b.ash_pct_db, 1)}%</td>
      </tr>`;
    }).join("")}</tbody></table>`;
  }

  function getSelectedAllocStocks() {
    return [...document.querySelectorAll("[data-opt-stk-use]:checked")].map(cb => {
      const code = cb.dataset.optStkUse;
      const getVal = (prefix) => {
        const el = document.querySelector(`[data-opt-stk-${prefix}="${CSS.escape(code)}"]`);
        return el ? el.value : "";
      };
      return {
        code,
        stock_kg: Number(getVal("kg")) || 0,
        moisture_pct: getVal("mc") === "" ? null : Number(getVal("mc")),
        purchase_price_per_kg: getVal("price") === "" ? null : Number(getVal("price"))
      };
    }).filter(s => s.stock_kg > 0);
  }

  async function runProductEvaluation(H, num, rp) {
    const out = $("fx-opt-eval-out");
    if (!out) return;
    return withBusy($("fx-opt-eval-go"), async () => {
      try {
        const com = $("fx-opt-com").value;
        const kg = Number($("fx-opt-kg").value) || 10000;
        const mc = numOrNull($("fx-opt-mc").value);
        const price = numOrNull($("fx-opt-price").value);

        const r = await api("/api/v1/factory/optimization/evaluate", {
          body: { commodity_code: com, quantity_kg: kg, moisture_pct: mc, purchase_price_per_kg: price }
        });

        const rec = r.recommendation || {};
        const fd = r.feedstock || {};
        out.innerHTML = `
          <div class="banner banner-info" role="note" style="margin-bottom:12px;">
            <div style="font-size:14px; font-weight:600; margin-bottom:4px;">🧭 Rekomendasi Optimal: ${H(rec.synthesis_rationale)}</div>
            <div class="kpi-lbl" style="display:flex; gap:16px; flex-wrap:wrap;">
              <span>💰 Profit Tertinggi: <b>${H(rec.best_economic_product)}</b></span>
              <span>⚡ Energi Maksimal: <b>${H(rec.best_energy_product)}</b></span>
              <span>🌱 Carbon Sink Maksimal: <b>${H(rec.best_carbon_product)}</b></span>
              <span>🏆 Pilihan Terbaik: <b>${H(rec.overall_recommended_product)}</b></span>
            </div>
          </div>
          <p class="kpi-lbl">Hasil analisis konversi ${num(fd.quantity_kg, 0)} kg <b>${H(fd.name)}</b> (MC ${num(fd.moisture_pct, 1)}%, Abu ${num(fd.ash_pct_db, 1)}% bk, LHV ${num(fd.lhv_db_mj_kg, 1)} MJ/kg):</p>
          <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px; margin-top:8px;">
            ${Object.entries(r.products).map(([k, p]) => {
              const st = p.suitability || {};
              const y = p.yield || {};
              const ec = p.economics || {};
              const en = p.energy || {};
              const cb = p.carbon || {};
              return `<div class="card" style="margin:0; border:1px solid var(--border-color, #e0e0e0); padding:12px; border-radius:8px;">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
                  <div>
                    <h4 style="margin:0; font-size:15px;">${PROD_ICONS[k] || "📦"} ${H(p.name)}</h4>
                    <span class="kpi-lbl">${H(p.standard)}</span>
                  </div>
                  <span class="badge ${GRADE_BADGE[st.grade] || "badge-gray"}" title="${H(st.verdict)}">
                    ${H(st.grade)} (${num(st.score, 0)}/100)
                  </span>
                </div>
                <div class="kpi-row" style="margin:6px 0; gap:4px;">
                  <div class="kpi-tile" style="padding:6px;"><div class="kpi-lbl">Hasil Produk</div><div class="kpi-val" style="font-size:15px;">${num(y.product_output_kg, 1)} kg</div><div class="kpi-lbl">Yield ${num(y.yield_pct, 1)}%</div></div>
                  <div class="kpi-tile" style="padding:6px;"><div class="kpi-lbl">Gross Margin</div><div class="kpi-val ${ec.gross_margin_rp >= 0 ? "kpi-green" : "kpi-amber"}" style="font-size:15px;">${rp(ec.gross_margin_rp)}</div><div class="kpi-lbl">${num(ec.gross_margin_pct, 1)}% margin</div></div>
                </div>
                <div class="kpi-row" style="margin:6px 0; gap:4px;">
                  <div class="kpi-tile" style="padding:6px;"><div class="kpi-lbl">SEC Listrik</div><div class="kpi-val" style="font-size:14px;">${num(en.electricity_sec_kwh_per_ton, 1)}</div><div class="kpi-lbl">kWh/t produk</div></div>
                  <div class="kpi-tile" style="padding:6px;"><div class="kpi-lbl">Net Karbon</div><div class="kpi-val" style="font-size:14px;">${num(cb.net_carbon_balance_tco2e, 3)}</div><div class="kpi-lbl">tCO₂e balance</div></div>
                </div>
                <div style="font-size:12px; margin-top:8px; line-height:1.4;">
                  <div>💰 <b>Harga:</b> ${rp(ec.selling_price_rp_per_kg)}/kg · <b>Margin/t:</b> ${rp(ec.margin_per_ton_feed_rp)}</div>
                  <div>⚡ <b>LHV:</b> ${num(en.product_lhv_ar_mj_kg, 1)} MJ/kg · <b>Energi:</b> ${num(en.total_energy_gj, 1)} GJ</div>
                </div>
                ${st.warnings && st.warnings.length ? `<div class="banner banner-warning" role="note" style="margin-top:8px; padding:4px 8px; font-size:11px;">⚠️ ${H(st.warnings[0])}</div>` : ""}
                ${st.compliance && st.compliance.length ? `<div style="font-size:11px; margin-top:6px; color:var(--text-muted, #666);">${st.compliance.map(c => `<span>${c.ok ? "✅" : "⛔"} ${H(c.standard)}</span>`).join(" · ")}</div>` : ""}
              </div>`;
            }).join("")}
          </div>
        `;
      } catch (err) {
        out.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(err.message)}</div>`;
      }
    }, "⏳");
  }

  async function runProductAllocation(optConfig, H, num, rp) {
    const out = $("fx-opt-alloc-out");
    if (!out) return;
    const stocks = getSelectedAllocStocks();
    if (!stocks.length) return showToast("Pilih minimal satu komoditas dengan stok > 0.", "⚠️");

    return withBusy($("fx-opt-alloc-go"), async () => {
      try {
        const obj = $("fx-opt-obj").value;
        const caps = {};
        for (const p of ["bio_pellet", "briket", "biochar", "bio_silika"]) {
          const el = $(`fx-opt-cap-${p}`);
          if (el && el.value !== "") caps[p] = Number(el.value);
        }

        const r = await api("/api/v1/factory/optimization/allocate", {
          body: { objective: obj, stocks, capacities: caps }
        });

        if (r.status !== "optimal" && r.status !== "success") {
          out.innerHTML = `<div class="banner banner-warning" role="alert">⚠️ Status Solver: ${H(r.status)}. Alokasi mungkin belum konvergen sepenuhnya.</div>`;
          return;
        }

        const sm = r.summary || {};
        out.innerHTML = `
          <div class="kpi-row" style="margin-top:12px;">
            <div class="kpi-tile"><div class="kpi-lbl">Biomassa Terolah</div><div class="kpi-val">${num(sm.total_feedstock_used_kg, 0)} kg</div><div class="kpi-lbl">${num(sm.total_feedstock_used_kg / 1000, 1)} ton umpan</div></div>
            <div class="kpi-tile"><div class="kpi-lbl">Total Produk</div><div class="kpi-val">${num(sm.total_product_output_kg, 0)} kg</div><div class="kpi-lbl">${num(sm.total_product_output_kg / 1000, 1)} ton produk</div></div>
            <div class="kpi-tile kpi-green"><div class="kpi-lbl">Total Gross Margin</div><div class="kpi-val">${rp(sm.total_gross_margin_rp)}</div><div class="kpi-lbl">Revenue ${rp(sm.total_revenue_rp)}</div></div>
            <div class="kpi-tile"><div class="kpi-lbl">Output Energi</div><div class="kpi-val">${num(sm.total_energy_output_gj, 1)} GJ</div><div class="kpi-lbl">LHV produk</div></div>
            <div class="kpi-tile"><div class="kpi-lbl">Net Carbon Balance</div><div class="kpi-val">${num(sm.total_net_carbon_balance_tco2e, 2)}</div><div class="kpi-lbl">tCO₂e mitigasi/sink</div></div>
          </div>

          <h4 style="margin:16px 0 6px;">Rencana Alokasi Produksi Optimal (HiGHS Solver)</h4>
          <div class="table-scroll"><table class="data-table"><thead><tr>
            <th>Umpan Biomassa</th><th>Produk Tujuan</th><th class="num">Alokasi Umpan</th>
            <th class="num">Estimasi Output</th><th class="num">Gross Margin</th><th class="num">Output Energi</th><th class="num">Net Karbon</th><th>Kesesuaian Mutu</th>
          </tr></thead><tbody>${r.allocations.map(a => `<tr>
            <td><b>${H(a.feedstock_name)}</b></td>
            <td>${PROD_ICONS[a.product_key] || ""} <b>${H(a.product_name)}</b></td>
            <td class="num"><b>${num(a.allocated_kg, 0)} kg</b></td>
            <td class="num">${num(a.product_output_kg, 0)} kg</td>
            <td class="num ${a.gross_margin_rp >= 0 ? "kpi-green" : "kpi-amber"}">${rp(a.gross_margin_rp)}</td>
            <td class="num">${num(a.energy_gj, 1)} GJ</td>
            <td class="num">${num(a.net_carbon_tco2e, 3)} tCO₂e</td>
            <td><span class="badge ${GRADE_BADGE[a.suitability_score >= 85 ? "S" : a.suitability_score >= 70 ? "A" : a.suitability_score >= 55 ? "B" : "C"]}">${H(a.suitability_verdict)} (${num(a.suitability_score, 0)})</span></td>
          </tr>`).join("")}</tbody></table></div>

          <h4 style="margin:16px 0 6px;">Utilisasi Kapasitas Lini Mesin Pabrik</h4>
          <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:8px;">
            ${Object.entries(r.capacity_utilization).map(([p, cu]) => {
              const pInfo = (optConfig.products || {})[p] || {};
              const pct = Math.min(100, Math.round(cu.utilization_pct || 0));
              return `<div class="card" style="margin:0; padding:10px; border-radius:6px; border:1px solid var(--border-color, #e0e0e0);">
                <div style="display:flex; justify-content:space-between; font-size:13px; font-weight:600;">
                  <span>${PROD_ICONS[p] || ""} ${H(pInfo.name || p)}</span>
                  <span>${pct}%</span>
                </div>
                <div style="background:var(--border-color, #eee); height:8px; border-radius:4px; overflow:hidden; margin:6px 0;">
                  <div style="background:var(--primary, #2e7d32); width:${pct}%; height:100%;"></div>
                </div>
                <div class="kpi-lbl">${num(cu.allocated_product_kg, 0)} kg / ${num(cu.capacity_kg, 0)} kg batas</div>
              </div>`;
            }).join("")}
          </div>

          ${r.managerial_insights && r.managerial_insights.length ? `
            <div class="banner banner-info" role="note" style="margin-top:14px;">
              <div style="font-weight:600; margin-bottom:4px;">💡 Insight &amp; Rekomendasi Manajerial Pabrik:</div>
              <ul style="margin:0; padding-left:18px; font-size:12.5px; line-height:1.5;">
                ${r.managerial_insights.map(i => `<li>${H(i)}</li>`).join("")}
              </ul>
            </div>` : ""}
        `;
      } catch (err) {
        out.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(err.message)}</div>`;
      }
    }, "⏳");
  }

  window.FactoryPyrolysisCalc = {
    renderAllocStocks,
    getSelectedAllocStocks,
    runProductEvaluation,
    runProductAllocation
  };
})();
