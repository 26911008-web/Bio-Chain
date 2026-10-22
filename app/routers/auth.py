"""Router: Authentication — Register, Login, Me, Demo Accounts & Data Seeding.

Mendukung login via username atau nomor telepon + password.
Menyediakan daftar akun demo resmi dan utilitas reset data demo.
"""

from typing import Annotated
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..concurrency import run_cpu
from ..config import settings
from ..database import get_db
from ..dependencies import create_access_token, get_current_user, security
from ..models.user import User, UserRole, IncentiveTier

router = APIRouter()

# Role yang boleh daftar sendiri. Admin & auditor hanya dibuat oleh administrator.
SELF_SERVICE_ROLES = {UserRole.PETANI.value, UserRole.PENGEPUL.value, UserRole.DRIVER.value, UserRole.PABRIK.value}


def hash_password(password: str) -> str:
    """Hash password dengan PBKDF2-HMAC-SHA256 (600k iterasi).

    Format output: pbkdf2$<iterations>$<salt_hex>$<hash_hex>
    """
    salt = secrets.token_bytes(16)
    iterations = 600_000
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2${iterations}${salt.hex()}${h.hex()}"


_DUMMY_HASH: str | None = None


def _dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_hex(8))
    return _DUMMY_HASH


def verify_password(password: str, password_hash: str) -> bool:
    """Verifikasi password — mendukung PBKDF2 (baru) dan legacy salt$sha256.

    TIDAK mendukung plaintext matching (kerentanan C1 dihapus).
    """
    if not password_hash:
        return False

    # Format baru: pbkdf2$<iterations>$<salt_hex>$<hash_hex>
    if password_hash.startswith("pbkdf2$"):
        parts = password_hash.split("$")
        if len(parts) == 4:
            _, iterations_str, salt_hex, hash_hex = parts
            iterations = int(iterations_str)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(hash_hex)
            actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
            return secrets.compare_digest(actual, expected)
        return False

    # Legacy format: salt$sha256 (32 char hex salt)
    if "$" in password_hash:
        parts = password_hash.split("$")
        if len(parts) == 2 and len(parts[0]) == 32:
            salt, h = parts
            computed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
            return secrets.compare_digest(computed, h)

    return False


class RegisterRequest(BaseModel):
    username: str | None = None
    email: str | None = None
    phone: str = Field(..., min_length=8, max_length=20,
                       description="Nomor telepon (format: 08xxxxxxxxxx)")
    password: str = Field(..., min_length=4, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=100)
    role: str = Field("petani", description="petani|pengepul|driver|pabrik|admin")
    kecamatan: str | None = None
    kabupaten: str | None = "Sleman"
    lat: float | None = None
    lon: float | None = None


class LoginRequest(BaseModel):
    identifier: str | None = Field(None, description="Username atau nomor telepon")
    phone: str | None = None
    username: str | None = None
    password: str = Field(..., min_length=1)
    expected_role: str | None = Field(None, description="Gerbang peran yang dipilih di halaman muka")


