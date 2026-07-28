"""Fullscreen overlay to drag-select a screen region and capture it."""

from __future__ import annotations

import tkinter as tk

import mss
from PIL import Image


class RegionSelector:
    """Modal fullscreen dim overlay; returns a PIL Image of the selected region."""

    def __init__(self, parent: tk.Misc | None = None) -> None:
        self._parent = parent

    def select(self) -> Image.Image | None:
        result: dict[str, Image.Image | None] = {"image": None}

        owns_root = self._parent is None
        root = tk.Tk() if owns_root else self._parent
        if owns_root:
            root.withdraw()
            root.update_idletasks()

        # Virtual desktop covering all monitors
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            left, top = monitor["left"], monitor["top"]
            width, height = monitor["width"], monitor["height"]

        overlay = tk.Toplevel(root)
        overlay.geometry(f"{width}x{height}+{left}+{top}")
        overlay.overrideredirect(True)
        overlay.attributes("-topmost", True)
        try:
            overlay.attributes("-alpha", 0.35)
        except tk.TclError:
            pass
        overlay.configure(bg="#000000", cursor="crosshair")

        canvas = tk.Canvas(
            overlay,
            width=width,
            height=height,
            highlightthickness=0,
            bg="#000000",
        )
        canvas.pack(fill="both", expand=True)

        # Soft dim like Snipping Tool
        canvas.create_rectangle(0, 0, width, height, fill="#000000", outline="")

        hint = canvas.create_text(
            width // 2,
            56,
            text="Drag to select text to read  ·  Esc to cancel",
            fill="#ffffff",
            font=("Segoe UI Semibold", 15),
        )

        state = {"x0": 0, "y0": 0, "rect": None, "fill": None}

        def on_press(event: tk.Event) -> None:
            state["x0"], state["y0"] = event.x, event.y
            if state["rect"] is not None:
                canvas.delete(state["rect"])
            if state["fill"] is not None:
                canvas.delete(state["fill"])
            state["fill"] = canvas.create_rectangle(
                event.x, event.y, event.x, event.y,
                outline="", fill="#ffffff", stipple="gray25",
            )
            state["rect"] = canvas.create_rectangle(
                event.x, event.y, event.x, event.y,
                outline="#60cdff", width=2,
            )
            canvas.itemconfigure(hint, state="hidden")

        def on_drag(event: tk.Event) -> None:
            if state["rect"] is None:
                return
            canvas.coords(state["rect"], state["x0"], state["y0"], event.x, event.y)
            if state["fill"] is not None:
                canvas.coords(state["fill"], state["x0"], state["y0"], event.x, event.y)

        def finish(image: Image.Image | None) -> None:
            result["image"] = image
            try:
                overlay.grab_release()
            except tk.TclError:
                pass
            overlay.destroy()
            if owns_root:
                root.destroy()

        def on_release(event: tk.Event) -> None:
            x1, y1 = state["x0"], state["y0"]
            x2, y2 = event.x, event.y
            left_r = min(x1, x2)
            top_r = min(y1, y2)
            right_r = max(x1, x2)
            bottom_r = max(y1, y2)
            if right_r - left_r < 8 or bottom_r - top_r < 8:
                finish(None)
                return

            # Overlay coords are relative to virtual desktop origin
            abs_left = left + left_r
            abs_top = top + top_r
            abs_width = right_r - left_r
            abs_height = bottom_r - top_r

            overlay.withdraw()
            overlay.update()
            with mss.mss() as sct:
                shot = sct.grab(
                    {
                        "left": abs_left,
                        "top": abs_top,
                        "width": abs_width,
                        "height": abs_height,
                    }
                )
                image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            finish(image)

        def on_escape(_event: tk.Event | None = None) -> None:
            finish(None)

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        overlay.bind("<Escape>", on_escape)
        canvas.bind("<Escape>", on_escape)

        overlay.focus_force()
        overlay.grab_set()
        overlay.wait_window()
        if owns_root:
            try:
                root.destroy()
            except tk.TclError:
                pass

        return result["image"]


def select_region(parent: tk.Misc | None = None) -> Image.Image | None:
    return RegionSelector(parent).select()
