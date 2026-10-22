# 📋 VIBE-CODING AUDIT & MODULARIZATION REPORT
**Repository**: `bio-chain-prototype`
**Branch**: `chore/vibe-audit-v2`
**Baseline Tag**: `pre-vibe-audit-baseline`
**Agent**: Principal Autonomous Refactoring & Audit Agent
**Date**: October 18, 2026

---

## 1. Stack & Baseline Status

| Component | Detected Stack / Specification |
|:---|:---|
| **Backend** | Python 3.14, FastAPI 0.115+, SQLAlchemy (AsyncPG PostgreSQL with local SQLite fallback), Pydantic v2 Settings |
| **Frontend** | Vanilla JavaScript (ES2022 PWA), Native CSS3 Tokens & Glassmorphism, Leaflet 1.9.4 |
| **Package Managers** | `npm` (Dev tools & Playwright), `pip` (Python dependencies) |
| **Backend Directories** | `app/` (`app/engines/`, `app/models/`, `app/routers/`, `app/services/`), `scripts/`, `migrations/` |
| **Frontend Directories** | `app/static/` (`app.js`, `field-ops.js`, `factory-ops.js`, `ui-enhance.js`, `excel-filter.js`, `sw.js`, `tokens.css`, `components.css`) |
| **Verification Suites** | - Python Pytest: `py -m pytest tests/test_fase_omni_e2e.py tests/test_circular_e2e.py tests/test_audit_hardening.py tests/test_field_compliance.py`<br>- Playwright E2E: `npx playwright test` |
| **Baseline Test Status** | **45/45 pytest PASSED** (57.0s) &bull; **37/37 Playwright PASSED** (4.9m) &bull; **100% Green** |
| **Total Source Lines** | 42,813 lines across 107 analyzed source files |

### Source Size Baseline (Top 10 Source Files)
1. `app/static/app.js` — **7,092 lines** (Frontend core orchestrator, auth, routing, map, bidding)
2. `app/static/field-ops.js` — **3,709 lines** (Field operations, farmer forms, offline queue, receipt)
3. `app/routers/factory.py` — **3,038 lines** (Factory gate, QC, blends, production batches, ash ledger)
4. `app/static/components.css` — **2,150 lines** (UI component design system)
5. `app/routers/collector.py` — **1,933 lines** (Collector bidding, CVRP logistics, settlements)
6. `app/static/factory-ops.js` — **1,337 lines** (Factory UI operations, lab test modals, conversion calculators)
7. `app/routers/farmer.py` — **1,209 lines** (Farmer harvest listings, PDP requests, carbon claims)
8. `app/static/index.html` — **1,154 lines** (Main SPA HTML template)
9. `app/engines/product_optimization.py` — **973 lines** (Multi-output bioenergy optimization engine)
10. `app/static/ui-enhance.js` — **939 lines** (Toast, modal animations, offline indicator)

---

## 2. Protected Framework Files
*The following framework and platform files are essential entry points or runtime targets. Static analysis tools (such as Knip or Vulture) flag them due to HTML/dynamic loading. They **MUST NOT** be deleted:*

- `app/main.py`: FastAPI server entrypoint and ASGI router mounter.
- `app/static/index.html`: SPA template and single-page container.
- `app/static/sw.js`: PWA service worker providing offline capability for rural field operations.
- `app/static/vendor/leaflet.min.js`: Leaflet mapping engine.
- `app/static/tokens.css` & `app/static/components.css`: Core design system CSS stylesheets.
- `app/models/__init__.py`: Central SQLAlchemy model export surface.
- `app/migrations.py`: Schema migration engine.
- `playwright.config.ts`: Playwright test runner configuration.

---

## 3. Actionable Backlog

### 3.1 [CRITICAL] Security & Env Leaks
- [ ] Ensure `JWT_SECRET` has no fallback in production mode (`DEBUG=False` validation strict check).
- [ ] Audit `.env.example` to ensure all config parameters (`CLIENT_CLOCK_MAX_PAST_HOURS`, `DEMO_MODE`, `AUTO_MIGRATE`, `CSP_ENABLED`) are documented with clear production instructions.
- [ ] Guard against hardcoded `http://localhost` fallback in production runtime.
- [ ] Verify sensitive user attributes (passwords, salts) are stripped from all API outputs.

### 3.2 [SAFE PURGE] Verified Dead Files & Unused Dependencies
- [ ] Remove obsolete ad-hoc runner scripts superseded by Playwright specs:
  - `tests/fase1_runner.js`
  - `tests/fase2_runner.js`
  - `tests/fase3_runner.js`
  - `tests/fase4_runner.js`
  - `tests/fase5_runner.js`
  - `tests/fase6_omni_regression.js`
