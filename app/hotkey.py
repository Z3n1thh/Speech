"""Global hotkey registration using the keyboard library."""

from __future__ import annotations

from typing import Callable

import keyboard


class HotkeyManager:
    def __init__(self) -> None:
        self._hotkey: str | None = None
        self._handle = None

    @property
    def hotkey(self) -> str | None:
        return self._hotkey

    def register(self, hotkey: str, callback: Callable[[], None]) -> None:
        self.unregister()
        normalized = hotkey.strip().lower()
        if not normalized:
            raise ValueError("Hotkey cannot be empty")

        def _wrapped() -> None:
            callback()

        self._handle = keyboard.add_hotkey(normalized, _wrapped, suppress=False)
        self._hotkey = normalized

    def unregister(self) -> None:
        if self._handle is not None:
            try:
                keyboard.remove_hotkey(self._handle)
            except (KeyError, ValueError, AttributeError):
                try:
                    keyboard.unhook_all_hotkeys()
                except Exception:
                    pass
            self._handle = None
            self._hotkey = None
