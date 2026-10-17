@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0SwitchPadStudio.exe" (
    start "" "%~dp0SwitchPadStudio.exe"
    exit /b 0
)
if exist "%~dp0.venv\switchpad-installed.ok" if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" /D "%~dp0" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
    exit /b 0
)
echo Prima esecuzione: installazione dell'app. E' necessaria una connessione Internet.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1"
if errorlevel 1 (
    echo.
    echo INSTALLAZIONE NON COMPLETATA. Copia l'errore e invialo per la diagnosi.
    pause
    exit /b 1
)
endlocal
