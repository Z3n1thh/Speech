@echo off
REM Build a standalone Windows folder for Screen Read-Aloud
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
  --name ScreenReadAloud ^
  --collect-all customtkinter ^
  --collect-all winocr ^
  --collect-all edge_tts ^
  --hidden-import=win32timezone ^
  --hidden-import=win32com.client ^
  --hidden-import=pythoncom ^
  --hidden-import=pystray._win32 ^
  --hidden-import=keyboard ^
  --hidden-import=mss ^
  --hidden-import=pyttsx3.drivers.sapi5 ^
  main.py

if errorlevel 1 exit /b 1

powershell -NoProfile -Command ^
  "Compress-Archive -Path 'dist\ScreenReadAloud\*' -DestinationPath 'dist\ScreenReadAloud-Windows.zip' -Force"

echo.
echo Built: dist\ScreenReadAloud\ScreenReadAloud.exe
echo Zip:   dist\ScreenReadAloud-Windows.zip
