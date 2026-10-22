"""Router: Upload File Bukti (📸) — Foto timbangan, bukti serah-terima, tiket QC."""

from pathlib import Path
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

    # Generate nama file acak & unik
    safe_filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = UPLOADS_DIR / safe_filename

    # Tulis file secara asinkron lewat thread pool
    await anyio.to_thread.run_sync(dest_path.write_bytes, content)

    return {
        "url": f"/uploads/{safe_filename}",
        "filename": safe_filename,
        "original_filename": file.filename,
        "size_bytes": len(content),
        "content_type": file.content_type or "application/octet-stream",
        "uploaded_by": user.id,
    }
