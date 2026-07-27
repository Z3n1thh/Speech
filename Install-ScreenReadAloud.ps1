# Install Screen Read-Aloud to your user profile (no admin required).
# Run from the unzipped release folder:
#   powershell -ExecutionPolicy Bypass -File .\Install-ScreenReadAloud.ps1

$ErrorActionPreference = "Stop"
$Source = $PSScriptRoot
$Exe = Join-Path $Source "ScreenReadAloud.exe"
if (-not (Test-Path $Exe)) {
    Write-Error "ScreenReadAloud.exe not found next to this script. Unzip the full release folder first."
}

$Target = Join-Path $env:LOCALAPPDATA "Programs\ScreenReadAloud"
New-Item -ItemType Directory -Force -Path $Target | Out-Null

Write-Host "Installing to $Target ..."
Copy-Item -Path (Join-Path $Source "*") -Destination $Target -Recurse -Force

$TargetExe = Join-Path $Target "ScreenReadAloud.exe"
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
