"""Suite Pengujian Otomatis Fase 5: Chaos Concurrency, Offline Refraction, Blending Slagging, & Ash Verification.

Konsorsium Ahli: Lead Supabase Security SRE, Principal Thermochemical Process Engineer, & Systems Architect.
Mencakup 4 Uji Wajib:
1. Uji Penawaran Serentak: 20 permintaan bidding paralel pada stok yang sama untuk menguji keandalan RPC lock.
2. Uji Konflik Offline & Refraksi: Rekonsiliasi data supir offline terhadap timbangan pabrik (single source of truth) dengan pemotongan refraksi kadar air otomatis.
3. Uji Keamanan Kimia Blending: Deteksi otomatis bahaya terak boiler jika campuran melebihi batas indeks alkali (AI > 0.34 kg/GJ) atau B/A tinggi.
4. Uji Verifikasi Abu: Validasi alokasi abu sisa bakar yang melampaui ambang logam berat (Pb < 50 ppm, Cd < 2 ppm, As < 10 ppm) langsung diblokir dari distribusi Poktan.
"""

import asyncio
import uuid
import pytest
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.engines.fuel_blend import evaluate, BlendFeed
from app.engines.refraction import refract
from tests.test_field_ops import PROX, env  # noqa: F401


# -----------------------------------------------------------------------------
# 1. UJI PENAWARAN SERENTAK (20 PERMINTAAN BIDDING PARALEL)
# -----------------------------------------------------------------------------
def test_twenty_concurrent_bids_rpc_lock(env):
    """Menguji 20 permintaan bidding & accept simultan pada listing stok 1.000 kg.
    Membuktikan tidak ada double-allocation, sisa stok tidak negatif, dan atomicity terjaga."""
    # Petani membuka listing stok 1000 kg sekam
    lst = env.ok(
        "petani", "POST", "/farmer/listings",
        {"quantity_kg": 1000.0, "commodity": "sekam_padi", "allow_jemput": True, "ask_price_jemput": 400.0},
        status=201
    )
    listing_id = lst["id"]

    # 20 bidding simultan dari pengepul berbeda/bergantian
    # Kita buat 20 panggilan paralel menawar porsi 200 kg
    async def run_concurrent():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=30) as client:
            headers = env.headers["pengepul"]
            tasks = [
                client.post(
                    "/api/v1/collector/bids",
                    json={"listing_id": listing_id, "scheme": "jemput", "price_per_kg": 410.0 + i, "quantity_kg": 200.0},
                    headers=headers
                )
                for i in range(20)
            ]
            return await asyncio.gather(*tasks)

    responses = asyncio.run(run_concurrent())
    # Semua request harus tertangani secara aman tanpa 500 internal server error
    assert all(r.status_code in (200, 201, 409) for r in responses)

    # Ambil tawaran aktif yang masuk
    bids = env.ok("petani", "GET", f"/farmer/listings/{listing_id}/bids")["bids"]
    assert len(bids) >= 1

    # Sekarang uji 20 accept bersamaan dari petani terhadap sisa stok
    bid_id = bids[0]["bid_id"]
    async def run_concurrent_accepts():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=30) as client:
            headers = env.headers["petani"]
            tasks = [
                client.post(
                    f"/api/v1/farmer/listings/{listing_id}/accept",
                    json={"bid_id": bid_id, "quantity_kg": 200.0},
                    headers=headers
                )
                for _ in range(20)
            ]
            return await asyncio.gather(*tasks)

    accept_responses = asyncio.run(run_concurrent_accepts())
    accepted = [r.json() for r in accept_responses if r.status_code in (200, 201)]
    # Akumulasi yang diterima tidak boleh melebihi kapasitas stok 1.000 kg
    total_awarded = sum(a.get("accepted_kg", a.get("quantity_kg", 200.0)) for a in accepted)
    assert total_awarded <= 1000.0 + 1e-6
    # Sisanya harus mendapatkan penolakan conflict 409
    assert any(r.status_code == 409 for r in accept_responses)


