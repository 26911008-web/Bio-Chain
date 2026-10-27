/**
 * Module: Factory Notice Modal & Operational Validation Dialog
 * Provides rich, high-contrast, Field Noir dialogs for Factory Operations
 * (PPIC, Warehouse, Shop Floor Production, and QC Laboratory).
 *
 * Strict Protocol:
 * 1. Apa yang salah (Error Description)
 * 2. Detail Parameter (Measured vs Required / Limits)
 * 3. Tindakan Penyelesaian (Actionable Remediation)
 *
 * Replaces all browser standard alerts and prompts with accessible,
 * design-system-compliant modals.
 */
(() => {
  "use strict";

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));

  /**
   * Opens an interactive Factory Notice modal.
   *
   * @param {Object} opts
   * @param {string} opts.title
   * @param {string} opts.whatWentWrong
   * @param {string|Object} opts.parameterDetails
   * @param {string} opts.resolutionAction
   * @param {'error'|'warning'|'info'} [opts.type='error']
   * @param {string} [opts.confirmText='Tutup / Mengerti']
   * @param {Function} [opts.onConfirm]
   */
  function factoryNoticeModal(opts) {
    const {
      title = "Peringatan Operasional Pabrik",
      whatWentWrong = "Terjadi ketidaksesuaian parameter operasional manufaktur.",
      parameterDetails = "",
      resolutionAction = "Periksa kembali data input sebelum memproses.",
      type = "error",
      confirmText = "Tutup / Mengerti",
      onConfirm
    } = opts || {};

    const badgeLabel = type === "error"
      ? "⛔ Validasi Gagal"
      : (type === "warning" ? "⚠️ Peringatan Operasional" : "ℹ️ Informasi Kontrol");
    const badgeClass = type === "error"
      ? "badge-error"
      : (type === "warning" ? "badge-warning" : "badge-info");

    let detailsHtml = "";
    if (typeof parameterDetails === "object" && parameterDetails !== null) {
      detailsHtml = `<table>${Object.entries(parameterDetails).map(([k, v]) => `
        <tr><td><b>${esc(k)}:</b></td><td><code>${esc(v)}</code></td></tr>
      `).join("")}</table>`;
    } else {
      detailsHtml = `<div>${esc(parameterDetails)}</div>`;
    }

    const d = document.createElement("dialog");
    d.className = "ui-confirm factory-notice-dialog";
    d.setAttribute("data-notice-type", type);
    d.setAttribute("role", "alertdialog");
    d.setAttribute("aria-modal", "true");

    d.innerHTML = `
      <div class="factory-notice-header">
        <div class="factory-notice-badge ${badgeClass}">
          <span>${badgeLabel}</span>
        </div>
        <button type="button" class="factory-notice-close" aria-label="Tutup dialog">✕</button>
      </div>

      <div class="factory-notice-body">
        <h3 class="factory-notice-title">${esc(title)}</h3>

        <div class="factory-notice-box box-wrong">
          <div class="factory-notice-box-label">❌ Apa Yang Salah:</div>
          <div>${esc(whatWentWrong)}</div>
        </div>

        ${parameterDetails ? `
        <div class="factory-notice-box box-details">
          <div class="factory-notice-box-label">📊 Detail Parameter:</div>
          <div>${detailsHtml}</div>
        </div>` : ""}

        <div class="factory-notice-box box-action">
          <div class="factory-notice-box-label">🛠️ Tindakan Penyelesaian:</div>
          <div>${esc(resolutionAction)}</div>
        </div>
      </div>

      <div class="factory-notice-footer">
        <button type="button" class="btn btn-primary btn-notice-confirm">${esc(confirmText)}</button>
      </div>
    `;

    document.body.appendChild(d);

    const closeDialog = () => {
      d.close();
      d.remove();
      if (typeof onConfirm === "function") {
        try { onConfirm(); } catch (err) { console.error("Notice modal onConfirm error:", err); }
      }
    };

    const closeBtn = d.querySelector(".factory-notice-close");
    const confirmBtn = d.querySelector(".btn-notice-confirm");

    if (closeBtn) closeBtn.onclick = closeDialog;
    if (confirmBtn) {
      confirmBtn.onclick = closeDialog;
      setTimeout(() => confirmBtn.focus(), 50);
    }

    d.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeDialog();
    });

    d.showModal();
    return d;
  }

  /**
   * Opens an interactive input modal (Zero window.prompt() compliance).
   *
   * @param {Object} opts
   * @param {string} opts.title
   * @param {string} opts.promptText
   * @param {string} [opts.defaultValue='']
   * @param {string} [opts.placeholder='']
   * @param {number} [opts.minLength=1]
   * @param {string} [opts.inputType='text']
   * @param {Function} opts.onConfirm - Called with string value
   * @param {Function} [opts.onCancel]
   */
  function factoryInputModal(opts) {
    const {
      title = "Input Operasional Pabrik",
      promptText = "Masukkan data:",
      defaultValue = "",
      placeholder = "",
      minLength = 1,
      inputType = "text",
      onConfirm,
      onCancel
    } = opts || {};

    const d = document.createElement("dialog");
    d.className = "ui-confirm factory-notice-dialog";
    d.setAttribute("data-notice-type", "info");
    d.setAttribute("role", "dialog");
    d.setAttribute("aria-modal", "true");

    d.innerHTML = `
      <form method="dialog">
        <div class="factory-notice-header">
          <div class="factory-notice-badge badge-info">
            <span>📝 Input Verifikasi</span>
          </div>
          <button type="button" class="factory-notice-close" aria-label="Batal">✕</button>
        </div>

        <div class="factory-notice-body">
          <h3 class="factory-notice-title">${esc(title)}</h3>
          <p class="ui-confirm-body" style="margin:0; font-size:13px; color:var(--ink-muted);">${esc(promptText)}</p>
          <div class="form-group" style="margin-top:8px;">
            <input id="fx-modal-inp" type="${esc(inputType)}" class="btn btn-secondary" style="width:100%; text-align:left; font-size:13px; padding:10px 12px;"
                   value="${esc(defaultValue)}" placeholder="${esc(placeholder)}" required>
            <p id="fx-modal-err" class="form-error" role="alert" style="color:var(--danger, #f87171); font-size:11.5px; margin-top:6px; display:none;"></p>
          </div>
        </div>

        <div class="factory-notice-footer">
          <button type="button" value="no" class="btn btn-secondary btn-cancel-input">Batal</button>
          <button type="submit" value="yes" class="btn btn-primary btn-submit-input">Konfirmasi</button>
        </div>
      </form>
    `;

    document.body.appendChild(d);
    const inp = d.querySelector("#fx-modal-inp");
    const err = d.querySelector("#fx-modal-err");
    const closeBtn = d.querySelector(".factory-notice-close");
    const cancelBtn = d.querySelector(".btn-cancel-input");
    const form = d.querySelector("form");

    const cleanup = () => {
      d.close();
      d.remove();
    };

    closeBtn.onclick = () => { cleanup(); if (onCancel) onCancel(); };
    cancelBtn.onclick = () => { cleanup(); if (onCancel) onCancel(); };

    form.onsubmit = (e) => {
      e.preventDefault();
      const val = inp.value.trim();
      if (val.length < minLength) {
        err.style.display = "block";
        err.textContent = `Wajib diisi minimal ${minLength} karakter.`;
        inp.focus();
        return;
      }
      cleanup();
      if (typeof onConfirm === "function") {
        onConfirm(val);
      }
    };

    setTimeout(() => { inp.focus(); inp.select(); }, 50);
    d.showModal();
    return d;
  }

  // Expose globally
  window.factoryNoticeModal = factoryNoticeModal;
  window.factoryInputModal = factoryInputModal;
  window.FactoryNoticeModal = {
    show: factoryNoticeModal,
    prompt: factoryInputModal
  };
})();
