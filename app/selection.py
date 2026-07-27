"""Copy currently selected text via Ctrl+C (clipboard round-trip)."""

from __future__ import annotations

import time

import keyboard


def get_selected_text(settle_seconds: float = 0.18) -> str:
    """Simulate Ctrl+C and return the new clipboard text.

    Restores the previous clipboard contents afterwards.
    """
    import win32clipboard
    import win32con

    def _read_clipboard() -> str:
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                    return str(data or "")
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            return ""
        return ""

    def _write_clipboard(text: str) -> None:
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            pass

    previous = _read_clipboard()
    # Unique marker so we can detect whether Ctrl+C changed anything
    marker = f"__SRA_{time.time_ns()}__"
    _write_clipboard(marker)
    time.sleep(0.05)
    keyboard.send("ctrl+c")
    time.sleep(settle_seconds)
    current = _read_clipboard().strip()
    _write_clipboard(previous)

    if not current or current == marker:
        return ""
    return current
