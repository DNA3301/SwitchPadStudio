@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
 echo Non trovo l'ambiente Python. Esegui prima INSTALLA_E_AVVIA.cmd
 pause
 exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0main.py"
echo.
echo Processo terminato, codice uscita %errorlevel%.
echo Log: %%APPDATA%%\SwitchPadStudio\logs\session.log
pause
endlocal
