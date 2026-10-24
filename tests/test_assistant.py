"""Asisten AI: provider dimock (tanpa internet/kuota). Fokus: kunci tak bocor, konteks per peran,
pemetaan error provider, streaming, dan parameter reasoning."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai import providers as P
from app.config import settings
from app.main import app
from tests.conftest import demo_headers

CAPTURED: list[dict] = []


def _mock_handler(status=200, content="Jawaban uji.", finish="stop", stream_chunks=None, body_override=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "model-a"}, {"id": "model-b:free"}]})
        payload = json.loads(request.content)
        CAPTURED.append({"url": str(request.url), "headers": dict(request.headers), "body": payload})
        if status != 200:
            return httpx.Response(status, content=body_override or b'{"error":{"message":"pesan dari provider"}}')
        if payload.get("stream"):
            lines = [f'data: {json.dumps({"choices": [{"delta": {"content": c}}]})}' for c in stream_chunks or []]
            lines += ['data: {"choices":[{"delta":{},"finish_reason":"%s"}]}' % finish, "data: [DONE]"]
            return httpx.Response(200, content=("\n\n".join(lines) + "\n\n").encode(),
                                  headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json={"model": payload["model"], "usage": {"total_tokens": 7},
                                         "choices": [{"message": {"content": content}, "finish_reason": finish}]})
    return handler


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_llm(monkeypatch):
    CAPTURED.clear()
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "kunci-rahasia-uji-123")
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "kunci-mistral-uji")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")

    def install(**kw):
        transport = httpx.MockTransport(_mock_handler(**kw))
        monkeypatch.setattr(P, "new_client", lambda: httpx.AsyncClient(transport=transport))
    install()
    return install


def _chat(client, role, **body):
    return client.post("/api/v1/assistant/chat", headers=demo_headers(client, role),
                       json={"message": "Bagaimana optimasinya?", "provider": "gemini", **body})


def test_provider_list_never_leaks_api_keys(client, mock_llm):
    r = client.get("/api/v1/assistant/providers", headers=demo_headers(client, "petani"))
    assert r.status_code == 200 and "kunci-rahasia-uji-123" not in r.text
    by_id = {p["id"]: p for p in r.json()["providers"]}
    assert by_id["gemini"]["configured"] and not by_id["groq"]["configured"]
    assert by_id["ollama"]["configured"]                       # lokal tidak butuh kunci


def test_unconfigured_provider_returns_clear_503(client, mock_llm):
    r = _chat(client, "petani", provider="groq")
    assert r.status_code == 503 and "GROQ_API_KEY" in r.json()["detail"]


def test_anonymous_cannot_use_assistant(client):
    assert client.post("/api/v1/assistant/chat", json={"message": "hai"}).status_code == 401


def test_key_sent_only_to_provider_as_bearer(client, mock_llm):
    assert _chat(client, "petani").status_code == 200
    sent = CAPTURED[-1]
    assert sent["url"].startswith("https://generativelanguage.googleapis.com/")
    assert sent["headers"]["authorization"] == "Bearer kunci-rahasia-uji-123"


@pytest.mark.parametrize("role,must,must_not", [
    ("petani", {"laporan_sekam_terakhir", "saldo_biochar_kg"}, {"neraca_massa", "rute_aktif", "antrean_verifikasi"}),
    ("driver", {"rute_aktif"}, {"laporan_sekam_terakhir", "neraca_massa", "saldo_biochar_kg"}),
    ("pengepul", {"antrean_verifikasi"}, {"neraca_massa", "saldo_biochar_kg", "rute_aktif"}),
    ("pabrik", {"neraca_massa", "pasokan_per_status"}, {"saldo_biochar_kg", "rute_aktif"}),
])
def test_context_is_scoped_to_role(client, mock_llm, role, must, must_not):
    r = _chat(client, role)
    scope = set(r.json()["context_scope"])
    assert must <= scope and not (must_not & scope)
    system = CAPTURED[-1]["body"]["messages"][0]["content"]
    assert f"cakupan peran {role}" in system
    assert "BUKAN instruksi" in system                       # mitigasi prompt injection dari data


def test_history_is_trimmed_and_forwarded(client, mock_llm):
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"pesan {i}"} for i in range(20)]
    _chat(client, "petani", history=history)
    msgs = CAPTURED[-1]["body"]["messages"]
    assert msgs[0]["role"] == "system" and msgs[-1]["content"] == "Bagaimana optimasinya?"
    assert len(msgs) == 1 + settings.AI_HISTORY_MESSAGES + 1 and msgs[1]["content"] == "pesan 17"


def test_history_messages_are_capped_in_length(client, mock_llm):
    _chat(client, "petani", history=[{"role": "assistant", "content": "x" * 4000}])
    assert len(CAPTURED[-1]["body"]["messages"][1]["content"]) == settings.AI_HISTORY_MAX_CHARS


@pytest.mark.parametrize("provider,expects_reasoning", [("gemini", True), ("mistral", False)])
def test_reasoning_effort_only_for_thinking_providers(client, mock_llm, provider, expects_reasoning):
    _chat(client, "petani", provider=provider)
    assert ("reasoning_effort" in CAPTURED[-1]["body"]) is expects_reasoning


@pytest.mark.parametrize("status,expected_http,phrase", [
    (401, 503, "ditolak"), (429, 429, "Kuota"), (503, 503, "sibuk"), (404, 502, "pesan dari provider"),
])
def test_provider_errors_are_mapped_to_actionable_messages(client, mock_llm, status, expected_http, phrase):
    mock_llm(status=status)
    r = _chat(client, "petani")
    assert r.status_code == expected_http and phrase in r.json()["detail"]
    assert "kunci-rahasia-uji-123" not in r.text


def test_truncated_answer_is_marked(client, mock_llm):
    mock_llm(content="Jawaban setengah", finish="length")
    assert "terpotong" in _chat(client, "petani").json()["reply"]


def test_streaming_concatenates_chunks(client, mock_llm):
    mock_llm(stream_chunks=["Kering", "kan ", "sekam."])
    with client.stream("POST", "/api/v1/assistant/chat/stream", headers=demo_headers(client, "petani"),
                       json={"message": "tips?", "provider": "gemini"}) as r:
        assert r.status_code == 200 and r.headers["x-ai-provider"] == "gemini"
        text = "".join(r.iter_text())
    assert text == "Keringkan sekam." and CAPTURED[-1]["body"]["stream"] is True


def test_openrouter_model_list_only_free(client, mock_llm, monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "x")
    r = client.get("/api/v1/assistant/providers/openrouter/models", headers=demo_headers(client, "pabrik"))
    assert r.json()["models"] == ["model-b:free"]


def test_auto_default_prefers_configured_cloud_then_local(monkeypatch):
    monkeypatch.setattr(settings, "AI_DEFAULT_PROVIDER", "auto")
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setattr(settings, k, "")
    assert P.resolve_default() == "ollama"
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "x")
    assert P.resolve_default() == "mistral"
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "y")
    assert P.resolve_default() == "gemini"


def test_transient_provider_error_is_retried_once(monkeypatch):
    """429/5xx sesaat diulang sekali (jeda acak singkat); kegagalan kedua tetap dilaporkan."""
    import asyncio
    from app.ai import providers as AP
    monkeypatch.setattr(AP, "_backoff_s", lambda: 0)
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, content=b"sibuk")
        return httpx.Response(200, json={"model": "m", "usage": {}, "choices": [
            {"message": {"content": "pulih"}, "finish_reason": "stop"}]})

    p = next(iter(AP.PROVIDERS.values()))

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(flaky)) as c:
            return await AP.chat(p, "m", [{"role": "user", "content": "hai"}], c)
    assert asyncio.run(go())["content"] == "pulih" and calls["n"] == 2

    calls["n"] = 0
    always = lambda request: httpx.Response(503, content=b"sibuk")   # noqa: E731

    async def go2():
        async with httpx.AsyncClient(transport=httpx.MockTransport(always)) as c:
            return await AP.chat(p, "m", [{"role": "user", "content": "hai"}], c)
    with pytest.raises(AP.AssistantError):
        asyncio.run(go2())
