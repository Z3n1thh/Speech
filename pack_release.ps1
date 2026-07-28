# Pack one-file exe + install helpers into a clear zip folder.
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Dist = Join-Path $Root "dist"
$Exe = Join-Path $Dist "ScreenReadAloud.exe"
if (-not (Test-Path $Exe)) {
    throw "Missing $Exe - run build_release.bat first."
}

$Stage = Join-Path $Dist "ScreenReadAloud-Windows"
if (Test-Path $Stage) {
    Remove-Item -Recurse -Force $Stage
}
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

Copy-Item -Force $Exe (Join-Path $Stage "ScreenReadAloud.exe")
Copy-Item -Force (Join-Path $Root "Install-ScreenReadAloud.ps1") (Join-Path $Stage "Install-ScreenReadAloud.ps1")

$StartHere = @"
Screen Read-Aloud — how to install
=================================

1. Keep this whole folder together (do not move only the .exe somewhere else).
2. Double-click Install-ScreenReadAloud.ps1
   OR right-click it → Run with PowerShell
3. Use the Desktop / Start Menu shortcut that appears.

Or just double-click ScreenReadAloud.exe in THIS folder.

If Windows SmartScreen appears: More info → Run anyway.

If you see an error about pythonXXX.dll or _internal:
- You probably moved only the .exe. Use this zip again and run the installer.
- Or download the latest release from:
  https://github.com/Z3n1thh/Speech/releases

Need help: reopen the latest ScreenReadAloud-Windows.zip and start here.
"@
Set-Content -Encoding UTF8 -Path (Join-Path $Stage "START_HERE.txt") -Value $StartHere

$Zip = Join-Path $Dist "ScreenReadAloud-Windows.zip"
if (Test-Path $Zip) {
    Remove-Item -Force $Zip
}
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $Zip -Force
Write-Host "Packed: $Zip"
