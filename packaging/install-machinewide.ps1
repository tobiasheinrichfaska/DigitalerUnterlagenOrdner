<#
.SYNOPSIS
  Machine-wide install of BelegTool (onedir) + HKLM .belegtool association.

.DESCRIPTION
  Installs the PyInstaller onedir build to a machine-wide location and registers the
  .belegtool file type in HKLM, so the association is identical for every user, has no
  per-user state, and survives logoff (the right model for an RDS / multi-user host;
  contrast the per-user MSIX/sideload, which roams badly under FSLogix). Must run elevated.

  Registers:
    HKLM\Software\Classes\.belegtool                 -> ProgId "BelegTool.Document"
    HKLM\Software\Classes\.belegtool\OpenWithProgids -> BelegTool.Document
    HKLM\Software\Classes\BelegTool.Document         (friendly name, DefaultIcon, open command)
    HKLM\Software\Classes\Applications\BelegTool.exe (clean "Open with" entry + SupportedTypes)
    HKLM\...\Uninstall\BelegTool                     (Programs & Features entry)

  Per-user UserChoice for .belegtool outranks HKLM, so any stale per-user association must
  be cleared first (see WindowsNetz items/06-belegtool-rds/Cleanup-BelegtoolAssoc.ps1) or it
  will override this machine-wide handler.

.PARAMETER Source
  The onedir folder that contains BelegTool.exe (default: ..\dist\BelegTool relative to this
  script). Produced by build.ps1.

.PARAMETER InstallDir
  Target (default: C:\Program Files\BelegTool).

.PARAMETER Uninstall
  Remove the association, the Programs & Features entry, and the install directory.

.EXAMPLE
  # elevated, on the target machine:
  powershell -ExecutionPolicy Bypass -File install-machinewide.ps1 -Source .\dist\BelegTool
  powershell -ExecutionPolicy Bypass -File install-machinewide.ps1 -Uninstall
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [string]$Source     = (Join-Path $PSScriptRoot '..\dist\BelegTool'),
  [string]$InstallDir = (Join-Path $env:ProgramFiles 'BelegTool'),
  [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$ProgId  = 'BelegTool.Document'
$ExePath = Join-Path $InstallDir 'BelegTool.exe'
$UninstKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\BelegTool'

# --- must be elevated ---
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw 'This installer must run elevated (Administrator).' }

function Set-Default { param($Path, $Value)
  if (-not (Test-Path $Path)) { New-Item -Path $Path -Force | Out-Null }
  Set-ItemProperty -Path $Path -Name '(default)' -Value $Value
}
function Refresh-Shell {
  Add-Type -Namespace Win32 -Name Shell -MemberDefinition '[DllImport("shell32.dll")] public static extern void SHChangeNotify(int eventId, int flags, System.IntPtr item1, System.IntPtr item2);' -ErrorAction SilentlyContinue
  [Win32.Shell]::SHChangeNotify(0x08000000, 0x0000, [IntPtr]::Zero, [IntPtr]::Zero)  # SHCNE_ASSOCCHANGED
}

if ($Uninstall) {
  if ($PSCmdlet.ShouldProcess('BelegTool', 'Uninstall (assoc + files)')) {
    foreach ($k in @("HKLM:\SOFTWARE\Classes\.belegtool",
                     "HKLM:\SOFTWARE\Classes\$ProgId",
                     'HKLM:\SOFTWARE\Classes\Applications\BelegTool.exe',
                     $UninstKey)) {
      if (Test-Path $k) { Remove-Item $k -Recurse -Force; "removed $k" }
    }
    if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force; "removed $InstallDir" }
    Refresh-Shell
    'BelegTool uninstalled (machine-wide).'
  }
  return
}

# --- install ---
$srcExe = Join-Path $Source 'BelegTool.exe'
if (-not (Test-Path $srcExe)) { throw "Source onedir invalid - BelegTool.exe not found in '$Source' (run build.ps1 first)." }

