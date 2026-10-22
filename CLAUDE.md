# Architecture & Engineering Guardrails: `bio-chain-prototype`

Welcome to `bio-chain-prototype`. This document establishes non-negotiable architectural standards, design contracts, and quality gates to maintain modularity, security, and zero-regression integrity.

---

## 1. Canonical Directory Map

| Path | Purpose & Rules |
|:---|:---|
| `app/routers/` | FastAPI REST route handlers. Domain controllers must remain modular. When domain logic exceeds ~600 lines, split into sub-routers (e.g. `factory.py` mounts `factory_inbound.py` and `factory_production.py`; `collector.py` mounts `collector_bidding.py` and `collector_logistics.py`). |
| `app/models/` | SQLAlchemy 2.0 ORM models and Pydantic v2 schemas. Models are centrally exported in `app/models/__init__.py`. |
| `app/services/` | Reusable domain business services (custody, circular audit logging, token authentication, PDP privacy masking). |
| `app/engines/` | Computational and optimization engines (e.g. `cvrp_advanced.py` for routing optimization, `product_optimization.py` for HiGHS multi-output pyrolysis yields). Keep pure algorithm logic separated from HTTP route handling. |
| `app/static/` | Vanilla PWA frontend assets. Core orchestrators: `app.js`, `field-ops.js`, `factory-ops.js`. |
| `app/static/js/modules/` | Dedicated, single-responsibility frontend modules (e.g. `notification-center.js`, `ai-assistant-widget.js`, `route-optimization-modal.js`, `field-kuitansi.js`, `factory-qc-modal.js`, `factory-pyrolysis-calc.js`). Expose functions via explicit `window.<ModuleName>` contracts. |
| `tests/` | Python Pytest suites (`test_*.py`), Playwright browser test specs (`*.spec.ts`), and shared test type contracts (`tests/types.ts`). |
| `scripts/` | Standalone utility, seed, and management scripts. Do NOT mix ad-hoc test runner scripts here. |

---

## 2. Protected Framework & Runtime Files (DO NOT DELETE)

Static analysis tools (e.g., Knip, Vulture) often yield false positives on dynamically loaded SPA assets or ASGI entrypoints. The following files are strictly protected:
- `app/main.py`: ASGI application entrypoint and router mount registry.
- `app/static/index.html`: Main SPA application shell.
- `app/static/sw.js`: PWA Service Worker for offline field data collection.
- `app/static/vendor/leaflet.min.js`: Map engine.
- `app/static/tokens.css` & `app/static/components.css`: Core design system CSS stylesheets.
- `app/models/__init__.py`: Central ORM entity export hub.
- `app/migrations.py`: Schema migration runner.
- `playwright.config.ts`: End-to-end browser test configuration.

---

## 3. Core Architectural Laws (Anti-Vibe-Coding Rules)

### 3.1 File Size & Decomposition Limits
- **Max File Size**: No newly created or refactored source file may exceed **500 lines** without justification. Existing orchestrators must not grow beyond current limits.
- **Single Responsibility Principle (SRP)**: UI modals, calculation wizards, and routing handlers must live in separate sub-modules rather than monolith files.

### 3.2 Network & Data Contracts
- **No Raw `fetch()` in Frontend**: Outbound network requests must use the centralized `api(path, options)` wrapper in `app/static/app.js`. It guarantees automatic Bearer token injection, CSRF validation, standardized error notifications, and offline queue routing.
- **Strong Typing**: 
  - Python: All public functions and endpoints must specify type hints (`list[dict]`, `Optional[str]`, etc.).
  - Playwright Tests: Do not use `: any`. Import typed interfaces from `tests/types.ts`.

### 3.3 Security & Environment Hardening
- **Secrets Management**: Never commit `.env` or hardcode credentials, JWT secrets, or encryption keys.
- **No Hardcoded Hosts**: Never hardcode `http://localhost:8000` in client code or production server paths.
- **Response Sanitization**: Never return passwords, password hashes, salt strings, or internal system keys in API responses.
- **Clock Tolerance**: Field offline sync timestamp delta is strictly validated against `CLIENT_CLOCK_MAX_PAST_HOURS`.

---

## 4. Mandatory Quality Gates & Verification Commands

Before creating any commit or pull request, the complete test suite must pass with 100% green status.

### Backend Pytest Suite
```bash
py -m pytest tests/test_fase_omni_e2e.py tests/test_circular_e2e.py tests/test_audit_hardening.py tests/test_field_compliance.py
```
*Expected: 45 passed (or greater).*

### Frontend Playwright E2E Suite
```bash
npx playwright test
```
*Expected: 37 passed across all browser engines.*

---

## 5. Git Commit Hygiene
- **Explicit Staging**: Always stage specific files (`git add app/routers/xyz.py tests/xyz.spec.ts`). **NEVER** use `git add .` or commit `.env`.
- **Atomic Commits**: Follow Conventional Commits format (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`).
