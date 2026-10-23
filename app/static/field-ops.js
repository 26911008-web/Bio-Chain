/* Bio-Chain field-ops UI — fitur kepatuhan lapangan di atas API yang ada.
 *  F7  Petani tanpa HP (pengepul mendaftarkan & melapor atas nama petani, nota QR)
 *  F8  Bayar petani + kuitansi BYR (pengepul) · Pembayaran saya (petani)
 *  F12 Data saya: persetujuan, unduh data, hapus akun (UU PDP) · nomor petani disamarkan + tombol Hubungi
 *  F6  Wajib ganti password setelah reset admin
 * Memakai helper global dari index.html (api, $, esc, num, rp, openModal, showToast, STATE, withBusy).
 */
(() => {
  "use strict";
  const H = (s) => esc(s == null ? "" : String(s));
  // Rupiah ringkas untuk tile KPI (angka lengkap di title) — "Rp 3.997.612" tidak muat di HP 360px
  const rpShort = (v) => {
    const n = Number(v) || 0, a = Math.abs(n);
    const t = a >= 1e9 ? `${num(n / 1e9, 1)} M` : a >= 1e6 ? `${num(n / 1e6, 1)} jt` : a >= 1e4 ? `${num(n / 1e3, 0)} rb` : num(n, 0);
    return `<span title="${rp(n)}">Rp ${t}</span>`;
  };
  const METHOD_LABEL = { tunai: "Tunai", transfer: "Transfer bank", qris: "QRIS", ewallet: "E-wallet" };
  const formatDateTime = (iso) => {
    if (!iso) return "-";
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return String(iso);
      return d.toLocaleString("id-ID", {
        year: "numeric", month: "short", day: "2-digit",
        hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false
      }) + " WIB";
    } catch { return String(iso); }
  };

  // ---------------------------------------------------------------- dialog generik (form)
  function formDialog({ title, body, ok = "Simpan", danger = false, wide = false, onSubmit }) {
    const d = document.createElement("dialog");
    d.className = wide ? "ui-confirm ui-confirm-wide" : "ui-confirm";
    d.innerHTML = `<form method="dialog" class="fo-form">
        <h3>${H(title)}</h3>
        <div class="fo-body">${body}</div>
        <p class="form-error" role="alert" hidden></p>
        <div class="ui-confirm-actions">
          <button value="no" class="btn btn-secondary" formnovalidate>Batal</button>
          <button value="yes" class="btn ${danger ? "btn-danger" : "btn-primary"}">${H(ok)}</button>
        </div></form>`;
    d.addEventListener("close", () => d.remove());
    document.body.appendChild(d);
    const form = d.querySelector("form");
    const err = d.querySelector(".form-error");
    form.addEventListener("submit", async (e) => {
      if (e.submitter && e.submitter.value === "no") return;
      e.preventDefault();
      if (!form.reportValidity()) return;
      const btn = form.querySelector('button[value="yes"]');
      btn.disabled = true;
      try {
        const keep = await onSubmit(new FormData(form), d);
        if (!keep) d.close();
      } catch (ex) {
        err.hidden = false;
        err.textContent = ex.message || String(ex);
      } finally { btn.disabled = false; }
    });
    form.addEventListener("change", async (e) => {
      const sel = e.target;
      if (sel && sel.tagName === "SELECT" && sel.value === "__custom__") {
        const name = prompt("Masukkan nama komoditas biomassa baru (misal: Kulit Kopi, Cangkang Sawit, Bonggol Jagung):");
        if (!name || !name.trim()) {
          sel.value = "sekam_padi";
          return;
        }
        try {
          const res = await api("/api/v1/biomass", { method: "POST", body: { name: name.trim() } });
          showToast(`Komoditas biomassa "${res.name}" berhasil ditambahkan!`, "🌿");
          if (typeof biomassList === "function") await biomassList();
          sel.innerHTML = await commodityOptions(res.code);
          sel.value = res.code;
          sel.dispatchEvent(new Event("input", { bubbles: true }));
        } catch (err) {
          showToast(err.message || "Gagal menambahkan biomassa", "❌");
          sel.value = "sekam_padi";
        }
      }
    });
    d.addEventListener("close", () => d.remove());
    d.showModal();
    const first = d.querySelector("input, select, textarea");
    if (first) first.focus();
    return d;
  }

  // ================================================================ PENGEPUL
  const PENGEPUL_HTML = `
    <section class="card" aria-labelledby="fo-proxy-title" style="margin-top:16px;">
      <div class="card-header"><div>
        <h3 class="card-title" id="fo-proxy-title">👵 Petani tanpa HP</h3>
        <p class="card-sub">Daftarkan & laporkan biomassa atas nama petani yang tidak punya HP. Petani menerima nota QR.</p></div>
        <button type="button" class="btn btn-secondary btn-sm" id="fo-proxy-new">➕ Daftarkan petani</button></div>
      <div id="fo-proxy-list"><p class="muted">Memuat…</p></div>
    </section>

    <section class="card" aria-labelledby="fo-pay-title" style="margin-top:16px;">
      <div class="card-header"><div>
        <h3 class="card-title" id="fo-pay-title">💸 Bayar petani</h3>
        <p class="card-sub">Lot yang sudah Anda timbang tetapi belum tercatat dibayar. DP (uang muka) dipotong otomatis saat pelunasan.</p></div></div>
      <div id="fo-unpaid"><p class="muted">Memuat…</p></div>
    </section>

    <section class="card" aria-labelledby="fo-wh-title" style="margin-top:16px;">
      <div class="card-header"><div>
        <h3 class="card-title" id="fo-wh-title">🏚️ Gudang &amp; stok multi-biomassa</h3>
        <p class="card-sub">Stok per gudang × komoditas. Berat bayar otomatis dipotong kadar air &amp; kotoran sesuai acuan komoditas — bisa dicatat tanpa sinyal.</p></div>
        <button type="button" class="btn btn-secondary btn-sm" id="fo-wh-new">➕ Gudang</button></div>
      <div id="fo-wh"><p class="muted">Memuat…</p></div>
    </section>

    <section class="card" aria-labelledby="fo-backhaul-title" style="margin-top:16px;">
      <div class="card-header"><div>
        <h3 class="card-title" id="fo-backhaul-title">🚚 Rute Konsolidasi &amp; Muatan Balik Abu Bottom Ash</h3>
        <p class="card-sub">Simulasi kapasitas ganda armada (30 m³ &amp; 5.000 kg) dengan integrasi pengiriman abu bottom ash untuk pembenah tanah sawah petani.</p></div>
        <button type="button" class="btn btn-primary btn-sm" id="fo-plan-route-btn" data-onclick="openRouteOptimizationModal()">🗺️ Optimasi &amp; Teknis Rute Terverifikasi</button></div>
      <div id="fo-backhaul-status"><p class="muted">Klik tombol di atas untuk membuka modul pop-up optimasi rute terverifikasi, peta spasial Leaflet, dan analisis teknis kapasitas.</p></div>
    </section>

    <section class="card" aria-labelledby="fo-rec-title" style="margin-top:16px;">
      <div class="card-header"><div>
        <h3 class="card-title" id="fo-rec-title">🏭 Piutang Pabrik &amp; Status DR</h3>
        <p class="card-sub">Daftar tagihan Delivery Request ke pabrik yang belum terbayar beserta umur piutang (aging).</p></div></div>
      <div id="fo-factory-receivables"><p class="muted">Memuat…</p></div>
    </section>

    <section class="card" aria-labelledby="fo-ch-title" style="margin-top:16px;">
      <div class="card-header"><div>
        <h3 class="card-title" id="fo-ch-title">🚚 Potongan logistik saya</h3>
        <p class="card-sub">Ongkos jarak kosong bila membatalkan saat truk di jalan / stok tidak ada saat truk tiba. Dipotong dari pembayaran pabrik berikutnya.</p></div></div>
      <div id="fo-charges"><p class="muted">Memuat…</p></div>
    </section>`;

  const CH_BADGE = { terbuka: "badge-amber", dipotong: "badge-gray", dibebaskan: "badge-green" };
  const CH_KIND = { batal_pembelian: "Batal saat truk di jalan", stop_gagal: "Stok tidak ada / batal saat truk tiba" };
  async function loadCharges() {
    const box = $("fo-charges");
    if (!box) return;
    try {
      const rows = await api("/api/v1/collector/charges");
      const open = rows.filter(r => r.status === "terbuka").reduce((a, r) => a + r.amount_rp, 0);
      box.innerHTML = rows.length ? `<p class="kpi-lbl">Terbuka: <b>${rp(open)}</b></p><div class="table-scroll"><table class="data-table"><thead><tr>
          <th>Kejadian</th><th class="num">Jarak</th><th class="num">Ongkos</th><th>Status</th></tr></thead><tbody>${rows.map(r => `<tr>
          <td>${H(CH_KIND[r.kind] || r.kind)}<br><span class="kpi-lbl">lot #${Number(r.harvest_id)} · ${H((r.created_at || "").slice(0, 10))}</span></td>
          <td class="num">${num(r.km, 1)} km</td><td class="num">${rp(r.amount_rp)}</td>
          <td><span class="badge ${CH_BADGE[r.status] || ""}">${H(r.status)}</span></td></tr>`).join("")}</tbody></table></div>`
        : emptyState("✅", "Tidak ada potongan", "Konfirmasi stok ke petani (💬 WA) sebelum truk berangkat agar tidak ada ongkos jarak kosong.");
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  function payDp(harvestId, amount, name) {
    const cap = Math.floor(amount * (typeof PV === "function" ? PV("pasar.dp_max_pct", 30) : 30) / 100);
    formDialog({
      title: `Uang muka (DP) · ${name}`, ok: "Catat DP",
      body: `<p class="ui-confirm-body">Lot #${harvestId} · nilai ±${rp(amount)}. DP maksimal ${rp(cap)}; dipotong otomatis saat pelunasan.
               Bila Anda membatalkan sepihak, DP menjadi hak petani.</p>
             <div class="form-group"><label for="fo-dp-amt">Jumlah DP (Rp)</label>
               <input id="fo-dp-amt" name="amount" type="number" min="1000" max="${cap}" step="1000" value="${Math.min(cap, Math.round(amount * 0.2 / 1000) * 1000)}" required inputmode="numeric"></div>
             <div class="form-group"><label for="fo-dp-m">Metode</label>
               <select id="fo-dp-m" name="method">${Object.entries(METHOD_LABEL).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></div>
             <div class="form-group"><label for="fo-dp-ref">No. referensi transfer / QRIS</label>
               <input id="fo-dp-ref" name="reference" maxlength="80" placeholder="wajib selain tunai"></div>`,
      onSubmit: async (fd) => {
        const r = await api(`/api/v1/collector/harvests/${harvestId}/pay-dp`, { body: {
          amount_rp: Number(fd.get("amount")), method: fd.get("method"), reference: fd.get("reference") || null,
          client_event_id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) } });
        openModal("Kuitansi uang muka", r.receipt_code, `${rp(r.amount_rp)} · ${METHOD_LABEL[r.method]} — berikan/foto untuk petani`);
        loadUnpaid();
        if (typeof loadCollectorData === "function") loadCollectorData();
      },
    });
  }

  async function loadProxyFarmers() {
    const box = $("fo-proxy-list");
    if (!box) return;
    try {
      const rows = await api("/api/v1/collector/proxy-farmers");
      box.innerHTML = rows.length ? `<div class="table-scroll"><table class="data-table"><thead><tr>
          <th>Petani</th><th>Kecamatan</th><th>Aksi</th></tr></thead><tbody>${rows.map(f => `
          <tr><td><b>${H(f.full_name)}</b>${f.phone ? `<br><span class="kpi-lbl">${H(f.phone)}</span>` : ""}</td>
              <td>${H(f.kecamatan || "-")}</td>
              <td><button type="button" class="btn btn-primary btn-sm" data-fo-report="${Number(f.id)}"
                    data-name="${H(f.full_name)}">Lapor biomassa</button></td></tr>`).join("")}</tbody></table></div>`
        : emptyState("👵", "Belum ada petani binaan", "Daftarkan petani yang tidak punya HP agar biomassanya tetap tercatat.");
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  function newProxyFarmer() {
    formDialog({
      title: "Daftarkan petani tanpa HP", ok: "Daftarkan",
      body: `<div class="form-group"><label for="fo-pf-name">Nama petani</label>
               <input id="fo-pf-name" name="full_name" required minlength="2" maxlength="100" autocomplete="off"></div>
             <div class="grid-2" style="gap:10px;">
               <div class="form-group"><label for="fo-pf-desa">Desa / dusun</label>
                 <input id="fo-pf-desa" name="desa" maxlength="100" placeholder="untuk membedakan nama sama"></div>
               <div class="form-group"><label for="fo-pf-kec">Kecamatan</label>
                 <input id="fo-pf-kec" name="kecamatan" maxlength="100" value="${H((STATE.user || {}).kecamatan || "")}"></div></div>
             <div class="grid-2" style="gap:10px;">
               <div class="form-group"><label for="fo-pf-kab">Kabupaten</label>
                 <input id="fo-pf-kab" name="kabupaten" maxlength="100" value="${H((STATE.user || {}).kabupaten || "Sleman")}"></div>
               <div class="form-group"><label for="fo-pf-phone">HP keluarga / ketua kelompok</label>
                 <input id="fo-pf-phone" name="phone" inputmode="tel" maxlength="30" placeholder="opsional"></div></div>
             <div class="form-group"><button type="button" class="btn btn-secondary btn-sm" id="fo-pf-gps">📍 Pakai lokasi saya sekarang</button>
               <span class="kpi-lbl" id="fo-pf-gps-lbl">opsional · berdiri di sawah/gudang petani</span>
               <input type="hidden" name="lat" id="fo-pf-lat"><input type="hidden" name="lon" id="fo-pf-lon"></div>
             <label class="fo-check"><input type="checkbox" name="consent" required>
               Petani sudah saya jelaskan & <b>setuju</b> nama, lokasi, timbangan dan pembayarannya dicatat di Bio-Chain.</label>`,
      onSubmit: async (fd) => {
        await api("/api/v1/collector/proxy-farmers", { body: {
          full_name: fd.get("full_name"), desa: fd.get("desa") || null, kecamatan: fd.get("kecamatan") || null,
          kabupaten: fd.get("kabupaten") || null, lat: fd.get("lat") ? Number(fd.get("lat")) : null,
          lon: fd.get("lon") ? Number(fd.get("lon")) : null,
          phone: fd.get("phone") || null, consent_given: fd.get("consent") === "on" } });
        showToast("Petani binaan terdaftar.", "👵");
        loadProxyFarmers();
      },
    });
    $("fo-pf-gps").onclick = () => {
      if (!navigator.geolocation) return showToast("GPS tidak tersedia di HP ini.", "⚠️");
      $("fo-pf-gps-lbl").textContent = "⏳ mencari lokasi…";
      navigator.geolocation.getCurrentPosition(pos => {
        $("fo-pf-lat").value = pos.coords.latitude.toFixed(6); $("fo-pf-lon").value = pos.coords.longitude.toFixed(6);
        $("fo-pf-gps-lbl").textContent = `✅ ${pos.coords.latitude.toFixed(5)}, ${pos.coords.longitude.toFixed(5)} (±${Math.round(pos.coords.accuracy)} m)`;
      }, () => { $("fo-pf-gps-lbl").textContent = "Lokasi tidak didapat — boleh dilewati."; },
      { enableHighAccuracy: true, timeout: 15000 });
    };
  }

  // Field mutu opsional yang SAMA dengan kartu "Lapor & Jual" petani
  const QUALITY_FIELDS = (pfx) => `
    <details class="demo-hint-box"><summary>💧 Info mutu <span class="muted">(opsional)</span></summary>
      <div class="sale-grid">
        <div><label class="kpi-lbl" for="${pfx}-moist">Taksiran kadar air (%)</label>
          <input id="${pfx}-moist" name="moisture_est" type="number" min="0" max="60" step="0.5" inputmode="decimal" placeholder="kosongkan bila tidak tahu"></div>
        <div><label class="kpi-lbl" for="${pfx}-grade">Taksiran grade</label>
          <select id="${pfx}-grade" name="grade_est"><option value="">Tidak tahu</option><option value="A">A · kering (≤12%)</option>
            <option value="B">B · standar (12–15%)</option><option value="C">C · lembap (15–18%)</option><option value="D">D · basah (&gt;18%)</option></select></div>
      </div><p class="form-hint">Tidak memengaruhi harga; harga final dari uji Anda saat menimbang.</p></details>`;
  let millCache = null;
  async function millOptions() {
    if (!millCache) millCache = await api("/api/v1/farmer/mills").catch(() => []);
    return millCache.map(m => `<option value="${Number(m.id)}">${H(m.name)} (${H(m.kecamatan)})</option>`).join("");
  }

  async function commodityOptions(selected = "sekam_padi") {
    const rows = typeof biomassList === "function" ? await biomassList() : [];
    if (!rows.length) return `<option value="sekam_padi">Biomassa</option><option value="__custom__">➕ Tambah Biomassa Lain...</option>`;
    const opts = rows.map(b => `<option value="${H(b.code)}" ${b.code === selected ? "selected" : ""}>${H(b.name)}</option>`);
    opts.push(`<option value="__custom__">➕ Tambah Biomassa Lain...</option>`);
    return opts.join("");
  }

  async function proxyReport(farmerId, name) {
    const mills = await millOptions();
    formDialog({
      title: `Lapor biomassa · ${name}`, ok: "Laporkan",
      body: `<div class="form-group"><label for="fo-pr-com">Jenis biomassa</label>
               <select id="fo-pr-com" name="commodity">${await commodityOptions()}</select></div>
             <div class="form-group"><label for="fo-pr-qty">Jumlah (kg)</label>
               <input id="fo-pr-qty" name="qty" type="number" min="50" max="50000" step="50" value="1000" required></div>
             <div class="form-group"><label for="fo-pr-mill">Lokasi titik pemasok / penggilingan</label>
               <select id="fo-pr-mill" name="mill_id"><option value="">—</option>${mills}</select></div>
             ${QUALITY_FIELDS("fo-pr")}
             <p class="kpi-lbl">Isian sama dengan laporan petani sendiri. Nota QR setelah ini diberikan/difoto untuk petani.</p>`,
      onSubmit: async (fd) => {
        const r = await api("/api/v1/collector/proxy-harvest", { body: {
          farmer_id: farmerId, quantity_kg: Number(fd.get("qty")), mill_id: Number(fd.get("mill_id")) || null,
          commodity: fd.get("commodity") || "sekam_padi",
          moisture_est: fd.get("moisture_est") === "" ? null : Number(fd.get("moisture_est")),
          grade_est: fd.get("grade_est") || null,
          client_event_id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) } });
        const comLabel = (r.commodity || fd.get("commodity") || "sekam").includes("sekam") ? "sekam" : "biomassa";
        const titlePrefix = `Nota ${comLabel}`;
        openModal(`${titlePrefix} · ${r.farmer_name || name}`, r.qr_code, `${num(r.quantity_kg, 0)} kg · dilaporkan pengepul untuk petani`);
        showToast(r.message, "✅");
        if (typeof loadCollectorData === "function") loadCollectorData();
      },
    });
  }

  async function loadUnpaid() {
    const box = $("fo-unpaid");
    if (!box) return;
    try {
      const rows = await api("/api/v1/collector/unpaid-harvests");
      if (!rows.length) {
        box.innerHTML = emptyState("✅", "Semua lot sudah dibayar", "Lot baru muncul di sini setelah Anda menimbang & menguji biomassa.");
        return;
      }

      // Pengelompokan Data per Bulan (Monthly Grouping)
      const monthGroups = {};
      rows.forEach(r => {
        const meta = (typeof window.getMonthYearMeta === "function")
          ? window.getMonthYearMeta(r.verified_at)
          : { key: "2026-10", label: "Oktober 2026", shortLabel: "Okt 2026" };
        if (!monthGroups[meta.key]) {
          monthGroups[meta.key] = {
            meta,
            rows: [],
            totalKg: 0,
            totalRp: 0
          };
        }
        monthGroups[meta.key].rows.push(r);
        monthGroups[meta.key].totalKg += (Number(r.verified_kg) || 0);
        monthGroups[meta.key].totalRp += (Number(r.amount_rp) || 0);
      });

      const sortedKeys = Object.keys(monthGroups).sort().reverse();
      const totalAllRp = rows.reduce((acc, r) => acc + (Number(r.amount_rp) || 0), 0);
      const totalAllKg = rows.reduce((acc, r) => acc + (Number(r.verified_kg) || 0), 0);

      let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px; background:var(--surface-2); padding:10px 14px; border-radius:8px; border:1px solid var(--border);">
          <div>
            <span class="kpi-lbl" style="font-size:12px;">Total Tagihan Belum Dibayar:</span>
            <b style="color:var(--primary); font-size:1.15rem; margin-left:6px;">${rp(totalAllRp)}</b>
            <span class="muted" style="font-size:11.5px; margin-left:6px;">(${rows.length} lot · ${num(totalAllKg, 0)} kg)</span>
          </div>
          <div style="font-size:12px; color:var(--ink-muted);">
            Terbagi dalam <b>${sortedKeys.length}</b> periode bulan
          </div>
        </div>
      `;

      sortedKeys.forEach((key, idx) => {
        const g = monthGroups[key];
        const isOpen = idx === 0 ? "open" : "";
        html += `
          <details class="month-group-card" ${isOpen} style="margin-bottom:14px; border:1px solid var(--border); border-radius:10px; overflow:hidden; background:var(--surface-1); transition:border-color 0.2s;">
            <summary style="cursor:pointer; padding:12px 16px; background:linear-gradient(90deg, var(--surface-2), var(--surface-1)); font-weight:700; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; user-select:none; border-bottom:1px solid var(--border);">
              <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                <span style="font-size:1rem; color:var(--ink);">📅 ${H(g.meta.label)}</span>
                <span class="badge badge-purple">${g.rows.length} Lot</span>
                <span class="badge badge-green">${num(g.totalKg, 0)} kg</span>
              </div>
              <div style="display:flex; align-items:center; gap:10px;">
                <span style="color:var(--primary); font-weight:800; font-size:1.05rem;">${rp(g.totalRp)}</span>
                <span class="btn btn-secondary btn-sm" style="font-size:11px; padding:3px 8px;">Detail Lot ▾</span>
              </div>
            </summary>
            <div class="table-scroll" style="margin:0; padding:4px 0 0;">
              <table class="data-table">
                <thead><tr><th>Lot</th><th>Petani</th><th class="num">Nilai</th><th>Aksi</th></tr></thead>
                <tbody>
                  ${g.rows.map(r => `
                    <tr>
                      <td>#${Number(r.harvest_id)}<br><span class="kpi-lbl">${num(r.verified_kg, 0)} kg · Grade ${H(r.grade || "-")}</span></td>
                      <td><b>${H(r.farmer_name)}</b>${r.verified_at ? `<br><small class="muted">${(typeof formatWIB === "function" ? formatWIB(r.verified_at).split(',')[0] : H(r.verified_at.slice(0, 10)))}</small>` : ''}</td>
                      <td class="num"><b style="color:var(--primary); font-size:13px;">${rp(r.amount_rp)}</b></td>
                      <td style="white-space:nowrap;">
                        <button type="button" class="btn btn-secondary btn-sm" data-fo-dp="${Number(r.harvest_id)}"
                          data-amount="${Number(r.amount_rp)}" data-name="${H(r.farmer_name)}" title="Uang muka; dipotong saat pelunasan">DP</button>
                        <button type="button" class="btn btn-primary btn-sm" data-fo-pay="${Number(r.harvest_id)}"
                          data-amount="${Number(r.amount_rp)}" data-name="${H(r.farmer_name)}">Bayar</button>
                      </td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          </details>
        `;
      });

      box.innerHTML = html;
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  function payFarmer(harvestId, amount, name) {
    formDialog({
      title: `Bayar ${name}`, ok: `Catat bayar ${rp(amount)}`,
      body: `<p class="ui-confirm-body">Lot #${harvestId} · nilai <b>${rp(amount)}</b> (potongan pajak dihitung server bila diatur).</p>
             <div class="form-group"><label for="fo-pay-m">Metode</label>
               <select id="fo-pay-m" name="method">${Object.entries(METHOD_LABEL).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></div>
             <div class="form-group"><label for="fo-pay-ref">No. referensi transfer / QRIS</label>
               <input id="fo-pay-ref" name="reference" maxlength="80" placeholder="wajib selain tunai"></div>`,
      onSubmit: async (fd) => {
        const method = fd.get("method");
        if (method !== "tunai" && !String(fd.get("reference") || "").trim()) throw new Error("Isi nomor referensi transfer/QRIS.");
        const r = await api(`/api/v1/collector/harvests/${harvestId}/pay-farmer`, { body: {
          method, reference: fd.get("reference") || null,
          client_event_id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) } });
        openModal("Kuitansi bayar petani", r.receipt_code,
          `${rp(r.net_rp)} bersih${r.tax_rp || r.dp_rp ? ` (bruto ${rp(r.gross_rp)}${r.tax_rp ? ` − pajak ${rp(r.tax_rp)}` : ""}${r.dp_rp ? ` − DP ${rp(r.dp_rp)}` : ""})` : ""} · ${METHOD_LABEL[r.method]} — berikan/foto untuk petani`
          + (r.dp_excess_rp ? ` · ⚠️ kelebihan DP ${rp(r.dp_excess_rp)} wajib dikembalikan petani` : ""));
        loadUnpaid();
      },
    });
  }

  // 08xx / +62 / 62 → 62xx (format wa.me)
  const waNumber = (phone) => {
    const d = String(phone || "").replace(/\D/g, "");
    return d.startsWith("0") ? "62" + d.slice(1) : d.startsWith("62") ? d : d ? "62" + d : "";
  };
  async function showContact(harvestId) {
    const win = window.open("", "_blank");                 // dibuka saat klik → tidak kena pemblokir pop-up
    try {
      const c = await api(`/api/v1/collector/harvests/${harvestId}/contact`);
      if (c.without_phone || !c.phone) {
        if (win) win.close();
        return showToast(`${c.farmer_name} tidak punya HP — temui langsung di ${c.kecamatan || "lokasi"}.`, "👵");
      }
      const me = (STATE.user || {}).full_name || "pengepul";
      const text = `Halo ${c.farmer_name}, saya ${me} dari Bio-Chain. Terkait laporan biomassa lot #${harvestId}: kapan bisa dijemput/ditimbang?`;
      const url = `https://wa.me/${waNumber(c.phone)}?text=${encodeURIComponent(text)}`;
      if (win) { win.opener = null; win.location.href = url; }
      else window.location.href = url;
      showToast("Membuka WhatsApp… (akses nomor tercatat sesuai UU PDP)", "💬");
    } catch (e) { if (win) win.close(); showToast(e.message, "❌"); }
  }

  // Tolak lot dengan penyebab terstruktur → defect rate & saran perbaikan di laporan petani
  const REJECT_CATS = { basah: "Terlalu basah", berjamur: "Berjamur / berbau", kontaminan: "Kontaminan (pasir/jerami/plastik)",
                        selisih_berat: "Selisih berat besar", stok_tidak_ada: "Stok tidak ada saat dijemput", lainnya: "Lainnya" };
  function rejectLot(harvestId) {
    if (!harvestId) return;
    formDialog({
      title: `Tolak lot #${harvestId}`, ok: "Tolak lot", danger: true,
      body: `<div class="form-group"><label for="fo-rj-cat">Penyebab utama</label>
               <select id="fo-rj-cat" name="category" required>${Object.entries(REJECT_CATS).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></div>
             <div class="form-group"><label for="fo-rj-why">Keterangan untuk petani</label>
               <input id="fo-rj-why" name="reason" required minlength="3" maxlength="500" placeholder="mis. kadar air 22%, masih lembap"></div>
             <p class="kpi-lbl">Penyebab tampil sebagai umpan balik di laporan bulanan petani agar bisa diperbaiki.</p>`,
      onSubmit: async (fd) => {
        await apiMutation("/api/v1/collector/reject", { harvest_id: harvestId, category: fd.get("category"),
                          reason: fd.get("reason") }, `Tolak lot #${harvestId}`);
        showToast(`Lot #${harvestId} ditolak & penyebab dicatat.`, "⛔");
        if (typeof loadCollectorData === "function") loadCollectorData();
      },
    });
  }
  window.rejectLot = rejectLot;

  // ================================================================ PETANI
  const PETANI_HTML = `
    <section class="card" aria-labelledby="fo-mypay-title">
      <div class="card-header"><div>
        <h3 class="card-title" id="fo-mypay-title">💰 Pembayaran &amp; Kuitansi Saya</h3>
        <p class="card-sub">Tracking terpadu uang muka (DP), verifikasi timbangan, kuitansi digital BYR, dan status pelunasan.</p></div></div>
      <div class="kpi-row" id="fo-pay-kpis"></div>
      
      <div style="margin:16px 0 10px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
        <h4 style="margin:0;">🧾 Riwayat Transaksi &amp; Pelunasan Terpadu</h4>
        <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
          <input type="text" id="fo-pay-search" class="btn btn-secondary btn-sm" placeholder="🔍 Cari QR, Kuitansi, Komoditas..." style="width:230px; text-align:left;">
          <select id="fo-pay-filter" class="btn btn-secondary btn-sm" aria-label="Saring status pembayaran">
            <option value="all">Semua Status</option>
            <option value="paid">✅ Sudah Lunas</option>
            <option value="waiting">⏳ Menunggu Pelunasan</option>
            <option value="dp">🤝 Ada Uang Muka (DP)</option>
          </select>
        </div>
      </div>
      <div id="fo-mypay-unified"><p class="muted">Memuat data pembayaran…</p></div>
    </section>
    <section class="card" aria-labelledby="fo-qc-dev-title" style="margin-top:16px;">
      <div class="card-header"><div>
        <h3 class="card-title" id="fo-qc-dev-title">⚖️ Transparansi Deviasi &amp; Refraksi Mutu</h3>
        <p class="card-sub">Perbandingan taksiran mandiri vs timbangan nyata pengepul &amp; alasan penolakan.</p></div></div>
      <div id="fo-qc-deviations"><p class="muted">Memuat…</p></div>
    </section>

    <section class="card" aria-labelledby="fo-col-rep-title" style="margin-top:16px;">
      <div class="card-header" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
        <div>
          <h3 class="card-title" id="fo-col-rep-title">⭐ Reputasi &amp; Keandalan Pengepul</h3>
          <p class="card-sub">Skor ketepatan pembayaran &amp; tempo bayar pengepul terdekat.</p>
        </div>
        <button type="button" class="btn btn-primary btn-sm" id="btn-open-rate-collector">⭐ Beri Rating Pengepul</button>
      </div>
      <div id="fo-col-reputations"><p class="muted">Memuat…</p></div>
    <section class="card" id="fo-soil-amendment-card" aria-labelledby="fo-soil-amendment-title" style="margin-top:16px;">
      <div class="card-header" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
        <div>
          <h3 class="card-title" id="fo-soil-amendment-title">🌿 Alokasi Abu Bottom Ash &amp; Evaluasi Kualitas Sirkular Sawah</h3>
          <p class="card-sub">Pemanfaatan produk sirkular kembali ke sawah: alokasi abu bottom ash bebas logam berat (Kepmentan 261/2019) untuk pembenah tanah, sementara biochar difokuskan pada material baterai.</p>
        </div>
        <button type="button" class="btn btn-primary btn-sm" id="btn-open-eval-biochar">📝 Isi Evaluasi Mutu Abu Bottom Ash</button>
      </div>

      <!-- Bagian 1: Alokasi Abu Pembenah Tanah untuk Kelompok (Poktan) -->
      <div style="margin-bottom:18px;">
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:6px; margin-bottom:10px;">
          <h4 style="margin:0; font-size:13.5px; font-weight:700; color:var(--ink); display:flex; align-items:center; gap:6px;">
            <span>🪨</span> <span>Alokasi Abu Bottom Ash Pembenah Tanah untuk Kelompok Anda</span>
          </h4>
          <span class="muted" style="font-size:11px;">Standar Uji Logam Berat: Pb, Cd, As &le; Ambang Aman</span>
        </div>
        <div id="fo-ash-container"><p class="muted" style="font-size:12px;">Memuat data alokasi abu...</p></div>
      </div>

      <!-- Bagian 2: Evaluasi & Ulasan Mutu Abu Bottom Ash Sawah -->
      <div>
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:6px; margin-bottom:10px;">
          <h4 style="margin:0; font-size:13.5px; font-weight:700; color:var(--ink); display:flex; align-items:center; gap:6px;">
            <span>🌾</span> <span>Evaluasi &amp; Ulasan Mutu Abu Bottom Ash Sawah</span>
          </h4>
          <span class="muted" style="font-size:11px;">Ukuran Butir, Kelembapan &amp; Dampak Kesuburan Tanah</span>
        </div>
        <div id="fo-biochar-evaluations"><p class="muted" style="font-size:12px;">Memuat evaluasi mutu abu bottom ash…</p></div>
      </div>
    </section>`;

  let cachedUnifiedPayments = [];

  function renderUnifiedPaymentTable() {
    if (window.FieldKuitansi && window.FieldKuitansi.renderUnifiedPaymentTable) {
      return window.FieldKuitansi.renderUnifiedPaymentTable(cachedUnifiedPayments, { H, num, rp, emptyState });
    }
  }


  async function loadPayOverview() {
    const k = $("fo-pay-kpis");
    if (!k) return;
    try {
      const [o, payments] = await Promise.all([
        api("/api/v1/farmer/payments/overview"),
        api("/api/v1/farmer/payments").catch(() => [])
      ]);
      k.innerHTML = `
        <div class="kpi-tile"><div class="kpi-lbl">Sudah diterima</div><div class="kpi-val">${rpShort(o.paid.net_rp)}</div>
          <div class="kpi-lbl">${num(o.paid.count, 0)} kuitansi</div></div>
        <div class="kpi-tile ${o.waiting.late_count ? "kpi-warn" : ""}"><div class="kpi-lbl">Menunggu dibayar</div><div class="kpi-val">${rpShort(o.waiting.net_rp)}</div>
          <div class="kpi-lbl">${num(o.waiting.count, 0)} lot${o.waiting.late_count ? ` · ${o.waiting.late_count} terlambat &gt; ${o.due_days} hari` : ""}</div></div>
        <div class="kpi-tile"><div class="kpi-lbl">Belum ditimbang</div><div class="kpi-val">${num(o.unweighed.quantity_kg, 0)} kg</div>
          <div class="kpi-lbl">${num(o.unweighed.count, 0)} laporan · harga belum final</div></div>`;

      // Build unified list
      const paidHarvestIds = new Set((payments || []).map(p => p.harvest_id));
      const combined = [];

      for (const p of (payments || [])) {
        combined.push({
          ...p,
          is_paid: true,
          status_type: "paid",
          date: p.paid_at,
        });
      }

      for (const w of (o.waiting.items || [])) {
        if (!paidHarvestIds.has(w.harvest_id)) {
          combined.push({
            harvest_id: w.harvest_id,
            origin_qr_code: w.origin_qr_code || ('WR-HV-' + w.harvest_id),
            commodity_name: w.commodity_name || 'Biomassa',
            quantity_kg: w.verified_kg,
            verified_kg: w.verified_kg,
            dp_rp: w.dp_rp || 0,
            dp_receipt_code: w.dp_receipt_code,
            receipt_code: null,
            is_paid: false,
            status_type: "waiting",
            net_rp: w.net_rp,
            gross_rp: w.gross_rp,
            collector_name: w.collector_name,
            verified_at: w.verified_at,
            date: w.verified_at,
          });
        }
      }

      for (const u of (o.unweighed.items || [])) {
        combined.push({
          harvest_id: u.harvest_id,
          origin_qr_code: u.origin_qr_code || ('WR-HV-' + u.harvest_id),
          commodity_name: u.commodity_name || 'Biomassa',
          quantity_kg: u.quantity_kg,
          dp_rp: 0,
          dp_receipt_code: null,
          receipt_code: null,
          is_paid: false,
          status_type: "unweighed",
          net_rp: 0,
          gross_rp: 0,
          collector_name: u.collector_name,
          reported_at: u.reported_at,
          date: u.reported_at,
        });
      }

      cachedUnifiedPayments = combined;
      renderUnifiedPaymentTable();

      const searchInput = $("fo-pay-search");
      if (searchInput && !searchInput._bound) {
        searchInput._bound = true;
        searchInput.oninput = renderUnifiedPaymentTable;
      }
      const filterSelect = $("fo-pay-filter");
      if (filterSelect && !filterSelect._bound) {
        filterSelect._bound = true;
        filterSelect.onchange = renderUnifiedPaymentTable;
      }
    } catch (e) {
      if (k) k.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`;
    }
  }

  // ---- Biochar untuk sawah: saldo, perkiraan manfaat (rumus sirkular), pengajuan & riwayat
  const BR_STATUS = { diajukan: "badge-amber", diserahkan: "badge-green", dibatalkan: "badge-gray" };
  async function loadBiochar() {
    const box = $("biochar-sawah");
    if (!box) return;
    try {
      const [w, reqs] = await Promise.all([api("/api/v1/farmer/wallet"), api("/api/v1/farmer/biochar/redemptions")]);
      box.innerHTML = `
        <div class="kpi-row">
          <div class="kpi-tile"><div class="kpi-lbl">Saldo Abu Bottom Ash</div><div class="kpi-val">${num(w.balance_kg, 1)} kg</div>
            <div class="kpi-lbl">hak dari biomassa yang diolah</div></div>
          <div class="kpi-tile"><div class="kpi-lbl">Potensi bisa diambil</div><div class="kpi-val">${num(w.available_kg, 1)} kg</div>
            <div class="kpi-lbl">${w.held_kg ? `${num(w.held_kg, 1)} kg sedang diajukan` : "siap diajukan"}</div></div>
          <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Sudah diambil</div><div class="kpi-val">${num(w.taken_kg || 0, 1)} kg</div>
            <div class="kpi-lbl">telah diaplikasikan ke sawah</div></div>
        </div>
        <div class="demo-hint-box" style="margin:12px 0 10px; padding:10px 14px; border-radius:8px; background:var(--surface-2); border:1px solid var(--border);">
          <div style="font-weight:700; color:var(--primary); margin-bottom:4px;">🌱 Informasi Ekonomi Sirkular Abu Bottom Ash:</div>
          <p style="margin:0; font-size:12px; line-height:1.4;" class="muted">
            Permintaan pengiriman abu bottom ash kini <b>terintegrasi langsung saat melapor biomassa</b> di modul <i>"🌾 Lapor &amp; Jual Biomassa"</i> agar armada membawa abu bottom ash muatan balik secara efisien. Tabel di bawah mencatat riwayat permohonan, nomor QR code, dan status serah terima abu bottom ash.
          </p>
        </div>
        <div id="br-list">
          ${reqs.length ? `
            <div class="table-scroll">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>No. QR Code Abu Bottom Ash</th>
                    <th>No. Lapor &amp; Kirim Asal</th>
                    <th class="num">Jumlah (kg)</th>
                    <th>Luas Sawah</th>
                    <th>Titik Serah Terima</th>
                    <th>Waktu Lapor/Kirim</th>
                    <th>Status</th>
                    <th>Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  ${reqs.map(x => `
                    <tr>
                      <td>
                        <code style="font-family:monospace; font-weight:700; color:var(--primary); font-size:12px;">${H(x.request_code || ('BCR-REQ-' + x.id))}</code>
                        <button type="button" class="btn btn-secondary btn-sm" style="padding:1px 5px; font-size:9px; height:18px; margin-left:4px;" data-onclick="openModal('QR Code Abu Bottom Ash Sawah', '${H(x.request_code || ('BCR-REQ-' + x.id))}', 'Nomor permohonan muatan balik abu bottom ash')">📱 QR</button>
                      </td>
                      <td>
                        <code>${H(x.harvest_qr || ('WR-HV-' + (x.harvest_id || x.id)))}</code>
                      </td>
                      <td class="num"><b>${num(x.kg, 1)} kg</b></td>
                      <td>${x.land_area_ha ? `${num(x.land_area_ha, 2)} ha` : '-'}</td>
                      <td>${H(x.pickup_point || x.delivery_point || '-')}</td>
                      <td>${formatDateTime(x.created_at)}</td>
                      <td><span class="badge ${BR_STATUS[x.status] || ''}">${H(x.status)}</span></td>
                      <td>
                        ${x.status === "diajukan" ? `<button type="button" class="btn btn-secondary btn-sm" data-br-cancel="${Number(x.id)}">Batal</button>` : `<span class="muted" style="font-size:11px;">–</span>`}
                      </td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          ` : emptyState("🌱", "Belum ada riwayat abu bottom ash", "Pesan abu bottom ash muatan balik saat melapor biomassa pada formulir di atas.")}
        </div>
      `;
    } catch (e) {
      box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`;
    }
  }

  // ---- Laporan bulanan petani: kurva umpan balik mutu & defect rate
  let qChart = null;
  window.renderQualityFeedback = async function () {
    const sec = $("rp-quality");
    if (!sec) return;
    const role = (STATE.user || {}).role;
    sec.hidden = role !== "petani";
    if (role !== "petani") return;
    try {
      const f = await api("/api/v1/farmer/quality-feedback?months=6");
      const last = [...f.series].reverse().find(x => x.lots_assessed) || {};
      $("rp-q-kpis").innerHTML = `
        <div class="kpi-tile"><div class="kpi-lbl">Skor QC pengepul (bulan terakhir)</div><div class="kpi-val">${last.collector_qc_score != null ? num(last.collector_qc_score, 1) : "–"}</div><div class="kpi-lbl">skala 100</div></div>
        <div class="kpi-tile"><div class="kpi-lbl">Skor QC pabrik</div><div class="kpi-val">${last.factory_qc_score != null ? num(last.factory_qc_score, 1) : "–"}</div><div class="kpi-lbl">muatan gabungan</div></div>
        <div class="kpi-tile ${f.summary.defect_rate_pct > 5 ? "kpi-danger" : ""}"><div class="kpi-lbl">Defect rate 6 bulan</div><div class="kpi-val">${f.summary.defect_rate_pct != null ? num(f.summary.defect_rate_pct, 1) + "%" : "–"}</div>
          <div class="kpi-lbl">${num(f.summary.defect_lots, 0)} dari ${num(f.summary.lots_assessed, 0)} lot</div></div>`;
      if (typeof Chart !== "undefined") {
        if (qChart) qChart.destroy();
        qChart = new Chart($("rp-q-chart"), { data: { labels: f.months, datasets: [
          { type: "line", label: "Skor QC pengepul", data: f.series.map(x => x.collector_qc_score), borderColor: "#15803d", spanGaps: true, yAxisID: "y" },
          { type: "line", label: "Skor QC pabrik", data: f.series.map(x => x.factory_qc_score), borderColor: "#2563eb", borderDash: [6, 4], spanGaps: true, yAxisID: "y" },
          { type: "bar", label: "Defect rate (%)", data: f.series.map(x => x.defect_rate_pct), backgroundColor: "#dc262699", yAxisID: "y1" },
        ] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } },
          scales: { y: { min: 0, max: 100, title: { display: true, text: "skor" } },
                    y1: { position: "right", beginAtZero: true, grid: { drawOnChartArea: false }, title: { display: true, text: "% lot cacat" } } } } });
      }
      $("rp-q-causes").innerHTML = f.causes.length ? `<h4 style="margin:0 0 8px;">Penyebab cacat &amp; cara memperbaiki</h4>
        <div class="table-scroll"><table class="data-table"><thead><tr><th>Penyebab</th><th class="num">Lot</th><th>Saran</th></tr></thead><tbody>
        ${f.causes.map(c => `<tr><td><b>${H(c.label)}</b></td><td class="num">${num(c.lots, 0)}</td><td>${H(c.tip || "-")}</td></tr>`).join("")}</tbody></table></div>
        <p class="kpi-lbl">${f.notes.map(H).join(" · ")}</p>`
        : `<p class="muted">✅ Tidak ada lot cacat dalam 6 bulan terakhir.</p>`;
    } catch (e) { $("rp-q-causes").innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  };

  async function loadMyPayments() {
    // Data pembayaran terpadu dimuat bersamaan dalam loadPayOverview()
    if (!cachedUnifiedPayments.length) {
      loadPayOverview();
    }
  }

  // ================================================================ SEMUA PERAN: Data saya (PDP) & ganti password
  async function openPrivacy() {
    let c;
    try { c = await api("/api/v1/me/consents"); } catch (e) { return showToast(e.message, "❌"); }
    const rows = c.purposes.map(p => `
      <label class="fo-check"><input type="checkbox" name="${H(p.purpose)}" ${p.granted ? "checked" : ""}
        ${p.purpose === "layanan_inti" ? "required" : ""}> ${H(p.description)}${p.purpose === "layanan_inti" ? " <b>(wajib)</b>" : ""}</label>`).join("");
    formDialog({
      title: "🔒 Data pribadi saya", ok: "Simpan persetujuan",
      body: `<p class="ui-confirm-body">Sesuai UU 27/2022 Pelindungan Data Pribadi. Versi kebijakan ${H(c.version)}.</p>
             ${rows}
             <div class="fo-actions">
               <button type="button" class="btn btn-secondary btn-sm" id="fo-export">⬇️ Unduh data saya</button>
               <button type="button" class="btn btn-secondary btn-sm" id="fo-delete">🗑️ Hapus akun & data saya</button>
               <button type="button" class="btn btn-secondary btn-sm" id="fo-chpw">🔑 Ganti password</button>
             </div>`,
      onSubmit: async (fd) => {
        const choices = Object.fromEntries(c.purposes.map(p => [p.purpose, fd.get(p.purpose) === "on"]));
        await api("/api/v1/me/consents", { body: { choices } });
        showToast("Persetujuan tersimpan.", "🔒");
        syncConsentBanner();
      },
    });
    $("fo-export").onclick = exportMyData;
    $("fo-delete").onclick = deleteMe;
    $("fo-chpw").onclick = () => changePassword(false);
  }

  async function exportMyData() {
    try {
      await apiDownload("/api/v1/me/data-export", `biochain-data-saya-${(STATE.user || {}).user_id || "akun"}.json`);
      showToast("Data Anda diunduh (JSON).", "📄");
    } catch (e) { showToast("Gagal mengunduh: " + e.message, "❌"); }
  }

  function deleteMe() {
    formDialog({
      title: "Hapus akun & data saya?", ok: "Hapus permanen", danger: true,
      body: `<p class="ui-confirm-body">Nama, nomor HP, username dan lokasi Anda dihapus permanen dan akun ditutup.
               Catatan timbangan, pembayaran & biochar tetap disimpan <b>tanpa identitas</b> untuk kewajiban audit/pajak.</p>
             <div class="form-group"><label for="fo-del-pw">Ketik password untuk konfirmasi</label>
               <input id="fo-del-pw" name="password" type="password" required autocomplete="current-password"></div>
             <div class="form-group"><label for="fo-del-why">Alasan (opsional)</label>
               <input id="fo-del-why" name="reason" maxlength="500"></div>`,
      onSubmit: async (fd) => {
        const r = await api("/api/v1/me/delete", { body: { password: fd.get("password"), reason: fd.get("reason") || null } });
        document.querySelectorAll("dialog").forEach(x => x.close());
        if (typeof logout === "function") logout(`Akun dihapus. Tanda terima: ${r.receipt_code}`);
      },
    });
  }

  function changePassword(forced) {
    formDialog({
      title: forced ? "Ganti password sementara" : "Ganti password", ok: "Ganti password",
      body: `${forced ? `<p class="ui-confirm-body">Password Anda baru direset admin. Buat password baru sebelum melanjutkan.</p>` : ""}
             <div class="form-group"><label for="fo-pw-old">Password ${forced ? "sementara" : "lama"}</label>
               <input id="fo-pw-old" name="old" type="password" required autocomplete="current-password"></div>
             <div class="form-group"><label for="fo-pw-new">Password baru (min. 6 karakter)</label>
               <input id="fo-pw-new" name="new" type="password" required minlength="6" autocomplete="new-password"></div>`,
      onSubmit: async (fd) => {
        const r = await api("/api/v1/auth/change-password", { body: { old_password: fd.get("old"), new_password: fd.get("new") } });
        if (r.access_token) { STATE.token = r.access_token; try { localStorage.setItem("biochain_token", r.access_token); } catch {} }
        if (STATE.user) { STATE.user.must_change_password = false; try { localStorage.setItem("biochain_user", JSON.stringify(STATE.user)); } catch {} }
        showToast("Password diganti.", "🔑");
      },
    });
  }

  // Banner persetujuan untuk akun lama (non-blokir agar alur kerja tidak terhenti)
  async function syncConsentBanner() {
    const host = $("persona-content");
    if (!host || !STATE.user) return;
    let el = $("fo-consent-banner");
    try {
      const c = await api("/api/v1/me/consents");
      if (!c.needs_consent) { if (el) el.remove(); return; }
      if (!el) {
        el = document.createElement("div");
        el.id = "fo-consent-banner";
        el.className = "banner banner-info";
        el.setAttribute("role", "status");
        el.innerHTML = `<span aria-hidden="true">🔒</span><span>Mohon tinjau & setujui pemakaian data pribadi Anda (UU PDP).</span>
          <button type="button" class="btn btn-secondary btn-sm">Tinjau</button>`;
        el.querySelector("button").onclick = openPrivacy;
        host.parentElement.insertBefore(el, host);
      }
    } catch { /* offline: coba lagi saat render berikutnya */ }
  }

  // ================================================================ abu untuk Poktan (018)
  async function loadGroupAsh() {
    const box = $("fo-ash-container");
    if (!box) return;
    try {
      const rows = await api("/api/v1/farmer/ash");
      if (!rows || !rows.length) {
        box.innerHTML = `<div class="muted" style="font-size:12px; padding:10px 14px; background:var(--surface-2); border-radius:8px; border:1px dashed var(--border);">
          Belum ada alokasi abu boiler untuk kelompok tani Anda pada siklus panen ini. Seluruh abu pabrik yang lolos uji batas logam berat (Pb, Cd, As — Kepmentan 261/2019) akan otomatis terdata di sini untuk diserahkan ke sawah.
        </div>`;
        return;
      }
      box.innerHTML = `
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>Kode</th>
                <th>Jenis Abu</th>
                <th class="num">Jumlah (kg)</th>
                <th>Hasil Uji Lab Logam Berat</th>
                <th>Status Penyerahan</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map(a => `
                <tr>
                  <td><code>${H(a.code)}</code></td>
                  <td><b>${H(a.ash_type.replace("_", " ").toUpperCase())}</b></td>
                  <td class="num"><b>${num(a.quantity_kg, 0)} kg</b></td>
                  <td class="kpi-lbl">Pb ${num(a.metals_ppm.pb, 1)} · Cd ${num(a.metals_ppm.cd, 2)} · As ${num(a.metals_ppm.as, 1)} mg/kg<br><span class="muted">${H(a.lab_report_no || "Lolos Uji Sucofindo")}</span></td>
                  <td><span class="badge ${a.status === "diserahkan" ? "badge-green" : "badge-blue"}">${H(a.status)}</span></td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `;
    } catch {
      box.innerHTML = `<div class="muted" style="font-size:12px; padding:8px;">Data abu kelompok siap diakses saat online.</div>`;
    }
  }

  // ================================================================ gudang (018)
  const MV_LABEL = { masuk: "Masuk (beli/terima)", keluar: "Keluar (kirim ke pabrik)", susut: "Susut / rusak" };
  let whCache = [];

  async function loadWarehouses() {
    try {
      whCache = await api("/api/v1/collector/warehouses");
      const names = Object.fromEntries((typeof biomassList === "function" ? await biomassList() : []).map(b => [b.code, b.name]));
      const queued = myOutbox().filter(i => /\/collector\/warehouses\/\d+\/movements$/.test(i.path)).length;
      const box = $("fo-wh");
      if (!box) return;
      box.innerHTML = (queued ? `<div class="banner banner-warning" role="status">📵 ${queued} mutasi stok menunggu sinyal</div>` : "")
        + (whCache.length ? whCache.map(w => `<div class="card" style="margin:8px 0; padding:12px;">
            <div style="display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap; align-items:center;">
              <b>${H(w.name)}</b> ${w.is_covered ? "" : '<span class="badge badge-amber" title="Musim hujan: biomassa terbuka cepat basah">tanpa atap</span>'}
              <button type="button" class="btn btn-primary btn-sm" data-fo-mv="${Number(w.id)}">± Catat stok</button></div>
            ${w.stock.length ? `<div class="table-scroll"><table class="data-table"><thead><tr><th>Komoditas</th>
              <th class="num">Timbang (kg)</th><th class="num">Berat bayar (kg)</th></tr></thead><tbody>${w.stock.map(st => `<tr>
              <td>${H(names[st.commodity] || st.commodity)}</td><td class="num">${num(st.gross_kg, 0)}</td>
              <td class="num">${num(st.payable_kg, 0)}</td></tr>`).join("")}</tbody></table></div>`
              : `<p class="kpi-lbl">Belum ada stok.</p>`}</div>`).join("")
          : emptyState("🏚️", "Belum ada gudang", "Tambahkan gudang untuk mencatat stok per komoditas."));
    } catch (e) {
      const box = $("fo-wh");
      if (box) box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`;
    }
  }

  function newWarehouse() {
    formDialog({
      title: "Gudang baru", ok: "Simpan",
      body: `<div class="form-group"><label for="fo-wh-name">Nama gudang</label><input id="fo-wh-name" name="name" required minlength="2" maxlength="80"></div>
             <div class="form-group"><label for="fo-wh-cap">Kapasitas (m³, opsional)</label><input id="fo-wh-cap" name="cap" type="number" min="1" step="1"></div>
             <label style="display:flex; gap:8px; align-items:center;"><input type="checkbox" name="covered" checked> Beratap</label>`,
      onSubmit: async (fd) => {
        let pos = null;
        try { pos = await new Promise((ok, no) => navigator.geolocation.getCurrentPosition(p => ok(p.coords), no, { timeout: 2000, maximumAge: 60000 })); } catch {}
        await api("/api/v1/collector/warehouses", { body: { name: fd.get("name"), capacity_m3: Number(fd.get("cap")) || null,
          is_covered: fd.get("covered") === "on", lat: pos ? pos.latitude : null, lon: pos ? pos.longitude : null } });
        showToast("Gudang ditambahkan", "🏚️"); loadWarehouses();
      },
    });
  }

  async function movementDialog(whId) {
    const d = formDialog({
      title: `Catat stok · ${(whCache.find(w => w.id === whId) || {}).name || ""}`, ok: "Simpan",   // formDialog meng-escape judul
      body: `<div class="form-group"><label for="fo-mv-kind">Jenis</label><select id="fo-mv-kind" name="movement">
               ${Object.entries(MV_LABEL).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></div>
             <div class="form-group"><label for="fo-mv-com">Komoditas</label><select id="fo-mv-com" name="commodity">${await commodityOptions()}</select></div>
             <div class="form-group"><label for="fo-mv-kg">Berat timbang (kg)</label><input id="fo-mv-kg" name="kg" type="number" min="1" step="0.1" required inputmode="decimal"></div>
             <div class="form-group fo-mv-q"><label for="fo-mv-mc">Kadar air (%) — moisture meter</label><input id="fo-mv-mc" name="moisture_pct" type="number" min="0" max="95" step="0.1" inputmode="decimal"></div>
             <div class="form-group fo-mv-q"><label for="fo-mv-ct">Kotoran tanah/batu (%)</label><input id="fo-mv-ct" name="contaminant_pct" type="number" min="0" max="100" step="0.1" inputmode="decimal"></div>
             <label class="fo-mv-q" style="display:flex; gap:8px; align-items:center;"><input type="checkbox" name="accept_wet"> Terima basah (saya keringkan sendiri)</label>
             <div id="fo-mv-prev" class="kpi-lbl" aria-live="polite"></div>`,
      onSubmit: async (fd) => {
        const body = { commodity: fd.get("commodity"), movement: fd.get("movement"), kg: Number(fd.get("kg")),
                       moisture_pct: fd.get("moisture_pct") === "" ? null : Number(fd.get("moisture_pct")),
                       contaminant_pct: fd.get("contaminant_pct") === "" ? null : Number(fd.get("contaminant_pct")),
                       accept_wet: fd.get("accept_wet") === "on" };
        const r = await apiMutation(`/api/v1/collector/warehouses/${whId}/movements`, body, `Stok ${body.movement} ${body.kg} kg`);
        showToast(r.queued ? "Offline: mutasi disimpan & dikirim saat ada sinyal." :
          `Tercatat · bayar ${num(Math.abs(r.payable_kg), 1)} kg${r.value_rp ? ` ≈ ${rp(r.value_rp)}` : ""}`, r.queued ? "📵" : "✅");
        loadWarehouses();
      },
    });
    const prev = async () => {
      const f = d.querySelector("form"), kind = f.movement.value;
      d.querySelectorAll(".fo-mv-q").forEach(el => { el.hidden = kind !== "masuk"; });
      const box = d.querySelector("#fo-mv-prev");
      if (kind !== "masuk" || !Number(f.kg.value) || navigator.onLine === false) { box.textContent = ""; return; }
      try {
        const r = await api("/api/v1/collector/refraction-preview", { body: { commodity: f.commodity.value, kg: Number(f.kg.value),
          moisture_pct: f.moisture_pct.value === "" ? null : Number(f.moisture_pct.value),
          contaminant_pct: f.contaminant_pct.value === "" ? null : Number(f.contaminant_pct.value), accept_wet: f.accept_wet.checked } });
        box.innerHTML = r.accepted
          ? `Berat bayar <b>${num(r.payable_kg, 1)} kg</b> (potong ${num(r.refraction_kg, 1)} kg · acuan air ${num(r.basis.moisture_ref_pct, 0)}%)`
            + (r.value_rp != null ? ` ≈ <b>${rp(r.value_rp)}</b>` : " · harga dasar belum diisi pabrik")
          : `⛔ ${H(r.reason)}`;
      } catch { box.textContent = ""; }
    };
    d.querySelector("form").addEventListener("input", prev);
    prev();
  }

  // ---- Omni 022: QC Deviations, Reputations, Receivables, Consolidated Routing
  let cachedQcDevRows = [];
  async function loadQcDeviations() {
    const box = $("fo-qc-deviations");
    if (!box) return;
    try {
      const rows = await api("/api/v1/farmer/qc-deviations");
      cachedQcDevRows = rows;
      box.innerHTML = rows.length ? `<div class="table-scroll"><table class="data-table"><thead><tr>
        <th>No. QR Code Ketelusuran</th><th>Komoditas Biomassa</th><th>Klaim Petani</th><th>Timbangan Pengepul</th><th>Deviasi &amp; Refraksi</th><th>Status QC</th><th>Aksi</th></tr></thead><tbody>
        ${rows.map(r => `<tr>
          <td>
            <div style="font-family:monospace; font-weight:700; color:var(--primary); font-size:12px; display:flex; align-items:center; gap:4px;">
              <span>🌾 ${H(r.origin_qr_code || r.qr_code || ('WR-HV-' + r.harvest_id))}</span>
              <button type="button" class="btn btn-secondary btn-sm" style="padding:1px 5px; font-size:9px; height:18px;" data-onclick="openModal('QR Code Lot Petani', '${H(r.origin_qr_code || r.qr_code || ('WR-HV-' + r.harvest_id))}', 'Kode batch biomassa asal petani')">📱 QR</button>
            </div>
            <small class="muted" style="font-size:10px;">Lot #${Number(r.harvest_id)}</small>
            ${r.trx_code ? `<br><span class="badge badge-purple" style="font-size:9px;">🏪 ${H(r.trx_code)}</span>` : ''}
          </td>
          <td><b>${H(r.commodity_name || r.commodity)}</b></td>
          <td>
            <b>${num(r.farmer_claimed_qty, 1)} kg</b>
            ${r.farmer_moisture_est != null ? `<br><small class="muted">Air ~${r.farmer_moisture_est}%</small>` : ''}
            ${r.farmer_grade_est ? `<br><small class="muted">Grade ~${r.farmer_grade_est}</small>` : ''}
          </td>
          <td>
            <b>${r.actual_weighed_qty ? `${num(r.actual_weighed_qty, 1)} kg` : "-"}</b>
            ${r.verified_moisture != null ? `<br><small class="muted">Air ${r.verified_moisture}%</small>` : ''}
            ${r.verified_grade ? `<br><small class="muted">Grade ${r.verified_grade}</small>` : ''}
          </td>
          <td>${r.deviation_kg !== null && r.deviation_kg !== undefined ? `<span style="color:${r.deviation_kg < 0 ? 'var(--warn)' : 'var(--green)'}; font-weight:700;">${r.deviation_kg > 0 ? "+" : ""}${num(r.deviation_kg, 1)} kg (${r.deviation_pct > 0 ? "+" : ""}${num(r.deviation_pct, 1)}%)</span>` : "-"}</td>
          <td><span class="badge ${r.qc_status === 'PASS' ? 'badge-green' : r.qc_status === 'REJECT' ? 'badge-red' : 'badge-amber'}">${H(r.qc_status)}</span>${r.qc_rejection_reason ? `<br><span class="kpi-lbl">${H(r.qc_rejection_reason)}</span>` : ""}</td>
          <td><button type="button" class="btn btn-secondary btn-sm" data-fo-dev-detail="${Number(r.harvest_id)}">🔍 Ketelusuran Mutu</button></td>
        </tr>`).join("")}
      </tbody></table></div>` : emptyState("⚖️", "Belum ada riwayat penimbangan", "Data deviasi timbangan dan hasil QC akan tampil otomatis saat pengepul memproses biomassa Anda.");
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  function showQcDetailModal(harvestId) {
    const r = cachedQcDevRows.find(x => x.harvest_id == harvestId);
    if (!r) return;
    const devColor = (r.deviation_kg || 0) < 0 ? 'var(--warn)' : 'var(--green)';
    formDialog({
      title: `🔍 Ketelusuran Mutu & Refraksi Lot #${r.harvest_id}`,
      ok: "Tutup",
      body: `
        <div style="font-size:12.5px; line-height:1.5;">
          <div style="background:var(--surface-2); padding:10px 14px; border-radius:8px; margin-bottom:12px; border:1px solid var(--border);">
            <div>• <b>Kode QR Batch Asal:</b> <code style="color:var(--primary); font-weight:700;">${H(r.origin_qr_code || r.qr_code || ('WR-HV-' + r.harvest_id))}</code></div>
            <div>• <b>Resi Serah Terima (TRX):</b> <code>${H(r.trx_code || 'Belum Diterbitkan Pengepul')}</code></div>
            <div>• <b>Komoditas:</b> <b>${H(r.commodity_name || r.commodity)}</b> · Skema: ${H(r.delivery_scheme || 'Jemput')}</div>
            <div>• <b>Waktu Dilaporkan:</b> ${formatDateTime(r.reported_at)}</div>
            <div>• <b>Waktu Diverifikasi:</b> ${formatDateTime(r.verified_at)}</div>
          </div>

          <h4 style="margin:10px 0 6px;">⚖️ Perbandingan Data Timbangan &amp; Mutu:</h4>
          <table class="data-table" style="margin-bottom:12px;">
            <thead><tr><th>Parameter</th><th>Klaim Mandiri Petani</th><th>Hasil Uji Pengepul</th><th>Selisih / Deviasi</th></tr></thead>
            <tbody>
              <tr>
                <td><b>Berat Tonase (kg)</b></td>
                <td>${num(r.farmer_claimed_qty, 1)} kg</td>
                <td><b>${r.actual_weighed_qty ? num(r.actual_weighed_qty, 1) + ' kg' : '-'}</b></td>
                <td><b style="color:${devColor};">${r.deviation_kg != null ? (r.deviation_kg > 0 ? '+' : '') + num(r.deviation_kg, 1) + ' kg (' + (r.deviation_pct > 0 ? '+' : '') + num(r.deviation_pct, 1) + '%)' : '-'}</b></td>
              </tr>
              <tr>
                <td><b>Kadar Air (% bb)</b></td>
                <td>${r.farmer_moisture_est != null ? num(r.farmer_moisture_est, 1) + '%' : '<span class="muted">Tidak diisi</span>'}</td>
                <td><b>${r.verified_moisture != null ? num(r.verified_moisture, 1) + '%' : '-'}</b></td>
                <td>${(r.verified_moisture != null && r.farmer_moisture_est != null) ? `${num(r.verified_moisture - r.farmer_moisture_est, 1)}%` : '-'}</td>
              </tr>
              <tr>
                <td><b>Grade Mutu</b></td>
                <td>${r.farmer_grade_est ? 'Grade ' + r.farmer_grade_est : '<span class="muted">Tidak diisi</span>'}</td>
                <td><b>${r.verified_grade ? 'Grade ' + r.verified_grade : '-'}</b></td>
                <td><span class="badge ${r.qc_status === 'PASS' ? 'badge-green' : 'badge-red'}">${H(r.qc_status)}</span></td>
              </tr>
            </tbody>
          </table>

          <div style="background:var(--surface-2); padding:10px 14px; border-radius:8px; border:1px solid var(--border);">
            <div style="font-weight:700; color:var(--primary); margin-bottom:4px;">📋 Catatan QC &amp; Refraksi Harga:</div>
            <div>${H(r.qc_rejection_reason || 'Mutu biomassa prima dan memenuhi syarat serah terima industri tanpa refraksi berat berlebih.')}</div>
          </div>
        </div>
      `,
      onSubmit: async () => false
    });
  }

  async function loadCollectorReputations() {
    const box = $("fo-col-reputations");
    if (!box) return;
    try {
      const rows = await api("/api/v1/farmer/collector-reputations");
      box.innerHTML = rows.length ? `<div class="table-scroll"><table class="data-table"><thead><tr>
        <th>Pengepul</th><th>Kecamatan</th><th>Tepat Waktu</th><th>Rating</th><th>Trust</th></tr></thead><tbody>
        ${rows.map(c => `<tr>
          <td><b>${H(c.collector_name)}</b><br><span class="kpi-lbl">${c.total_transactions} transaksi</span></td>
          <td>${H(c.kecamatan || "-")}</td>
          <td><b style="color:var(--green);">${num(c.on_time_settlement_rate, 1)}%</b></td>
          <td>⭐ ${num(c.punctuality_rating, 1)} / 5.0</td>
          <td><span class="badge badge-green">${H(c.trust_badge)}</span></td>
        </tr>`).join("")}
      </tbody></table></div>` : emptyState("⭐", "Belum ada scorecard", "Scorecard keandalan pengepul akan dihitung dari riwayat penyelesaian transaksi.");
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  async function loadFactoryReceivables() {
    const box = $("fo-factory-receivables");
    if (!box) return;
    try {
      const res = await api("/api/v1/collector/factory-receivables");
      if (!res.items || !res.items.length) {
        box.innerHTML = emptyState("🏭", "Tidak ada piutang aktif", "Seluruh pengiriman ke pabrik telah lunas terbayar.");
        return;
      }
      
      const monthGroups = {};
      res.items.forEach(i => {
        const meta = (typeof window.getMonthYearMeta === "function")
          ? window.getMonthYearMeta(i.created_at || i.delivered_at)
          : { key: "2026-10", label: "Oktober 2026", shortLabel: "Okt 2026" };
        if (!monthGroups[meta.key]) {
          monthGroups[meta.key] = { meta, items: [], totalRp: 0, totalKg: 0 };
        }
        monthGroups[meta.key].items.push(i);
        monthGroups[meta.key].totalRp += (Number(i.amount_rp) || 0);
        monthGroups[meta.key].totalKg += (Number(i.quantity_kg) || 0);
      });
      
      const sortedKeys = Object.keys(monthGroups).sort().reverse();
      
      let html = `<p class="kpi-lbl">Total Piutang Belum Terbayar: <b style="color:var(--green); font-size:1.1em;">${rp(res.total_unpaid_rp)}</b> (${res.pending_invoices_count} pengiriman)</p>`;
      
      sortedKeys.forEach((key, idx) => {
        const g = monthGroups[key];
        const isOpen = idx === 0 ? "open" : "";
        html += `
          <details class="month-group-card" ${isOpen} style="margin-bottom:12px; border:1px solid var(--border); border-radius:10px; overflow:hidden; background:var(--surface-1);">
            <summary style="cursor:pointer; padding:10px 14px; background:var(--surface-2); font-weight:700; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span>📅 ${H(g.meta.label)}</span>
                <span class="badge badge-purple">${g.items.length} Pengiriman</span>
                <span class="badge badge-green">${num(g.totalKg, 0)} kg</span>
              </div>
              <div style="display:flex; align-items:center; gap:8px;">
                <b style="color:var(--green); font-size:1.05rem;">${rp(g.totalRp)}</b>
                <span class="btn btn-secondary btn-sm" style="font-size:11px; padding:2px 8px;">Detail ▾</span>
              </div>
            </summary>
            <div class="table-scroll" style="margin:0;">
              <table class="data-table">
                <thead><tr><th>Kode DR</th><th>Pabrik</th><th class="num">Net (kg)</th><th class="num">Tagihan (Rp)</th><th>Umur Piutang</th><th>Status</th></tr></thead>
                <tbody>
                  ${g.items.map(i => `
                    <tr>
                      <td><code>${H(i.request_code)}</code></td>
                      <td>${H(i.factory_name)}</td>
                      <td class="num">${num(i.quantity_kg, 0)}</td>
                      <td class="num"><b style="color:var(--primary);">${rp(i.amount_rp)}</b></td>
                      <td>${i.days_outstanding} hari</td>
                      <td><span class="badge ${i.is_settled ? 'badge-green' : 'badge-amber'}">${H(i.status)}</span></td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          </details>
        `;
      });
      box.innerHTML = html;
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  // ================================================================
  // 6. MODAL OPTIMASI & ANALISIS TEKNIS RUTE (Extracted to app/static/js/modules/route-optimization-modal.js)
  // ================================================================

  async function openCollectorRatingModal() {
    let collectors = [];
    try {
      collectors = await api("/api/v1/farmer/collector-reputations");
    } catch (_) {}
    const optionsHtml = (collectors && collectors.length)
      ? collectors.map(c => `<option value="${c.collector_id}">${H(c.collector_name)} (${H(c.kecamatan || "Pengepul")})</option>`).join("")
      : `<option value="3">Pak Ahmad (KUD Tani Makmur Sleman)</option>`;

    formDialog({
      title: "⭐ Beri Rating & Ulasan Kinerja Pengepul",
      ok: "Kirim Rating Pengepul",
      body: `
        <div class="form-group">
          <label for="cr-collector-id">Pilih Pengepul Spesialis</label>
          <select id="cr-collector-id" name="collector_id" required>
            ${optionsHtml}
          </select>
        </div>
        <div class="form-group">
          <label for="cr-punc">Rating Ketepatan Waktu Penjemputan (1-5 Bintang)</label>
          <input type="number" id="cr-punc" name="punctuality_rating" min="1" max="5" value="5" required>
        </div>
        <div class="form-group">
          <label for="cr-pay">Rating Performa &amp; Kecepatan Pembayaran (1-5 Bintang)</label>
          <input type="number" id="cr-pay" name="payment_rating" min="1" max="5" value="5" required>
        </div>
        <div class="form-group">
          <label for="cr-review">Ulasan Singkat</label>
          <textarea id="cr-review" name="review_text" rows="2" placeholder="Pengepul datang tepat waktu dan pembayaran langsung diselesaikan."></textarea>
        </div>
      `,
      onSubmit: async (fd) => {
        await api("/api/v1/farmer/collector-ratings", {
          method: "POST",
          body: {
            collector_id: Number(fd.get("collector_id")),
            punctuality_rating: Number(fd.get("punctuality_rating")),
            payment_rating: Number(fd.get("payment_rating")),
            review_text: fd.get("review_text") || null,
          }
        });
        showToast("Rating kinerja pengepul berhasil dicatat!", "⭐");
        loadCollectorReputations();
      }
    });
  }

  function openBiocharEvaluationModal() {
    formDialog({
      title: "🌿 Evaluasi Mutu Abu Bottom Ash (Pembenah Tanah Sawah)",
      ok: "Kirim Evaluasi Mutu",
      body: `
        <div class="form-group">
          <label for="be-batch">Kode Batch / ID Alokasi Abu Bottom Ash</label>
          <input type="text" id="be-batch" name="batch_code" value="ASH-SAWAH-01" required>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
          <div class="form-group">
            <label for="be-mesh">Ukuran Butir / Mesh (1-5)</label>
            <input type="number" id="be-mesh" name="mesh" min="1" max="5" value="5" required>
          </div>
          <div class="form-group">
            <label for="be-mat">Kadar Kalsinasi / Kematangan (1-5)</label>
            <input type="number" id="be-mat" name="maturity" min="1" max="5" value="5" required>
          </div>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
          <div class="form-group">
            <label for="be-moist">Kadar Kelembapan (1-5)</label>
            <input type="number" id="be-moist" name="moisture" min="1" max="5" value="5" required>
          </div>
          <div class="form-group">
            <label for="be-soil">Dampak Kesuburan Tanah (1-5)</label>
            <input type="number" id="be-soil" name="soil" min="1" max="5" value="5" required>
          </div>
        </div>
        <div class="form-group">
          <label for="be-notes">Catatan Dampak Pada Lahan / Tanaman</label>
          <textarea id="be-notes" name="notes" rows="2" placeholder="Tanah sawah lebih gembur dan daya ikat air meningkat pesat."></textarea>
        </div>
      `,
      onSubmit: async (fd) => {
        await api("/api/v1/farmer/biochar-evaluations", {
          method: "POST",
          body: {
            batch_code: fd.get("batch_code"),
            grain_size_mesh_rating: Number(fd.get("mesh")),
            pyrolysis_maturity_rating: Number(fd.get("maturity")),
            moisture_rating: Number(fd.get("moisture")),
            soil_impact_rating: Number(fd.get("soil")),
            review_notes: fd.get("notes") || null,
          }
        });
        showToast("Evaluasi kualitas abu bottom ash berhasil dicatat!", "🌿");
        loadBiocharEvaluations();
      }
    });
  }

  async function loadBiocharEvaluations() {
    const box = $("fo-biochar-evaluations");
    if (!box) return;
    try {
      const rows = await api("/api/v1/farmer/biochar-evaluations");
      box.innerHTML = rows.length ? `<div class="table-scroll"><table class="data-table"><thead><tr>
        <th>Batch / Alokasi</th><th>Skor Total</th><th>Mesh</th><th>Kalsinasi</th><th>Kelembapan</th><th>Dampak Tanah</th><th>Catatan</th></tr></thead><tbody>
        ${rows.map(e => `<tr>
          <td><code>${H(e.batch_code || `#${e.biochar_request_id || '-'}`)}</code></td>
          <td><b style="color:var(--green); font-size:1.05em;">⭐ ${num(e.overall_score, 1)} / 5.0</b></td>
          <td>${e.grain_size_mesh_rating}/5</td>
          <td>${e.pyrolysis_maturity_rating}/5</td>
          <td>${e.moisture_rating}/5</td>
          <td>${e.soil_impact_rating}/5</td>
          <td><small>${H(e.review_notes || '-')}</small></td>
        </tr>`).join("")}
      </tbody></table></div>` : emptyState("🌿", "Belum ada evaluasi mutu abu bottom ash", "Klik tombol di atas untuk mengisi ulasan abu bottom ash yang telah diaplikasikan ke lahan sawah.");
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  // ================================================================ sambungan ke dashboard
  window.renderFieldExtras = function (role, container) {
    if (!container) return;
    if (role === "pengepul") {
      container.insertAdjacentHTML("beforeend", PENGEPUL_HTML);
      $("fo-proxy-new").onclick = newProxyFarmer;
      $("fo-wh-new").onclick = newWarehouse;
      if ($("fo-plan-route-btn")) $("fo-plan-route-btn").onclick = openConsolidatedRoutePlanner;
      loadProxyFarmers(); loadUnpaid(); loadCharges(); loadWarehouses(); loadFactoryReceivables();
      renderCollectorGateFeedback(container);
    } else if (role === "petani") {
      container.insertAdjacentHTML("beforeend", PETANI_HTML);
      loadPayOverview(); loadMyPayments(); loadBiochar(); loadGroupAsh();
      loadQcDeviations(); loadCollectorReputations(); loadBiocharEvaluations();
      if ($("btn-open-rate-collector")) $("btn-open-rate-collector").onclick = openCollectorRatingModal;
      if ($("btn-open-eval-biochar")) $("btn-open-eval-biochar").onclick = openBiocharEvaluationModal;
    }
    else if (role === "pabrik" || role === "admin") {
      renderFactoryGateQC(container);
    }
  };
  window.renderFactoryExtras = function (container) {
    renderFactoryGateQC(container);
  };
  // Semua peran, setelah login: wajib ganti password (F6) & banner persetujuan PDP (F12)
  window.afterLoginChecks = function () {
    if (STATE.user && STATE.user.must_change_password) changePassword(true);
    setTimeout(syncConsentBanner, 600);                 // tunggu persona-content dirender
  };
  window.openPrivacy = openPrivacy;
  window.showFarmerContact = showContact;
  window.showQcDetailModal = showQcDetailModal;

  document.addEventListener("click", (e) => {
    const dev = e.target.closest("[data-fo-dev-detail]");
    if (dev) return showQcDetailModal(Number(dev.dataset.foDevDetail));
    const mv = e.target.closest("[data-fo-mv]");
    if (mv) return movementDialog(Number(mv.dataset.foMv));
    const r = e.target.closest("[data-fo-report]");
    if (r) return proxyReport(Number(r.dataset.foReport), r.dataset.name);
    const dpb = e.target.closest("[data-fo-dp]");
    if (dpb) return payDp(Number(dpb.dataset.foDp), Number(dpb.dataset.amount), dpb.dataset.name);
    const p = e.target.closest("[data-fo-pay]");
    if (p) return payFarmer(Number(p.dataset.foPay), Number(p.dataset.amount), p.dataset.name);
    const c = e.target.closest("[data-fo-contact]");
    if (c) return showContact(Number(c.dataset.foContact));
    const bc = e.target.closest("[data-br-cancel]");
    if (bc) return api(`/api/v1/farmer/biochar/redemptions/${Number(bc.dataset.brCancel)}/cancel`, { method: "POST" })
      .then(() => { showToast("Pengajuan dibatalkan.", "↩️"); loadBiochar(); }).catch(err => showToast(err.message, "❌"));
    const pm = e.target.closest("[data-pct]");
    if (pm) {
      const inp = $("mk-margin");
      inp.value = Math.min(50, Math.max(0, (Number(inp.value) || 0) + Number(pm.dataset.pct))).toFixed(1);
      inp.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });
  // Margin %: tampilkan setara Rp/kg dari harga jual
  document.addEventListener("input", (e) => {
    if (e.target && (e.target.id === "mk-margin" || e.target.id === "mk-resale") && $("mk-margin-rp")) {
      const v = (Number($("mk-resale").value) || 0) * (Number($("mk-margin").value) || 0) / 100;
      $("mk-margin-rp").textContent = `≈ ${rp(v)}/kg`;
    }
  });


  // ================================================================
  // FASE 2: GERBANG PABRIK, QC TIMBANGAN JEMBATAN & LOADING RAMP UI
  // ================================================================
  const PABRIK_GATE_HTML = `
    <section class="card" aria-labelledby="fo-gate-title" style="margin-top: 1.5rem; border: 1px solid var(--border-color, var(--surface-2));">
      <div class="card-header" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
        <div>
          <h3 class="card-title" id="fo-gate-title" style="display:flex; align-items:center; gap:8px;">
            <span>⚖️</span> Gerbang Masuk &amp; QC Timbangan Jembatan
          </h3>
          <p class="card-sub">Verifikasi Gross-Tare-Netto, keputusan QC 3-State, alokasi ramp rekursif, dan penerbitan invoice multi-skema.</p>
        </div>
        <div style="display:flex; gap:8px;">
          <button type="button" class="btn btn-secondary btn-sm" id="btn-refresh-gate">🔄 Refresh Ramp</button>
          <button type="button" class="btn btn-primary btn-sm" id="btn-open-gate-modal">➕ Timbang Masuk &amp; Input QC</button>
        </div>
      </div>

      <!-- Live Loading Ramp Monitoring -->
      <div style="padding: 1rem 1.25rem; background: rgba(0,0,0,0.15); border-bottom: 1px solid var(--border-color, var(--surface-2));">
        <h4 style="font-size:0.9rem; font-weight:600; margin-bottom:0.75rem; color:var(--text-muted, var(--ink-muted));">📊 STATUS REAL-TIME LOADING RAMP (MUTU REKURSIF):</h4>
        <div id="gate-ramps-container" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:12px;">
          <p class="muted">Memuat loading ramp…</p>
        </div>
      </div>

      <!-- Recent Gate Receptions Table -->
      <div style="padding: 1rem 1.25rem;">
        <h4 style="font-size:0.9rem; font-weight:600; margin-bottom:0.75rem; color:var(--text-muted, var(--ink-muted));">📜 RIWAYAT PENERIMAAN GERBANG &amp; QC TIMBANGAN:</h4>
        <div class="table-scroll">
          <table class="table" id="gate-receptions-table">
            <thead>
              <tr>
                <th>No. Tiket</th>
                <th>Plat Truk / Supir</th>
                <th>Armada</th>
                <th>Biomassa</th>
                <th>Gross / Tare / Netto</th>
                <th>Keputusan QC</th>
                <th>Alokasi Ramp</th>
                <th>Waktu</th>
              </tr>
            </thead>
            <tbody id="gate-receptions-body">
              <tr><td colspan="8" class="muted text-center">Memuat riwayat gerbang…</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  `;

  async function loadLoadingRamps() {
    const wrap = $("gate-ramps-container");
    if (!wrap) return;
    try {
      const ramps = await api("/api/v1/factory/loading-ramps");
      if (!ramps || !ramps.length) {
        wrap.innerHTML = `<p class="muted">Belum ada ramp terdaftar.</p>`;
        return;
      }
      wrap.innerHTML = ramps.map(r => `
        <div style="background:var(--card-bg, var(--surface-1)); border:1px solid ${r.utilization_pct > 90 ? '#e53e3e' : 'var(--border-strong)'}; border-radius:8px; padding:10px 12px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <strong style="color:var(--primary, #38a169); font-size:0.95rem;">${H(r.ramp_code)}</strong>
            <span class="badge ${r.utilization_pct > 90 ? 'badge-red' : 'badge-green'}" style="font-size:0.75rem;">${r.utilization_pct}% Kapasitas</span>
          </div>
          <div style="font-weight:600; font-size:0.85rem; margin-top:2px;">${H(r.name)}</div>
          <div style="font-size:0.8rem; color:var(--text-muted, var(--ink-muted)); margin-top:4px;">
            Stok: <strong>${num(r.current_stock_kg, 0)} kg</strong> / ${num(r.max_capacity_kg, 0)} kg
          </div>
          <div style="font-size:0.75rem; margin-top:6px; padding-top:6px; border-top:1px dashed var(--border-strong); display:flex; justify-content:space-between;">
            <span>💧 MC: <strong>${num(r.aggregate_mc, 1)}%</strong></span>
            <span>🔥 Ash: <strong>${num(r.aggregate_ash, 1)}%</strong></span>
            <span>⚡ LHV: <strong>${num(r.aggregate_lhv_kcal, 0)}</strong></span>
          </div>
        </div>
      `).join("");
    } catch (e) {
      wrap.innerHTML = `<p class="form-error">Gagal memuat ramp: ${H(e.message)}</p>`;
    }
  }

  async function loadGateReceptions() {
    const tbody = $("gate-receptions-body");
    if (!tbody) return;
    try {
      const rows = await api("/api/v1/factory/gate-receptions");
      if (!rows || !rows.length) {
        tbody.innerHTML = `<tr><td colspan="8" class="muted text-center">Belum ada penerimaan gerbang tercatat.</td></tr>`;
        return;
      }

      const COMMODITY_MAP = {
        sekam_padi: { label: "🌾 Sekam Padi", badge: "badge-purple" },
        tongkol_jagung: { label: "🌽 Tongkol Jagung", badge: "badge-amber" },
        serbuk_sengon: { label: "🪵 Serbuk Sengon", badge: "badge-blue" },
        serbuk_kayu: { label: "🪵 Serbuk Kayu", badge: "badge-blue" },
        tempurung_kelapa: { label: "🥥 Tempurung Kelapa", badge: "badge-amber" },
        ampas_tebu: { label: "🎋 Ampas Tebu", badge: "badge-green" },
        cangkang_sawit: { label: "🌴 Cangkang Sawit", badge: "badge-amber" },
      };

      const grouped = {};
      for (const g of rows) {
        const key = g.biomass_type || "sekam_padi";
        if (!grouped[key]) grouped[key] = [];
        grouped[key].push(g);
      }

      let tbodyHtml = "";
      for (const [bioKey, groupRows] of Object.entries(grouped)) {
        const meta = COMMODITY_MAP[bioKey] || { label: bioKey.replace("_", " ").toUpperCase(), badge: "badge-gray" };
        const totalNetKg = groupRows.reduce((acc, r) => acc + (Number(r.net_weight) || 0), 0);
        tbodyHtml += `
          <tr class="group-header-row" style="background:var(--bg-elevated, rgba(255,255,255,0.06)); font-weight:700;">
            <td colspan="8" style="padding:10px 14px; border-top:2px solid var(--border); color:var(--primary, #38a169);">
              <span style="font-size:1.02em;">${meta.label}</span>
              <span class="badge ${meta.badge}" style="margin-left:8px;">${groupRows.length} Tiket Gerbang</span>
              <span class="badge badge-green" style="margin-left:4px;">Total Netto: ${num(totalNetKg / 1000, 2)} ton</span>
            </td>
          </tr>
        `;

        tbodyHtml += groupRows.map(g => {
          let badgeClass = "badge-green";
          if (g.qc_decision === "PARTIALLY_ACCEPTED") badgeClass = "badge-amber";
          if (g.qc_decision === "REJECTED") badgeClass = "badge-red";
          return `
            <tr>
              <td>
                <div style="display:flex; align-items:center; gap:6px;">
                  <button type="button" class="btn btn-secondary btn-sm" style="padding:1px 5px; font-size:9px; height:18px;" data-onclick="openModal('Tiket Pabrik', '${H(g.ticket_number)}', 'Tiket Jembatan Timbang Gerbang Pabrik')">📱 QR</button>
                  <code>${H(g.ticket_number)}</code>
                </div>
              </td>
              <td><strong>${H(g.vehicle_plate)}</strong><br><span style="font-size:0.8rem; color:var(--ink-muted);">${H(g.driver_name)}</span></td>
              <td><span class="badge ${g.carrier === 'FACTORY_FLEET' ? 'badge-blue' : 'badge-amber'}">${H(g.carrier === 'FACTORY_FLEET' ? '🚛 Armada Pabrik' : '🚜 Antar Mandiri')}</span></td>
              <td><span class="badge ${meta.badge}">${H(g.biomass_type)}</span></td>
              <td>
                <span title="Gross: ${num(g.gross_weight, 0)} kg | Tare: ${num(g.tare_weight, 0)} kg">
                  Netto: <strong>${num(g.net_weight, 0)} kg</strong>
                </span>
              </td>
              <td>
                <span class="badge ${badgeClass}">${H(g.qc_decision)}</span>
                ${g.rejected_qty_kg > 0 ? `<br><small style="color:#e53e3e;">Tolak: ${num(g.rejected_qty_kg, 0)} kg</small>` : ''}
              </td>
              <td>${g.accepted_qty_kg > 0 ? `<span class="badge badge-green">Diterima: ${num(g.accepted_qty_kg, 0)} kg</span>` : '<span class="muted">-</span>'}</td>
              <td style="font-size:0.8rem;">${formatDateTime(g.created_at)}</td>
            </tr>
          `;
        }).join("");
      }
      tbody.innerHTML = tbodyHtml;
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="8" class="form-error text-center">Gagal memuat riwayat gerbang: ${H(e.message)}</td></tr>`;
    }
  }

  function openGateReceptionModal() {
    formDialog({
      title: "⚖️ Timbang Masuk Jembatan & Input Keputusan QC",
      ok: "✅ Proses Masuk & Terbitkan Invoice",
      wide: true,
      body: `
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
          <div class="form-group">
            <label for="gc-carrier">Armada Logistik Pengantar</label>
            <select id="gc-carrier" name="logistics_carrier" class="input" required>
              <option value="FACTORY_FLEET">🚛 Armada Pabrik (FACTORY_FLEET)</option>
              <option value="COLLECTOR_SELF">📦 Pengantaran Mandiri Pengepul (COLLECTOR_SELF)</option>
            </select>
          </div>
          <div class="form-group">
            <label for="gc-plate">Nomor Polisi Truk</label>
            <input type="text" id="gc-plate" name="vehicle_plate" class="input" placeholder="misal: AB 8492 BZ" required>
          </div>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
          <div class="form-group">
            <label for="gc-driver">Nama Sopir</label>
            <input type="text" id="gc-driver" name="driver_name" class="input" placeholder="Nama sopir truk" required>
          </div>
          <div class="form-group">
            <label for="gc-biomass">Komoditas Biomassa</label>
            <select id="gc-biomass" name="biomass_type" class="input" required>
              <option value="sekam_padi">🌾 Biomassa Sekam Padi</option>
              <option value="tongkol_jagung">🌽 Biomassa Tongkol Jagung</option>
              <option value="serbuk_sengon">🪵 Biomassa Serbuk Kayu Sengon</option>
              <option value="tempurung_kelapa">🥥 Biomassa Tempurung Kelapa</option>
              <option value="ampas_tebu">🎋 Biomassa Ampas Tebu</option>
            </select>
          </div>
        </div>

        <!-- Section Timbangan Jembatan -->
        <div style="background:rgba(0,0,0,0.2); padding:10px; border-radius:6px; margin-bottom:12px; border:1px solid var(--border-strong);">
          <h4 style="font-size:0.85rem; font-weight:600; margin-bottom:8px; color:#63b3ed;">⚖️ METROLOGI TIMBANGAN JEMBATAN (KG):</h4>
          <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px;">
            <div class="form-group">
              <label for="gc-gross">Berat Kotor (Gross)</label>
              <input type="number" id="gc-gross" name="gross_weight" class="input" min="1" step="any" placeholder="misal: 11500" required>
            </div>
            <div class="form-group">
              <label for="gc-tare">Berat Kosong (Tare)</label>
              <input type="number" id="gc-tare" name="tare_weight" class="input" min="0" step="any" placeholder="misal: 7500" required>
            </div>
            <div class="form-group">
              <label>Netto Terhitung</label>
              <input type="text" id="gc-net-display" class="input" style="font-weight:bold; color:#68d391; background:var(--surface-2);" readonly value="0 kg">
            </div>
          </div>
        </div>

        <!-- Section Hasil Uji Mutu QC -->
        <div style="background:rgba(0,0,0,0.2); padding:10px; border-radius:6px; margin-bottom:12px; border:1px solid var(--border-strong);">
          <h4 style="font-size:0.85rem; font-weight:600; margin-bottom:8px; color:#f6e05e;">🔬 PENGUJIAN MUTU SAMPEL (LAB LAPANGAN):</h4>
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(110px, 1fr)); gap:8px;">
            <div class="form-group">
              <label for="gc-mc">Kadar Air (%)</label>
              <input type="number" id="gc-mc" name="tested_mc_pct" class="input" min="0" max="100" step="any" value="13.5" required>
            </div>
            <div class="form-group">
              <label for="gc-ash">Kadar Abu (%)</label>
              <input type="number" id="gc-ash" name="tested_ash_pct" class="input" min="0" max="100" step="any" value="16.0" required>
            </div>
            <div class="form-group">
              <label for="gc-lhv">LHV (kcal/kg)</label>
              <input type="number" id="gc-lhv" name="tested_lhv_kcal" class="input" min="0" step="any" value="3500" required>
            </div>
            <div class="form-group">
              <label for="gc-contam">Kotoran (%)</label>
              <input type="number" id="gc-contam" name="contamination_pct" class="input" min="0" max="100" step="any" value="1.0" required>
            </div>
          </div>
        </div>

        <!-- Section Keputusan QC 3-State -->
        <div style="background:rgba(0,0,0,0.2); padding:10px; border-radius:6px; margin-bottom:12px; border:1px solid var(--border-strong);">
          <h4 style="font-size:0.85rem; font-weight:600; margin-bottom:8px; color:#fc8181;">🚦 KEPUTUSAN QC GERBANG (3-STATE):</h4>
          <div style="display:flex; gap:10px; margin-bottom:10px;">
            <label style="display:flex; align-items:center; gap:6px; cursor:pointer;">
              <input type="radio" name="qc_decision" value="ACCEPTED" checked> 🟢 Diterima Penuh
            </label>
            <label style="display:flex; align-items:center; gap:6px; cursor:pointer;">
              <input type="radio" name="qc_decision" value="PARTIALLY_ACCEPTED"> 🟡 Diterima Sebagian
            </label>
            <label style="display:flex; align-items:center; gap:6px; cursor:pointer;">
              <input type="radio" name="qc_decision" value="REJECTED"> 🔴 Ditolak Total
            </label>
          </div>

          <div id="gc-partial-box" style="display:none; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:8px;">
            <div class="form-group">
              <label for="gc-acc-qty">Qty Disetujui Masuk (kg)</label>
              <input type="number" id="gc-acc-qty" name="accepted_qty_kg" class="input" min="0" step="any" placeholder="Kuantitas diterima">
            </div>
            <div class="form-group">
              <label for="gc-rej-qty">Qty Ditolak / Retur (kg)</label>
              <input type="number" id="gc-rej-qty" name="rejected_qty_kg" class="input" min="0" step="any" placeholder="Kuantitas ditolak">
            </div>
          </div>

          <div id="gc-rejection-box" style="display:none; margin-bottom:8px;">
            <div class="form-group">
              <label for="gc-reject-reason" style="color:#fc8181;">Alasan Penolakan (Wajib Dicatat)</label>
              <textarea id="gc-reject-reason" name="rejection_reason" class="input" rows="2" placeholder="Jelaskan alasan penolakan mutu/kontaminan..."></textarea>
            </div>
          </div>

          <div class="form-group">
            <label for="gc-target-ramp">Alokasi Loading Ramp Tujuan</label>
            <select id="gc-target-ramp" name="allocated_ramp_id" class="input">
              <option value="1">RAMP-01: Ramp Biomassa 01 (Granular/Sekam)</option>
              <option value="2">RAMP-02: Ramp Biomassa 02 (Cacah/Tongkol)</option>
              <option value="3">RAMP-03: Ramp Biomassa 03 (Serbuk Kayu)</option>
              <option value="4">RAMP-04: Ramp Biomassa 04 (Cangkang/Tempurung)</option>
            </select>
          </div>
        </div>

        <!-- Section Skema Pembayaran & Invoice Otomatis -->
        <div style="background:rgba(0,0,0,0.2); padding:10px; border-radius:6px; border:1px solid var(--border-strong);">
          <h4 style="font-size:0.85rem; font-weight:600; margin-bottom:8px; color:#48bb78;">💰 PEMICU INVOICE OTOMATIS:</h4>
          <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px;">
            <div class="form-group">
              <label for="gc-scheme">Skema Bayar</label>
              <select id="gc-scheme" name="payment_scheme" class="input" required>
                <option value="CASH">💵 Cash (Lunas Instan)</option>
                <option value="DP">🪙 DP Bertermin</option>
                <option value="TOP">⏳ TOP (Jatuh Tempo)</option>
              </select>
            </div>
            <div class="form-group">
              <label for="gc-unit-price">Harga Dasar (Rp/kg)</label>
              <input type="number" id="gc-unit-price" name="unit_price_rp" class="input" min="100" step="any" value="450" required>
            </div>
            <div class="form-group">
              <label for="gc-due-days">Termin (Hari)</label>
              <input type="number" id="gc-due-days" name="due_days" class="input" min="1" max="90" value="14" required>
            </div>
          </div>
          <div id="gc-dp-amount-box" class="form-group" style="display:none; margin-top:8px;">
            <label for="gc-dp-val">Nominal DP Dibayarkan di Muka (Rp)</label>
            <input type="number" id="gc-dp-val" name="dp_paid_amount" class="input" min="0" step="any" placeholder="Nominal uang muka">
          </div>
        </div>
      `,
      onSubmit: async (fd) => {
        const gross = Number(fd.get("gross_weight")) || 0;
        const tare = Number(fd.get("tare_weight")) || 0;
        const net = Math.max(0, gross - tare);
        const decision = fd.get("qc_decision");
        let accQty = net;
        let rejQty = 0;

        if (decision === "REJECTED") {
          accQty = 0;
          rejQty = net;
        } else if (decision === "PARTIALLY_ACCEPTED") {
          accQty = Number(fd.get("accepted_qty_kg")) || 0;
          rejQty = Number(fd.get("rejected_qty_kg")) || 0;
        }

        const payload = {
          collector_id: 3, // Default Mitra Pengepul Sleman (User ID 3)
          vehicle_plate: fd.get("vehicle_plate"),
          driver_name: fd.get("driver_name"),
          logistics_carrier: fd.get("logistics_carrier"),
          biomass_type: fd.get("biomass_type"),
          gross_weight: gross,
          tare_weight: tare,
          tested_mc_pct: Number(fd.get("tested_mc_pct")),
          tested_ash_pct: Number(fd.get("tested_ash_pct")),
          tested_lhv_kcal: Number(fd.get("tested_lhv_kcal")),
          contamination_pct: Number(fd.get("contamination_pct")),
          qc_decision: decision,
          accepted_qty_kg: accQty,
          rejected_qty_kg: rejQty,
          rejection_reason: fd.get("rejection_reason") || null,
          allocated_ramp_id: Number(fd.get("allocated_ramp_id")),
          payment_scheme: fd.get("payment_scheme"),
          unit_price_rp: Number(fd.get("unit_price_rp")),
          dp_paid_amount: Number(fd.get("dp_paid_amount")) || 0,
          due_days: Number(fd.get("due_days")) || 14,
        };

        const res = await api("/api/v1/factory/gate-receptions", { method: "POST", body: payload });
        showToast(res.message, "✅");
        await loadLoadingRamps();
        await loadGateReceptions();
        return false;
      }
    });

    // Event listener kalkulasi netto dan dynamic boxes
    setTimeout(() => {
      const grossInp = $("gc-gross");
      const tareInp = $("gc-tare");
      const netDisp = $("gc-net-display");
      const calcNet = () => {
        const g = Number(grossInp.value) || 0;
        const t = Number(tareInp.value) || 0;
        const net = Math.max(0, g - t);
        netDisp.value = `${num(net, 0)} kg`;
      };
      if (grossInp) grossInp.addEventListener("input", calcNet);
      if (tareInp) tareInp.addEventListener("input", calcNet);

      document.querySelectorAll("input[name='qc_decision']").forEach(r => {
        r.addEventListener("change", (e) => {
          const val = e.target.value;
          const pBox = $("gc-partial-box");
          const rBox = $("gc-rejection-box");
          if (pBox) pBox.style.display = (val === "PARTIALLY_ACCEPTED") ? "grid" : "none";
          if (rBox) rBox.style.display = (val === "REJECTED" || val === "PARTIALLY_ACCEPTED") ? "block" : "none";
        });
      });

      const schemeSel = $("gc-scheme");
      if (schemeSel) {
        schemeSel.addEventListener("change", (e) => {
          const dpBox = $("gc-dp-amount-box");
          if (dpBox) dpBox.style.display = (e.target.value === "DP") ? "block" : "none";
        });
      }
    }, 100);
  }


  // ================================================================
  // FASE 3 & 4: MULTI-RAMP BLENDING OPTIMIZER & GROUPED DASHBOARD UI
  // ================================================================
  const PABRIK_BLENDING_HTML = `
    <!-- Mesin Blending Multi-Ramp -->
    <section class="card" aria-labelledby="fo-blending-title" style="margin-top: 1.5rem; border: 1px solid var(--border-color, var(--surface-2));">
      <div class="card-header" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
        <div>
          <h3 class="card-title" id="fo-blending-title" style="display:flex; align-items:center; gap:8px;">
            <span>⚗️</span> Mesin Rekomendasi Blending Multi-Ramp (4 Produk Akhir)
          </h3>
          <p class="card-sub">Optimasi formulasi pakan reaktor multi-ramp untuk Biopellet, Biochar, Bio-Silika, dan Briket dengan simulasi margin laba &amp; emisi GHG Protocol.</p>
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
          <label for="blend-batch-size" style="font-size:0.85rem; color:var(--text-muted, var(--ink-muted));">Batch Size (kg):</label>
          <input type="number" id="blend-batch-size" value="10000" min="500" max="500000" step="500" style="width:110px; padding:6px 10px; font-size:0.85rem; border-radius:6px; background:var(--surface-1); color:var(--ink); border:1px solid var(--border-strong);">
          <button type="button" class="btn btn-primary btn-sm" id="btn-run-blending">⚡ Hitung Rekomendasi</button>
        </div>
      </div>

      <!-- 4-Product Comparative Cards -->
      <div style="padding: 1.25rem;">
        <div id="blending-cards-container" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:16px;">
          <p class="muted">Klik tombol "Hitung Rekomendasi" untuk menjalankan optimasi multi-ramp.</p>
        </div>
      </div>

      <!-- Riwayat Blending & By-Product Ledger -->
      <div style="padding: 1rem 1.25rem; border-top:1px solid var(--border-color, var(--surface-2)); background: rgba(0,0,0,0.15);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
          <h4 style="font-size:0.9rem; font-weight:600; color:var(--text-muted, var(--ink-muted));">📜 BUKU BESAR BATCH BLENDING &amp; HASIL SAMPING (CIRCULAR LEDGER):</h4>
          <button type="button" class="btn btn-secondary btn-sm" id="btn-refresh-blends" style="font-size:0.75rem;">🔄 Refresh Blends</button>
        </div>
        <div class="table-scroll">
          <table class="table" id="blend-history-table">
            <thead>
              <tr>
                <th>Kode Batch</th>
                <th>Target Produk</th>
                <th>Total Input</th>
                <th>Mutu Akhir (MC / Ash / LHV)</th>
                <th>Margin Laba Est.</th>
                <th>Net GHG (tCO2e)</th>
                <th>Waktu Kunci</th>
              </tr>
            </thead>
            <tbody id="blend-history-body">
              <tr><td colspan="7" class="muted text-center">Memuat riwayat blending…</td></tr>
            </tbody>
          </table>
        </div>

        <!-- By-Products Inventory -->
        <div style="margin-top:1rem; padding-top:0.75rem; border-top:1px dashed var(--border-strong);">
          <h5 style="font-size:0.85rem; font-weight:600; color:#4fd1c5; margin-bottom:6px;">♻️ Inventaris Hasil Samping Sirkular (By-Products):</h5>
          <div id="byproducts-container" style="display:flex; gap:12px; flex-wrap:wrap;">
            <span class="muted" style="font-size:0.8rem;">Memuat inventaris by-product…</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Grouped Biomass Monitoring Dashboard -->
    <section class="card" aria-labelledby="fo-biomass-grouped-title" style="margin-top: 1.5rem; border: 1px solid var(--border-color, var(--surface-2));">
      <div class="card-header" style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <h3 class="card-title" id="fo-biomass-grouped-title" style="display:flex; align-items:center; gap:8px;">
            <span>📊</span> Dashboard Monitoring Terkelompok (Per Jenis Biomassa)
          </h3>
          <p class="card-sub">Agregasi analitik tonase gerbang, mutu rata-rata (MC/Ash/LHV), stok ramp, dan liabilitas keuangan per komoditas.</p>
        </div>
        <button type="button" class="btn btn-secondary btn-sm" id="btn-refresh-grouped">🔄 Refresh Analitik</button>
      </div>
      <div style="padding: 1rem 1.25rem;">
        <div class="table-scroll">
          <table class="table" id="biomass-grouped-table">
            <thead>
              <tr>
                <th>Biomassa</th>
                <th>Frekuensi Truk</th>
                <th>Total Masuk</th>
                <th>Diterima / Ditolak</th>
                <th>Laju Penolakan</th>
                <th>Rerata Mutu (MC / Ash / LHV)</th>
                <th>Stok Ramp Terkini</th>
                <th>Total Tagihan (Rp)</th>
                <th>Tunggakan Belum Lunas</th>
              </tr>
            </thead>
            <tbody id="biomass-grouped-body">
              <tr><td colspan="9" class="muted text-center">Memuat ringkasan biomassa…</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  `;

  const COLLECTOR_FEEDBACK_HTML = `
    <section class="card" aria-labelledby="fo-feedback-title" style="margin-top: 1.5rem; border: 1px solid var(--border-color, var(--surface-2));">
      <div class="card-header" style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <h3 class="card-title" id="fo-feedback-title" style="display:flex; align-items:center; gap:8px;">
            <span>⚖️</span> Transparansi Mutu &amp; Evaluasi QC Gerbang Pabrik
          </h3>
          <p class="card-sub">Riwayat penimbangan timbangan jembatan pabrik, potongan deviasi, alasan penolakan, dan rekomendasi teknis perbaikan mutu.</p>
        </div>
        <button type="button" class="btn btn-secondary btn-sm" id="btn-refresh-feedback">🔄 Refresh</button>
      </div>
      <div style="padding: 1rem 1.25rem;">
        <div class="table-scroll">
          <table class="table" id="collector-feedback-table">
            <thead>
              <tr>
                <th>No. Tiket</th>
                <th>Biomassa</th>
                <th>Netto Timbang</th>
                <th>Diterima</th>
                <th>Ditolak</th>
                <th>Hasil Uji (MC / Abu / LHV)</th>
                <th>Alasan Penolakan</th>
                <th>Saran Perbaikan Mutu</th>
              </tr>
            </thead>
            <tbody id="collector-feedback-body">
              <tr><td colspan="8" class="muted text-center">Memuat umpan balik gerbang pabrik…</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  `;

  async function loadBiomassGroupedDashboard() {
    const tbody = $("biomass-grouped-body");
    if (!tbody) return;
    try {
      const res = await api("/api/v1/factory/dashboard/biomass-grouped");
      const list = res.summary || [];
      if (!list.length) {
        tbody.innerHTML = `<tr><td colspan="9" class="muted text-center">Belum ada data biomassa tercatat.</td></tr>`;
        return;
      }
      tbody.innerHTML = list.map(b => `
        <tr>
          <td><strong>${H(b.display_name)}</strong><br><small style="color:var(--ink-muted);">${H(b.biomass_type)}</small></td>
          <td><span class="badge badge-blue">${b.incoming_trips} trip</span></td>
          <td><strong>${num(b.total_incoming_kg, 0)} kg</strong></td>
          <td>
            <span class="badge badge-green">✓ ${num(b.total_accepted_kg, 0)} kg</span>
            ${b.total_rejected_kg > 0 ? `<br><span class="badge badge-red" style="margin-top:2px;">✗ ${num(b.total_rejected_kg, 0)} kg</span>` : ''}
          </td>
          <td>
            <span class="badge ${b.rejection_rate_pct > 10 ? 'badge-red' : b.rejection_rate_pct > 0 ? 'badge-amber' : 'badge-green'}">
              ${b.rejection_rate_pct}%
            </span>
          </td>
          <td>
            <small>💧 ${num(b.avg_mc_pct, 1)}% | 🔥 ${num(b.avg_ash_pct, 1)}% | ⚡ ${num(b.avg_lhv_kcal, 0)}</small>
          </td>
          <td>
            <strong>${num(b.ramp_stock_kg, 0)} kg</strong>
            ${b.ramp_capacity_kg > 0 ? `<br><small style="color:var(--ink-muted);">kap: ${num(b.ramp_capacity_kg, 0)} kg</small>` : ''}
          </td>
          <td>${rp(b.total_invoiced_rp)}</td>
          <td>
            ${b.total_unpaid_rp > 0 ? `<span style="color:#e53e3e; font-weight:700;">${rp(b.total_unpaid_rp)}</span>` : '<span class="badge badge-green">Lunas</span>'}
          </td>
        </tr>
      `).join("");
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="9" class="form-error">Gagal memuat analitik: ${H(e.message)}</td></tr>`;
    }
  }

  async function loadMultiRampBlendingRecommendations() {
    const wrap = $("blending-cards-container");
    const batchInput = $("blend-batch-size");
    if (!wrap) return;
    const batchKg = batchInput ? Number(batchInput.value) || 10000 : 10000;

    wrap.innerHTML = `<p class="muted">Mengalkulasi optimasi formulasi pakan untuk ${num(batchKg, 0)} kg biomassa…</p>`;
    try {
      const res = await api("/api/v1/factory/blends/optimize", {
        method: "POST",
        body: { batch_size_kg: batchKg }
      });
      const recs = res.recommendations || [];
      if (!recs.length) {
        wrap.innerHTML = `<p class="muted">Tidak ada stok biomassa yang mencukupi untuk batch blending.</p>`;
        return;
      }

      wrap.innerHTML = recs.map(r => {
        let borderStyle = "1px solid var(--border-strong)";
        if (r.is_most_profitable) borderStyle = "2px solid #d69e2e";
        else if (r.is_lowest_carbon) borderStyle = "2px solid #319795";

        const allocSummary = r.ramp_allocations.map(a => 
          `<span class="badge badge-gray" style="font-size:0.75rem; margin-right:4px;">${H(a.ramp_code)}: ${num(a.qty_kg, 0)} kg</span>`
        ).join("");

        return `
          <div style="background:var(--card-bg, var(--surface-1)); border:${borderStyle}; border-radius:10px; padding:16px; display:flex; flex-direction:column; justify-content:space-between; position:relative;">
            <div>
              <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px;">
                <h4 style="font-size:1.05rem; font-weight:700; color:var(--ink); margin-bottom:4px;">${H(r.product_name)}</h4>
                <div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px;">
                  ${r.is_most_profitable ? `<span class="badge" style="background:#d69e2e; color:#1a202c; font-weight:700; font-size:0.7rem;">⭐ PALING UNTUNG</span>` : ''}
                  ${r.is_lowest_carbon ? `<span class="badge" style="background:#319795; color:#fff; font-weight:700; font-size:0.7rem;">🌱 LOW CARBON</span>` : ''}
                </div>
              </div>

              <div style="font-size:0.85rem; color:var(--ink-muted); margin-top:4px;">
                Input: <strong>${num(r.total_input_kg, 0)} kg</strong> ➔ Output: <strong style="color:#48bb78;">${num(r.estimated_output_kg, 0)} kg</strong> (Rendemen ${r.yield_pct}%)
              </div>

              <!-- Ramp allocation -->
              <div style="margin-top:10px; padding:8px; background:rgba(0,0,0,0.25); border-radius:6px;">
                <div style="font-size:0.75rem; color:var(--ink-muted); margin-bottom:4px; font-weight:600;">ALOKASI LOADING RAMP:</div>
                <div style="display:flex; flex-wrap:wrap; gap:4px;">${allocSummary}</div>
              </div>

              <!-- Mutu Prediksi -->
              <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; margin-top:10px; font-size:0.75rem; text-align:center;">
                <div style="background:var(--surface-2); padding:4px 6px; border-radius:4px;">💧 MC: <strong>${r.final_mc_pct}%</strong></div>
                <div style="background:var(--surface-2); padding:4px 6px; border-radius:4px;">🔥 Ash: <strong>${r.final_ash_pct}%</strong></div>
                <div style="background:var(--surface-2); padding:4px 6px; border-radius:4px;">⚡ LHV: <strong>${num(r.final_lhv_kcal, 0)}</strong></div>
              </div>

              <!-- Indeks Alkali & Slagging Risk + WtE Drying Penalty -->
              <div style="margin-top:8px; display:flex; flex-direction:column; gap:4px;">
                <div style="display:flex; justify-content:space-between; align-items:center; background:var(--surface-2); padding:4px 8px; border-radius:4px; font-size:0.75rem;">
                  <span>🧪 Indeks Alkali (Miles): <strong>${num(r.alkali_index || 0, 3)} kg/GJ</strong></span>
                  <span class="badge ${r.slagging_verdict === 'AMAN' ? 'badge-green' : (r.slagging_verdict === 'WASPADA' ? 'badge-amber' : 'badge-red')}" style="font-size:0.7rem;">
                    ${r.slagging_verdict || 'AMAN'}
                  </span>
                </div>
                ${r.drying_penalty && r.drying_penalty.water_to_evaporate_kg > 0 ? `
                  <div style="font-size:0.75rem; color:#fc8181; background:rgba(229, 62, 62, 0.15); padding:4px 8px; border-radius:4px; border:1px solid rgba(229, 62, 62, 0.3);">
                    ♨️ Penalti Pengeringan: <strong>-${num(r.drying_penalty.net_electric_penalty_kwh, 1)} kWh</strong> (${num(r.drying_penalty.water_to_evaporate_kg, 1)} kg air, derating -${num(r.drying_penalty.efficiency_derating_pct, 1)}%)
                  </div>
                ` : `
                  <div style="font-size:0.75rem; color:#68d391; background:rgba(72, 187, 120, 0.1); padding:4px 8px; border-radius:4px; border:1px solid rgba(72, 187, 120, 0.2);">
                    ✅ MC Memenuhi Spek (${num(r.final_mc_pct, 1)}% ≤ 14%), Derating 0%
                  </div>
                `}
              </div>

              <!-- Margin Finansial & Karbon -->
              <div style="margin-top:12px; padding-top:8px; border-top:1px dashed var(--border-strong); font-size:0.85rem;">
                <div style="display:flex; justify-content:space-between;">
                  <span>HPP: <strong>${rp(r.hpp_per_kg)}/kg</strong></span>
                  <span>Jual: <strong>${rp(r.target_selling_price_per_kg)}/kg</strong></span>
                </div>
                <div style="display:flex; justify-content:space-between; margin-top:4px;">
                  <span>Margin: <strong style="color:#48bb78;">+${rp(r.margin_per_kg)}/kg</strong></span>
                  <span>Laba Est: <strong style="color:#ecc94b;">${rp(r.total_profit_rp)}</strong></span>
                </div>
                <div style="margin-top:6px; font-size:0.8rem; color:#4fd1c5;">
                  🌍 Net Serapan Karbon: <strong>${num(r.net_tco2e, 2)} tCO2e</strong>
                </div>
              </div>
            </div>

            <div style="margin-top:14px;">
              <button type="button" class="btn btn-primary btn-sm btn-commit-blend" data-prod="${H(r.target_product)}" style="width:100%; font-weight:600;">
                🔒 Kunci Batch Produksi
              </button>
            </div>
          </div>
        `;
      }).join("");

      // Wire commit buttons
      wrap.querySelectorAll(".btn-commit-blend").forEach((btn, idx) => {
        btn.onclick = async () => {
          const rec = recs[idx];
          if (!confirm(`Konfirmasi eksekusi batch produksi ${rec.product_name} sebesar ${num(rec.total_input_kg, 0)} kg?\nStok pada loading ramp akan dipotong secara permanen.`)) {
            return;
          }
          try {
            const commitRes = await api("/api/v1/factory/blends/commit", {
              method: "POST",
              body: {
                target_product: rec.target_product,
                total_input_kg: rec.total_input_kg,
                ramp_allocations: rec.ramp_allocations,
                cost_per_kg: rec.hpp_per_kg,
                target_selling_price_per_kg: rec.target_selling_price_per_kg,
                estimated_margin_rp: rec.total_profit_rp,
                net_tco2e: rec.net_tco2e,
                final_mc_pct: rec.final_mc_pct,
                final_ash_pct: rec.final_ash_pct,
                final_lhv_kcal: rec.final_lhv_kcal,
              }
            });
            showToast(commitRes.message || "Batch produksi berhasil dikunci!", "🎉");
            await loadLoadingRamps();
            await loadMultiRampBlendingRecommendations();
            await loadBlendHistoryAndByProducts();
            await loadBiomassGroupedDashboard();
          } catch (err) {
            showToast(err.message || "Gagal mengunci batch blending", "❌");
          }
        };
      });

    } catch (e) {
      wrap.innerHTML = `<p class="form-error">Gagal menghitung optimasi: ${H(e.message)}</p>`;
    }
  }

  async function loadBlendHistoryAndByProducts() {
    const tbody = $("blend-history-body");
    const bpWrap = $("byproducts-container");
    if (tbody) {
      try {
        const rows = await api("/api/v1/factory/blends");
        if (!rows || !rows.length) {
          tbody.innerHTML = `<tr><td colspan="7" class="muted text-center">Belum ada batch blending yang dieksekusi.</td></tr>`;
        } else {
          const grouped = {};
          rows.forEach(b => {
            const cat = b.target_product || "LAINNYA";
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push(b);
          });

          const productIcons = {
            "BIOPELLET": "🌿 BIOPELLET (Bahan Bakar Industri)",
            "BIOCHAR": "🔋 BIOCHAR (Material Prekursor Baterai & Carbon Sink)",
            "BIO_SILICA": "🧪 BIO-SILIKA (Presipitasi Sekam Padi)",
            "BRIQUETTE": "🔥 BRIKET (Arang Kalori Tinggi)",
          };

          let html = "";
          for (const [prodKey, blendList] of Object.entries(grouped)) {
            const lotCount = blendList.length;
            const totalKg = blendList.reduce((acc, x) => acc + (x.total_input_kg || 0), 0);
            const totalTco2 = blendList.reduce((acc, x) => acc + (x.net_tco2e || 0), 0);
            const title = productIcons[prodKey] || `📦 ${prodKey}`;

            html += `
              <tr style="background: rgba(49, 151, 149, 0.15); border-top: 2px solid #319795;">
                <td colspan="7" style="padding: 10px 14px; font-weight: 700; color: #81e6d9;">
                  <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span>${H(title)}</span>
                    <span style="font-size:0.8rem; font-weight:normal; color:var(--ink);">
                      ${lotCount} Batch | Total Input: <strong>${num(totalKg, 0)} kg</strong> | Karbon: <strong style="color:#4fd1c5;">+${num(totalTco2, 2)} tCO2e</strong>
                    </span>
                  </div>
                </td>
              </tr>
            `;

            html += blendList.map(b => `
              <tr>
                <td><code>${H(b.blend_code)}</code></td>
                <td><span class="badge badge-green">${H(b.target_product)}</span></td>
                <td><strong>${num(b.total_input_kg, 0)} kg</strong></td>
                <td>💧 ${num(b.final_mc_pct, 1)}% | 🔥 ${num(b.final_ash_pct, 1)}% | ⚡ ${num(b.final_lhv_kcal, 0)}</td>
                <td><strong style="color:#ecc94b;">${rp(b.estimated_margin_rp)}</strong></td>
                <td><span style="color:#4fd1c5;">${num(b.net_tco2e, 2)} tCO2e</span></td>
                <td><small>${H(b.created_at ? b.created_at.slice(0, 16).replace('T', ' ') : '-')}</small></td>
              </tr>
            `).join("");
          }
          tbody.innerHTML = html;
        }
      } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" class="form-error">Gagal memuat riwayat: ${H(e.message)}</td></tr>`;
      }
    }

    if (bpWrap) {
      try {
        const bps = await api("/api/v1/factory/by-products");
        if (!bps || !bps.length) {
          bpWrap.innerHTML = `<span class="muted" style="font-size:0.8rem;">Belum ada hasil samping tercatat.</span>`;
        } else {
          bpWrap.innerHTML = bps.map(bp => {
            const isApproved = bp.circular_status === 'APPROVED_FOR_SOIL';
            const isRejected = bp.circular_status === 'REJECTED_HAZARDOUS';
            const isTested = bp.is_safety_passed || isApproved || isRejected;

            let statusBadge = `<span class="badge badge-amber" style="font-size:0.7rem;">${H(bp.circular_status)}</span>`;
            if (isApproved) statusBadge = `<span class="badge badge-green" style="font-size:0.7rem;">🌱 APPROVED FOR SOIL</span>`;
            if (isRejected) statusBadge = `<span class="badge badge-red" style="font-size:0.7rem;">⛔ DIKARANTINA B3</span>`;

            return `
              <div style="background:var(--surface-2); padding:8px 12px; border-radius:8px; font-size:0.8rem; display:flex; flex-direction:column; gap:6px; border:1px solid var(--border-strong); flex:1 1 260px; min-width:0; max-width:100%;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
                  <div style="display:flex; align-items:center; gap:8px;">
                    <span class="badge ${bp.by_product_type === 'WOOD_VINEGAR' ? 'badge-amber' : (bp.by_product_type === 'BIOCHAR' ? 'badge-green' : 'badge-gray')}">${H(bp.by_product_type)}</span>
                    <strong>${num(bp.quantity_kg, 1)} kg</strong>
                  </div>
                  ${statusBadge}
                </div>
                <div style="font-size:0.75rem; color:var(--ink-muted);">${H(bp.notes || '-')}</div>
                ${isTested ? `
                  <div style="font-size:0.72rem; color:#81e6d9; background:rgba(49,151,149,0.15); padding:4px 6px; border-radius:4px;">
                    🧪 Lab: <strong>${H(bp.lab_cert_no || 'Uji Internal')}</strong> | Pb: <strong>${num(bp.pb_ppm, 2)}</strong>, Cd: <strong>${num(bp.cd_ppm, 2)}</strong>, As: <strong>${num(bp.as_ppm, 2)}</strong> ppm
                  </div>
                ` : `
                  <div style="margin-top:2px;">
                    <button type="button" class="btn btn-secondary btn-sm btn-bp-safety" data-id="${bp.id}" data-type="${H(bp.by_product_type)}" style="font-size:0.72rem; padding:2px 8px; width:100%;">
                      🔬 Input Uji Logam Berat (SNI/EBC Gatekeeper)
                    </button>
                  </div>
                `}
              </div>
            `;
          }).join("");

          bpWrap.querySelectorAll(".btn-bp-safety").forEach(btn => {
            btn.onclick = async () => {
              const bpId = btn.dataset.id;
              const bType = btn.dataset.type;
              const certNo = prompt(`Masukkan Nomor Sertifikat Uji Lab KAN/ISO 17025 untuk ${bType}:`, `KAN-ISO17025-${new Date().getFullYear()}-001`);
              if (!certNo) return;
              const pb = parseFloat(prompt("Kadar Timbal / Pb (ppm) [Ambang batas aman < 50 ppm]:", "4.2") || "0");
              const cd = parseFloat(prompt("Kadar Kadmium / Cd (ppm) [Ambang batas aman < 2 ppm]:", "0.15") || "0");
              const as_ = parseFloat(prompt("Kadar Arsenik / As (ppm) [Ambang batas aman < 10 ppm]:", "0.8") || "0");
              try {
                const res = await api(`/api/v1/factory/by-products/${bpId}/safety-test`, {
                  method: "POST",
                  body: { pb_ppm: pb, cd_ppm: cd, as_ppm: as_, lab_cert_no: certNo }
                });
                showToast(res.message, res.is_safety_passed ? "✅" : "⛔");
                loadBlendHistoryAndByProducts();
              } catch (err) {
                showToast(err.message || "Gagal menyimpan uji lab", "❌");
              }
            };
          });
        }
      } catch (e) {
        bpWrap.innerHTML = `<span class="form-error">${H(e.message)}</span>`;
      }
    }
  }

  async function loadCollectorGateFeedback() {
    const tbody = $("collector-feedback-body");
    if (!tbody) return;
    try {
      const res = await api("/api/v1/collector/gate-feedback");
      const list = res.items || [];
      if (!list.length) {
        tbody.innerHTML = `<tr><td colspan="8" class="muted text-center">Belum ada catatan pengiriman gerbang pabrik.</td></tr>`;
        return;
      }

      // Group by biomass_type
      const grouped = {};
      list.forEach(g => {
        const cat = g.biomass_type || "LAINNYA";
        if (!grouped[cat]) grouped[cat] = [];
        grouped[cat].push(g);
      });

      const COMM_ICONS = {
        "sekam_padi": "🌾 SEKAM PADI",
        "tongkol_jagung": "🌽 TONGKOL JAGUNG",
        "ampas_tebu": "🎋 AMPAS TEBU (BAGASSE)",
        "tempurung_kelapa": "🥥 TEMPURUNG KELAPA",
        "sabut_kelapa": "🥥 SABUT KELAPA",
        "serbuk_sengon": "🪵 SERBUK SENGON",
        "serbuk_karet": "🪵 SERBUK KARET",
      };

      let html = "";
      for (const [bioKey, items] of Object.entries(grouped)) {
        const lotCount = items.length;
        const totalNet = items.reduce((acc, x) => acc + (x.net_weight_kg || 0), 0);
        const totalAcc = items.reduce((acc, x) => acc + (x.accepted_qty_kg || 0), 0);
        const totalRej = items.reduce((acc, x) => acc + (x.rejected_qty_kg || 0), 0);
        const title = COMM_ICONS[bioKey] || `📦 ${bioKey.toUpperCase().replace(/_/g, ' ')}`;

        html += `
          <tr style="background: rgba(49, 151, 149, 0.15); border-top: 2px solid #319795;">
            <td colspan="8" style="padding: 10px 14px; font-weight: 700; color: #81e6d9;">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <span>${H(title)}</span>
                <span style="font-size:0.8rem; font-weight:normal; color:var(--ink);">
                  ${lotCount} Pengiriman | Net: <strong>${num(totalNet, 0)} kg</strong> | Diterima: <strong style="color:#48bb78;">${num(totalAcc, 0)} kg</strong> | Ditolak: <strong style="color:#fc8181;">${num(totalRej, 0)} kg</strong>
                </span>
              </div>
            </td>
          </tr>
        `;

        html += items.map(g => {
          let badgeClass = "badge-green";
          if (g.qc_decision === "PARTIALLY_ACCEPTED") badgeClass = "badge-amber";
          if (g.qc_decision === "REJECTED") badgeClass = "badge-red";

          return `
            <tr>
              <td>
                <div style="font-family:monospace; font-weight:700; color:var(--primary); font-size:12px; display:flex; align-items:center; gap:4px;">
                  <span>🏭 ${H(g.ticket_number)}</span>
                  <button type="button" class="btn btn-secondary btn-sm" style="padding:1px 5px; font-size:9px; height:18px;" data-onclick="openModal('Tiket Pabrik', '${H(g.ticket_number)}', 'Tiket Umpan Balik Mutu Gerbang Pabrik')">📱 QR</button>
                </div>
                <small style="color:var(--ink-muted); font-size:10px;">${formatDateTime(g.created_at)}</small>
              </td>
              <td><strong>${H(g.biomass_type)}</strong></td>
              <td>${num(g.net_weight_kg, 0)} kg</td>
              <td><span class="badge ${badgeClass}">${num(g.accepted_qty_kg, 0)} kg</span></td>
              <td>${g.rejected_qty_kg > 0 ? `<span class="badge badge-red">${num(g.rejected_qty_kg, 0)} kg</span>` : '<span class="muted">0 kg</span>'}</td>
              <td><small>💧 ${num(g.tested_mc_pct, 1)}% | 🔥 ${num(g.tested_ash_pct, 1)}% | ⚡ ${num(g.tested_lhv_kcal, 0)}</small></td>
              <td>${g.rejection_reason ? `<span style="color:#e53e3e; font-size:0.8rem;">${H(g.rejection_reason)}</span>` : '<span class="muted">-</span>'}</td>
              <td><span style="color:#4fd1c5; font-size:0.8rem;">💡 ${H(g.actionable_feedback || 'Mutu standar')}</span></td>
            </tr>
          `;
        }).join("");
      }
      tbody.innerHTML = html;
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="8" class="form-error">Gagal memuat umpan balik: ${H(e.message)}</td></tr>`;
    }
  }

  function renderCollectorGateFeedback(container) {
    if (!container || $("fo-feedback-title")) return;
    container.insertAdjacentHTML("beforeend", COLLECTOR_FEEDBACK_HTML);
    const btnRef = $("btn-refresh-feedback");
    if (btnRef) btnRef.onclick = loadCollectorGateFeedback;
    loadCollectorGateFeedback();
  }

  function renderFactoryGateQC(container) {
    if (!container || $("fo-gate-title")) return;
    container.insertAdjacentHTML("beforeend", PABRIK_GATE_HTML);
    container.insertAdjacentHTML("beforeend", PABRIK_BLENDING_HTML);

    const btnRef = $("btn-refresh-gate");
    if (btnRef) btnRef.onclick = () => { loadLoadingRamps(); loadGateReceptions(); };
    const btnOpen = $("btn-open-gate-modal");
    if (btnOpen) btnOpen.onclick = openGateReceptionModal;

    const btnRunBlend = $("btn-run-blending");
    if (btnRunBlend) btnRunBlend.onclick = loadMultiRampBlendingRecommendations;

    const btnRefBlend = $("btn-refresh-blends");
    if (btnRefBlend) btnRefBlend.onclick = loadBlendHistoryAndByProducts;

    const btnRefGrouped = $("btn-refresh-grouped");
    if (btnRefGrouped) btnRefGrouped.onclick = loadBiomassGroupedDashboard;

    loadLoadingRamps();
    loadGateReceptions();
    loadMultiRampBlendingRecommendations();
    loadBlendHistoryAndByProducts();
    loadBiomassGroupedDashboard();
  }

})();
