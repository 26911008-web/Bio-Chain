"""Muat & simpan parameter asumsi ke database (dengan audit)."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import params
from ..models.params import ParameterChange, SystemParameter
from ..models.user import User


async def load(db: AsyncSession) -> None:
    rows = (await db.execute(select(SystemParameter))).scalars().all()
    params._set_cache({r.key: r.value for r in rows})


async def maybe_refresh(db: AsyncSession) -> None:
    """Segarkan cache berkala agar perubahan dari proses worker lain ikut terbaca (≤ REFRESH_S detik)."""
    if params.needs_refresh():
        await load(db)


async def _notify_param_change(db: AsyncSession) -> None:
    try:
        bind = db.get_bind()
        if bind and bind.dialect.name == "postgresql":
            from sqlalchemy import text
            await db.execute(text("NOTIFY biochain_params_channel, 'reload'"))
    except Exception:
        pass


async def set_value(db: AsyncSession, key: str, value, user: User, reason: str) -> dict:
    d = params.REGISTRY.get(key)
    if d is None:
        raise LookupError(f"Parameter '{key}' tidak dikenal")
    await load(db)                                   # validasi lintas-parameter terhadap nilai terbaru
    clean = params.validate(d, value)
    params.cross_check(key, clean)
    old = params.P(key)
    row = await db.get(SystemParameter, key)
    if row is None:
        db.add(SystemParameter(key=key, value=clean, updated_by_id=user.id))
    else:
        row.value, row.updated_by_id = clean, user.id
    db.add(ParameterChange(key=key, old_value=old, new_value=clean, changed_by_id=user.id,
                           changed_by_role=user.role.value if hasattr(user.role, "value") else str(user.role),
                           reason=reason))
    await db.flush()
    await _notify_param_change(db)
    params._values[key] = clean
    return params.describe(key)


async def reset_value(db: AsyncSession, key: str, user: User, reason: str) -> dict:
    d = params.REGISTRY.get(key)
    if d is None:
        raise LookupError(f"Parameter '{key}' tidak dikenal")
    await load(db)
    params.cross_check(key, d.default)
    old = params.P(key)
    await db.execute(delete(SystemParameter).where(SystemParameter.key == key))
    db.add(ParameterChange(key=key, old_value=old, new_value=None, changed_by_id=user.id,
                           changed_by_role=user.role.value if hasattr(user.role, "value") else str(user.role),
                           reason=reason))
    await db.flush()
    await _notify_param_change(db)
    params._values.pop(key, None)
    return params.describe(key)


async def start_pg_listener(database_url: str):
    """Background task mendengarkan NOTIFY biochain_params_channel pada PostgreSQL (instant invalidation)."""
    import asyncio
    if not database_url.startswith("postgresql"):
        return
    url = database_url.replace("postgresql+asyncpg://", "postgresql://").replace("?ssl=", "?sslmode=")
    while True:
        try:
            import asyncpg
            conn = await asyncpg.connect(url)
            def on_notify(connection, pid, channel, payload):
                params.mark_stale()
            await conn.add_listener("biochain_params_channel", on_notify)
            try:
                while True:
                    await asyncio.sleep(3600)
            finally:
                await conn.close()
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(5)
