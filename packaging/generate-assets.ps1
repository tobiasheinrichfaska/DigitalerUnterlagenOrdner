# Generate the MSIX tile/logo PNGs from assets/icon.ico into an output folder.
# Auto-generated assets are fine for a first submission; replace with hand-crafted
# artwork later for crisp large tiles. Windows PowerShell 5.1 (GDI+ via System.Drawing).
param(
  [string]$IconPath = (Join-Path $PSScriptRoot "..\assets\icon.ico"),
  [string]$OutDir   = (Join-Path $PSScriptRoot "Assets"),
  [string]$BackColor = "#1E293B"   # used only for the wide tile's padding
)

Add-Type -AssemblyName System.Drawing
$ErrorActionPreference = "Stop"
if (-not (Test-Path $IconPath)) { throw "Icon not found: $IconPath" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# Load the largest available frame from the .ico (256 if present).
$srcIcon = New-Object System.Drawing.Icon($IconPath, 256, 256)
$src = $srcIcon.ToBitmap()

function Save-Square([int]$size, [string]$name) {
  $bmp = New-Object System.Drawing.Bitmap($size, $size)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
  $g.Clear([System.Drawing.Color]::Transparent)
  $g.DrawImage($src, 0, 0, $size, $size)
  $g.Dispose()
  $path = Join-Path $OutDir $name
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  Write-Host "  $name ($size x $size)"
}

function Save-Wide([int]$w, [int]$h, [string]$name) {
  $bmp = New-Object System.Drawing.Bitmap($w, $h)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
  $g.Clear([System.Drawing.ColorTranslator]::FromHtml($BackColor))
  $s = [Math]::Min($w, $h)                  # centered square icon, full height
  $g.DrawImage($src, [int](($w - $s) / 2), [int](($h - $s) / 2), $s, $s)
  $g.Dispose()
  $path = Join-Path $OutDir $name
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  Write-Host "  $name ($w x $h)"
}

Write-Host "Generating MSIX assets into $OutDir :"
Save-Square 44  "Square44x44Logo.png"
Save-Square 71  "Square71x71Logo.png"
Save-Square 150 "Square150x150Logo.png"
Save-Square 310 "Square310x310Logo.png"
Save-Square 50  "StoreLogo.png"
Save-Wide  310 150 "Wide310x150Logo.png"

$src.Dispose()
$srcIcon.Dispose()
Write-Host "Done."
