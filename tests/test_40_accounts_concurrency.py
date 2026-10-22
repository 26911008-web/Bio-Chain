"""Bio-Chain v2 — 40 Concurrent Accounts Multi-Persona Load & Traffic Benchmark.

Simulates 40 distinct, authenticated accounts performing realistic operations
simultaneously against the live server (http://127.0.0.1:8000).

40 Personas Distribution:
- 15 Petani (petani_01 .. petani_15)
- 15 Pengepul (pengepul_01 .. pengepul_15)
- 4 Driver (driver_01 .. driver_04)
- 4 Pabrik (pabrik_01 .. pabrik_04)
- 2 Auditor (auditor_01 .. auditor_02)
Total = 40 active concurrent users.
"""

import asyncio
import json
import statistics
import time
from collections import defaultdict
import httpx

BASE_URL = "http://127.0.0.1:8000"
PASSWORD = "BioChain2026!"

ACCOUNTS = []
for i in range(1, 16):
    ACCOUNTS.append({"username": f"petani_{i:02d}", "role": "petani"})
for i in range(1, 16):
    ACCOUNTS.append({"username": f"pengepul_{i:02d}", "role": "pengepul"})
for i in range(1, 5):
    ACCOUNTS.append({"username": f"driver_{i:02d}", "role": "driver"})
for i in range(1, 5):
    ACCOUNTS.append({"username": f"pabrik_{i:02d}", "role": "pabrik"})
for i in range(1, 3):
    ACCOUNTS.append({"username": f"auditor_{i:02d}", "role": "auditor"})

assert len(ACCOUNTS) == 40, f"Expected 40 accounts, got {len(ACCOUNTS)}"

class BenchmarkRecorder:
    def __init__(self):
        self.records = []
        self.lock = asyncio.Lock()

    async def record(self, persona: str, username: str, method: str, endpoint: str, status_code: int, duration_ms: float, error: str = None):
        async with self.lock:
            self.records.append({
                "persona": persona,
                "username": username,
                "method": method,
                "endpoint": endpoint,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "error": error,
                "timestamp": time.time(),
            })

    def get_stats(self):
        if not self.records:
            return {}
        durations = [r["duration_ms"] for r in self.records]
        success_count = sum(1 for r in self.records if 200 <= r["status_code"] < 300)
        error_count = len(self.records) - success_count
        durations.sort()
        p50 = durations[int(len(durations) * 0.50)]
        p95 = durations[min(int(len(durations) * 0.95), len(durations) - 1)]
        p99 = durations[min(int(len(durations) * 0.99), len(durations) - 1)]

        by_endpoint = defaultdict(list)
        by_persona = defaultdict(list)
        for r in self.records:
            by_endpoint[f"{r['method']} {r['endpoint']}"].append(r["duration_ms"])
            by_persona[r["persona"]].append(r["duration_ms"])

        return {
            "total_requests": len(self.records),
            "successful_requests": success_count,
            "failed_requests": error_count,
            "success_rate_pct": (success_count / len(self.records)) * 100,
            "min_ms": min(durations),
            "avg_ms": statistics.mean(durations),
            "median_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
            "max_ms": max(durations),
            "by_endpoint": {
                ep: {
                    "count": len(d_list),
                    "avg_ms": statistics.mean(d_list),
                    "p95_ms": sorted(d_list)[min(int(len(d_list) * 0.95), len(d_list) - 1)]
                } for ep, d_list in by_endpoint.items()
            },
            "by_persona": {
                p: {
                    "count": len(d_list),
                    "avg_ms": statistics.mean(d_list),
                    "p95_ms": sorted(d_list)[min(int(len(d_list) * 0.95), len(d_list) - 1)]
                } for p, d_list in by_persona.items()
            }
        }


async def login_user(client: httpx.AsyncClient, account: dict, recorder: BenchmarkRecorder) -> dict:
    t0 = time.perf_counter()
    try:
        r = await client.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"identifier": account["username"], "password": PASSWORD}
        )
        elapsed = (time.perf_counter() - t0) * 1000
        if r.status_code == 200:
            data = r.json()
            await recorder.record(account["role"], account["username"], "POST", "/api/v1/auth/login", 200, elapsed)
            return {**account, "token": data["access_token"], "user_id": data["user_id"]}
        else:
            await recorder.record(account["role"], account["username"], "POST", "/api/v1/auth/login", r.status_code, elapsed, r.text)
            return {**account, "token": None, "error": r.text}
    except Exception as exc:
        elapsed = (time.perf_counter() - t0) * 1000
        await recorder.record(account["role"], account["username"], "POST", "/api/v1/auth/login", 0, elapsed, str(exc))
        return {**account, "token": None, "error": str(exc)}


