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
    d.addEventListener("close", () => d.remove());
    d.showModal();
    const first = d.querySelector("input, select, textarea");
    if (first) first.focus();
    return d;
  }

  // ================================================================ PENGEPUL
  const PENGEPUL_HTML = `
    <div class="grid-2">
      <section class="card" aria-labelledby="fo-proxy-title">
        <div class="card-header"><div>
          <h3 class="card-title" id="fo-proxy-title">👵 Petani tanpa HP</h3>
          <p class="card-sub">Daftarkan & laporkan sekam atas nama petani yang tidak punya HP. Petani menerima nota QR.</p></div>
          <button type="button" class="btn btn-secondary btn-sm" id="fo-proxy-new">➕ Daftarkan petani</button></div>
        <div id="fo-proxy-list"><p class="muted">Memuat…</p></div>
      </section>
      <section class="card" aria-labelledby="fo-pay-title">
        <div class="card-header"><div>
          <h3 class="card-title" id="fo-pay-title">💸 Bayar petani</h3>
          <p class="card-sub">Lot yang sudah Anda timbang tetapi belum tercatat dibayar. DP (uang muka) dipotong otomatis saat pelunasan.</p></div></div>
        <div id="fo-unpaid"><p class="muted">Memuat…</p></div>
      </section>
    </div>
    <section class="card" aria-labelledby="fo-ch-title">
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
                    data-name="${H(f.full_name)}">Lapor sekam</button></td></tr>`).join("")}</tbody></table></div>`
        : emptyState("👵", "Belum ada petani binaan", "Daftarkan petani yang tidak punya HP agar sekamnya tetap tercatat.");
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

  async function proxyReport(farmerId, name) {
    const mills = await millOptions();
    formDialog({
      title: `Lapor sekam · ${name}`, ok: "Laporkan",
      body: `<div class="form-group"><label for="fo-pr-qty">Jumlah sekam (kg)</label>
               <input id="fo-pr-qty" name="qty" type="number" min="50" max="50000" step="50" value="1000" required></div>
             <div class="form-group"><label for="fo-pr-mill">Lokasi penggilingan</label>
               <select id="fo-pr-mill" name="mill_id"><option value="">—</option>${mills}</select></div>
             ${QUALITY_FIELDS("fo-pr")}
             <p class="kpi-lbl">Isian sama dengan laporan petani sendiri. Nota QR setelah ini diberikan/difoto untuk petani.</p>`,
      onSubmit: async (fd) => {
        const r = await api("/api/v1/collector/proxy-harvest", { body: {
          farmer_id: farmerId, quantity_kg: Number(fd.get("qty")), mill_id: Number(fd.get("mill_id")) || null,
          moisture_est: fd.get("moisture_est") === "" ? null : Number(fd.get("moisture_est")),
          grade_est: fd.get("grade_est") || null,
          client_event_id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) } });
        openModal(`Nota sekam · ${r.farmer_name || name}`, r.qr_code, `${num(r.quantity_kg, 0)} kg · dilaporkan pengepul untuk petani`);
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
      box.innerHTML = rows.length ? `<div class="table-scroll"><table class="data-table"><thead><tr>
          <th>Lot</th><th>Petani</th><th class="num">Nilai</th><th>Aksi</th></tr></thead><tbody>${rows.map(r => `
          <tr><td>#${Number(r.harvest_id)}<br><span class="kpi-lbl">${num(r.verified_kg, 0)} kg · Grade ${H(r.grade || "-")}</span></td>
              <td>${H(r.farmer_name)}</td><td class="num"><b>${rp(r.amount_rp)}</b></td>
              <td style="white-space:nowrap;"><button type="button" class="btn btn-secondary btn-sm" data-fo-dp="${Number(r.harvest_id)}"
                    data-amount="${Number(r.amount_rp)}" data-name="${H(r.farmer_name)}" title="Uang muka; dipotong saat pelunasan">DP</button>
                  <button type="button" class="btn btn-primary btn-sm" data-fo-pay="${Number(r.harvest_id)}"
                    data-amount="${Number(r.amount_rp)}" data-name="${H(r.farmer_name)}">Bayar</button></td></tr>`).join("")}
          </tbody></table></div>`
        : emptyState("✅", "Semua lot sudah dibayar", "Lot baru muncul di sini setelah Anda menimbang & menguji sekam.");
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
      const text = `Halo ${c.farmer_name}, saya ${me} dari Bio-Chain. Terkait laporan sekam lot #${harvestId}: kapan bisa dijemput/ditimbang?`;
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
        <h3 class="card-title" id="fo-mypay-title">💰 Pembayaran Saya</h3>
        <p class="card-sub">Lapor stok → ditimbang &amp; diuji pengepul (harga final) → dibayar + kuitansi BYR.</p></div></div>
      <div class="kpi-row" id="fo-pay-kpis"></div>
      <div id="fo-waiting"></div>
      <h4 style="margin:16px 0 8px;">🧾 Kuitansi diterima</h4>
      <div id="fo-mypay"><p class="muted">Memuat…</p></div>
    </section>`;

  async function loadPayOverview() {
    const k = $("fo-pay-kpis"), w = $("fo-waiting");
    if (!k) return;
    try {
      const o = await api("/api/v1/farmer/payments/overview");
      k.innerHTML = `
        <div class="kpi-tile"><div class="kpi-lbl">Sudah diterima</div><div class="kpi-val">${rpShort(o.paid.net_rp)}</div>
          <div class="kpi-lbl">${num(o.paid.count, 0)} kuitansi</div></div>
        <div class="kpi-tile ${o.waiting.late_count ? "kpi-warn" : ""}"><div class="kpi-lbl">Menunggu dibayar</div><div class="kpi-val">${rpShort(o.waiting.net_rp)}</div>
          <div class="kpi-lbl">${num(o.waiting.count, 0)} lot${o.waiting.late_count ? ` · ${o.waiting.late_count} terlambat &gt; ${o.due_days} hari` : ""}</div></div>
        <div class="kpi-tile"><div class="kpi-lbl">Belum ditimbang</div><div class="kpi-val">${num(o.unweighed.quantity_kg, 0)} kg</div>
          <div class="kpi-lbl">${num(o.unweighed.count, 0)} laporan · harga belum final</div></div>`;
      const DP_LBL = { aktif: ["badge-blue", "aktif · dipotong saat lunas"], dipotong: ["badge-gray", "sudah dipotong"],
                       hangus_untuk_petani: ["badge-green", "hak Anda (pengepul batal)"], wajib_dikembalikan: ["badge-red", "wajib dikembalikan"],
                       dikembalikan: ["badge-gray", "dikembalikan"] };
      const dpHtml = (o.down_payments || []).length ? `<h4 style="margin:16px 0 8px;">🤝 Uang muka (DP) diterima</h4>
        <div class="table-scroll"><table class="data-table"><thead><tr><th>Kuitansi</th><th>Lot</th><th class="num">DP</th><th>Status</th></tr></thead><tbody>
        ${o.down_payments.map(d => `<tr><td><code>${H(d.receipt_code)}</code></td><td>#${Number(d.harvest_id)}</td><td class="num">${rp(d.amount_rp)}</td>
          <td><span class="badge ${(DP_LBL[d.status] || [""])[0]}">${H((DP_LBL[d.status] || [d.status, d.status])[1])}</span>${d.status_note ? `<br><span class="kpi-lbl">${H(d.status_note)}</span>` : ""}</td></tr>`).join("")}
        </tbody></table></div>` : "";
      w.innerHTML = (o.waiting.items.length ? `<div class="table-scroll"><table class="data-table"><thead><tr>
          <th>Lot</th><th>Pengepul</th><th class="num">Akan diterima</th><th>Status</th></tr></thead><tbody>${o.waiting.items.map(x => `
          <tr><td>#${Number(x.harvest_id)}<br><span class="kpi-lbl">${num(x.verified_kg, 0)} kg · Grade ${H(x.grade || "-")}</span></td>
              <td>${H(x.collector_name || "-")}</td><td class="num"><b>${rp(x.net_rp)}</b></td>
              <td>${x.late ? `<span class="badge badge-red">Terlambat ${x.days_waiting} hari</span><br><span class="kpi-lbl">hubungi pengepul</span>`
                           : `<span class="badge badge-amber">Menunggu ${x.days_waiting ?? 0} hari</span>`}${x.dp_rp ? `<br><span class="kpi-lbl">sudah DP ${rp(x.dp_rp)}</span>` : ""}</td></tr>`).join("")}
          </tbody></table></div>` : "") + dpHtml;
    } catch (e) { k.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  // ---- Biochar untuk sawah: saldo, perkiraan manfaat (rumus sirkular), pengajuan & riwayat
  const BR_STATUS = { diajukan: "badge-amber", diserahkan: "badge-green", dibatalkan: "badge-gray" };
  let estTimer = null;
  async function loadBiochar() {
    const box = $("biochar-sawah");
    if (!box) return;
    try {
      const [w, reqs] = await Promise.all([api("/api/v1/farmer/wallet"), api("/api/v1/farmer/biochar/redemptions")]);
      box.innerHTML = `
        <div class="kpi-row">
          <div class="kpi-tile"><div class="kpi-lbl">Saldo biochar</div><div class="kpi-val">${num(w.balance_kg, 1)} kg</div>
            <div class="kpi-lbl">hak dari sekam yang diolah</div></div>
          <div class="kpi-tile"><div class="kpi-lbl">Bisa diambil</div><div class="kpi-val">${num(w.available_kg, 1)} kg</div>
            <div class="kpi-lbl">${w.held_kg ? `${num(w.held_kg, 1)} kg sedang diajukan` : "siap diajukan"}</div></div>
        </div>
        <form id="br-form" class="sale-grid">
          <div><label class="kpi-lbl" for="br-kg">Ambil (kg)</label>
            <input id="br-kg" type="number" class="btn btn-secondary" style="width:100%;" min="1" step="10" value="${w.available_kg > 0 ? Math.min(500, Math.floor(w.available_kg)) : 500}" inputmode="numeric" required></div>
          <div><label class="kpi-lbl" for="br-ha">Luas sawah (ha)</label>
            <input id="br-ha" type="number" class="btn btn-secondary" style="width:100%;" min="0.01" step="0.05" value="0.5" inputmode="decimal" required></div>
          <div><label class="kpi-lbl" for="br-pick">Ambil di</label>
            <select id="br-pick" class="btn btn-secondary" style="width:100%;"><option value="pabrik">Gudang pabrik</option><option value="pengepul">Gudang pengepul</option></select></div>
          <div style="align-self:end;"><button type="submit" class="btn btn-primary" style="width:100%;" ${w.available_kg > 0 ? "" : "disabled"}>♻️ Ajukan pengambilan</button></div>
        </form>
        ${w.available_kg > 0 ? "" : `<p class="form-hint">Saldo masih 0 — biochar dialokasikan setelah sekam Anda diolah pabrik. Perkiraan di bawah memakai contoh 500 kg.</p>`}
        <div id="br-est" class="sale-preview" aria-live="polite"></div>
        <div id="br-list">${reqs.length ? `<div class="table-scroll"><table class="data-table"><thead><tr><th>#</th><th class="num">kg</th><th>Status</th><th></th></tr></thead><tbody>
          ${reqs.map(x => `<tr><td>${Number(x.id)}<br><span class="kpi-lbl">${H((x.created_at || "").slice(0, 10))} · ${H(x.pickup_point)}</span></td>
            <td class="num">${num(x.kg, 1)}</td><td><span class="badge ${BR_STATUS[x.status] || ""}">${H(x.status)}</span></td>
            <td>${x.status === "diajukan" ? `<button type="button" class="btn btn-secondary btn-sm" data-br-cancel="${Number(x.id)}">Batal</button>` : ""}</td></tr>`).join("")}
          </tbody></table></div>` : ""}</div>`;
      const refresh = () => { clearTimeout(estTimer); estTimer = setTimeout(showEstimate, 300); };
      $("br-kg").addEventListener("input", refresh); $("br-ha").addEventListener("input", refresh);
      showEstimate();
      $("br-form").onsubmit = (e) => {
        e.preventDefault();
        return withBusy(e.target.querySelector("[type=submit]"), async () => {
          try {
            await api("/api/v1/farmer/biochar/redeem", { body: { kg: Number($("br-kg").value), land_area_ha: Number($("br-ha").value),
                                                                pickup_point: $("br-pick").value } });
            showToast("Pengajuan terkirim. Ambil karung saat pabrik mengonfirmasi.", "♻️");
            loadBiochar();
          } catch (err) { showToast(err.message, "❌"); }
        });
      };
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
  }

  async function showEstimate() {
    const out = $("br-est"), kg = Number(($("br-kg") || {}).value), ha = Number(($("br-ha") || {}).value);
    if (!out) return;
    if (!(kg > 0 && ha > 0)) { out.innerHTML = `<span class="form-hint">Isi kg &amp; luas sawah untuk melihat perkiraan manfaat.</span>`; return; }
    try {
      const e = await api(`/api/v1/farmer/biochar/estimate?kg=${kg}&land_area_ha=${ha}`);
      out.innerHTML = `
        <div style="display:flex; justify-content:space-between; gap:8px;"><span>Perkiraan manfaat bersih (${e.residual_seasons} musim)</span>
          <strong>${rp(e.net_benefit_rp)}</strong></div>
        <div class="form-hint" style="margin-top:4px;">Dosis ${num(e.rate_t_ha, 2)} t/ha · hasil padi +${num(e.yield_gain_pct, 1)}% (±${num(e.extra_grain_t_per_season * 1000, 0)} kg gabah/musim)
          · tambahan ${rp(e.extra_revenue_rp)} · hemat urea ${rp(e.fertilizer_saving_rp)} − ongkos tebar ${rp(e.spreading_cost_rp)}</div>
        <div class="kpi-lbl">🌍 Karbon tersimpan di tanah ±${num(e.carbon_stored_tco2e, 2)} t CO₂e · ${H(e.advice)}</div>
        <details style="margin-top:4px;"><summary class="kpi-lbl">Rumus &amp; sumber</summary>
          <pre class="kpi-lbl" style="white-space:pre-wrap; margin:4px 0;">${H(e.formula)}</pre>
          <p class="kpi-lbl">${H(e.disclaimer)}<br>Sumber: ${H(e.sources)}</p></details>`;
    } catch (err) { out.innerHTML = `<span class="form-hint">⚠️ ${H(err.message)}</span>`; }
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
    const box = $("fo-mypay");
    if (!box) return;
    try {
      const rows = await api("/api/v1/farmer/payments");
      box.innerHTML = rows.length ? `<div class="table-scroll"><table class="data-table"><thead><tr>
          <th>Kuitansi</th><th>Lot</th><th class="num">Diterima</th><th>Metode</th></tr></thead><tbody>${rows.map(p => `
          <tr><td><code>${H(p.receipt_code)}</code><br><span class="kpi-lbl">${H((p.paid_at || "").slice(0, 10))}</span></td>
              <td>#${Number(p.harvest_id)}</td>
              <td class="num"><b>${rp(p.net_rp)}</b>${p.tax_rp ? `<br><span class="kpi-lbl">pajak ${rp(p.tax_rp)}</span>` : ""}</td>
              <td>${H(METHOD_LABEL[p.method] || p.method)}${p.reference ? `<br><span class="kpi-lbl">${H(p.reference)}</span>` : ""}</td></tr>`).join("")}
          </tbody></table></div>`
        : emptyState("🧾", "Belum ada pembayaran tercatat", "Setelah pengepul membayar, kuitansinya muncul di sini.");
    } catch (e) { box.innerHTML = `<div class="banner banner-error" role="alert">⚠️ ${H(e.message)}</div>`; }
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
               <button type="button" class="btn btn-secondary btn-sm" id="fo-export">⬇️ Unduh data saya (JSON)</button>
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
      showToast("Data Anda diunduh.", "⬇️");
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

  // ================================================================ sambungan ke dashboard
  window.renderFieldExtras = function (role, container) {
    if (!container) return;
    if (role === "pengepul") {
      container.insertAdjacentHTML("beforeend", PENGEPUL_HTML);
      $("fo-proxy-new").onclick = newProxyFarmer;
      loadProxyFarmers(); loadUnpaid(); loadCharges();
    } else if (role === "petani") {
      container.insertAdjacentHTML("beforeend", PETANI_HTML);
      loadPayOverview(); loadMyPayments(); loadBiochar();
    }
  };
  // Semua peran, setelah login: wajib ganti password (F6) & banner persetujuan PDP (F12)
  window.afterLoginChecks = function () {
    if (STATE.user && STATE.user.must_change_password) changePassword(true);
    setTimeout(syncConsentBanner, 600);                 // tunggu persona-content dirender
  };
  window.openPrivacy = openPrivacy;
  window.showFarmerContact = showContact;

  document.addEventListener("click", (e) => {
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
})();
