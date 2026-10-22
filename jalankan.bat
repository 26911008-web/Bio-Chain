@echo off
title Bio-Chain Prototype
cd /d "%~dp0"

echo === Bio-Chain Prototype ===
echo.

where py >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python launcher "py" tidak ditemukan. Install Python dari https://www.python.org
    pause
    exit /b 1
)

echo [1/3] Memeriksa dependensi...
py -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo       Menginstal dependensi dari requirements.txt...
    py -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Gagal menginstal dependensi.
        pause
        exit /b 1
    )
)

echo [2/3] Membuka browser di http://127.0.0.1:8000 ...
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8000"

echo [3/3] Menjalankan server. Tutup jendela ini atau tekan Ctrl+C untuk berhenti.
echo.
py -m uvicorn app.main:app --port 8000 --reload

pause
