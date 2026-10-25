"""Perlindungan data pribadi (F12, UU 27/2022 PDP) & petani tanpa HP (F7).

- Persetujuan dicatat append-only (`consents`); yang berlaku = entri terbaru per tujuan.
- Ekspor data subjek: profil + seluruh catatan transaksi miliknya (JSON, bisa diunduh).
- Hapus akun = ANONIMISASI: identitas (nama, HP, username, email, lokasi) dihapus permanen; catatan transaksi
  (timbangan, pembayaran, biochar) tetap untuk kewajiban audit/pajak, tetapi tidak lagi terhubung ke orang.
- Nomor HP disamarkan di daftar lintas-pengguna (minimisasi data); nomor lengkap hanya lewat aksi "hubungi".
"""

import secrets
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.compliance import Consent, DataRequest, FarmerPayment
from ..models.harvest import Harvest
from ..models.ledger import BiocharLedgerEntry, CustodyEvent
from ..models.trade import Bid, StockListing
from ..models.user import User, UserRole

CONSENT_VERSION = "2026-10"
PURPOSES = {
    "layanan_inti": "Memproses identitas, lokasi penggilingan, timbangan & pembayaran untuk jual-beli sekam (wajib)",
    "lokasi_gps": "Merekam lokasi GPS saat penjemputan/rute untuk bukti serah-terima & emisi angkut",
    "foto_bukti": "Menyimpan foto bukti timbangan/serah-terima",
}
PROXY_PHONE_PREFIX = "NOHP-"
DELETED_PHONE_PREFIX = "DEL-"


def has_real_phone(phone: str | None) -> bool:
    """False untuk petani tanpa HP (NOHP-…) dan akun yang dianonimkan (DEL-…)."""
    return bool(phone) and not phone.startswith((PROXY_PHONE_PREFIX, DELETED_PHONE_PREFIX))


def mask_phone(phone: str | None) -> str | None:
    if not has_real_phone(phone):
        return None
    return phone[:4] + "*" * max(len(phone) - 8, 2) + phone[-4:] if len(phone) >= 10 else "****"


def _receipt(kind: str) -> str:
    return f"PDP-{kind.upper()[:3]}-{datetime.now(timezone.utc):%y%m%d}-{secrets.token_hex(3).upper()}"


async def record_consents(db: AsyncSession, user_id: int, choices: dict[str, bool], method: str = "aplikasi",
                          recorded_by_id: int | None = None) -> None:
    for purpose, granted in choices.items():
        if purpose not in PURPOSES:
            raise HTTPException(422, f"Tujuan persetujuan tidak dikenal: {purpose}")
        db.add(Consent(user_id=user_id, purpose=purpose, version=CONSENT_VERSION, granted=bool(granted),
                       method=method, recorded_by_id=recorded_by_id))


async def current_consents(db: AsyncSession, user_id: int) -> dict:
    rows = (await db.execute(select(Consent).where(Consent.user_id == user_id).order_by(Consent.id))).scalars().all()
    latest = {}
    for c in rows:
        latest[c.purpose] = {"granted": c.granted, "version": c.version, "method": c.method,
                             "at": c.created_at.isoformat() if c.created_at else None}
    return {"version": CONSENT_VERSION,
            "purposes": [{"purpose": p, "description": d, **(latest.get(p) or {"granted": None})}
                         for p, d in PURPOSES.items()],
            "needs_consent": (latest.get("layanan_inti") or {}).get("granted") is not True
                             or (latest.get("layanan_inti") or {}).get("version") != CONSENT_VERSION}


def _row(obj, cols) -> dict:
    out = {}
    for c in cols:
        v = getattr(obj, c, None)
        out[c] = v.value if hasattr(v, "value") else (v.isoformat() if isinstance(v, datetime) else
                                                      (int(v) if c.endswith("_rp") and v is not None else v))
    return out


