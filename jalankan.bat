@echo off
title Bio-Chain Prototype
cd /d "%~dp0"

echo ========================================
echo        Bio-Chain Prototype (v2)        
echo ========================================
echo.

where py >nul 2>&1
if errorlevel 1 (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python tidak ditemukan. Install Python dari https://www.python.org
        pause
        exit /b 1
    )
    set PY_CMD=python
) else (
    set PY_CMD=py
)

set PORT=8000
if "%1"=="pg" goto :postgres
if "%1"=="postgres" goto :postgres
if not "%1"=="" set PORT=%1
goto :start_app

:postgres
echo [Mode] Menyiapkan PostgreSQL di port 5433...
docker compose up -d postgres
if errorlevel 1 (
    echo [ERROR] Gagal menjalankan Docker PostgreSQL. Pastikan Docker Desktop aktif.
    pause
    exit /b 1
)
%PY_CMD% scripts/pg_setup.py
set DATABASE_URL=postgresql+asyncpg://biochain_app:biochain_app_dev@localhost:5433/biochain
set AUTO_MIGRATE=false
if not "%2"=="" set PORT=%2
echo.

:start_app
echo [1/3] Memeriksa dependensi penuh (requirements.txt)...
%PY_CMD% -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Gagal menginstal dependensi.
    pause
    exit /b 1
)

netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [PERINGATAN] Port %PORT% sedang digunakan oleh proses lain.
    set /a ALT_PORT=%PORT%+1
    echo Mencoba beralih otomatis ke port %ALT_PORT%...
    netstat -ano | findstr ":!ALT_PORT! " | findstr "LISTENING" >nul 2>&1
    set PORT=8001
    echo Menggunakan port alternatif: 8001
)

echo [2/3] Membuka browser di http://127.0.0.1:%PORT% ...
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:%PORT%"

echo [3/3] Menjalankan server Bio-Chain di http://127.0.0.1:%PORT% ...
echo Tutup jendela ini atau tekan Ctrl+C untuk berhenti.
echo.
%PY_CMD% -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% --reload

pause
