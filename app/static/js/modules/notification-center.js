/**
 * Module: Notification Center & Status Grouping
 * Handles role-based notifications, real-time unread badges,
 * and detail modals for biomass updates and dispatches.
 */
(() => {
  "use strict";

// ==============================================================
// NOTIFICATION CENTER LOGIC & STATUS GROUPING
// ==============================================================
let currentNotifFilter = "";
let cachedNotifData = null;

async function openNotificationCenterModal() {
  const modal = $("notification-center-modal");
  if (!modal) return;
  modal.classList.add("open");

  const role = (STATE.user && STATE.user.role) || "petani";
  const personaBadge = $("notif-modal-persona-badge");
  if (personaBadge) {
    const roleIcons = {
      petani: "🌾 Petani",
      pengepul: "📦 Pengepul",
      driver: "🚛 Driver",
      pabrik: "🏭 Pabrik",
      auditor: "🔍 Auditor",
      admin: "⚙️ Admin",
    };
    personaBadge.innerText = roleIcons[role] || role.toUpperCase();
  }

  await loadNotifications(currentNotifFilter);
}
window.openNotificationCenterModal = openNotificationCenterModal;

function closeNotificationCenterModal() {
  const modal = $("notification-center-modal");
  if (modal) modal.classList.remove("open");
}
window.closeNotificationCenterModal = closeNotificationCenterModal;

async function filterNotificationGroup(groupKey) {
  currentNotifFilter = groupKey || "";
  document.querySelectorAll(".notif-filter-btn").forEach(btn => {
    btn.classList.toggle("active", (btn.getAttribute("data-group") || "") === currentNotifFilter);
  });
  await loadNotifications(currentNotifFilter);
}
window.filterNotificationGroup = filterNotificationGroup;

async function refreshNotifications() {
  await loadNotifications(currentNotifFilter);
  showToast("Daftar notifikasi berhasil disegarkan.", "🔄");
}
window.refreshNotifications = refreshNotifications;

async function loadNotifications(statusGroup = null) {
  const content = $("notif-modal-content");
  if (content) {
    content.innerHTML = `
      <div style="text-align:center; padding:40px 20px;">
        <div class="spinner" style="margin:0 auto 12px; width:32px; height:32px; border:3px solid var(--border); border-top-color:var(--primary); border-radius:50%; animation:spin 1s linear infinite;"></div>
        <div style="font-size:13px; font-weight:600; color:var(--ink);">Memuat Notifikasi Transaksi Biomassa...</div>
      </div>
    `;
  }

  try {
    const query = statusGroup ? `?status_group=${encodeURIComponent(statusGroup)}` : "";
    const data = await api(`/api/v1/notifications/${query}`);
    cachedNotifData = data;
    updateNotifBadges(data);
    renderNotificationList(data, statusGroup);
  } catch (err) {
    if (content) {
      content.innerHTML = `
        <div style="text-align:center; padding:30px; color:var(--danger);">
          <div style="font-size:32px; margin-bottom:8px;">⚠️</div>
          <div style="font-weight:700;">Gagal memuat notifikasi</div>
          <div class="muted" style="font-size:12px; margin-top:4px;">${esc(err.message || "Koneksi terputus")}</div>
          <button type="button" class="btn btn-secondary btn-sm" style="margin-top:12px;" data-onclick="refreshNotifications()">Coba Lagi</button>
        </div>
      `;
    }
  }
}
window.loadNotifications = loadNotifications;

function updateNotifBadges(data) {
  if (!data) return;
  const counts = data.counts_by_group || {};
  const unread = data.unread_count || 0;
  const total = data.total_count || 0;

  if ($("notif-cnt-all")) $("notif-cnt-all").innerText = total;
  if ($("notif-cnt-pending")) $("notif-cnt-pending").innerText = counts["PENDING_ACTION"] || 0;
  if ($("notif-cnt-progress")) $("notif-cnt-progress").innerText = counts["IN_PROGRESS"] || 0;
  if ($("notif-cnt-completed")) $("notif-cnt-completed").innerText = counts["COMPLETED"] || 0;
  if ($("notif-cnt-alert")) $("notif-cnt-alert").innerText = counts["ALERT_DISCREPANCY"] || 0;

  const modalUnread = $("notif-modal-unread-badge");
  if (modalUnread) {
    modalUnread.innerText = `${unread} Belum Dibaca`;
    modalUnread.className = unread > 0 ? "badge badge-amber" : "badge badge-green";
  }

  const headerBadge = $("header-notif-badge");
  if (headerBadge) {
    if (unread > 0) {
      headerBadge.innerText = unread > 99 ? "99+" : unread;
      headerBadge.style.display = "inline-block";
    } else {
      headerBadge.style.display = "none";
    }
  }

  const personaWidgetBadge = $("persona-unread-badge");
  if (personaWidgetBadge) {
    if (unread > 0) {
      personaWidgetBadge.innerText = `${unread} Belum Dibaca`;
      personaWidgetBadge.style.display = "inline-block";
    } else {
      personaWidgetBadge.style.display = "none";
    }
  }
}

async function updateNotificationBadge() {
  if (!STATE.token) return;
  try {
    const sum = await api("/api/v1/notifications/summary");
    updateNotifBadges(sum);
  } catch {}
}
window.updateNotificationBadge = updateNotificationBadge;

function renderNotificationCard(item) {
  const isUnread = !item.is_read;
  const statusMeta = item.status_meta || { label: "Info", icon: "ℹ️", badge: "badge-blue" };
  const timeFormatted = formatWIB(item.created_at);
  const trxCode = item.transaction_code || (item.harvest_id ? `LOT-${item.harvest_id}` : null);
  const actor = item.actor_name ? `${item.actor_name} (${item.actor_role || 'sistem'})` : null;

  return `
    <div class="notif-card group-${esc(item.status_group)} ${isUnread ? 'unread' : ''}" id="notif-card-${item.id}">
      <div class="notif-card-head">
        <div class="notif-card-title">
          <span>${statusMeta.icon || '🔔'}</span>
          <span>${esc(item.title)}</span>
          ${isUnread ? '<span class="notif-unread-dot" title="Belum dibaca"></span>' : ''}
        </div>
        <span class="notif-card-time">${esc(timeFormatted)}</span>
      </div>

      <div class="notif-card-msg">
        ${esc(item.message)}
      </div>

      <div class="notif-card-footer">
        <div class="notif-card-tags">
          <span class="badge ${statusMeta.badge || 'badge-secondary'}" style="font-size:11px;">
            ${statusMeta.icon} ${esc(statusMeta.label)}
          </span>
          ${trxCode ? `<span class="badge badge-purple" style="font-family:monospace; font-size:11px;">📄 ${esc(trxCode)}</span>` : ''}
          ${actor ? `<span class="badge badge-secondary" style="font-size:10.5px;">👤 ${esc(actor)}</span>` : ''}
        </div>

        <div class="notif-card-actions">
          ${isUnread ? `
            <button type="button" class="btn btn-secondary btn-sm" style="padding:2px 8px; font-size:11px;" data-onclick="markNotificationAsRead(${item.id})">
              ✓ Tandai Dibaca
            </button>
          ` : ''}
          ${trxCode ? `
            <button type="button" class="btn btn-primary btn-sm" style="padding:2px 8px; font-size:11px; background:linear-gradient(135deg, #059669, #0284c7); border:none;" data-onclick="openCircularTraceFromNotif('${esc(trxCode)}')">
              🔄 Lacak Sirkular
            </button>
          ` : ''}
        </div>
      </div>
    </div>
  `;
}

function openCircularTraceFromNotif(code) {
  closeNotificationCenterModal();
  openCircularTraceModal(code);
}
window.openCircularTraceFromNotif = openCircularTraceFromNotif;

function renderNotificationList(data, activeFilter = "") {
  const content = $("notif-modal-content");
  if (!content) return;

  const items = data.items || [];
  if (items.length === 0) {
    content.innerHTML = `
      <div style="text-align:center; padding:45px 20px; color:var(--ink-muted);">
        <div style="font-size:48px; margin-bottom:10px;">📭</div>
        <h4 style="margin:0 0 6px; color:var(--ink);">Belum Ada Notifikasi</h4>
        <p style="margin:0; font-size:12.5px;">Tidak ada transaksi atau perlakuan baru pada status ini.</p>
      </div>
    `;
    return;
  }

  // Jika difilter spesifik, tampilkan kartu-kartu dalam grup tersebut
  if (activeFilter && activeFilter in (data.group_meta || {})) {
    const meta = data.group_meta[activeFilter];
    const cardsHtml = items.map(renderNotificationCard).join("");
    content.innerHTML = `
      <div class="notif-group-section">
        <div class="notif-group-header">
          <h4><span>${meta.icon}</span> <span>${esc(meta.label)}</span> <span class="badge ${meta.badge}">${items.length}</span></h4>
          <span class="muted" style="font-size:11.5px;">${esc(meta.desc)}</span>
        </div>
        <div>${cardsHtml}</div>
      </div>
    `;
    return;
  }

  // Jika "Semua", tampilkan 4 grup status terorganisir
  const grouped = data.grouped_items || {};
  const metaMap = data.group_meta || {};
  const statusKeys = ["PENDING_ACTION", "IN_PROGRESS", "COMPLETED", "ALERT_DISCREPANCY"];

  let fullHtml = "";
  for (const k of statusKeys) {
    const groupList = grouped[k] || [];
    const meta = metaMap[k] || { label: k, icon: "📌", badge: "badge-secondary", desc: "" };

    fullHtml += `
      <div class="notif-group-section" id="notif-section-${k}">
        <div class="notif-group-header">
          <h4>
            <span>${meta.icon}</span>
            <span>${esc(meta.label)}</span>
            <span class="badge ${meta.badge}" style="font-size:11px;">${groupList.length}</span>
          </h4>
          <span class="muted" style="font-size:11px;">${esc(meta.desc)}</span>
        </div>
        <div>
          ${groupList.length > 0 ? groupList.map(renderNotificationCard).join("") : `<div class="muted" style="font-size:12px; padding:10px 14px; background:var(--surface-2); border-radius:8px; border:1px dashed var(--border); margin-bottom:10px;">Tidak ada notifikasi dalam status ${esc(meta.label.toLowerCase())}.</div>`}
        </div>
      </div>
    `;
  }

  content.innerHTML = fullHtml;
}

async function markNotificationAsRead(id) {
  try {
    await api(`/api/v1/notifications/${id}/read`, { method: "POST" });
    showToast("Notifikasi ditandai telah dibaca.", "✓");

    const card = $(`notif-card-${id}`);
    if (card) {
      card.classList.remove("unread");
      const dot = card.querySelector(".notif-unread-dot");
      if (dot) dot.remove();
      const readBtn = card.querySelector("button[data-onclick*='markNotificationAsRead']");
      if (readBtn) readBtn.remove();
    }

    if (cachedNotifData) {
      if (cachedNotifData.unread_count > 0) cachedNotifData.unread_count--;
      const it = (cachedNotifData.items || []).find(x => x.id === id);
      if (it) it.is_read = true;
      updateNotifBadges(cachedNotifData);
    }
  } catch (err) {
    showToast(err.message || "Gagal menandai notifikasi", "❌");
  }
}
window.markNotificationAsRead = markNotificationAsRead;

async function markAllNotificationsAsRead() {
  try {
    const res = await api("/api/v1/notifications/read-all", { method: "POST" });
    showToast(`${res.marked_read_count || 'Semua'} notifikasi ditandai dibaca.`, "✓");

    document.querySelectorAll(".notif-card.unread").forEach(c => {
      c.classList.remove("unread");
      const dot = c.querySelector(".notif-unread-dot");
      if (dot) dot.remove();
      const readBtn = c.querySelector("button[data-onclick*='markNotificationAsRead']");
      if (readBtn) readBtn.remove();
    });

    if (cachedNotifData) {
      cachedNotifData.unread_count = 0;
      (cachedNotifData.items || []).forEach(it => it.is_read = true);
      updateNotifBadges(cachedNotifData);
    }
  } catch (err) {
    showToast(err.message || "Gagal menandai semua notifikasi", "❌");
  }
}
window.markAllNotificationsAsRead = markAllNotificationsAsRead;

function renderPersonaNotifWidgetHtml(role) {
  return `
    <div class="card notif-persona-widget" style="margin-top:14px; margin-bottom:14px; padding:12px 16px; background:linear-gradient(180deg, var(--surface-1), var(--surface-2)); border:1px solid var(--border); border-radius:12px;">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="font-size:1.2rem;">🔔</span>
          <div>
            <h4 style="margin:0; font-size:0.95rem; font-weight:700;">Aktivitas &amp; Notifikasi Transaksi Biomassa</h4>
            <span class="muted" style="font-size:0.75rem;">Status terkini penawaran, logistik, QC timbangan, dan pembayaran persona ${esc(role)}</span>
          </div>
        </div>
        <div style="display:flex; gap:8px; align-items:center;">
          <span class="badge badge-amber" id="persona-unread-badge" style="display:none;">0 Belum Dibaca</span>
          <button type="button" class="btn btn-primary btn-sm" data-onclick="openNotificationCenterModal()" style="font-size:11.5px; padding:4px 12px; font-weight:700; background:linear-gradient(135deg, #059669, #0284c7); border:none;">
            Buka Pusat Notifikasi Lengkap (${role.toUpperCase()}) ➔
          </button>
        </div>
      </div>
      <div id="persona-notif-cards-container" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:10px; margin-top:12px;">
        <!-- Top status notification cards injected dynamically -->
      </div>
    </div>
  `;
}
window.renderPersonaNotifWidgetHtml = renderPersonaNotifWidgetHtml;

async function loadPersonaNotifWidget() {
  const container = $("persona-notif-cards-container");
  if (!container) return;

  try {
    const data = await api("/api/v1/notifications/?limit=8");
    const items = data.items || [];
    if (items.length === 0) {
      container.innerHTML = `<div class="muted" style="font-size:12px; grid-column:1/-1; padding:8px;">Belum ada aktivitas transaksi baru untuk persona ini.</div>`;
      return;
    }

    // Tampilkan maksimal 4 kartu teratas yang mewakili status berbeda
    container.innerHTML = items.slice(0, 4).map(it => {
      const meta = it.status_meta || { label: "Info", icon: "ℹ️", badge: "badge-blue" };
      return `
        <div class="notif-card group-${esc(it.status_group)} ${!it.is_read ? 'unread' : ''}" style="margin-bottom:0; padding:10px 12px; cursor:pointer;" data-onclick="openNotificationCenterModal()">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:6px;">
            <div style="font-weight:700; font-size:12.5px; display:flex; align-items:center; gap:5px;">
              <span>${meta.icon}</span>
              <span>${esc(it.title)}</span>
            </div>
            ${!it.is_read ? '<span class="notif-unread-dot"></span>' : ''}
          </div>
          <p style="margin:4px 0 6px; font-size:11.5px; line-height:1.4; color:var(--ink); display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">
            ${esc(it.message)}
          </p>
          <div style="display:flex; justify-content:space-between; align-items:center; font-size:10px;">
            <span class="badge ${meta.badge}" style="font-size:9.5px; padding:1px 6px;">${esc(meta.label)}</span>
            <span class="muted">${esc(it.transaction_code || '')}</span>
          </div>
        </div>
      `;
    }).join("");
  } catch {}
}
window.loadPersonaNotifWidget = loadPersonaNotifWidget;


function openDetailModal(title, htmlContent) {
  if ($("detail-modal-title")) $("detail-modal-title").innerText = title;
  if ($("detail-modal-body")) $("detail-modal-body").innerHTML = htmlContent;
  if ($("detail-modal")) $("detail-modal").classList.add("open");
}

function closeDetailModal() {
  if ($("detail-modal")) $("detail-modal").classList.remove("open");
}

window.openDetailModal = openDetailModal;
window.closeDetailModal = closeDetailModal;

window.viewPhotoModal = function(url, title) {
  openDetailModal(title || "Foto Muatan Biomassa", `
    <div style="text-align:center; padding:10px;">
      <img src="${esc(url)}" style="max-height:420px; max-width:100%; border-radius:10px; border:1px solid var(--border); box-shadow:var(--shadow-md);" alt="${esc(title || 'Foto')}">
    </div>
  `);
};

window.viewOfferDetailModal = function(id, tab) {
  const items = tab === "langsung" ? ((cachedOffersData && cachedOffersData.langsung_diambil) || []) : ((cachedOffersData && cachedOffersData.lelang) || []);
  const it = items.find(x => (x.listing_id == id || x.harvest_id == id));
  if (!it) {
    showToast("Data penawaran tidak ditemukan.", "⚠️");
    return;
  }
  const biocharReq = it.biochar_request;
  const html = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; padding-bottom:10px; border-bottom:1px solid var(--border);">
      <div>
        <span class="kpi-lbl">No. Unik WR / QR Code:</span>
        <div style="font-family:monospace; font-size:1.15rem; font-weight:800; color:var(--primary); letter-spacing:0.5px;">${esc(it.wr_code || (it.harvest_id ? 'WR-HV-' + it.harvest_id : 'WR-LST-' + it.listing_id))}</div>
        <small class="muted">Referensi Sistem: #${it.listing_id || it.harvest_id}</small>
      </div>
      <div style="text-align:right;">
        <span class="badge ${it.is_active ? 'badge-green' : 'badge-gray'}" style="font-size:12px; padding:4px 8px;">
          ${it.is_active ? '🟢 Sedang Aktif' : '⚪ Non-Aktif'}
        </span>
        <div style="font-size:11px; color:var(--ink-muted); margin-top:3px;">${esc(it.status_label || it.status)}</div>
      </div>
    </div>

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:12px;">
      <div style="background:var(--surface-2); padding:10px 12px; border-radius:8px; border:1px solid var(--border);">
        <span class="kpi-lbl" style="font-size:11px;">🌾 Identitas Petani:</span>
        <div style="font-weight:700; font-size:1.05rem; margin-top:2px;">${esc(it.nama_petani)}</div>
        <div style="font-size:12px; color:var(--ink-muted); margin-top:3px;">📱 ${esc(it.farmer_phone || 'Nomor HP tidak tercantum')}</div>
        <div style="font-size:12px; color:var(--ink-muted);">📍 Domisili / Wilayah: Kec. ${esc(it.kecamatan || '-')}</div>
      </div>
      <div style="background:var(--surface-2); padding:10px 12px; border-radius:8px; border:1px solid var(--border);">
        <span class="kpi-lbl" style="font-size:11px;">🏭 Titik Pasok Penggilingan:</span>
        <div style="font-weight:700; font-size:1.05rem; margin-top:2px;">${esc(it.titik_pasok || 'Lahan Pertanian Petani')}</div>
        <div style="font-size:12px; color:var(--ink-muted); margin-top:3px;">⏰ Waktu Lapor: ${esc(it.reported_at ? new Date(it.reported_at).toLocaleString('id-ID') : '-')}</div>
      </div>
    </div>

    <div style="background:var(--surface-1); border:1px solid var(--border); border-radius:8px; padding:12px; margin-bottom:12px;">
      <div style="font-weight:700; margin-bottom:8px; color:var(--primary); font-size:13.5px;">📦 Rincian Pasokan &amp; Spesifikasi Mutu:</div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:12.5px; line-height:1.5;">
        <div><b>Komoditas Biomassa:</b><br><span class="badge badge-purple">${esc(it.jenis_biomassa)} (${esc(it.commodity_code)})</span></div>
        <div><b>Jumlah Tonase:</b><br><b>${num(it.qty_kg, 0)} kg</b> ${it.farmer_claimed_qty ? `<small class="muted">(Klaim: ${num(it.farmer_claimed_qty, 0)} kg)</small>` : ''}</div>
        <div><b>Taksiran Kadar Air:</b><br>${it.moisture_est != null ? `<b>${num(it.moisture_est, 1)}%</b>` : 'Standar Referensi'}</div>
        <div><b>Taksiran Grade Mutu:</b><br>${it.grade_est ? `<b>Grade ${esc(it.grade_est)}</b>` : 'Grade Standar (A)'}</div>
        <div><b>Skema Penyerahan:</b><br><span class="badge ${it.pilihan_kirim && it.pilihan_kirim.includes('Dijemput') ? 'badge-blue' : 'badge-green'}">${esc(it.pilihan_kirim)}</span></div>
        <div><b>Harga Acuan / Batas:</b><br><b style="color:var(--primary); font-size:13px;">${rp(it.harga_per_kg)} / kg</b> <small class="muted">(Est: ${rp((Number(it.qty_kg) || 0) * (Number(it.harga_per_kg) || 0))})</small></div>
      </div>
    </div>

    <div style="background:var(--surface-1); border:1px solid var(--border); border-radius:8px; padding:12px; margin-bottom:12px;">
      <div style="font-weight:700; margin-bottom:6px; color:var(--primary); font-size:13.5px;">🌱 Pesanan Muatan Balik Abu Bottom Ash untuk Sawah (Sirkular):</div>
      ${biocharReq ? `
        <div style="font-size:12.5px; line-height:1.6;">
          <div>• <b>Jumlah Pesanan:</b> <span class="badge badge-green">${num(biocharReq.requested_kg, 0)} kg Abu Bottom Ash</span></div>
          <div>• <b>Luas Lahan Aplikasi:</b> ${biocharReq.land_area_ha ? `${biocharReq.land_area_ha} ha` : 'Tidak disebutkan'}</div>
          <div>• <b>Titik Penyerahan:</b> ${esc(biocharReq.delivery_point || 'Lahan Petani')}</div>
          <div style="color:var(--ink-muted); font-size:11px; margin-top:4px;">💡 Truk penjemput biomassa membawa muatan abu bottom ash ini dari gudang saat berangkat menjemput, memangkas biaya transportasi (zero empty miles). Biochar bernilai tinggi difokuskan pabrik untuk material baterai.</div>
        </div>
      ` : `<div style="font-size:12px; color:var(--ink-muted);">Petani tidak mengajukan pesanan muatan balik abu bottom ash untuk lot ini.</div>`}
    </div>

    ${it.photo_url ? `
      <div style="background:var(--surface-1); border:1px solid var(--border); border-radius:8px; padding:12px;">
        <div style="font-weight:700; margin-bottom:6px; font-size:13px;">📷 Bukti Foto Muatan (Kompresi Canvas):</div>
        <div style="text-align:center;">
          <img src="${esc(it.photo_url)}" style="max-height:220px; border-radius:8px; max-width:100%; border:1px solid var(--border);" alt="Foto Muatan">
        </div>
      </div>
    ` : ''}
  `;
  openDetailModal(`Rincian Penawaran · ${it.nama_petani}`, html);
};

window.showHarvestFarmerDetail = async function(harvestId) {
  try {
    const harvests = await api("/api/v1/farmer/harvests?limit=100");
    const h = (harvests || []).find(x => x.id == harvestId);
    if (!h) {
      showToast("Data laporan tidak ditemukan.", "⚠️");
      return;
    }
    const html = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid var(--border);">
        <div>
          <span class="kpi-lbl">No. Unik WR / QR Code Asal:</span>
          <div style="font-family:monospace; font-size:1.15rem; font-weight:800; color:var(--primary);">${esc(h.origin_qr_code || h.wr_code || h.qr_code || ('WR-HV-' + h.id))}</div>
          <small class="muted">Batch Asal: ${esc(h.origin_qr_code || h.qr_code || ('WR-HV-' + h.id))} · Ref #${h.id} ${h.listing_id ? `· Lot Lelang #${h.listing_id}` : ''}</small>
        </div>
        <div style="text-align:right;">
          <span class="badge ${h.status === 'verified' ? 'badge-blue' : (h.status === 'reported' ? 'badge-amber' : (h.status === 'collected' ? 'badge-purple' : 'badge-green'))}">
            ${h.status === 'verified' ? '🔵 Terverifikasi Pengepul' : (h.status === 'reported' ? '🟡 Menunggu Verifikasi Pengepul' : (h.status === 'collected' ? '🚚 Diangkut Pengepul' : (h.status_label || '✅ Selesai')))}
          </span>
          <div style="font-size:11px; color:var(--ink-muted); margin-top:2px;">
            ${h.pickup_date ? `📅 Jadwal Logistik: ${esc(h.pickup_date)}` : (h.status_label || esc(h.status))}
          </div>
        </div>
      </div>

      <div style="background:var(--surface-1); border:1px solid var(--border); border-radius:8px; padding:12px; margin-bottom:12px; font-size:13px; line-height:1.6;">
        <div style="font-weight:700; color:var(--primary); margin-bottom:6px;">🌾 Informasi Laporan Biomassa:</div>
        <div>• <b>Jenis Komoditas:</b> <span class="badge badge-purple">${esc((h.commodity || 'sekam_padi').replace('_', ' ').toUpperCase())}</span></div>
        ${h.listing_id ? `<div>• <b>Status Bursa Lelang:</b> <span class="badge badge-blue">WR-LST-${String(h.listing_id).padStart(4, '0')} (Lot #${h.listing_id})</span></div>` : ''}
        <div>• <b>Kuantitas Lapor:</b> <b>${num(h.quantity_kg, 0)} kg</b> ${h.verified_kg ? `(Riil Timbang Pengepul: <b>${num(h.verified_kg, 0)} kg</b>)` : ''}</div>
        <div>• <b>Mutu:</b> ${h.grade ? `Grade ${esc(h.grade)}` : (h.farmer_grade_est ? `Taksiran Grade ${esc(h.farmer_grade_est)}` : 'Standar')} · Kadar Air: ${h.farmer_moisture_est != null ? `${num(h.farmer_moisture_est, 1)}%` : 'Standar'}</div>
        <div>• <b>Skema Logistik:</b> ${h.delivery_scheme === 'antar' ? '🚜 Antar Mandiri ke Gudang (+Premi)' : '🚚 Jemput di Lokasi Petani'}</div>
        <div>• <b>Jadwal Logistik:</b> 📅 <b>${h.pickup_date || (h.verified_at ? formatWIB(h.verified_at).split(',')[0] : 'Menunggu penjadwalan routing')}</b> (${h.delivery_scheme === 'antar' ? 'Rencana Pengantaran' : 'Rencana Penjemputan'})</div>
        <div>• <b>Status Pembayaran:</b> ${h.payment_status === 'SETTLED' ? '<span class="badge badge-green">Lunas</span> (Transaksi Selesai Sepenuhnya)' : (h.payment_status === 'DP' ? '<span class="badge badge-amber">Uang Muka (DP) Diterima</span>' : '<span class="muted">Menunggu Pelunasan</span>')}</div>
        <div>• <b>Waktu Dilaporkan:</b> ${h.reported_at ? formatWIB(h.reported_at) : '-'}</div>
      </div>

      ${h.biochar_backhaul_requested ? `
        <div style="background:var(--surface-1); border:1px solid var(--border); border-radius:8px; padding:12px; margin-bottom:12px; font-size:13px;">
          <div style="font-weight:700; color:var(--primary); margin-bottom:4px;">🌱 Pesanan Muatan Balik Abu Bottom Ash:</div>
          <div>• <b>Kebutuhan Abu Bottom Ash:</b> <span class="badge badge-green">${num(h.biochar_backhaul_kg, 0)} kg</span></div>
          <div style="font-size:11px; color:var(--ink-muted); margin-top:4px;">Armada pengepul akan membawakan abu bottom ash ini saat menuju lahan Anda.</div>
        </div>
      ` : ''}

      ${h.photo_url ? `
        <div style="background:var(--surface-1); border:1px solid var(--border); border-radius:8px; padding:12px;">
          <div style="font-weight:700; margin-bottom:6px; font-size:13px;">📷 Foto Muatan Biomassa:</div>
          <div style="text-align:center;">
            <img src="${esc(h.photo_url)}" style="max-height:220px; border-radius:8px; max-width:100%; border:1px solid var(--border);" alt="Foto Biomassa">
          </div>
        </div>
      ` : ''}
    `;
    openDetailModal(`Detail Laporan Biomassa #${harvestId}`, html);
  } catch (err) {
    showToast(err.message, "❌");
  }
};


})();
