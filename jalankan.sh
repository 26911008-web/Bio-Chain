#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "=== Bio-Chain Prototype ==="
echo

# Deteksi perintah Python
if command -v py >/dev/null 2>&1; then
    PY_CMD="py"
elif command -v python3 >/dev/null 2>&1; then
    PY_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PY_CMD="python"
else
    echo "[ERROR] Python tidak ditemukan. Silakan pasang Python 3.11+."
    exit 1
fi

# Opsi PostgreSQL
if [ "$1" = "pg" ] || [ "$1" = "postgres" ]; then
    echo "[Mode] Menyiapkan PostgreSQL di port 5433..."
    if command -v docker >/dev/null 2>&1; then
        docker compose up -d postgres
        $PY_CMD scripts/pg_setup.py
        export DATABASE_URL="postgresql+asyncpg://biochain_app:biochain_app_dev@localhost:5433/biochain"
        export AUTO_MIGRATE="false"
    else
        echo "[ERROR] Docker tidak ditemukan untuk menjalankan PostgreSQL."
        exit 1
    fi
fi

echo "[1/3] Memeriksa dependensi penuh (requirements.txt)..."
$PY_CMD -m pip install -q -r requirements.txt

# Cek port 8000
if command -v lsof >/dev/null 2>&1; then
    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "[PERINGATAN] Port 8000 sudah digunakan oleh proses lain."
        exit 1
    fi
elif command -v netstat >/dev/null 2>&1; then
    if netstat -ano 2>/dev/null | grep -q ":8000 .*LISTENING"; then
        echo "[PERINGATAN] Port 8000 sudah digunakan oleh proses lain."
        exit 1
    fi
fi

echo "[2/3] Membuka browser di http://127.0.0.1:8000 ..."
(
    sleep 3
    if command -v start >/dev/null 2>&1; then
        start http://127.0.0.1:8000
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open http://127.0.0.1:8000
    elif command -v open >/dev/null 2>&1; then
        open http://127.0.0.1:8000
    fi
) &

echo "[3/3] Menjalankan server. Tekan Ctrl+C untuk berhenti."
echo
$PY_CMD -m uvicorn app.main:app --port 8000 --reload
