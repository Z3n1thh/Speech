"""Global hotkey registration using the keyboard library."""

from __future__ import annotations

from typing import Callable

import keyboard


class HotkeyManager:
    def __init__(self) -> None:
        self._handles: list[object] = []
        self._bindings: dict[str, str] = {}

    @property
    def bindings(self) -> dict[str, str]:
        return dict(self._bindings)

    def register_many(self, mapping: dict[str, Callable[[], None]]) -> None:
        """Register multiple hotkeys. Values are callbacks keyed by hotkey string."""
        self.unregister()
        for hotkey, callback in mapping.items():
            normalized = (hotkey or "").strip().lower()
            if not normalized:
                continue

            def _wrapped(cb: Callable[[], None] = callback) -> None:
                cb()

            handle = keyboard.add_hotkey(normalized, _wrapped, suppress=False)
            self._handles.append(handle)
            self._bindings[normalized] = normalized

    def unregister(self) -> None:
        if self._handles:
            try:
                keyboard.unhook_all_hotkeys()
            except Exception:
                for handle in self._handles:
                    try:
                        keyboard.remove_hotkey(handle)
                    except Exception:
                        pass
        self._handles.clear()
        self._bindings.clear()
