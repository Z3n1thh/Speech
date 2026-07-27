# Screen Read-Aloud

A free Windows helper for people who find reading hard: press a shortcut, draw a box around text on your screen, and hear it read aloud.

## Download (Windows)

1. Go to **[Releases](https://github.com/Z3n1thh/Speech/releases)**
2. Download **`ScreenReadAloud-Windows.zip`**
3. Unzip the folder
4. Run **`ScreenReadAloud.exe`**

Windows may show a SmartScreen warning for unsigned apps — choose **More info** → **Run anyway**.

No Python install needed for the release build.

## Features

- **Global hotkey** (default `Ctrl+Shift+R`) to capture a screen region
- **Windows built-in OCR** (`winocr`) — no paid API
- **Offline speech** via Windows voices (`pyttsx3`)
- **Optional higher-quality voices** via free Edge neural TTS (`edge-tts`, played with Windows Media Player)
- Editable text preview, rate/volume controls, system tray

## Requirements

- Windows 10 or 11
- A Windows OCR language pack (English is usually already present)

If OCR fails, install the language pack in **Admin PowerShell**:

```powershell
Add-WindowsCapability -Online -Name "Language.OCR~~~en-US~0.0.1.0"
```

## How to use

1. Start the app (window + tray icon).
2. Press **`Ctrl+Shift+R`** (or click **Select region**).
3. Drag a rectangle over the words you want read.
4. Review the recognized text (edit if needed).
5. It speaks automatically if **Auto-speak** is on; otherwise click **Read**.

### Tips

- Use **Offline** engine when you have no internet (default).
- Switch to **Edge** for clearer neural voices (needs internet).
- Change the hotkey in the window and click **Apply hotkey**.
- Closing the window hides to the tray; use the tray menu to quit.

## Run from source (developers)

```powershell
cd path\to\Speech
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

To rebuild the downloadable zip:

```powershell
pip install pyinstaller
.\build_release.bat
```

## Privacy

- OCR runs on your PC (Windows OCR).
- Offline speech stays on your PC.
- Edge TTS sends text to Microsoft’s free Edge online voices only when that engine is selected.

## License

Free to use for personal accessibility needs.
