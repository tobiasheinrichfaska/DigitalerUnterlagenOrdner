# Clean-venv Build fuer BelegTool (onedir)
$ErrorActionPreference = 'Stop'
$Root    = $PSScriptRoot
$VenvDir = "$Root\.build_venv"

Write-Host "=== Alte Build-Artefakte entfernen ===" -ForegroundColor Cyan
Remove-Item -Recurse -Force "$Root\build" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$Root\dist"  -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $VenvDir       -ErrorAction SilentlyContinue

Write-Host "=== React-UI bauen (webui/dist) ===" -ForegroundColor Cyan
Push-Location "$Root\webui"
npm install
npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "webui build failed" }
Pop-Location

# Pin the build Python explicitly via the py launcher (don't silently use whatever
# 'python' happens to be first on PATH). Bump $PyVer when moving the build Python.
$PyVer = '3.13'
Write-Host "=== Saubere venv erstellen (Python $PyVer) ===" -ForegroundColor Cyan
$found = $false
if (Get-Command py -ErrorAction SilentlyContinue) {
    py "-$PyVer" --version > $null 2> $null
    $found = ($LASTEXITCODE -eq 0)
}
if (-not $found) {
    throw "Python $PyVer wird fuer den Build benoetigt. Installieren ('winget install Python.Python.3.13' oder python.org) und erneut ausfuehren."
}
py "-$PyVer" -m venv $VenvDir

Write-Host "=== Abhaengigkeiten installieren ===" -ForegroundColor Cyan
& "$VenvDir\Scripts\python.exe" -m pip install --upgrade pip --quiet
& "$VenvDir\Scripts\pip.exe" install -r "$Root\requirements.txt" --quiet

Write-Host "=== PyInstaller Build (onedir) ===" -ForegroundColor Cyan
& "$VenvDir\Scripts\pyinstaller.exe" "$Root\belegtool.spec" `
    --distpath "$Root\dist" `
    --workpath "$Root\build" `
    --noconfirm

# Ship an EDITABLE datev.config.json NEXT TO the exe (PyInstaller datas land under
# _internal/, but the app reads the config from the exe's own dir). Only seed it if the
# user hasn't already placed/edited one in the dist folder.
Write-Host "=== datev.config.json bereitstellen ===" -ForegroundColor Cyan
$cfgDst = "$Root\dist\BelegTool\datev.config.json"
if (-not (Test-Path $cfgDst)) {
    Copy-Item "$Root\datev.config.example.json" $cfgDst
    Write-Host "    datev.config.json (Vorlage) neben die exe gelegt" -ForegroundColor Green
}

Write-Host "=== Fertig ===" -ForegroundColor Green
Write-Host "    App:   dist\BelegTool\BelegTool.exe" -ForegroundColor Green
Write-Host "    Datei: dist\BelegTool\BelegTool.exe <datei.belegtool>" -ForegroundColor Green
Write-Host "    DATEV: dist\BelegTool\datev.config.json (Host/Port anpassen)" -ForegroundColor Green
