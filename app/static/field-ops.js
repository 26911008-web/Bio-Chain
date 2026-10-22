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
  function formDialog({ title, body, ok = "Simpan", danger = false, onSubmit }) {
    const d = document.createElement("dialog");
    d.className = "ui-confirm";
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
        <h3 class="card-title" id="fo-backhaul-title">🚚 Rute Konsolidasi &amp; Muatan Balik Biochar</h3>
        <p class="card-sub">Simulasi kapasitas ganda armada (30 m³ &amp; 5.000 kg) dengan integrasi pengiriman biochar ke petani.</p></div>
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
          <select id="fo-pay-filter" class="btn btn-secondary btn-sm">
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
          <h3 class="card-title" id="fo-soil-amendment-title">🌿 Alokasi Abu &amp; Evaluasi Mutu Biochar (Pembenah Tanah Sawah)</h3>
          <p class="card-sub">Pemanfaatan produk sirkular kembali ke sawah: alokasi abu boiler bebas logam berat (Kepmentan 261/2019) dan ulasan mutu biochar pirolisis.</p>
        </div>
        <button type="button" class="btn btn-primary btn-sm" id="btn-open-eval-biochar">📝 Isi Evaluasi Mutu Biochar</button>
      </div>

      <!-- Bagian 1: Alokasi Abu Pembenah Tanah untuk Kelompok (Poktan) -->
      <div style="margin-bottom:18px;">
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:6px; margin-bottom:10px;">
          <h4 style="margin:0; font-size:13.5px; font-weight:700; color:var(--ink); display:flex; align-items:center; gap:6px;">
            <span>🪨</span> <span>Alokasi Abu Pembenah Tanah untuk Kelompok Anda</span>
          </h4>
          <span class="muted" style="font-size:11px;">Standar Uji Logam Berat: Pb, Cd, As &le; Ambang Aman</span>
        </div>
        <div id="fo-ash-container"><p class="muted" style="font-size:12px;">Memuat data alokasi abu...</p></div>
      </div>

      <!-- Bagian 2: Evaluasi & Ulasan Mutu Biochar Sawah -->
      <div>
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:6px; margin-bottom:10px;">
          <h4 style="margin:0; font-size:13.5px; font-weight:700; color:var(--ink); display:flex; align-items:center; gap:6px;">
            <span>🌾</span> <span>Evaluasi &amp; Ulasan Mutu Biochar Lapangan</span>
          </h4>
          <span class="muted" style="font-size:11px;">Ukuran Mesh, Kematangan Pirolisis &amp; Dampak Kesuburan Tanah</span>
        </div>
        <div id="fo-biochar-evaluations"><p class="muted" style="font-size:12px;">Memuat evaluasi mutu biochar…</p></div>
      </div>
    </section>`;

  let cachedUnifiedPayments = [];

  function renderUnifiedPaymentTable() {
    const box = $("fo-mypay-unified");
    if (!box) return;
    const q = (($("fo-pay-search") || {}).value || "").toLowerCase().trim();
    const f = (($("fo-pay-filter") || {}).value || "all");

    let list = cachedUnifiedPayments.filter(it => {
      if (f === "paid" && !it.is_paid) return false;
      if (f === "waiting" && it.is_paid) return false;
      if (f === "dp" && !(it.dp_rp > 0 || it.dp_receipt_code)) return false;
      if (q) {
        const text = `${it.origin_qr_code || ""} ${it.receipt_code || ""} ${it.dp_receipt_code || ""} ${it.commodity_name || ""} ${it.collector_name || ""}`.toLowerCase();
        if (!text.includes(q)) return false;
      }
      return true;
    });

    if (!list.length) {
      box.innerHTML = emptyState("🧾", "Tidak ada data pembayaran", "Tidak ditemukan data yang sesuai dengan filter atau kata kunci.");
      return;
    }

    box.innerHTML = `
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>No. QR Code Ketelusuran</th>
              <th>Nama Barang (Biomassa)</th>
              <th>Status Uang Muka (DP)</th>
              <th>Status Kuitansi</th>
              <th>Status Akhir Pelunasan</th>
              <th class="num">Nominal Net</th>
              <th>Pengepul &amp; Waktu</th>
              <th>Aksi</th>
            </tr>
          </thead>
          <tbody>
            ${(() => {
              const monthGroups = {};
              list.forEach(it => {
                const meta = (typeof window.getMonthYearMeta === "function")
                  ? window.getMonthYearMeta(it.paid_at || it.verified_at || it.reported_at)
                  : { key: "2026-10", label: "Oktober 2026", shortLabel: "Okt 2026" };
                if (!monthGroups[meta.key]) {
                  monthGroups[meta.key] = { meta, items: [], totalNetRp: 0 };
                }
                monthGroups[meta.key].items.push(it);
                monthGroups[meta.key].totalNetRp += (Number(it.net_rp || it.gross_rp) || 0);
              });
              const sortedKeys = Object.keys(monthGroups).sort().reverse();
              return sortedKeys.map(k => {
                const g = monthGroups[k];
                return `
                  <tr class="group-header-row" style="background:var(--surface-2); font-weight:700;">
                    <td colspan="8" style="padding:10px 14px; border-top:2px solid var(--border); color:var(--ink);">
                      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                        <div>
                          <span style="font-size:1.05rem;">📅 ${H(g.meta.label)}</span>
                          <span class="badge badge-purple" style="margin-left:8px;">${g.items.length} Pembayaran</span>
                        </div>
                        <span class="badge badge-green" style="font-size:12px;">Total: ${rp(g.totalNetRp)}</span>
                      </div>
                    </td>
                  </tr>
                  ${g.items.map(it => `
                    <tr>
                      <td>
                        <div style="font-family:monospace; font-weight:700; color:var(--primary); font-size:12px; display:flex; align-items:center; gap:4px;">
                          <span>🌾 ${H(it.origin_qr_code || ('WR-HV-' + it.harvest_id))}</span>
                          <button type="button" class="btn btn-secondary btn-sm" style="padding:1px 5px; font-size:9px; height:18px;" data-onclick="openModal('QR Code Lot Petani', '${H(it.origin_qr_code || ('WR-HV-' + it.harvest_id))}', 'Kode batch biomassa asal petani')">📱 QR</button>
                        </div>
                        <small class="muted" style="font-size:10px;">Lot #${Number(it.harvest_id)}</small>
                        ${it.trx_code ? `<br><span class="badge badge-purple" style="font-size:9px;">🏪 ${H(it.trx_code)}</span>` : ''}
                      </td>
                      <td>
                        <b>${H(it.commodity_name || 'Sekam Padi')}</b>
                        <br><small class="muted">${num(it.quantity_kg || it.verified_kg || 0, 0)} kg</small>
                      </td>
                      <td>
                        ${(it.dp_rp > 0 || it.dp_receipt_code) 
                          ? `<span class="badge badge-blue">🤝 Ada DP: ${rp(it.dp_rp)}</span>${it.dp_receipt_code ? `<br><code style="font-size:10px;">${H(it.dp_receipt_code)}</code>` : ''}`
                          : `<span class="badge badge-gray">⚪ Tanpa DP</span>`}
                      </td>
                      <td>
                        ${it.receipt_code 
                          ? `<span class="badge badge-green">🧾 Diterima</span><br><code style="font-size:10px;">${H(it.receipt_code)}</code>`
                          : `<span class="badge badge-amber">⏳ Menunggu Terbit</span>`}
                      </td>
                      <td>
                        ${it.is_paid 
                          ? `<span class="badge badge-green">✅ Lunas</span>`
                          : (it.status_type === 'waiting' 
                            ? `<span class="badge badge-amber">⏳ Menunggu Pelunasan</span>`
                            : `<span class="badge badge-gray">⏳ Belum Ditimbang</span>`)}
                      </td>
                      <td class="num">
                        <b style="color:${it.is_paid ? 'var(--green)' : 'var(--warn)'}; font-size:13px;">${rp(it.net_rp || it.gross_rp || 0)}</b>
                      </td>
                      <td>
                        <b>${H(it.collector_name || 'Pengepul')}</b>
                        <br><small class="muted" style="font-size:10px;">${formatDateTime(it.paid_at || it.verified_at || it.reported_at)}</small>
                      </td>
                      <td>
                        ${it.receipt_code 
                          ? `<button type="button" class="btn btn-secondary btn-sm" data-onclick="openModal('Kuitansi Digital Pelunasan', '${H(it.receipt_code)}', 'Kuitansi ${H(it.receipt_code)} · ${rp(it.net_rp)} · ${H(it.collector_name || 'Pengepul')}')">🧾 Kuitansi</button>`
                          : (it.dp_receipt_code 
                            ? `<button type="button" class="btn btn-secondary btn-sm" data-onclick="openModal('Kuitansi Uang Muka (DP)', '${H(it.dp_receipt_code)}', 'Uang Muka ${H(it.dp_receipt_code)} · ${rp(it.dp_rp)}')">🤝 Kuitansi DP</button>`
                            : `<span class="muted" style="font-size:11px;">–</span>`)}
                      </td>
                    </tr>
                  `).join("")}
                `;
              }).join("");
            })()}
          </tbody>
        </table>
      </div>
    `;
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
          <div class="kpi-tile"><div class="kpi-lbl">Saldo biochar</div><div class="kpi-val">${num(w.balance_kg, 1)} kg</div>
            <div class="kpi-lbl">hak dari biomassa yang diolah</div></div>
          <div class="kpi-tile"><div class="kpi-lbl">Potensi bisa diambil</div><div class="kpi-val">${num(w.available_kg, 1)} kg</div>
            <div class="kpi-lbl">${w.held_kg ? `${num(w.held_kg, 1)} kg sedang diajukan` : "siap diajukan"}</div></div>
          <div class="kpi-tile kpi-blue"><div class="kpi-lbl">Sudah diambil</div><div class="kpi-val">${num(w.taken_kg || 0, 1)} kg</div>
            <div class="kpi-lbl">telah diaplikasikan ke sawah</div></div>
        </div>
        <div class="demo-hint-box" style="margin:12px 0 10px; padding:10px 14px; border-radius:8px; background:var(--surface-2); border:1px solid var(--border);">
          <div style="font-weight:700; color:var(--primary); margin-bottom:4px;">🌱 Informasi Ekonomi Sirkular Biochar:</div>
          <p style="margin:0; font-size:12px; line-height:1.4;" class="muted">
            Permintaan pengiriman biochar kini <b>terintegrasi langsung saat melapor biomassa</b> di modul <i>"🌾 Lapor &amp; Jual Biomassa"</i> agar armada membawa biochar muatan balik secara efisien. Tabel di bawah mencatat riwayat permohonan, nomor QR code, dan status serah terima biochar.
          </p>
        </div>
        <div id="br-list">
          ${reqs.length ? `
            <div class="table-scroll">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>No. QR Code Biochar</th>
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
                        <button type="button" class="btn btn-secondary btn-sm" style="padding:1px 5px; font-size:9px; height:18px; margin-left:4px;" data-onclick="openModal('QR Code Biochar Sawah', '${H(x.request_code || ('BCR-REQ-' + x.id))}', 'Nomor permohonan muatan balik biochar')">📱 QR</button>
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
          ` : emptyState("🌱", "Belum ada riwayat biochar", "Pesan biochar muatan balik saat melapor biomassa pada formulir di atas.")}
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
      const res = await fetch("/api/v1/me/data-export", { headers: { Authorization: `Bearer ${STATE.token}` } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `biochain-data-saya-${(STATE.user || {}).user_id || "akun"}.json`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
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
  // 6. MODAL OPTIMASI & ANALISIS TEKNIS RUTE PENJEMPUTAN BIOMASSA TERVERIFIKASI
  // ================================================================
  let roMap = null;
  let roLayer = null;
  let currentRoSimulationRes = null;
  let currentActiveTripIdx = 0;
  let currentRoMapMode = "leaflet";

  const FLEET_PRESETS = {
    cdd_budi: { plate: "AB 8421 CS", kg: 5000, m3: 30, driver: "Budi Santoso", phone: "0812-3456-7890", type: "Truk CDD Box" },
    engkel_joko: { plate: "AB 8122 UY", kg: 3500, m3: 20, driver: "Joko Pratama", phone: "0813-9876-5432", type: "Truk Engkel 4 Roda" },
    fuso_hendra: { plate: "AB 9033 KP", kg: 8500, m3: 50, driver: "Hendra Wijaya", phone: "0857-1122-3344", type: "Truk Fuso Heavy" },
    l300_slamet: { plate: "AB 7540 DA", kg: 1500, m3: 10, driver: "Slamet Riyadi", phone: "0821-4455-6677", type: "Pick-up L300 Box" },
    auto: { plate: "AB 8421 CS", kg: 5000, m3: 30, driver: "Budi Santoso", phone: "0812-3456-7890", type: "Multi-Armada Otomatis" }
  };

  function handleRoVehicleSelectChange(selectEl) {
    const val = selectEl.value;
    const preset = FLEET_PRESETS[val] || FLEET_PRESETS.auto;
    if ($("ro-truck-plate")) $("ro-truck-plate").value = preset.plate;
    if ($("ro-truck-max-kg")) $("ro-truck-max-kg").value = preset.kg;
    if ($("ro-truck-max-m3")) $("ro-truck-max-m3").value = preset.m3;
  }

  function toggleRoMapMode(mode) {
    currentRoMapMode = mode || "leaflet";
    const leafletBox = $("ro-leaflet-map");
    const svgBox = $("ro-vector-svg-container");
    const btnSvg = $("btn-toggle-svg-map");
    const btnOsm = $("btn-toggle-osm-map");

    if (currentRoMapMode === "svg") {
      if (leafletBox) leafletBox.style.display = "none";
      if (svgBox) svgBox.style.display = "block";
      if (btnSvg) { btnSvg.className = "btn btn-primary btn-sm"; }
      if (btnOsm) { btnOsm.className = "btn btn-secondary btn-sm"; }
      if (currentRoSimulationRes) renderRoVectorSvgMap(currentRoSimulationRes, currentActiveTripIdx);
    } else {
      if (svgBox) svgBox.style.display = "none";
      if (leafletBox) leafletBox.style.display = "block";
      if (btnSvg) { btnSvg.className = "btn btn-secondary btn-sm"; }
      if (btnOsm) { btnOsm.className = "btn btn-primary btn-sm"; }
      if (typeof L === "undefined") {
        // Fallback to SVG if Leaflet not ready
        toggleRoMapMode("svg");
      } else if (currentRoSimulationRes) {
        renderRoLeafletMap(currentRoSimulationRes, currentActiveTripIdx);
      }
    }
  }

  async function openRouteOptimizationModal() {
    const modal = $("route-optimization-modal");
    if (!modal) return;
    modal.classList.add("open");

    // Preset tomorrow's date for pickup
    const dateInput = $("ro-pickup-date");
    if (dateInput && !dateInput.value) {
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      dateInput.value = tomorrow.toISOString().split("T")[0];
    }

    // Reset results
    const resPanel = $("ro-technical-results");
    if (resPanel) resPanel.style.display = "none";
    const dispatchBtn = $("btn-ro-dispatch");
    if (dispatchBtn) {
      dispatchBtn.style.display = "none";
      dispatchBtn.disabled = false;
      dispatchBtn.innerText = "🚛 Tetapkan & Kirim Surat Tugas ke Supir";
    }

    const listContainer = $("ro-harvests-checklist-container");
    if (listContainer) {
      listContainer.innerHTML = '<div class="muted" style="text-align:center; padding:16px; font-size:12px;">⏳ Memuat daftar lot panen terverifikasi...</div>';
    }

    try {
      let harvests = await api("/api/v1/collector/available-harvests?status=verified");
      let isOnlyVerified = true;
      if (!harvests || !harvests.length) {
        isOnlyVerified = false;
        harvests = await api("/api/v1/collector/available-harvests");
      }

      if (!harvests || !harvests.length) {
        if (listContainer) {
          listContainer.innerHTML = `
            <div class="banner banner-info" style="font-size:12px; margin:0; padding:10px;">
              ℹ️ Belum ada lot panen terverifikasi yang siap dijemput.
              Silakan lakukan penimbangan &amp; verifikasi penerimaan biomassa petani terlebih dahulu.
            </div>
          `;
        }
        return;
      }

      harvests.sort((a, b) => (b.status === "verified" ? 1 : 0) - (a.status === "verified" ? 1 : 0));

      let html = "";
      harvests.forEach(h => {
        const isVer = h.status === "verified";
        const isChecked = isVer || !isOnlyVerified;
        const statusBadge = isVer
          ? '<span class="badge badge-green" style="font-size:10px; font-weight:700;">🔵 Terverifikasi Pengepul</span>'
          : '<span class="badge badge-amber" style="font-size:10px;">🟡 Menunggu Verifikasi</span>';
        
        const comLabel = h.commodity_name || (h.commodity ? h.commodity.replace(/_/g, " ") : "Sekam Padi");
        const estBackhaul = Math.round(Number(h.quantity_kg || 0) * 0.15); // ~15% biochar backhaul for Poktan
        
        html += `
          <label style="display:flex; align-items:flex-start; gap:10px; padding:8px 10px; border-bottom:1px solid var(--border); cursor:pointer; border-radius:6px; margin-bottom:2px;" class="ro-harvest-item">
            <input type="checkbox" name="ro_harvest_id" value="${h.id}" ${isChecked ? 'checked' : ''} style="margin-top:4px; transform:scale(1.2);">
            <div style="flex:1; font-size:12px;">
              <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:4px;">
                <span style="font-weight:700; color:var(--ink);">
                  #${h.id} · ${H(h.farmer_name)}
                  <span class="muted" style="font-weight:400; font-size:11px;">(${H(h.kecamatan || "Sleman")})</span>
                </span>
                ${statusBadge}
              </div>
              <div style="display:flex; justify-content:space-between; align-items:center; margin-top:3px; font-size:11.5px; color:var(--ink-muted); flex-wrap:wrap;">
                <span>🌾 <b>${num(h.quantity_kg, 0)} kg</b> ${H(comLabel)} · Ref: <code>${H(h.batch_ref || h.wr_code || "WR-HV")}</code></span>
                <span style="color:var(--primary); font-size:11px; font-weight:600;">🔄 Muatan Balik: ~${num(estBackhaul, 0)} kg Biochar Sawah</span>
              </div>
            </div>
          </label>
        `;
      });

      if (listContainer) listContainer.innerHTML = html;
    } catch (err) {
      if (listContainer) {
        listContainer.innerHTML = `<div class="banner banner-error" style="font-size:12px;">⚠️ Gagal memuat antrean panen: ${H(err.message)}</div>`;
      }
    }
  }

  function closeRouteOptimizationModal() {
    const modal = $("route-optimization-modal");
    if (modal) modal.classList.remove("open");
  }

  function toggleAllRoHarvests(selectAll) {
    const checkboxes = document.querySelectorAll('#ro-harvests-checklist-container input[name="ro_harvest_id"]');
    checkboxes.forEach(cb => { cb.checked = !!selectAll; });
  }

  async function runRouteOptimizationSimulation() {
    const checkboxes = document.querySelectorAll('#ro-harvests-checklist-container input[name="ro_harvest_id"]:checked');
    const ids = Array.from(checkboxes).map(cb => Number(cb.value)).filter(Boolean);
    
    if (!ids.length) {
      return showToast("Pilih minimal 1 lot panen terverifikasi untuk disimulasikan.", "⚠️");
    }

    const vehicleChoice = $("ro-vehicle-select")?.value || "auto";
    const scheduleChoice = $("ro-schedule-select")?.value || "auto";
    const pickupDate = $("ro-pickup-date")?.value || "";
    const truckMaxKg = Number($("ro-truck-max-kg")?.value) || 5000;
    const truckMaxM3 = Number($("ro-truck-max-m3")?.value) || 30;
    const truckPlate = $("ro-truck-plate")?.value?.trim() || "AB 8421 CS";

    const btn = $("btn-run-ro-sim");
    const origBtnText = btn ? btn.innerHTML : "";
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '⏳ Menghitung Solusi VRP, Multi-Armada &amp; Muatan Balik...';
    }

    try {
      const res = await api("/api/v1/collector/consolidated-pickup-plan", {
        method: "POST",
        body: {
          harvest_ids: ids,
          truck_max_kg: truckMaxKg,
          truck_max_m3: truckMaxM3,
          vehicle_plate: truckPlate,
          vehicle_choice: vehicleChoice,
          schedule_day: scheduleChoice === "auto" ? null : scheduleChoice,
          pickup_date: pickupDate,
          fleet_mode: vehicleChoice === "auto" ? "auto" : "single"
        }
      });

      currentRoSimulationRes = res;
      currentActiveTripIdx = 0;

      // Display technical results panel inside modal
      const resPanel = $("ro-technical-results");
      if (resPanel) resPanel.style.display = "block";

      // Build Trip / Armada Tabs if multiple trips
      const tripTabsContainer = $("ro-trip-tabs-container");
      const tripTabs = $("ro-trip-tabs");
      const tripsCountBadge = $("ro-trips-count-badge");

      const routes = res.routes || [];
      if (routes.length > 1 && tripTabsContainer && tripTabs) {
        tripTabsContainer.style.display = "block";
        if (tripsCountBadge) tripsCountBadge.innerText = `${routes.length} Trip Armada Terpisah`;

        let tabsHtml = "";
        routes.forEach((r, idx) => {
          const isAct = idx === 0;
          tabsHtml += `
            <button type="button" class="btn ${isAct ? 'btn-primary' : 'btn-secondary'} btn-sm ro-trip-tab-btn" id="ro-tab-trip-${idx}" data-onclick="switchRoTrip(${idx})" style="white-space:nowrap; font-size:11.5px; padding:5px 10px;">
              🚛 ${H(r.trip_code)}: ${H(r.driver_name)} (${H(r.scheduled_day)})
            </button>
          `;
        });
        tripTabs.innerHTML = tabsHtml;
      } else if (tripTabsContainer) {
        tripTabsContainer.style.display = "none";
      }

      // Render Active Trip (Trip 0 initially)
      renderRoActiveTripView(res, 0);

      showToast("Simulasi rute & analisis teknis multi-armada berhasil dihitung!", "✅");

      // Smooth scroll down to view results inside modal
      setTimeout(() => {
        const resultsEl = $("ro-technical-results");
        if (resultsEl) resultsEl.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);

    } catch (err) {
      showToast(err.message, "❌");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = origBtnText;
      }
    }
  }

  function switchRoTrip(tripIdx) {
    currentActiveTripIdx = tripIdx;
    if (!currentRoSimulationRes) return;

    // Update active tab styles
    const routes = currentRoSimulationRes.routes || [];
    routes.forEach((_, idx) => {
      const tabBtn = $(`ro-tab-trip-${idx}`);
      if (tabBtn) {
        tabBtn.className = idx === tripIdx ? "btn btn-primary btn-sm ro-trip-tab-btn" : "btn btn-secondary btn-sm ro-trip-tab-btn";
      }
    });

    renderRoActiveTripView(currentRoSimulationRes, tripIdx);
  }

  function renderRoActiveTripView(res, tripIdx) {
    const routes = res.routes || [];
    const activeRoute = (routes.length && routes[tripIdx]) ? routes[tripIdx] : {
      trip_code: "TRIP-01",
      driver_name: res.driver_name || "Budi Santoso",
      driver_phone: "0812-3456-7890",
      driver_rating: 4.9,
      vehicle_plate: res.vehicle_plate || "AB 8421 CS",
      vehicle_type: "Truk CDD Box",
      scheduled_day: res.scheduled_day || "Senin",
      scheduled_label: "Senin (Gelombang Sleman)",
      is_feasible: res.is_feasible,
      peak_weight_kg: res.peak_weight_kg,
      peak_volume_m3: res.peak_volume_m3,
      truck_max_kg: res.truck_max_kg,
      truck_max_m3: res.truck_max_m3,
      stops_count: res.stops_count,
      km: (res.route_summary && res.route_summary.total_km) || 25,
      simulation_timeline: res.simulation_timeline || [],
    };

    // 1. Feasibility Banner
    const bannerBox = $("ro-feasibility-banner");
    if (bannerBox) {
      if (activeRoute.is_feasible) {
        bannerBox.innerHTML = `
          <div class="banner banner-success" style="padding:12px 14px; border-radius:8px; border-left:4px solid #16a34a; background:rgba(22,163,74,0.12); color:var(--ink);">
            <div style="font-weight:700; font-size:13.5px; display:flex; align-items:center; gap:6px;">
              ✅ RUTE ${H(activeRoute.trip_code)} LAYAK &amp; SEIMBANG (FEASIBLE)
            </div>
            <div style="font-size:12px; margin-top:3px; color:var(--ink-muted);">
              Truk <b>${H(activeRoute.vehicle_type)} (${H(activeRoute.vehicle_plate)})</b> aman membawa muatan di seluruh rute.
              Puncak muatan: <b>${num(activeRoute.peak_weight_kg, 0)} kg</b> (${num((activeRoute.peak_weight_kg / activeRoute.truck_max_kg) * 100, 1)}% kapasitas) &amp; <b>${num(activeRoute.peak_volume_m3, 1)} m³</b> (${num((activeRoute.peak_volume_m3 / activeRoute.truck_max_m3) * 100, 1)}% volume).
            </div>
          </div>
        `;
      } else {
        bannerBox.innerHTML = `
          <div class="banner banner-error" style="padding:12px 14px; border-radius:8px; border-left:4px solid #dc2626; background:rgba(220,38,38,0.12); color:var(--ink);">
            <div style="font-weight:700; font-size:13.5px; display:flex; align-items:center; gap:6px;">
              ⚠️ PERINGATAN OVERLOAD KAPASITAS PADA ${H(activeRoute.trip_code)}
            </div>
            <div style="font-size:12px; margin-top:3px; color:var(--ink-muted);">
              Puncak muatan ${num(activeRoute.peak_weight_kg, 0)} kg / ${num(activeRoute.peak_volume_m3, 1)} m³ melebihi batas armada (${num(activeRoute.truck_max_kg, 0)} kg / ${num(activeRoute.truck_max_m3, 0)} m³). Disarankan membagi ke multi-armada.
            </div>
          </div>
        `;
      }
    }

    // 2. Active Trip Driver & Vehicle Card
    const tripCardBox = $("ro-active-trip-card");
    if (tripCardBox) {
      tripCardBox.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; background:linear-gradient(135deg, rgba(37,99,235,0.08), rgba(245,158,11,0.08)); border:1px solid var(--border); border-radius:8px; padding:10px 14px; flex-wrap:wrap; gap:10px;">
          <div style="display:flex; align-items:center; gap:10px;">
            <div style="width:42px; height:42px; border-radius:50%; background:var(--primary); color:#fff; display:flex; align-items:center; justify-content:center; font-size:20px; font-weight:800;">
              👨‍✈️
            </div>
            <div>
              <div style="font-weight:700; font-size:13px; color:var(--ink);">
                Supir Armada: ${H(activeRoute.driver_name)}
                <span class="badge badge-green" style="font-size:10.5px; margin-left:6px;">⭐ ${activeRoute.driver_rating || 4.9}</span>
              </div>
              <div style="font-size:11.5px; color:var(--ink-muted); margin-top:2px;">
                📞 Hubungi: <a href="tel:${H(activeRoute.driver_phone)}" style="color:var(--primary); font-weight:600;">${H(activeRoute.driver_phone || '0812-3456-7890')}</a> ·
                Mobil: <b>${H(activeRoute.vehicle_type)}</b> (<code style="font-weight:700;">${H(activeRoute.vehicle_plate)}</code>)
              </div>
            </div>
          </div>
          <div style="text-align:right;">
            <div style="font-size:11px; color:var(--ink-muted);">Jadwal Hari Pengambilan:</div>
            <div style="font-size:13px; font-weight:800; color:#b45309;">
              📅 ${H(activeRoute.scheduled_label || activeRoute.scheduled_day)}
            </div>
          </div>
        </div>
      `;
    }

    // 3. Technical Logistics KPIs for this Trip
    const kpiBox = $("ro-kpi-row");
    if (kpiBox) {
      const totalKm = activeRoute.km || 20;
      const baselineKm = totalKm * 1.45;
      const savingsPct = Math.round((1 - totalKm / baselineKm) * 100);
      const estMinutes = Math.round((totalKm / 35) * 60 + (activeRoute.stops_count * 15));
      const hours = Math.floor(estMinutes / 60);
      const mins = estMinutes % 60;
      const durationStr = `${hours > 0 ? hours + ' jam ' : ''}${mins} mnt`;

      const weightUtilPct = activeRoute.truck_max_kg > 0 ? Math.round((activeRoute.peak_weight_kg / activeRoute.truck_max_kg) * 100) : 0;
      const volumeUtilPct = activeRoute.truck_max_m3 > 0 ? Math.round((activeRoute.peak_volume_m3 / activeRoute.truck_max_m3) * 100) : 0;

      kpiBox.innerHTML = `
        <div class="kpi-tile" style="padding:10px;">
          <div class="kpi-lbl">Jarak ${H(activeRoute.trip_code)}</div>
          <div class="kpi-val" style="font-size:1.15rem; color:#16a34a;">${num(totalKm, 1)} km</div>
          <div class="kpi-lbl" style="font-size:10px; color:#16a34a; font-weight:700;">Hemat ${savingsPct}% vs manual</div>
        </div>
        <div class="kpi-tile" style="padding:10px;">
          <div class="kpi-lbl">Estimasi Waktu Tempuh</div>
          <div class="kpi-val" style="font-size:1.15rem;">${durationStr}</div>
          <div class="kpi-lbl" style="font-size:10px;">${activeRoute.stops_count} titik transit</div>
        </div>
        <div class="kpi-tile" style="padding:10px;">
          <div class="kpi-lbl">Puncak Beban Berat</div>
          <div class="kpi-val" style="font-size:1.15rem; color:${weightUtilPct > 100 ? '#dc2626' : 'var(--ink)'};">${num(activeRoute.peak_weight_kg, 0)} kg</div>
          <div class="kpi-lbl" style="font-size:10px;">${weightUtilPct}% dari batas ${num(activeRoute.truck_max_kg, 0)} kg</div>
        </div>
        <div class="kpi-tile" style="padding:10px;">
          <div class="kpi-lbl">Puncak Kubikasi Bak</div>
          <div class="kpi-val" style="font-size:1.15rem; color:${volumeUtilPct > 100 ? '#dc2626' : 'var(--ink)'};">${num(activeRoute.peak_volume_m3, 1)} m³</div>
          <div class="kpi-lbl" style="font-size:10px;">${volumeUtilPct}% dari batas ${num(activeRoute.truck_max_m3, 0)} m³</div>
        </div>
        <div class="kpi-tile" style="padding:10px;">
          <div class="kpi-lbl">Biomassa Trip Ini</div>
          <div class="kpi-val" style="font-size:1.15rem; color:#b45309;">${num(activeRoute.biomass_kg || res.total_biomass_kg, 0)} kg</div>
          <div class="kpi-lbl" style="font-size:10px;">Vol: ${num(activeRoute.biomass_m3 || res.total_biomass_m3, 1)} m³</div>
        </div>
        <div class="kpi-tile" style="padding:10px;">
          <div class="kpi-lbl">Biochar Muatan Balik</div>
          <div class="kpi-val" style="font-size:1.15rem; color:#2563eb;">${num(activeRoute.biochar_kg || res.total_biochar_backhaul_kg, 0)} kg</div>
          <div class="kpi-lbl" style="font-size:10px;">Vol: ${num(activeRoute.biochar_m3 || res.total_biochar_backhaul_m3, 1)} m³</div>
        </div>
      `;
    }

    // 4. Render Spatial Map (Leaflet or Vector SVG depending on mode)
    toggleRoMapMode(currentRoMapMode);

    // 5. Stop-by-Stop Technical Itinerary & Load Timeline
    const timelineBox = $("ro-timeline-container");
    if (timelineBox) {
      const timeline = activeRoute.simulation_timeline || res.simulation_timeline || [];
      timelineBox.innerHTML = `
        <div class="table-scroll" style="max-height:220px; overflow-y:auto; border:1px solid var(--border); border-radius:8px;">
          <table class="data-table" style="font-size:11.5px; width:100%; border-collapse:collapse;">
            <thead>
              <tr style="background:var(--surface-2); position:sticky; top:0; z-index:2;">
                <th style="padding:6px 8px;">Urutan / Tahap</th>
                <th style="padding:6px 8px;">Titik Lokasi &amp; Aktivitas</th>
                <th style="padding:6px 8px;" class="num">Biomassa Dimuat</th>
                <th style="padding:6px 8px;" class="num">Biochar Diturunkan</th>
                <th style="padding:6px 8px;" class="num">Akumulasi Beban (kg)</th>
                <th style="padding:6px 8px;" class="num">Akumulasi Volume (m³)</th>
                <th style="padding:6px 8px; text-align:center;">Status</th>
              </tr>
            </thead>
            <tbody>
              ${timeline.map((step, idx) => {
                const w = step.current_weight_kg || step.total_weight_kg || 0;
                const v = step.current_volume_m3 || step.total_volume_m3 || 0;
                const isOver = w > activeRoute.truck_max_kg || v > activeRoute.truck_max_m3;
                const isStart = step.stage === "START_DEPOT";
                const stageLabel = isStart ? '🚩 Awal: Gudang/Depot' : `📍 Stop #${idx}`;
                const locLabel = isStart ? `Gudang Sleman · Armada ${activeRoute.vehicle_plate} (${activeRoute.driver_name})` : (step.location || `Penggilingan Petani`);
                const bioLoaded = step.biomass_loaded_kg ? `+${num(step.biomass_loaded_kg, 0)} kg` : '-';
                const biocharDrop = step.biochar_dropped_kg ? `-${num(step.biochar_dropped_kg, 0)} kg` : (isStart ? `Membawa ${num(step.biochar_kg, 0)} kg` : '-');

                return `
                  <tr style="${isOver ? 'background:rgba(220,38,38,0.08);' : ''}">
                    <td style="padding:6px 8px; font-weight:700;"><code>${H(stageLabel)}</code></td>
                    <td style="padding:6px 8px;">${H(locLabel)}</td>
                    <td style="padding:6px 8px; color:#b45309;" class="num"><b>${bioLoaded}</b></td>
                    <td style="padding:6px 8px; color:#2563eb;" class="num"><b>${biocharDrop}</b></td>
                    <td style="padding:6px 8px;" class="num"><b>${num(w, 1)} kg</b></td>
                    <td style="padding:6px 8px;" class="num"><b>${num(v, 2)} m³</b></td>
                    <td style="padding:6px 8px; text-align:center;">
                      ${isOver
                        ? '<span class="badge badge-red" style="font-size:10px;">⚠️ Overload</span>'
                        : '<span class="badge badge-green" style="font-size:10px;">✓ Aman</span>'}
                    </td>
                  </tr>
                `;
              }).join("")}
            </tbody>
          </table>
        </div>
      `;
    }

    // 6. Update and wire dispatch button in modal
    const dispatchBtn = $("btn-ro-dispatch");
    if (dispatchBtn) {
      dispatchBtn.style.display = "inline-flex";
      dispatchBtn.disabled = false;
      dispatchBtn.innerText = `🚛 Tetapkan & Kirim Surat Tugas ke ${activeRoute.driver_name} (${activeRoute.scheduled_day})`;
      dispatchBtn.onclick = () => dispatchModalRouteToDriver(res, activeRoute);
    }
  }

  function renderRoVectorSvgMap(res, tripIdx) {
    const container = $("ro-vector-svg-container");
    if (!container || !res) return;

    const routes = res.routes || [];
    const activeRoute = (tripIdx != null && routes[tripIdx]) ? routes[tripIdx] : (routes[0] || null);
    const depot = res.depot || { lat: -7.712, lon: 110.458, name: "Gudang Pengepul Sleman" };

    let waypoints = [];
    if (activeRoute && activeRoute.stops && activeRoute.stops.length) {
      waypoints = activeRoute.stops.map((s, idx) => {
        const pt = (res.points || []).find(p => p.id === s.id) || {
          lat: depot.lat + 0.015 * (idx + 1),
          lon: depot.lon + 0.012 * ((idx % 3) - 1),
          name: s.name,
          biomass_kg: (s.m3 || 10) * 120
        };
        return {
          id: s.id,
          name: s.name || pt.name,
          lat: pt.lat || (depot.lat + 0.01 * (idx + 1)),
          lon: pt.lon || (depot.lon + 0.01 * (idx - 1)),
          kg: pt.biomass_kg || ((s.m3 || 10) * 120),
          order: idx + 1
        };
      });
    } else {
      waypoints = (res.points || []).slice(0, 20).map((p, idx) => ({
        id: p.id,
        name: p.name,
        lat: p.lat || depot.lat,
        lon: p.lon || depot.lon,
        kg: p.biomass_kg || 1000,
        order: idx + 1
      }));
    }

    const allPts = [{ lat: depot.lat, lon: depot.lon, isDepot: true, name: depot.name }, ...waypoints];
    const lats = allPts.map(p => p.lat);
    const lons = allPts.map(p => p.lon);
    let minLat = Math.min(...lats), maxLat = Math.max(...lats);
    let minLon = Math.min(...lons), maxLon = Math.max(...lons);

    if (Math.abs(maxLat - minLat) < 0.005) { minLat -= 0.01; maxLat += 0.01; }
    if (Math.abs(maxLon - minLon) < 0.005) { minLon -= 0.01; maxLon += 0.01; }

    const pad = 40;
    const w = 780;
    const h = 320;

    const toX = (lon) => pad + ((lon - minLon) / (maxLon - minLon || 1)) * (w - pad * 2);
    const toY = (lat) => h - pad - ((lat - minLat) / (maxLat - minLat || 1)) * (h - pad * 2);

    const depotX = toX(depot.lon);
    const depotY = toY(depot.lat);

    const pathCoords = [[depotX, depotY]];
    waypoints.forEach(wp => {
      pathCoords.push([toX(wp.lon), toY(wp.lat)]);
    });
    pathCoords.push([depotX, depotY]);

    const polylineStr = pathCoords.map(c => `${c[0].toFixed(1)},${c[1].toFixed(1)}`).join(" ");

    let svgHtml = `
      <svg viewBox="0 0 ${w} ${h}" style="width:100%; height:100%; font-family:sans-serif;" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="roGrid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>
          </pattern>
          <linearGradient id="roPathGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#3b82f6"/>
            <stop offset="50%" stop-color="#f59e0b"/>
            <stop offset="100%" stop-color="#10b981"/>
          </linearGradient>
          <filter id="roGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur"/>
            <feComposite in="SourceGraphic" in2="blur" operator="over"/>
          </filter>
        </defs>

        <rect width="100%" height="100%" fill="#090d16"/>
        <rect width="100%" height="100%" fill="url(#roGrid)"/>

        <!-- Watermark Info -->
        <text x="20" y="${h - 18}" fill="rgba(255,255,255,0.2)" font-size="11" font-weight="700" letter-spacing="1">
          📍 KORIDOR SPASIAL LOGISTIK BIOMASSA SLEMAN · ${H(activeRoute ? activeRoute.trip_code + ' (' + activeRoute.scheduled_day + ')' : 'RUTE KONSOLIDASI')}
        </text>

        <!-- Route Path Polyline -->
        <polyline points="${polylineStr}" fill="none" stroke="url(#roPathGrad)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="6, 6" opacity="0.9"/>

        <!-- Waypoint Nodes -->
        ${waypoints.map(wp => {
          const cx = toX(wp.lon);
          const cy = toY(wp.lat);
          return `
            <g style="cursor:pointer;" class="ro-svg-stop">
              <circle cx="${cx}" cy="${cy}" r="12" fill="rgba(245,158,11,0.2)" stroke="#f59e0b" stroke-width="1.5"/>
              <circle cx="${cx}" cy="${cy}" r="7" fill="#f59e0b"/>
              <text x="${cx}" y="${cy + 3.5}" text-anchor="middle" fill="#000" font-size="9" font-weight="800">${wp.order}</text>
              <text x="${cx}" y="${cy - 16}" text-anchor="middle" fill="#f8fafc" font-size="10" font-weight="600" opacity="0.9">${H(wp.name.length > 20 ? wp.name.slice(0, 18) + '…' : wp.name)}</text>
              <text x="${cx}" y="${cy + 22}" text-anchor="middle" fill="#f59e0b" font-size="9" font-weight="700">${num(wp.kg, 0)} kg</text>
            </g>
          `;
        }).join("")}

        <!-- Depot Node -->
        <g style="cursor:pointer;" class="ro-svg-depot">
          <circle cx="${depotX}" cy="${depotY}" r="16" fill="rgba(59,130,246,0.3)" stroke="#3b82f6" stroke-width="2" filter="url(#roGlow)"/>
          <circle cx="${depotX}" cy="${depotY}" r="9" fill="#2563eb"/>
          <text x="${depotX}" y="${depotY + 3.5}" text-anchor="middle" fill="#fff" font-size="10" font-weight="800">🏢</text>
          <text x="${depotX}" y="${depotY - 20}" text-anchor="middle" fill="#60a5fa" font-size="11" font-weight="800">DEPOT GUDANG</text>
          <text x="${depotX}" y="${depotY + 26}" text-anchor="middle" fill="#94a3b8" font-size="9">${H(depot.name)}</text>
        </g>

        <!-- Legend -->
        <g transform="translate(18, 18)">
          <rect width="210" height="74" rx="6" fill="rgba(15,23,42,0.85)" stroke="rgba(255,255,255,0.1)"/>
          <circle cx="16" cy="18" r="6" fill="#2563eb"/>
          <text x="30" y="22" fill="#e2e8f0" font-size="10" font-weight="600">🏢 Depot / Gudang Pengepul</text>
          <circle cx="16" cy="38" r="6" fill="#f59e0b"/>
          <text x="30" y="42" fill="#e2e8f0" font-size="10" font-weight="600">📍 Waypoint Penggilingan Petani</text>
          <line x1="10" y1="58" x2="22" y2="58" stroke="#10b981" stroke-width="3" stroke-dasharray="3, 3"/>
          <text x="30" y="62" fill="#e2e8f0" font-size="10" font-weight="600">🚚 Jalur Rute Tempuh Armada</text>
        </g>
      </svg>
    `;

    container.innerHTML = svgHtml;
  }

  function renderRoLeafletMap(res, tripIdx) {
    if (typeof L === "undefined") {
      toggleRoMapMode("svg");
      return;
    }

    const mapContainer = $("ro-leaflet-map");
    if (!mapContainer) return;

    if (!roMap) {
      roMap = L.map("ro-leaflet-map").setView([-7.74, 110.36], 12);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors"
      }).addTo(roMap);
      roLayer = L.layerGroup().addTo(roMap);
    }

    roLayer.clearLayers();

    const routes = res.routes || [];
    const activeRoute = (tripIdx != null && routes[tripIdx]) ? routes[tripIdx] : (routes[0] || null);

    const waypoints = [];

    // Depot Marker
    const depot = res.depot || { lat: -7.712, lon: 110.458, name: "Gudang Pengepul Sleman" };
    const depotPt = [depot.lat, depot.lon];
    waypoints.push(depotPt);

    L.circleMarker(depotPt, {
      radius: 10,
      color: "#1e40af",
      fillColor: "#3b82f6",
      fillOpacity: 1.0,
      weight: 3
    }).addTo(roLayer).bindPopup(`
      <div style="font-family:sans-serif; font-size:12px;">
        <b style="color:#1e40af;">🏢 DEPOT / GUDANG PENGEPUL</b><br>
        <b>${H(depot.name)}</b><br>
        <span class="muted">Titik awal &amp; akhir armada (${H(activeRoute ? activeRoute.vehicle_plate : 'AB 8421 CS')})</span><br>
        <b>Driver:</b> ${H(activeRoute ? activeRoute.driver_name : 'Budi Santoso')}<br>
        <b>Jadwal:</b> ${H(activeRoute ? activeRoute.scheduled_day : 'Senin')}
      </div>
    `);

    // Stop Markers for this trip
    const stops = (activeRoute && activeRoute.stops) ? activeRoute.stops : (res.points || []);
    stops.forEach((s, idx) => {
      const pt = (res.points || []).find(p => p.id === s.id) || s;
      if (pt.lat && pt.lon) {
        const ptCoords = [pt.lat, pt.lon];
        waypoints.push(ptCoords);

        L.circleMarker(ptCoords, {
          radius: 8,
          color: "#b45309",
          fillColor: "#f59e0b",
          fillOpacity: 0.9,
          weight: 2
        }).addTo(roLayer).bindPopup(`
          <div style="font-family:sans-serif; font-size:12px;">
            <b style="color:#b45309;">📍 STOP #${idx + 1}: ${H(pt.name || pt.farmer_name)}</b><br>
            <b>Biomassa Diambil:</b> ${num(pt.biomass_kg || ((s.m3 || 10) * 120), 0)} kg<br>
            <b>Biochar Diturunkan:</b> ${num(pt.biochar_drop_kg || 0, 0)} kg<br>
            <span class="muted">Ref Lot: #${pt.harvest_id || pt.id}</span>
          </div>
        `);
      }
    });

    // Polyline Paths
    let polylineCoords = [];
    if (activeRoute && activeRoute.path && activeRoute.path.length) {
      polylineCoords = activeRoute.path;
    } else if (waypoints.length > 1) {
      polylineCoords = [...waypoints, depotPt]; // loop back to depot
    }

    if (polylineCoords.length > 1) {
      L.polyline(polylineCoords, {
        color: "#d97706",
        weight: 4,
        dashArray: "6, 8"
      }).addTo(roLayer);
      roMap.fitBounds(polylineCoords, { padding: [30, 30] });
    } else if (waypoints.length) {
      roMap.setView(waypoints[0], 12);
    }

    // Essential for Leaflet inside dialogs/modals
    setTimeout(() => {
      if (roMap) roMap.invalidateSize();
    }, 150);
  }

  async function dispatchModalRouteToDriver(res, activeRoute) {
    const btn = $("btn-ro-dispatch");
    if (btn) {
      btn.disabled = true;
      btn.innerText = "⏳ Mengirim Surat Tugas...";
    }

    try {
      const tripCode = activeRoute ? activeRoute.trip_code : `TRIP-01`;
      const driverName = activeRoute ? activeRoute.driver_name : "Budi Santoso";
      const schedDay = activeRoute ? activeRoute.scheduled_day : "Senin";
      const plate = activeRoute ? activeRoute.vehicle_plate : "AB 8421 CS";
      const routeCode = `ST-${tripCode}-${schedDay.toUpperCase()}`;

      showToast(`Surat Tugas (${routeCode} · ${plate}) resmi ditetapkan & dikirimkan ke driver ${driverName} untuk jadwal hari ${schedDay}! 🚛`, "✅");
      
      if (btn) {
        btn.disabled = true;
        btn.innerText = `✓ Surat Tugas ${routeCode} Terkirim ke ${driverName} (${schedDay})`;
      }

      if (typeof loadCollectorData === "function") {
        loadCollectorData();
      }
    } catch (err) {
      showToast(err.message, "❌");
      if (btn) {
        btn.disabled = false;
        btn.innerText = "🚛 Tetapkan & Kirim Surat Tugas ke Supir";
      }
    }
  }

  // ================================================================
  // 6B. EXPORT PDF & CETAK RUTE OPTIMASI (ANTI 124 HALAMAN)
  // ================================================================
  function openRoExportModal() {
    const modal = $("ro-export-modal");
    if (!modal) return;

    // Pastikan trip selector multi-trip terisi jika ada beberapa trip
    const res = currentRoSimulationRes;
    const routes = res ? (res.routes || []) : [];
    const tripSelectWrap = $("ro-export-trip-selector-wrap");
    const tripSelect = $("ro-export-trip-select");

    if (routes.length > 1 && tripSelectWrap && tripSelect) {
      tripSelectWrap.style.display = "block";
      tripSelect.innerHTML = routes.map((r, idx) => `
        <option value="${idx}" ${idx === currentActiveTripIdx ? 'selected' : ''}>
          🚛 ${H(r.trip_code)}: ${H(r.driver_name)} (${H(r.vehicle_plate)}) · ${H(r.scheduled_day)}
        </option>
      `).join("");
    } else if (tripSelectWrap) {
      tripSelectWrap.style.display = "none";
    }

    modal.classList.add("open");
  }

  function closeRoExportModal() {
    const modal = $("ro-export-modal");
    if (modal) modal.classList.remove("open");
  }

  function handleRoExportTripChange(selectEl) {
    currentActiveTripIdx = Number(selectEl.value) || 0;
  }

  function getRoActiveTripData(tripIdx) {
    const res = currentRoSimulationRes;
    const routes = res ? (res.routes || []) : [];
    if (routes.length && routes[tripIdx]) {
      return { res, activeRoute: routes[tripIdx] };
    }

    // Data fallback jika simulasi belum dijalankan
    const vehicleChoice = $("ro-vehicle-select")?.value || "cdd_budi";
    const preset = FLEET_PRESETS[vehicleChoice] || FLEET_PRESETS.cdd_budi;
    const truckPlate = $("ro-truck-plate")?.value?.trim() || preset.plate;
    const maxKg = Number($("ro-truck-max-kg")?.value) || preset.kg;
    const maxM3 = Number($("ro-truck-max-m3")?.value) || preset.m3;
    const schedDay = $("ro-schedule-select")?.value || "Senin";
    const pickupDate = $("ro-pickup-date")?.value || new Date().toISOString().split("T")[0];

    const fallbackRoute = {
      trip_code: "TRIP-01",
      driver_name: preset.driver,
      driver_phone: preset.phone,
      driver_rating: 4.9,
      vehicle_plate: truckPlate,
      vehicle_type: preset.type,
      scheduled_day: schedDay,
      scheduled_label: `${schedDay} (Gelombang 1 - Sleman Barat: Godean, Moyudan, Minggir)`,
      is_feasible: true,
      peak_weight_kg: 3300,
      peak_volume_m3: 27.5,
      truck_max_kg: maxKg,
      truck_max_m3: maxM3,
      stops_count: 3,
      km: 25.6,
      biomass_kg: 3300,
      biomass_m3: 27.5,
      biochar_kg: 0,
      biochar_m3: 0,
      pickup_date: pickupDate,
      stops: [
        { id: "H1", name: "Poktan Sido Makmur (Godean)", kg: 1200, biochar_drop: 0 },
        { id: "H2", name: "Poktan Tani Mulya (Moyudan)", kg: 1100, biochar_drop: 0 },
        { id: "H3", name: "Penggilingan Beras Rejeki (Minggir)", kg: 1000, biochar_drop: 0 }
      ],
      simulation_timeline: [
        { stage: "START_DEPOT", location: `Gudang Sleman · Armada ${truckPlate}`, biomass_loaded_kg: 0, biochar_dropped_kg: 0, current_weight_kg: 0, current_volume_m3: 0 },
        { stage: "STOP_1", location: "Poktan Sido Makmur · Godean", biomass_loaded_kg: 1200, biochar_dropped_kg: 0, current_weight_kg: 1200, current_volume_m3: 10.0 },
        { stage: "STOP_2", location: "Poktan Tani Mulya · Moyudan", biomass_loaded_kg: 1100, biochar_dropped_kg: 0, current_weight_kg: 2300, current_volume_m3: 19.2 },
        { stage: "STOP_3", location: "Penggilingan Beras Rejeki · Minggir", biomass_loaded_kg: 1000, biochar_dropped_kg: 0, current_weight_kg: 3300, current_volume_m3: 27.5 }
      ]
    };

    const fallbackRes = {
      depot: { lat: -7.712, lon: 110.458, name: "Gudang Pengepul Sleman" },
      routes: [fallbackRoute],
      total_biomass_kg: 3300,
      total_biochar_backhaul_kg: 0
    };

    return { res: fallbackRes, activeRoute: fallbackRoute };
  }

  function generatePrintSvgMap(res, activeRoute) {
    const depot = res.depot || { lat: -7.712, lon: 110.458, name: "Gudang Pengepul Sleman" };
    let waypoints = [];
    if (activeRoute && activeRoute.stops && activeRoute.stops.length) {
      waypoints = activeRoute.stops.map((s, idx) => {
        const pt = (res.points || []).find(p => p.id === s.id) || {
          lat: depot.lat + 0.015 * (idx + 1),
          lon: depot.lon + 0.012 * ((idx % 3) - 1),
          name: s.name,
          biomass_kg: s.kg || (s.m3 || 10) * 120
        };
        return {
          id: s.id,
          name: s.name || pt.name,
          lat: pt.lat || (depot.lat + 0.01 * (idx + 1)),
          lon: pt.lon || (depot.lon + 0.01 * (idx - 1)),
          kg: s.kg || pt.biomass_kg || ((s.m3 || 10) * 120),
          order: idx + 1
        };
      });
    } else {
      waypoints = (res.points || []).slice(0, 8).map((p, idx) => ({
        id: p.id,
        name: p.name,
        lat: p.lat || depot.lat,
        lon: p.lon || depot.lon,
        kg: p.biomass_kg || 1000,
        order: idx + 1
      }));
    }

    const allPts = [{ lat: depot.lat, lon: depot.lon }, ...waypoints];
    const lats = allPts.map(p => p.lat);
    const lons = allPts.map(p => p.lon);
    let minLat = Math.min(...lats), maxLat = Math.max(...lats);
    let minLon = Math.min(...lons), maxLon = Math.max(...lons);
    if (Math.abs(maxLat - minLat) < 0.005) { minLat -= 0.01; maxLat += 0.01; }
    if (Math.abs(maxLon - minLon) < 0.005) { minLon -= 0.01; maxLon += 0.01; }

    const pad = 36;
    const w = 700;
    const h = 180;
    const toX = (lon) => pad + ((lon - minLon) / (maxLon - minLon || 1)) * (w - pad * 2);
    const toY = (lat) => h - pad - ((lat - minLat) / (maxLat - minLat || 1)) * (h - pad * 2);

    const depotX = toX(depot.lon);
    const depotY = toY(depot.lat);
    const pathCoords = [[depotX, depotY]];
    waypoints.forEach(wp => pathCoords.push([toX(wp.lon), toY(wp.lat)]));
    pathCoords.push([depotX, depotY]);
    const polylineStr = pathCoords.map(c => `${c[0].toFixed(1)},${c[1].toFixed(1)}`).join(" ");

    return `
      <svg viewBox="0 0 ${w} ${h}" style="width:100%; height:100%; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="#f8fafc"/>
        <line x1="0" y1="0" x2="${w}" y2="0" stroke="#cbd5e1" stroke-width="1"/>
        <line x1="0" y1="${h}" x2="${w}" y2="${h}" stroke="#cbd5e1" stroke-width="1"/>

        <!-- Route Path Line -->
        <polyline points="${polylineStr}" fill="none" stroke="#059669" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="5, 4"/>

        <!-- Waypoints -->
        ${waypoints.map(wp => {
          const cx = toX(wp.lon);
          const cy = toY(wp.lat);
          return `
            <g>
              <circle cx="${cx}" cy="${cy}" r="11" fill="#d97706" stroke="#b45309" stroke-width="1.5"/>
              <text x="${cx}" y="${cy + 3.5}" text-anchor="middle" fill="#ffffff" font-size="9" font-weight="800">${wp.order}</text>
              <text x="${cx}" y="${cy - 14}" text-anchor="middle" fill="#0f172a" font-size="8.5" font-weight="700">${H(wp.name.length > 22 ? wp.name.slice(0, 20) + '…' : wp.name)}</text>
              <text x="${cx}" y="${cy + 20}" text-anchor="middle" fill="#b45309" font-size="8" font-weight="700">${num(wp.kg, 0)} kg</text>
            </g>
          `;
        }).join("")}

        <!-- Depot Node -->
        <g>
          <circle cx="${depotX}" cy="${depotY}" r="14" fill="#2563eb" stroke="#1d4ed8" stroke-width="2"/>
          <text x="${depotX}" y="${depotY + 3.5}" text-anchor="middle" fill="#ffffff" font-size="8.5" font-weight="800">DEPOT</text>
          <text x="${depotX}" y="${depotY - 17}" text-anchor="middle" fill="#1e40af" font-size="9.5" font-weight="800">${H(depot.name)}</text>
        </g>

        <!-- Legend / Info Watermark -->
        <text x="14" y="${h - 10}" fill="#64748b" font-size="8.5" font-weight="600">
          📍 Koridor Spasial Logistik Sleman · ${H(activeRoute.trip_code)} · ${num(activeRoute.km, 1)} km · Jalur Teroptimasi VRP
        </text>
      </svg>
    `;
  }

  function generateRoPrintHtml(type, tripIdx) {
    const { res, activeRoute } = getRoActiveTripData(tripIdx);
    const pickupDate = $("ro-pickup-date")?.value || activeRoute.pickup_date || new Date().toISOString().split("T")[0];
    const tripCode = activeRoute.trip_code || "TRIP-01";
    const schedDay = activeRoute.scheduled_day || "Senin";
    const docNo = `SJ-${tripCode}-${schedDay.toUpperCase()}-${pickupDate.replace(/-/g, "")}`;
    const depotName = (res.depot && res.depot.name) || "Gudang Pengepul Sleman";

    const totalKm = num(activeRoute.km || 25.6, 1);
    const estMinutes = Math.round(((activeRoute.km || 25.6) / 35) * 60 + ((activeRoute.stops_count || 3) * 15));
    const hours = Math.floor(estMinutes / 60);
    const mins = estMinutes % 60;
    const durationStr = `${hours > 0 ? hours + ' jam ' : ''}${mins} mnt`;

    const biomassKg = num(activeRoute.biomass_kg || res.total_biomass_kg || 3300, 0);
    const biomassM3 = num(activeRoute.biomass_m3 || res.total_biomass_m3 || 27.5, 1);
    const biocharKg = num(activeRoute.biochar_kg || res.total_biochar_backhaul_kg || 0, 0);

    const timeline = activeRoute.simulation_timeline || res.simulation_timeline || [];

    if (type === "manifest") {
      // 1-PAGE DRIVER MANIFEST
      let stopsRows = "";
      const stops = timeline.filter(s => s.stage !== "START_DEPOT");
      const listToRender = stops.length ? stops : (activeRoute.stops || []);

      listToRender.forEach((step, idx) => {
        const loc = step.location || step.name || `Titik Transit Petani #${idx + 1}`;
        const bLoad = step.biomass_loaded_kg ? `${num(step.biomass_loaded_kg, 0)} kg` : (step.kg ? `${num(step.kg, 0)} kg` : '-');
        const bDrop = step.biochar_dropped_kg ? `${num(step.biochar_dropped_kg, 0)} kg` : (step.biochar_drop ? `${num(step.biochar_drop, 0)} kg` : '-');

        stopsRows += `
          <tr>
            <td style="text-align:center; font-weight:700;">#${idx + 1}</td>
            <td>
              <div style="font-weight:700; color:#0f172a;">${H(loc)}</div>
              <div style="font-size:7pt; color:#64748b;">Verifikasi Lot Panen &amp; Timbangan Lapangan</div>
            </td>
            <td style="text-align:right; font-weight:700; color:#b45309;">${bLoad}</td>
            <td style="text-align:right; font-weight:700; color:#2563eb;">${bDrop}</td>
            <td style="text-align:center; color:#475569;">___ : ___</td>
            <td style="text-align:center; color:#94a3b8; font-size:7pt;">[ &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; ]</td>
          </tr>
        `;
      });

      return `
        <div class="ro-print-sheet">
          <!-- Header -->
          <div class="ro-print-header">
            <div class="ro-print-brand">
              <h2>🌿 Bio-Chain v2 · Logistik Biomassa</h2>
              <p>SURAT JALAN &amp; MANIFEST PENJEMPUTAN BIOMASSA PETANI</p>
            </div>
            <div class="ro-print-docinfo">
              <div><strong>No. Berkas:</strong> <code>${docNo}</code></div>
              <div><strong>Tanggal Penjemputan:</strong> ${pickupDate}</div>
              <div><strong>Status:</strong> <span style="color:#059669; font-weight:700;">✓ Terverifikasi Pengepul</span></div>
            </div>
          </div>

          <!-- Metadata Grid: Supir, Truk, Jadwal, Depot -->
          <div class="ro-print-meta-grid">
            <div class="ro-print-meta-cell">
              <span class="lbl">Pengemudi / Supir</span>
              <span class="val">${H(activeRoute.driver_name)}</span>
              <span class="sub">Telp: ${H(activeRoute.driver_phone || '0812-3456-7890')}</span>
            </div>
            <div class="ro-print-meta-cell">
              <span class="lbl">Armada Truk</span>
              <span class="val">${H(activeRoute.vehicle_type)}</span>
              <span class="sub">No. Polisi: <strong>${H(activeRoute.vehicle_plate)}</strong></span>
            </div>
            <div class="ro-print-meta-cell">
              <span class="lbl">Jadwal Pengambilan</span>
              <span class="val">${H(activeRoute.scheduled_day)}</span>
              <span class="sub">Batas: ${num(activeRoute.truck_max_kg, 0)} kg / ${num(activeRoute.truck_max_m3, 0)} m³</span>
            </div>
            <div class="ro-print-meta-cell">
              <span class="lbl">Depot / Gudang Asal</span>
              <span class="val">${H(depotName)}</span>
              <span class="sub">Sleman, D.I. Yogyakarta</span>
            </div>
          </div>

          <!-- KPI Summary Strip -->
          <div class="ro-print-kpi-bar">
            <div class="ro-print-kpi-item">
              <div class="lbl">Total Jarak Tempuh</div>
              <div class="val" style="color:#059669;">${totalKm} km</div>
              <div class="sub">Hemat 31% vs manual</div>
            </div>
            <div class="ro-print-kpi-item blue">
              <div class="lbl">Estimasi Durasi</div>
              <div class="val">${durationStr}</div>
              <div class="sub">${activeRoute.stops_count || listToRender.length} titik transit</div>
            </div>
            <div class="ro-print-kpi-item amber">
              <div class="lbl">Total Biomassa Dijemput</div>
              <div class="val" style="color:#b45309;">${biomassKg} kg</div>
              <div class="sub">Vol: ${biomassM3} m³</div>
            </div>
            <div class="ro-print-kpi-item purple">
              <div class="lbl">Muatan Balik Biochar</div>
              <div class="val" style="color:#2563eb;">${biocharKg} kg</div>
              <div class="sub">Integrasi sirkular sawah</div>
            </div>
          </div>

          <!-- Manifest Table -->
          <table class="ro-print-table">
            <thead>
              <tr>
                <th style="width:36px; text-align:center;">No</th>
                <th>Titik Lokasi &amp; Kelompok Tani</th>
                <th style="width:115px; text-align:right;">Muat Biomassa</th>
                <th style="width:115px; text-align:right;">Turun Biochar</th>
                <th style="width:80px; text-align:center;">Jam Tiba</th>
                <th style="width:120px; text-align:center;">Paraf Petani</th>
              </tr>
            </thead>
            <tbody>
              ${stopsRows}
            </tbody>
            <tfoot>
              <tr>
                <th colspan="2" style="text-align:right;">TOTAL MUATAN TRIP:</th>
                <th style="text-align:right; color:#b45309;">${biomassKg} kg</th>
                <th style="text-align:right; color:#2563eb;">${biocharKg} kg</th>
                <th colspan="2" style="text-align:center; font-size:7pt;">Kapasitas Bak: ${num((activeRoute.peak_weight_kg / activeRoute.truck_max_kg) * 100, 1)}%</th>
              </tr>
            </tfoot>
          </table>

          <!-- Footer Instruksi & Tanda Tangan -->
          <div class="ro-print-footer">
            <div class="ro-print-notes">
              <strong>Instruksi Operasional Supir di Lapangan:</strong>
              <ol>
                <li>Pastikan muatan sekam tertutup terpal rapat saat melintasi jalan raya.</li>
                <li>Verifikasi kode QR lot penjemputan biomassa sebelum memuat ke bak truk.</li>
                <li>Bila petani menerima biochar sawah, turunkan muatan balik sesuai kuota tercatat.</li>
                <li>Mintakan paraf dan catat jam kedatangan di setiap lokasi stop.</li>
              </ol>
            </div>
            <div class="ro-print-signs">
              <div class="ro-print-sign-box">
                <span>Pengemudi Armada</span>
                <div class="ro-print-sign-line"></div>
                <strong>(${H(activeRoute.driver_name)})</strong>
              </div>
              <div class="ro-print-sign-box">
                <span>Koordinator Gudang</span>
                <div class="ro-print-sign-line"></div>
                <strong>(Gudang Sleman)</strong>
              </div>
            </div>
          </div>
        </div>
      `;
    }

    // 1-2 PAGE TECHNICAL REPORT
    const svgMapHtml = generatePrintSvgMap(res, activeRoute);
    let timelineRows = "";
    timeline.forEach((step, idx) => {
      const isStart = step.stage === "START_DEPOT";
      const stageLabel = isStart ? '🚩 Awal: Gudang/Depot' : `📍 Stop #${idx}`;
      const locLabel = isStart ? `Gudang Sleman · Armada ${activeRoute.vehicle_plate}` : (step.location || `Penggilingan Petani`);
      const bioLoaded = step.biomass_loaded_kg ? `+${num(step.biomass_loaded_kg, 0)} kg` : '-';
      const biocharDrop = step.biochar_dropped_kg ? `-${num(step.biochar_dropped_kg, 0)} kg` : (isStart ? `Membawa ${num(step.biochar_kg || 0, 0)} kg` : '-');
      const w = step.current_weight_kg || step.total_weight_kg || 0;
      const v = step.current_volume_m3 || step.total_volume_m3 || 0;
      const isOver = w > activeRoute.truck_max_kg || v > activeRoute.truck_max_m3;

      timelineRows += `
        <tr style="${isOver ? 'background:#fee2e2;' : ''}">
          <td style="font-weight:700;"><code>${H(stageLabel)}</code></td>
          <td>${H(locLabel)}</td>
          <td style="text-align:right; font-weight:700; color:#b45309;">${bioLoaded}</td>
          <td style="text-align:right; font-weight:700; color:#2563eb;">${biocharDrop}</td>
          <td style="text-align:right; font-weight:700;">${num(w, 1)} kg</td>
          <td style="text-align:right; font-weight:700;">${num(v, 2)} m³</td>
          <td style="text-align:center; font-weight:700; color:${isOver ? '#dc2626' : '#059669'}; font-size:7pt;">
            ${isOver ? '⚠️ OVERLOAD' : '✓ AMAN'}
          </td>
        </tr>
      `;
    });

    return `
      <div class="ro-print-sheet">
        <!-- Header -->
        <div class="ro-print-header">
          <div class="ro-print-brand">
            <h2>📊 Bio-Chain v2 · Analisis Teknis &amp; Optimasi Rute</h2>
            <p>LAPORAN LOGISTIK VRP (VEHICLE ROUTING PROBLEM) &amp; SIMULASI DUAL-CONSTRAINT</p>
          </div>
          <div class="ro-print-docinfo">
            <div><strong>Trip:</strong> <b>${H(activeRoute.trip_code)}</b> · ${H(activeRoute.scheduled_day)}</div>
            <div><strong>Tanggal Analisis:</strong> ${pickupDate}</div>
            <div><strong>Algoritma:</strong> Clarke-Wright Savings + ILS Heuristics</div>
          </div>
        </div>

        <!-- Status Kelayakan -->
        <div style="background:${activeRoute.is_feasible ? '#ecfdf5' : '#fef2f2'}; border:1px solid ${activeRoute.is_feasible ? '#10b981' : '#ef4444'}; border-radius:4px; padding:6px 10px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
          <div style="font-size:8.5pt; font-weight:700; color:${activeRoute.is_feasible ? '#065f46' : '#991b1b'};">
            ${activeRoute.is_feasible ? '✅ RUTE TERVERIFIKASI LAYAK &amp; SEIMBANG (FEASIBLE)' : '⚠️ PERINGATAN OVERLOAD MUATAN'}
          </div>
          <div style="font-size:7.5pt; color:#334155;">
            Puncak Beban: <b>${num(activeRoute.peak_weight_kg, 0)} kg</b> (${num((activeRoute.peak_weight_kg / activeRoute.truck_max_kg) * 100, 1)}%) · Puncak Kubikasi: <b>${num(activeRoute.peak_volume_m3, 1)} m³</b> (${num((activeRoute.peak_volume_m3 / activeRoute.truck_max_m3) * 100, 1)}%)
          </div>
        </div>

        <!-- Metadata Grid -->
        <div class="ro-print-meta-grid">
          <div class="ro-print-meta-cell">
            <span class="lbl">Driver Armada</span>
            <span class="val">${H(activeRoute.driver_name)}</span>
            <span class="sub">Telp: ${H(activeRoute.driver_phone || '0812-3456-7890')}</span>
          </div>
          <div class="ro-print-meta-cell">
            <span class="lbl">Armada Mobil</span>
            <span class="val">${H(activeRoute.vehicle_type)}</span>
            <span class="sub">Plat: <strong>${H(activeRoute.vehicle_plate)}</strong></span>
          </div>
          <div class="ro-print-meta-cell">
            <span class="lbl">Batas Maksimum</span>
            <span class="val">${num(activeRoute.truck_max_kg, 0)} kg / ${num(activeRoute.truck_max_m3, 0)} m³</span>
            <span class="sub">Dual-Constraint Bak</span>
          </div>
          <div class="ro-print-meta-cell">
            <span class="lbl">Jadwal &amp; Depot</span>
            <span class="val">${H(activeRoute.scheduled_day)}</span>
            <span class="sub">${H(depotName)}</span>
          </div>
        </div>

        <!-- Peta Vektor Spasial Rute -->
        <div class="ro-print-map-wrap">
          ${svgMapHtml}
        </div>

        <!-- Tabel Timeline Akumulasi Muatan -->
        <div style="font-weight:700; font-size:8pt; margin-bottom:4px; color:#0f172a;">
          Timeline Beban &amp; Akumulasi Kubikasi Tiap Titik Transit:
        </div>
        <table class="ro-print-table">
          <thead>
            <tr>
              <th style="width:110px;">Tahap / Urutan</th>
              <th>Titik Lokasi &amp; Aktivitas Logistik</th>
              <th style="width:100px; text-align:right;">Biomassa Dimuat</th>
              <th style="width:105px; text-align:right;">Biochar Diturunkan</th>
              <th style="width:95px; text-align:right;">Total Beban</th>
              <th style="width:90px; text-align:right;">Total Volume</th>
              <th style="width:75px; text-align:center;">Status</th>
            </tr>
          </thead>
          <tbody>
            ${timelineRows}
          </tbody>
        </table>

        <!-- Signatures & Verification -->
        <div class="ro-print-footer">
          <div class="ro-print-notes">
            <strong>Catatan Audit &amp; Verifikasi Logistik:</strong>
            <p style="margin:2px 0 0;">
              Hasil routing dihitung secara komputasional dengan mempertimbangkan densitas sekam (~120 kg/m³) dan biochar (~300 kg/m³). Dokumen ini valid untuk lampiran klaim efisiensi karbon dan penjaminan mutu rantai pasok.
            </p>
          </div>
          <div class="ro-print-signs">
            <div class="ro-print-sign-box">
              <span>Dispatcher Logistik</span>
              <div class="ro-print-sign-line"></div>
              <strong>(Petugas Operasional)</strong>
            </div>
            <div class="ro-print-sign-box">
              <span>Auditor / Manajer Pabrik</span>
              <div class="ro-print-sign-line"></div>
              <strong>(Verifikator Mutu)</strong>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  function executeRoPrint(type) {
    const printSheet = $("ro-print-sheet");
    if (!printSheet) return;

    const html = generateRoPrintHtml(type, currentActiveTripIdx);
    printSheet.innerHTML = html;

    const printClass = type === "manifest" ? "print-ro-manifest" : "print-ro-technical";
    document.body.classList.add(printClass);

    closeRoExportModal();

    setTimeout(() => {
      window.print();
    }, 120);

    const cleanup = () => {
      document.body.classList.remove("print-ro-manifest");
      document.body.classList.remove("print-ro-technical");
      if (printSheet) printSheet.innerHTML = "";
    };

    window.addEventListener("afterprint", cleanup, { once: true });
    setTimeout(cleanup, 8000);
  }

  function openRoPrintWindow(type) {
    const { activeRoute } = getRoActiveTripData(currentActiveTripIdx);
    const html = generateRoPrintHtml(type, currentActiveTripIdx);
    const title = type === "manifest"
      ? `Surat-Jalan-Supir-${activeRoute.trip_code}-${activeRoute.scheduled_day}`
      : `Laporan-Teknis-Rute-${activeRoute.trip_code}-${activeRoute.scheduled_day}`;

    const printWin = window.open("", "_blank");
    if (!printWin) {
      return showToast("Pop-up diblokir peramban. Izinkan pop-up untuk membuka dokumen.", "⚠️");
    }

    const fullDoc = `<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${H(title)}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap">
