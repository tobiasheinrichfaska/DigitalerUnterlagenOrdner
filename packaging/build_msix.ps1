# Build a Store-ready MSIX for BelegTool.
#
#   .\packaging\build_msix.ps1                # build app + pack the Store-upload .msix
#   .\packaging\build_msix.ps1 -SkipBuild     # reuse existing dist\BelegTool
#   .\packaging\build_msix.ps1 -Sign          # ALSO emit a self-signed copy for sideload testing
#
# Outputs (packaging\out\):
#   BelegTool-<ver>-x64.msix             -> UPLOAD this to Partner Center (Microsoft re-signs it).
#   BelegTool-<ver>-x64-TEST-signed.msix -> only with -Sign; for LOCAL sideload testing.
#   BelegTool-test-publisher.cer         -> only with -Sign; trust it once to install the test pkg.
param(
  [switch]$SkipBuild,
  [switch]$Sign,
  [string]$Publisher = "CN=2A87E267-9C96-4414-B440-06EB61A80222"  # must match the manifest Identity/Publisher
)
$ErrorActionPreference = "Stop"
$pkg    = $PSScriptRoot
$root   = Split-Path $pkg -Parent
$dist   = Join-Path $root "dist\BelegTool"
$layout = Join-Path $pkg  "msix_layout"
$out    = Join-Path $pkg  "out"

# 1. Build the PyInstaller onedir output (unless reusing it)
if (-not $SkipBuild) {
  Write-Host "== Building app (build.ps1) =="
  & powershell -ExecutionPolicy Bypass -File (Join-Path $root "build.ps1")
}
if (-not (Test-Path (Join-Path $dist "BelegTool.exe"))) {
  throw "Build output missing: $dist\BelegTool.exe (run without -SkipBuild)"
}

# 2. Version: VERSION="X.Y.Z" -> X.Y.Z.0 (Store reserves the revision)
$vtext = Get-Content (Join-Path $root "version_info.py") -Raw
if ($vtext -notmatch 'VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)"') { throw "Cannot read VERSION from version_info.py" }
$ver = "$($Matches[1]).$($Matches[2]).$($Matches[3]).0"
Write-Host "== Version $ver =="

# 3. Logo/tile assets from assets\icon.ico
& (Join-Path $pkg "generate-assets.ps1")

# 4. Lay out the package root: AppxManifest.xml + Assets\ + BelegTool\ (the onedir payload)
if (Test-Path $layout) { Remove-Item $layout -Recurse -Force }
New-Item -ItemType Directory -Force -Path $layout, $out | Out-Null
Copy-Item (Join-Path $pkg "Assets") (Join-Path $layout "Assets") -Recurse
Copy-Item $dist (Join-Path $layout "BelegTool") -Recurse
$manifest = Get-Content (Join-Path $pkg "AppxManifest.xml") -Raw
$manifest = $manifest -replace 'Version="\d+\.\d+\.\d+\.\d+"', "Version=`"$ver`""
Set-Content (Join-Path $layout "AppxManifest.xml") -Value $manifest -Encoding UTF8

# 5. Find the Windows SDK tools (latest x64)
function Find-SdkTool([string]$name) {
  $base = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
  $hit = Get-ChildItem $base -Recurse -Filter $name -ErrorAction SilentlyContinue |
         Where-Object { $_.FullName -match '\\x64\\' } |
         Sort-Object FullName -Descending | Select-Object -First 1
  if (-not $hit) { throw "$name not found - install the Windows 10/11 SDK (App Certification / Packaging tools)." }
  return $hit.FullName
}
$makeappx = Find-SdkTool "makeappx.exe"

# 6. Pack -> the Store-upload artifact (UNSIGNED; Microsoft signs on ingestion)
$msix = Join-Path $out "BelegTool-$ver-x64.msix"
Write-Host "== Packing $msix =="
& $makeappx pack /o /d $layout /p $msix
if ($LASTEXITCODE -ne 0) { throw "makeappx failed ($LASTEXITCODE)" }
Write-Host "STORE UPLOAD  -> $msix"

# 7. Optional: self-signed cert + signed copy for LOCAL sideload testing only
if ($Sign) {
  $signtool = Find-SdkTool "signtool.exe"
  $cert = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -eq $Publisher } | Select-Object -First 1
  if (-not $cert) {
    Write-Host "== Creating self-signed test cert ($Publisher) =="
    $cert = New-SelfSignedCertificate -Type Custom -Subject $Publisher `
      -KeyUsage DigitalSignature -FriendlyName "BelegTool MSIX test (local only)" `
      -CertStoreLocation Cert:\CurrentUser\My `
      -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3")   # EKU: Code Signing
  }
  $test = Join-Path $out "BelegTool-$ver-x64-TEST-signed.msix"
  Copy-Item $msix $test -Force
  & $signtool sign /fd SHA256 /sha1 $cert.Thumbprint $test
  if ($LASTEXITCODE -ne 0) { throw "signtool failed ($LASTEXITCODE)" }
  $cer = Join-Path $out "BelegTool-test-publisher.cer"
  Export-Certificate -Cert $cert -FilePath $cer | Out-Null
  Write-Host "LOCAL TEST    -> $test"
  Write-Host "Trust the cert ONCE (elevated): Import-Certificate -FilePath '$cer' -CertStoreLocation Cert:\LocalMachine\TrustedPeople"
  Write-Host "Then install:  Add-AppxPackage '$test'"
}
