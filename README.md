# Screen Read-Aloud

Lightweight Windows helper shaped like **Snipping Tool**: mark a screen region, then Start / Stop / Continue reading.

**License:** [MIT](LICENSE) · **Third-party:** [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

## Download (Windows)

1. Open **[Releases](https://github.com/Z3n1thh/Speech/releases)**
2. Download **`ScreenReadAloud-Windows.zip`**
3. Unzip → run **`Install-ScreenReadAloud.ps1`**

## How to use

1. **+ New** (`Ctrl+Shift+R`) — drag a rectangle over text
2. Marked text appears in the preview; **yellow** = current word/sentence, **green** = already read
3. **Start** — read from the beginning
4. **Stop** (`Ctrl+Shift+X`) — pause and remember position
5. **Continue** — resume where you stopped
6. **Options** — Swedish/English Edge voices, volume, pitch, dark/light, **Uninstall**

## Uninstall

- In the app: **Options → Uninstall app**
- Or run `Uninstall-ScreenReadAloud.ps1` from the zip / install folder

## Free stack / third-party

- App code is **MIT**
- Dependencies are free/open-source libraries (see **THIRD_PARTY_NOTICES.md**)
- OCR and offline speech use built-in **Windows** features on your PC
- Optional **Edge neural voices** need internet and follow Microsoft’s terms (no paid API key is included)
- **PyMuPDF was removed** from this project to avoid AGPL redistribution issues

## Run from source

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
.\build_release.bat
```
