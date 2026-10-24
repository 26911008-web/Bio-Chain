"""Layanan Notifikasi Perubahan Transaksi Biomassa Lintas Persona (Real-Time & Persistent).

Mengelompokkan notifikasi ke dalam 4 kategori status:
- 🟡 PENDING_ACTION: Menunggu verifikasi, persetujuan harga, konfirmasi jadwal, atau pembayaran.
- 🔵 IN_PROGRESS: Dalam perjalanan armada supir, proses QC gerbang, atau pirolisis aktif.
- 🟢 COMPLETED: Pembayaran lunas, konversi selesai & dompet terisi, atau abu bottom ash diserahkan ke sawah.
- 🔴 ALERT_DISCREPANCY: Susut di luar toleransi, penolakan mutu, atau tagihan lewat jatuh tempo.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, exists, func, insert, or_, select, true, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.harvest import Harvest, HarvestStatus
from ..models.ledger import CustodyEvent
from ..models.notification import Notification, NotificationRead, NotificationStatusGroup
from ..models.user import User, UserRole

_now = lambda: datetime.now(timezone.utc)

STATUS_GROUP_LABELS = {
    "PENDING_ACTION": {
        "label": "Menunggu Tindakan",
        "icon": "🟡",
        "badge": "badge-amber",
        "desc": "Perlu verifikasi kuantitas, persetujuan harga, jadwal jemput, atau pembayaran",
    },
    "IN_PROGRESS": {
        "label": "Dalam Proses & Logistik",
        "icon": "🔵",
        "badge": "badge-blue",
        "desc": "Armada sedang menjemput, antrean jembatan timbang, atau konversi pabrik aktif",
    },
    "COMPLETED": {
        "label": "Selesai & Lunas",
        "icon": "🟢",
        "badge": "badge-green",
        "desc": "Transaksi berhasil diverifikasi, pembayaran tuntas, atau sirkular sawah terpenuhi",
    },
    "ALERT_DISCREPANCY": {
        "label": "Perhatian & Refraksi",
        "icon": "🔴",
        "badge": "badge-red",
        "desc": "Susut timbangan tinggi, penolakan mutu kadar air, atau selisih klaim",
    },
}


async def record_notification(
    db: AsyncSession,
    *,
    event_type: str,
    title: str,
    message: str,
    status_group: str = "PENDING_ACTION",
    target_role: str = "all",
    user_id: int | None = None,
    harvest_id: int | None = None,
    transaction_code: str | None = None,
    actor_role: str | None = None,
    actor_name: str | None = None,
    action_type: str = "trace",
    action_payload: str | None = None,
    created_at: datetime | None = None,
) -> Notification:
    """Mencatat entri notifikasi baru ke database."""
    notif = Notification(
        event_type=event_type,
        title=title,
        message=message,
        status_group=status_group,
        target_role=target_role,
        user_id=user_id,
        harvest_id=harvest_id,
        transaction_code=transaction_code,
        actor_role=actor_role,
        actor_name=actor_name,
        action_type=action_type,
        action_payload=action_payload or transaction_code,
        created_at=created_at or _now(),
        is_read=False,
    )
    db.add(notif)
    await db.flush()
    return notif


_seed_checked = False


def _val(x: Any) -> str:
    return x.value if hasattr(x, "value") else str(x)


def _read_by(user: User) -> Any:
    """Sudah dibaca OLEH pengguna ini: milik sendiri → kolom is_read; lainnya → baris notification_reads."""
    own = and_(Notification.user_id.is_not(None), Notification.user_id == user.id, Notification.is_read.is_(True))
    other = exists().where(NotificationRead.notification_id == Notification.id, NotificationRead.user_id == user.id)
    return or_(own, other)


def _visibility_filter(user: User) -> Any:
    """Notifikasi yang boleh dilihat/ditandai seorang pengguna.

    Notifikasi bertuan (user_id terisi) hanya untuk pemiliknya, walau target_role juga terisi: pemanggil
    seperti farmer.py & custody.py mengisi keduanya, dan filter lama `user_id == me OR target_role == peran`
    membuat setiap petani melihat laporan/penolakan petani lain (dan pengepul melihat tawaran pengepul lain).
    Siaran (user_id kosong) tetap per peran. Admin & auditor melihat semua.
    """
    u_role = user.role.value if hasattr(user.role, "value") else str(user.role)
    if u_role in ("admin", "auditor"):
        return true()
    return (Notification.user_id == user.id) | (
        Notification.user_id.is_(None) & Notification.target_role.in_([u_role, "all"])
    )


async def get_persona_notifications(
    db: AsyncSession,
    user: User,
    status_group: str | None = None,
    limit: int = 60,
) -> dict[str, Any]:
    """Mengambil notifikasi relevan untuk persona aktif yang dikelompokkan berdasarkan status."""
    await ensure_seed_notifications(db, user)

    u_role = user.role.value if hasattr(user.role, "value") else str(user.role)
    role_filter = _visibility_filter(user)

    # Base query
    read_col = _read_by(user).label("read_by_me")
    base_stmt = select(Notification, read_col).where(role_filter)
    if status_group and status_group in STATUS_GROUP_LABELS:
        base_stmt = base_stmt.where(Notification.status_group == status_group)

    rows = (await db.execute(base_stmt.order_by(Notification.id.desc()).limit(limit))).all()

    # Hitung jumlah belum dibaca dan per grup status
    counts_by_group = {k: 0 for k in STATUS_GROUP_LABELS}
    count_stmt = select(Notification.status_group, func.count(Notification.id)).where(role_filter).group_by(Notification.status_group)
    res_counts = (await db.execute(count_stmt)).all()
    for grp, cnt in res_counts:
        if grp in counts_by_group:
            counts_by_group[grp] = cnt

    unread_stmt = select(func.count(Notification.id)).where(role_filter, ~_read_by(user))
    unread_count = (await db.execute(unread_stmt)).scalar() or 0

    # Kelompokkan item
    grouped_items = {k: [] for k in STATUS_GROUP_LABELS}
    serialized_all = []

    for n, read_by_me in rows:
        serialized = {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "status_group": n.status_group,
            "status_meta": STATUS_GROUP_LABELS.get(n.status_group, STATUS_GROUP_LABELS["PENDING_ACTION"]),
            "event_type": n.event_type,
            "transaction_code": n.transaction_code,
            "harvest_id": n.harvest_id,
            "actor_role": n.actor_role,
            "actor_name": n.actor_name,
            "action_type": n.action_type,
            "action_payload": n.action_payload,
            "is_read": bool(read_by_me),
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        serialized_all.append(serialized)
        if n.status_group in grouped_items:
            grouped_items[n.status_group].append(serialized)

    return {
        "persona": u_role,
        "user_name": user.full_name or user.username,
        "unread_count": unread_count,
        "total_count": sum(counts_by_group.values()),
        "counts_by_group": counts_by_group,
        "group_meta": STATUS_GROUP_LABELS,
        "grouped_items": grouped_items,
        "items": serialized_all,
    }


async def mark_notification_read(db: AsyncSession, notif_id: int, user: User) -> bool:
    """Tandai satu notifikasi telah dibaca."""
    n = (await db.execute(select(Notification.id, Notification.user_id)
                          .where(Notification.id == notif_id, _visibility_filter(user)))).first()
    if n is None:
        return False
    if n.user_id == user.id:
        await db.execute(update(Notification).where(Notification.id == notif_id).values(is_read=True))
    else:
        already = (await db.execute(select(NotificationRead.notification_id).where(
            NotificationRead.notification_id == notif_id, NotificationRead.user_id == user.id))).first()
        if already is None:
            db.add(NotificationRead(user_id=user.id, notification_id=notif_id))
    await db.commit()
    return True


async def mark_all_notifications_read(db: AsyncSession, user: User) -> int:
    """Tandai seluruh notifikasi persona aktif telah dibaca."""
    role_filter = _visibility_filter(user)
    own = await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    others = (await db.execute(
        select(Notification.id).where(role_filter, or_(Notification.user_id.is_(None), Notification.user_id != user.id),
                                      ~_read_by(user))
    )).scalars().all()
    if others:
        await db.execute(insert(NotificationRead), [{"user_id": user.id, "notification_id": i} for i in others])
    await db.commit()
    return (own.rowcount or 0) + len(others)


async def ensure_seed_notifications(db: AsyncSession, user: User | None = None) -> None:
    """Mengisi notifikasi awal yang komprehensif bila tabel notifikasi masih kosong atau belum lengkap."""
    global _seed_checked
    if _seed_checked:            # dipanggil di setiap polling (25 s/pengguna): cukup sekali per proses
        return
    # PostgreSQL ber-RLS (migrasi 027): pengguna biasa hanya melihat notifikasinya sendiri, sehingga hitungan di
    # bawah akan selalu "kurang" dan seed terulang. Cek hanya dengan identitas yang melihat semua baris.
    if db.bind.dialect.name == "postgresql" and user is not None and _val(user.role) not in ("admin", "auditor"):
        return
    cnt = (await db.execute(select(func.count(Notification.id)))).scalar() or 0
    existing_roles = (await db.execute(select(Notification.target_role).distinct())).scalars().all()
    all_needed = {"petani", "pengepul", "driver", "pabrik", "auditor"}
    if cnt >= 15 and all_needed.issubset(set(existing_roles)):
        _seed_checked = True
        return

    now = _now()

    # 1. Seed notifikasi komprehensif lintas persona & 4 grup status
    seeds = [
        # === 🟡 PENDING_ACTION ===
        {
            "event_type": "OFFER_PENDING_VERIFICATION",
            "title": "🌾 Penawaran Menunggu Verifikasi (WR-HV-0006)",
            "message": "Laporan pasokan 2.500 kg sekam padi telah terkirim dan sedang menunggu verifikasi kuantitas & harga dari Pengepul.",
            "status_group": "PENDING_ACTION",
            "target_role": "petani",
            "transaction_code": "WR-HV-0006",
            "actor_role": "petani",
            "actor_name": "Pak Sugeng (Petani)",
            "action_type": "trace",
            "action_payload": "WR-HV-0006",
        },
        {
            "event_type": "NEW_OFFER_TO_VERIFY",
            "title": "📦 Penawaran Masuk: 2.500 kg Sekam Padi",
            "message": "Petani Sugeng mendaftarkan panen di Penggilingan Berkah. Mohon lakukan pengecekan timbangan dan penetapan harga beli.",
            "status_group": "PENDING_ACTION",
            "target_role": "pengepul",
            "transaction_code": "WR-HV-0006",
            "actor_role": "petani",
            "actor_name": "Pak Sugeng",
            "action_type": "action",
            "action_payload": "verify_offer",
        },
        {
            "event_type": "ROUTE_DISPATCH_ASSIGNED",
            "title": "🚚 Tugas Jemput Armada Tersedia (DSP-RT-01)",
            "message": "Rute penjemputan Sleman Barat telah aktif. Terdapat 2 titik jemput biomassa menunggu konfirmasi pengemudi.",
            "status_group": "PENDING_ACTION",
            "target_role": "driver",
            "transaction_code": "DSP-RT-01",
            "actor_role": "pengepul",
            "actor_name": "Logistik KUD",
            "action_type": "trace",
            "action_payload": "DSP-RT-01",
        },
        {
            "event_type": "GATE_TRUCK_WAITING",
            "title": "🏭 Truk Masuk Antrean Jembatan Timbang",
            "message": "Truk AB 8421 CS (Budi Santoso) tiba di pos gerbang pabrik membawa 5.200 kg biomassa. Menunggu penimbangan bruto & sampling QC.",
            "status_group": "PENDING_ACTION",
            "target_role": "pabrik",
            "transaction_code": "TIK-GATE-0021",
            "actor_role": "driver",
            "actor_name": "Budi Santoso",
            "action_type": "action",
            "action_payload": "gate_weighing",
        },
        {
            "event_type": "AUDIT_REVIEW_PENDING",
            "title": "🔍 Laporan Compliance Rantai Pasok Siap Ditinjau",
            "message": "Penutupan batch biomassa bulan berjalan memerlukan verifikasi kepatuhan ESG & sirkularitas karbon.",
            "status_group": "PENDING_ACTION",
            "target_role": "auditor",
            "transaction_code": "AUD-202610-01",
            "actor_role": "admin",
            "actor_name": "Sistem Bio-Chain",
            "action_type": "trace",
            "action_payload": "AUD-202610-01",
        },

        # === 🔵 IN_PROGRESS ===
        {
            "event_type": "DRIVER_EN_ROUTE",
            "title": "🚛 Armada Supir OTW Menjemput Biomassa",
            "message": "Supir Budi Santoso (Truk Colt Diesel AB 8421 CS) sedang dalam perjalanan menuju lokasi penggilingan Anda (Est. tiba 20 mnt).",
            "status_group": "IN_PROGRESS",
            "target_role": "petani",
            "transaction_code": "DO-TRUCK-0006",
            "actor_role": "driver",
            "actor_name": "Budi Santoso (Armada)",
            "action_type": "trace",
            "action_payload": "WR-HV-0006",
        },
        {
            "event_type": "DELIVERY_IN_TRANSIT",
            "title": "🚚 Pengiriman Konsolidasi ke Pabrik Berjalan",
            "message": "Armada pembawa 5.200 kg biomassa sekam terverifikasi sedang transit menuju Pabrik Indmira Sleman.",
            "status_group": "IN_PROGRESS",
            "target_role": "pengepul",
            "transaction_code": "DSP-DELIV-0014",
            "actor_role": "driver",
            "actor_name": "Armada Logistik",
            "action_type": "trace",
            "action_payload": "DSP-DELIV-0014",
        },
        {
            "event_type": "TRIP_ACTIVE",
            "title": "🧭 Penjemputan Aktif Menuju Titik 2",
            "message": "Perjalanan menuju Penggilingan Moyudan sedang berlangsung. GPS pelacak logistik tersimpan aktif.",
            "status_group": "IN_PROGRESS",
            "target_role": "driver",
            "transaction_code": "DSP-RT-01",
            "actor_role": "driver",
            "actor_name": "Supir Budi",
            "action_type": "trace",
            "action_payload": "DSP-RT-01",
        },
        {
            "event_type": "PYROLYSIS_PROCESSING",
            "title": "⚗️ Reaktor Pirolisis Aktif (Batch PRD-04)",
            "message": "Pengolahan 8.000 kg biomassa terblending pada Ramp-01 sedang berlangsung di temperatur 480°C (Progres 65%).",
            "status_group": "IN_PROGRESS",
            "target_role": "pabrik",
            "transaction_code": "BATCH-PRD-0004",
            "actor_role": "pabrik",
            "actor_name": "Operator Pirolisis",
            "action_type": "trace",
            "action_payload": "BATCH-PRD-0004",
        },
        {
            "event_type": "CARBON_CHAIN_SYNC",
            "title": "📊 Komputasi Jejak Karbon GHG Berjalan",
            "message": "Sinkronisasi kalkulasi emisi Scope 1, 2, dan 3 sedang dihitung dari data rute GPS dan konversi pabrik.",
            "status_group": "IN_PROGRESS",
            "target_role": "auditor",
            "transaction_code": "GHG-SYNC-002",
            "actor_role": "system",
            "actor_name": "Engine Emisi",
            "action_type": "trace",
            "action_payload": "GHG-SYNC-002",
        },

        # === 🟢 COMPLETED ===
        {
            "event_type": "PAYMENT_AND_BIOCHAR_CREDITED",
            "title": "💰 Pembayaran Lunas & +285 kg Saldo Abu Bottom Ash",
            "message": "Pembayaran hasil jual biomassa sebesar Rp 1.029.000 telah berhasil ditransfer. Saldo muatan balik 285 kg abu bottom ash sawah telah masuk ke Dompet Abu Anda.",
            "status_group": "COMPLETED",
            "target_role": "petani",
            "transaction_code": "TRX-PAY-0006",
            "actor_role": "pengepul",
            "actor_name": "KUD Sleman Mandiri",
            "action_type": "trace",
            "action_payload": "WR-HV-0006",
        },
        {
            "event_type": "FACTORY_PAYMENT_SETTLED",
            "title": "💳 Tagihan Pabrik Lunas (INV-202610-008)",
            "message": "Pabrik Indmira telah menyelesaikan pembayaran invoice Rp 2.450.000 untuk pengiriman biomassa 5.000 kg.",
            "status_group": "COMPLETED",
            "target_role": "pengepul",
            "transaction_code": "INV-202610-008",
            "actor_role": "pabrik",
            "actor_name": "Finance Pabrik",
            "action_type": "trace",
            "action_payload": "INV-202610-008",
        },
        {
            "event_type": "DELIVERY_COMPLETED_SIGN",
            "title": "✅ Serah Terima Pabrik Selesai & Ditandatangani",
            "message": "Muatan seberat 5.120 kg sukses dibongkar di Ramp-01. Surat Jalan & Berita Acara timbang telah diverifikasi.",
            "status_group": "COMPLETED",
            "target_role": "driver",
            "transaction_code": "BAST-0021",
            "actor_role": "pabrik",
            "actor_name": "Timbang Pabrik",
            "action_type": "trace",
            "action_payload": "TIK-GATE-0021",
        },
        {
            "event_type": "CIRCULAR_CLOSED_LOOP",
            "title": "🔄 Sirkularitas 100% Terpenuhi (Batch 04)",
            "message": "Seluruh by-product abu bottom ash telah didistribusikan kembali ke kelompok tani sawah (biochar difokuskan untuk material baterai).",
            "status_group": "COMPLETED",
            "target_role": "pabrik",
            "transaction_code": "CIRC-LOOP-004",
            "actor_role": "pabrik",
            "actor_name": "Unit Sirkular",
            "action_type": "trace",
            "action_payload": "CIRC-LOOP-004",
        },
        {
            "event_type": "AUDIT_PASSPORT_CERTIFIED",
            "title": "🛡️ Paspor Sirkular Terkunci Hash SHA256",
            "message": "Integritas kriptografis rantai pasok lot #6 hingga muatan balik sawah telah tersertifikasi sah tanpa anomali.",
            "status_group": "COMPLETED",
            "target_role": "auditor",
            "transaction_code": "PASSPORT-006",
            "actor_role": "auditor",
            "actor_name": "Auditor ESG",
            "action_type": "trace",
            "action_payload": "6",
        },

        # === 🔴 ALERT_DISCREPANCY ===
        {
            "event_type": "QUALITY_MOISTURE_HIGH",
            "title": "⚠️ Kadar Air Biomassa 16.8% (Grade B)",
            "message": "Hasil uji kadar air biomassa di atas batas Grade A (12%). Diberlakukan penyesuaian harga acuan mutu. Disarankan penjemuran sebelum disetor.",
            "status_group": "ALERT_DISCREPANCY",
            "target_role": "petani",
            "transaction_code": "WR-HV-0005",
            "actor_role": "pengepul",
            "actor_name": "QC Pengepul",
            "action_type": "trace",
            "action_payload": "WR-HV-0005",
        },
        {
            "event_type": "WEIGHT_SHRINKAGE_HIGH",
            "title": "🔴 Susut Pengiriman Melebihi Toleransi (5.9%)",
            "message": "Selisih timbangan kirim pengepul (5.200 kg) vs terima pabrik (4.893 kg) tercatat susut 307 kg. Refraksi pembayaran Rp 122.800 diberlakukan.",
            "status_group": "ALERT_DISCREPANCY",
            "target_role": "pengepul",
            "transaction_code": "TIK-GATE-0019",
            "actor_role": "pabrik",
            "actor_name": "Jembatan Timbang",
            "action_type": "trace",
            "action_payload": "TIK-GATE-0019",
        },
        {
            "event_type": "DRIVER_DELAY_ALERT",
            "title": "⚠️ Keterlambatan Waktu Tempuh Armada > 45 Menit",
            "message": "Armada truk AB 8421 CS mengalami deviasi rute dan keterlambatan kedatangan di checkpoint 2 akibat kendala jalan.",
            "status_group": "ALERT_DISCREPANCY",
            "target_role": "driver",
            "transaction_code": "DSP-RT-01",
            "actor_role": "system",
            "actor_name": "Monitor Rute",
            "action_type": "trace",
            "action_payload": "DSP-RT-01",
        },
        {
            "event_type": "QC_ASH_CONTENT_EXCEEDED",
            "title": "🔴 Kadar Abu Biomassa Melebihi Spesifikasi (18.5%)",
            "message": "Biomassa sekam padi lot #22 melebihi batas abu boiler 16%. Dilakukan relokasi ke Ramp-03 untuk blending kompensasi dengan serbuk kayu.",
            "status_group": "ALERT_DISCREPANCY",
            "target_role": "pabrik",
            "transaction_code": "QC-RAMP-022",
            "actor_role": "pabrik",
            "actor_name": "Laboratorium Pabrik",
            "action_type": "trace",
            "action_payload": "QC-RAMP-022",
        },
        {
            "event_type": "AUDIT_DISCREPANCY_FLAG",
            "title": "⚠️ Anomali Selisih Timbangan Terdeteksi pada 2 Lot",
            "message": "Terdapat anomali susut > 5% pada pengiriman tanggal 15 Oktober. Perlu klarifikasi dokumen timbang basah vs kering.",
            "status_group": "ALERT_DISCREPANCY",
            "target_role": "auditor",
            "transaction_code": "ALERT-AUD-009",
            "actor_role": "system",
            "actor_name": "Audit Rules Engine",
            "action_type": "trace",
            "action_payload": "ALERT-AUD-009",
        },
    ]

    for item in seeds:
        await record_notification(
            db,
            event_type=item["event_type"],
            title=item["title"],
            message=item["message"],
            status_group=item["status_group"],
            target_role=item["target_role"],
            transaction_code=item.get("transaction_code"),
            actor_role=item.get("actor_role"),
            actor_name=item.get("actor_name"),
            action_type=item.get("action_type", "trace"),
            action_payload=item.get("action_payload"),
            created_at=now,
        )

    await db.commit()

