"""Sub-router petani: evaluasi mutu abu/biochar, rating pengepul & konfirmasi jadwal jemput.

Dipisah dari app/routers/farmer.py (audit 23 Okt 2026, CLAUDE.md §3.1) dan di-mount olehnya.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_role
from ..models.user import User, UserRole
from ..models.harvest import Harvest
from ..models.trade import StockListing, Bid, CollectorPaymentReputation, CollectorRating
from ..models.circular import BiocharQualityEvaluation

router = APIRouter()



# -----------------------------------------------------------------------------
# Evaluasi Mutu Abu Bottom Ash & Performa Pengepul oleh Petani
# -----------------------------------------------------------------------------
class BiocharEvaluationCreate(BaseModel):
    biochar_request_id: int | None = None
    collector_id: int | None = None
    batch_code: str | None = Field(None, max_length=50)
    grain_size_mesh_rating: int = Field(5, ge=1, le=5, description="Kesesuaian ukuran butir/mesh (1-5)")
    pyrolysis_maturity_rating: int = Field(5, ge=1, le=5, description="Tingkat kalsinasi / kematangan (1-5)")
    moisture_rating: int = Field(5, ge=1, le=5, description="Kekeringan / kelembapan abu (1-5)")
    soil_impact_rating: int = Field(5, ge=1, le=5, description="Dampak perbaikan struktur tanah & tanaman (1-5)")
    review_notes: str | None = Field(None, max_length=1000)


@router.post("/biochar-evaluations", status_code=201)
async def submit_biochar_evaluation(
    req: BiocharEvaluationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Petani mengisi evaluasi kualitas abu bottom ash yang diterima (mesh, kematangan, kelembapan, dampak tanah)."""
    overall = round((req.grain_size_mesh_rating + req.pyrolysis_maturity_rating + req.moisture_rating + req.soil_impact_rating) / 4.0, 2)
    eval_record = BiocharQualityEvaluation(
        farmer_id=user.id,
        biochar_request_id=req.biochar_request_id,
        collector_id=req.collector_id,
        batch_code=req.batch_code,
        grain_size_mesh_rating=req.grain_size_mesh_rating,
        pyrolysis_maturity_rating=req.pyrolysis_maturity_rating,
        moisture_rating=req.moisture_rating,
        soil_impact_rating=req.soil_impact_rating,
        overall_score=overall,
        review_notes=req.review_notes,
    )
    db.add(eval_record)
    await db.flush()
    return {
        "success": True,
        "id": eval_record.id,
        "overall_score": overall,
        "evaluation": {
            "id": eval_record.id,
            "overall_score": overall,
            "batch_code": eval_record.batch_code,
            "review_notes": eval_record.review_notes,
        },
        "message": f"✅ Evaluasi mutu abu bottom ash berhasil dicatat (Skor: {overall}/5.0). Umpan balik Anda membantu kontrol mutu pabrik & pembenah tanah sawah."
    }


