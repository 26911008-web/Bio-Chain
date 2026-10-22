"""Kunci baris yang bekerja di PostgreSQL DAN SQLite.

`SELECT ... FOR UPDATE` diabaikan SQLite (mode cadangan lapangan), sehingga pola "baca saldo/status → cek → tulis" bisa
lolos ganda di sana. UPDATE kosong (`SET id = id`) sebagai pernyataan PERTAMA transaksi:
  * PostgreSQL — mengunci baris (sama seperti FOR UPDATE) hingga commit;
  * SQLite     — mengambil kunci penulis, sehingga transaksi lain menunggu dan membaca data setelah commit.
"""

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession


async def lock_row(db: AsyncSession, model, pk) -> bool:
    res = await db.execute(update(model).where(model.id == pk).values(id=model.id)
                           .execution_options(synchronize_session=False))
    return res.rowcount == 1
