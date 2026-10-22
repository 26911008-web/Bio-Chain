// Bio-Chain — Optimal Concurrency Threshold Discovery
// Mengukur titik jenuh optimal (sweet-spot) tanpa load-shedding

import http from "k6/http";
import { sleep } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";

const reqLatency = new Trend("req_latency", true);
const successRate = new Rate("success_rate");
const loadShedded = new Counter("load_shedded_503");
const serverErrors = new Counter("server_errors_5xx");

export const options = {
  scenarios: {
    sweet_spot_sweep: {
      executor: "ramping-vus",
      startVUs: 5,
      stages: [
        { duration: "6s", target: 20 },  // 20 VU
        { duration: "8s", target: 50 },  // 50 VU
        { duration: "8s", target: 80 },  // 80 VU
        { duration: "4s", target: 0 },   // Cool down
      ],
    },
  },
  thresholds: {
    server_errors_5xx: ["count==0"],
  },
};

export function setup() {
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

  let res;
  if (pick < 0.45) {
    // Read status & health (Ultra-ringan)
    res = http.get(`${BASE_URL}/api/v1/system/status`);
  } else if (pick < 0.70) {
    // Read demo accounts (Cacheable)
    res = http.get(`${BASE_URL}/api/v1/auth/demo-accounts`);
  } else if (pick < 0.90) {
    // Read params (Authenticated)
    res = http.get(`${BASE_URL}/api/v1/params`, { headers: authHeaders });
  } else {
    // Pricing recommendation (Business calculation)
    const payload = JSON.stringify({
      moisture: 14.5,
      ash: 18.0,
      contamination: 0.0,
      sensitivity: true,
    });
    res = http.post(`${BASE_URL}/api/v1/factory/pricing/recommend`, payload, {
      headers: authHeaders,
    });
  }

  record(res);
  sleep(0.04 + Math.random() * 0.04);
}

function record(res) {
  reqLatency.add(res.timings.duration);
  if (res.status === 200 || res.status === 201) {
    successRate.add(1);
  } else {
    successRate.add(0);
    if (res.status === 503) loadShedded.add(1);
    else if (res.status >= 500) serverErrors.add(1);
  }
}