@router.get("/biochar-evaluations")
async def list_biochar_evaluations(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Daftar riwayat evaluasi mutu abu bottom ash yang diajukan petani."""
    rows = (await db.execute(
        select(BiocharQualityEvaluation)
        .where(BiocharQualityEvaluation.farmer_id == user.id)
        .order_by(BiocharQualityEvaluation.id.desc())
    )).scalars().all()
    return [
        {
            "id": r.id,
            "biochar_request_id": r.biochar_request_id,
            "collector_id": r.collector_id,
            "batch_code": r.batch_code,
            "grain_size_mesh_rating": r.grain_size_mesh_rating,
            "pyrolysis_maturity_rating": r.pyrolysis_maturity_rating,
            "moisture_rating": r.moisture_rating,
            "soil_impact_rating": r.soil_impact_rating,
            "overall_score": r.overall_score,
            "review_notes": r.review_notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


class CollectorRatingCreate(BaseModel):
    collector_id: int
    harvest_id: int | None = None
    punctuality_rating: int = Field(5, ge=1, le=5, description="Ketepatan waktu penjemputan/penerimaan (1-5)")
    payment_rating: int = Field(5, ge=1, le=5, description="Ketepatan & kelancaran pembayaran DP/pelunasan (1-5)")
    review_text: str | None = Field(None, max_length=1000)


@router.post("/collector-ratings", status_code=201)
async def submit_collector_rating(
    req: CollectorRatingCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Petani memberikan rating performa ketepatan waktu & kelancaran pembayaran pengepul."""
    collector = (await db.execute(select(User).where(User.id == req.collector_id, User.role == UserRole.PENGEPUL))).scalar_one_or_none()
    if not collector:
        raise HTTPException(404, "Pengepul tidak ditemukan.")

    # Rating hanya dari transaksi nyata, satu kali per panen — tanpa ini petani mana pun bisa menilai pengepul
    # mana pun berulang-ulang dan memanipulasi skor reputasi (moving average di bawah).
    rated = select(CollectorRating.harvest_id).where(CollectorRating.farmer_id == user.id,
                                                      CollectorRating.harvest_id.is_not(None))
    own_tx = select(Harvest.id).where(Harvest.farmer_id == user.id, Harvest.collector_id == req.collector_id)
    if req.harvest_id is not None:
        if (await db.execute(own_tx.where(Harvest.id == req.harvest_id))).first() is None:
            raise HTTPException(403, "Panen ini bukan transaksi Anda dengan pengepul tersebut.")
        if (await db.execute(rated.where(CollectorRating.harvest_id == req.harvest_id))).first() is not None:
            raise HTTPException(409, "Transaksi ini sudah Anda nilai.")
        harvest_id = req.harvest_id
    else:
        # UI memilih pengepul saja → nilai transaksi terbaru dengan pengepul itu yang belum dinilai
        harvest_id = (await db.execute(own_tx.where(Harvest.id.not_in(rated)).order_by(Harvest.id.desc()).limit(1))).scalar()
        if harvest_id is None:
            raise HTTPException(403, "Belum ada transaksi dengan pengepul ini yang bisa dinilai (atau semua sudah dinilai).")

    overall = round((req.punctuality_rating + req.payment_rating) / 2.0, 1)
    rating = CollectorRating(
        farmer_id=user.id,
        collector_id=req.collector_id,
        harvest_id=harvest_id,
        punctuality_rating=req.punctuality_rating,
        payment_rating=req.payment_rating,
        overall_rating=overall,
        review_text=req.review_text,
    )
    db.add(rating)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as e:          # indeks unik (farmer_id, harvest_id) — klik ganda / dua HP bersamaan
        raise HTTPException(409, "Transaksi ini sudah Anda nilai.") from e

    # Perbarui scorecard reputasi pengepul
    rep = (await db.execute(
        select(CollectorPaymentReputation).where(CollectorPaymentReputation.collector_id == req.collector_id)
    )).scalar_one_or_none()
    if not rep:
        rep = CollectorPaymentReputation(
            collector_id=req.collector_id,
            total_transactions=1,
            on_time_settlement_count=1,
            punctuality_score=overall * 20.0,
            rating_tier="EXCELLENT" if overall >= 4.5 else ("GOOD" if overall >= 3.5 else "FAIR"),
        )
        db.add(rep)
    else:
        rep.total_transactions += 1
        # Bobot moving average
        current_score = rep.punctuality_score or 90.0
        new_score = round((current_score * 0.8) + (overall * 20.0 * 0.2), 1)
        rep.punctuality_score = new_score
        rep.rating_tier = "EXCELLENT" if new_score >= 85 else ("GOOD" if new_score >= 70 else "FAIR")
    await db.flush()

    return {
        "success": True,
        "id": rating.id,
        "overall_rating": overall,
        "rating": {
            "id": rating.id,
            "overall_rating": overall,
            "punctuality_rating": rating.punctuality_rating,
            "payment_rating": rating.payment_rating,
            "review_text": rating.review_text,
        },
        "message": f"⭐ Terima kasih! Rating {overall}/5.0 berhasil disimpan untuk {collector.full_name}."
    }


@router.get("/collector-ratings")
async def list_collector_ratings(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Daftar riwayat rating performa pengepul yang telah dikirim oleh petani."""
    rows = (await db.execute(
        select(CollectorRating, User)
        .join(User, User.id == CollectorRating.collector_id)
        .where(CollectorRating.farmer_id == user.id)
        .order_by(CollectorRating.id.desc())
    )).all()
    return [
        {
            "id": r.id,
            "collector_id": r.collector_id,
            "collector_name": c.full_name or c.username,
            "harvest_id": r.harvest_id,
            "punctuality_rating": r.punctuality_rating,
            "payment_rating": r.payment_rating,
            "overall_rating": r.overall_rating,
            "review_text": r.review_text,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r, c in rows
    ]


# -----------------------------------------------------------------------------
# FASE 2: Konfirmasi Jadwal & Feedback QC Petani
# -----------------------------------------------------------------------------


class ScheduleConfirmRequest(BaseModel):
    bid_id: int
    decision: str = Field(..., pattern="^(APPROVE|RESCHEDULE)$", description="'APPROVE' | 'RESCHEDULE'")
    reschedule_note: str | None = Field(None, max_length=500, description="Alasan jika minta jadwal ulang")


@router.post("/schedule/confirm")
async def confirm_pickup_schedule(
    req: ScheduleConfirmRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role(UserRole.PETANI))],
):
    """Petani mengonfirmasi (Approve / Reschedule) rencana jadwal penjemputan dari pengepul."""
    bid = (await db.execute(
        select(Bid).where(Bid.id == req.bid_id, Bid.farmer_id == user.id).with_for_update()
    )).scalar_one_or_none()
    if not bid:
        # Fallback coba via listing_id
        bid = (await db.execute(
            select(Bid).join(StockListing, StockListing.id == Bid.listing_id)
            .where(Bid.id == req.bid_id, StockListing.farmer_id == user.id).with_for_update()
        )).scalar_one_or_none()

    if not bid:
        raise HTTPException(404, "Data penawaran/jadwal tidak ditemukan.")

    if req.decision == "APPROVE":
        bid.farmer_schedule_status = "APPROVED"
        bid.farmer_schedule_note = req.reschedule_note or "Petani menyetujui jadwal penjemputan resmi."
        msg = "✅ Jadwal penjemputan berhasil dikonfirmasi resmi. Pengepul siap berangkat sesuai jadwal."
    else:
        bid.farmer_schedule_status = "RESCHEDULE_REQUESTED"
        bid.farmer_schedule_note = req.reschedule_note or "Petani meminta penyesuaian jadwal penjemputan."
        msg = "📅 Permintaan jadwal ulang berhasil dikirimkan ke pengepul."

    await db.flush()
    return {
        "success": True,
        "bid_id": bid.id,
        "farmer_schedule_status": bid.farmer_schedule_status,
        "note": bid.farmer_schedule_note,
        "message": msg
    }
