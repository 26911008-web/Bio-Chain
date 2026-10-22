"""Multi-biomassa Jawa (migrasi 018): master karakteristik, gudang pengepul + ledger stok, Poktan & ledger abu.

Prinsip lapangan:
  * nilai master = titik tengah literatur (docs/15) — hasil lab per lot selalu menang;
  * stok gudang = SUM ledger append-only (tidak ada saldo yang bisa ditimpa), idempoten untuk antrean offline;
  * abu ke lahan petani HANYA bila lulus uji logam berat (CHECK di DB, bukan sekadar aturan UI).
"""

from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, CheckConstraint, Column, DateTime, Double, ForeignKey, Integer, String, Text,
                        Index, event, func, text, true,
                        UniqueConstraint)

from ..database import Base

_now = lambda: datetime.now(timezone.utc)  # noqa: E731

OXIDES = ("sio2", "k2o", "na2o", "cao", "mgo", "fe2o3", "al2o3", "p2o5")
ASH_TYPES = ("fly_ash", "bottom_ash", "silica_ash")
ASH_STATUSES = ("tersedia", "dialokasikan", "diserahkan", "dibuang")
MOVEMENTS = ("masuk", "keluar", "susut", "koreksi")


class BiomassParameter(Base):
    __tablename__ = "biomass_parameters"
    __table_args__ = (
        CheckConstraint("moisture_typ_pct BETWEEN 0 AND 95 AND moisture_ref_pct BETWEEN 0 AND 95 "
                        "AND moisture_reject_pct > moisture_ref_pct", name="ck_bp_moisture"),
        CheckConstraint("ash_pct_db >= 0 AND ash_pct_db < 60", name="ck_bp_ash"),
        CheckConstraint("lhv_db_mj_kg > 5 AND lhv_db_mj_kg < 35", name="ck_bp_lhv"),
        CheckConstraint("base_price_per_kg IS NULL OR base_price_per_kg >= 0", name="ck_bp_price"),
    )

    code = Column(String(24), primary_key=True)
    name = Column(String(80), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())
    moisture_typ_pct = Column(Double, nullable=False)
    moisture_min_pct = Column(Double)
    moisture_max_pct = Column(Double)
    ash_pct_db = Column(Double, nullable=False)
    volatile_pct_db = Column(Double)
    fixed_carbon_pct_db = Column(Double)
    hhv_db_mj_kg = Column(Double)
    lhv_db_mj_kg = Column(Double, nullable=False)
    bulk_density_kg_m3 = Column(Double)
    carbon_pct_db = Column(Double)
    hydrogen_pct_db = Column(Double)
    nitrogen_pct_db = Column(Double)
    sulfur_pct_db = Column(Double)
    chlorine_pct_db = Column(Double)
    sio2_pct_ash = Column(Double)
    k2o_pct_ash = Column(Double)
    na2o_pct_ash = Column(Double)
    cao_pct_ash = Column(Double)
    mgo_pct_ash = Column(Double)
    fe2o3_pct_ash = Column(Double)
    al2o3_pct_ash = Column(Double)
    p2o5_pct_ash = Column(Double)
    moisture_ref_pct = Column(Double, nullable=False)
    moisture_reject_pct = Column(Double, nullable=False)
    contaminant_tol_pct = Column(Double, nullable=False, default=2.0, server_default="2")
    # Logam berat (Heavy Metals) - Standar EBC / IBI / Kementan
    pb_ppm = Column(Double, default=5.0)   # Timbal (Batas aman < 50 ppm)
    cd_ppm = Column(Double, default=0.2)   # Kadmium (Batas aman < 2 ppm)
    as_ppm = Column(Double, default=1.0)   # Arsenik (Batas aman < 10 ppm)
    base_price_per_kg = Column(Double, nullable=True)        # harga beli dasar — WAJIB diisi pabrik (tanpa bawaan)
    source = Column(Text, nullable=False)
    updated_by_id = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, server_default=func.now())