async def export_data(db: AsyncSession, user: User) -> dict:
    uid = user.id
    harvests = (await db.execute(select(Harvest).where(or_(Harvest.farmer_id == uid, Harvest.collector_id == uid))
                                 .order_by(Harvest.id))).scalars().all()
    payments = (await db.execute(select(FarmerPayment).where(or_(FarmerPayment.farmer_id == uid,
                                                                 FarmerPayment.collector_id == uid)))).scalars().all()
    listings = (await db.execute(select(StockListing).where(StockListing.farmer_id == uid))).scalars().all()
    bids = (await db.execute(select(Bid).where(or_(Bid.collector_id == uid, Bid.farmer_id == uid)))).scalars().all()
    ledger = (await db.execute(select(BiocharLedgerEntry).where(BiocharLedgerEntry.farmer_id == uid))).scalars().all()
    events = (await db.execute(select(CustodyEvent).where(CustodyEvent.actor_id == uid)
                               .order_by(CustodyEvent.id))).scalars().all()
    db.add(DataRequest(user_id=uid, kind="ekspor", status="selesai", receipt_code=(code := _receipt("ekspor"))))
    await db.commit()
    return {
        "receipt_code": code, "generated_at": datetime.now(timezone.utc).isoformat(),
        "legal_basis": "UU 27/2022 Pelindungan Data Pribadi — hak akses & portabilitas data",
        "profile": _row(user, ["id", "username", "phone", "email", "full_name", "role", "kecamatan", "kabupaten",
                               "lat", "lon", "xp_total", "created_at"]),
        "consents": await current_consents(db, uid),
        "harvests": [_row(h, ["id", "qr_code", "status", "quantity_kg", "verified_kg", "received_kg", "grade",
                              "moisture", "total_price", "reported_at", "verified_at", "delivered_at"]) for h in harvests],
        "farmer_payments": [_row(p, ["id", "harvest_id", "gross_rp", "tax_rp", "net_rp", "method", "reference",
                                     "receipt_code", "paid_at"]) for p in payments],
        "stock_listings": [_row(x, ["id", "quantity_kg", "remaining_kg", "status", "created_at"]) for x in listings],
        "bids": [_row(b, ["id", "listing_id", "price_per_kg", "quantity_kg", "status", "created_at"]) for b in bids],
        "biochar_ledger": [_row(e, ["id", "entry_type", "amount_kg", "created_at"]) for e in ledger],
        "custody_events": [_row(e, ["id", "harvest_id", "stage", "weight_kg", "verification_code", "lat", "lon",
                                    "created_at"]) for e in events],
    }


