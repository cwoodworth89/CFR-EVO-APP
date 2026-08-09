# scripts/install_dev_packages.ps1
# Installs CFR EVO microservices into the active Python environment in editable mode (-e)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " CFR EVO: Installing Sibling Services in Editable Mode   " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Check for active python
$PythonPath = "python"
if (Test-Path "$RepoRoot\.venv\Scripts\python.exe") {
    $PythonPath = "$RepoRoot\.venv\Scripts\python.exe"
    Write-Host "Using virtualenv Python: $PythonPath" -ForegroundColor Green
}

& $PythonPath -m pip install --upgrade pip

Write-Host "`n[1/4] Installing services/gis..." -ForegroundColor Yellow
& $PythonPath -m pip install -e "$RepoRoot\services\gis"

Write-Host "`n[2/4] Installing services/audio_analysis..." -ForegroundColor Yellow
& $PythonPath -m pip install -e "$RepoRoot\services\audio_analysis"

Write-Host "`n[3/4] Installing services/dispatch_notifications..." -ForegroundColor Yellow
& $PythonPath -m pip install -e "$RepoRoot\services\dispatch_notifications"

Write-Host "`n[4/4] Installing backend (cfr-dispatch)..." -ForegroundColor Yellow
& $PythonPath -m pip install -e "$RepoRoot\backend"

Write-Host "`nVerifying native package imports..." -ForegroundColor Cyan
& $PythonPath -c "import gis_service; import audio_service; import notification_service; import cfr_dispatch; print('>>> SUCCESS: All 4 microservices installed and resolved natively!')"

Write-Host "`nAll packages ready for development!" -ForegroundColor Green
