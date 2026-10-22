"""Router: Hak subjek data pribadi (UU 27/2022 PDP) — semua peran, hanya atas data diri sendiri."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..concurrency import run_cpu
from ..database import get_db
from ..dependencies import get_current_user
from ..models.user import User
from ..services import privacy

router = APIRouter()


class ConsentRequest(BaseModel):
    choices: dict[str, bool] = Field(..., description="{tujuan: setuju?} — lihat GET /consents")


class DeleteRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)
    reason: str | None = Field(None, max_length=500)


@router.get("/consents")
async def get_consents(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await privacy.current_consents(db, user.id)


@router.post("/consents")
async def set_consents(req: ConsentRequest, user: Annotated[User, Depends(get_current_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    if req.choices.get("layanan_inti") is False:
        raise HTTPException(422, "Persetujuan layanan inti wajib untuk memakai aplikasi. Untuk berhenti, gunakan "
                                 "'Hapus akun & data saya'.")
    await privacy.record_consents(db, user.id, req.choices)
    await db.commit()
    return await privacy.current_consents(db, user.id)


@router.get("/data-export")
async def data_export(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    format: str = "json",
):
    data = await privacy.export_data(db, user)
    if format.lower() == "docx":
        from fastapi import Response
        docx_bytes = privacy.export_data_docx(data)
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="biochain-data-saya-{user.id}.docx"',
                "Cache-Control": "no-store",
            },
        )
    return JSONResponse(data, headers={"Content-Disposition": f'attachment; filename="biochain-data-saya-{user.id}.json"',
                                       "Cache-Control": "no-store"})


@router.post("/delete")
async def delete_me(req: DeleteRequest, user: Annotated[User, Depends(get_current_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    from .auth import verify_password
    if not await run_cpu(verify_password, req.password, user.password_hash):
        raise HTTPException(401, "Password salah.")
    return await privacy.anonymize(db, user, req.reason)
