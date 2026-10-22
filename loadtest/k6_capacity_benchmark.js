// Bio-Chain — Benchmarking Batas Kapasitas & Pengaturan Lalu Lintas Simultan
// Menguji batas throughput, latensi p95, dan regulasi traffic (backpressure & load shedding)

import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";

const reqLatency = new Trend("req_latency", true);
const successRate = new Rate("success_rate");
const rateLimited = new Counter("rate_limited_429");
const loadShedded = new Counter("load_shedded_503");
const serverErrors = new Counter("server_errors_5xx");

export const options = {
  scenarios: {
    // Ramp-up traffic pengguna simultan (10 -> 50 -> 150 -> 250 VUs)
    concurrency_ramp: {
      executor: "ramping-vus",
      startVUs: 10,
      stages: [
        { duration: "6s", target: 50 },   // Fase 1: Beban normal (50 VU)
        { duration: "8s", target: 120 },  // Fase 2: Beban puncak sedang (120 VU)
        { duration: "8s", target: 250 },  // Fase 3: Stress test batas saturasi (250 VU)
        { duration: "4s", target: 0 },    // Ramp down pendinginan
      ],
    },
  },
  thresholds: {
    req_latency: ["p(95)<500"], // 95% request di bawah 500ms
    success_rate: ["rate>0.85"], // Minimal 85% sukses (termasuk backpressure 503)
    server_errors_5xx: ["count==0"], // 0 unhandled crash (500)
  },
};

export function setup() {
  // Login sebagai admin/pabrik untuk mendapatkan token JWT
  const loginRes = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({ identifier: "admin", password: "admin2026" }),
    { headers: { "Content-Type": "application/json" } }
  );

  let token = "";
  if (loginRes.status === 200) {
    const body = loginRes.json();
    token = body.access_token;
  }
  return { token: token };
}

export default function (data) {
  const pick = Math.random();
  const authHeaders = data.token
    ? {
        "Content-Type": "application/json",
        Authorization: `Bearer ${data.token}`,
      }
    : { "Content-Type": "application/json" };

  if (pick < 0.40) {
    // 1. Health check & status probe (Read-only, ultra-ringan)
    const res = http.get(`${BASE_URL}/api/v1/system/status`);
    record(res);
  } else if (pick < 0.65) {
    // 2. Akses akun demo / katalog publik (Read-heavy)
    const res = http.get(`${BASE_URL}/api/v1/auth/demo-accounts`);
    record(res);
  } else if (pick < 0.85) {
    // 3. Pengecekan parameter sistem & harga acuan (Authenticated Read)
    const res = http.get(`${BASE_URL}/api/v1/params`, { headers: authHeaders });
    record(res);
  } else {
    // 4. Simulasi komputasi engine pricing & sensitivitas (CPU/Business Logic)
    const payload = JSON.stringify({
      moisture: 14.5,
      ash: 18.0,
      contamination: 0.0,
      sensitivity: true,
    });
    const res = http.post(`${BASE_URL}/api/v1/factory/pricing/recommend`, payload, {
      headers: authHeaders,
    });
    record(res);
  }

  // Jeda realistis antar aksi pengguna (20ms - 50ms)
  sleep(0.02 + Math.random() * 0.03);
}

function record(res) {
  reqLatency.add(res.timings.duration);
  if (res.status === 200 || res.status === 201) {
    successRate.add(1);
  } else {
    successRate.add(0);
    if (res.status === 429) rateLimited.add(1);
    else if (res.status === 503) loadShedded.add(1);
    else if (res.status >= 500) serverErrors.add(1);
  }
}
