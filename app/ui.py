"""Compact Snipping Tool–style toolbar: mark a region, hear it read aloud."""

from __future__ import annotations

import threading
from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

from app.config import APP_VERSION, load_settings, save_settings
from app.hotkey import HotkeyManager
from app.memory import has_memory, load_memory, save_memory
from app.ocr import OCR_LANG_CHOICES, OcrError, recognize_image
from app.region import select_region
from app.textutil import sentence_at_or_after
from app.tts import TextToSpeech
from app.uninstall import launch_uninstall

THEME = {
    "dark": {
        "bg": "#1c1c1c",
        "surface": "#2b2b2b",
        "surface2": "#333333",
        "border": "#3d3d3d",
        "text": "#f3f3f3",
        "muted": "#a0a0a0",
        "accent": "#60cdff",
        "accent_hover": "#4bb8ea",
        "accent_text": "#001a26",
        "danger": "#e81123",
        "danger_hover": "#c50f1f",
        "ok": "#0f7b0f",
    },
    "light": {
        "bg": "#f3f3f3",
        "surface": "#ffffff",
        "surface2": "#f9f9f9",
        "border": "#e5e5e5",
        "text": "#1a1a1a",
        "muted": "#5c5c5c",
        "accent": "#0067c0",
        "accent_hover": "#005a9e",
        "accent_text": "#ffffff",
        "danger": "#c42b1c",
        "danger_hover": "#a12115",
        "ok": "#0f7b0f",
    },
}


def _colors(theme: str) -> dict[str, str]:
    return THEME["dark" if theme == "dark" else "light"]


