@echo off
REM Build a standalone Windows one-file exe for Screen Read-Aloud
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pyinstaller.exe" (
  echo Create/activate venv and install requirements + pyinstaller first.
  exit /b 1
)

".venv\Scripts\pyinstaller.exe" ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --onefile ^
  --name ScreenReadAloud ^
  --collect-all customtkinter ^
  --collect-all edge_tts ^
  --hidden-import=win32timezone ^
  --hidden-import=win32com.client ^
  --hidden-import=win32clipboard ^
  --hidden-import=pythoncom ^
  --hidden-import=pystray._win32 ^
  --hidden-import=keyboard ^
  --hidden-import=mss ^
  --hidden-import=pyttsx3.drivers.sapi5 ^
  --collect-all pymupdf ^
  main.py

if errorlevel 1 exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -File ".\pack_release.ps1"
if errorlevel 1 exit /b 1

echo.
echo Built: dist\ScreenReadAloud.exe
echo Zip:   dist\ScreenReadAloud-Windows.zip
echo Tip:   unzip, then run Install-ScreenReadAloud.ps1 OR double-click the exe
