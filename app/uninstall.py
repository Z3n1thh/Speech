"""Uninstall helpers for the installed Windows app."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def install_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "ScreenReadAloud"


def data_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "ScreenReadAloud"


def shortcut_paths() -> list[Path]:
    desktop = Path.home() / "Desktop"
    # Prefer Windows API folder when available
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        ) as key:
            desktop = Path(winreg.QueryValueEx(key, "Desktop")[0])
    except Exception:
        pass
    start = (
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
    )
    return [
        desktop / "Screen Read-Aloud.lnk",
        start / "Screen Read-Aloud.lnk",
    ]


def find_uninstall_script() -> Path | None:
    here = Path(sys.executable).resolve().parent
    candidates = [
        here / "Uninstall-ScreenReadAloud.ps1",
        Path(__file__).resolve().parent.parent / "Uninstall-ScreenReadAloud.ps1",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def launch_uninstall(*, keep_data: bool = False) -> None:
    """Start uninstall in a detached process, then caller should quit the app."""
    script = find_uninstall_script()
    if script is not None:
        args = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-Quiet",
        ]
        if keep_data:
            args.append("-KeepData")
        subprocess.Popen(
            args,
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            close_fds=True,
        )
        return

    # Fallback: write a tiny delayed PowerShell cleaner
    install = install_dir()
    data = data_dir()
    links = shortcut_paths()
    keep = "$true" if keep_data else "$false"
    link_lines = "\n".join(f'Remove-Item -Force -ErrorAction SilentlyContinue "{p}"' for p in links)
    ps = f"""
Start-Sleep -Seconds 2
Get-Process -Name ScreenReadAloud -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
{link_lines}
if (Test-Path "{install}") {{ Remove-Item -Recurse -Force "{install}" }}
if (-not {keep} -and (Test-Path "{data}")) {{ Remove-Item -Recurse -Force "{data}" }}
"""
    tmp = Path(tempfile.gettempdir()) / "ScreenReadAloud-uninstall.ps1"
    tmp.write_text(ps, encoding="utf-8")
    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(tmp),
        ],
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        close_fds=True,
    )
