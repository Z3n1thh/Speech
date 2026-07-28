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
Copy-Item -Force (Join-Path $Root "Uninstall-ScreenReadAloud.ps1") (Join-Path $Stage "Uninstall-ScreenReadAloud.ps1")
Copy-Item -Force (Join-Path $Root "LICENSE") (Join-Path $Stage "LICENSE")
Copy-Item -Force (Join-Path $Root "THIRD_PARTY_NOTICES.md") (Join-Path $Stage "THIRD_PARTY_NOTICES.md")

$StartHere = @"
Screen Read-Aloud — how to install
=================================

1. Keep this whole folder together (do not move only the .exe somewhere else).
2. Double-click Install-ScreenReadAloud.ps1
   OR right-click it → Run with PowerShell
3. Use the Desktop / Start Menu shortcut that appears.

Or just double-click ScreenReadAloud.exe in THIS folder.

To uninstall later:
- Options → Uninstall app
  OR run Uninstall-ScreenReadAloud.ps1

Licenses in this folder:
- LICENSE (app code, MIT)
- THIRD_PARTY_NOTICES.md (bundled libraries + Edge/Windows notes)

If Windows SmartScreen appears: More info → Run anyway.
"@
Set-Content -Encoding UTF8 -Path (Join-Path $Stage "START_HERE.txt") -Value $StartHere

$Zip = Join-Path $Dist "ScreenReadAloud-Windows.zip"
if (Test-Path $Zip) {
    Remove-Item -Force $Zip
}
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $Zip -Force
Write-Host "Packed: $Zip"
