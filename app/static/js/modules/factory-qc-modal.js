/**
 * Module: Factory QC & Dispatch Modals
 * Handles dialog modals for biochar return dispatch, weighbridge confirmation,
 * and quality inspection alerts.
 */
(() => {
  "use strict";

  function openBiocharDispatchModal(callbacks) {
    const { onCreated } = callbacks || {};
    const d = document.createElement("dialog");
    d.className = "ui-confirm";
    d.innerHTML = `<form method="dialog" style="max-width:440px;">
      <h3>🚚 Terbitkan Surat Jalan Muatan Balik Biochar</h3>
      <p class="ui-confirm-body">Muatan balik biochar mengoptimalkan utilisasi armada dan mewujudkan rantai pasok sirkular (ZONA 5B ➔ ZONA 4).</p>
      <div class="form-group"><label for="fx-bd-col">Pengepul Mitra</label>
        <select id="fx-bd-col" required>
          <option value="2">UD Sekam Berkah (#2)</option>
          <option value="3">UD Jagung Makmur (#3)</option>
          <option value="11">UD Kayu Lestari (#11)</option>
          <option value="12">UD Tebu Barokah (#12)</option>
        </select></div>
      <div class="form-group"><label for="fx-bd-drv">Supir / Driver Ditugaskan</label>
        <select id="fx-bd-drv" required>
          <option value="4">Budi Santoso - Driver (#4)</option>
          <option value="13">Joko Widodo - Driver (#13)</option>
        </select></div>
      <div class="form-group"><label for="fx-bd-plate">Nomor Plat Truk</label>
        <input id="fx-bd-plate" required value="AB 8888 XY" maxlength="20"></div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
        <div class="form-group"><label for="fx-bd-kg">Total Berat (kg)</label>
          <input id="fx-bd-kg" type="number" min="50" max="20000" step="25" value="500" required></div>
        <div class="form-group"><label for="fx-bd-bags">Jumlah Karung (sak)</label>
          <input id="fx-bd-bags" type="number" min="1" max="1000" step="1" value="20" required></div>
      </div>
      <div class="form-group"><label for="fx-bd-inst">Instruksi Muat &amp; Penurunan</label>
        <input id="fx-bd-inst" value="Antar ke sawah binaan petani kelompok tani mitra" maxlength="250"></div>
      <div class="ui-confirm-actions">
        <button value="no" class="btn btn-secondary" formnovalidate>Batal</button>
        <button value="yes" class="btn btn-primary">Terbitkan &amp; Buat QR</button>
      </div></form>`;
    document.body.appendChild(d);
    d.addEventListener("close", async () => {
      if (d.returnValue === "yes") {
        try {
          const colId = Number(d.querySelector("#fx-bd-col").value);
          const drvId = Number(d.querySelector("#fx-bd-drv").value);
          const plate = d.querySelector("#fx-bd-plate").value.trim();
          const kg = Number(d.querySelector("#fx-bd-kg").value);
          const bags = Number(d.querySelector("#fx-bd-bags").value);
          const inst = d.querySelector("#fx-bd-inst").value.trim();
          const r = await api("/api/v1/factory/dispatch-biochar", {
            method: "POST",
            body: { collector_id: colId, driver_id: drvId, vehicle_plate: plate, total_weight_kg: kg, total_bags: bags, loading_instructions: inst }
          });
          showToast(r.message, "✅");
          openModal("Surat Jalan Muatan Balik Biochar", r.qr_dispatch_token, `${r.dispatch_code} · ${num(r.total_weight_kg, 0)} kg biochar (${r.total_bags} karung)`);
          if (typeof onCreated === "function") onCreated();
        } catch (err) { showToast(err.message, "❌"); }
      }
      d.remove();
    });
    d.showModal();
  }

  window.FactoryQcModal = {
    openBiocharDispatchModal
  };
})();
