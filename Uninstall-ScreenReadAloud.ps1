# Uninstall Screen Read-Aloud (no admin required).
# Run:
#   powershell -ExecutionPolicy Bypass -File .\Uninstall-ScreenReadAloud.ps1
#
# Optional:
#   -KeepData   keep settings / reading memory under LocalAppData\ScreenReadAloud

param(
    [switch]$KeepData,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\ScreenReadAloud"
$DataDir = Join-Path $env:LOCALAPPDATA "ScreenReadAloud"
$Desktop = [Environment]::GetFolderPath("Desktop")
$DesktopLink = Join-Path $Desktop "Screen Read-Aloud.lnk"
$StartLink = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Screen Read-Aloud.lnk"

# Stop a running instance if possible (ignore errors)
Get-Process -Name "ScreenReadAloud" -ErrorAction SilentlyContinue | ForEach-Object {
    try { $_.CloseMainWindow() | Out-Null } catch {}
}
Start-Sleep -Milliseconds 400
Get-Process -Name "ScreenReadAloud" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 300

foreach ($link in @($DesktopLink, $StartLink)) {
    if (Test-Path $link) {
        Remove-Item -Force $link
        if (-not $Quiet) { Write-Host "Removed shortcut: $link" }
    }
}

if (Test-Path $InstallDir) {
    Remove-Item -Recurse -Force $InstallDir
    if (-not $Quiet) { Write-Host "Removed: $InstallDir" }
}

if (-not $KeepData -and (Test-Path $DataDir)) {
    Remove-Item -Recurse -Force $DataDir
    if (-not $Quiet) { Write-Host "Removed app data: $DataDir" }
}

if (-not $Quiet) {
    Write-Host ""
    Write-Host "Screen Read-Aloud has been uninstalled."
}