# -----------------------------------------------------------------------------
# 2. UJI KONFLIK OFFLINE & REFRAKSI (WEIGHBRIDGE SINGLE SOURCE OF TRUTH)
# -----------------------------------------------------------------------------
def test_offline_conflict_and_moisture_refraction_reconciliation(env):
    """Simulasi supir menginput muatan offline (mis. 5.000 kg), lalu tiba di pabrik
    dan ditimbang jembatan timbang (4.800 kg aktual, MC 16% vs acuan kontrak 12%).
    Sistem wajib memotong berat refraksi otomatis dan mengunci timbangan pabrik sebagai acuan mutlak."""
    # Data pengujian refraksi matematis:
    # Gross: 4.800 kg, MC Aktual: 16%, MC Acuan: 12%, Toleransi Kontaminan: 2%, Kontaminan Terukur: 2%
    # Rumus: Dry basis setara = Gross * (100 - MC_aktual) / (100 - MC_acuan)
    # Refraksi berat = Gross - Payable
    refr = refract(
        gross_kg=4800.0, moisture_pct=16.0, contaminant_pct=2.0,
        moisture_ref_pct=12.0, moisture_reject_pct=20.0, contaminant_tol_pct=2.0
    )
    expected_payable = 4800.0 * (1.0 - 0.16) / (1.0 - 0.12)  # 4.800 * 0.84 / 0.88 = 4581.81 kg
    assert abs(refr["payable_kg"] - expected_payable) < 1.0
    assert refr["refraction_kg"] > 0.0

    # Simulasi pengiriman muatan ke pabrik dengan kadar air tinggi
    req = env.ok("pengepul", "POST", "/collector/delivery-requests", {
        "quantity_kg": 4800.0, "moisture_est": 12.0, "proposed_date": "2026-10-20",
        "proposed_price_per_kg": 450.0
    }, status=201)
    env.ok("pabrik", "POST", f"/factory/delivery-requests/{req['id']}/respond", {"action": "accept"})

    # Timbangan jembatan pabrik (Inbound QC) memasukkan data timbangan riil 4.800 kg dengan MC 16%
    qc = env.ok("pabrik", "POST", "/factory/qc", {
        "request_id": req["id"], "gross_kg": 5800.0, "tare_kg": 1000.0, "moisture": 16.0,
        "ash": 17.5, "volatile_matter": 66.0, "fixed_carbon": 16.5, "contamination": 2.0
    }, status=201)

    assert qc["decision"] in ("terima", "terima_potongan")
    assert qc["refraction_kg"] > 0
    assert qc["payable_kg"] < 4800.0
    # Hak bayar pengepul berbasis berat bersih setelah refraksi
    assert qc["total_payment_rp"] == round(qc["payable_kg"] * qc["final_price_per_kg"])


# -----------------------------------------------------------------------------
# 3. UJI KEAMANAN KIMIA BLENDING (PROTEKSI TERAK BOILER & INDEKS ALKALI)
# -----------------------------------------------------------------------------
def test_chemical_blending_slagging_danger_alert(env):
    """Verifikasi bahwa biomassa berkadar alkali tinggi (mis. tongkol jagung murni 100% K2O 35%)
    secara deterministik memicu status BAHAYA dan ditolak oleh parameter boiler aman (AI > 0.34 kg/GJ)."""
    corn_feed = BlendFeed(
        code="tongkol_jagung", name="Tongkol Jagung", available_kg=10000.0, price_per_kg=600.0,
        moisture_pct=13.0, ash_pct_db=2.2, lhv_db_mj_kg=17.5, hhv_db_mj_kg=18.5,
        sio2_pct_ash=32.0, k2o_pct_ash=35.0, na2o_pct_ash=1.5, cao_pct_ash=6.0,
        chlorine_pct_db=0.15, sulfur_pct_db=0.05
    )
    wood_feed = BlendFeed(
        code="serbuk_sengon", name="Serbuk Sengon", available_kg=10000.0, price_per_kg=450.0,
        moisture_pct=15.0, ash_pct_db=1.2, lhv_db_mj_kg=18.5, hhv_db_mj_kg=19.5,
        sio2_pct_ash=20.0, k2o_pct_ash=12.0, na2o_pct_ash=1.5, cao_pct_ash=32.0,
        chlorine_pct_db=0.02, sulfur_pct_db=0.03
    )

    # Evaluasi 100% Tongkol Jagung murni: K2O tinggi memicu eutektik silika-kalium
    eval_dangerous = evaluate([corn_feed, wood_feed], [100.0, 0.0], product_moisture_pct=10.0)
    assert eval_dangerous["slagging_verdict"] == "BAHAYA"
    assert eval_dangerous["indices"]["alkali_index"] > 0.34
    assert any("Risiko Tinggi Terak/Slagging" in w for w in eval_dangerous["warnings"])

    # Evaluasi Pencampuran Aman (Blending 30% Tongkol + 70% Serbuk Kayu):
    eval_safe = evaluate([corn_feed, wood_feed], [30.0, 70.0], product_moisture_pct=10.0)
    assert eval_safe["slagging_verdict"] in ("AMAN", "WASPADA")
    assert eval_safe["indices"]["alkali_index"] <= 0.34 + 0.05