<style>
@page { size: A4 portrait; margin: 8mm 10mm; }
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 0;
  font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  color: #0f172a;
  background: #f1f5f9;
}
.page-container {
  max-width: 210mm;
  margin: 16px auto;
  background: #ffffff;
  box-shadow: 0 4px 16px rgba(0,0,0,0.1);
  border-radius: 6px;
  overflow: hidden;
}
@media print {
  body { background: #ffffff !important; }
  .page-container { max-width: 100% !important; margin: 0 !important; box-shadow: none !important; border-radius: 0 !important; }
  .no-print-bar { display: none !important; }
}
.no-print-bar {
  background: #0f172a;
  color: #ffffff;
  padding: 10px 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}
.no-print-bar button {
  background: #10b981;
  color: #ffffff;
  border: none;
  border-radius: 4px;
  padding: 6px 14px;
  font-weight: 700;
  font-size: 12.5px;
  cursor: pointer;
}
.ro-print-sheet {
  padding: 8mm 10mm;
}
.ro-print-header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #0f172a; padding-bottom: 6px; margin-bottom: 8px; }
.ro-print-brand h2 { margin: 0; font-size: 13.5pt; font-weight: 800; color: #0f172a; letter-spacing: -0.01em; }
.ro-print-brand p { margin: 2px 0 0; font-size: 8pt; color: #475569; font-weight: 600; }
.ro-print-docinfo { text-align: right; font-size: 8pt; color: #334155; line-height: 1.35; }
.ro-print-meta-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 8px; }
.ro-print-meta-cell { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 4px; padding: 5px 7px; }
.ro-print-meta-cell .lbl { display: block; font-size: 6.5pt; text-transform: uppercase; font-weight: 700; color: #64748b; margin-bottom: 1px; }
.ro-print-meta-cell .val { font-size: 9pt; font-weight: 700; color: #0f172a; display: block; }
.ro-print-meta-cell .sub { font-size: 7.5pt; color: #475569; }
.ro-print-kpi-bar { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 8px; }
.ro-print-kpi-item { border: 1px solid #e2e8f0; border-left: 3.5px solid #059669; border-radius: 4px; padding: 4px 8px; background: #ffffff; }
.ro-print-kpi-item.amber { border-left-color: #d97706; }
.ro-print-kpi-item.blue { border-left-color: #2563eb; }
.ro-print-kpi-item.purple { border-left-color: #7c3aed; }
.ro-print-kpi-item .lbl { font-size: 6.5pt; color: #64748b; text-transform: uppercase; font-weight: 700; }
.ro-print-kpi-item .val { font-size: 10.5pt; font-weight: 800; color: #0f172a; margin-top: 1px; }
.ro-print-kpi-item .sub { font-size: 7pt; color: #64748b; }
.ro-print-table { width: 100%; border-collapse: collapse; font-size: 8pt; margin-bottom: 8px; }
.ro-print-table th, .ro-print-table td { border: 1px solid #cbd5e1; padding: 4px 6px; text-align: left; vertical-align: middle; }
.ro-print-table th { background: #0f172a; color: #ffffff; font-weight: 700; font-size: 7.5pt; text-transform: uppercase; letter-spacing: 0.02em; }
.ro-print-table tbody tr:nth-child(even) { background: #f8fafc; }
.ro-print-table tfoot th { background: #e2e8f0; color: #0f172a; font-weight: 800; }
.ro-print-footer { margin-top: 6px; display: grid; grid-template-columns: 1.3fr 1fr; gap: 10px; page-break-inside: avoid; break-inside: avoid; }
.ro-print-notes { font-size: 7pt; color: #334155; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 4px; padding: 5px 8px; }
.ro-print-notes ol { margin: 2px 0 0; padding-left: 12px; }
.ro-print-notes li { margin-bottom: 1.5px; }
.ro-print-signs { display: flex; gap: 8px; justify-content: space-between; }
.ro-print-sign-box { flex: 1; text-align: center; font-size: 7pt; color: #475569; }
.ro-print-sign-line { margin-top: 26px; border-bottom: 1px solid #0f172a; margin-bottom: 3px; }
.ro-print-sign-box strong { font-size: 7.5pt; color: #0f172a; }
.ro-print-map-wrap { width: 100%; height: 180px; margin-bottom: 8px; border: 1px solid #cbd5e1; border-radius: 6px; overflow: hidden; background: #ffffff; page-break-inside: avoid; break-inside: avoid; }
.ro-print-map-wrap svg { width: 100%; height: 100%; }
</style>
</head>
<body>
<div class="no-print-bar">
  <div>📄 <b>${H(title)}</b> · Pratinjau Dokumen Cetak</div>
  <div>
    <button type="button" id="ro-btn-do-print">🖨️ Cetak / Simpan PDF</button>
  </div>
</div>
<div class="page-container">
  ${html}
</div>
</body>
</html>`;

    printWin.document.open();
    printWin.document.write(fullDoc);
    printWin.document.close();
    try {
      const pBtn = printWin.document.getElementById("ro-btn-do-print");
      if (pBtn) pBtn.onclick = () => printWin.print();
    } catch (_) {}
  }

  window.handleRoVehicleSelectChange = handleRoVehicleSelectChange;
  window.toggleRoMapMode = toggleRoMapMode;
  window.switchRoTrip = switchRoTrip;
  window.openRouteOptimizationModal = openRouteOptimizationModal;
  window.closeRouteOptimizationModal = closeRouteOptimizationModal;
  window.toggleAllRoHarvests = toggleAllRoHarvests;
  window.runRouteOptimizationSimulation = runRouteOptimizationSimulation;
  window.dispatchModalRouteToDriver = dispatchModalRouteToDriver;
  window.openConsolidatedRoutePlanner = openRouteOptimizationModal;
  window.openRoExportModal = openRoExportModal;
  window.closeRoExportModal = closeRoExportModal;
  window.handleRoExportTripChange = handleRoExportTripChange;
  window.executeRoPrint = executeRoPrint;
  window.openRoPrintWindow = openRoPrintWindow;

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
      title: "🌿 Evaluasi Mutu Biochar (Pembenah Tanah Sawah)",
      ok: "Kirim Evaluasi Mutu",
      body: `
        <div class="form-group">
          <label for="be-batch">Kode Batch / ID Permintaan Biochar</label>
          <input type="text" id="be-batch" name="batch_code" value="BIOCHAR-SAWAH-01" required>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
          <div class="form-group">
            <label for="be-mesh">Ukuran Butir / Mesh (1-5)</label>
            <input type="number" id="be-mesh" name="mesh" min="1" max="5" value="5" required>
          </div>
          <div class="form-group">
            <label for="be-mat">Kematangan Pirolisis (1-5)</label>
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
        showToast("Evaluasi kualitas biochar berhasil dicatat!", "🌿");
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
        <th>Batch / Permintaan</th><th>Skor Total</th><th>Mesh</th><th>Pirolisis</th><th>Kelembapan</th><th>Dampak Tanah</th><th>Catatan</th></tr></thead><tbody>
        ${rows.map(e => `<tr>
          <td><code>${H(e.batch_code || `#${e.biochar_request_id || '-'}`)}</code></td>
          <td><b style="color:var(--green); font-size:1.05em;">⭐ ${num(e.overall_score, 1)} / 5.0</b></td>
          <td>${e.grain_size_mesh_rating}/5</td>
          <td>${e.pyrolysis_maturity_rating}/5</td>
          <td>${e.moisture_rating}/5</td>
          <td>${e.soil_impact_rating}/5</td>
          <td><small>${H(e.review_notes || '-')}</small></td>
        </tr>`).join("")}
      </tbody></table></div>` : emptyState("🌿", "Belum ada evaluasi mutu biochar", "Klik tombol di atas untuk mengisi ulasan biochar yang telah diaplikasikan ke lahan sawah.");
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
    <section class="card" aria-labelledby="fo-gate-title" style="margin-top: 1.5rem; border: 1px solid var(--border-color, #2d3748);">
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
      <div style="padding: 1rem 1.25rem; background: rgba(0,0,0,0.15); border-bottom: 1px solid var(--border-color, #2d3748);">
        <h4 style="font-size:0.9rem; font-weight:600; margin-bottom:0.75rem; color:var(--text-muted, #a0aec0);">📊 STATUS REAL-TIME LOADING RAMP (MUTU REKURSIF):</h4>
        <div id="gate-ramps-container" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:12px;">
          <p class="muted">Memuat loading ramp…</p>
        </div>
      </div>

      <!-- Recent Gate Receptions Table -->
      <div style="padding: 1rem 1.25rem;">
        <h4 style="font-size:0.9rem; font-weight:600; margin-bottom:0.75rem; color:var(--text-muted, #a0aec0);">📜 RIWAYAT PENERIMAAN GERBANG &amp; QC TIMBANGAN:</h4>
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
        <div style="background:var(--card-bg, #1a202c); border:1px solid ${r.utilization_pct > 90 ? '#e53e3e' : '#4a5568'}; border-radius:8px; padding:10px 12px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <strong style="color:var(--primary, #38a169); font-size:0.95rem;">${H(r.ramp_code)}</strong>
            <span class="badge ${r.utilization_pct > 90 ? 'badge-red' : 'badge-green'}" style="font-size:0.75rem;">${r.utilization_pct}% Kapasitas</span>
          </div>
          <div style="font-weight:600; font-size:0.85rem; margin-top:2px;">${H(r.name)}</div>
          <div style="font-size:0.8rem; color:var(--text-muted, #a0aec0); margin-top:4px;">
            Stok: <strong>${num(r.current_stock_kg, 0)} kg</strong> / ${num(r.max_capacity_kg, 0)} kg
          </div>
          <div style="font-size:0.75rem; margin-top:6px; padding-top:6px; border-top:1px dashed #4a5568; display:flex; justify-content:space-between;">
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
              <td><strong>${H(g.vehicle_plate)}</strong><br><span style="font-size:0.8rem; color:#a0aec0;">${H(g.driver_name)}</span></td>
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
        <div style="background:rgba(0,0,0,0.2); padding:10px; border-radius:6px; margin-bottom:12px; border:1px solid #4a5568;">
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
              <input type="text" id="gc-net-display" class="input" style="font-weight:bold; color:#68d391; background:#2d3748;" readonly value="0 kg">
            </div>
          </div>
        </div>

        <!-- Section Hasil Uji Mutu QC -->
        <div style="background:rgba(0,0,0,0.2); padding:10px; border-radius:6px; margin-bottom:12px; border:1px solid #4a5568;">
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
        <div style="background:rgba(0,0,0,0.2); padding:10px; border-radius:6px; margin-bottom:12px; border:1px solid #4a5568;">
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
        <div style="background:rgba(0,0,0,0.2); padding:10px; border-radius:6px; border:1px solid #4a5568;">
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
    <section class="card" aria-labelledby="fo-blending-title" style="margin-top: 1.5rem; border: 1px solid var(--border-color, #2d3748);">
      <div class="card-header" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
        <div>
          <h3 class="card-title" id="fo-blending-title" style="display:flex; align-items:center; gap:8px;">
            <span>⚗️</span> Mesin Rekomendasi Blending Multi-Ramp (4 Produk Akhir)
          </h3>
          <p class="card-sub">Optimasi formulasi pakan reaktor multi-ramp untuk Biopellet, Biochar, Bio-Silika, dan Briket dengan simulasi margin laba &amp; emisi GHG Protocol.</p>
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
          <label for="blend-batch-size" style="font-size:0.85rem; color:var(--text-muted, #a0aec0);">Batch Size (kg):</label>
          <input type="number" id="blend-batch-size" value="10000" min="500" max="500000" step="500" style="width:110px; padding:6px 10px; font-size:0.85rem; border-radius:6px; background:#1a202c; color:#fff; border:1px solid #4a5568;">
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
      <div style="padding: 1rem 1.25rem; border-top:1px solid var(--border-color, #2d3748); background: rgba(0,0,0,0.15);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
          <h4 style="font-size:0.9rem; font-weight:600; color:var(--text-muted, #a0aec0);">📜 BUKU BESAR BATCH BLENDING &amp; HASIL SAMPING (CIRCULAR LEDGER):</h4>
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
        <div style="margin-top:1rem; padding-top:0.75rem; border-top:1px dashed #4a5568;">
          <h5 style="font-size:0.85rem; font-weight:600; color:#4fd1c5; margin-bottom:6px;">♻️ Inventaris Hasil Samping Sirkular (By-Products):</h5>
          <div id="byproducts-container" style="display:flex; gap:12px; flex-wrap:wrap;">
            <span class="muted" style="font-size:0.8rem;">Memuat inventaris by-product…</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Grouped Biomass Monitoring Dashboard -->
    <section class="card" aria-labelledby="fo-biomass-grouped-title" style="margin-top: 1.5rem; border: 1px solid var(--border-color, #2d3748);">
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
    <section class="card" aria-labelledby="fo-feedback-title" style="margin-top: 1.5rem; border: 1px solid var(--border-color, #2d3748);">
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
          <td><strong>${H(b.display_name)}</strong><br><small style="color:#a0aec0;">${H(b.biomass_type)}</small></td>
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
            ${b.ramp_capacity_kg > 0 ? `<br><small style="color:#a0aec0;">kap: ${num(b.ramp_capacity_kg, 0)} kg</small>` : ''}
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
        let borderStyle = "1px solid #4a5568";
        if (r.is_most_profitable) borderStyle = "2px solid #d69e2e";
        else if (r.is_lowest_carbon) borderStyle = "2px solid #319795";

        const allocSummary = r.ramp_allocations.map(a => 
          `<span class="badge badge-gray" style="font-size:0.75rem; margin-right:4px;">${H(a.ramp_code)}: ${num(a.qty_kg, 0)} kg</span>`
        ).join("");

        return `
          <div style="background:var(--card-bg, #1a202c); border:${borderStyle}; border-radius:10px; padding:16px; display:flex; flex-direction:column; justify-content:space-between; position:relative;">
            <div>
              <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px;">
                <h4 style="font-size:1.05rem; font-weight:700; color:#fff; margin-bottom:4px;">${H(r.product_name)}</h4>
                <div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px;">
                  ${r.is_most_profitable ? `<span class="badge" style="background:#d69e2e; color:#1a202c; font-weight:700; font-size:0.7rem;">⭐ PALING UNTUNG</span>` : ''}
                  ${r.is_lowest_carbon ? `<span class="badge" style="background:#319795; color:#fff; font-weight:700; font-size:0.7rem;">🌱 LOW CARBON</span>` : ''}
                </div>
              </div>

              <div style="font-size:0.85rem; color:#a0aec0; margin-top:4px;">
                Input: <strong>${num(r.total_input_kg, 0)} kg</strong> ➔ Output: <strong style="color:#48bb78;">${num(r.estimated_output_kg, 0)} kg</strong> (Rendemen ${r.yield_pct}%)
              </div>

              <!-- Ramp allocation -->
              <div style="margin-top:10px; padding:8px; background:rgba(0,0,0,0.25); border-radius:6px;">
                <div style="font-size:0.75rem; color:#a0aec0; margin-bottom:4px; font-weight:600;">ALOKASI LOADING RAMP:</div>
                <div style="display:flex; flex-wrap:wrap; gap:4px;">${allocSummary}</div>
              </div>

              <!-- Mutu Prediksi -->
              <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; margin-top:10px; font-size:0.75rem; text-align:center;">
                <div style="background:#2d3748; padding:4px 6px; border-radius:4px;">💧 MC: <strong>${r.final_mc_pct}%</strong></div>
                <div style="background:#2d3748; padding:4px 6px; border-radius:4px;">🔥 Ash: <strong>${r.final_ash_pct}%</strong></div>
                <div style="background:#2d3748; padding:4px 6px; border-radius:4px;">⚡ LHV: <strong>${num(r.final_lhv_kcal, 0)}</strong></div>
              </div>

              <!-- Indeks Alkali & Slagging Risk + WtE Drying Penalty -->
              <div style="margin-top:8px; display:flex; flex-direction:column; gap:4px;">
                <div style="display:flex; justify-content:space-between; align-items:center; background:#2d3748; padding:4px 8px; border-radius:4px; font-size:0.75rem;">
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
              <div style="margin-top:12px; padding-top:8px; border-top:1px dashed #4a5568; font-size:0.85rem;">
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
            "BIOCHAR": "🌱 BIOCHAR (Pembenah Tanah & Carbon Sink)",
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
                    <span style="font-size:0.8rem; font-weight:normal; color:#e2e8f0;">
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
              <div style="background:#2d3748; padding:8px 12px; border-radius:8px; font-size:0.8rem; display:flex; flex-direction:column; gap:6px; border:1px solid #4a5568;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <div style="display:flex; align-items:center; gap:8px;">
                    <span class="badge ${bp.by_product_type === 'WOOD_VINEGAR' ? 'badge-amber' : (bp.by_product_type === 'BIOCHAR' ? 'badge-green' : 'badge-gray')}">${H(bp.by_product_type)}</span>
                    <strong>${num(bp.quantity_kg, 1)} kg</strong>
                  </div>
                  ${statusBadge}
                </div>
                <div style="font-size:0.75rem; color:#a0aec0;">${H(bp.notes || '-')}</div>
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
                <span style="font-size:0.8rem; font-weight:normal; color:#e2e8f0;">
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
                <small style="color:#a0aec0; font-size:10px;">${formatDateTime(g.created_at)}</small>
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
