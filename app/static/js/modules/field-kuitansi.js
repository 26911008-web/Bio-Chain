/**
 * Module: Field Kuitansi & Digital Payments
 * Handles digital payment receipt rendering, PDP data masking,
 * and unified payment tables for farmers and collectors.
 */
(() => {
  "use strict";

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

  function renderUnifiedPaymentTable(cachedUnifiedPayments, helpers) {
    const { H, num, rp, emptyState } = helpers || {};
    const box = $("fo-mypay-unified");
    if (!box) return;
    const q = (($("fo-pay-search") || {}).value || "").toLowerCase().trim();
    const f = (($("fo-pay-filter") || {}).value || "all");

    let list = (cachedUnifiedPayments || []).filter(it => {
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

  window.FieldKuitansi = {
    formatDateTime,
    renderUnifiedPaymentTable
  };
})();
