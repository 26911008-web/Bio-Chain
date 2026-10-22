"""Router: Asisten AI — tanya-jawab & saran optimasi, sesuai peran yang login."""

from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..ai import providers as P
from ..ai.context import build_context, system_prompt
from ..database import get_db
from ..dependencies import get_current_user
from ..models.user import User

router = APIRouter()


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    provider: str | None = None
    model: str | None = Field(None, max_length=200)


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
    return p, req.model or P.default_model(p), messages, ctx


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
