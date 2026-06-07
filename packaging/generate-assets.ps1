# Generate the MSIX tile/logo PNGs from assets/icon.ico into an output folder.
# Uses WPF imaging (System.Windows.Media.Imaging), which decodes PNG-compressed .ico frames
# that the older System.Drawing.Icon GDI+ path chokes on. Windows PowerShell 5.1 (STA).
# Auto-generated assets are fine for a first submission; replace with hand-crafted artwork
# (and per-scale variants) for crisp large tiles later.
param(
  [string]$IconPath  = (Join-Path $PSScriptRoot "..\assets\icon.ico"),
  [string]$OutDir    = (Join-Path $PSScriptRoot "Assets"),
  [string]$BackColor = "#1E293B"   # used only as padding for the wide tile
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase
if (-not (Test-Path $IconPath)) { throw "Icon not found: $IconPath" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# Decode the .ico and take the largest frame.
$bytes = [System.IO.File]::ReadAllBytes($IconPath)
$ms = New-Object System.IO.MemoryStream(,$bytes)
$decoder = [System.Windows.Media.Imaging.BitmapDecoder]::Create(
  $ms,
  [System.Windows.Media.Imaging.BitmapCreateOptions]::None,
  [System.Windows.Media.Imaging.BitmapCacheOption]::OnLoad)
$src = $decoder.Frames | Sort-Object PixelWidth -Descending | Select-Object -First 1
Write-Host "Source frame: $($src.PixelWidth)x$($src.PixelHeight)"

function Save-Png([System.Windows.Media.Imaging.RenderTargetBitmap]$rtb, [string]$name) {
  $enc = New-Object System.Windows.Media.Imaging.PngBitmapEncoder
  $enc.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($rtb))
  $path = Join-Path $OutDir $name
  $fs = [System.IO.File]::Create($path)
  try { $enc.Save($fs) } finally { $fs.Close() }
}

function Render([int]$w, [int]$h, [scriptblock]$draw, [string]$name) {
  $rtb = New-Object System.Windows.Media.Imaging.RenderTargetBitmap($w, $h, 96, 96, [System.Windows.Media.PixelFormats]::Pbgra32)
  $dv = New-Object System.Windows.Media.DrawingVisual
  $ctx = $dv.RenderOpen()
  & $draw $ctx $w $h
  $ctx.Close()
  $rtb.Render($dv)
  Save-Png $rtb $name
  Write-Host "  $name ($w x $h)"
}

$drawSquare = {
  param($ctx, $w, $h)
  $ctx.DrawImage($src, (New-Object System.Windows.Rect(0, 0, $w, $h)))
}
$drawWide = {
  param($ctx, $w, $h)
  $color = [System.Windows.Media.ColorConverter]::ConvertFromString($BackColor)
  $ctx.DrawRectangle((New-Object System.Windows.Media.SolidColorBrush($color)), $null, (New-Object System.Windows.Rect(0, 0, $w, $h)))
  $s = [Math]::Min($w, $h)
  $ctx.DrawImage($src, (New-Object System.Windows.Rect((($w - $s) / 2), (($h - $s) / 2), $s, $s)))
}

Write-Host "Generating MSIX assets into $OutDir :"
Render 44  44  $drawSquare "Square44x44Logo.png"
Render 71  71  $drawSquare "Square71x71Logo.png"
Render 150 150 $drawSquare "Square150x150Logo.png"
Render 310 310 $drawSquare "Square310x310Logo.png"
Render 50  50  $drawSquare "StoreLogo.png"
Render 310 150 $drawWide   "Wide310x150Logo.png"
$ms.Dispose()
Write-Host "Done."
