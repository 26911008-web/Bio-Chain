"""Router: Authentication — Register, Login, Me, Demo Accounts & Data Seeding.

Mendukung login via username atau nomor telepon + password.
Menyediakan daftar akun demo resmi dan utilitas reset data demo.
"""

from typing import Annotated
import hashlib
import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..concurrency import run_cpu
from ..config import settings
from ..database import get_db
from ..dependencies import create_access_token, get_current_user, security
from ..models.user import User, UserRole, IncentiveTier

from ..services.phone import normalize_phone, require_phone

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
    username: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=100)
    phone: str = Field(..., min_length=8, max_length=20,
                       description="Nomor telepon (format: 08xxxxxxxxxx)")
    password: str = Field(..., min_length=6, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=100)
    role: str = Field("petani", pattern="^(petani|pengepul|driver|pabrik)$",
                      description="petani|pengepul|driver|pabrik")
    kecamatan: str | None = Field(None, max_length=100)
    kabupaten: str | None = Field("Sleman", max_length=100)
    lat: float | None = None
    lon: float | None = None

    _phone = field_validator("phone")(require_phone)       # F6: +62/62/spasi/strip → 08…

    @field_validator("username")
    @classmethod
    def _username_not_phone(cls, v: str | None) -> str | None:
        # Username yang berupa nomor telepon bisa menabrak login berbasis HP milik orang lain.
        if v is not None and re.fullmatch(r"[+\d][\d\s\-]*", v.strip()):
            raise ValueError("Username tidak boleh berupa nomor telepon; gunakan huruf, mis. budi_sleman")
        return v

    # F12: persetujuan pemrosesan data (UI wajib centang layanan_inti). Opsional di API demi klien lama;
    # tanpa ini /me/consents melaporkan needs_consent=true dan UI meminta persetujuan setelah login.
    consents: dict[str, bool] | None = None


class LoginRequest(BaseModel):
    identifier: str | None = Field(None, max_length=100, description="Username atau nomor telepon")
    phone: str | None = Field(None, max_length=30)
    username: str | None = Field(None, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)
    expected_role: str | None = Field(None, max_length=20, description="Gerbang peran yang dipilih di halaman muka")


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
    must_change_password: bool = False


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
    must_change_password: bool = False


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=100)


def _build_token_response(user: User) -> TokenResponse:
    role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    token = create_access_token(user.id, role_str, user.token_version or 0)
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
        must_change_password=bool(user.must_change_password),
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    """Registrasi user baru."""
    role_val = req.role.lower()
    if role_val not in SELF_SERVICE_ROLES:
        raise HTTPException(403, f"Registrasi mandiri hanya untuk role: {', '.join(sorted(SELF_SERVICE_ROLES))}. "
                                 "Akun admin/auditor dibuat oleh administrator.")

    # Cek duplikat (termasuk silang: username baru = nomor HP lama, atau nomor HP baru = username lama)
    conds = [User.phone == req.phone, User.username == req.phone]
    if req.username:
        conds += [User.username == req.username, User.phone == req.username]
    if req.email:
        conds.append(User.email == req.email)

    existing = await db.execute(select(User.id).where(or_(*conds)).limit(1))
    if existing.scalars().first() is not None:
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
    if req.consents:                                       # F12: jejak persetujuan sejak pendaftaran
        if req.consents.get("layanan_inti") is not True:
            raise HTTPException(422, "Persetujuan layanan inti wajib untuk mendaftar.")
        from ..security.rls import apply_now, bind_identity
        from ..services.privacy import record_consents
        bind_identity(db, user.id, user.role.value if hasattr(user.role, "value") else str(user.role))
        await apply_now(db)                                # PostgreSQL RLS: catat sebagai pemilik akun baru
        await record_consents(db, user.id, req.consents)

    return _build_token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    """Login via username ATAU nomor telepon + password."""
    lookup = (req.identifier or req.username or req.phone or "").strip()
    if not lookup:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Username atau nomor telepon wajib diisi")

    phone_norm = normalize_phone(lookup)                 # "+62 812-…" sama dengan "0812…"
    # Nomor HP dicocokkan lebih dulu, baru username — dua kueri terpisah. Dulu satu OR + scalar_one_or_none():
    # bila orang lain mendaftar dengan username = nomor HP korban, login korban jadi 500 permanen.
    phone_conds = [User.phone == lookup]
    if phone_norm and phone_norm != lookup:
        phone_conds.append(User.phone == phone_norm)
    user = (await db.execute(select(User).where(or_(*phone_conds)).limit(1))).scalars().first()
    if user is None:
        user = (await db.execute(select(User).where(User.username == lookup).limit(1))).scalars().first()
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

    return _build_token_response(user)


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
        must_change_password=bool(user.must_change_password),
    )


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, user: Annotated[User, Depends(get_current_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    """Ganti password sendiri (wajib setelah reset oleh admin — F6)."""
    from ..security.demo_guard import forbid_shared_account_change
    forbid_shared_account_change(user.username, "Ganti password")
    if not await run_cpu(verify_password, req.old_password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Password lama salah")
    if req.old_password == req.new_password:
        raise HTTPException(422, "Password baru harus berbeda dari password lama")
    user.password_hash = await run_cpu(hash_password, req.new_password)
    user.must_change_password = False
    user.token_version = int(user.token_version or 0) + 1      # cabut semua token lama (perangkat lain)
    await db.commit()
    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
    return {"message": "Password berhasil diganti. Sesi di perangkat lain otomatis keluar.",
            "access_token": create_access_token(user.id, role_str, user.token_version)}


@router.get("/demo-accounts")
async def get_demo_accounts():
    """Daftar akun demo resmi untuk auto-fill di halaman login (hanya DEMO_MODE; produksi → 404)."""
    if not settings.DEMO_MODE:
        raise HTTPException(404, "Not Found")
    from ..security.demo_guard import visible_demo_accounts
    return visible_demo_accounts()


@router.post("/reset-demo")
async def reset_demo(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
):
    """Reset & isi ulang database dengan data demo — hanya admin & hanya DEMO_MODE (operasi destruktif)."""
    if not settings.DEMO_MODE:
        raise HTTPException(404, "Not Found")
    from ..security.demo_guard import forbid_in_public_demo
    forbid_in_public_demo("Reset data demo")
    user = await get_current_user(request, credentials, db)
    if user.role != UserRole.ADMIN:
        raise HTTPException(403, "Reset data hanya untuk admin.")
    from ..seed import seed_demo_data
    result = await seed_demo_data(db, force_reset=True)
    return result