class OptionsWindow(ctk.CTkToplevel):
    """Voice, volume, pitch, appearance, uninstall."""

    def __init__(self, master: "App") -> None:
        super().__init__(master)
        self.app = master
        self.title("Options")
        self.geometry("460x580")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.attributes("-topmost", True)

        self._voice_map: dict[str, str] = {}
        c = _colors(str(self.app.settings.get("theme", "dark")))
        self.configure(fg_color=c["bg"])

        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=22, pady=18)

        ctk.CTkLabel(
            pad, text="Options",
            font=ctk.CTkFont(family="Segoe UI Semibold", size=20),
            text_color=c["text"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            pad, text="Voice, sound, look, and uninstall",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=c["muted"],
        ).pack(anchor="w", pady=(2, 14))

        card = ctk.CTkFrame(
            pad, fg_color=c["surface"], corner_radius=12, border_width=1, border_color=c["border"]
        )
        card.pack(fill="both", expand=True)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=14)

        def row(label: str) -> ctk.CTkFrame:
            r = ctk.CTkFrame(inner, fg_color="transparent")
            r.pack(fill="x", pady=7)
            ctk.CTkLabel(r, text=label, width=100, anchor="w", text_color=c["text"]).pack(side="left")
            return r

        r = row("Mode")
        self.theme_var = ctk.StringVar(value=str(self.app.settings.get("theme", "dark")))
        ctk.CTkSegmentedButton(
            r, values=["dark", "light"], variable=self.theme_var, width=220,
            command=self._on_theme,
            selected_color=c["accent"], selected_hover_color=c["accent_hover"],
            unselected_color=c["surface2"], unselected_hover_color=c["border"],
            text_color=c["text"],
        ).pack(side="left", padx=(8, 0))

        r = row("Volume")
        self.volume_slider = ctk.CTkSlider(
            r, from_=0, to=1, number_of_steps=20, width=200,
            progress_color=c["accent"], button_color=c["accent"],
            command=self._on_volume,
        )
        self.volume_slider.set(float(self.app.settings.get("volume", 1.0)))
        self.volume_slider.pack(side="left", padx=(8, 8))
        self.volume_label = ctk.CTkLabel(r, text="100%", width=44, text_color=c["muted"])
        self.volume_label.pack(side="left")
        self._on_volume(float(self.app.settings.get("volume", 1.0)))

        r = row("Pitch")
        self.pitch_slider = ctk.CTkSlider(
            r, from_=80, to=260, number_of_steps=36, width=200,
            progress_color=c["accent"], button_color=c["accent"],
            command=self._on_pitch,
        )
        self.pitch_slider.set(float(self.app.settings.get("rate", 160)))
        self.pitch_slider.pack(side="left", padx=(8, 8))
        self.pitch_label = ctk.CTkLabel(r, text="160", width=44, text_color=c["muted"])
        self.pitch_label.pack(side="left")
        self._on_pitch(float(self.app.settings.get("rate", 160)))

        r = row("Voice lang")
        self.filter_var = ctk.StringVar(value=str(self.app.settings.get("voice_filter", "en")))
        ctk.CTkOptionMenu(
            r, values=["en", "sv", "de", "fr", "es", "all"],
            variable=self.filter_var, width=200,
            fg_color=c["surface2"], button_color=c["border"],
            command=lambda _v: self._reload_voices(),
        ).pack(side="left", padx=(8, 0))

        r = row("Voice")
        self.voice_var = ctk.StringVar(value="Loading...")
        self.voice_menu = ctk.CTkComboBox(
            r, values=["Loading..."], variable=self.voice_var, width=280,
            fg_color=c["surface2"], border_color=c["border"], button_color=c["border"],
        )
        self.voice_menu.pack(side="left", padx=(8, 0))

        r = row("OCR lang")
        self.ocr_var = ctk.StringVar(value=str(self.app.settings.get("ocr_lang", "en")))
        ctk.CTkOptionMenu(
            r, values=OCR_LANG_CHOICES, variable=self.ocr_var, width=200,
            fg_color=c["surface2"], button_color=c["border"],
        ).pack(side="left", padx=(8, 0))

        r = row("Engine")
        self.engine_var = ctk.StringVar(value=str(self.app.settings.get("engine", "edge")))
        ctk.CTkSegmentedButton(
            r, values=["edge", "offline"], variable=self.engine_var, width=220,
            command=lambda _v: self._reload_voices(),
            selected_color=c["accent"], selected_hover_color=c["accent_hover"],
            unselected_color=c["surface2"], unselected_hover_color=c["border"],
            text_color=c["text"],
        ).pack(side="left", padx=(8, 0))

        danger = ctk.CTkFrame(inner, fg_color="transparent")
        danger.pack(fill="x", pady=(16, 4))
        ctk.CTkButton(
            danger,
            text="Uninstall app",
            height=34,
            corner_radius=8,
            fg_color=c["danger"],
            hover_color=c["danger_hover"],
            text_color="#ffffff",
            command=self._uninstall,
        ).pack(anchor="w")
        ctk.CTkLabel(
            danger,
            text="Removes shortcuts, the installed app, and saved settings.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=c["muted"],
        ).pack(anchor="w", pady=(4, 0))

        btns = ctk.CTkFrame(pad, fg_color="transparent")
        btns.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(
            btns, text="Save", width=110, height=36, corner_radius=8,
            fg_color=c["accent"], hover_color=c["accent_hover"],
            text_color=c["accent_text"], command=self._save,
        ).pack(side="right")
        ctk.CTkButton(
            btns, text="Cancel", width=90, height=36, corner_radius=8,
            fg_color=c["surface2"], hover_color=c["border"], text_color=c["text"],
            command=self.destroy,
        ).pack(side="right", padx=(0, 8))

        self.after(40, self._reload_voices)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _on_theme(self, value: str) -> None:
        self.app.settings["theme"] = value
        self.app._apply_theme(value)
        self.app._paint()
        self.destroy()
        self.app.after(20, self.app.open_options)

    def _on_volume(self, value: float) -> None:
        self.volume_label.configure(text=f"{int(float(value) * 100)}%")

    def _on_pitch(self, value: float) -> None:
        self.pitch_label.configure(text=str(int(value)))

    def _reload_voices(self) -> None:
        self.voice_menu.configure(values=["Loading..."])
        self.voice_var.set("Loading...")
        engine = self.engine_var.get()
        filt = self.filter_var.get() or "all"

        def _load() -> None:
            voice_map: dict[str, str] = {}
            labels: list[str] = []
            selected = ""
            try:
                if engine == "edge":
                    for voice in self.app.tts.list_edge_voices_sync(filt):
                        label = voice["name"]
                        voice_map[label] = voice["id"]
                        labels.append(label)
                    wanted = self.app.settings.get("edge_voice", "")
                    selected = next(
                        (lbl for lbl, vid in voice_map.items() if vid == wanted),
                        labels[0] if labels else "",
                    )
                else:
                    labels = ["(default)"]
                    voice_map["(default)"] = ""
                    for voice in self.app.tts.list_offline_voices():
                        label = voice["name"]
                        voice_map[label] = voice["id"]
                        labels.append(label)
                    wanted = self.app.settings.get("offline_voice", "")
                    selected = next(
                        (lbl for lbl, vid in voice_map.items() if vid == wanted),
                        "(default)",
                    )
            except Exception as exc:  # noqa: BLE001
                labels = ["(default)"]
                voice_map = {"(default)": ""}
                selected = "(default)"
                self.app._queue_status(f"Could not load voices: {exc}")

            def _apply() -> None:
                if not self.winfo_exists():
                    return
                self._voice_map = voice_map
                if not labels:
                    labels.append("(default)")
                self.voice_menu.configure(values=labels)
                self.voice_var.set(selected if selected in labels else labels[0])

            self.app._queue_call(_apply)

        threading.Thread(target=_load, daemon=True).start()

    def _save(self) -> None:
        label = self.voice_var.get()
        voice_id = self._voice_map.get(label, "")
        self.app.settings["theme"] = self.theme_var.get()
        self.app.settings["volume"] = float(self.volume_slider.get())
        self.app.settings["rate"] = int(self.pitch_slider.get())
        self.app.settings["voice_filter"] = self.filter_var.get()
        self.app.settings["ocr_lang"] = self.ocr_var.get()
        self.app.settings["engine"] = self.engine_var.get()
        if self.engine_var.get() == "edge":
            if voice_id:
                self.app.settings["edge_voice"] = voice_id
        else:
            self.app.settings["offline_voice"] = voice_id
        save_settings(self.app.settings)
        self.app._apply_theme(self.app.settings["theme"])
        self.app._paint()
        self.app._set_status("Options saved")
        self.destroy()

    def _uninstall(self) -> None:
        ok = messagebox.askyesno(
            "Uninstall Screen Read-Aloud",
            "Remove the app, Desktop/Start shortcuts, and saved settings?\n\n"
            "The app will close after uninstall starts.",
            parent=self,
        )
        if not ok:
            return
        try:
            launch_uninstall(keep_data=False)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Uninstall failed", str(exc), parent=self)
            return
        self.destroy()
        self.app._set_status("Uninstalling…")
        self.app.after(300, self.app.quit_app)