# -----------------------------------------------------------------------------
# 4. UJI VERIFIKASI ABU (AMBANG LOGAM BERAT & PEMBLOKIRAN DISTRIBUSI POKTAN)
# -----------------------------------------------------------------------------
def test_ash_heavy_metals_safety_gate(env):
    """Validasi gerbang keamanan pangan & tanah: Abu sisa pembakaran yang melebihi ambang
    logam berat (Kepmentan 261/2019: Pb < 50 ppm, Cd < 2 ppm, As < 10 ppm) wajib berstatus 'gagal'
    dan DITOLAK saat dialokasikan ke Poktan tani."""
    # Buat Poktan penerima
    group = env.ok("pabrik", "POST", "/factory/farmer-groups", {
        "name": "Poktan Ngudi Makmur", "kecamatan": "Seyegan", "kabupaten": "Sleman",
        "leader_name": "Pak Mulyono", "leader_user_id": env.uid["petani"]
    }, status=201)

    # 1. Kasus Abu Terkontaminasi Kadmium Tinggi (Cd = 4.5 ppm > batas 2 ppm)
    bad_ash = env.ok("pabrik", "POST", "/factory/ash", {
        "ash_type": "fly_ash", "source_commodity": "sekam_padi", "quantity_kg": 500.0
    }, status=201)

    lab_bad = env.ok("pabrik", "POST", f"/factory/ash/{bad_ash['id']}/lab", {
        "pb_ppm": 12.0, "cd_ppm": 4.5, "as_ppm": 2.1, "hg_ppm": 0.01,
        "lab_report_no": "LAB-TOXIC-CD-2026"
    })
    assert lab_bad["heavy_metal_status"] == "gagal"

    # Verifikasi sistem MENOLAK alokasi abu gagal ke Poktan (HTTP 409 Conflict)
    alloc_fail = env.call("pabrik", "POST", f"/factory/ash/{bad_ash['id']}/allocate", {
        "farmer_group_id": group["id"]
    })
    assert alloc_fail.status_code == 409

    # 2. Kasus Abu Bersih & Lulus Uji Lab (Pb = 8 ppm, Cd = 0.4 ppm, As = 1.2 ppm)
    clean_ash = env.ok("pabrik", "POST", "/factory/ash", {
        "ash_type": "silica_ash", "source_commodity": "sekam_padi", "quantity_kg": 600.0
    }, status=201)

    lab_clean = env.ok("pabrik", "POST", f"/factory/ash/{clean_ash['id']}/lab", {
        "pb_ppm": 8.0, "cd_ppm": 0.4, "as_ppm": 1.2, "hg_ppm": 0.01,
        "lab_report_no": "LAB-CLEAN-OK-2026"
    })
    assert lab_clean["heavy_metal_status"] == "lulus"

    # Alokasi abu bersih ke Poktan berhasil
    alloc_ok = env.ok("pabrik", "POST", f"/factory/ash/{clean_ash['id']}/allocate", {
        "farmer_group_id": group["id"]
    })
    assert alloc_ok["status"] == "dialokasikan"
    assert alloc_ok["farmer_group_id"] == group["id"]
