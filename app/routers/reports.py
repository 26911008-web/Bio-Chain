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
    format: str = Query("json", pattern="^(json|csv|xlsx)$"),
):
    """Volume pasokan, % konversi biomassa, efisiensi biaya per bulan. Petani/pengepul/supir: data sendiri;
    pabrik/admin/auditor: seluruh pabrik."""
    try:
        rep = await monthly_report(db, user, start, end)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if format == "json":
        return rep
    if format == "xlsx":
        import openpyxl
        wb = openpyxl.Workbook()
        ws_data = wb.active
        ws_data.title = "Ringkasan Laporan"
        cols = rep["columns"]
        ws_data.append(["Bulan"] + [f"{c['label']} ({c['unit']})" for c in cols])
        for row in rep["months"]:
            ws_data.append([row["month"]] + [row.get(c["key"].split(".")[0], {}).get(c["key"].split(".", 1)[1]) for c in cols])

        ws_meta = wb.create_sheet(title="Info & Cakupan")
        ws_meta.append(["Parameter", "Nilai"])
        ws_meta.append(["Peran Pengguna", rep["scope"]["label"]])
        ws_meta.append(["Cakupan Data", rep["scope"]["kind"]])
        ws_meta.append(["Periode Dari", rep["period"]["from"]])
        ws_meta.append(["Periode Sampai", rep["period"]["to"]])

        out_buf = io.BytesIO()
        wb.save(out_buf)
        out_buf.seek(0)
        fname = f"laporan_{rep['scope']['kind']}_{rep['period']['from']}_{rep['period']['to']}.xlsx"
        return StreamingResponse(
            out_buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'}
        )
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = rep["columns"]
    w.writerow(["bulan"] + [f"{c['label']} ({c['unit']})" for c in cols])
    for row in rep["months"]:
        w.writerow([row["month"]] + [row.get(c["key"].split(".")[0], {}).get(c["key"].split(".", 1)[1]) for c in cols])
    fname = f"laporan_{rep['scope']['kind']}_{rep['period']['from']}_{rep['period']['to']}.csv"
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})
