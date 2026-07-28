# Screen Read-Aloud

Lightweight Windows helper shaped like **Snipping Tool**: mark a screen region, then Start / Stop / Continue reading.

**License:** [MIT](LICENSE)

## Download (Windows)

1. Open **[Releases](https://github.com/Z3n1thh/Speech/releases)**
2. Download **`ScreenReadAloud-Windows.zip`**
3. Unzip → run **`Install-ScreenReadAloud.ps1`**

## How to use

1. **+ New** (`Ctrl+Shift+R`) — drag a rectangle over text
2. **Start** — read from the beginning
3. **Stop** (`Ctrl+Shift+X`) — pause and remember position
4. **Continue** — resume where you stopped
5. **Options** — voice, volume, pitch, dark/light, **Uninstall**

## Uninstall

- In the app: **Options → Uninstall app**
- Or run `Uninstall-ScreenReadAloud.ps1` from the zip / install folder

## Run from source

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
.\build_release.bat
```
