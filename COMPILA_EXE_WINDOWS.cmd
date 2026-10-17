@echo off
setlocal
cd /d "%~dp0"
echo Questo comando compila il vero file SwitchPadStudio.exe per Windows.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1" -BuildExe
if errorlevel 1 (
    echo.
    echo COMPILAZIONE NON COMPLETATA.
    pause
    exit /b 1
)
echo.
echo SwitchPadStudio.exe creato nella cartella corrente.
pause
endlocal
