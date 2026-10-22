"""F14 — QR lot bertanda tangan HMAC, cek offline di HP supir, dan masa transisi QR lama yang sudah tercetak."""
import hashlib

from sqlalchemy import select, update

from app import params
from app.models.harvest import Harvest
from app.models.ledger import CustodyEvent
from app.services import qr_sign
from tests.test_field_ops import dispatched, env, pickup, verified  # noqa: F401  (fixture env)


def test_new_code_is_signed_and_tamper_evident():
    code = qr_sign.new_qr_code("1a2b3c4d-0000-0000-0000-000000000000")
    assert qr_sign.is_signed(code) and code.startswith("BIO-1A2B3C4D-")
    assert qr_sign.signature_valid(code) and qr_sign.signature_valid(" " + code.lower() + " ")   # input manual
    forged = code[:-1] + ("A" if code[-1] != "A" else "B")
    assert not qr_sign.signature_valid(forged)
    assert qr_sign.check_scan(forged, code) == "tidak_sah"
    assert qr_sign.check_scan(code, code) == "ok"
    assert qr_sign.check_scan("BIO-1A2B3C4D", "BIO-1A2B3C4D") == "ok_legacy"
    assert qr_sign.check_scan(qr_sign.new_qr_code(), code) == "beda_lot"


def test_harvest_gets_signed_qr_and_route_carries_offline_digest(env):
    h = verified(env)
    assert qr_sign.signature_valid(h["qr_code"])
    dispatched(env, [h])
    route = env.ok("supir", "GET", "/driver/active-route")
    stop = route["stops"][0]
    assert "qr_code" not in stop and h["qr_code"] not in str(route)              # kode tidak bocor ke supir
    chk = stop["qr_check"]
    assert hashlib.sha256((chk["salt"] + h["qr_code"]).encode()).hexdigest() == chk["sha256"]


def test_forged_or_mistyped_qr_rejected_with_clear_message(env):
    h = verified(env)
    r = dispatched(env, [h])
    bad = h["qr_code"][:-1] + ("A" if h["qr_code"][-1] != "A" else "B")
    res = env.call("supir", "POST", "/driver/confirm-pickup",
                   {"route_stop_id": r["stops"][0]["route_stop_id"], "qr_code": bad, "actual_ton": 1.0})
    assert res.status_code == 400 and "tidak sah" in res.json()["detail"]
    pickup(env, r, 0, h)                                                          # QR asli tetap bisa


def _make_legacy(env, hid):
    async def go(s):
        await s.execute(update(Harvest).where(Harvest.id == hid).values(qr_code=f"BIO-OLD{hid:05d}"))
        await s.commit()
    env.q(go)
    return f"BIO-OLD{hid:05d}"


def test_printed_legacy_qr_accepted_but_flagged_for_auditor(env):
    h = verified(env)
    legacy = _make_legacy(env, h["id"])
    r = dispatched(env, [h])
    route = env.ok("supir", "GET", "/driver/active-route")
    assert route["stops"][0]["qr_check"] is None                                  # 32 bit: tanpa digest offline
    pickup(env, r, 0, {**h, "qr_code": legacy})
    notes = env.q(lambda s: s.execute(select(CustodyEvent.note).where(CustodyEvent.harvest_id == h["id"])))
    assert any(n and "QR_LAMA" in n for n in notes.scalars())


def test_legacy_qr_refused_after_transition_ends(env):
    h = verified(env)
    legacy = _make_legacy(env, h["id"])
    r = dispatched(env, [h])
    params._values["logistik.qr_legacy_policy"] = "tolak"
    res = env.call("supir", "POST", "/driver/confirm-pickup",
                   {"route_stop_id": r["stops"][0]["route_stop_id"], "qr_code": legacy, "actual_ton": 1.0})
    assert res.status_code == 400 and "QR lama" in res.json()["detail"]
