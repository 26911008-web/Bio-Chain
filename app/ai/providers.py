"""Provider LLM untuk Asisten Bio-Chain — semua lewat API chat-completions kompatibel OpenAI.

Satu klien generik melayani: Gemini (endpoint kompatibilitas OpenAI), Mistral, Groq, OpenRouter
(model `:free`), dan AI lokal Ollama. API key HANYA dibaca dari environment server (.env) dan
tidak pernah dikirim ke browser.
"""

from dataclasses import dataclass

import asyncio
import json
import os
import random
import ssl
import time

import httpx

from ..config import settings


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    base_url: str
    key_setting: str | None      # nama setting API key; None = tanpa key (lokal)
    model_setting: str
    note: str


PROVIDERS: dict[str, Provider] = {p.id: p for p in [
    Provider("ollama", "AI Lokal (Ollama)", "", None, "OLLAMA_MODEL",
             "Gratis & offline, data tidak keluar dari server"),
    Provider("gemini", "Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai",
             "GEMINI_API_KEY", "GEMINI_MODEL", "Tier gratis via Google AI Studio"),
    Provider("mistral", "Mistral AI", "https://api.mistral.ai/v1",
             "MISTRAL_API_KEY", "MISTRAL_MODEL", "Paket gratis 'Experiment'"),
    Provider("groq", "Groq", "https://api.groq.com/openai/v1",
             "GROQ_API_KEY", "GROQ_MODEL", "Tier gratis berbatas laju, sangat cepat"),
    Provider("openai", "OpenAI", "https://api.openai.com/v1",
             "OPENAI_API_KEY", "OPENAI_MODEL", "Berbayar per token; kunci dari platform.openai.com"),
    Provider("openrouter", "OpenRouter", "https://openrouter.ai/api/v1",
             "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "Pilih model berakhiran ':free'"),
]}


def ssl_context() -> ssl.SSLContext:
    """Trust store sistem operasi (bukan bundle certifi): lolos di jaringan dengan proxy/antivirus yang
    memeriksa HTTPS dengan root CA lokal, tanpa mematikan verifikasi sertifikat."""
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return ssl.create_default_context()


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(verify=ssl_context())


class AssistantError(Exception):
    """Kesalahan yang aman ditampilkan ke pengguna (tanpa detail kunci/respons mentah)."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def _base_url(p: Provider) -> str:
    return f"{settings.OLLAMA_BASE_URL.rstrip('/')}/v1" if p.id == "ollama" else p.base_url


def _api_key(p: Provider) -> str:
    return getattr(settings, p.key_setting, "") if p.key_setting else ""


def default_model(p: Provider) -> str:
    return getattr(settings, p.model_setting, "")


def is_configured(p: Provider) -> bool:
    return p.key_setting is None or bool(_api_key(p))


def _headers(p: Provider) -> dict:
    h = {"Content-Type": "application/json"}
    if key := _api_key(p):
        h["Authorization"] = f"Bearer {key}"
    if p.id == "openrouter":
        h["X-Title"] = "Bio-Chain Assistant"
    return h


# Urutan pilihan otomatis: cloud gratis yang sudah ada kuncinya dulu (lebih cepat & akurat daripada
# model kecil di CPU), Ollama sebagai cadangan offline.
AUTO_ORDER = ("gemini", "groq", "mistral", "openrouter", "openai", "ollama")


def resolve_default() -> str:
    if settings.AI_DEFAULT_PROVIDER != "auto":
        return settings.AI_DEFAULT_PROVIDER
    return next(pid for pid in AUTO_ORDER if is_configured(PROVIDERS[pid]))


def get_provider(provider_id: str | None) -> Provider:
    provider_id = provider_id or resolve_default()
    p = PROVIDERS.get(provider_id)
    if p is None:
        raise AssistantError(f"Provider '{provider_id}' tidak dikenal.", 422)
    if not is_configured(p):
        raise AssistantError(f"{p.label} belum dikonfigurasi: isi {p.key_setting} di file .env server.", 503)
    return p


async def list_models(p: Provider, client: httpx.AsyncClient) -> list[str]:
    """Daftar model dari provider (GET /models). Untuk OpenRouter hanya model gratis."""
    try:
        r = await client.get(f"{_base_url(p)}/models", headers=_headers(p), timeout=10)
        r.raise_for_status()
        ids = sorted(m["id"] for m in r.json().get("data", []) if "id" in m)
    except (httpx.HTTPError, ValueError, KeyError) as e:
        raise AssistantError(f"Tidak bisa mengambil daftar model {p.label}: {type(e).__name__}") from e
    if p.id == "openrouter":
        ids = [m for m in ids if m.endswith(":free")]
    if p.id == "gemini":
        ids = [m.removeprefix("models/") for m in ids if "gemini" in m]
    return ids


def _upstream_message(body: bytes | str) -> str:
    """Ambil pesan error dari provider (mis. 'model sudah tidak tersedia, gunakan X'), dipotong."""
    try:
        data = json.loads(body)
        data = data[0] if isinstance(data, list) else data
        msg = data.get("error", {}).get("message") or data.get("message") or ""
    except (ValueError, AttributeError, IndexError):
        msg = ""
    return f" — {msg[:240]}" if msg else ""


# Model "thinking" (Gemini 3.x, gpt-oss di Groq) memakai token reasoning tersembunyi dari jatah
# max_tokens; tanpa batas ini jawaban terpotong (terukur: 474 dari 600 token habis untuk reasoning).
REASONING_LOW = {"gemini", "groq"}
TRUNCATED_NOTE = "\n\n_(Jawaban terpotong karena batas panjang; minta lanjutan bila perlu.)_"


def _body(p: Provider, model: str, messages: list[dict], stream: bool) -> dict:
    body = {"model": model, "messages": messages, "temperature": 0.3, "max_tokens": settings.AI_MAX_TOKENS}
    if p.id == "openai":
        # API OpenAI terbaru: max_completion_tokens (max_tokens ditolak model reasoning) dan temperature
        # bawaan saja; token reasoning ikut jatah → beri ruang lebih & usaha reasoning rendah.
        body = {"model": model, "messages": messages, "max_completion_tokens": settings.AI_MAX_TOKENS * 3}
        if settings.OPENAI_REASONING_EFFORT:
            body["reasoning_effort"] = settings.OPENAI_REASONING_EFFORT
    elif p.id in REASONING_LOW:
        body["reasoning_effort"] = "low"
    if stream:
        body["stream"] = True
    return body


def _check_status(p: Provider, status: int, body: bytes | str = b"") -> None:
    if status in (401, 403):
        raise AssistantError(f"API key {p.label} ditolak; periksa {p.key_setting}.", 503)
    if status == 429:
        raise AssistantError(f"Kuota/batas laju gratis {p.label} habis; coba lagi nanti atau ganti provider.", 429)
    if status >= 500:
        raise AssistantError(f"Server {p.label} sedang sibuk/gangguan (HTTP {status}); coba lagi atau ganti provider.", 503)
    if status >= 400:
        raise AssistantError(f"{p.label} menolak permintaan (HTTP {status}){_upstream_message(body)}", 502)


# Batas laju / gangguan sesaat provider: ulangi SEKALI dengan jeda acak (bukan untuk 4xx lain — itu permanen)
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def _backoff_s() -> float:
    return 0.6 + random.random() * 0.6


def total_timeout_s() -> float:
    """Batas total jawaban AI (detik); 0 = tanpa batas."""
    if settings.AI_TOTAL_TIMEOUT_S > 0:
        return settings.AI_TOTAL_TIMEOUT_S
    return 50.0 if os.getenv("VERCEL") else 0.0


async def chat_stream(p: Provider, model: str, messages: list[dict], client: httpx.AsyncClient):
    """Streaming (SSE kompatibel OpenAI): yield potongan teks segera setelah dihasilkan.
    Timeout dihitung per potongan, sehingga jawaban panjang dari model lokal tetap lolos."""
    if not model:
        raise AssistantError(f"Pilih model untuk {p.label} (atau isi {p.model_setting} di .env).", 422)
    body = _body(p, model, messages, stream=True)
    timeout = httpx.Timeout(connect=10, read=settings.AI_TIMEOUT_S, write=10, pool=10)
    deadline = time.monotonic() + total_timeout_s() if total_timeout_s() else None
    for attempt in (1, 2):
        try:
            async with client.stream("POST", f"{_base_url(p)}/chat/completions", headers=_headers(p),
                                     json=body, timeout=timeout) as r:
                if r.status_code in RETRYABLE_STATUS and attempt == 1:
                    await r.aread()
                    await asyncio.sleep(_backoff_s())   # sebelum potongan pertama: aman diulang sekali
                    continue
                if r.status_code >= 400:
                    _check_status(p, r.status_code, await r.aread())
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        choice = json.loads(data)["choices"][0]
                    except (ValueError, KeyError, IndexError, TypeError):
                        continue
                    if delta := (choice.get("delta") or {}).get("content"):
                        yield delta
                    if choice.get("finish_reason") == "length":
                        yield TRUNCATED_NOTE
                    if deadline and time.monotonic() > deadline:
                        yield TRUNCATED_NOTE        # akhiri rapi sebelum platform memutus koneksi
                        break
                return
        except httpx.ConnectError as e:
            if attempt == 1:
                await asyncio.sleep(_backoff_s())
                continue
            hint = " Pastikan Ollama berjalan (`ollama serve`)." if p.id == "ollama" else ""
            raise AssistantError(f"Tidak bisa terhubung ke {p.label}.{hint}", 503) from e
        except httpx.TimeoutException as e:
            raise AssistantError(f"{p.label} berhenti merespons > {settings.AI_TIMEOUT_S:g} detik.", 504) from e


async def chat(p: Provider, model: str, messages: list[dict], client: httpx.AsyncClient) -> dict:
    """Satu giliran chat. Mengembalikan {'content', 'model', 'usage'}."""
    if not model:
        raise AssistantError(f"Pilih model untuk {p.label} (atau isi {p.model_setting} di .env).", 422)
    body = _body(p, model, messages, stream=False)
    for attempt in (1, 2):
        try:
            r = await client.post(f"{_base_url(p)}/chat/completions", headers=_headers(p), json=body,
                                  timeout=min(settings.AI_TIMEOUT_S, total_timeout_s() or settings.AI_TIMEOUT_S))
        except httpx.ConnectError as e:
            if attempt == 1:
                await asyncio.sleep(_backoff_s())
                continue
            hint = " Pastikan Ollama berjalan (`ollama serve`)." if p.id == "ollama" else ""
            raise AssistantError(f"Tidak bisa terhubung ke {p.label}.{hint}", 503) from e
        except httpx.TimeoutException as e:
            raise AssistantError(f"{p.label} tidak merespons dalam {settings.AI_TIMEOUT_S:g} detik.", 504) from e
        if r.status_code in RETRYABLE_STATUS and attempt == 1:
            await asyncio.sleep(_backoff_s())
            continue
        break
    _check_status(p, r.status_code, r.content)
    try:
        data = r.json()
        choice = data["choices"][0]
        content = (choice["message"]["content"] or "") + (TRUNCATED_NOTE if choice.get("finish_reason") == "length" else "")
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise AssistantError(f"Format respons {p.label} tidak dikenali.") from e
    return {"content": content.strip(), "model": data.get("model", model), "usage": data.get("usage")}