def export_data_docx(data: dict) -> bytes:
    """Ekspor salinan resmi data pribadi pengguna ke dokumen Microsoft Word (.docx) sesuai UU 27/2022 PDP."""
    import io
    import docx
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls

    doc = docx.Document()
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    def _cell_bg(cell, hex_color):
        tcPr = cell._tc.get_or_add_tcPr()
        tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>'))

    def _style_run(run, size=10, bold=False, italic=False, color=(33, 33, 33)):
        run.font.name = "Calibri"
        run.font.size = Pt(size)
        run.bold = bold
        run.italic = italic
        run.font.color.rgb = RGBColor(*color)

    # Header
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_after = Pt(2)
    r = title_p.add_run("SALINAN DATA PRIBADI PENGGUNA (UU 27/2022 PDP)")
    _style_run(r, size=16, bold=True, color=(27, 94, 32))

    meta_p = doc.add_paragraph()
    meta_p.paragraph_format.space_after = Pt(12)
    prof = data.get("profile") or {}
    r_meta = meta_p.add_run(
        f"Tanda Terima: {data.get('receipt_code')} · Waktu Unduh: {data.get('generated_at')}\n"
        f"Dasar Hukum: {data.get('legal_basis')}"
    )
    _style_run(r_meta, size=9.5, italic=True, color=(100, 100, 100))

    # 1. Profil Pengguna
    h1 = doc.add_heading("1. Profil Subjek Data", level=2)
    _style_run(h1.runs[0], size=12, bold=True, color=(27, 94, 32))
    t_prof = doc.add_table(rows=0, cols=2)
    fields = [
        ("ID Pengguna", str(prof.get("id"))),
        ("Nama Lengkap", str(prof.get("full_name") or "-")),
        ("Username", str(prof.get("username") or "-")),
        ("Nomor HP", str(prof.get("phone") or "-")),
        ("Email", str(prof.get("email") or "-")),
        ("Peran Sistem", str(prof.get("role") or "-")),
        ("Lokasi", f"{prof.get('kecamatan') or '-'}, {prof.get('kabupaten') or '-'}"),
        ("XP Total", str(prof.get("xp_total") or "0")),
        ("Tanggal Terdaftar", str(prof.get("created_at") or "-")),
    ]
    for k, v in fields:
        row = t_prof.add_row()
        c0, c1 = row.cells
        _cell_bg(c0, "E8F5E9")
        r0 = c0.paragraphs[0].add_run(k)
        _style_run(r0, size=9.5, bold=True, color=(27, 94, 32))
        r1 = c1.paragraphs[0].add_run(v)
        _style_run(r1, size=9.5, color=(33, 33, 33))

    # 2. Persetujuan Pemrosesan Data
    doc.add_paragraph()
    h2 = doc.add_heading("2. Persetujuan Pemrosesan Data Pribadi", level=2)
    _style_run(h2.runs[0], size=12, bold=True, color=(27, 94, 32))
    cons = data.get("consents") or {}
    t_cons = doc.add_table(rows=1, cols=3)
    hdr_cells = t_cons.rows[0].cells
    for i, title in enumerate(["Tujuan Pemrosesan", "Deskripsi Kebijakan", "Status Persetujuan"]):
        _cell_bg(hdr_cells[i], "2E7D32")
        r = hdr_cells[i].paragraphs[0].add_run(title)
        _style_run(r, size=9.5, bold=True, color=(255, 255, 255))
    for p in cons.get("purposes", []):
        row = t_cons.add_row()
        c0, c1, c2 = row.cells
        r0 = c0.paragraphs[0].add_run(p.get("purpose", ""))
        _style_run(r0, size=9, bold=True)
        r1 = c1.paragraphs[0].add_run(p.get("description", ""))
        _style_run(r1, size=9)
        st_text = "DISETUJUI" if p.get("granted") else "TIDAK DISETUJUI"
        _cell_bg(c2, "C8E6C9" if p.get("granted") else "FFCDD2")
        r2 = c2.paragraphs[0].add_run(st_text)
        _style_run(r2, size=9, bold=True, color=(27, 94, 32) if p.get("granted") else (183, 28, 28))

    # 3. Laporan Panen / Biomassa
    harvests = data.get("harvests", [])
    if harvests:
        doc.add_paragraph()
        h3 = doc.add_heading(f"3. Riwayat Laporan Panen & Mutu Biomassa ({len(harvests)} Catatan)", level=2)
        _style_run(h3.runs[0], size=12, bold=True, color=(27, 94, 32))
        t_h = doc.add_table(rows=1, cols=7)
        for i, title in enumerate(["ID", "Status", "Lapor (kg)", "Timbang (kg)", "Grade", "Air (%)", "Waktu Lapor"]):
            _cell_bg(t_h.rows[0].cells[i], "2E7D32")
            r = t_h.rows[0].cells[i].paragraphs[0].add_run(title)
            _style_run(r, size=9, bold=True, color=(255, 255, 255))
        for h in harvests[:50]:
            row = t_h.add_row()
            cells = row.cells
            vals = [
                f"#{h.get('id')}", str(h.get("status") or "-"),
                str(h.get("quantity_kg") or "-"), str(h.get("verified_kg") or "-"),
                str(h.get("grade") or "-"), str(h.get("moisture") or "-"),
                str(h.get("reported_at") or "-")[:16].replace("T", " ")
            ]
            for idx, val in enumerate(vals):
                r = cells[idx].paragraphs[0].add_run(val)
                _style_run(r, size=8.5)

    # 4. Kuitansi & Pembayaran
    payments = data.get("farmer_payments", [])
    if payments:
        doc.add_paragraph()
        h4 = doc.add_heading(f"4. Riwayat Kuitansi & Pembayaran ({len(payments)} Catatan)", level=2)
        _style_run(h4.runs[0], size=12, bold=True, color=(27, 94, 32))
        t_p = doc.add_table(rows=1, cols=6)
        for i, title in enumerate(["No Kuitansi", "Bruto (Rp)", "Pajak (Rp)", "Netto (Rp)", "Metode", "Waktu Bayar"]):
            _cell_bg(t_p.rows[0].cells[i], "2E7D32")
            r = t_p.rows[0].cells[i].paragraphs[0].add_run(title)
            _style_run(r, size=9, bold=True, color=(255, 255, 255))
        for p in payments[:50]:
            row = t_p.add_row()
            cells = row.cells
            vals = [
                str(p.get("receipt_code") or f"BYR-#{p.get('id')}"),
                f"{p.get('gross_rp', 0):,}", f"{p.get('tax_rp', 0):,}", f"{p.get('net_rp', 0):,}",
                str(p.get("method") or "-").upper(),
                str(p.get("paid_at") or "-")[:16].replace("T", " ")
            ]
            for idx, val in enumerate(vals):
                r = cells[idx].paragraphs[0].add_run(val)
                _style_run(r, size=8.5)

    # 5. Dompet Biochar
    ledger = data.get("biochar_ledger", [])
    if ledger:
        doc.add_paragraph()
        h5 = doc.add_heading(f"5. Buku Besar Saldo Dompet Biochar ({len(ledger)} Catatan)", level=2)
        _style_run(h5.runs[0], size=12, bold=True, color=(27, 94, 32))
        t_l = doc.add_table(rows=1, cols=3)
        for i, title in enumerate(["Jenis Transaksi", "Jumlah (kg)", "Waktu Transaksi"]):
            _cell_bg(t_l.rows[0].cells[i], "2E7D32")
            r = t_l.rows[0].cells[i].paragraphs[0].add_run(title)
            _style_run(r, size=9, bold=True, color=(255, 255, 255))
        for l in ledger[:50]:
            row = t_l.add_row()
            cells = row.cells
            vals = [str(l.get("entry_type") or "-"), f"{l.get('amount_kg', 0):+.2f}", str(l.get("created_at") or "-")[:16].replace("T", " ")]
            for idx, val in enumerate(vals):
                r = cells[idx].paragraphs[0].add_run(val)
                _style_run(r, size=8.5)

    doc.add_paragraph()
    foot = doc.add_paragraph()
    foot.paragraph_format.space_before = Pt(14)
    r_f = foot.add_run("Dokumen ini dihasilkan secara otomatis oleh Platform Bio-Chain sebagai pemenuhan hak akses data subjek berdasarkan UU No. 27/2022.")
    _style_run(r_f, size=8.5, italic=True, color=(128, 128, 128))

    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()


