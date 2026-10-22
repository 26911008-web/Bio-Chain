"""Router: 📊 Laporan bulanan dari gudang data tunggal — cakupan otomatis sesuai peran."""

import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models.user import User
from ..services.reports import monthly_report

router = APIRouter()
MONTH = r"^\d{4}-(0[1-9]|1[0-2])$"


@router.get("/monthly")
async def monthly(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    start: str | None = Query(None, alias="from", pattern=MONTH, description="YYYY-MM (default: 11 bulan sebelum 'to')"),
    end: str | None = Query(None, alias="to", pattern=MONTH, description="YYYY-MM (default: bulan ini, WIB)"),
    format: str = Query("json", pattern="^(json|csv)$"),
):
    """Volume pasokan, % konversi biomassa, efisiensi biaya per bulan. Petani/pengepul/supir: data sendiri;
    pabrik/admin/auditor: seluruh pabrik."""
    try:
        rep = await monthly_report(db, user, start, end)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if format == "json":
        return rep
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = rep["columns"]
    w.writerow(["bulan"] + [f"{c['label']} ({c['unit']})" for c in cols])
    for row in rep["months"]:
        w.writerow([row["month"]] + [row.get(c["key"].split(".")[0], {}).get(c["key"].split(".", 1)[1]) for c in cols])
    fname = f"laporan_{rep['scope']['kind']}_{rep['period']['from']}_{rep['period']['to']}.csv"
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})