# WebView2 runtime check (the React UI renders blank without it)
$g = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
$wv2 = $false
foreach ($k in "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\$g","HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$g") {
  $pv = (Get-ItemProperty $k -ErrorAction SilentlyContinue).pv
  if ($pv -and $pv -ne '0.0.0.0') { $wv2 = $true }
}
if (-not $wv2) { Write-Warning 'WebView2 Runtime not detected - the GUI will render blank until it is installed (https://developer.microsoft.com/microsoft-edge/webview2/).' }

if ($PSCmdlet.ShouldProcess($InstallDir, "Install BelegTool onedir + register .belegtool (HKLM)")) {
  # 1. copy payload (mirror = clean update)
  New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
  & robocopy.exe $Source $InstallDir /MIR /R:1 /W:1 /NJH /NJS /NFL /NDL | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed (exit $LASTEXITCODE) copying payload to $InstallDir." }
  if (-not (Test-Path $ExePath)) { throw "Install copy failed - $ExePath missing." }

  # 2. ProgId
  Set-Default "HKLM:\SOFTWARE\Classes\$ProgId" 'BelegTool-Dokument'
  Set-Default "HKLM:\SOFTWARE\Classes\$ProgId\DefaultIcon" ("$ExePath,0")
  Set-Default "HKLM:\SOFTWARE\Classes\$ProgId\shell\open\command" ('"' + $ExePath + '" "%1"')

  # 3. extension -> ProgId
  Set-Default 'HKLM:\SOFTWARE\Classes\.belegtool' $ProgId
  New-Item -Path 'HKLM:\SOFTWARE\Classes\.belegtool\OpenWithProgids' -Force | Out-Null
  New-ItemProperty -Path 'HKLM:\SOFTWARE\Classes\.belegtool\OpenWithProgids' -Name $ProgId -Value ([byte[]]@()) -PropertyType None -Force | Out-Null

  # 4. clean "Open with" application entry
  Set-Default 'HKLM:\SOFTWARE\Classes\Applications\BelegTool.exe\shell\open\command' ('"' + $ExePath + '" "%1"')
  New-Item -Path 'HKLM:\SOFTWARE\Classes\Applications\BelegTool.exe\SupportedTypes' -Force | Out-Null
  New-ItemProperty -Path 'HKLM:\SOFTWARE\Classes\Applications\BelegTool.exe\SupportedTypes' -Name '.belegtool' -Value '' -PropertyType String -Force | Out-Null

  # 5. Programs & Features entry
  $ver = '3.9.5'
  $vinfo = Join-Path $PSScriptRoot '..\version_info.py'
  if (Test-Path $vinfo) { $m = (Get-Content $vinfo | Select-String 'VERSION\s*=\s*"([^"]+)"'); if ($m) { $ver = $m.Matches[0].Groups[1].Value } }
  New-Item -Path $UninstKey -Force | Out-Null
  Set-ItemProperty -Path $UninstKey -Name 'DisplayName'     -Value 'BelegTool'
  Set-ItemProperty -Path $UninstKey -Name 'DisplayVersion'  -Value $ver
  Set-ItemProperty -Path $UninstKey -Name 'Publisher'       -Value 'Tobias Heinrich'
  Set-ItemProperty -Path $UninstKey -Name 'InstallLocation' -Value $InstallDir
  Set-ItemProperty -Path $UninstKey -Name 'DisplayIcon'     -Value "$ExePath,0"
  Set-ItemProperty -Path $UninstKey -Name 'NoModify'        -Value 1 -Type DWord
  Set-ItemProperty -Path $UninstKey -Name 'NoRepair'        -Value 1 -Type DWord
  Set-ItemProperty -Path $UninstKey -Name 'UninstallString' -Value ('powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $InstallDir 'install-machinewide.ps1') + '" -Uninstall')

  # keep a copy of this installer in the install dir (so Uninstall works from P&F)
  Copy-Item -Path $PSCommandPath -Destination (Join-Path $InstallDir 'install-machinewide.ps1') -Force

  Refresh-Shell
  "Installed BelegTool $ver to $InstallDir"
  "Registered .belegtool -> $ProgId -> `"$ExePath`" `"%1`" (HKLM, all users)"
  if (-not $wv2) { 'NOTE: install WebView2 runtime before users launch (warning above).' }
}