async def anonymize(db: AsyncSession, user: User, reason: str | None) -> dict:
    if user.anonymized_at:
        raise HTTPException(409, "Akun sudah dianonimkan.")
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    if role == UserRole.ADMIN.value:
        others = (await db.execute(select(User.id).where(User.role == UserRole.ADMIN, User.id != user.id,
                                                         User.is_active.is_(True), User.anonymized_at.is_(None)))).first()
        if not others:
            raise HTTPException(409, "Tidak bisa menghapus admin aktif terakhir.")
    from ..routers.auth import hash_password
    from ..concurrency import run_cpu
    tag = secrets.token_hex(4)
    user.full_name = f"Pengguna terhapus #{user.id}"
    user.phone = f"{DELETED_PHONE_PREFIX}{user.id}-{tag}"[:20]
    user.username = None
    user.email = None
    user.lat = user.lon = None
    user.password_hash = await run_cpu(hash_password, secrets.token_urlsafe(24))
    user.is_active = False
    user.anonymized_at = datetime.now(timezone.utc)
    db.add(DataRequest(user_id=user.id, kind="hapus", status="selesai", receipt_code=(code := _receipt("hapus")),
                       note=(reason or "")[:500] or None))
    await db.commit()
    return {"receipt_code": code, "status": "dianonimkan",
            "kept": "Catatan timbangan, pembayaran & biochar disimpan tanpa identitas untuk kewajiban audit/pajak."}
