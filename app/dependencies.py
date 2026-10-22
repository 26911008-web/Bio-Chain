"""Authentication & authorization dependencies.

JWT-based auth with role guard untuk multi-persona access control.
Login via nomor telepon — cocok untuk semua level literasi.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .config import settings
from .database import get_db
from .models.user import User, UserRole
from .security.rls import apply_now, bind_identity

security = HTTPBearer(auto_error=False)


# Saat akun wajib ganti password (reset admin), hanya jalur ini yang boleh dipakai — ditegakkan di server.
MUST_CHANGE_ALLOWED = ("/api/v1/auth/me", "/api/v1/auth/change-password", "/api/v1/me/")


def create_access_token(user_id: int, role: str, token_version: int = 0) -> str:
    """Buat JWT access token dengan payload {sub, role, tv, iat, exp}. `tv` = users.token_version."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "role": role, "tv": int(token_version or 0), "iat": now, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Dependency: extract dan validasi user dari JWT token."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token diperlukan")

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = int(payload["sub"])
        token_role = payload.get("role")
        token_version = int(payload.get("tv", 0))
    except (jwt.ExpiredSignatureError,):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token kedaluwarsa")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token tidak valid")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User tidak ditemukan atau nonaktif")
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    if token_role != role:
        # Role diubah admin setelah token terbit → token lama tidak boleh membawa hak lama.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Peran akun berubah; silakan login ulang")
    if token_version != int(user.token_version or 0):
        # Password diganti/direset setelah token terbit → semua sesi lama (HP hilang, dipinjam) berakhir.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesi berakhir karena password diganti; silakan login ulang")
    if user.must_change_password and not request.url.path.startswith(MUST_CHANGE_ALLOWED):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ganti password sementara Anda terlebih dahulu.")

    # RLS PostgreSQL: semua query berikutnya di request ini dibatasi ke identitas ini.
    bind_identity(db, user.id, role)
    await apply_now(db)
    # Parameter asumsi yang diubah di proses worker lain terbaca dalam ≤ 30 detik
    from .services.params_store import maybe_refresh
    await maybe_refresh(db)
    return user


def require_role(*allowed_roles: UserRole):
    """Dependency factory: hanya izinkan role tertentu mengakses endpoint.

    Contoh:
        @router.get("/admin-only")
        async def admin_endpoint(user = Depends(require_role(UserRole.ADMIN))):
            ...
    """
    async def role_checker(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        user_role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
        if user_role_str not in [r.value for r in allowed_roles]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Akses ditolak. Dibutuhkan role: {', '.join(r.value for r in allowed_roles)}",
            )
        return user
    return role_checker
