"""Penjaga demo publik (PUBLIC_DEMO=true, mis. deploy Vercel yang URL-nya dibagikan).

Akun demo dipakai bersama oleh semua pengunjung, jadi satu pengunjung tidak boleh merusak demo untuk yang lain:
- akun admin tidak ditampilkan di halaman login (password diambil dari DEMO_ADMIN_PASSWORD),
- reset/seed ulang database dimatikan,
- akun demo bersama tidak bisa diganti password-nya atau dihapus (hak hapus PDP) — akun buatan sendiri tetap bisa.
"""

from fastapi import HTTPException

from ..config import settings


def shared_demo_usernames() -> set[str]:
    from ..seed import DEMO_ACCOUNTS
    return {a["username"] for a in DEMO_ACCOUNTS}


def visible_demo_accounts() -> list[dict]:
    from ..seed import DEMO_ACCOUNTS
    if not settings.PUBLIC_DEMO:
        return DEMO_ACCOUNTS
    return [a for a in DEMO_ACCOUNTS if a["role"] != "admin"]


def demo_password(account: dict) -> str:
    if account["role"] == "admin" and settings.DEMO_ADMIN_PASSWORD:
        return settings.DEMO_ADMIN_PASSWORD
    return account["password"]


def forbid_in_public_demo(action: str) -> None:
    if settings.PUBLIC_DEMO:
        raise HTTPException(403, f"{action} dinonaktifkan di demo publik.")


def forbid_shared_account_change(username: str | None, action: str) -> None:
    if settings.PUBLIC_DEMO and username in shared_demo_usernames():
        raise HTTPException(403, f"{action} tidak diizinkan untuk akun demo bersama di demo publik. "
                                 "Daftarkan akun sendiri untuk mencobanya.")
