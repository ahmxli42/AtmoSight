$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (!(Test-Path backend/artifacts/baseline.joblib)) { throw 'Train the model first: python -m backend.train' }
$artifactDir = (Resolve-Path backend/artifacts).Path
$iconPath = (Resolve-Path Design/src-tauri/icons/icon.ico).Path
& backend/.venv/Scripts/python.exe -m PyInstaller --noconfirm --onefile --name atmosight-backend --icon $iconPath --distpath backend/dist --workpath backend/build --specpath backend --add-data "$artifactDir;artifacts" --collect-data shap --hidden-import shap._cext --hidden-import sklearn.ensemble._forest --hidden-import sklearn.ensemble._iforest --hidden-import sklearn.impute._base --hidden-import sklearn.pipeline --hidden-import sklearn.tree._tree --exclude-module tensorflow --exclude-module torch --exclude-module keras --exclude-module matplotlib --exclude-module pytest --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.protocols.websockets.auto backend/app.py
if ($LASTEXITCODE -ne 0) { throw 'Backend packaging failed.' }
New-Item -ItemType Directory Design/src-tauri/binaries -Force | Out-Null
Copy-Item backend/dist/atmosight-backend.exe Design/src-tauri/binaries/atmosight-backend-x86_64-pc-windows-msvc.exe -Force
