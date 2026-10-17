# SwitchPad Studio: user-level Python environment + optional Windows EXE build.
[CmdletBinding()]
param([switch]$BuildExe, [switch]$NoLaunch)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Root

function Test-PythonCandidate {
    param([string]$Exe, [string[]]$Prefix=@())
    try {
        $check = & $Exe @Prefix -c 'import sys; print(int((3,10) <= sys.version_info[:2] <= (3,13) and sys.maxsize > 2**32))' 2>$null
        if ($LASTEXITCODE -eq 0 -and ($check -join ' ').Trim() -eq '1') {
            return @{ Exe=$Exe; Prefix=$Prefix }
        }
    } catch { }
    return $null
}

function Resolve-Python {
    $possible = @(
        @{ Exe='py.exe'; Prefix=@('-3.12') },
        @{ Exe=(Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'); Prefix=@() },
        @{ Exe='py.exe'; Prefix=@('-3.11') },
        @{ Exe='py.exe'; Prefix=@('-3.13') },
        @{ Exe='py.exe'; Prefix=@('-3.10') },
        @{ Exe='python.exe'; Prefix=@() },
        @{ Exe='python3.exe'; Prefix=@() }
    )
    foreach($candidate in $possible) {
        $r = Test-PythonCandidate -Exe $candidate.Exe -Prefix $candidate.Prefix
        if ($r) { return $r }
    }
    return $null
}

Write-Host ''
Write-Host '=========================================' -ForegroundColor Cyan
Write-Host '      SWITCHPAD STUDIO 4.0 - WINDOWS' -ForegroundColor Cyan
Write-Host '=========================================' -ForegroundColor Cyan
Write-Host ''

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'Questo installer richiede Windows.'
}
$python = Resolve-Python
if (-not $python) {
    Write-Host 'Python 3.12 non trovato. Tentativo di installazione tramite winget (solo utente)...' -ForegroundColor Yellow
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw 'winget non disponibile. Installa Python 3.12 x64 dal sito https://www.python.org/downloads/windows/ e riprova.'
    }
    & winget.exe install --id Python.Python.3.12 -e --source winget --scope user --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw 'Installazione di Python non completata. Apri https://www.python.org/downloads/windows/' }
    $python = Resolve-Python
    if (-not $python) { throw 'Python installato ma non ancora rilevabile. Chiudi e riapri il programma (o Windows Terminal) e riprova.' }
}
Write-Host ('Python rilevato: {0} {1}' -f $python.Exe, ($python.Prefix -join ' ')) -ForegroundColor Green

$venv = Join-Path $Root '.venv'
$venvpython = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvpython)) {
    Write-Host 'Creo ambiente isolato (solo alla prima installazione)...' -ForegroundColor Cyan
    $baseExe = $python.Exe
    $baseArgs = $python.Prefix
    & $baseExe @baseArgs -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Creazione ambiente Python fallita.' }
}

# Never execute upstream vgamepad/setup.py: it invokes an obsolete driver MSI.
& $venvpython (Join-Path $Root 'tools\safe_vgamepad.py')
if ($LASTEXITCODE -ne 0) { throw 'Preparazione sicura di vgamepad fallita. Nessun driver e stato installato.' }
Write-Host 'Installo le librerie dell''app (pygame, vgamepad, tray icon)...' -ForegroundColor Cyan
& $venvpython -m pip install --disable-pip-version-check --no-input -r (Join-Path $Root 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze fallita. Controlla la connessione Internet e riprova.' }
Set-Content -LiteralPath (Join-Path $venv 'switchpad-installed.ok') -Value '4.0.0' -Encoding Ascii

if ($BuildExe) {
    Write-Host 'Compilazione eseguibile Windows x64 in corso...' -ForegroundColor Cyan
    & $venvpython -m pip install --disable-pip-version-check --no-input -r (Join-Path $Root 'requirements-build.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Installazione PyInstaller fallita.' }
    # Bundle only runtime ViGEmClient DLLs; never the obsolete driver MSI files.
    $buildOriginalPath = $env:PATH
    try {
      # Prevent unrelated applications' codec DLLs on PATH leaking into the bundle.
      $env:PATH = (Join-Path $env:SystemRoot 'System32') + ';' + $env:SystemRoot + ';' + (Split-Path -Parent $venvpython)
      & $venvpython -m PyInstaller --noconfirm --clean --onefile --windowed --name SwitchPadStudio `
        --icon (Join-Path $Root 'assets\switchpad.ico') `
        --additional-hooks-dir (Join-Path $Root 'tools\hooks') `
        --exclude-module pygame.mixer --exclude-module pygame.mixer_music `
        --exclude-module pygame.font --exclude-module pygame.freetype `
        --exclude-module pygame._freetype --exclude-module pygame.imageext `
        --exclude-module pygame.pypm --exclude-module pygame.midi `
        --collect-binaries vgamepad --hidden-import pygame._sdl2.controller `
        --hidden-import pystray._win32 --paths $Root (Join-Path $Root 'main.py')
    } finally {
      $env:PATH = $buildOriginalPath
    }
    if ($LASTEXITCODE -ne 0) { throw 'Compilazione EXE fallita. Controlla gli errori precedenti.' }
    $exeSource = Join-Path $Root 'dist\SwitchPadStudio.exe'
    if (-not (Test-Path -LiteralPath $exeSource)) { throw 'EXE non trovato al termine del processo.' }
    Copy-Item -LiteralPath $exeSource -Destination (Join-Path $Root 'SwitchPadStudio.exe') -Force
    Write-Host ''
    Write-Host 'EXE GENERATO: SwitchPadStudio.exe' -ForegroundColor Green
    Write-Host 'Se ViGEmBus non e installato, usa il link ufficiale nella scheda Diagnostica.' -ForegroundColor Yellow
    if (-not $NoLaunch) {
        Start-Process -WindowStyle Hidden -FilePath (Join-Path $Root 'SwitchPadStudio.exe') -WorkingDirectory $Root
    }
} elseif (-not $NoLaunch) {
    Write-Host 'Apro interfaccia SwitchPad Studio...' -ForegroundColor Green
    $pythonw = Join-Path $venv 'Scripts\pythonw.exe'
    if (-not (Test-Path -LiteralPath $pythonw)) { $pythonw = $venvpython }
    Start-Process -WindowStyle Hidden -FilePath $pythonw -ArgumentList ('"' + (Join-Path $Root 'main.py') + '"') -WorkingDirectory $Root
    Write-Host 'Se manca il driver Xbox virtuale, la GUI ti mostrera come installarlo.' -ForegroundColor Yellow
}
