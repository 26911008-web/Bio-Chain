# Bio-Chain Prototype — Script Peluncur PowerShell
param (
    [int]$Port = 8000,
    [switch]$Postgres
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "========================================" -ForegroundColor Green
Write-Host "       Bio-Chain Prototype (v2)        " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# 1. Cari binary Python
$pythonCmd = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonCmd = "python3"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Test-Path "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe") {
    $pythonCmd = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe"
} else {
    Write-Host "[ERROR] Python tidak ditemukan. Silakan pasang Python 3.11+." -ForegroundColor Red
    exit 1
}

# 2. Mode PostgreSQL jika diminta
if ($Postgres) {
    Write-Host "[Mode] Menyiapkan PostgreSQL di port 5433..." -ForegroundColor Cyan
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        docker compose up -d postgres
        & $pythonCmd scripts/pg_setup.py
        $env:DATABASE_URL = "postgresql+asyncpg://biochain_app:biochain_app_dev@localhost:5433/biochain"
        $env:AUTO_MIGRATE = "false"
    } else {
        Write-Host "[ERROR] Docker tidak ditemukan untuk PostgreSQL." -ForegroundColor Red
        exit 1
    }
}

# 3. Cek ketersediaan port
$conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($conn) {
    Write-Host "[PERINGATAN] Port $Port sedang digunakan oleh proses lain." -ForegroundColor Yellow
    $altPort = $Port + 1
    Write-Host "Mencoba beralih otomatis ke port $altPort..." -ForegroundColor Cyan
    $connAlt = Get-NetTCPConnection -LocalPort $altPort -ErrorAction SilentlyContinue
    if (-not $connAlt) {
        $Port = $altPort
        Write-Host "Menggunakan port alternatif: $Port" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Port $Port dan $altPort sama-sama sedang digunakan." -ForegroundColor Red
        Write-Host "Silakan matikan proses yang menggunakan port tersebut, atau jalankan dengan port lain:"
        Write-Host "   .\jalankan.ps1 -Port 8080" -ForegroundColor White
        exit 1
    }
}

# 4. Instal / verifikasi dependensi
Write-Host "[1/3] Memeriksa dependensi (requirements.txt)..." -ForegroundColor Cyan
& $pythonCmd -m pip install -q -r requirements.txt

# 5. Buka browser
Write-Host "[2/3] Membuka browser di http://127.0.0.1:$Port ..." -ForegroundColor Cyan
Start-Process "http://127.0.0.1:$Port"

# 6. Jalankan Uvicorn
Write-Host "[3/3] Menjalankan server Bio-Chain di http://127.0.0.1:$Port ..." -ForegroundColor Green
Write-Host "Tekan Ctrl+C untuk menghentikan server.`n" -ForegroundColor DarkGray

& $pythonCmd -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
