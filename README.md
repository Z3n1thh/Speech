# Screen Read-Aloud

Free Windows helper: mark a screen region, then hear the text read aloud **once**.

**License:** [MIT](LICENSE)

## Download (Windows)

1. Open **[Releases](https://github.com/Z3n1thh/Speech/releases)**
2. Download **`ScreenReadAloud-Windows.zip`**
3. Unzip the folder (keep all files together)
4. Open **`START_HERE.txt`**, then run **`Install-ScreenReadAloud.ps1`**
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\Install-ScreenReadAloud.ps1
   ```
5. Or just double-click **`ScreenReadAloud.exe`** inside the unzipped folder

Windows SmartScreen may warn on unsigned apps — **More info** → **Run anyway**.

### If you see `pythonXXX.dll` / `_internal` errors

Download the latest zip again, unzip, and run the installer. Use the Desktop shortcut — don’t copy only the `.exe`.

## How to use

1. Click **Select region** (or `Ctrl+Shift+R`)
2. Drag a box over the text
3. The app reads it **once** (extra clicks while speaking are ignored)
4. Press **Stop** (`Ctrl+Shift+X`) to cancel
5. Open **Options** for voice, volume, and dark/light mode

## Free stack

App code is MIT. Libraries are free/open-source. OCR/speech use free Windows features; Edge neural voices are optional and need internet (no paid API key).

## Run from source

```powershell
cd path\to\Speech
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Rebuild release zip:

```powershell
pip install pyinstaller
.\build_release.bat
```

## Privacy

- OCR and offline speech stay on your PC
- Edge voices send text to Microsoft’s free Edge TTS only when that engine is selected
- No account, no telemetry