class CollectorWarehouse(Base):
    __tablename__ = "collector_warehouses"
    __table_args__ = (UniqueConstraint("collector_id", "name", name="uq_warehouse_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    lat = Column(Double)
    lon = Column(Double)
    capacity_m3 = Column(Double)
    is_covered = Column(Boolean, nullable=False, default=True, server_default=true())
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now, server_default=func.now())


class WarehouseStockMovement(Base):
    """Ledger stok append-only (PG: trigger forbid_mutation). Saldo = SUM(gross_kg / payable_kg)."""
    __tablename__ = "warehouse_stock_movements"
    __table_args__ = (
        CheckConstraint("movement IN ('masuk', 'keluar', 'susut', 'koreksi')", name="ck_wsm_movement"),
        CheckConstraint("(movement = 'masuk' AND gross_kg > 0) OR (movement IN ('keluar', 'susut') AND gross_kg < 0) "
                        "OR movement = 'koreksi'", name="ck_wsm_sign"),
        CheckConstraint("refraction_kg >= 0 AND (movement <> 'masuk' OR payable_kg <= gross_kg)", name="ck_wsm_refr"),
        CheckConstraint("(moisture_pct IS NULL OR moisture_pct BETWEEN 0 AND 95) AND "
                        "(contaminant_pct IS NULL OR contaminant_pct BETWEEN 0 AND 100)", name="ck_wsm_quality"),
        # satu lot pembelian hanya boleh dibukukan masuk gudang sekali (audit: lot bisa dicatat berulang)
        Index("uq_wsm_harvest_in", "harvest_id", unique=True,
              postgresql_where=text("movement = 'masuk' AND harvest_id IS NOT NULL"),
              sqlite_where=text("movement = 'masuk' AND harvest_id IS NOT NULL")),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    warehouse_id = Column(Integer, ForeignKey("collector_warehouses.id"), nullable=False, index=True)
    commodity = Column(String(24), ForeignKey("biomass_parameters.code"), nullable=False)
    movement = Column(String(12), nullable=False)
    gross_kg = Column(Double, nullable=False)
    moisture_pct = Column(Double)
    contaminant_pct = Column(Double)
    payable_kg = Column(Double, nullable=False)
    refraction_kg = Column(Double, nullable=False, default=0.0, server_default="0")
    refraction_basis = Column(JSON)
    harvest_id = Column(Integer, ForeignKey("harvests.id"))
    delivery_ref = Column(String(40))
    note = Column(Text)
    client_event_id = Column(String(64), unique=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now, server_default=func.now())


class FarmerGroup(Base):
    __tablename__ = "farmer_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    simluhtan_id = Column(String(40), unique=True)
    desa = Column(String(100))
    kecamatan = Column(String(100), nullable=False)
    kabupaten = Column(String(100), nullable=False)
    leader_user_id = Column(Integer, ForeignKey("users.id"))
    leader_name = Column(String(120), nullable=False)
    member_count = Column(Integer)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now, server_default=func.now())


class IndustrialAshLedger(Base):
    __tablename__ = "industrial_ash_ledgers"
    __table_args__ = (
        CheckConstraint("ash_type IN ('fly_ash', 'bottom_ash', 'silica_ash')", name="ck_ash_type"),
        CheckConstraint("quantity_kg > 0", name="ck_ash_qty"),
        CheckConstraint("heavy_metal_status IN ('belum_uji', 'lulus', 'gagal')", name="ck_ash_metal"),
        CheckConstraint("status IN ('tersedia', 'dialokasikan', 'diserahkan', 'dibuang')", name="ck_ash_status"),
        CheckConstraint("status IN ('tersedia', 'dibuang') OR heavy_metal_status = 'lulus'", name="ck_ash_only_pass_to_farm"),
        CheckConstraint("heavy_metal_status <> 'lulus' OR (pb_ppm IS NOT NULL AND cd_ppm IS NOT NULL "
                        "AND as_ppm IS NOT NULL AND lab_report_no IS NOT NULL)", name="ck_ash_lulus_needs_lab"),
        CheckConstraint("status NOT IN ('dialokasikan', 'diserahkan') OR farmer_group_id IS NOT NULL", name="ck_ash_alloc"),
        CheckConstraint("status <> 'diserahkan' OR (handover_photo_url IS NOT NULL AND handed_over_at IS NOT NULL "
                        "AND land_lat IS NOT NULL AND land_lon IS NOT NULL)", name="ck_ash_handover"),
        CheckConstraint("status <> 'dibuang' OR disposal_note IS NOT NULL", name="ck_ash_dispose"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(24), nullable=False, unique=True)
    factory_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ash_type = Column(String(12), nullable=False)
    source_commodity = Column(String(24), ForeignKey("biomass_parameters.code"))
    batch_id = Column(Integer, ForeignKey("manufacturing_batches.id"))
    quantity_kg = Column(Double, nullable=False)
    pb_ppm = Column(Double)
    cd_ppm = Column(Double)
    as_ppm = Column(Double)
    hg_ppm = Column(Double)
    cr_ppm = Column(Double)
    ni_ppm = Column(Double)
    lab_name = Column(String(120))
    lab_report_no = Column(String(80))
    lab_report_url = Column(Text)
    limits_snapshot = Column(JSON)
    heavy_metal_status = Column(String(10), nullable=False, default="belum_uji", server_default="belum_uji")
    k2o_pct = Column(Double)
    cao_pct = Column(Double)
    sio2_pct = Column(Double)
    ph = Column(Double)
    status = Column(String(12), nullable=False, default="tersedia", server_default="tersedia", index=True)
    farmer_group_id = Column(Integer, ForeignKey("farmer_groups.id"), index=True)
    land_lat = Column(Double)
    land_lon = Column(Double)
    land_area_ha = Column(Double)
    handover_photo_url = Column(Text)
    handed_over_at = Column(DateTime(timezone=True))
    handed_over_by_id = Column(Integer, ForeignKey("users.id"))
    disposal_note = Column(Text)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now, server_default=func.now())


class FeedstockParameter(Base):
    __tablename__ = "feedstock_parameters"

    code = Column(String(30), primary_key=True)
    name = Column(String(100), nullable=False)
    moisture_typical_pct = Column(Double, nullable=False)
    ash_typical_pct = Column(Double, nullable=False)
    lhv_typical_kcal_kg = Column(Double, nullable=False)
    bulk_density_kg_m3 = Column(Double, nullable=False, default=150.0)
    sio2_pct_ash = Column(Double, default=0.0)
    k2o_pct_ash = Column(Double, default=0.0)
    pb_max_ppm = Column(Double, nullable=False, default=50.0)
    cd_max_ppm = Column(Double, nullable=False, default=2.0)
    as_max_ppm = Column(Double, nullable=False, default=10.0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)



@event.listens_for(BiomassParameter.__table__, "after_create")
def _seed_on_create(target, connection, **kw):
    """Tabel baru (create_all: SQLite, skema uji PG) langsung berisi master → FK commodity 'sekam_padi' valid."""
    from ..biomass_seed import BIOMASS_SEED
    now = _now()
    connection.execute(target.insert(), [{**r, "is_active": True, "updated_at": now} for r in BIOMASS_SEED])
