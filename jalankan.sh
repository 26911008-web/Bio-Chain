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
elif [ -f "$LOCALAPPDATA/Python/pythoncore-3.14-64/python.exe" ]; then
    PY_CMD="$LOCALAPPDATA/Python/pythoncore-3.14-64/python.exe"
else
    echo "[ERROR] Python tidak ditemukan. Silakan pasang Python 3.11+."
    exit 1
fi

# Opsi PostgreSQL atau Port khusus
PORT="${PORT:-8000}"
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
    if [ -n "$2" ]; then PORT="$2"; fi
elif [ -n "$1" ]; then
    PORT="$1"
fi

echo "[1/3] Memeriksa dependensi penuh (requirements.txt)..."
$PY_CMD -m pip install -q -r requirements.txt

# Cek ketersediaan port dengan auto-fallback
port_is_busy() {
    local p="$1"
    if command -v lsof >/dev/null 2>&1; then
        lsof -Pi :"$p" -sTCP:LISTEN -t >/dev/null 2>&1
    elif command -v netstat >/dev/null 2>&1; then
        netstat -ano 2>/dev/null | grep -q ":$p .*LISTENING"
    else
        return 1
    fi
}

if port_is_busy "$PORT"; then
    echo "[PERINGATAN] Port $PORT sedang digunakan oleh proses lain."
    ALT_PORT=$((PORT + 1))
    echo "Mencoba beralih otomatis ke port $ALT_PORT..."
    if ! port_is_busy "$ALT_PORT"; then
        PORT="$ALT_PORT"
        echo "Menggunakan port alternatif: $PORT"
    else
        echo "[ERROR] Port $PORT dan $ALT_PORT sama-sama sedang digunakan."
        echo "Silakan gunakan port lain: ./jalankan.sh 8080"
        exit 1
    fi
fi

echo "[2/3] Membuka browser di http://127.0.0.1:$PORT ..."
(
    sleep 3
    if command -v explorer.exe >/dev/null 2>&1; then
        explorer.exe "http://127.0.0.1:$PORT"
    elif command -v cmd.exe >/dev/null 2>&1; then
        cmd.exe //c start "http://127.0.0.1:$PORT"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://127.0.0.1:$PORT"
    elif command -v open >/dev/null 2>&1; then
        open "http://127.0.0.1:$PORT"
    fi
) &

echo "[3/3] Menjalankan server Bio-Chain di http://127.0.0.1:$PORT ... Tekan Ctrl+C untuk berhenti."
echo
$PY_CMD -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --reload