async def execute_persona_tasks(client: httpx.AsyncClient, session: dict, recorder: BenchmarkRecorder, wave: int):
    token = session.get("token")
    if not token:
        return

    headers = {"Authorization": f"Bearer {token}"}
    role = session["role"]
    username = session["username"]

    async def req(method: str, path: str, json_data: dict = None):
        t0 = time.perf_counter()
        try:
            if method == "GET":
                r = await client.get(f"{BASE_URL}{path}", headers=headers)
            else:
                r = await client.post(f"{BASE_URL}{path}", json=json_data or {}, headers=headers)
            elapsed = (time.perf_counter() - t0) * 1000
            await recorder.record(role, username, method, path, r.status_code, elapsed, None if r.status_code < 400 else r.text[:120])
            return r
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            await recorder.record(role, username, method, path, 0, elapsed, str(e))
            return None

    if role == "petani":
        await req("GET", "/api/v1/farmer/harvests")
        await req("GET", "/api/v1/farmer/listings")
        await req("GET", "/api/v1/farmer/incentive")
        await req("GET", "/api/v1/farmer/wallet")
        # Write action
        await req("POST", "/api/v1/farmer/harvest", {
            "quantity_kg": 1500.0 + (wave * 50),
            "notes": f"Batch dari {username} wave {wave}"
        })

    elif role == "pengepul":
        await req("GET", "/api/v1/collector/market")
        await req("GET", "/api/v1/collector/delivery-requests")
        await req("GET", "/api/v1/collector/available-harvests")
        await req("GET", "/api/v1/collector/daily-summary")
        # Computational planning call (CVRP route planning)
        await req("POST", "/api/v1/collector/pickup-plan", {})

    elif role == "driver":
        await req("GET", "/api/v1/driver/active-route")

    elif role == "pabrik":
        await req("GET", "/api/v1/factory/delivery-requests")
        await req("GET", "/api/v1/factory/settlements")
        await req("GET", "/api/v1/factory/qc/lots")
        await req("GET", "/api/v1/factory/batches")
        # Netback pricing calculation
        await req("POST", "/api/v1/factory/pricing/recommend", {
            "moisture": 11.5,
            "ash": 17.5,
            "price_pellet_per_kg": 650.0,
            "price_biochar_per_kg": 2200.0,
            "price_silica_per_kg": 5000.0,
            "silica_route": "biochar"
        })

    elif role == "auditor":
        await req("GET", "/api/v1/auditor/summary")
        await req("GET", "/api/v1/auditor/discrepancies")
        await req("GET", "/api/v1/auditor/mass-balance/1")


