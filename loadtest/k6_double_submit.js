// Bio-Chain · Chaos load test: 1.000 user, double-submit / spam-click pada transaksi sensitif.
//
// Jalankan (server harus hidup, mis. `py -m uvicorn app.main:app --port 8000`):
//   k6 run loadtest/k6_double_submit.js
//   k6 run -e BASE_URL=http://127.0.0.1:8000 -e VUS=1000 -e DURATION=60s loadtest/k6_double_submit.js
//
// Skenario paralel:
//   spam_report  : tiap VU menekan "Lapor Sekam" 5× serentak dengan client_event_id sama (spam click / retry offline)
//   spam_verify  : 5 pengepul-klik serentak memverifikasi harvest yang sama (tanpa kunci idempotensi)
//   login_storm  : badai login (PBKDF2) pada laju tetap
//   probe        : health check 5 rps — mengukur apakah event loop ikut membeku
//
// Lulus bila: 0 efek ganda (harvest/verifikasi dobel), 0 error 5xx, probe p95 < 250 ms.

import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Trend } from "k6/metrics";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8000";
const VUS = Number(__ENV.VUS || 1000);
const DURATION = __ENV.DURATION || "30s";
const SPAM = 5;
const THINK = () => sleep(1 + Math.random() * 2);   // jeda manusia antar aksi (1–3 s); 0 = mode banjir
const NO_THINK = __ENV.NO_THINK === "1";

const duplicateEffects = new Counter("duplicate_effects");   // data tumpang tindih
const serverErrors = new Counter("server_errors");           // 5xx
const shed = new Counter("load_shed_503_429");               // penolakan terkendali (bukan crash)
const probeLatency = new Trend("probe_latency", true);

export const options = {
  setupTimeout: "120s",
  scenarios: {
    spam_report: {
      executor: "ramping-vus", exec: "spamReport", startVUs: 0,
      stages: [{ duration: "10s", target: VUS }, { duration: DURATION, target: VUS }, { duration: "5s", target: 0 }],
    },
    spam_verify: {
      executor: "constant-vus", exec: "spamVerify", vus: Math.max(1, Math.floor(VUS / 20)), duration: DURATION,
      startTime: "10s",
    },
    login_storm: {
      executor: "constant-arrival-rate", exec: "loginStorm", rate: Number(__ENV.LOGIN_RPS || 20),
      timeUnit: "1s", duration: DURATION, preAllocatedVUs: 50, maxVUs: 400, startTime: "10s",
    },
    probe: {
      executor: "constant-arrival-rate", exec: "probe", rate: 5, timeUnit: "1s",
      duration: DURATION, preAllocatedVUs: 5, maxVUs: 50, startTime: "10s",
    },
  },
  thresholds: {
    duplicate_effects: ["count==0"],
    server_errors: ["count==0"],
    probe_latency: ["p(95)<250"],
  },
};

function uid() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${__VU}-${__ITER}`;
}

function login(identifier, password) {
  const r = http.post(`${BASE}/api/v1/auth/login`, JSON.stringify({ identifier, password }),
    { headers: { "Content-Type": "application/json" }, timeout: "60s" });
  if (r.status !== 200) throw new Error(`login ${identifier} gagal: ${r.status} ${r.body}`);
  return { headers: { "Content-Type": "application/json", Authorization: `Bearer ${r.json("access_token")}` },
           timeout: "60s" };
}

export function setup() {
  return {
    petani: [login("petani_sugeng", "sekam123"), login("petani_sari", "sekam123")],
    pengepul: login("pengepul_sleman", "kud2026"),
  };
}

function tally(responses) {
  for (const r of responses) {
    if (r.status >= 500 && r.status !== 503) serverErrors.add(1);
    if (r.status === 503 || r.status === 429) shed.add(1);
  }
}

export function spamReport(data) {
  const auth = data.petani[__VU % data.petani.length];
  const body = JSON.stringify({ quantity_kg: 50 + (__ITER % 50), client_event_id: uid() });
  const res = http.batch(Array.from({ length: SPAM }, () =>
    ["POST", `${BASE}/api/v1/farmer/harvest`, body, auth]));
  tally(res);
  const ids = new Set(res.filter(r => r.status === 201).map(r => r.json("id")));
  if (ids.size > 1) duplicateEffects.add(ids.size - 1);
  check(res, { "spam lapor → satu harvest": () => ids.size <= 1 });
  if (!NO_THINK) THINK();
}

export function spamVerify(data) {
  const auth = data.petani[__VU % data.petani.length];
  const created = http.post(`${BASE}/api/v1/farmer/harvest`, JSON.stringify({ quantity_kg: 100 }), auth);
  if (created.status !== 201) { tally([created]); if (!NO_THINK) THINK(); return; }
  const body = JSON.stringify({ harvest_id: created.json("id"), weighed_kg: 98, moisture: 11, ash: 18,
                                volatile_matter: 66, fixed_carbon: 16, contamination: 1 });
  const res = http.batch(Array.from({ length: SPAM }, () =>
    ["POST", `${BASE}/api/v1/collector/verify`, body, data.pengepul]));
  tally(res);
  const wins = res.filter(r => r.status === 200).length;
  if (wins > 1) duplicateEffects.add(wins - 1);
  check(res, {
    "verifikasi ganda → tidak pernah >1 menang": () => wins <= 1,
    "verifikasi ganda → ada 1 pemenang (tidak di-shed)": () => wins === 1,
    "sisanya 409 Conflict": () => res.every(r => [200, 409, 429, 503].includes(r.status)),
  });
  if (!NO_THINK) THINK();
}

export function loginStorm() {
  const r = http.post(`${BASE}/api/v1/auth/login`,
    JSON.stringify({ identifier: "petani_sugeng", password: "sekam123" }),
    { headers: { "Content-Type": "application/json" }, timeout: "60s" });
  tally([r]);
  check(r, { "login 200/429": x => x.status === 200 || x.status === 429 });
}

export function probe() {
  const r = http.get(`${BASE}/health`, { timeout: "30s" });
  probeLatency.add(r.timings.duration);
  tally([r]);
}
