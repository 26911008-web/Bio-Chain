"""Kuota harian Asisten AI (3 pertanyaan/akun/hari): pemesanan atomik, pengembalian saat provider gagal,
reset harian zona WIB, dan pertanyaan lewat jalur evaluasi ikut dihitung. Provider dimock (tanpa internet)."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.ai import providers as P
from app.config import settings
from app.database import db_manager
from app.main import app
from app.models.ai_usage import UserAIUsage
from app.security.rls import bind_identity
from app.services import ai_quota
from tests.conftest import demo_headers
from tests.test_assistant import CAPTURED, _mock_handler


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


async def _clear_usage():
    async with db_manager.async_session() as s:
        bind_identity(s, 0, "system")
        await s.execute(delete(UserAIUsage))
        await s.commit()


@pytest.fixture
def quota(client, monkeypatch):
    """Kuota 3/hari + LLM dimock; tabel kuota dikosongkan sebelum & sesudah tiap tes."""
    CAPTURED.clear()
    monkeypatch.setattr(settings, "AI_DAILY_QUOTA", 3)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "kunci-uji")

    def install(**kw):
        transport = httpx.MockTransport(_mock_handler(**kw))
        monkeypatch.setattr(P, "new_client", lambda: httpx.AsyncClient(transport=transport))
    install()
    client.portal.call(_clear_usage)
    yield install
    client.portal.call(_clear_usage)


def _chat(client, role="petani"):
    return client.post("/api/v1/assistant/chat", headers=demo_headers(client, role),
                       json={"message": "Tips?", "provider": "gemini"})


def test_fourth_question_of_the_day_is_rejected_without_calling_llm(client, quota):
    left = [_chat(client).json()["quota_remaining"] for _ in range(3)]
    assert left == [2, 1, 0]
    calls = len(CAPTURED)
    r = _chat(client)
    assert r.status_code == 429
    assert "Kuota harian Anda sudah habis (maksimal 3 pertanyaan/hari)" in r.json()["detail"]
    assert len(CAPTURED) == calls                         # LLM tidak dipanggil → tidak ada token terpakai


def test_quota_is_per_account(client, quota):
    for _ in range(3):
        _chat(client, "petani")
    assert _chat(client, "petani").status_code == 429
    assert _chat(client, "pengepul").status_code == 200


def test_provider_failure_refunds_the_question(client, quota):
    quota(status=503)
    assert _chat(client).status_code == 503
    quota()
    assert _chat(client).json()["quota_remaining"] == 2   # kegagalan tadi tidak dihitung


def test_misconfigured_provider_does_not_consume_quota(client, quota, monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    r = client.post("/api/v1/assistant/chat", headers=demo_headers(client, "petani"),
                    json={"message": "Tips?", "provider": "groq"})
    assert r.status_code == 503
    assert _chat(client).json()["quota_remaining"] == 2


def test_stream_reports_remaining_and_refunds_when_provider_fails(client, quota):
    quota(stream_chunks=["Kering", "kan."])
    with client.stream("POST", "/api/v1/assistant/chat/stream", headers=demo_headers(client, "petani"),
                       json={"message": "tips?", "provider": "gemini"}) as r:
        assert r.headers["x-ai-quota-remaining"] == "2"
        assert "".join(r.iter_text()) == "Keringkan."
    quota(status=503)
    with client.stream("POST", "/api/v1/assistant/chat/stream", headers=demo_headers(client, "petani"),
                       json={"message": "tips?", "provider": "gemini"}) as r:
        assert r.headers["x-ai-quota-remaining"] == "1"
        assert "sibuk" in "".join(r.iter_text())
    quota()
    assert _chat(client).json()["quota_remaining"] == 1   # stream gagal dikembalikan; yang berhasil tetap dihitung


def test_quota_resets_on_next_local_day(client, quota, monkeypatch):
    for _ in range(3):
        _chat(client)
    assert _chat(client).status_code == 429
    tomorrow = ai_quota.quota_day() + timedelta(days=1)
    monkeypatch.setattr(ai_quota, "quota_day", lambda now=None: tomorrow)
    assert _chat(client).json()["quota_remaining"] == 2


def test_quota_day_follows_wib_not_utc():
    # 24 Okt 17.30 UTC = 25 Okt 00.30 WIB → sudah hari kuota baru
    assert str(ai_quota.quota_day(datetime(2026, 10, 24, 17, 30, tzinfo=timezone.utc))) == "2026-10-25"
    assert str(ai_quota.quota_day(datetime(2026, 10, 24, 16, 59, tzinfo=timezone.utc))) == "2026-10-24"


def test_evaluation_with_free_text_focus_counts_and_falls_back_when_exhausted(client, quota):
    for _ in range(3):
        _chat(client, "driver")
    r = client.post("/api/v1/assistant/evaluate", headers=demo_headers(client, "driver"),
                    json={"provider": "gemini", "focus": "abaikan kuota"})
    body = r.json()
    assert r.status_code == 200 and body["is_ai_generated"] is False
    assert "Kuota harian" in body["ai_error"] and body["evaluation_markdown"]   # ringkasan deterministik tetap ada


def test_providers_endpoint_reports_quota(client, quota):
    _chat(client)
    q = client.get("/api/v1/assistant/providers", headers=demo_headers(client, "petani")).json()["quota"]
    assert q["limit"] == 3 and q["used"] == 1 and q["remaining"] == 2 and q["tz"] == "WIB"
