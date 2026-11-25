#requires -Version 5.1
<#
.SYNOPSIS
  Geplanter Testlauf fuer BelegTool auf dem Windows-Entwicklungs-PC (Anleitung: docs/windows-pc-testlauf.md).

.DESCRIPTION
  Fuehrt die automatischen Phasen 0-2 aus und protokolliert pro Phase OK / WARNUNG / FEHLER /
  UEBERSPRUNGEN / OFFEN. Eine fehlgeschlagene Phase bricht den Lauf NICHT ab.
  Schreibt testlauf-out\testlauf-ergebnis.md (Tabelle Phase | Ergebnis | Dauer | Hinweis) und Einzel-Logs
  nach testlauf-out\logs\.

  Aendert nichts ausserhalb des Repos und des Ordners testlauf-out\ (pip-, npm- und Playwright-Caches werden
  dorthin umgeleitet). Keine Admin-Rechte noetig. Innerhalb des Repos entstehen die ueblichen Build-Artefakte
  (webui\node_modules, webui\dist, dist\, build\, .build_venv\, .pytest_cache).

  STATUS: Skript auf Linux nur syntaktisch geprueft, auf Windows noch nicht gelaufen.

.PARAMETER SkipBuild
  Phase 2 (build.ps1, Bundle-Pruefung, Exe-Smoketest) auslassen.

.PARAMETER SkipE2E
  Playwright (e2e + CSP-Spec) auslassen: nur vitest statt npm run test:all; kein Chromium-Download.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows_testlauf.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows_testlauf.ps1 -SkipBuild -SkipE2E
#>
param(
    [switch]$SkipBuild,
    [switch]$SkipE2E
)

$ErrorActionPreference = 'Continue'
$script:Root = Split-Path -Parent $PSScriptRoot
$script:Out = Join-Path $script:Root 'testlauf-out'
$script:LogDir = Join-Path $script:Out 'logs'
$script:Results = New-Object System.Collections.ArrayList
$script:Details = New-Object System.Collections.ArrayList
$script:VenvPy = Join-Path $script:Out 'venv\Scripts\python.exe'
$script:Phase0Ok = $false
$script:HasOffice = $false
$script:BuildExists = $false
$script:EnvInfo = New-Object System.Collections.ArrayList

Set-Location $script:Root
New-Item -ItemType Directory -Force -Path $script:Out, $script:LogDir | Out-Null

# Alles, was Werkzeuge sonst im Benutzerprofil ablegen, nach testlauf-out umleiten.
$env:PIP_CACHE_DIR = Join-Path $script:Out 'pip-cache'
$env:npm_config_cache = Join-Path $script:Out 'npm-cache'
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $script:Out 'pw-browsers'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
$env:PYTHONIOENCODING = 'utf-8'

# ---------------------------------------------------------------- Hilfsfunktionen

function Redact([string]$s) {
    # Keine lokalen Pfade/Benutzernamen in das Ergebnis schreiben.
    if (-not $s) { return '' }
    $s = $s.Replace($script:Root, '<repo>')
    if ($env:USERPROFILE) { $s = $s.Replace($env:USERPROFILE, '%USERPROFILE%') }
    return $s
}

function New-Res([string]$Status, [string]$Note) {
    return @{ Status = $Status; Note = $Note }
}

function Add-Result([string]$Phase, [string]$Status, [string]$Dauer, [string]$Note) {
    $clean = (Redact $Note) -replace '[\r\n]+', ' ' -replace '\|', '/'
    [void]$script:Results.Add([pscustomobject]@{ Phase = $Phase; Ergebnis = $Status; Dauer = $Dauer; Hinweis = $clean })
}

function Format-Dauer($ts) {
    return ('{0}:{1:00} min' -f ([int][math]::Floor($ts.TotalMinutes)), $ts.Seconds)
}

function Invoke-Phase([string]$Name, [scriptblock]$Body) {
    Write-Host ''
    Write-Host ('=== ' + $Name + ' ===') -ForegroundColor Cyan
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $status = 'OK'
    $note = ''
    try {
        $r = @(& $Body) | Select-Object -Last 1
        if ($r -is [hashtable]) { $status = $r.Status; $note = $r.Note }
        else { $status = 'FEHLER'; $note = 'Phase lieferte kein Ergebnis (Skriptfehler)' }
    }
    catch {
        $status = 'FEHLER'
        $note = 'Ausnahme: ' + $_.Exception.Message
    }
    $sw.Stop()
    $color = 'Green'
    if ($status -eq 'FEHLER') { $color = 'Red' }
    elseif ($status -eq 'WARNUNG') { $color = 'Yellow' }
    elseif ($status -ne 'OK') { $color = 'Gray' }
    Write-Host ('    -> ' + $status + ' (' + (Format-Dauer $sw.Elapsed) + ') ' + (Redact $note)) -ForegroundColor $color
    Add-Result $Name $status (Format-Dauer $sw.Elapsed) $note
}

