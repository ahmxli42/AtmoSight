param([ValidateSet('setup','rebuild','backend','frontend','desktop','tests','build')][string]$Task = 'tests')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = 'backend/.venv/Scripts/python.exe'
function CheckExit { if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE)" } }
switch ($Task) {
 'setup' { python -m venv backend/.venv; CheckExit; & $py -m pip install -r requirements.txt; CheckExit; npm.cmd ci --prefix Design; CheckExit }
 'rebuild' { & $py scripts/verify_data.py; CheckExit; foreach ($module in @('backend.train','backend.noise_evaluation','backend.train_sensor_models','backend.evaluate_station_transfer')) { & $py -m $module; CheckExit } }
 'backend' { & $py -m backend.app; CheckExit }
 'frontend' { npm.cmd --prefix Design run dev; CheckExit }
 'desktop' { & powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-backend.ps1; CheckExit; npm.cmd --prefix Design run tauri -- dev; CheckExit }
 'tests' { & $py -m unittest backend.test_api backend.test_adaptability backend.test_large_imports backend.test_frozen_adaptability experiments.robustness.test_robustness -v; CheckExit }
 'build' { npm.cmd --prefix Design run build; CheckExit }
}
