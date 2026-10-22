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
  // Simpan state filter aktif per tabel: Map<HTMLTableElement, { [colIndex]: Set<string> | null }>
  const tableFiltersMap = new WeakMap();

  // Simpan state pagination per tabel: Map<HTMLTableElement, { pageSize: string, currentPage: number }>
  const tablePaginationMap = new WeakMap();

  function ensureTableId(table) {
    if (!table.id) {
      table.id = "tbl-" + Math.random().toString(36).slice(2, 9);
    }
    return table.id;
  }

  function getTableContainer(table) {
    let container = table.closest(".table-scroll");
    if (!container) {
      const parent = table.parentElement;
      if (parent && (parent.style.overflowX === "auto" || window.getComputedStyle(parent).overflowX === "auto" || parent.classList.contains("table-scroll"))) {
        container = parent;
      }
    }
    if (!container) {
      container = table.parentElement;
    }
    if (container && !container.classList.contains("table-scroll")) {
      container.classList.add("table-scroll");
      container.style.overflowX = "auto";
      container.style.webkitOverflowScrolling = "touch";
    }
    return container;
  }

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

  // Terapkan filter kolom dan pagination pada tabel
  function applyFiltersToTable(table) {
    if (!table || (table.style && table.style.display === "none") || (table.parentElement && table.parentElement.style && table.parentElement.style.display === "none")) return;
    const filters = tableFiltersMap.get(table) || {};
    const tbody = table.tBodies[0];
    if (!tbody) return;

    const rows = [...tbody.rows].filter(r => r.cells.length > 1 && !r.classList.contains("empty-state-row"));
    const matchingRows = [];

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
      row.dataset.excelFilterMatch = isVisible ? "1" : "0";
      if (isVisible) matchingRows.push(row);
    });

    // Pagination calculations (10, 50, 100, 200, atau semua baris)
    let savedLimit = "all";
    try {
      const stored = localStorage.getItem("biochain_table_rows_limit");
      if (stored) savedLimit = stored;
    } catch (_) {}

    let pState = tablePaginationMap.get(table);
    if (!pState) {
      pState = { pageSize: savedLimit, currentPage: 1 };
      tablePaginationMap.set(table, pState);
    }

    const isAll = (pState.pageSize === "all");
    const pageSizeNum = isAll ? matchingRows.length : (parseInt(pState.pageSize, 10) || 50);
    const totalPages = Math.max(1, Math.ceil(matchingRows.length / (pageSizeNum || 1)));

    if (pState.currentPage > totalPages) pState.currentPage = totalPages;
    if (pState.currentPage < 1) pState.currentPage = 1;

    const startIdx = isAll ? 0 : (pState.currentPage - 1) * pageSizeNum;
    const endIdx = isAll ? matchingRows.length : Math.min(matchingRows.length, startIdx + pageSizeNum);

    // Update baris DOM
    rows.forEach(row => {
      if (row.dataset.excelFilterMatch === "0") {
        row.style.display = "none";
      } else {
        const mIdx = matchingRows.indexOf(row);
        row.style.display = (mIdx >= startIdx && mIdx < endIdx) ? "" : "none";
      }
    });

    // Update status bar excel filter
    updateStatusBar(table, matchingRows.length, rows.length);

    // Update highlight tombol header
    updateHeaderFilterIndicators(table, filters);

    // Update toolbar pagination & baris data
    updatePaginationToolbar(table, matchingRows.length, rows.length, startIdx, endIdx, pState.currentPage, totalPages, pState.pageSize);

    // Update synchronized top scrollbar
    updateTopScrollbar(table);
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

  // Helper update status tombol geser horizontal
  function updateScrollNavButtons(toolbar, container) {
    if (!toolbar || !container) return;
    const btnL = toolbar.querySelector(".tpt-scroll-left");
    const btnR = toolbar.querySelector(".tpt-scroll-right");
    if (!btnL || !btnR) return;

    const maxScroll = Math.max(0, container.scrollWidth - container.clientWidth);
    const curScroll = container.scrollLeft;

    if (maxScroll <= 2) {
      btnL.disabled = true;
      btnR.disabled = true;
      btnL.title = "Semua kolom pas di layar (tidak terpotong)";
      btnR.title = "Semua kolom pas di layar (tidak terpotong)";
    } else {
      btnL.disabled = (curScroll <= 2);
      btnR.disabled = (curScroll >= maxScroll - 2);
      btnL.title = (curScroll > 2) ? "Geser tabel ke kiri" : "Sudah di kolom paling kiri";
      btnR.title = (curScroll < maxScroll - 2) ? "Geser tabel ke kanan" : "Sudah di kolom paling kanan";
    }
  }

  // Update toolbar pagination dan kontrol jumlah baris (10, 20, 50, 100, semua) + navigasi geser tabel
  function updatePaginationToolbar(table, matchingCount, totalCount, startIdx, endIdx, currentPage, totalPages, pageSize) {
    const tableId = ensureTableId(table);
    const container = getTableContainer(table);
    if (!container || !container.parentNode) return;

    let toolbar = container.parentNode.querySelector(`.table-pagination-toolbar[data-for="${tableId}"]`);
    if (!toolbar) {
      toolbar = document.createElement("div");
      toolbar.className = "table-pagination-toolbar";
      toolbar.dataset.for = tableId;

      toolbar.innerHTML = `
        <div class="tpt-controls">
          <label class="tpt-label">
            <span style="font-size:13px;">📄</span>
            <span>Tampilkan:</span>
            <select class="tpt-select" aria-label="Jumlah raw data yang ditampilkan">
              <option value="10">10 baris</option>
              <option value="20">20 baris</option>
              <option value="50">50 baris</option>
              <option value="100">100 baris</option>
              <option value="all">Semua baris data</option>
            </select>
          </label>
          <span class="tpt-info"></span>
        </div>
        <div class="tpt-scroll-nav">
          <span class="tpt-scroll-lbl">↔ Geser Tabel:</span>
          <button type="button" class="btn btn-secondary btn-sm tpt-scroll-left" title="Geser tabel ke kiri" aria-label="Geser tabel ke kiri">◀ Geser Kiri</button>
          <button type="button" class="btn btn-secondary btn-sm tpt-scroll-right" title="Geser tabel ke kanan" aria-label="Geser tabel ke kanan">Geser Kanan ▶</button>
        </div>
        <div class="tpt-paging">
          <button type="button" class="btn btn-secondary btn-sm tpt-prev" aria-label="Halaman sebelumnya">◀ Prev</button>
          <span class="tpt-page-num"></span>
          <button type="button" class="btn btn-secondary btn-sm tpt-next" aria-label="Halaman berikutnya">Next ▶</button>
        </div>
      `;

      container.parentNode.insertBefore(toolbar, container);

      const sel = toolbar.querySelector(".tpt-select");
      sel.value = pageSize || "all";
      sel.onchange = () => {
        const val = sel.value;
        try { localStorage.setItem("biochain_table_rows_limit", val); } catch (_) {}
        const p = tablePaginationMap.get(table) || {};
        p.pageSize = val;
        p.currentPage = 1;
        tablePaginationMap.set(table, p);
        applyFiltersToTable(table);
      };

      const btnScrollLeft = toolbar.querySelector(".tpt-scroll-left");
      const btnScrollRight = toolbar.querySelector(".tpt-scroll-right");
      if (btnScrollLeft) {
        btnScrollLeft.onclick = (e) => {
          e.preventDefault();
          container.scrollBy({ left: -320, behavior: "smooth" });
        };
      }
      if (btnScrollRight) {
        btnScrollRight.onclick = (e) => {
          e.preventDefault();
          container.scrollBy({ left: 320, behavior: "smooth" });
        };
      }
    }

    toolbar.dataset.totalPages = String(totalPages || 1);
    toolbar.dataset.currentPage = String(currentPage || 1);

    // Dynamic onclick handlers bound without stale closure
    const btnPrev = toolbar.querySelector(".tpt-prev");
    const btnNext = toolbar.querySelector(".tpt-next");

    if (btnPrev) {
      btnPrev.onclick = (e) => {
        e.preventDefault();
        const p = tablePaginationMap.get(table) || { currentPage: 1, pageSize: "all" };
        if (p.currentPage > 1) {
          p.currentPage--;
          tablePaginationMap.set(table, p);
          applyFiltersToTable(table);
        }
      };
    }

    if (btnNext) {
      btnNext.onclick = (e) => {
        e.preventDefault();
        const p = tablePaginationMap.get(table) || { currentPage: 1, pageSize: "all" };
        const maxPages = parseInt(toolbar.dataset.totalPages, 10) || 1;
        if (p.currentPage < maxPages) {
          p.currentPage++;
          tablePaginationMap.set(table, p);
          applyFiltersToTable(table);
        }
      };
    }

    const sel = toolbar.querySelector(".tpt-select");
    if (sel && sel.value !== pageSize) sel.value = pageSize;

    const info = toolbar.querySelector(".tpt-info");
    const isFiltered = (matchingCount < totalCount);
    const filterSuffix = isFiltered ? ` (difilter dari total ${totalCount} baris)` : "";

    if (totalCount === 0) {
      info.textContent = "Tidak ada baris data";
    } else if (matchingCount === 0) {
      info.textContent = `0 data cocok${filterSuffix}`;
    } else if (pageSize === "all") {
      info.textContent = `Menampilkan semua ${matchingCount} baris data${filterSuffix}`;
    } else {
      info.textContent = `Menampilkan ${startIdx + 1}–${endIdx} dari ${matchingCount} baris data${filterSuffix}`;
    }

    const pageNum = toolbar.querySelector(".tpt-page-num");
    pageNum.textContent = (pageSize === "all") ? "Semua Baris" : `Hal ${currentPage} / ${totalPages}`;

    if (btnPrev) btnPrev.disabled = (currentPage <= 1 || pageSize === "all" || matchingCount === 0);
    if (btnNext) btnNext.disabled = (currentPage >= totalPages || pageSize === "all" || matchingCount === 0);

    updateScrollNavButtons(toolbar, container);
  }

  // Update synchronized top scrollbar ("garis penggeser di taruh atas tabel saja")
  function updateTopScrollbar(table) {
    const tableId = ensureTableId(table);
    const container = getTableContainer(table);
    if (!container || !container.parentNode) return;

    let topBar = container.parentNode.querySelector(`.table-top-scrollbar[data-for="${tableId}"]`);
    if (!topBar) {
      topBar = document.createElement("div");
      topBar.className = "table-top-scrollbar";
      topBar.dataset.for = tableId;
      topBar.setAttribute("title", "Garis penggeser horizontal tabel (geser ke kanan/kiri)");
      topBar.innerHTML = `<div class="table-top-scrollbar-inner"></div>`;

      // Sisipkan tepat sebelum container (setelah toolbar)
      container.parentNode.insertBefore(topBar, container);
    }

    const inner = topBar.querySelector(".table-top-scrollbar-inner");
    const scrollW = container.scrollWidth;
    const clientW = container.clientWidth;

    inner.style.width = `${scrollW}px`;

    // Tampilkan jika tabel melebihi lebar layar horizontal
    if (scrollW > clientW + 2) {
      topBar.style.display = "block";
      topBar.scrollLeft = container.scrollLeft;
    } else {
      topBar.style.display = "none";
    }

    const toolbar = container.parentNode.querySelector(`.table-pagination-toolbar[data-for="${tableId}"]`);
    if (toolbar) {
      updateScrollNavButtons(toolbar, container);
    }

    // Pasang listener sinkronisasi scroll dua arah (top bar <-> table container)
    if (!container.dataset.topScrollAttached) {
      container.dataset.topScrollAttached = "1";
      let isSyncing = false;

      topBar.addEventListener("scroll", () => {
        if (isSyncing) return;
        isSyncing = true;
        container.scrollLeft = topBar.scrollLeft;
        isSyncing = false;
        if (toolbar) updateScrollNavButtons(toolbar, container);
      });

      container.addEventListener("scroll", () => {
        if (isSyncing) return;
        isSyncing = true;
        topBar.scrollLeft = container.scrollLeft;
        isSyncing = false;
        if (toolbar) updateScrollNavButtons(toolbar, container);
      });

      if (window.ResizeObserver) {
        const ro = new ResizeObserver(() => {
          updateTopScrollbar(table);
        });
        ro.observe(container);
        ro.observe(table);
      }
    }
  }

  // Update status bar di atas tabel
  function updateStatusBar(table, visibleCount, totalCount) {
    const tableId = ensureTableId(table);
    const container = getTableContainer(table);
    if (!container || !container.parentNode) return;

    let bar = container.parentNode.querySelector(`.excel-filter-status-bar[data-for="${tableId}"]`);
    const filters = tableFiltersMap.get(table) || {};
    const activeFilterCount = Object.values(filters).filter(Boolean).length;

    if (!bar) {
      bar = document.createElement("div");
      bar.className = "excel-filter-status-bar";
      bar.dataset.for = tableId;
      container.parentNode.insertBefore(bar, container);
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
    root.querySelectorAll("table.data-table, table.table").forEach(table => {
      enhanceTableWithExcelFilter(table);
      applyFiltersToTable(table);
    });
  }

  // Global Observer
  let scanPending = false;
  const observer = new MutationObserver((mutations) => {
    let hasRelevantMutation = false;
    for (const m of mutations) {
      for (const node of m.addedNodes) {
        if (node.nodeType === 1) {
          const cl = node.classList;
          if (cl?.contains("table-pagination-toolbar") ||
              cl?.contains("table-top-scrollbar") ||
              cl?.contains("excel-filter-status-bar") ||
              cl?.contains("excel-filter-popover") ||
              node.closest?.(".table-pagination-toolbar, .table-top-scrollbar, .excel-filter-popover")) {
            continue;
          }
          hasRelevantMutation = true;
          break;
        }
      }
      if (hasRelevantMutation) break;
      for (const node of m.removedNodes) {
        if (node.nodeType === 1) {
          const cl = node.classList;
          if (cl?.contains("table-pagination-toolbar") ||
              cl?.contains("table-top-scrollbar") ||
              cl?.contains("excel-filter-status-bar") ||
              cl?.contains("excel-filter-popover") ||
              node.closest?.(".table-pagination-toolbar, .table-top-scrollbar, .excel-filter-popover")) {
            continue;
          }
          hasRelevantMutation = true;
          break;
        }
      }
      if (hasRelevantMutation) break;
    }

    if (!hasRelevantMutation) return;

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

  window.addEventListener("resize", () => {
    document.querySelectorAll("table.data-table, table.table").forEach(updateTopScrollbar);
  });

  // Expose API ke Window
  window.enableExcelTableFilters = scanAndEnhanceTables;
  window.toggleQuickFilterRow = toggleQuickFilterRow;
  window.updateAllTableTopScrollbars = () => {
    document.querySelectorAll("table.data-table, table.table").forEach(updateTopScrollbar);
  };
})();
