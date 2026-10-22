"""Exploratory audit script for Bio-Chain live API.
Tests every persona's workflow and actively probes for edge cases, bugs, and data inconsistencies.
"""

import sys
import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000"

def request_api(method, path, body=None, token=None):
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"raw": err_body}
        return e.code, parsed

def run_audit():
    results = {"passed": [], "bugs": []}
    
    # 1. Login all personas
    print("[1] Logging in personas...")
    tokens = {}
    users = {
        "admin": ("admin", "admin2026"),
        "petani": ("petani_sugeng", "sekam123"),
        "pengepul": ("pengepul_sleman", "kud2026"),
        "driver": ("sopir_budi", "truk2026"),
        "pabrik": ("pabrik_indmira", "pabrik2026"),
        "auditor": ("auditor_esg", "audit2026"),
    }
    for role, (u, p) in users.items():
        st, res = request_api("POST", "/api/v1/auth/login", {"identifier": u, "password": p})
        if st == 200:
            tokens[role] = res["access_token"]
            results["passed"].append(f"Login {role} OK")
        else:
            results["bugs"].append(f"Login {role} failed with status {st}: {res}")

    # 2. Check Petani listing features
    print("[2] Auditing Petani listing & validation...")
    # Edge case: Negative quantity
    st, res = request_api("POST", "/api/v1/farmer/listings", {
        "quantity_kg": -50,
        "moisture_pct": 14.0,
        "allow_jemput": True,
        "ask_price_jemput": 350,
    }, token=tokens["petani"])
    if st == 422:
        results["passed"].append("Petani negative quantity rejected with 422")
    else:
        results["bugs"].append(f"Petani negative quantity accepted or wrong status: {st} -> {res}")

    # Edge case: Extreme moisture (> 100%)
    st, res = request_api("POST", "/api/v1/farmer/listings", {
        "quantity_kg": 500,
        "moisture_pct": 105.0,
        "allow_jemput": True,
        "ask_price_jemput": 350,
    }, token=tokens["petani"])
    if st == 422:
        results["passed"].append("Petani moisture > 60% rejected with 422")
    else:
        results["bugs"].append(f"Petani extreme moisture accepted or wrong status: {st} -> {res}")

    # Valid listing creation
    st, res = request_api("POST", "/api/v1/farmer/listings", {
        "quantity_kg": 1000,
        "moisture_pct": 14.5,
        "allow_jemput": True,
        "ask_price_jemput": 350,
        "allow_antar": True,
        "ask_price_antar": 450,
    }, token=tokens["petani"])
    listing_id = None
    if st == 201:
        listing_id = res["id"]
        results["passed"].append(f"Petani created listing #{listing_id}")
    else:
        results["bugs"].append(f"Petani failed to create valid listing: {st} -> {res}")

    # 3. Check Pengepul Market & Bidding
    print("[3] Auditing Pengepul market & bid...")
    st, res = request_api("GET", "/api/v1/collector/market", token=tokens["pengepul"])
    if st == 200 and isinstance(res, list):
        results["passed"].append(f"Pengepul market retrieved ({len(res)} listings)")
    else:
        results["bugs"].append(f"Pengepul market failed: {st} -> {res}")

    if listing_id:
        # Edge case: Bid quantity > remaining
        st, res = request_api("POST", "/api/v1/collector/bids", {
            "listing_id": listing_id,
            "scheme": "jemput",
            "price_per_kg": 380,
            "quantity_kg": 5000,
        }, token=tokens["pengepul"])
        if st in (400, 409, 422):
            results["passed"].append("Bid exceeding stock rejected")
        else:
            results["bugs"].append(f"Bid exceeding stock accepted or wrong code: {st} -> {res}")

        # Valid bid
        st, bid_res = request_api("POST", "/api/v1/collector/bids", {
            "listing_id": listing_id,
            "scheme": "jemput",
            "price_per_kg": 380,
            "quantity_kg": 500,
        }, token=tokens["pengepul"])
        bid_id = None
        if st == 201:
            bid_id = bid_res["bid_id"]
            results["passed"].append(f"Pengepul bid #{bid_id} placed")
        else:
            results["bugs"].append(f"Pengepul bid failed: {st} -> {bid_res}")

        if bid_id:
            # Petani accepts bid
            st, acc_res = request_api("POST", f"/api/v1/farmer/listings/{listing_id}/accept", {
                "bid_id": bid_id,
                "quantity_kg": 500,
            }, token=tokens["petani"])
            if st == 200:
                results["passed"].append(f"Petani accepted bid #{bid_id}")
            else:
                results["bugs"].append(f"Petani accept bid failed: {st} -> {acc_res}")

    # 4. Check Factory Pricing & Mass Balance
    print("[4] Auditing Factory pricing recommendation & mass balance...")
    st, res = request_api("POST", "/api/v1/factory/pricing/recommend", {
        "moisture": 14.0,
        "ash": 16.0,
        "contamination": 2.0,
        "price_pellet_per_kg": 1500.0,
        "price_biochar_per_kg": 3500.0,
        "price_silica_per_kg": 15000.0,
        "sensitivity": True,
    }, token=tokens["pabrik"])
    if st == 200 and "target_per_kg" in res:
        results["passed"].append(f"Factory pricing recommended target: Rp {res['target_per_kg']}/kg")
    else:
        results["bugs"].append(f"Factory pricing failed: {st} -> {res}")

    # Check Mass balance calculations
    st, res = request_api("GET", "/api/v1/factory/batches", token=tokens["pabrik"])
    if st == 200:
        results["passed"].append("Factory batches list OK")
    else:
        results["bugs"].append(f"Factory batches list failed: {st} -> {res}")

    # 5. Check CVRP Routing Engine
    print("[5] Auditing Routing engine...")
    st, res = request_api("POST", "/api/v1/labs/routes/optimize", {
        "mills": [
            {"id": 1, "name": "Penggilingan A", "lat": -7.72, "lon": 110.35, "stock_ton": 3.0},
            {"id": 2, "name": "Penggilingan B", "lat": -7.74, "lon": 110.38, "stock_ton": 2.5},
            {"id": 3, "name": "Penggilingan C", "lat": -7.70, "lon": 110.33, "stock_ton": 4.0},
        ],
        "truck_capacity_ton": 5.0,
        "depot_lat": -7.75,
        "depot_lon": 110.36,
    }, token=tokens["pabrik"])
    trips = res.get("routes") or res.get("trips") or []
    if st == 200 and trips:
        results["passed"].append(f"Routing optimize returned {len(trips)} vehicle trips")
    else:
        results["bugs"].append(f"Routing optimize failed: {st} -> {res.get('detail', 'missing routes')}")

    # 6. Check Carbon IPCC Tier 2 Engine
    print("[6] Auditing Carbon calculation...")
    st, res = request_api("POST", "/api/v1/labs/carbon/calculate", {
        "biomass_ton": 10.0,
        "pyrolysis_temp_c": 500.0,
        "transport_distance_km": 25.0,
        "truck_fuel_type": "diesel",
    }, token=tokens["pabrik"])
    if st == 200 and "net_reduction_tco2" in res:
        results["passed"].append(f"Carbon calculation net CO2: {res['net_reduction_tco2']} tCO2e")
    else:
        results["bugs"].append(f"Carbon calculation failed: {st} -> {res}")

    # 7. Check Admin & Auditor privileges
    print("[7] Auditing Admin & Auditor...")
    st, res = request_api("GET", "/api/v1/admin/stats", token=tokens["admin"])
    if st == 200:
        results["passed"].append("Admin stats retrieved")
    else:
        results["bugs"].append(f"Admin stats failed: {st} -> {res}")

    st, res = request_api("GET", "/api/v1/auditor/summary", token=tokens["auditor"])
    if st == 200:
        results["passed"].append("Auditor summary retrieved")
    else:
        results["bugs"].append(f"Auditor summary failed: {st} -> {res}")

    # Edge case: Petani trying to access admin stats
    st, res = request_api("GET", "/api/v1/admin/stats", token=tokens["petani"])
    if st in (401, 403):
        results["passed"].append("Petani blocked from admin stats (RBAC OK)")
    else:
        results["bugs"].append(f"RBAC breach: Petani accessed admin stats: {st}")

    print("\n" + "=" * 60)
    print("AUDIT SUMMARY RESULTS")
    print("=" * 60)
    print(f"Passed assertions: {len(results['passed'])}")
    for p in results["passed"]:
        print(f"  [OK] {p}")
    print(f"Bugs/Failures detected: {len(results['bugs'])}")
    for b in results["bugs"]:
        print(f"  [BUG] {b}")

if __name__ == "__main__":
    run_audit()
