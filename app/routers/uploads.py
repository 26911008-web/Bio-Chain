"""Router: Upload File Bukti (📸) — Foto timbangan, bukti serah-terima, tiket QC."""

from pathlib import Path
import hashlib
import uuid
import anyio.to_thread
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

from ..dependencies import get_current_user
from ..models.user import User

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
UPLOADS_DIR = STATIC_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Unggah file bukti (foto karung, timbangan, atau tiket penerimaan).

    Hanya pengguna terautentikasi yang diizinkan.
    Maksimal ukuran file: 5 MB.
    Format yang diizinkan: JPG, PNG, WEBP, PDF.
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Format file '{ext}' tidak diizinkan. Gunakan {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
        )

    # Validasi content type jika dikirim oleh client
    if file.content_type and file.content_type.lower() not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipe konten '{file.content_type}' tidak diizinkan.",
        )

    content = await file.read()
    original = content
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Ukuran file melebihi batas maksimum 5 MB.",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File kosong.",
        )

    content_type = file.content_type or "application/octet-stream"
    if ext != ".pdf":
        # F10: encode ulang di server — membuktikan isinya gambar sungguhan (bukan HTML/skrip berekstensi .jpg)
        # dan membuang seluruh metadata EXIF (GPS rumah, model HP) walau klien tidak mengompres.
        try:
            content, ext, content_type = await anyio.to_thread.run_sync(sanitize_image, content)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    elif not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Berkas bukan PDF yang sah.")

    # Nama file = sha256 isi ASLI (sebelum encode ulang): foto yang sama selalu menghasilkan nama yang sama →
    # pemakaian ulang foto bukti lintas transaksi terdeteksi (`duplicate`), tanpa tabel tambahan.
    digest = hashlib.sha256(original).hexdigest()
    safe_filename = f"{digest[:40]}{ext}"
    dest_path = UPLOADS_DIR / safe_filename
    duplicate = dest_path.exists()
    if not duplicate:
        await anyio.to_thread.run_sync(dest_path.write_bytes, content)

    return {
        "url": f"/uploads/{safe_filename}",
        "filename": safe_filename,
        "original_filename": file.filename,
        "size_bytes": len(content),
        "content_type": content_type,
        "uploaded_by": user.id,
        "sha256": digest,
        "duplicate": duplicate,
    }


MAX_IMAGE_SIDE = 2048


def sanitize_image(data: bytes) -> tuple[bytes, str, str]:
    """Buka gambar dengan Pillow, putar sesuai orientasi EXIF, perkecil ≤2048 px, simpan ulang TANPA metadata."""
    import io

    from PIL import Image, ImageOps, UnidentifiedImageError

    Image.MAX_IMAGE_PIXELS = 50_000_000                 # tolak "decompression bomb"
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()                                    # struktur berkas sah
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError):
        raise ValueError("Berkas bukan gambar yang sah (JPG/PNG/WEBP).")
    if max(img.size) > MAX_IMAGE_SIDE:
        img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    out = io.BytesIO()
    if img.mode in ("RGBA", "LA", "P") and "transparency" in img.info or img.mode in ("RGBA", "LA"):
        img.convert("RGBA").save(out, format="PNG", optimize=True)
        return out.getvalue(), ".png", "image/png"
    img.convert("RGB").save(out, format="JPEG", quality=82, optimize=True)
    return out.getvalue(), ".jpg", "image/jpeg"