async def run_benchmark():
    recorder = BenchmarkRecorder()
    limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    timeout = httpx.Timeout(60.0, connect=10.0)

    print("=" * 70)
    print("BIO-CHAIN v2: 40 CONCURRENT ACCOUNTS LOAD BENCHMARK")
    print("=" * 70)
    print(f"Target Server: {BASE_URL}")
    print(f"Total Concurrent Accounts: {len(ACCOUNTS)}")
    print(f"Role Breakdown: 15 Petani, 15 Pengepul, 4 Driver, 4 Pabrik, 2 Auditor")
    print("-" * 70)

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        # Check system health first
        h = await client.get(f"{BASE_URL}/api/v1/system/status")
        print(f"[PRE-FLIGHT] System Health: {h.status_code} {h.json().get('status')}")

        # PHASE 1: LOGIN STORM (Simultaneous 40 Accounts)
        print("\n[PHASE 1] Firing simultaneous login storm for 40 accounts...")
        t_login_start = time.perf_counter()
        login_tasks = [login_user(client, acc, recorder) for acc in ACCOUNTS]
        authenticated_sessions = await asyncio.gather(*login_tasks)
        t_login_total = time.perf_counter() - t_login_start

        successful_logins = [s for s in authenticated_sessions if s.get("token")]
        print(f"[PHASE 1 RESULT] Logins successful: {len(successful_logins)}/{len(ACCOUNTS)} in {t_login_total:.2f}s")
        print(f"[PHASE 1 RESULT] Login Throughput: {len(successful_logins)/t_login_total:.2f} logins/sec")

        if len(successful_logins) < 40:
            print("WARNING: Some accounts failed to log in:")
            for s in authenticated_sessions:
                if not s.get("token"):
                    print(f"  - {s['username']}: {s.get('error')}")

        # PHASE 2: CONCURRENT MULTI-PERSONA WORKLOAD (WAVE 1 & WAVE 2)
        print("\n[PHASE 2] Launching concurrent multi-persona operations across all 40 accounts...")
        t_ops_start = time.perf_counter()
        wave1_tasks = [execute_persona_tasks(client, s, recorder, wave=1) for s in successful_logins]
        await asyncio.gather(*wave1_tasks)
        t_wave1 = time.perf_counter() - t_ops_start
        print(f"[PHASE 2 - WAVE 1] Complete in {t_wave1:.2f}s")

        t_wave2_start = time.perf_counter()
        wave2_tasks = [execute_persona_tasks(client, s, recorder, wave=2) for s in successful_logins]
        await asyncio.gather(*wave2_tasks)
        t_wave2 = time.perf_counter() - t_wave2_start
        print(f"[PHASE 2 - WAVE 2] Complete in {t_wave2:.2f}s")

        # PHASE 3: SUSTAINED HIGH-CONCURRENCY READ & WRITE BURST
        print("\n[PHASE 3] Executing sustained high-concurrency burst across 40 accounts...")
        t_burst_start = time.perf_counter()
        burst_tasks = []
        for s in successful_logins:
            burst_tasks.append(execute_persona_tasks(client, s, recorder, wave=3))
            burst_tasks.append(execute_persona_tasks(client, s, recorder, wave=4))
        await asyncio.gather(*burst_tasks)
        t_burst = time.perf_counter() - t_burst_start
        print(f"[PHASE 3 BURST] Complete in {t_burst:.2f}s")

    # COMPILE & DISPLAY BENCHMARK RESULTS
    stats = recorder.get_stats()
    total_time = t_login_total + t_wave1 + t_wave2 + t_burst
    rps = stats["total_requests"] / total_time if total_time > 0 else 0

    print("\n" + "=" * 70)
    print("BENCHMARK & LOAD DIVISION PERFORMANCE REPORT")
    print("=" * 70)
    print(f"Total Requests Executed:    {stats['total_requests']}")
    print(f"Successful Requests (2xx):  {stats['successful_requests']} ({stats['success_rate_pct']:.1f}%)")
    print(f"Failed Requests (4xx/5xx):  {stats['failed_requests']}")
    print(f"Total Benchmark Time:       {total_time:.2f} seconds")
    print(f"Overall Throughput:         {rps:.2f} req/s")
    print("-" * 70)
    print("LATENCY DISTRIBUTION (ms):")
    print(f"  Min:                      {stats['min_ms']:.2f} ms")
    print(f"  Average:                  {stats['avg_ms']:.2f} ms")
    print(f"  Median (p50):             {stats['median_ms']:.2f} ms")
    print(f"  95th Percentile (p95):    {stats['p95_ms']:.2f} ms")
    print(f"  99th Percentile (p99):    {stats['p99_ms']:.2f} ms")
    print(f"  Max:                      {stats['max_ms']:.2f} ms")
    print("-" * 70)
    print("LATENCY BY PERSONA (40 Accounts):")
    for persona, p_data in stats["by_persona"].items():
        print(f"  - {persona.upper():<10}: {p_data['count']:>4} reqs | Avg: {p_data['avg_ms']:>6.2f} ms | p95: {p_data['p95_ms']:>6.2f} ms")
    print("-" * 70)
    print("TOP ENDPOINTS LATENCY:")
    for ep, ep_data in sorted(stats["by_endpoint"].items(), key=lambda x: x[1]["avg_ms"], reverse=True)[:8]:
        print(f"  - {ep:<38}: {ep_data['count']:>3} reqs | Avg: {ep_data['avg_ms']:>6.2f} ms | p95: {ep_data['p95_ms']:>6.2f} ms")
    print("=" * 70)

    # Save detailed report to json
    report_file = "load_test_40_accounts_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "accounts_count": len(ACCOUNTS),
            "benchmark_summary": stats,
            "overall_rps": rps,
            "total_duration_s": total_time,
            "phases": {
                "phase1_login_storm_s": t_login_total,
                "phase2_wave1_s": t_wave1,
                "phase2_wave2_s": t_wave2,
                "phase3_burst_s": t_burst
            }
        }, f, indent=2)
    print(f"\nDetailed report saved to: {report_file}")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
