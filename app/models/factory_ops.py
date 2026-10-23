"""SQLAlchemy ORM — Operasi pabrik: Delivery Request & negosiasi, QC masuk, batch manufaktur sirkular, biaya."""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, CheckConstraint, Column, DateTime, Double, Enum, ForeignKey, Integer, Numeric, String, Text,
    UniqueConstraint,
)

from ..database import Base


def _enum(e):
    return Enum(e, native_enum=False, values_callable=lambda x: [m.value for m in x])


def _now():
    return datetime.now(timezone.utc)


class RequestStatus(str, enum.Enum):
    SUBMITTED = "submitted"        # diajukan pengepul, menunggu pabrik
    COUNTERED = "countered"        # pabrik/pengepul mengajukan tawaran balik
    ACCEPTED = "accepted"          # jadwal & harga disepakati
    DELIVERED = "delivered"        # sudah lolos QC masuk
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class QCDecision(str, enum.Enum):
    ACCEPT = "terima"
    ACCEPT_PENALTY = "terima_potongan"
    REJECT = "tolak"


class DeliveryRequest(Base):
    __tablename__ = "delivery_requests"
    __table_args__ = (CheckConstraint("quantity_kg > 0", name="ck_dr_qty"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    quantity_kg = Column(Double, nullable=False)
    moisture_est = Column(Double, nullable=False)
    ash_est = Column(Double, nullable=True)
    grade_est = Column(String(5), nullable=True)
    proposed_date = Column(String(10), nullable=False)
    proposed_price_per_kg = Column(Double, nullable=False)
    recommended_price_per_kg = Column(Double, nullable=True)     # snapshot Pricing Engine saat diajukan
    agreed_price_per_kg = Column(Double, nullable=True)
    agreed_date = Column(String(10), nullable=True)
    pending_party = Column(String(10), nullable=True)          # "pabrik" | "pengepul" — siapa yang harus menjawab
    rounds = Column(Integer, nullable=False, default=0)
    status = Column(_enum(RequestStatus), nullable=False, default=RequestStatus.SUBMITTED, index=True)
    logistics_carrier = Column(String(30), default="FACTORY_FLEET", index=True)
    mill_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    biomass_type = Column(String(50), default="sekam_padi", server_default="sekam_padi", nullable=False)
    pricing_mode = Column(String(20), default="AUCTION", nullable=False)
    note = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=_now)
    decided_at = Column(DateTime(timezone=True), nullable=True)


class NegotiationEvent(Base):
    """Append-only: setiap ajuan, tawaran balik, persetujuan, penolakan."""
    __tablename__ = "negotiation_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey("delivery_requests.id"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor_role = Column(String(20), nullable=False)
    action = Column(String(20), nullable=False)          # submit | counter | accept | reject | cancel | qc
    price_per_kg = Column(Double, nullable=True)
    date = Column(String(10), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class InboundQC(Base):
    """Pemeriksaan mutu & timbang masuk. Lot yang diterima menjadi stok bahan baku (remaining_kg)."""
    __tablename__ = "inbound_qc"
    __table_args__ = (
        CheckConstraint("gross_kg >= tare_kg AND tare_kg >= 0", name="ck_qc_weights"),
        CheckConstraint("remaining_kg >= 0", name="ck_qc_remaining"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey("delivery_requests.id"), nullable=False, unique=True)
    gross_kg = Column(Double, nullable=False)
    tare_kg = Column(Double, nullable=False, default=0)
    net_kg = Column(Double, nullable=False)
    payable_kg = Column(Double, nullable=False)          # net × (1 − kontaminan)
    moisture = Column(Double, nullable=False)
    ash = Column(Double, nullable=False)
    volatile_matter = Column(Double, nullable=False)
    fixed_carbon = Column(Double, nullable=False)
    contamination = Column(Double, nullable=False, default=0)
    grade = Column(String(6), nullable=False)
    score = Column(Double, nullable=False)
    decision = Column(_enum(QCDecision), nullable=False)
    final_price_per_kg = Column(Double, nullable=False)
    total_payment_rp = Column(Double, nullable=False)
    remaining_kg = Column(Double, nullable=False)        # stok lot yang belum masuk batch
    verification_code = Column(String(40), unique=True, nullable=True)
    evidence_photo_url = Column(Text, nullable=True)
    inspector_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    note = Column(Text, nullable=True)
    rejected_kg = Column(Double, nullable=False, default=0.0)   # karung disortir keluar (basah/berjamur), tidak dibayar
    # Refraksi: kg basis kering setara kadar air acuan kontrak; refraction_kg = selisih yang "dipotong" di nota
    refraction_kg = Column(Double, nullable=False, default=0.0)
    dry_basis_kg = Column(Double, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class ManufacturingBatch(Base):
    __tablename__ = "manufacturing_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_code = Column(String(50), unique=True, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    operating_hours = Column(Double, nullable=True)
    pyrolysis_temp_c = Column(Double, nullable=True)
    pellet_share = Column(Double, nullable=False)
    silica_share_of_biochar = Column(Double, nullable=False)
    silica_route = Column(String(16), nullable=False, default="biochar")
    silica_husk_share = Column(Double, nullable=False, default=0.0)
    input_kg = Column(Double, nullable=False)
    closure_error_pct = Column(Double, nullable=False)
    closure_ok = Column(Integer, nullable=False)              # 1/0 (portabel SQLite & PG)
    economics = Column(JSON, nullable=False)                 # snapshot hasil Engine ⑪ + parameter saat itu
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class BatchInput(Base):
    __tablename__ = "batch_inputs"
    __table_args__ = (CheckConstraint("input_kg > 0", name="ck_bi_pos"),
                      UniqueConstraint("batch_id", "qc_id", name="uq_batch_lot"))

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("manufacturing_batches.id"), nullable=False, index=True)
    qc_id = Column(Integer, ForeignKey("inbound_qc.id"), nullable=False, index=True)
    input_kg = Column(Double, nullable=False)
    moisture = Column(Double, nullable=False)


class BatchOutput(Base):
    """Satu baris per produk (Bill of Materials terbalik: 1 input sekam → 3 output).
    expected_kg = model Engine ⑪ untuk mutu lot yang sama; yield_pct = output ÷ input batch."""
    __tablename__ = "batch_outputs"
    __table_args__ = (CheckConstraint("quantity_kg >= 0", name="ck_bo_nonneg"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("manufacturing_batches.id"), nullable=False, index=True)
    product = Column(String(12), nullable=False)               # bio_pellet | biochar | bio_silika
    quantity_kg = Column(Double, nullable=False)
    expected_kg = Column(Double, nullable=True)
    yield_pct = Column(Double, nullable=True)
    yield_variance_pct = Column(Double, nullable=True)
    quality = Column(JSON, nullable=True)


class FinishedGoodsMovement(Base):
    """Buku stok produk jadi (append-only). Produksi batch = masuk (+), penjualan/penyesuaian = keluar (−).
    Saldo per produk = Σ quantity_kg — tidak pernah disimpan sebagai angka yang bisa diubah."""
    __tablename__ = "finished_goods_movements"
    __table_args__ = (
        CheckConstraint("product IN ('bio_pellet', 'biochar', 'bio_silika')", name="ck_fg_product"),
        CheckConstraint("movement IN ('produksi', 'penjualan', 'penyesuaian', 'retur_pelanggan', 'alokasi_petani')",
                        name="ck_fg_movement"),
        CheckConstraint("quantity_kg <> 0", name="ck_fg_nonzero"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    product = Column(String(12), nullable=False, index=True)
    movement = Column(String(16), nullable=False)
    quantity_kg = Column(Double, nullable=False)                 # bertanda: + masuk, − keluar
    batch_id = Column(Integer, ForeignKey("manufacturing_batches.id"), nullable=True, index=True)
    unit_price_rp = Column(Double, nullable=True)
    reference = Column(String(80), nullable=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class ReturnReason(str, enum.Enum):
    BASAH = "basah"
    BERJAMUR = "berjamur"
    KONTAMINAN = "kontaminan"
    SELISIH_BERAT = "selisih_berat"
    STOK_TIDAK_ADA = "stok_tidak_ada"
    DIBATALKAN_PENGEPUL = "dibatalkan_pengepul"
    LAINNYA = "lainnya"


class ReturnDisposition(str, enum.Enum):
    PENDING = "menunggu"
    RETURN_TO_SENDER = "kembalikan_ke_pengirim"
    REDRY = "keringkan_ulang"
    DOWNGRADE = "turun_grade"
    BOILER_FUEL = "bahan_bakar_boiler"
    DISPOSE = "musnahkan"


class ReturnCase(Base):
    """Kasus retur / karantina sekam yang ditolak (seluruh lot atau sebagian karung).

    Dibuka otomatis saat pabrik menolak muatan / QC menolak lot / sortir sebagian, atau manual.
    Barang fisik berada di `location` sampai disposisi diputuskan; biaya penanganan dibebankan ke
    `cost_bearer` (pihak yang terakhir menimbang & menyatakan lolos mutu)."""
    __tablename__ = "return_cases"
    __table_args__ = (
        CheckConstraint("quantity_kg > 0", name="ck_ret_qty"),
        CheckConstraint("handling_cost_rp IS NULL OR handling_cost_rp >= 0", name="ck_ret_cost"),
        CheckConstraint("harvest_id IS NOT NULL OR qc_id IS NOT NULL OR request_id IS NOT NULL", name="ck_ret_ref"),
        CheckConstraint("status IN ('terbuka', 'selesai')", name="ck_ret_status"),
        CheckConstraint("(status = 'selesai') = (disposition <> 'menunggu')", name="ck_ret_resolved"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    harvest_id = Column(Integer, ForeignKey("harvests.id"), nullable=True, index=True)
    request_id = Column(Integer, ForeignKey("delivery_requests.id"), nullable=True, index=True)
    qc_id = Column(Integer, ForeignKey("inbound_qc.id"), nullable=True, index=True)
    stage = Column(String(20), nullable=False)                   # gerbang_pabrik | qc_pabrik | pengepul
    reason_code = Column(_enum(ReturnReason), nullable=False)
    moisture = Column(Double, nullable=True)
    quantity_kg = Column(Double, nullable=False)
    location = Column(String(20), nullable=False, default="pabrik")    # pabrik | pengepul | petani
    disposition = Column(_enum(ReturnDisposition), nullable=False, default=ReturnDisposition.PENDING)
    cost_bearer = Column(String(10), nullable=True)              # petani | pengepul | pabrik
    handling_cost_rp = Column(Double, nullable=True)
    status = Column(String(8), nullable=False, default="terbuka", index=True)
    evidence_photo_url = Column(Text, nullable=True)
    note = Column(Text, nullable=True)
    opened_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    resolved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolution_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class BatchLoss(Base):
    __tablename__ = "batch_losses"
    __table_args__ = (CheckConstraint("quantity_kg >= 0", name="ck_bl_nonneg"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("manufacturing_batches.id"), nullable=False, index=True)
    kind = Column(String(20), nullable=False)   # air | volatil_syngas | gas_pembakaran | residu_ekstraksi | susut_proses
    quantity_kg = Column(Double, nullable=False)


class BatchCost(Base):
    __tablename__ = "batch_costs"
    __table_args__ = (CheckConstraint("amount_rp >= 0", name="ck_bc_nonneg"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("manufacturing_batches.id"), nullable=False, index=True)
    cost_type = Column(String(10), nullable=False)            # variabel | tetap
    item = Column(String(40), nullable=False)
    driver_qty = Column(Double, nullable=True)
    driver_unit = Column(String(20), nullable=True)
    rate = Column(Double, nullable=True)
    amount_rp = Column(Double, nullable=False)
    product = Column(String(12), nullable=True)               # NULL = biaya bersama; terisi = biaya terpisah


class SettlementStatus(str, enum.Enum):
    PENDING_PRICE = "menunggu_harga"     # harga belum dapat ditentukan (harga jual produk belum diisi)
    PAYABLE = "terutang"                 # harga & jumlah final, menunggu transfer
    PAID = "dibayar"


class CollectorSettlement(Base):
    """Kewajiban bayar pabrik → pengepul. SATU tabel untuk kedua jalur pasokan:
    'qc'   = Delivery Request + QC masuk (harga kontrak, disesuaikan basis kering);
    'rute' = sekam diangkut armada pabrik lalu ditimbang terima (harga diisi pabrik / engine pricing)."""
    __tablename__ = "collector_settlements"
    __table_args__ = (
        CheckConstraint("payable_kg >= 0", name="ck_settle_kg"),
        CheckConstraint("amount_rp IS NULL OR amount_rp >= 0", name="ck_settle_amount"),
        CheckConstraint("(source = 'qc' AND qc_id IS NOT NULL) OR (source = 'rute' AND harvest_id IS NOT NULL)",
                        name="ck_settle_source"),
        CheckConstraint("(status = 'menunggu_harga') = (amount_rp IS NULL)", name="ck_settle_priced"),
        CheckConstraint("status IN ('menunggu_harga', 'terutang', 'dibayar')", name="ck_settle_status"),
        CheckConstraint("status != 'dibayar' OR payment_reference IS NOT NULL", name="ck_settle_paid_ref"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    source = Column(String(4), nullable=False)                       # qc | rute
    qc_id = Column(Integer, ForeignKey("inbound_qc.id"), nullable=True, unique=True)
    harvest_id = Column(Integer, ForeignKey("harvests.id"), nullable=True, unique=True)
    payable_kg = Column(Double, nullable=False)
    moisture = Column(Double, nullable=True)
    price_per_kg = Column(Double, nullable=True)
    amount_rp = Column(Double, nullable=True)
    price_basis = Column(Text, nullable=True)
    status = Column(_enum(SettlementStatus), nullable=False, index=True)
    payment_reference = Column(String(80), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)
    priced_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)


class SettlementEvent(Base):
    """Jejak audit perubahan harga dan status tagihan (append-only)."""
    __tablename__ = "settlement_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    settlement_id = Column(Integer, ForeignKey("collector_settlements.id"), nullable=False, index=True)
    action = Column(String(20), nullable=False)                      # dibuat | harga | dibayar
    old_price = Column(Double, nullable=True)
    new_price = Column(Double, nullable=True)
    old_amount = Column(Double, nullable=True)
    new_amount = Column(Double, nullable=True)
    reason = Column(Text, nullable=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)



class LogisticsCharge(Base):
    """Potongan logistik yang ditanggung pengepul (ongkos jarak kosong saat batal / stok tidak ada ketika truk tiba).
    Dipotong otomatis dari tagihan pabrik → pengepul berikutnya saat ditandai lunas (status dipotong)."""
    __tablename__ = "logistics_charges"
    __table_args__ = (
        CheckConstraint("amount_rp >= 0", name="ck_lch_amount"),
        CheckConstraint("kind IN ('batal_pembelian', 'stop_gagal')", name="ck_lch_kind"),
        CheckConstraint("status IN ('terbuka', 'dipotong', 'dibebaskan')", name="ck_lch_status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    kind = Column(String(20), nullable=False)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=True)
    stop_id = Column(Integer, ForeignKey("route_stops.id"), nullable=True, unique=True)
    harvest_id = Column(Integer, ForeignKey("harvests.id"), nullable=True)
    km = Column(Double, nullable=True)
    amount_rp = Column(Numeric(14, 0), nullable=False)
    status = Column(String(12), nullable=False, default="terbuka", index=True)
    settlement_id = Column(Integer, ForeignKey("collector_settlements.id"), nullable=True)
    reason = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
