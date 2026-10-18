$ErrorActionPreference = 'Stop'
$workspaceDir = Split-Path $PSScriptRoot -Parent
Set-Location $workspaceDir
$pythonExe = Join-Path $workspaceDir 'backend/.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $pythonExe)) { throw 'Create backend/.venv and install requirements first. See README.md.' }
if (!(Test-Path backend/artifacts/baseline.joblib)) { throw 'Run backend/.venv/Scripts/python.exe -m backend.train first.' }
$backendProcess = Start-Process -FilePath $pythonExe -ArgumentList '-m', 'backend.app' -WorkingDirectory $workspaceDir -WindowStyle Hidden -PassThru
try {
    & npm.cmd --prefix Design run dev
} finally {
    if (!$backendProcess.HasExited) { $backendProcess.Kill() }
}
