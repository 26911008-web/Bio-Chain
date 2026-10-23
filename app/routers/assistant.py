"""Router: Asisten AI — tanya-jawab & saran optimasi, sesuai peran yang login."""

from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..ai import providers as P
from ..config import settings
from ..ai.context import build_context, optimization_prompt, system_prompt
from ..database import get_db
from ..dependencies import get_current_user
from ..models.user import User
from ..services import insights

router = APIRouter()


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    provider: str | None = None
    model: str | None = Field(None, max_length=200)


class EvaluateRequest(BaseModel):
    provider: str | None = None
    model: str | None = Field(None, max_length=200)
    focus: str | None = Field(None, max_length=200)


def _pick_model(p: "P.Provider", requested: str | None, user: User) -> str:
    """Admin bebas memilih model; peran lain hanya model default atau yang ada di AI_ALLOWED_MODELS."""
    default = P.default_model(p)
    if not requested or requested == default:
        return default
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    allowed = {m.strip() for m in settings.AI_ALLOWED_MODELS.split(",") if m.strip()}
    if role == "admin" or requested in allowed:
        return requested
    raise P.AssistantError("Model ini tidak diizinkan untuk akun Anda; gunakan model default.", 403)


def _error(e: P.AssistantError) -> JSONResponse:
    return JSONResponse(status_code=e.status, content={"detail": str(e)})


async def http_client():
    async with P.new_client() as client:
        yield client


@router.get("/providers")
async def providers(user: Annotated[User, Depends(get_current_user)]):
    """Provider yang tersedia + status konfigurasi. API key tidak pernah dikembalikan."""
    return {
        "default": P.resolve_default(),
        "providers": [{"id": p.id, "label": p.label, "note": p.note, "configured": P.is_configured(p),
                       "default_model": P.default_model(p), "needs": p.key_setting}
                      for p in P.PROVIDERS.values()],
    }


@router.get("/providers/{provider_id}/models")
async def models(provider_id: str, user: Annotated[User, Depends(get_current_user)],
                 client: Annotated[httpx.AsyncClient, Depends(http_client)]):
    try:
        p = P.get_provider(provider_id)
        return {"provider": p.id, "default_model": P.default_model(p), "models": await P.list_models(p, client)}
    except P.AssistantError as e:
        return _error(e)


async def _prepare(req: ChatRequest, user: User, db: AsyncSession):
    p = P.get_provider(req.provider)
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    ctx = await build_context(db, user)
    await db.commit()                             # lepas koneksi DB selama menunggu LLM (bisa puluhan detik)
    messages = [{"role": "system", "content": system_prompt(role, ctx)}]
    messages += [t.model_dump() for t in req.history[-10:]]
    messages.append({"role": "user", "content": req.message})
    return p, _pick_model(p, req.model, user), messages, ctx


@router.post("/chat")
async def chat(req: ChatRequest, user: Annotated[User, Depends(get_current_user)],
               db: Annotated[AsyncSession, Depends(get_db)],
               client: Annotated[httpx.AsyncClient, Depends(http_client)]):
    """Jawaban utuh sekaligus (untuk integrasi/tes). UI memakai /chat/stream."""
    try:
        p, model, messages, ctx = await _prepare(req, user, db)
        out = await P.chat(p, model, messages, client)
        return {"reply": out["content"], "provider": p.id, "model": out["model"], "usage": out["usage"],
                "context_scope": sorted(ctx)}
    except P.AssistantError as e:
        return _error(e)


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, user: Annotated[User, Depends(get_current_user)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    """Jawaban mengalir (text/plain) — kata pertama tampil secepat model menghasilkannya."""
    try:
        p, model, messages, _ = await _prepare(req, user, db)
        if not model:
            raise P.AssistantError(f"Pilih model untuk {p.label} (atau isi {p.model_setting} di .env).", 422)
    except P.AssistantError as e:
        return _error(e)

    async def gen():
        # Klien HTTP dimiliki generator: dependency yield sudah ditutup sebelum streaming dimulai.
        async with P.new_client() as client:
            try:
                async for chunk in P.chat_stream(p, model, messages, client):
                    yield chunk
            except P.AssistantError as e:
                yield f"\n\n⚠️ {e}"

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8",
                             headers={"X-AI-Provider": p.id, "X-AI-Model": model, "Cache-Control": "no-store"})



