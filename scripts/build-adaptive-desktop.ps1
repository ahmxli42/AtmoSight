$ErrorActionPreference = 'Stop'
$workspaceDir = Split-Path $PSScriptRoot -Parent
Set-Location $workspaceDir
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-backend.ps1
if ($LASTEXITCODE -ne 0) { throw 'Backend build failed.' }
$env:CARGO_TARGET_DIR = Join-Path $workspaceDir 'Design/src-tauri/target-adaptive'
$env:PATH = (Join-Path $env:USERPROFILE '.cargo/bin') + ';' + $env:PATH
Remove-Item Env:VITE_BACKEND_URL -ErrorAction SilentlyContinue
& npm.cmd --prefix Design run tauri -- build --no-bundle
if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed.' }
Write-Output 'Updated app: Design/src-tauri/target-adaptive/release/atmosight.exe. Close the previous app before launching this version.'
