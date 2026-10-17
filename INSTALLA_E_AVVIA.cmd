@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1"
if errorlevel 1 (
    echo.
    echo INSTALLAZIONE NON COMPLETATA.
    pause
    exit /b 1
)
endlocal
