# Screen Read-Aloud

Lightweight Windows helper shaped like **Snipping Tool**: mark a screen region, hear the text once.

**License:** [MIT](LICENSE)

## Download (Windows)

1. Open **[Releases](https://github.com/Z3n1thh/Speech/releases)**
2. Download **`ScreenReadAloud-Windows.zip`**
3. Unzip → run **`Install-ScreenReadAloud.ps1`** (or the `.exe`)

## How to use

1. Press **+ New** (or `Ctrl+Shift+R`)
2. Drag a rectangle over text
3. It reads aloud once
4. **Stop** / `Ctrl+Shift+X` to cancel
5. **Options** — voice, volume, pitch, dark/light mode

## Free stack

MIT app code. Free/open-source libraries. OCR + offline speech stay on your PC; Edge neural voices need internet (no paid API key).

## Run from source

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

```powershell
.\build_release.bat
```
