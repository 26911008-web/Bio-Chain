/* Navigasi "Lompat ke bagian" untuk dashboard persona yang panjang.
 *
 * Dashboard pabrik/admin di HP 360px bisa setinggi >30.000px; pengguna lapangan kehilangan orientasi
 * dan harus menggulir jauh untuk menemukan satu kartu. Modul ini membaca kartu tingkat atas di
 * #persona-content lalu menampilkan:
 *   - baris chip "Lompat ke:" di atas dashboard (bisa digeser horizontal), dan
 *   - tombol mengambang "↑ Bagian" setelah pengguna menggulir jauh, untuk kembali ke daftar itu.
 * Hanya tampil bila ada ≥ MIN_SECTIONS kartu bertajuk. Tidak memanggil jaringan.
 *
 * Kontrak: window.SectionJump = { refresh() }
 */
(function () {
  "use strict";

  const MIN_SECTIONS = 4;
  const MAX_LABEL = 30;
  let bar = null;
  let backBtn = null;
  let pending = 0;

  function cardTitle(card) {
    const t = card.querySelector(".card-title, h2, h3");
    if (!t) return "";
    const text = (t.textContent || "").replace(/\s+/g, " ").trim();
    return text.length > MAX_LABEL ? text.slice(0, MAX_LABEL - 1) + "…" : text;
  }

  function topLevelCards(root) {
    return [...root.querySelectorAll(".card")].filter(c =>
      !c.parentElement.closest(".card") && c.offsetParent !== null && cardTitle(c));
  }

  function scrollToEl(el) {
    const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
  }

  function render() {
    pending = 0;
    const root = document.getElementById("persona-content");
    if (!root) return;
    const cards = topLevelCards(root);
    if (cards.length < MIN_SECTIONS) {
      if (bar) bar.hidden = true;
      if (backBtn) backBtn.hidden = true;
      return;
    }
    if (!bar) {
      bar = document.createElement("nav");
      bar.className = "section-jump";
      bar.setAttribute("aria-label", "Lompat ke bagian dashboard");
      root.parentElement.insertBefore(bar, root);
    }
    bar.hidden = false;
    bar.textContent = "";
    const lbl = document.createElement("span");
    lbl.className = "section-jump-lbl";
    lbl.textContent = "Lompat ke:";
    bar.appendChild(lbl);
    cards.forEach((card, i) => {
      if (!card.id) card.id = `sj-sec-${i + 1}`;
      const b = document.createElement("button");
      b.type = "button";
      b.className = "section-jump-chip";
      b.textContent = cardTitle(card);
      b.addEventListener("click", () => {
        scrollToEl(card);
        card.setAttribute("tabindex", "-1");
        card.focus({ preventScroll: true });
      });
      bar.appendChild(b);
    });
    ensureBackButton();
  }

  function ensureBackButton() {
    if (backBtn) return;
    backBtn = document.createElement("button");
    backBtn.type = "button";
    backBtn.className = "section-jump-back";
    backBtn.hidden = true;
    backBtn.setAttribute("aria-label", "Kembali ke daftar bagian");
    backBtn.textContent = "↑ Bagian";
    backBtn.addEventListener("click", () => { if (bar) scrollToEl(bar); });
    document.body.appendChild(backBtn);
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  function onScroll() {
    if (!backBtn || !bar || bar.hidden) { if (backBtn) backBtn.hidden = true; return; }
    const personaActive = document.getElementById("tab-persona")?.classList.contains("active");
    backBtn.hidden = !personaActive || window.scrollY < window.innerHeight * 1.5;
  }

  function schedule() {
    if (pending) return;
    pending = window.setTimeout(render, 400);   // tunggu render bertahap (fetch per kartu) selesai
  }

  function init() {
    const root = document.getElementById("persona-content");
    if (!root) return;
    new MutationObserver(schedule).observe(root, { childList: true, subtree: true });
    schedule();
  }

  window.SectionJump = { refresh: schedule };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
