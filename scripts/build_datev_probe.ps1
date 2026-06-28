# Build the standalone DATEV read-probe as a ONE-FILE exe → dist/DATEV-Probe.exe
#
# The probe is stdlib-only (urllib / ssl / tkinter / json), so no requirements install is
# needed; we reuse .build_venv only for its PyInstaller. Run build.ps1 once if the venv is
# missing. PyInstaller writes INFO to stderr — do NOT redirect it (PowerShell 5.1 would turn
# that into a terminating NativeCommandError); we check $LASTEXITCODE for real failure.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root '.build_venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "Build venv not found: $py  (run build.ps1 once to create it)" }

Push-Location $root
try {
    Write-Host 'Cleaning previous probe build…'
    Remove-Item -Recurse -Force `
        (Join-Path $root 'build\DATEV-Probe'), `
        (Join-Path $root 'dist\DATEV-Probe.exe'), `
        (Join-Path $root 'DATEV-Probe.spec') -ErrorAction SilentlyContinue

    Write-Host 'Building one-file exe (PyInstaller --onefile --windowed)…'
    & $py -m PyInstaller --onefile --windowed --clean --noconfirm --name 'DATEV-Probe' 'datev_probe.py'
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed (exit $LASTEXITCODE)" }

    $exe = Join-Path $root 'dist\DATEV-Probe.exe'
    if (-not (Test-Path $exe)) { throw "Expected exe not produced: $exe" }
    Write-Host "Done → $exe"
}
finally { Pop-Location }
