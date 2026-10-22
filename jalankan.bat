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

if "%1"=="pg" goto :postgres
if "%1"=="postgres" goto :postgres
goto :start_app

:postgres
echo [Mode] Menyiapkan PostgreSQL di port 5433...
docker compose up -d postgres
if errorlevel 1 (
    echo [ERROR] Gagal menjalankan Docker PostgreSQL. Pastikan Docker Desktop aktif.
    pause
    exit /b 1
)
py scripts/pg_setup.py
set DATABASE_URL=postgresql+asyncpg://biochain_app:biochain_app_dev@localhost:5433/biochain
set AUTO_MIGRATE=false
echo.

:start_app
echo [1/3] Memeriksa dependensi penuh (requirements.txt)...
py -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Gagal menginstal dependensi.
    pause
    exit /b 1
)

netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [PERINGATAN] Port 8000 sudah digunakan oleh proses lain.
    echo Matikan proses yang memakai port 8000 atau gunakan port lain.
    pause
    exit /b 1
)

echo [2/3] Membuka browser di http://127.0.0.1:8000 ...
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8000"

echo [3/3] Menjalankan server. Tutup jendela ini atau tekan Ctrl+C untuk berhenti.
echo.
py -m uvicorn app.main:app --port 8000 --reload

pause
