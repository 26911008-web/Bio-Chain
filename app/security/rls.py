"""Row-Level Security: teruskan identitas pengguna ke PostgreSQL di setiap transaksi.

Kebijakan RLS (migrations/004_row_level_security.sql) membaca `app.user_id` dan `app.role`.
Nilai diset dengan `set_config(..., true)` = SET LOCAL, sehingga hilang di akhir transaksi dan aman
untuk PgBouncer transaction pooling. Hook `after_begin` memasang ulang identitas di SETIAP transaksi
baru pada sesi yang sama (mis. setelah rollback di tengah request), jadi tidak ada query yang
berjalan tanpa identitas. SQLite tidak punya RLS → hook tidak melakukan apa pun.
"""

from sqlalchemy import event, text
from sqlalchemy.orm import Session

RLS_KEY = "rls_identity"
SYSTEM_IDENTITY = ("0", "system")          # seed / tugas internal


def bind_identity(session, user_id: int | str, role: str) -> None:
    """Tandai sesi (AsyncSession atau Session) dengan identitas untuk transaksi berikutnya."""
    sync = getattr(session, "sync_session", session)
    sync.info[RLS_KEY] = (str(user_id), role)


async def apply_now(session) -> None:
    """Pasang identitas ke transaksi yang SUDAH berjalan (after_begin hanya untuk yang baru)."""
    sync = session.sync_session
    ident = sync.info.get(RLS_KEY)
    if ident and session.bind.dialect.name == "postgresql":
        await session.execute(text("SELECT set_config('app.user_id', :u, true), set_config('app.role', :r, true)"),
                              {"u": ident[0], "r": ident[1]})


@event.listens_for(Session, "after_begin")
def _set_identity(session, transaction, connection):
    ident = session.info.get(RLS_KEY)
    if ident and connection.dialect.name == "postgresql":
        connection.execute(text("SELECT set_config('app.user_id', :u, true), set_config('app.role', :r, true)"),
                           {"u": ident[0], "r": ident[1]})
