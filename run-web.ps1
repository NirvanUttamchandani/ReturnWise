# Builds the web app (if needed) and starts the API + web app on http://localhost:8000
# Usage (venv active):  .\run-web.ps1
if (-not (Test-Path frontend/node_modules)) { Push-Location frontend; npm install; Pop-Location }
if (-not (Test-Path frontend/dist/index.html)) { Push-Location frontend; npm run build; Pop-Location }
python -m uvicorn api.main:app --port 8000
