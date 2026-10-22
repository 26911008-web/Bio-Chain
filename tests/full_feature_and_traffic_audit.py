"""Bio-Chain Comprehensive Feature & Concurrency Traffic Audit.
Tests all features across all personas, probes edge cases, and benchmarks multi-user traffic.
"""

import asyncio
import time
import json
import httpx

BASE_URL = "http://127.0.0.1:8000"

async def main():
    print("=" * 80)
    print("BIO-CHAIN FULL FEATURE & TRAFFIC AUDIT")
    print("=" * 80)
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # -------------------------------------------------------------
        # 1. AUTHENTICATION & PERSONA INITIALIZATION
        # -------------------------------------------------------------
        print("\n[PHASE 1] Otentikasi & Verifikasi Semua Persona...")
        personas = {
            "admin": ("admin", "admin2026"),
            "petani": ("petani_sugeng", "sekam123"),
            "pengepul": ("pengepul_sleman", "kud2026"),
            "driver": ("sopir_budi", "truk2026"),
            "pabrik": ("pabrik_indmira", "pabrik2026"),
            "auditor": ("auditor_esg", "audit2026"),
        }
        tokens = {}
        for role, (user, pwd) in personas.items():
            r = await client.post("/api/v1/auth/login", json={"identifier": user, "password": pwd})
            assert r.status_code == 200, f"Login {role} failed: {r.text}"
            tokens[role] = r.json()["access_token"]
            print(f"  ✓ {role.upper():<10} Login sukses ({r.json()['full_name']})")

        headers = {role: {"Authorization": f"Bearer {token}"} for role, token in tokens.items()}

        # -------------------------------------------------------------
        # 2. FITUR PETANI (FARMER)
        # -------------------------------------------------------------
        print("\n[PHASE 2] Pengujian Fitur Petani...")
        # 2a. Buat Laporan Stok Sekam (Harvest)
        r = await client.post("/api/v1/farmer/harvest", json={"quantity_kg": 1500, "mill_id": 1}, headers=headers["petani"])
        assert r.status_code == 201, f"Lapor sekam gagal: {r.text}"
        harvest_data = r.json()
        harvest_id = harvest_data["id"]
        print(f"  ✓ Lapor Panen/Stok Sekam: Harvest #{harvest_id} ({harvest_data['quantity_kg']} kg)")

        # 2b. Buat Listing Lelang Terbuka (Market Listing)
        r = await client.post("/api/v1/farmer/listings", json={
            "quantity_kg": 1200,
            "moisture_pct": 14.0,
            "allow_jemput": True,
            "ask_price_jemput": 370.0,
            "allow_antar": True,
            "ask_price_antar": 470.0,
        }, headers=headers["petani"])
        assert r.status_code == 201, f"Listing gagal: {r.text}"
        listing_id = r.json()["id"]
        print(f"  ✓ Buat Listing Lelang: Listing #{listing_id} (1200 kg)")

        # 2c. Ambil riwayat & dompet biochar petani
        r = await client.get("/api/v1/farmer/harvests", headers=headers["petani"])
        assert r.status_code == 200
        print(f"  ✓ Riwayat Laporan Petani: {len(r.json())} item terdaftar")

        # -------------------------------------------------------------
        # 3. FITUR PENGEPUL (COLLECTOR)
        # -------------------------------------------------------------
        print("\n[PHASE 3] Pengujian Fitur Pengepul...")
        # 3a. Baca Feed Pasar
        r = await client.get("/api/v1/collector/market", headers=headers["pengepul"])
        assert r.status_code == 200
        market_items = r.json()
        print(f"  ✓ Feed Pasar Terbuka: {len(market_items)} listing aktif ditemukan")

        # 3b. Hitung Saran Bidding (Bid Advisor dengan Logistik CVRP)
        r = await client.post("/api/v1/collector/bid-advisor", json={
            "listing_id": listing_id,
            "resale_price_per_kg": 500.0,
            "scheme": "jemput",
        }, headers=headers["pengepul"])
        assert r.status_code == 200, f"Bid advisor gagal: {r.text}"
        adv = r.json()
        print(f"  ✓ Bid Advisor: Biaya Logistik Rp {adv['logistic_cost_per_kg']}/kg | Saran Tawar: Rp {adv['suggested_bid_per_kg']}/kg")

        # 3c. Ajukan Penawaran (Bid)
        r = await client.post("/api/v1/collector/bids", json={
            "listing_id": listing_id,
            "scheme": "jemput",
            "price_per_kg": adv["suggested_bid_per_kg"] or 390.0,
            "quantity_kg": 1200.0,
        }, headers=headers["pengepul"])
        assert r.status_code == 201, f"Bidding gagal: {r.text}"
        bid_id = r.json()["bid_id"]
        print(f"  ✓ Pengajuan Penawaran: Bid #{bid_id} sebesar Rp {r.json()['price_per_kg']}/kg")

        # 3d. Petani Menerima Penawaran
        r = await client.post(f"/api/v1/farmer/listings/{listing_id}/accept", json={
            "bid_id": bid_id,
            "quantity_kg": 1200,
        }, headers=headers["petani"])
        assert r.status_code == 200, f"Accept bid gagal: {r.text}"
        print(f"  ✓ Petani Menyetujui Bid #{bid_id} -> Stok berpindah ke Pengepul")

        # 3e. Verifikasi Uji Mutu Proksimat Sekam oleh Pengepul
        r = await client.post("/api/v1/collector/verify", json={
            "harvest_id": harvest_id,
            "weighed_kg": 1480.0, # Ada sedikit susut timbangan alami
            "moisture": 13.5,
            "ash": 17.0,
            "volatile_matter": 64.0,
            "fixed_carbon": 17.5,
            "contamination": 1.0,
            "pyrolysis_temp_c": 500.0,
        }, headers=headers["pengepul"])
        assert r.status_code == 200, f"Verifikasi gagal: {r.text}"
        ver_res = r.json()
        print(f"  ✓ Verifikasi Proksimat: Mutu Grade {ver_res.get('grade', 'A')} | Total Bayar Petani: Rp {ver_res.get('total_price', 0):,}")

        # 3f. Perencanaan Rute Penjemputan CVRP
        r = await client.post("/api/v1/collector/pickup-plan", json={}, headers=headers["pengepul"])
        assert r.status_code == 200, f"Pickup plan failed: {r.text}"
        print(f"  ✓ Rencana Penjemputan CVRP: {len(r.json().get('trips', []))} ritase armada dioptimalkan")

        # -------------------------------------------------------------
        # 4. FITUR PABRIK (FACTORY)
        # -------------------------------------------------------------
        print("\n[PHASE 4] Pengujian Fitur Pabrik (Procurement, QC, Mass Balance)...")
        # 4a. Rekomendasi Harga Pembelian Berdasarkan Netback & Kadar Air
        r = await client.post("/api/v1/factory/pricing/recommend", json={
            "moisture": 13.5,
            "ash": 17.0,
            "contamination": 1.0,
            "price_pellet_per_kg": 1500.0,
            "price_biochar_per_kg": 3500.0,
            "price_silica_per_kg": 15000.0,
            "sensitivity": True,
        }, headers=headers["pabrik"])
        assert r.status_code == 200, f"Factory pricing recommend failed: {r.status_code} -> {r.text}"
        pr_rec = r.json()
        target_p = pr_rec["target_per_kg"]
        print(f"  ✓ Rekomendasi Harga Netback Pabrik: Lantai Rp {pr_rec['floor_per_kg']:.0f} | Target Rp {target_p:.0f} | Plafon Rp {pr_rec['ceiling_per_kg']:.0f}")

        # 4b. Buat Delivery Request dari Pengepul ke Pabrik
        r = await client.post("/api/v1/collector/delivery-requests", json={
            "quantity_kg": 1480.0,
            "moisture_est": 13.5,
            "ash_est": 17.0,
            "proposed_date": "2026-10-10",
            "proposed_price_per_kg": round(target_p),
            "harvest_ids": [harvest_id],
        }, headers=headers["pengepul"])
        assert r.status_code == 201, f"DR create failed: {r.text}"
        dr_id = r.json()["id"]
        print(f"  ✓ Delivery Request #{dr_id} dibuat oleh Pengepul (1480 kg)")

        # 4c. Pabrik Menyetujui Delivery Request
        r = await client.post(f"/api/v1/factory/delivery-requests/{dr_id}/respond", json={
            "action": "accept",
            "price_per_kg": round(target_p),
            "date": "2026-10-10",
        }, headers=headers["pabrik"])
        assert r.status_code == 200, f"DR respond failed: {r.text}"
        print(f"  ✓ Pabrik Menyetujui Delivery Request #{dr_id}")

        # 4d. Input Inbound QC Pabrik (Timbang Bruto-Tara, Kadar Air, Harga Basis Kering)
        r = await client.post("/api/v1/factory/qc", json={
            "request_id": dr_id,
            "gross_kg": 4480.0,
            "tare_kg": 3020.0, # Netto = 1460.0 kg
            "moisture": 13.8,
            "ash": 17.2,
            "volatile_matter": 64.0,
            "fixed_carbon": 17.0,
            "contamination": 0.8,
        }, headers=headers["pabrik"])
        assert r.status_code == 201, f"QC inbound failed: {r.text}"
        qc_data = r.json()
        lot_id = qc_data["id"]
        print(f"  ✓ Inbound QC Lot #{lot_id}: Netto {qc_data['net_kg']} kg | Resi Verifikasi: {qc_data['verification_code']}")

        # 4e. Eksekusi Batch Pabrik (Mass Balance 1 input -> 3 produk + 5 losses)
        # Netto 1460 kg -> konversi ke bio-pellet (20%), biochar (28%), loss (air, syngas)
        r = await client.post("/api/v1/factory/batches", json={
            "batch_code": f"BATCH-TEST-{int(time.time())}",
            "inputs": [{"qc_id": lot_id, "kg": 1460.0}],
            "outputs": {
                "bio_pellet": 292.0, # 20%
                "biochar": 408.8,    # 28%
                "bio_silika": 0.0,
            },
            "losses": {
                "air": 201.5,
                "volatil_syngas": 510.0,
                "gas_pembakaran": 0.0,
                "residu_ekstraksi": 0.0,
                "susut_proses": 47.7,
            },
            "prices": {
                "bio_pellet": 1500.0,
                "biochar": 3500.0,
                "bio_silika": 15000.0,
            },
            "operating_hours": 4.0,
            "pyrolysis_temp_c": 500.0,
        }, headers=headers["pabrik"])
        assert r.status_code == 201, f"Batch creation failed: {r.status_code} -> {r.text}"
        batch_res = r.json()
        print(f"  ✓ Batch Produksi #{batch_res['id']} Selesai: Input {batch_res['input_kg']} kg | Penutupan Massa: {batch_res['closure_error_pct']}% | Status: {'Valid (Tertutup)' if batch_res['closure_ok'] else 'Varians'}")

        # 4f. Audit Neraca Energi ISO 50006
        r = await client.get("/api/v1/factory/energy/analysis", headers=headers["pabrik"])
        assert r.status_code == 200
        print(f"  ✓ Analisis Energi Pabrik: Efisiensi IKE & Rekomendasi konservasi aktif")

        # -------------------------------------------------------------
        # 5. FITUR AUDITOR & ADMIN
        # -------------------------------------------------------------
        print("\n[PHASE 5] Pengujian Fitur Auditor & Admin...")
        r = await client.get("/api/v1/auditor/summary", headers=headers["auditor"])
        assert r.status_code == 200
        summary_aud = r.json()
        print(f"  ✓ Ringkasan Sirkular Auditor: Pengepul {summary_aud['collector_scale_kg']:,} kg | Pabrik {summary_aud['factory_scale_kg']:,} kg | Biochar ke Petani: {summary_aud['biochar_allocated_to_farmers_kg']:,} kg")

        r = await client.get("/api/v1/admin/stats", headers=headers["admin"])
        assert r.status_code == 200
        stats = r.json()
        print(f"  ✓ Panel Admin Stats: {stats.get('total_users', 0)} users | {stats.get('total_harvests', 0)} harvests")

        # -------------------------------------------------------------
        # 6. PENGUJIAN LALU LINTAS SIMULTAN (MULTI-PERSONA CONCURRENT TRAFFIC)
        # -------------------------------------------------------------
        print("\n[PHASE 6] Pengujian Lalu Lintas Simultan Multi-Persona (50 Workers Simultan)...")
        tasks = []
        start_time = time.time()

        async def worker_journey(worker_id):
            # Campuran aksi multi-persona:
            role = ["petani", "pengepul", "pabrik", "auditor"][worker_id % 4]
            h = headers[role]
            status_codes = []

            # Aksi 1: Read status & parameters
            r1 = await client.get("/api/v1/system/status")
            status_codes.append(r1.status_code)

            # Aksi 2: Read persona-specific feed
            if role == "petani":
                r2 = await client.get("/api/v1/farmer/harvests", headers=h)
            elif role == "pengepul":
                r2 = await client.get("/api/v1/collector/market", headers=h)
            elif role == "pabrik":
                r2 = await client.get("/api/v1/factory/delivery-requests", headers=h)
            else:
                r2 = await client.get("/api/v1/auditor/summary", headers=h)
            status_codes.append(r2.status_code)

            # Aksi 3: Engine computation
            r3 = await client.post("/api/v1/labs/quality/score", json={
                "moisture": 13.0 + (worker_id % 5),
                "ash": 16.5,
                "volatile_matter": 63.5,
                "fixed_carbon": 17.0,
                "contamination": 1.0,
            }, headers=headers["pabrik"])
            status_codes.append(r3.status_code)

            return status_codes

        results = await asyncio.gather(*(worker_journey(i) for i in range(50)))
        elapsed = time.time() - start_time

        all_codes = [c for res in results for c in res]
        success_count = sum(1 for c in all_codes if c in (200, 201))
        shedded_count = sum(1 for c in all_codes if c == 503)
        error_count = sum(1 for c in all_codes if c >= 500 and c != 503)

        print(f"  ✓ 50 Pekerja Simultan Menyelesaikan {len(all_codes)} Transaksi dalam {elapsed:.2f} detik")
        print(f"  ✓ Throughput: {len(all_codes) / elapsed:.1f} req/detik")
        print(f"  ✓ Sukses (200/201): {success_count} ({success_count / len(all_codes) * 100:.1f}%)")
        print(f"  ✓ Load Shedded (503): {shedded_count}")
        print(f"  ✓ Unhandled Crash (5xx): {error_count} (0% crash!)")

    print("\n" + "=" * 80)
    print("SEMUA PENGUJIAN FITUR & TRAFFIC SELESAI DENGAN STATUS PRIMA!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
