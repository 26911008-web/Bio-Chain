/**
 * Bio-Chain Excel-Like Table Filter Engine
 * Menghadirkan fitur auto-filter spreadsheet Excel lengkap pada semua kolom di semua tabel web app:
 * 1. Filter dropdown popover per-kolom (Sort A-Z / Z-A, Cari teks, Checklist nilai unik seperti Excel).
 * 2. Baris filter cepat (Quick Search Input per kolom) yang dapat diaktifkan.
 * 3. Indikator filter aktif pada header (berwarna hijau saat aktif).
 * 4. Status bar informatif (jumlah baris lolos filter vs total baris, tombol Reset Semua Filter).
 * 5. Kompatibel 100% dengan DOM dinamis & aman dari perubahan data / Playwright tests.
 */

(function () {
  "use strict";

  // Simpan state filter aktif per tabel
  // Map<HTMLTableElement, { [colIndex]: Set<string> | null }>
  const tableFiltersMap = new WeakMap();

  // Helper untuk membersihkan teks cell
  function getCellCleanText(cell) {
    if (!cell) return "";
    // Jangan sertakan teks tombol popover filter
    const clone = cell.cloneNode(true);
    clone.querySelectorAll(".excel-th-btn, .th-sort-ind, .excel-quick-filter-row").forEach(el => el.remove());
    return clone.textContent.trim().replace(/\s+/g, " ");
  }

  // Parse angka untuk sorting numerik
  function parseCellValue(text) {
    const clean = String(text || "").replace(/[^\d.,\-]/g, "").replace(/\./g, "").replace(",", ".");
    const num = parseFloat(clean);
    return isNaN(num) ? text.toLowerCase() : num;
  }

  // Tutup semua popover yang terbuka
  function closeAllExcelPopovers() {
    document.querySelectorAll(".excel-filter-popover").forEach(p => p.remove());
    document.querySelectorAll(".excel-th-btn.open").forEach(b => b.classList.remove("open"));
  }

  // Pasang listener global untuk menutup popover saat klik di luar atau tekan Escape
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".excel-filter-popover") && !e.target.closest(".excel-th-btn")) {
      closeAllExcelPopovers();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeAllExcelPopovers();
    }
  });

  // Terapkan filter pada tabel
  function applyFiltersToTable(table) {
    const filters = tableFiltersMap.get(table) || {};
    const tbody = table.tBodies[0];
    if (!tbody) return;

    const rows = [...tbody.rows].filter(r => r.cells.length > 1 && !r.classList.contains("empty-state-row"));
    let visibleCount = 0;

    rows.forEach(row => {
      let isVisible = true;
      for (const [colIdxStr, allowedSet] of Object.entries(filters)) {
        if (!allowedSet) continue;
        const colIdx = parseInt(colIdxStr, 10);
        const cell = row.cells[colIdx];
        const val = getCellCleanText(cell);
        if (!allowedSet.has(val)) {
          isVisible = false;
          break;
        }
      }
      row.style.display = isVisible ? "" : "none";
      if (isVisible) visibleCount++;
    });

    // Update status bar
    updateStatusBar(table, visibleCount, rows.length);

    // Update highlight tombol header
    updateHeaderFilterIndicators(table, filters);
  }

  // Update indikator header (hijau jika kolom sedang difilter)
  function updateHeaderFilterIndicators(table, filters) {
    const thead = table.tHead;
    if (!thead || !thead.rows.length) return;
    const headerRow = thead.rows[0];

    [...headerRow.cells].forEach((th, idx) => {
      const btn = th.querySelector(".excel-th-btn");
      if (!btn) return;
      const isFiltered = !!filters[idx];
      if (isFiltered) {
        btn.classList.add("is-filtered");
        btn.setAttribute("title", "Filter aktif pada kolom ini (Klik untuk ubah/reset)");
      } else {
        btn.classList.remove("is-filtered");
        btn.setAttribute("title", "Filter & Urutkan kolom");
      }
    });
  }

  // Update status bar di atas tabel
  function updateStatusBar(table, visibleCount, totalCount) {
    let bar = table.parentElement ? table.parentElement.querySelector(`.excel-filter-status-bar[data-for="${table.id || 'tbl'}"]`) : null;
    const filters = tableFiltersMap.get(table) || {};
    const activeFilterCount = Object.values(filters).filter(Boolean).length;

    if (!bar) {
      bar = document.createElement("div");
      bar.className = "excel-filter-status-bar";
      bar.dataset.for = table.id || "tbl";
      table.parentNode.insertBefore(bar, table);
    }

    if (activeFilterCount === 0) {
      bar.style.display = "none";
      return;
    }

    bar.style.display = "flex";
    bar.innerHTML = `
      <div style="display:flex; align-items:center; gap:8px;">
        <span style="font-size:14px;">📊</span>
        <span>Filter Excel Aktif (<b>${activeFilterCount}</b> kolom): Menampilkan <b>${visibleCount}</b> dari <b>${totalCount}</b> baris</span>
      </div>
      <button type="button" class="btn btn-secondary btn-sm excel-reset-all-btn" style="padding:2px 8px; font-size:11px;">
        ↺ Reset Semua Filter
      </button>
    `;

    bar.querySelector(".excel-reset-all-btn").onclick = () => {
      tableFiltersMap.set(table, {});
      applyFiltersToTable(table);
      // Bersihkan juga quick filter row jika ada
      table.querySelectorAll(".excel-quick-input").forEach(inp => inp.value = "");
    };
  }

  // Urutkan baris tabel
  function sortTableByColumn(table, colIdx, direction) {
    const tbody = table.tBodies[0];
    if (!tbody) return;
    const rows = [...tbody.rows].filter(r => r.cells.length > 1);
    if (rows.length < 2) return;

    rows.sort((a, b) => {
      const valA = parseCellValue(getCellCleanText(a.cells[colIdx]));
      const valB = parseCellValue(getCellCleanText(b.cells[colIdx]));

      if (typeof valA === "number" && typeof valB === "number") {
        return direction === "asc" ? valA - valB : valB - valA;
      }
      return direction === "asc"
        ? String(valA).localeCompare(String(valB), "id")
        : String(valB).localeCompare(String(valA), "id");
    });

    rows.forEach(r => tbody.appendChild(r));
    applyFiltersToTable(table);
  }

  // Tampilkan Popover Filter Excel untuk Kolom
  function openExcelFilterPopover(table, colIdx, th, btn) {
    closeAllExcelPopovers();
    btn.classList.add("open");

    const tbody = table.tBodies[0];
    const rows = tbody ? [...tbody.rows].filter(r => r.cells.length > 1) : [];
    
    // Ambil nilai unik dan hitung frekuensinya
    const valueCounts = new Map();
    rows.forEach(r => {
      const text = getCellCleanText(r.cells[colIdx]) || "(Kosong)";
      valueCounts.set(text, (valueCounts.get(text) || 0) + 1);
    });

    const uniqueValues = [...valueCounts.keys()].sort((a, b) => a.localeCompare(b, "id"));

    // Cek filter yang saat ini aktif
    const currentFilters = tableFiltersMap.get(table) || {};
    const activeAllowed = currentFilters[colIdx] || null;

    const colTitle = th.cloneNode(true);
    colTitle.querySelectorAll(".excel-th-btn, .th-sort-ind").forEach(el => el.remove());
    const titleText = colTitle.textContent.trim() || `Kolom #${colIdx + 1}`;

    const popover = document.createElement("div");
    popover.className = "excel-filter-popover";

    // Hitung posisi popover relatif terhadap viewport / button
    const rect = btn.getBoundingClientRect();
    popover.style.top = `${rect.bottom + window.scrollY + 4}px`;
    let leftPos = rect.left + window.scrollX - 20;
    if (leftPos + 270 > window.innerWidth) {
      leftPos = Math.max(10, window.innerWidth - 280);
    }
    popover.style.left = `${leftPos}px`;

    popover.innerHTML = `
      <div class="excel-pop-head">
        <div class="excel-pop-title" title="${titleText}">📊 Filter: <b>${titleText}</b></div>
        <button type="button" class="excel-pop-close" aria-label="Tutup">✕</button>
      </div>

      <!-- Quick Sorting -->
      <div class="excel-pop-section">
        <div class="excel-sort-row" data-sort="asc">
          <span>🔼</span> <span>Urutkan A ➔ Z (Terkecil ke Terbesar)</span>
        </div>
        <div class="excel-sort-row" data-sort="desc">
          <span>🔽</span> <span>Urutkan Z ➔ A (Terbesar ke Terkecil)</span>
        </div>
      </div>

      <!-- Search Input -->
      <div class="excel-pop-section" style="padding-top:4px;">
        <input type="text" class="excel-search-box" placeholder="🔍 Cari nilai dalam kolom..." />
      </div>

      <!-- Value Checklist Container -->
      <div class="excel-checklist-container">
        <label class="excel-check-item excel-select-all">
          <input type="checkbox" id="excel-chk-all" ${!activeAllowed || activeAllowed.size === uniqueValues.length ? 'checked' : ''} />
          <span><b>(Pilih Semua)</b></span>
        </label>
        <div class="excel-checklist-items">
          ${uniqueValues.map((v, i) => {
            const isChecked = !activeAllowed || activeAllowed.has(v);
            return `
              <label class="excel-check-item" data-val="${encodeURIComponent(v)}">
                <input type="checkbox" class="excel-val-chk" value="${encodeURIComponent(v)}" ${isChecked ? 'checked' : ''} />
                <span class="excel-val-text" title="${v}">${v}</span>
                <span class="excel-val-count">${valueCounts.get(v)}</span>
              </label>
            `;
          }).join("")}
        </div>
      </div>

      <!-- Action Footer -->
      <div class="excel-pop-footer">
        <button type="button" class="btn btn-secondary btn-sm excel-pop-clear">↺ Reset Kolom</button>
        <button type="button" class="btn btn-primary btn-sm excel-pop-apply">✓ Terapkan</button>
      </div>
    `;

    document.body.appendChild(popover);

    // Event Handlers Popover
    popover.querySelector(".excel-pop-close").onclick = closeAllExcelPopovers;

    // Sorting
    popover.querySelectorAll(".excel-sort-row").forEach(row => {
      row.onclick = () => {
        const dir = row.dataset.sort;
        sortTableByColumn(table, colIdx, dir);
        closeAllExcelPopovers();
      };
    });

    // Real-time Search Checklist
    const searchBox = popover.querySelector(".excel-search-box");
    const itemLabels = popover.querySelectorAll(".excel-checklist-items .excel-check-item");
    searchBox.oninput = () => {
      const q = searchBox.value.toLowerCase().trim();
      itemLabels.forEach(lbl => {
        const txt = lbl.querySelector(".excel-val-text").textContent.toLowerCase();
        lbl.style.display = txt.includes(q) ? "" : "none";
      });
    };

    // Select All Toggle
    const chkAll = popover.querySelector("#excel-chk-all");
    const valCheckboxes = popover.querySelectorAll(".excel-val-chk");
    chkAll.onchange = () => {
      valCheckboxes.forEach(cb => {
        if (cb.closest(".excel-check-item").style.display !== "none") {
          cb.checked = chkAll.checked;
        }
      });
    };

    // Sinkronisasi status Select All saat individu diubah
    valCheckboxes.forEach(cb => {
      cb.onchange = () => {
        const allChecked = [...valCheckboxes].every(c => c.checked);
        chkAll.checked = allChecked;
      };
    });

    // Reset Filter Kolom
    popover.querySelector(".excel-pop-clear").onclick = () => {
      const current = tableFiltersMap.get(table) || {};
      delete current[colIdx];
      tableFiltersMap.set(table, current);
      applyFiltersToTable(table);
      closeAllExcelPopovers();
    };

    // Terapkan Filter
    popover.querySelector(".excel-pop-apply").onclick = () => {
      const selected = new Set();
      valCheckboxes.forEach(cb => {
        if (cb.checked) {
          selected.add(decodeURIComponent(cb.value));
        }
      });

      const current = tableFiltersMap.get(table) || {};
      if (selected.size === uniqueValues.length) {
        // Jika semua dipilih, tidak perlu filter
        delete current[colIdx];
      } else {
        current[colIdx] = selected;
      }
      tableFiltersMap.set(table, current);
      applyFiltersToTable(table);
      closeAllExcelPopovers();
    };

    // Autofocus pada search box
    setTimeout(() => searchBox.focus(), 50);
  }

  // Enhanced baris filter cepat (Quick Input Row)
  function toggleQuickFilterRow(table) {
    const thead = table.tHead;
    if (!thead) return;

    let qRow = thead.querySelector(".excel-quick-filter-row");
    if (qRow) {
      qRow.remove();
      return;
    }

    const headerRow = thead.rows[0];
    qRow = document.createElement("tr");
    qRow.className = "excel-quick-filter-row";

    [...headerRow.cells].forEach((th, idx) => {
      const thCell = document.createElement("th");
      thCell.style.padding = "4px 6px";
      thCell.style.background = "var(--surface-2, #1e293b)";

      const isAction = /^(aksi|action|pilih|qr|tutup|detail)$/i.test(th.textContent.trim());
      if (isAction) {
        thCell.innerHTML = `<span style="font-size:10px; color:var(--ink-muted);">-</span>`;
      } else {
        const inp = document.createElement("input");
        inp.type = "text";
        inp.className = "excel-quick-input";
        inp.placeholder = "🔍 filter...";
        inp.oninput = () => {
          const val = inp.value.toLowerCase().trim();
          const tbody = table.tBodies[0];
          if (!tbody) return;
          const rows = [...tbody.rows].filter(r => r.cells.length > 1);
          
          if (!val) {
            const current = tableFiltersMap.get(table) || {};
            delete current[idx];
            tableFiltersMap.set(table, current);
          } else {
            // Dapatkan semua nilai cell yang match
            const matched = new Set();
            rows.forEach(r => {
              const txt = getCellCleanText(r.cells[idx]);
              if (txt.toLowerCase().includes(val)) {
                matched.add(txt);
              }
            });
            const current = tableFiltersMap.get(table) || {};
            current[idx] = matched;
            tableFiltersMap.set(table, current);
          }
          applyFiltersToTable(table);
        };
        thCell.appendChild(inp);
      }
      qRow.appendChild(thCell);
    });

    thead.appendChild(qRow);
  }

  // Inisialisasi Fitur Excel Filter pada Sebuah Tabel
  function enhanceTableWithExcelFilter(table) {
    if (!table || table.dataset.excelFilterActive || !table.tHead || !table.tHead.rows.length) return;
    table.dataset.excelFilterActive = "1";

    const thead = table.tHead;
    const headerRow = thead.rows[0];

    [...headerRow.cells].forEach((th, colIdx) => {
      if (th.querySelector(".excel-th-btn")) return;

      // Wrapper flex jika belum ada
      let wrap = th.querySelector(".th-flex-wrap");
      if (!wrap) {
        wrap = document.createElement("div");
        wrap.className = "th-flex-wrap";
        wrap.style.cssText = "display:flex; align-items:center; justify-content:space-between; gap:4px; width:100%;";
        while (th.firstChild) {
          wrap.appendChild(th.firstChild);
        }
        th.appendChild(wrap);
      }

      // Tombol trigger Excel Filter
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "excel-th-btn";
      btn.innerHTML = `<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" style="pointer-events:none; display:block;"><path d="M10 18h4v-2h-4v2zM3 6v2h18V6H3zm3 7h12v-2H6v2z"/></svg>`;
      btn.title = "Filter & Urutkan kolom ini (Mode Excel)";
      btn.setAttribute("aria-label", `Filter Excel untuk kolom ${colIdx + 1}`);

      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        openExcelFilterPopover(table, colIdx, th, btn);
      });

      wrap.appendChild(btn);
    });
  }

  // Scanner otomatis untuk tabel baru di DOM
  function scanAndEnhanceTables(root = document) {
    root.querySelectorAll("table.data-table, table.table").forEach(enhanceTableWithExcelFilter);
  }

  // Global Observer
  let scanPending = false;
  const observer = new MutationObserver(() => {
    if (scanPending) return;
    scanPending = true;
    requestAnimationFrame(() => {
      scanPending = false;
      scanAndEnhanceTables();
    });
  });

  if (document.body) {
    observer.observe(document.body, { childList: true, subtree: true });
    scanAndEnhanceTables();
  } else {
    document.addEventListener("DOMContentLoaded", () => {
      observer.observe(document.body, { childList: true, subtree: true });
      scanAndEnhanceTables();
    });
  }

  // Expose API ke Window
  window.enableExcelTableFilters = scanAndEnhanceTables;
  window.toggleQuickFilterRow = toggleQuickFilterRow;
})();