function Invoke-Native([string]$LogName, [string]$Exe, [string]$ArgLine, [string]$WorkDir) {
    # Startet ein Programm, schreibt stdout+stderr nach logs\<LogName>.log, liefert den Exitcode.
    $log = Join-Path $script:LogDir ($LogName + '.log')
    $err = $log + '.err'
    Remove-Item $log, $err -ErrorAction SilentlyContinue
    try {
        $p = Start-Process -FilePath $Exe -ArgumentList $ArgLine -WorkingDirectory $WorkDir `
            -RedirectStandardOutput $log -RedirectStandardError $err -NoNewWindow -Wait -PassThru -ErrorAction Stop
        $p.WaitForExit()
        $code = $p.ExitCode
    }
    catch {
        Set-Content -Path $log -Value ('Start fehlgeschlagen: ' + $_.Exception.Message)
        return 9009
    }
    if (Test-Path $err) {
        $e = Get-Content $err -ErrorAction SilentlyContinue
        if ($e) { Add-Content -Path $log -Value '--- stderr ---'; Add-Content -Path $log -Value $e }
        Remove-Item $err -ErrorAction SilentlyContinue
    }
    if ($null -eq $code) { return 0 }
    return [int]$code
}

function Get-LogLine([string]$LogName, [string]$Pattern) {
    $log = Join-Path $script:LogDir ($LogName + '.log')
    if (-not (Test-Path $log)) { return '' }
    $m = Get-Content $log -ErrorAction SilentlyContinue | Where-Object { $_ -match $Pattern } | Select-Object -Last 1
    if ($m) { return ([string]$m).Trim() }
    return ''
}

function Get-LogTail([string]$LogName, [int]$N) {
    $log = Join-Path $script:LogDir ($LogName + '.log')
    if (-not (Test-Path $log)) { return '(kein Log)' }
    $t = Get-Content $log -ErrorAction SilentlyContinue | Where-Object { $_ -and $_.Trim() } | Select-Object -Last $N
    return (($t | ForEach-Object { ([string]$_).Trim() }) -join ' // ')
}

function Add-Detail([string]$Line) {
    [void]$script:Details.Add($Line)
}

function Get-WebView2Version {
    $guid = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
    $keys = @(
        ('HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + $guid),
        ('HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\' + $guid),
        ('HKCU:\Software\Microsoft\EdgeUpdate\Clients\' + $guid)
    )
    foreach ($k in $keys) {
        try {
            $v = (Get-ItemProperty -Path $k -ErrorAction Stop).pv
            if ($v -and $v -ne '0.0.0.0') { return [string]$v }
        }
        catch { }
    }
    return $null
}

function Test-OfficeApp([string]$ProgId) {
    return (Test-Path ('Registry::HKEY_CLASSES_ROOT\' + $ProgId + '\CLSID'))
}

function Initialize-Venv([string]$VenvDir) {
    $py = Join-Path $VenvDir 'Scripts\python.exe'
    if (Test-Path $py) { return 0 }
    return (Invoke-Native ('venv-' + (Split-Path -Leaf $VenvDir)) 'py' ('-3.13 -m venv "' + $VenvDir + '"') $script:Root)
}

# ---------------------------------------------------------------- Phase 0

Invoke-Phase '0 Voraussetzungen' {
    $problems = New-Object System.Collections.ArrayList
    $warns = New-Object System.Collections.ArrayList

    # Windows / Git / Branch
    $os = ''
    try { $os = (Get-CimInstance Win32_OperatingSystem).Caption + ' ' + (Get-CimInstance Win32_OperatingSystem).Version } catch { $os = 'unbekannt' }
    [void]$script:EnvInfo.Add('Windows: ' + $os)

    $gitVer = (& git --version 2>$null)
    if (-not $gitVer) { [void]$problems.Add('git fehlt') }
    $branch = ''
    $commit = ''
    if ($gitVer) {
        $branch = [string](& git rev-parse --abbrev-ref HEAD 2>$null)
        $commit = [string](& git rev-parse --short HEAD 2>$null)
    }
    [void]$script:EnvInfo.Add('Branch: ' + $branch + ' @ ' + $commit)
    if ($branch -and $branch -ne 'claude/exciting-hawking-ifv36m' -and $branch -ne 'master') {
        [void]$warns.Add('Branch ist "' + $branch + '" (erwartet: claude/exciting-hawking-ifv36m oder master)')
    }

    # Git LFS
    $lfs = (& git lfs version 2>$null)
    if (-not $lfs) {
        [void]$problems.Add('git lfs fehlt')
    }
    else {
        $c = Invoke-Native 'p0-lfs-pull' 'git' 'lfs pull' $script:Root
        if ($c -ne 0) { [void]$problems.Add('git lfs pull Exitcode ' + $c) }
    }
    $probe = Join-Path $script:Root 'tests\data\input\compress_sample.pdf'
    if (Test-Path $probe) {
        $fs = [System.IO.File]::OpenRead($probe)
        $buf = New-Object byte[] 5
        [void]$fs.Read($buf, 0, 5)
        $fs.Close()
        $head = [System.Text.Encoding]::ASCII.GetString($buf)
        if ($head -ne '%PDF-') { [void]$problems.Add('tests\data\input\compress_sample.pdf ist ein LFS-Zeiger (git lfs pull hat nicht gegriffen)') }
    }
    else { [void]$problems.Add('tests\data\input\compress_sample.pdf fehlt') }

    # Python 3.13 (py-Launcher), Node, npm
    $pyv = (& py -3.13 --version 2>$null)
    if (-not $pyv) { [void]$problems.Add('Python 3.13 (py -3.13) fehlt') } else { [void]$script:EnvInfo.Add('Python: ' + $pyv) }
    $nodev = (& node --version 2>$null)
    if (-not $nodev) { [void]$problems.Add('Node.js fehlt') } else { [void]$script:EnvInfo.Add('Node: ' + $nodev) }
    $npmv = (& cmd.exe /c 'npm.cmd --version' 2>$null)
    if (-not $npmv) { [void]$problems.Add('npm fehlt') } else { [void]$script:EnvInfo.Add('npm: ' + $npmv) }

    # WebView2 / Edge
    $wv = Get-WebView2Version
    if ($wv) { [void]$script:EnvInfo.Add('WebView2-Runtime: ' + $wv) }
    else { [void]$problems.Add('WebView2-Runtime nicht gefunden (Registry)'); [void]$script:EnvInfo.Add('WebView2-Runtime: NICHT gefunden') }
    $edge1 = Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'
    $edge2 = Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'
    if ((Test-Path $edge1) -or (Test-Path $edge2)) { [void]$script:EnvInfo.Add('Edge: vorhanden') }
    else { [void]$warns.Add('Edge (msedge.exe) nicht gefunden - nur fuer den Testkit-Build noetig'); [void]$script:EnvInfo.Add('Edge: nicht gefunden') }

    # Office
    $w = Test-OfficeApp 'Word.Application'
    $x = Test-OfficeApp 'Excel.Application'
    $pp = Test-OfficeApp 'PowerPoint.Application'
    $script:HasOffice = ($w -or $x -or $pp)
    $o = 'Office: Word=' + $(if ($w) { 'ja' } else { 'nein' }) + ', Excel=' + $(if ($x) { 'ja' } else { 'nein' }) + ', PowerPoint=' + $(if ($pp) { 'ja' } else { 'nein' })
    [void]$script:EnvInfo.Add($o)

    # Test-venv + Abhaengigkeiten + npm + Playwright
    if ($problems.Count -eq 0) {
        $c = Initialize-Venv (Join-Path $script:Out 'venv')
        if ($c -ne 0) { [void]$problems.Add('venv anlegen Exitcode ' + $c) }
        else {
            $c = Invoke-Native 'p0-pip-upgrade' $script:VenvPy '-m pip install --upgrade pip' $script:Root
            if ($c -ne 0) { [void]$warns.Add('pip-Upgrade Exitcode ' + $c) }
            $c = Invoke-Native 'p0-pip-install' $script:VenvPy '-m pip install -r requirements.txt -r requirements-dev.txt' $script:Root
            if ($c -ne 0) { [void]$problems.Add('pip install Exitcode ' + $c + ' (Log p0-pip-install.log)') }
        }
        $c = Invoke-Native 'p0-npm-ci' 'cmd.exe' '/c npm.cmd ci' (Join-Path $script:Root 'webui')
        if ($c -ne 0) { [void]$problems.Add('npm ci Exitcode ' + $c + ' (Log p0-npm-ci.log)') }
        if (-not $SkipE2E) {
            $c = Invoke-Native 'p0-playwright-install' 'cmd.exe' '/c npx.cmd playwright install chromium' (Join-Path $script:Root 'webui')
            if ($c -ne 0) { [void]$problems.Add('playwright install chromium Exitcode ' + $c) }
        }
    }

    $script:Phase0Ok = ($problems.Count -eq 0)
    if ($problems.Count -gt 0) { return (New-Res 'FEHLER' (($problems -join '; ') + $(if ($warns.Count) { ' | Warnungen: ' + ($warns -join '; ') } else { '' }))) }
    if ($warns.Count -gt 0) { return (New-Res 'WARNUNG' ($warns -join '; ')) }
    return (New-Res 'OK' ('Office: ' + $(if ($script:HasOffice) { 'ja' } else { 'nein' }) + '; WebView2 ' + $wv))
}

# ---------------------------------------------------------------- Phase 1

$skipPh1 = 'Phase 0 nicht erfolgreich (siehe oben)'

Invoke-Phase '1a pytest Hauptrepo' {
    if (-not $script:Phase0Ok) { return (New-Res 'UEBERSPRUNGEN' $skipPh1) }
    $c = Invoke-Native '1a-pytest' $script:VenvPy '-m pytest -q -rs' $script:Root
    $sum = Get-LogLine '1a-pytest' '(passed|failed|error)'
    $skipOffice = Get-LogLine '1a-pytest' 'office|Office'
    $note = $sum
    if (-not $script:HasOffice) { $note = $note + ' (ohne Office: Office-Golden uebersprungen erwartet)' }
    elseif ($skipOffice -match 'SKIP') { $note = $note + ' | Office-Tests wurden trotz Office uebersprungen: ' + $skipOffice }
    if ($c -ne 0) { return (New-Res 'FEHLER' ('Exitcode ' + $c + ': ' + $note)) }
    if ($script:HasOffice -and $skipOffice -match 'SKIP') { return (New-Res 'WARNUNG' $note) }
    return (New-Res 'OK' $note)
}

$pkgDirs = @()
if (Test-Path (Join-Path $script:Root 'packages')) {
    $pkgDirs = @(Get-ChildItem (Join-Path $script:Root 'packages') -Directory | Sort-Object Name)
}
foreach ($pd in $pkgDirs) {
    $pkgName = $pd.Name
    $pkgPath = $pd.FullName
    Invoke-Phase ('1b pytest Paket ' + $pkgName) {
        if (-not $script:Phase0Ok) { return (New-Res 'UEBERSPRUNGEN' $skipPh1) }
        if (-not (Test-Path (Join-Path $pkgPath 'pyproject.toml'))) { return (New-Res 'UEBERSPRUNGEN' 'keine pyproject.toml') }
        $venv = Join-Path $script:Out ('pkgvenv\' + $pkgName)
        $pyp = Join-Path $venv 'Scripts\python.exe'
        $c = Initialize-Venv $venv
        if ($c -ne 0) { return (New-Res 'FEHLER' ('venv anlegen Exitcode ' + $c)) }
        $c = Invoke-Native ('1b-' + $pkgName + '-install') $pyp '-m pip install -e ".[dev]"' $pkgPath
        if ($c -ne 0) { return (New-Res 'FEHLER' ('pip install -e .[dev] Exitcode ' + $c + ': ' + (Get-LogTail ('1b-' + $pkgName + '-install') 2))) }
        $c = Invoke-Native ('1b-' + $pkgName + '-pytest') $pyp '-m pytest -q -rs' $pkgPath
        $sum = Get-LogLine ('1b-' + $pkgName + '-pytest') '(passed|failed|error)'
        if ($c -ne 0) { return (New-Res 'FEHLER' ('Exitcode ' + $c + ': ' + $sum)) }
        return (New-Res 'OK' $sum)
    }
}

Invoke-Phase '1c npm run lint' {
    if (-not $script:Phase0Ok) { return (New-Res 'UEBERSPRUNGEN' $skipPh1) }
    $c = Invoke-Native '1c-lint' 'cmd.exe' '/c npm.cmd run lint' (Join-Path $script:Root 'webui')
    if ($c -ne 0) { return (New-Res 'FEHLER' ('Exitcode ' + $c + ': ' + (Get-LogTail '1c-lint' 4))) }
    return (New-Res 'OK' '0 Fehler')
}

Invoke-Phase '1d npm run test:all (vitest + Playwright + CSP)' {
    if (-not $script:Phase0Ok) { return (New-Res 'UEBERSPRUNGEN' $skipPh1) }
    if ($SkipE2E) {
        $c = Invoke-Native '1d-vitest' 'cmd.exe' '/c npm.cmd test' (Join-Path $script:Root 'webui')
        $sum = Get-LogLine '1d-vitest' 'Tests'
        if ($c -ne 0) { return (New-Res 'FEHLER' ('vitest Exitcode ' + $c + ': ' + $sum)) }
        return (New-Res 'WARNUNG' ('-SkipE2E: nur vitest, Playwright/CSP NICHT gelaufen. ' + $sum))
    }
    $c = Invoke-Native '1d-test-all' 'cmd.exe' '/c npm.cmd run test:all' (Join-Path $script:Root 'webui')
    $sum = Get-LogLine '1d-test-all' '(passed|failed)'
    if ($c -ne 0) { return (New-Res 'FEHLER' ('Exitcode ' + $c + ': ' + (Get-LogTail '1d-test-all' 4))) }
    return (New-Res 'OK' $sum)
}

Invoke-Phase '1e npm run build' {
    if (-not $script:Phase0Ok) { return (New-Res 'UEBERSPRUNGEN' $skipPh1) }
    $c = Invoke-Native '1e-build' 'cmd.exe' '/c npm.cmd run build' (Join-Path $script:Root 'webui')
    if ($c -ne 0) { return (New-Res 'FEHLER' ('Exitcode ' + $c + ': ' + (Get-LogTail '1e-build' 4))) }
    return (New-Res 'OK' 'vite build erfolgreich')
}

# ---------------------------------------------------------------- Phase 2

$dist = Join-Path $script:Root 'dist\BelegTool'
$internal = Join-Path $dist '_internal'
$exe = Join-Path $dist 'BelegTool.exe'

Invoke-Phase '2a build.ps1' {
    if ($SkipBuild) { return (New-Res 'UEBERSPRUNGEN' '-SkipBuild') }
    if (-not $script:Phase0Ok) { return (New-Res 'UEBERSPRUNGEN' $skipPh1) }
    # build.ps1 loescht build\, dist\ und .build_venv\ im Repo und baut neu (siehe Skript).
    $c = Invoke-Native '2a-build' 'powershell.exe' ('-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $script:Root 'build.ps1') + '"') $script:Root
    if (Test-Path $exe) { $script:BuildExists = $true }
    if ($c -ne 0) { return (New-Res 'FEHLER' ('Exitcode ' + $c + ': ' + (Get-LogTail '2a-build' 4))) }
    if (-not (Test-Path $exe)) { return (New-Res 'FEHLER' 'build.ps1 endete ohne Fehler, aber dist\BelegTool\BelegTool.exe fehlt (PyInstaller-Fehler: Log 2a-build.log)') }
    return (New-Res 'OK' 'dist\BelegTool\BelegTool.exe vorhanden')
}

$bundleHelper = @'
# Hilfsskript (vom Testlauf erzeugt): prueft, welche Module im PyInstaller-Bundle (PYZ) stecken.
import re, sys
exe, toc_file = sys.argv[1], sys.argv[2]
REQ = ["datev", "belegtool_archives", "belegtool_compress", "pi_heif"]
FORBID = ["pillow_heif"]
INFO = ["extract_msg", "fitz"]
names = None
source = ""
try:
    from PyInstaller.archive.readers import CArchiveReader
    r = CArchiveReader(exe)
    for key in r.toc:
        if key.endswith(".pyz"):
            names = set(r.open_embedded_archive(key).toc.keys())
            source = "PYZ der Exe"
            break
except Exception as e:
    print("NOTE CArchiveReader fehlgeschlagen: %s" % e)
if names is None:
    try:
        text = open(toc_file, encoding="utf-8", errors="replace").read()
        names = set(re.findall(r"\('([A-Za-z0-9_.]+)',\s*'", text))
        source = "PYZ-00.toc (Fallback)"
    except Exception as e:
        print("ERROR kein PYZ lesbar: %s" % e)
        sys.exit(2)
print("SOURCE " + source)
def has(n):
    return any(k == n or k.startswith(n + ".") for k in names)
for n in REQ:
    print("REQ %s %s" % (n, "yes" if has(n) else "no"))
for n in FORBID:
    print("FORBID %s %s" % (n, "yes" if has(n) else "no"))
for n in INFO:
    print("INFO %s %s" % (n, "yes" if has(n) else "no"))
'@

Invoke-Phase '2b Bundle-Pruefung' {
    if ($SkipBuild -and -not (Test-Path $exe)) { return (New-Res 'UEBERSPRUNGEN' '-SkipBuild und kein vorhandenes dist\BelegTool') }
    if (-not (Test-Path $exe)) { return (New-Res 'FEHLER' 'kein Build vorhanden (dist\BelegTool\BelegTool.exe fehlt)') }
    $script:BuildExists = $true
    $fails = New-Object System.Collections.ArrayList
    $infos = New-Object System.Collections.ArrayList
    Add-Detail ''
    Add-Detail '### Bundle-Pruefung dist\BelegTool'
    Add-Detail ''

    # 1. Lizenztexte (neben der Exe UND/ODER in _internal)
    foreach ($f in @('COPYING', 'LICENSE', 'THIRD_PARTY_NOTICES.md')) {
        $where = @()
        if (Test-Path (Join-Path $dist $f)) { $where += 'neben der Exe' }
        if (Test-Path (Join-Path $internal $f)) { $where += '_internal' }
        if ($where.Count -eq 0) { [void]$fails.Add($f + ' fehlt'); Add-Detail ('- FEHLT: ' + $f) }
        else { Add-Detail ('- ok: ' + $f + ' in: ' + ($where -join ' + ')); [void]$infos.Add($f + '=' + ($where -join '+')) }
    }

    # 2. Python-Module im PYZ
    $helper = Join-Path $script:Out 'bundle_check.py'
    Set-Content -Path $helper -Value $bundleHelper -Encoding ASCII
    $py = Join-Path $script:Root '.build_venv\Scripts\python.exe'
    if (-not (Test-Path $py)) { $py = $script:VenvPy }
    $toc = Join-Path $script:Root 'build\belegtool\PYZ-00.toc'
    $c = Invoke-Native '2b-pyz' $py ('"' + $helper + '" "' + $exe + '" "' + $toc + '"') $script:Root
    $modLog = Join-Path $script:LogDir '2b-pyz.log'
    $pyzTxt = ''
    if (Test-Path $modLog) { $pyzTxt = Get-Content $modLog }
    if ($c -ne 0 -or -not $pyzTxt) { [void]$fails.Add('Modulpruefung (PYZ) nicht moeglich, Log 2b-pyz.log') }
    else {
        foreach ($line in $pyzTxt) {
            $parts = ([string]$line).Trim() -split '\s+'
            if ($parts.Count -ge 3) {
                $kind = $parts[0]; $mod = $parts[1]; $yes = ($parts[2] -eq 'yes')
                # zusaetzlich: als Datei/Ordner in _internal (Erweiterungsmodule liegen dort, nicht im PYZ)
                $inDir = $false
                if (Test-Path $internal) { $inDir = [bool](Get-ChildItem $internal -Directory -Filter ($mod + '*') -ErrorAction SilentlyContinue | Select-Object -First 1) }
                $present = ($yes -or $inDir)
                $loc = @(); if ($yes) { $loc += 'PYZ' }; if ($inDir) { $loc += '_internal' }
                if ($kind -eq 'REQ') {
                    if ($present) { Add-Detail ('- ok: Modul ' + $mod + ' im Bundle (' + ($loc -join '+') + ')') }
                    else {
                        [void]$fails.Add('Modul ' + $mod + ' fehlt im Bundle')
                        Add-Detail ('- FEHLT: Modul ' + $mod + ' im Bundle')
                    }
                }
                elseif ($kind -eq 'FORBID') {
                    if ($present) { [void]$fails.Add('verbotenes Modul ' + $mod + ' im Bundle'); Add-Detail ('- VERBOTEN VORHANDEN: ' + $mod + ' (' + ($loc -join '+') + ')') }
                    else { Add-Detail ('- ok: ' + $mod + ' nicht im Bundle') }
                }
                elseif ($kind -eq 'SOURCE' -or $kind -eq 'NOTE') { Add-Detail ('- ' + ([string]$line).Trim()) }
                elseif ($kind -eq 'INFO') { Add-Detail ('- Info: ' + $mod + ' im Bundle: ' + $(if ($present) { 'ja' } else { 'nein' })) }
            }
            elseif (([string]$line) -match '^(SOURCE|NOTE)') { Add-Detail ('- ' + ([string]$line).Trim()) }
        }
    }

    # 3. keine x265-Datei
    $x265 = @(Get-ChildItem $dist -Recurse -File -Filter '*x265*' -ErrorAction SilentlyContinue)
    if ($x265.Count -gt 0) {
        [void]$fails.Add([string]$x265.Count + ' Datei(en) *x265* im Bundle')
        foreach ($f in $x265) { Add-Detail ('- VERBOTEN VORHANDEN: ' + $f.FullName.Replace($script:Root, '<repo>')) }
    }
    else { Add-Detail '- ok: keine Datei *x265*' }

    # 4. webui/dist mit CSP-Meta
    $web = Join-Path $internal 'webui\dist'
    if (-not (Test-Path $web)) { $web = Join-Path $dist 'webui\dist' }
    if (-not (Test-Path $web)) { [void]$fails.Add('webui\dist fehlt im Bundle'); Add-Detail '- FEHLT: webui\dist' }
    else {
        foreach ($h in @('index.html', 'pdf-tool.html')) {
            $hp = Join-Path $web $h
            if (-not (Test-Path $hp)) { [void]$fails.Add($h + ' fehlt'); Add-Detail ('- FEHLT: ' + $h) }
            elseif (Select-String -Path $hp -SimpleMatch 'Content-Security-Policy' -Quiet) { Add-Detail ('- ok: CSP-Meta in ' + $h) }
            else { [void]$fails.Add('CSP-Meta fehlt in ' + $h); Add-Detail ('- FEHLT: CSP-Meta in ' + $h) }
        }
        if (Test-Path (Join-Path $web 'pdfjs\wasm')) { Add-Detail '- ok: pdfjs\wasm vorhanden' }
        else { [void]$fails.Add('pdfjs\wasm fehlt (gescannte PDFs wuerden leer rendern)'); Add-Detail '- FEHLT: pdfjs\wasm' }
    }

    if ($fails.Count -gt 0) {
        return (New-Res 'FEHLER' (($fails -join '; ') + ' | Hinweis: pi_heif/pillow_heif/x265-Befunde sind VOR der HEIC-Umstellung auf pi-heif (siehe docs/pymupdf-extract-msg-ersatz.md) erwartbar'))
    }
    return (New-Res 'OK' ('Lizenztexte: ' + ($infos -join ', ')))
}

Invoke-Phase '2c Exe-Smoketest' {
    if ($SkipBuild -and -not (Test-Path $exe)) { return (New-Res 'UEBERSPRUNGEN' '-SkipBuild und kein vorhandenes dist\BelegTool') }
    if (-not (Test-Path $exe)) { return (New-Res 'FEHLER' 'kein Build vorhanden') }
    $warn = New-Object System.Collections.ArrayList
    $fail = New-Object System.Collections.ArrayList
    Add-Detail ''
    Add-Detail '### Exe-Smoketest'
    Add-Detail ''

    # Einstellungen (settings.json/window.json) des Smoketests landen in testlauf-out, nicht im echten %APPDATA%.
    $fakeAppData = Join-Path $script:Out 'appdata'
    New-Item -ItemType Directory -Force -Path $fakeAppData | Out-Null
    $oldAppData = $env:APPDATA
    $env:APPDATA = $fakeAppData
    $startTime = Get-Date
    $proc = $null
    try {
        $proc = Start-Process -FilePath $exe -WorkingDirectory $dist -PassThru -ErrorAction Stop
    }
    catch {
        $env:APPDATA = $oldAppData
        return (New-Res 'FEHLER' ('Exe liess sich nicht starten: ' + $_.Exception.Message))
    }
    $env:APPDATA = $oldAppData
    try {
        Start-Sleep -Seconds 10
        $proc.Refresh()
        if ($proc.HasExited) {
            [void]$fail.Add('Prozess nach 10 s bereits beendet, Exitcode ' + $proc.ExitCode)
            Add-Detail ('- FEHLER: Prozess beendet, Exitcode ' + $proc.ExitCode)
        }
        else {
            Add-Detail '- ok: Prozess laeuft nach 10 s'
            $title = [string]$proc.MainWindowTitle
            if ($proc.MainWindowHandle -ne [IntPtr]::Zero) { Add-Detail ('- ok: Hauptfenster vorhanden, Titel: ' + $title) }
            else { [void]$warn.Add('kein Hauptfenster-Handle erkannt'); Add-Detail '- WARNUNG: kein Hauptfenster-Handle' }
            $wv = @()
            try {
                $wv = @(Get-CimInstance Win32_Process -Filter "Name='msedgewebview2.exe'" -ErrorAction Stop |
                        Where-Object { $_.CreationDate -ge $startTime.AddSeconds(-2) })
            }
            catch { }
            if ($wv.Count -gt 0) { Add-Detail ('- ok: ' + $wv.Count + ' WebView2-Prozess(e) seit dem Start') }
            else { [void]$fail.Add('kein msedgewebview2.exe-Prozess seit dem Start (UI vermutlich leer)'); Add-Detail '- FEHLER: kein WebView2-Prozess' }
        }
    }
    finally {
        if ($proc -and -not $proc.HasExited) {
            [void]$proc.CloseMainWindow()
            if (-not $proc.WaitForExit(10000)) {
                [void]$warn.Add('Exe reagierte nicht auf Fenster schliessen, wurde beendet')
                Add-Detail '- WARNUNG: Fenster schliessen wirkungslos, Prozess hart beendet'
                try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch { }
                Get-CimInstance Win32_Process -Filter "Name='msedgewebview2.exe'" -ErrorAction SilentlyContinue |
                    Where-Object { $_.CreationDate -ge $startTime.AddSeconds(-2) } |
                    ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch { } }
            }
            else { Add-Detail '- ok: sauber beendet (Fenster schliessen)' }
        }
    }

    # Startup-Log auswerten
    $logCands = @(
        (Join-Path $dist 'belegtool_startup.log'),
        (Join-Path $fakeAppData 'DigitalerUnterlagenOrdner\belegtool_startup.log'),
        (Join-Path ([System.IO.Path]::GetTempPath()) 'belegtool_startup.log')
    )
    $sl = $null
    foreach ($cand in $logCands) { if (Test-Path $cand) { $sl = $cand; break } }
    if (-not $sl) { [void]$fail.Add('belegtool_startup.log nicht gefunden'); Add-Detail '- FEHLER: kein belegtool_startup.log' }
    else {
        $txt = Get-Content $sl -ErrorAction SilentlyContinue
        Copy-Item $sl (Join-Path $script:LogDir '2c-belegtool_startup.log') -Force -ErrorAction SilentlyContinue
        if (-not ($txt -match 'entering GUI loop')) { [void]$fail.Add('Startup-Log ohne "entering GUI loop" (Start nicht bis zum Fenster gekommen)'); Add-Detail '- FEHLER: Startup-Log ohne "entering GUI loop"' }
        else { Add-Detail '- ok: Startup-Log erreicht "entering GUI loop"' }
        $bad = @($txt | Where-Object { $_ -match 'Traceback|Exception|ERROR|Error' } | Select-Object -First 3)
        if ($bad.Count -gt 0) { [void]$warn.Add('Auffaelligkeiten im Startup-Log (' + $bad.Count + '+)'); Add-Detail ('- WARNUNG: Startup-Log: ' + (($bad | ForEach-Object { ([string]$_).Trim() }) -join ' // ')) }
        else { Add-Detail '- ok: keine Fehlerzeilen im Startup-Log' }
        $pre = @($txt | Where-Object { $_ -match 'elapsed BEFORE main' } | Select-Object -First 1)
        if ($pre.Count -gt 0) { Add-Detail ('- Info: ' + ([string]$pre[0]).Trim()) }
    }

    if ($fail.Count -gt 0) { return (New-Res 'FEHLER' ($fail -join '; ')) }
    if ($warn.Count -gt 0) { return (New-Res 'WARNUNG' ($warn -join '; ')) }
    return (New-Res 'OK' 'Exe lief 10 s, WebView2 vorhanden, sauber beendet')
}

# ---------------------------------------------------------------- Phasen 3-5 (nicht automatisch)

Invoke-Phase '3 Echte GUI per CDP (Playwright/WebView2)' {
    if (Test-Path (Join-Path $script:Root 'tests\gui\launch_host.py')) {
        return (New-Res 'OFFEN' 'tests\gui\launch_host.py vorhanden, wird von diesem Skript aber nicht aufgerufen - siehe docs/windows-pc-testlauf.md Phase 3')
    }
    return (New-Res 'UEBERSPRUNGEN' 'nicht implementiert (Plan Ebene G, docs/test-automation-plan.md; tests\gui\ existiert nicht)')
}
Invoke-Phase '4 Manuell-kurz' { return (New-Res 'OFFEN' 'von Hand, Checkliste: docs/windows-pc-testlauf.md Phase 4') }
Invoke-Phase '5 Paritaetsvergleich (nach PyMuPDF-Austausch)' { return (New-Res 'OFFEN' 'Platzhalter: erst nach dem Merge des Austauschs, docs/windows-pc-testlauf.md Phase 5') }

# ---------------------------------------------------------------- Ergebnis schreiben

$resultFile = Join-Path $script:Out 'testlauf-ergebnis.md'
$gitChanged = ''
try {
    $st = @(& git status --porcelain 2>$null | Where-Object { $_ -notmatch 'testlauf-out' })
    $gitChanged = [string]$st.Count
}
catch { $gitChanged = '?' }

$md = New-Object System.Collections.ArrayList
[void]$md.Add('# Testlauf-Ergebnis')
[void]$md.Add('')
[void]$md.Add('Skript: scripts/windows_testlauf.ps1 (auf Linux nur syntaktisch geprueft, auf Windows erstmals mit diesem Lauf)')
[void]$md.Add('Datum: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm'))
[void]$md.Add('Parameter: SkipBuild=' + $SkipBuild.IsPresent + ', SkipE2E=' + $SkipE2E.IsPresent)
[void]$md.Add('')
[void]$md.Add('## Umgebung')
[void]$md.Add('')
foreach ($e in $script:EnvInfo) { [void]$md.Add('- ' + (Redact ([string]$e))) }
[void]$md.Add('- Geaenderte/neue Dateien im Repo ausserhalb testlauf-out (git status): ' + $gitChanged)
[void]$md.Add('')
[void]$md.Add('## Ergebnis')
[void]$md.Add('')
[void]$md.Add('| Phase | Ergebnis | Dauer | Hinweis |')
[void]$md.Add('|---|---|---|---|')
foreach ($r in $script:Results) {
    [void]$md.Add('| ' + $r.Phase + ' | ' + $r.Ergebnis + ' | ' + $r.Dauer + ' | ' + $r.Hinweis + ' |')
}
if ($script:Details.Count -gt 0) {
    [void]$md.Add('')
    [void]$md.Add('## Details')
    foreach ($d in $script:Details) { [void]$md.Add((Redact ([string]$d))) }
}
[void]$md.Add('')
[void]$md.Add('Logs der Einzelschritte: testlauf-out\logs\ (nicht mitschicken, ausser auf Nachfrage; koennen lokale Pfade enthalten).')
Set-Content -Path $resultFile -Value $md -Encoding UTF8

Write-Host ''
Write-Host ('Ergebnis: ' + $resultFile) -ForegroundColor Cyan
$nFail = @($script:Results | Where-Object { $_.Ergebnis -eq 'FEHLER' }).Count
$nWarn = @($script:Results | Where-Object { $_.Ergebnis -eq 'WARNUNG' }).Count
Write-Host ('FEHLER: ' + $nFail + ', WARNUNG: ' + $nWarn)
if ($nFail -gt 0) { exit 1 }
exit 0
