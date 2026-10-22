@echo off
REM Wrapper untuk menjalankan Git Bash di Windows, menghindari konflik WSL bash.exe yang rusak
if exist "C:\Program Files\Git\bin\bash.exe" (
    "C:\Program Files\Git\bin\bash.exe" %*
) else if exist "C:\Program Files (x86)\Git\bin\bash.exe" (
    "C:\Program Files (x86)\Git\bin\bash.exe" %*
) else if exist "%LOCALAPPDATA%\Programs\Git\bin\bash.exe" (
    "%LOCALAPPDATA%\Programs\Git\bin\bash.exe" %*
) else (
    echo [ERROR] Git Bash tidak ditemukan di lokasi standar.
    echo Silakan jalankan menggunakan "jalankan.bat" atau ".\jalankan.ps1".
    exit /b 1
)
