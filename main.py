"""Entrypoint for Screen Read-Aloud."""

from __future__ import annotations

import sys


def main() -> int:
    if sys.platform != "win32":
        print("Screen Read-Aloud currently supports Windows only.")
        return 1

    from app.tray import TrayIcon
    from app.ui import App

    app = App()
    tray = TrayIcon(
        on_show=app.show_window,
        on_select=app.request_select_region,
        on_selection=app.request_read_selection,
        on_quit=app.request_quit,
    )
    app.add_quit_callback(tray.stop)
    tray.start()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
