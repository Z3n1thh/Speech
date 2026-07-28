# Third-party notices

Screen Read-Aloud (this repository) is licensed under the **MIT License**.
See [LICENSE](LICENSE).

This file lists major third-party components used by the app or included in
Windows release builds. License texts are available from each project’s
repository / PyPI page. This is an attribution notice, not legal advice.

## Python packages

| Package | Typical use in this app | License (as commonly published) |
|---|---|---|
| [customtkinter](https://github.com/TomSchimansky/CustomTkinter) | UI | CC0-1.0 |
| [pystray](https://github.com/moses-palmer/pystray) | System tray | LGPL-3.0 |
| [Pillow](https://github.com/python-pillow/Pillow) | Images / capture | HPND (Pillow) |
| [keyboard](https://github.com/boppreh/keyboard) | Global hotkeys | MIT |
| [mss](https://github.com/BoboTiG/python-mss) | Screen capture | MIT |
| [winocr](https://pypi.org/project/winocr/) | Windows OCR bridge | See package metadata |
| [pyttsx3](https://github.com/nateshmbhat/pyttsx3) | Offline TTS | MPL-2.0 |
| [edge-tts](https://github.com/rany2/edge-tts) | Neural voices client | See package metadata (commonly LGPL-3.0) |
| [pywin32](https://github.com/mhammond/pywin32) | Windows COM / playback | PSF-style |

Python itself is available under the [PSF License](https://docs.python.org/3/license.html).
Release builds may also include PyInstaller bootloader components
([PyInstaller license](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt)).

### Removed on purpose

**PyMuPDF (`pymupdf`)** and **pypdf** were removed from this project and from
release builds. PyMuPDF is dual-licensed **AGPL-3.0 / commercial**; keeping it
in a redistributed binary without AGPL compliance (or a commercial license)
creates unnecessary legal risk. This app no longer includes PDF reading.

## Platform / online services (not “your” APIs)

These are not paid API keys owned by this project:

- **Windows OCR** and **Windows SAPI** voices — built into Windows; subject to
  Microsoft Windows terms.
- **Microsoft Edge online neural voices** (via `edge-tts`) — optional; requires
  internet and is subject to Microsoft’s terms for Edge / related services.
  No Microsoft API key is shipped with this app.

## Source availability

Application source for Screen Read-Aloud:
https://github.com/Z3n1thh/Speech

Third-party package sources are available from the project links above and via
PyPI (`pip download <package>`).