class App(ctk.CTk):
    """Floating toolbar inspired by Windows Snipping Tool."""

    def __init__(self) -> None:
        super().__init__()
        self.title(f"Screen Read-Aloud {APP_VERSION}")
        self.geometry("700x156")
        self.minsize(640, 148)
        self.resizable(False, False)
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass

        self.settings = load_settings()
        self._apply_theme(self.settings.get("theme", "dark"))

        self.tts = TextToSpeech(on_status=self._queue_status)
        self.hotkeys = HotkeyManager()
        self._busy = False
        self._speaking = False
        self._on_quit_callbacks: list[Callable[[], None]] = []
        self._ui_queue: list[Callable[[], None]] = []
        self._options_window: OptionsWindow | None = None
        self._last_text = ""
        self._read_offset = 0

        mem = load_memory()
        if mem and mem.get("text"):
            self._last_text = str(mem["text"])
            self._read_offset = int(mem.get("offset", 0) or 0)

        self._build_ui()
        self._paint()
        self._register_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.after(80, self._drain_ui_queue)

    def _apply_theme(self, theme: str) -> None:
        mode = "dark" if theme == "dark" else "light"
        ctk.set_appearance_mode(mode)
        ctk.set_default_color_theme("blue")

    def _paint(self) -> None:
        c = _colors(str(self.settings.get("theme", "dark")))
        self.configure(fg_color=c["bg"])
        self.shell.configure(fg_color=c["surface"], border_color=c["border"])
        self.title_label.configure(text_color=c["text"])
        self.subtitle_label.configure(text_color=c["muted"])
        self.mode_chip.configure(
            fg_color=c["surface2"], text_color=c["text"], border_color=c["border"]
        )
        self.new_btn.configure(
            fg_color=c["accent"], hover_color=c["accent_hover"], text_color=c["accent_text"]
        )
        self.start_btn.configure(
            fg_color=c["ok"], hover_color="#0c650c", text_color="#ffffff"
        )
        self.continue_btn.configure(
            fg_color=c["surface2"], hover_color=c["border"], text_color=c["text"]
        )
        self.stop_btn.configure(
            fg_color=c["danger"] if self._speaking else c["surface2"],
            hover_color=c["danger_hover"] if self._speaking else c["border"],
            text_color="#ffffff" if self._speaking else c["text"],
        )
        self.options_btn.configure(
            fg_color=c["surface2"], hover_color=c["border"], text_color=c["text"]
        )
        self.status_label.configure(text_color=c["muted"])

    # ---- tray API ----
    def add_quit_callback(self, callback: Callable[[], None]) -> None:
        self._on_quit_callbacks.append(callback)

    def show_window(self) -> None:
        self.after(0, self._show_window)

    def request_select_region(self) -> None:
        self.after(0, self.start_region_capture)

    def request_quit(self) -> None:
        self.after(0, self.quit_app)

    def hide_to_tray(self) -> None:
        self._persist_position()
        self.withdraw()
        self._set_status("In tray — Ctrl+Shift+R to read a region")

    def quit_app(self) -> None:
        self._persist_position()
        try:
            self.hotkeys.unregister()
        except Exception:
            pass
        self.tts.stop(silent=True)
        for callback in self._on_quit_callbacks:
            try:
                callback()
            except Exception:
                pass
        self.destroy()

    # ---- UI ----
    def _build_ui(self) -> None:
        self.shell = ctk.CTkFrame(self, corner_radius=14, border_width=1)
        self.shell.pack(fill="both", expand=True, padx=10, pady=10)

        top = ctk.CTkFrame(self.shell, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(12, 4))
        titles = ctk.CTkFrame(top, fg_color="transparent")
        titles.pack(side="left", fill="x", expand=True)
        self.title_label = ctk.CTkLabel(
            titles, text="Screen Read-Aloud",
            font=ctk.CTkFont(family="Segoe UI Semibold", size=15), anchor="w",
        )
        self.title_label.pack(anchor="w")
        self.subtitle_label = ctk.CTkLabel(
            titles, text="Mark text · Start / Stop / Continue",
            font=ctk.CTkFont(family="Segoe UI", size=11), anchor="w",
        )
        self.subtitle_label.pack(anchor="w")

        bar = ctk.CTkFrame(self.shell, fg_color="transparent")
        bar.pack(fill="x", padx=14, pady=(8, 6))

        self.new_btn = ctk.CTkButton(
            bar, text="+  New", height=40, width=92, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI Semibold", size=14),
            command=self.start_region_capture,
        )
        self.new_btn.pack(side="left")

        self.mode_chip = ctk.CTkLabel(
            bar, text="  Rectangle  ", height=40, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self.mode_chip.pack(side="left", padx=(8, 0))

        self.start_btn = ctk.CTkButton(
            bar, text="Start", height=40, width=70, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            command=self.start_reading,
        )
        self.start_btn.pack(side="left", padx=(8, 0))

        self.stop_btn = ctk.CTkButton(
            bar, text="Stop", height=40, width=70, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            command=self.stop_reading,
        )
        self.stop_btn.pack(side="left", padx=(8, 0))

        self.continue_btn = ctk.CTkButton(
            bar, text="Continue", height=40, width=88, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            command=self.continue_reading,
        )
        self.continue_btn.pack(side="left", padx=(8, 0))

        self.options_btn = ctk.CTkButton(
            bar, text="⚙  Options", height=40, width=108, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            command=self.open_options,
        )
        self.options_btn.pack(side="right")

        self.status_label = ctk.CTkLabel(
            self.shell, text="Ready — press New or Ctrl+Shift+R",
            font=ctk.CTkFont(family="Segoe UI", size=11), anchor="w",
        )
        self.status_label.pack(fill="x", padx=16, pady=(2, 12))

    # ---- queue ----
    def _queue_status(self, message: str) -> None:
        self._ui_queue.append(lambda m=message: self._set_status(m))

    def _queue_call(self, fn: Callable[[], None]) -> None:
        self._ui_queue.append(fn)

    def _drain_ui_queue(self) -> None:
        while self._ui_queue:
            fn = self._ui_queue.pop(0)
            try:
                fn()
            except Exception:
                pass
        self.after(80, self._drain_ui_queue)

    def _set_status(self, message: str) -> None:
        text = (message or "").replace("\n", " ")
        if len(text) > 78:
            text = text[:75] + "..."
        self.status_label.configure(text=text)

    def _show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def open_options(self) -> None:
        if self._options_window is not None and self._options_window.winfo_exists():
            self._options_window.focus_force()
            return
        self._options_window = OptionsWindow(self)

    def _register_hotkeys(self) -> None:
        mapping = {
            self.settings.get("hotkey_region", "ctrl+shift+r"): self.request_select_region,
            self.settings.get("hotkey_stop", "ctrl+shift+x"): lambda: self.after(
                0, self.stop_reading
            ),
        }
        try:
            self.hotkeys.register_many(mapping)
            self._set_status("Ready — New to mark text, then Start / Continue")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Hotkey failed — use New ({exc})")

    def _persist_position(self) -> None:
        if not self._last_text.strip():
            return
        try:
            save_memory(self._last_text, self._read_offset, source="region")
        except Exception:
            pass

    def _on_progress(self, offset: int) -> None:
        self._read_offset = max(0, int(offset))
        # Throttle disk writes
        last = getattr(self, "_last_saved_offset", -9999)
        if abs(self._read_offset - last) < 40:
            return
        self._last_saved_offset = self._read_offset
        self._persist_position()

    # ---- capture / speak ----
    def start_region_capture(self) -> None:
        if self._busy:
            return
        if self._speaking or self.tts.is_busy():
            self._set_status("Already reading — press Stop")
            return
        self._busy = True
        self._set_status("Drag to select text… Esc cancels")
        self.update_idletasks()
        self.after(120, self._run_capture_flow)

    def _run_capture_flow(self) -> None:
        was_visible = self.state() == "normal"
        try:
            if was_visible:
                self.withdraw()
                self.update()
            image = select_region(parent=self)
        except Exception as exc:  # noqa: BLE001
            self._busy = False
            if was_visible:
                self._show_window()
            self._set_status(f"Select failed: {exc}")
            return
        if was_visible:
            self._show_window()
        if image is None:
            self._busy = False
            self._set_status("Cancelled")
            return
        self._set_status("Reading text…")
        lang = str(self.settings.get("ocr_lang") or "en")

        def _ocr() -> None:
            try:
                text = recognize_image(image, lang=lang)
            except OcrError as exc:
                self._queue_call(lambda: self._on_text_ready(None, str(exc)))
                return
            except Exception as exc:  # noqa: BLE001
                self._queue_call(lambda: self._on_text_ready(None, f"OCR error: {exc}"))
                return
            self._queue_call(lambda: self._on_text_ready(text, None))

        threading.Thread(target=_ocr, daemon=True).start()

    def _on_text_ready(self, text: str | None, error: str | None) -> None:
        self._busy = False
        if error:
            self._set_status(error)
            return
        assert text is not None
        self._last_text = text
        self._read_offset = 0
        self._persist_position()
        preview = text.replace("\n", " ").strip()
        if len(preview) > 42:
            preview = preview[:39] + "..."
        self._set_status(f"Ready: {preview} — press Start" if preview else "Text ready — press Start")

    def start_reading(self) -> None:
        """Read current text from the beginning."""
        if not self._last_text.strip():
            self._set_status("No text yet — press New to mark a region")
            return
        self._read_offset = 0
        self._persist_position()
        self._speak_from(0)

    def continue_reading(self) -> None:
        """Resume from last saved position."""
        mem = load_memory()
        if mem and mem.get("text"):
            self._last_text = str(mem["text"])
            self._read_offset = int(mem.get("offset", 0) or 0)
        if not self._last_text.strip():
            self._set_status("Nothing to continue — mark text with New first")
            return
        hit = sentence_at_or_after(self._last_text, self._read_offset)
        if not hit:
            self._set_status("Already at the end — press Start to replay")
            return
        start, _, _ = hit
        self._set_status(f"Continuing from character {start}")
        self._speak_from(start)

    def _speak_from(self, offset: int) -> None:
        if self._speaking or self.tts.is_busy():
            self._set_status("Already reading — press Stop")
            return
        text = self._last_text or ""
        if not text.strip():
            self._set_status("No text to read")
            return

        engine = str(self.settings.get("engine", "edge"))
        voice_id = (
            str(self.settings.get("edge_voice", "en-US-JennyNeural"))
            if engine == "edge"
            else str(self.settings.get("offline_voice", ""))
        )
        self._speaking = True
        self._read_offset = offset
        self.new_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.continue_btn.configure(state="disabled")
        self._paint()

        def _done() -> None:
            self._queue_call(self._on_speak_done)

        started = self.tts.speak(
            text,
            engine=engine,
            rate=int(self.settings.get("rate", 160)),
            volume=float(self.settings.get("volume", 1.0)),
            voice_id=voice_id,
            highlight=False,
            start_offset=offset,
            on_progress=lambda off: self._queue_call(lambda o=off: self._on_progress(o)),
            on_done=_done,
        )
        if not started:
            self._speaking = False
            self.new_btn.configure(state="normal")
            self.start_btn.configure(state="normal")
            self.continue_btn.configure(state="normal")
            self._paint()

    def _on_speak_done(self) -> None:
        self._speaking = False
        self.new_btn.configure(state="normal")
        self.start_btn.configure(state="normal")
        self.continue_btn.configure(state="normal")
        # Finished all the way — mark end
        if self._last_text:
            self._read_offset = len(self._last_text)
            self._persist_position()
        self._paint()
        self._set_status("Done — Start to replay, Continue if stopped early, or New")

    def stop_reading(self) -> None:
        self.tts.stop()
        self._speaking = False
        self.new_btn.configure(state="normal")
        self.start_btn.configure(state="normal")
        self.continue_btn.configure(state="normal")
        self._persist_position()
        self._paint()
        if has_memory() or self._last_text:
            self._set_status(f"Stopped at {self._read_offset} — press Continue to resume")
        else:
            self._set_status("Stopped")
