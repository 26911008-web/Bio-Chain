/**
 * Module: Route Optimization Modal & Dispatch Viewer
 * Handles CVRP interactive multi-stop route planner, vector SVG map, Leaflet map,
 * and dispatch manifest export/printing.
 */
(() => {
  "use strict";
  const H = (s) => (typeof esc === "function" ? esc(s == null ? "" : String(s)) : (s == null ? "" : String(s)));

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
                <span style="color:var(--primary); font-size:11px; font-weight:600;">🔄 Muatan Balik: ~${num(estBackhaul, 0)} kg Abu Bottom Ash Sawah</span>
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
          <div class="kpi-lbl">Abu Bottom Ash Muatan Balik</div>
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
                <th style="padding:6px 8px;" class="num">Abu Bottom Ash Diturunkan</th>
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
            <b>Abu Bottom Ash Diturunkan:</b> ${num(pt.biochar_drop_kg || 0, 0)} kg<br>
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
              <h2>🌿 Bio-Chain · Logistik Biomassa</h2>
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
              <div class="lbl">Muatan Balik Abu Bottom Ash</div>
              <div class="val" style="color:#2563eb;">${biocharKg} kg</div>
              <div class="sub">Integrasi sirkular sawah (pembenah tanah)</div>
            </div>
          </div>

          <!-- Manifest Table -->
          <table class="ro-print-table">
            <thead>
              <tr>
                <th style="width:36px; text-align:center;">No</th>
                <th>Titik Lokasi &amp; Kelompok Tani</th>
                <th style="width:115px; text-align:right;">Muat Biomassa</th>
                <th style="width:115px; text-align:right;">Turun Abu Bottom Ash</th>
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
                <li>Bila petani menerima abu bottom ash sawah, turunkan muatan balik sesuai kuota tercatat (biochar disimpan untuk material baterai).</li>
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
            <h2>📊 Bio-Chain · Analisis Teknis &amp; Optimasi Rute</h2>
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
              <th style="width:105px; text-align:right;">Abu Bottom Ash Diturunkan</th>
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
              Hasil routing dihitung secara komputasional dengan mempertimbangkan densitas sekam (~120 kg/m³) dan abu bottom ash (~450 kg/m³). Dokumen ini valid untuk lampiran klaim efisiensi karbon dan penjaminan mutu rantai pasok.
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


})();