def _role(user: User) -> str:
    return user.role.value if hasattr(user.role, "value") else str(user.role)


async def _evaluation(user: User, db: AsyncSession, window_months: int | None = None) -> dict:
    ev = await insights.evaluate(db, user, window_months=window_months)
    await db.commit()                             # lepas koneksi DB sebelum menunggu LLM
    return ev


def _opt_messages(user: User, ev: dict, focus: str | None) -> list[dict]:
    return [{"role": "system", "content": optimization_prompt(_role(user), ev, focus)},
            {"role": "user", "content": "Susun evaluasi dan rencana optimasi saya berdasarkan data di atas."}]


@router.get("/evaluation")
async def evaluation(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    window_months: int | None = None,
):
    """KPI, skor, dan prioritas optimasi (deterministik, tanpa kuota AI)."""
    ev = await _evaluation(user, db, window_months=window_months)
    return {**ev, "summary_markdown": insights.deterministic_markdown(ev)}


@router.post("/evaluate")
async def evaluate(req: EvaluateRequest, user: Annotated[User, Depends(get_current_user)],
                   db: Annotated[AsyncSession, Depends(get_db)],
                   client: Annotated[httpx.AsyncClient, Depends(http_client)]):
    """Evaluasi + narasi AI sekaligus (non-streaming). Bila AI tidak tersedia, ringkasan deterministik."""
    ev = await _evaluation(user, db)
    out = {**ev, "is_ai_generated": False, "provider": None, "model": None, "ai_error": None,
           "evaluation_markdown": insights.deterministic_markdown(ev)}
    try:
        p = P.get_provider(req.provider)
        model = _pick_model(p, req.model, user)
        res = await P.chat(p, model, _opt_messages(user, ev, req.focus), client)
        out.update(evaluation_markdown=res["content"], is_ai_generated=True, provider=p.label, model=res["model"])
    except P.AssistantError as e:
        out["ai_error"] = str(e)
    return out


@router.post("/evaluate/stream")
async def evaluate_stream(req: EvaluateRequest, user: Annotated[User, Depends(get_current_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    """Narasi AI mengalir kata demi kata. Header X-AI-Fallback=1 bila AI tidak tersedia."""
    ev = await _evaluation(user, db)
    fallback = insights.deterministic_markdown(ev)
    try:
        p = P.get_provider(req.provider)
        model = _pick_model(p, req.model, user)
        if not model:
            raise P.AssistantError(f"Pilih model untuk {p.label} (atau isi {p.model_setting} di .env).", 422)
    except P.AssistantError as e:
        reason = str(e)                       # `e` dihapus Python di akhir blok except — simpan pesannya

        async def fb():
            yield f"⚠️ Asisten AI tidak tersedia ({reason}). Ringkasan otomatis:\n\n{fallback}"
        return StreamingResponse(fb(), media_type="text/plain; charset=utf-8",
                                 headers={"X-AI-Fallback": "1", "Cache-Control": "no-store"})
    messages = _opt_messages(user, ev, req.focus)

    async def gen():
        async with P.new_client() as client:
            sent = False
            try:
                async for chunk in P.chat_stream(p, model, messages, client):
                    sent = True
                    yield chunk
            except P.AssistantError as e:
                yield (f"\n\n⚠️ {e}" if sent else f"⚠️ {e}. Ringkasan otomatis:\n\n{fallback}")

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8",
                             headers={"X-AI-Provider": p.id, "X-AI-Model": model, "Cache-Control": "no-store"})
