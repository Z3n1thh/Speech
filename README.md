# Screen Read-Aloud

Free Windows helper for people who find reading hard: mark or select text (or open a PDF), then hear it read aloud.

**License:** [MIT](LICENSE)

## Download (Windows)

1. Open **[Releases](https://github.com/Z3n1thh/Speech/releases)**
2. Download **`ScreenReadAloud-Windows.zip`**
3. Unzip the folder
4. Optional install (Start Menu + Desktop shortcuts):
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\Install-ScreenReadAloud.ps1
   ```
5. Or just run **`ScreenReadAloud.exe`**

Windows SmartScreen may warn on unsigned apps — **More info** → **Run anyway**.

## Features

- Screen **region OCR** (`Ctrl+Shift+R`)
- **Selected text** (`Ctrl+Shift+S`)
- **PDF text** reading
- Neural **Edge voices** (default) + offline Windows voices
- Voice filter for **all languages**, favorites (★), and **Preview**
- Word highlighting, next sentence, read from cursor
- Dark/light high-contrast theme
- Simple mode, quiet mode (tray after speak), autostart, history

### Hotkeys

| Action | Default |
|---|---|
| Select region (OCR) | `Ctrl+Shift+R` |
| Read highlighted selection | `Ctrl+Shift+S` |
| Stop | `Ctrl+Shift+X` |
| Faster | `Ctrl+Shift+Up` |
| Slower | `Ctrl+Shift+Down` |

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
