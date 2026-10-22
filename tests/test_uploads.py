"""Tests for evidence and proof file upload endpoint (/api/v1/uploads)."""

import io
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.security.url import validate_evidence_url
from tests.conftest import demo_headers


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def farmer_token(client):
    return demo_headers(client, "petani")["Authorization"].split()[1]


@pytest.fixture(scope="module")
def collector_token(client):
    return demo_headers(client, "pengepul")["Authorization"].split()[1]


@pytest.mark.asyncio
async def test_upload_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("test.jpg", b"\xff\xd8\xff\xe0fakejpeg", "image/jpeg")}
        resp = await ac.post("/api/v1/uploads", files=files)
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_invalid_extension(farmer_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("script.sh", b"echo hello", "text/plain")}
        resp = await ac.post(
            "/api/v1/uploads",
            files=files,
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 400
        assert "Format file" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_empty_file(farmer_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("empty.png", b"", "image/png")}
        resp = await ac.post(
            "/api/v1/uploads",
            files=files,
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 400
        assert "File kosong" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_file_too_large(farmer_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        large_content = b"A" * (6 * 1024 * 1024)  # 6 MB > 5 MB
        files = {"file": ("big.jpg", large_content, "image/jpeg")}
        resp = await ac.post(
            "/api/v1/uploads",
            files=files,
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 413
        assert "melebihi batas" in resp.json()["detail"]


def _jpeg_with_gps(size=(3000, 1500)) -> bytes:
    """JPEG sungguhan dengan EXIF GPS (seperti foto HP di rumah petani)."""
    import io
    from PIL import Image
    img = Image.new("RGB", size, (180, 160, 90))
    exif = Image.Exif()
    exif[0x0110] = "HP Petani X1"                          # Model
    exif[0x8825] = {1: "S", 2: (7.0, 45.0, 0.0), 3: "E", 4: (110.0, 21.0, 0.0)}   # GPSInfo
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif)
    return out.getvalue()


@pytest.mark.asyncio
async def test_upload_valid_image_and_retrieve(collector_token):
    import io
    from PIL import Image
    jpeg_bytes = _jpeg_with_gps()
    assert Image.open(io.BytesIO(jpeg_bytes)).getexif().get(0x8825), "prasyarat: foto asli memuat GPS"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("receipt.jpg", jpeg_bytes, "image/jpeg")}
        resp = await ac.post(
            "/api/v1/uploads",
            files=files,
            headers={"Authorization": f"Bearer {collector_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["url"].startswith("/uploads/")
        assert data["url"].endswith(".jpg")

        # Verifikasi validate_evidence_url menerima URL ini
        valid_url = validate_evidence_url(data["url"])
        assert valid_url == data["url"]

        # File tersimpan: tanpa EXIF (GPS & model HP hilang), diperkecil ≤ 2048 px
        get_resp = await ac.get(data["url"])
        assert get_resp.status_code == 200
        stored = Image.open(io.BytesIO(get_resp.content))
        assert not stored.getexif().get(0x8825) and not stored.getexif().get(0x0110)
        assert max(stored.size) == 2048 and data["size_bytes"] == len(get_resp.content)


@pytest.mark.asyncio
async def test_upload_rejects_fake_image(collector_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("bukti.jpg", b"<html><script>alert(1)</script></html>", "image/jpeg")}
        resp = await ac.post("/api/v1/uploads", files=files, headers={"Authorization": f"Bearer {collector_token}"})
        assert resp.status_code == 400 and "bukan gambar" in resp.json()["detail"]
