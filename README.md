# Screen Read-Aloud

Free and open-source Windows helper for people who find reading hard: mark or select text on screen, then hear it read aloud.

**License:** [MIT](LICENSE)

## Download (Windows)

1. Go to **[Releases](https://github.com/Z3n1thh/Speech/releases)**
2. Download **`ScreenReadAloud-Windows.zip`**
3. Unzip → run **`ScreenReadAloud.exe`**

Windows SmartScreen may warn on unsigned apps — **More info** → **Run anyway**.

## Features

- Screen **region OCR** (`Ctrl+Shift+R`)
- **Selected text** reading (`Ctrl+Shift+S`)
- Offline Windows voices only (no paid / gray-area cloud TTS)
- Word highlighting while speaking
- Pause / resume, rate & volume, history
- Simple mode (big buttons)
- Start with Windows
- Swedish / English OCR language

### Hotkeys

| Action | Default |
|---|---|
| Select region (OCR) | `Ctrl+Shift+R` |
| Read highlighted selection | `Ctrl+Shift+S` |
| Stop | `Ctrl+Shift+X` |
| Faster | `Ctrl+Shift+Up` |
| Slower | `Ctrl+Shift+Down` |

## Free & open-source stack

| Piece | What | License / cost |
|---|---|---|
| App code | This repo | MIT |
| UI | customtkinter | MIT |
| Hotkeys | keyboard | MIT |
| Screenshot | mss | MIT |
| Tray | pystray | MIT / LGPL |
| Images | Pillow | HPND |
| OCR | Windows.Media.Ocr via winocr | Free Windows feature |
| Speech | Windows SAPI via pyttsx3 | Free Windows feature + MPL-2.0 lib |

No paid APIs. Edge/cloud TTS was removed so everything stays free and clearly legitimate.

For Swedish OCR on Windows (Admin PowerShell):

```powershell
Add-WindowsCapability -Online -Name "Language.OCR~~~sv-SE~0.0.1.0"
```

## Run from source

```powershell
cd path\to\Speech
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Rebuild the zip:

```powershell
pip install pyinstaller
.\build_release.bat
```

## Privacy

- OCR and speech run on your PC
- No account, no telemetry, no cloud TTS
