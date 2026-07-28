# Screen Read-Aloud

Free Windows helper for people who find reading hard: mark or select text (or open a PDF), then hear it read aloud.

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

That usually means only the `.exe` was moved (for example to the Desktop) without the rest of the app. Fix:

1. Delete the broken copy
2. Download the latest **`ScreenReadAloud-Windows.zip`** again
3. Unzip and run **`Install-ScreenReadAloud.ps1`**
4. Start the app from the new Desktop shortcut (not a lone `.exe` on the Desktop)

## Features

- Screen **region OCR** (`Ctrl+Shift+R`) with multi-try preprocessing + OCR tips
- **Selected text** (`Ctrl+Shift+S`)
- **PDF text** reading + **OCR for scanned/image PDFs** (page by page)
- **Continue** / memory — resume where you stopped
- **Profiles** (e.g. Swedish slow / English fast)
- **Reading mode** — nearly fullscreen, text + play
- **MP3 export** — save narration as an audiobook file
- **Auto language** (sv/en) switches OCR + voice
- **Sentence highlight** while speaking (including Edge neural voices)
- **Check updates** against GitHub Releases
- Neural **Edge voices** (default) + offline Windows voices
- Voice filter for **all languages**, favorites (★), and **Preview**
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