- [ ] Remove obsolete temporary debugging script: `scripts/test_gate_click.js`.
- [ ] Remove unused Python imports across `app/routers/`, `app/services/`, and `app/engines/` (`anyio.to_thread`, `timedelta`, `LIVE_STOP_STATUSES`, `Conversion`, `calculate_incentive`, `DeliveryEvent`, `DeliveryScheme`).
- [ ] Clean up `package.json` entry point hint (`"main": "index.js"` pointing to missing root file).

### 3.3 [DEDUPLICATION] Duplicated Utilities & Logic to Consolidate
- [ ] Deduplicate multi-output conversion calculations and response formatting in `app/engines/product_optimization.py` (lines 239-262, 391-414, 524-540, 640-656).
- [ ] Deduplicate token generation and user response structuring in `app/routers/auth.py` (lines 193-214 vs 243-264).
- [ ] Consolidate shared circular notification / audit event helpers between `app/routers/collector.py` and `app/routers/factory.py`.
- [ ] Consolidate duplicate table row formatting and currency formatters across `app/static/app.js` and `app/static/factory-ops.js`.

### 3.4 [CONTRACTS] Type Safety & API Client Centralization
- [ ] Enforce standard `api(path, options)` wrapper for all outbound HTTP requests in `app/static/` (eliminate raw scattered `fetch` calls).
- [ ] Ensure standardized error handling with user-facing toast feedback and offline queue intercept.
- [ ] Audit TypeScript test specs (`tests/*.spec.ts`) for un-typed `: any` casts and standardize payload contracts.

### 3.5 [MODULARIZATION] Top 5 God Files Decomposition Plan
- [ ] **God File 1: `app/static/app.js` (7,092 lines)**
  - Sub-module 1: `app/static/js/core/api-client.js` — Centralized network client, bearer token refresh, and network retry logic.
  - Sub-module 2: `app/static/js/modules/auth-session.js` — Authentication modal, role selector, demo account switcher, and session management.
  - Sub-module 3: `app/static/js/modules/collector-view.js` — B2B bidding interface, stock listing cards, and CVRP map route visualization.
  - Orchestrator: Retain `app.js` as the coordinator wiring state and modules.
- [ ] **God File 2: `app/static/field-ops.js` (3,709 lines)**
  - Sub-module 1: `app/static/js/modules/farmer-harvest-form.js` — Harvest submission, biomass type selection, geolocation capture.
  - Sub-module 2: `app/static/js/modules/offline-sync-queue.js` — IndexedDB offline outbox, retry scheduler, connectivity monitors.
  - Sub-module 3: `app/static/js/modules/field-kuitansi.js` — Digital payment receipt generator, QR code stamper, PDP masking.
  - Orchestrator: Retain `field-ops.js` as coordinator.
- [ ] **God File 3: `app/routers/factory.py` (3,038 lines)**
  - Sub-module 1: `app/routers/factory_inbound.py` — Inbound reception, weighbridge gross/tare measurement, and moisture/ash QC testing.
  - Sub-module 2: `app/routers/factory_production.py` — Production blend formulation, pyrolysis batch tracking, and mass balance calculus.
  - Sub-module 3: `app/routers/factory_ash.py` — Industrial ash ledger, toxic heavy metal lab verification, and Poktan circular distribution.
  - Orchestrator: Retain `factory.py` as unified router mounting inbound, production, and ash endpoints.
- [ ] **God File 4: `app/routers/collector.py` (1,933 lines)**
  - Sub-module 1: `app/routers/collector_bidding.py` — Stock listing discovery, competitive bid placement, and price negotiation engine.
  - Sub-module 2: `app/routers/collector_logistics.py` — CVRP multi-stop pickup routing plan, bulk-density checks, driver dispatch.
  - Sub-module 3: `app/routers/collector_settlement.py` — Down payment tracking, logistics charges, warehouse inventory ledger.
  - Orchestrator: Retain `collector.py` as unified router.
- [ ] **God File 5: `app/static/factory-ops.js` (1,337 lines)**
  - Sub-module 1: `app/static/js/modules/factory-qc-modal.js` — Weighbridge reception modal, tare subtraction, refraction deductions.
  - Sub-module 2: `app/static/js/modules/factory-pyrolysis-calc.js` — Pyrolysis yield interactive calculator, bio-silica projection, ISO 50001 energy log.
  - Orchestrator: Retain `factory-ops.js` as coordinator.

---

## 4. Verification Checkpoints
- After every deletion or decomposition: Run `py -m pytest tests/test_fase_omni_e2e.py tests/test_circular_e2e.py tests/test_audit_hardening.py tests/test_field_compliance.py`.
- After every phase completion: Run full Playwright test suite `npx playwright test`.
- Zero tolerance for regressions: 100% tests must pass before proceeding.
