# Install Screen Read-Aloud to your user profile (no admin required).
# Run from the unzipped release folder:
#   powershell -ExecutionPolicy Bypass -File .\Install-ScreenReadAloud.ps1

$ErrorActionPreference = "Stop"
$Source = $PSScriptRoot
$Exe = Join-Path $Source "ScreenReadAloud.exe"
if (-not (Test-Path $Exe)) {
    Write-Error "ScreenReadAloud.exe not found next to this script. Unzip the full ScreenReadAloud-Windows.zip first."
}

# Old folder builds needed _internal next to the exe. New builds are one-file,
# but still warn clearly if someone mixes an old broken copy.
$LegacyInternal = Join-Path $Source "_internal"
if (Test-Path $LegacyInternal) {
    $PyDlls = Get-ChildItem -Path $LegacyInternal -Filter "python*.dll" -ErrorAction SilentlyContinue
    if (-not $PyDlls) {
        Write-Error @"
Broken install folder: _internal exists but python*.dll is missing.
Delete this folder, download a fresh ScreenReadAloud-Windows.zip from GitHub Releases,
unzip again, then run this installer.
"@
    }
}

$Target = Join-Path $env:LOCALAPPDATA "Programs\ScreenReadAloud"
if (Test-Path $Target) {
    Remove-Item -Recurse -Force $Target
}
New-Item -ItemType Directory -Force -Path $Target | Out-Null

Write-Host "Installing to $Target ..."
# One-file release: copy exe (+ helpers). If a full folder build is present, copy all.
$Internal = Join-Path $Source "_internal"
if (Test-Path $Internal) {
    Copy-Item -Path (Join-Path $Source "*") -Destination $Target -Recurse -Force
} else {
    Copy-Item -Force $Exe (Join-Path $Target "ScreenReadAloud.exe")
    $StartHere = Join-Path $Source "START_HERE.txt"
    if (Test-Path $StartHere) {
        Copy-Item -Force $StartHere (Join-Path $Target "START_HERE.txt")
    }
}

$TargetExe = Join-Path $Target "ScreenReadAloud.exe"
if (-not (Test-Path $TargetExe)) {
    Write-Error "Install failed — ScreenReadAloud.exe missing in $Target"
}

$Wsh = New-Object -ComObject WScript.Shell

$Desktop = [Environment]::GetFolderPath("Desktop")
$DesktopLink = Join-Path $Desktop "Screen Read-Aloud.lnk"
$Shortcut = $Wsh.CreateShortcut($DesktopLink)
$Shortcut.TargetPath = $TargetExe
$Shortcut.WorkingDirectory = $Target
$Shortcut.Description = "Screen Read-Aloud"
$Shortcut.Save()

$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$StartLink = Join-Path $StartMenu "Screen Read-Aloud.lnk"
$Shortcut2 = $Wsh.CreateShortcut($StartLink)
$Shortcut2.TargetPath = $TargetExe
$Shortcut2.WorkingDirectory = $Target
$Shortcut2.Description = "Screen Read-Aloud"
$Shortcut2.Save()

Write-Host ""
Write-Host "Installed."
Write-Host "Desktop shortcut: $DesktopLink"
Write-Host "Start Menu shortcut: $StartLink"
Write-Host "Run: $TargetExe"
Write-Host ""
Write-Host "Important: use the shortcut (or the exe inside $Target)."
Write-Host "Do not copy only ScreenReadAloud.exe to the Desktop by itself."
