"""System tray icon for background access."""

from __future__ import annotations

import threading
from typing import Callable

import pystray
from PIL import Image, ImageDraw


def _make_icon_image() -> Image.Image:
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((4, 4, size - 4, size - 4), fill=(33, 110, 150, 255))
    # Simple speaker shape
    draw.polygon(
        [(18, 24), (30, 24), (42, 14), (42, 50), (30, 40), (18, 40)],
        fill=(245, 245, 245, 255),
    )
    draw.arc((44, 20, 56, 44), start=300, end=60, fill=(245, 245, 245, 255), width=3)
    return image


class TrayIcon:
    def __init__(
        self,
        *,
        on_show: Callable[[], None],
        on_select: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._on_show = on_show
        self._on_select = on_select
        self._on_quit = on_quit
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem("Show", lambda: self._on_show(), default=True),
            pystray.MenuItem("Select region", lambda: self._on_select()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: self._quit()),
        )
        self._icon = pystray.Icon(
            "ScreenReadAloud",
            _make_icon_image(),
            "Screen Read-Aloud",
            menu,
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def _quit(self) -> None:
        self.stop()
        self._on_quit()

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