class UserProfileResponse(BaseModel):
    user_id: int
    username: str | None = None
    phone: str
    email: str | None = None
    full_name: str
    role: str
    is_active: bool
    kabupaten: str | None = None
    kecamatan: str | None = None
    lat: float | None = None
    lon: float | None = None
    xp_total: int = 0
    incentive_tier: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    user_id: int
    username: str | None = None
    phone: str
    kabupaten: str | None = None
    kecamatan: str | None = None
    xp_total: int = 0
    incentive_tier: str | None = None


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    """Registrasi user baru."""
    role_val = req.role.lower()
    if role_val not in SELF_SERVICE_ROLES:
        raise HTTPException(403, f"Registrasi mandiri hanya untuk role: {', '.join(sorted(SELF_SERVICE_ROLES))}. "
                                 "Akun admin/auditor dibuat oleh administrator.")

    # Cek duplikat
    conds = [User.phone == req.phone]
    if req.username:
        conds.append(User.username == req.username)
    if req.email:
        conds.append(User.email == req.email)

    existing = await db.execute(select(User).where(or_(*conds)))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Nomor telepon, username, atau email sudah terdaftar")

    role_enum = UserRole(role_val)
    user = User(
        username=req.username,
        email=req.email,
        phone=req.phone,
        password_hash=await run_cpu(hash_password, req.password),
        full_name=req.full_name,
        role=role_enum,
        # Petani langsung aktif; role operasional menunggu aktivasi admin (/admin/users/{id}/activate).
        is_active=role_enum == UserRole.PETANI,
        kecamatan=req.kecamatan,
        kabupaten=req.kabupaten or "Sleman",
        lat=req.lat,
        lon=req.lon,
        xp_total=0,
        incentive_tier=IncentiveTier.PEMULA,
    )
    db.add(user)
    await db.flush()

    role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    token = create_access_token(user.id, role_str)
    tier_str = user.incentive_tier.value if hasattr(user.incentive_tier, 'value') else str(user.incentive_tier)

    return TokenResponse(
        access_token=token,
        role=role_str,
        full_name=user.full_name,
        user_id=user.id,
        username=user.username,
        phone=user.phone,
        kabupaten=user.kabupaten,
        kecamatan=user.kecamatan,
        xp_total=user.xp_total or 0,
        incentive_tier=tier_str,
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    """Login via username ATAU nomor telepon + password."""
    lookup = (req.identifier or req.username or req.phone or "").strip()
    if not lookup:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Username atau nomor telepon wajib diisi")

    result = await db.execute(
        select(User).where(or_(User.phone == lookup, User.username == lookup))
    )
    user = result.scalar_one_or_none()
    # Lepas koneksi DB sebelum hashing (~0,3 s) agar pool tidak habis saat badai login.
    await db.commit()

    # PBKDF2 di thread pool terbatas (event loop tetap responsif). User tak dikenal tetap
    # di-hash dengan hash tiruan supaya waktu respons tidak membocorkan keberadaan akun.
    stored = user.password_hash if user else _dummy_hash()
    valid = await run_cpu(verify_password, req.password, stored)
    if not user or not valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Username/nomor telepon atau password salah")

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Akun belum aktif atau dinonaktifkan oleh admin")
    actual_role = user.role.value if hasattr(user.role, "value") else str(user.role)
    if req.expected_role and req.expected_role != actual_role:
        # Gerbang peran: akun pabrik tidak bisa masuk lewat gerbang petani, dst.
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"Akun ini bukan akun {req.expected_role}. Silakan pilih gerbang yang sesuai.")

    role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    token = create_access_token(user.id, role_str)
    tier_str = user.incentive_tier.value if hasattr(user.incentive_tier, 'value') else str(user.incentive_tier)

    return TokenResponse(
        access_token=token,
        role=role_str,
        full_name=user.full_name,
        user_id=user.id,
        username=user.username,
        phone=user.phone,
        kabupaten=user.kabupaten,
        kecamatan=user.kecamatan,
        xp_total=user.xp_total or 0,
        incentive_tier=tier_str,
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_me(user: Annotated[User, Depends(get_current_user)]):
    """Ambil data profil pengguna yang sedang login."""
    role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    tier_str = user.incentive_tier.value if hasattr(user.incentive_tier, 'value') else str(user.incentive_tier)
    return UserProfileResponse(
        user_id=user.id,
        username=user.username,
        phone=user.phone,
        email=user.email,
        full_name=user.full_name,
        role=role_str,
        is_active=user.is_active,
        kabupaten=user.kabupaten,
        kecamatan=user.kecamatan,
        lat=user.lat,
        lon=user.lon,
        xp_total=user.xp_total or 0,
        incentive_tier=tier_str,
    )


@router.get("/demo-accounts")
async def get_demo_accounts():
    """Daftar akun demo resmi untuk auto-fill di halaman login."""
    from ..seed import DEMO_ACCOUNTS
    return DEMO_ACCOUNTS


@router.post("/reset-demo")
async def reset_demo(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
):
    """Reset & isi ulang database dengan data demo — hanya admin (operasi destruktif)."""
    user = await get_current_user(credentials, db)
    if user.role != UserRole.ADMIN:
        raise HTTPException(403, "Reset data hanya untuk admin.")
    from ..seed import seed_demo_data
    result = await seed_demo_data(db, force_reset=True)
    return result
