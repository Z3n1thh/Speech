"""Simple region-OCR read-aloud window + Options dialog."""

from __future__ import annotations

import threading
from typing import Any, Callable

import customtkinter as ctk

from app.config import APP_VERSION, load_settings, save_settings
from app.hotkey import HotkeyManager
from app.ocr import OCR_LANG_CHOICES, OcrError, recognize_image
from app.region import select_region
from app.tts import TextToSpeech


class OptionsWindow(ctk.CTkToplevel):
    """Settings: voice, volume, dark mode, OCR language."""

    def __init__(self, master: "App") -> None:
        super().__init__(master)
        self.app = master
        self.title("Options")
        self.geometry("520x420")
        self.minsize(480, 380)
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self._voice_map: dict[str, str] = {}

        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(
            pad, text="Options", font=ctk.CTkFont(family="Segoe UI Semibold", size=22)
        ).pack(anchor="w")

        # Theme / dark mode
        theme_row = ctk.CTkFrame(pad, fg_color="transparent")
        theme_row.pack(fill="x", pady=(16, 8))
        ctk.CTkLabel(theme_row, text="Appearance", width=110, anchor="w").pack(side="left")
        self.theme_var = ctk.StringVar(value=str(self.app.settings.get("theme", "dark")))
        ctk.CTkOptionMenu(
            theme_row,
            values=["dark", "light"],
            variable=self.theme_var,
            width=160,
            command=self._on_theme,
        ).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(theme_row, text="(dark mode / light mode)").pack(side="left", padx=(10, 0))

        # Volume
        vol_row = ctk.CTkFrame(pad, fg_color="transparent")
        vol_row.pack(fill="x", pady=8)
        ctk.CTkLabel(vol_row, text="Volume", width=110, anchor="w").pack(side="left")
        self.volume_slider = ctk.CTkSlider(
            vol_row, from_=0, to=1, number_of_steps=20, width=220, command=self._on_volume
        )
        self.volume_slider.set(float(self.app.settings.get("volume", 1.0)))
        self.volume_slider.pack(side="left", padx=(8, 8))
        self.volume_label = ctk.CTkLabel(vol_row, text="100%", width=48)
        self.volume_label.pack(side="left")
        self.volume_label.configure(
            text=f"{int(float(self.app.settings.get('volume', 1.0)) * 100)}%"
        )

        # Voice language filter
        filt_row = ctk.CTkFrame(pad, fg_color="transparent")
        filt_row.pack(fill="x", pady=8)
        ctk.CTkLabel(filt_row, text="Voice lang", width=110, anchor="w").pack(side="left")
        self.filter_var = ctk.StringVar(value=str(self.app.settings.get("voice_filter", "en")))
        self.filter_menu = ctk.CTkOptionMenu(
            filt_row,
            values=["en", "sv", "de", "fr", "es", "all"],
            variable=self.filter_var,
            width=160,
            command=lambda _v: self._reload_voices(),
        )
        self.filter_menu.pack(side="left", padx=(8, 0))

        # Voice picker
        voice_row = ctk.CTkFrame(pad, fg_color="transparent")
        voice_row.pack(fill="x", pady=8)
        ctk.CTkLabel(voice_row, text="Voice", width=110, anchor="w").pack(side="left")
        self.voice_var = ctk.StringVar(value="Loading...")
        self.voice_menu = ctk.CTkComboBox(
            voice_row, values=["Loading..."], variable=self.voice_var, width=340
        )
        self.voice_menu.pack(side="left", padx=(8, 0))

        # OCR language
        ocr_row = ctk.CTkFrame(pad, fg_color="transparent")
        ocr_row.pack(fill="x", pady=8)
        ctk.CTkLabel(ocr_row, text="OCR lang", width=110, anchor="w").pack(side="left")
        self.ocr_var = ctk.StringVar(value=str(self.app.settings.get("ocr_lang", "en")))
        ctk.CTkOptionMenu(
            ocr_row, values=OCR_LANG_CHOICES, variable=self.ocr_var, width=160
        ).pack(side="left", padx=(8, 0))

        # Engine
        eng_row = ctk.CTkFrame(pad, fg_color="transparent")
        eng_row.pack(fill="x", pady=8)
        ctk.CTkLabel(eng_row, text="Engine", width=110, anchor="w").pack(side="left")
        self.engine_var = ctk.StringVar(value=str(self.app.settings.get("engine", "edge")))
        ctk.CTkOptionMenu(
            eng_row,
            values=["edge", "offline"],
            variable=self.engine_var,
            width=160,
            command=lambda _v: self._reload_voices(),
        ).pack(side="left", padx=(8, 0))

        btns = ctk.CTkFrame(pad, fg_color="transparent")
        btns.pack(fill="x", pady=(24, 0))
        ctk.CTkButton(btns, text="Save", width=120, command=self._save).pack(side="right")
        ctk.CTkButton(
            btns, text="Cancel", width=100, fg_color="#555555", command=self.destroy
        ).pack(side="right", padx=(0, 8))

        self.after(50, self._reload_voices)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _on_theme(self, value: str) -> None:
        self.app._apply_theme(value)

    def _on_volume(self, value: float) -> None:
        self.volume_label.configure(text=f"{int(float(value) * 100)}%")

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
                self._voice_map = voice_map
                if not labels:
                    labels = ["(default)"]
                self.voice_menu.configure(values=labels)
                self.voice_var.set(selected if selected in labels else labels[0])

            self.app._queue_call(_apply)

        threading.Thread(target=_load, daemon=True).start()

    def _save(self) -> None:
        label = self.voice_var.get()
        voice_id = self._voice_map.get(label, "")
        self.app.settings["theme"] = self.theme_var.get()
        self.app.settings["volume"] = float(self.volume_slider.get())
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
        self.app._set_status("Options saved")
        self.destroy()


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Screen Read-Aloud v{APP_VERSION}")
        self.geometry("640x520")
        self.minsize(520, 420)

        self.settings = load_settings()
        self._apply_theme(self.settings.get("theme", "dark"))

        self.tts = TextToSpeech(on_status=self._queue_status, on_word=self._on_word)
        self.hotkeys = HotkeyManager()
        self._busy = False
        self._speaking = False
        self._on_quit_callbacks: list[Callable[[], None]] = []
        self._ui_queue: list[Callable[[], None]] = []
        self._options: OptionsWindow | None = None

        self._build_ui()
        self._register_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.after(80, self._drain_ui_queue)

    def _apply_theme(self, theme: str) -> None:
        mode = "dark" if theme == "dark" else "light"
        ctk.set_appearance_mode(mode)
        ctk.set_default_color_theme("blue")

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
        self.withdraw()
        self._set_status("Running in tray — Ctrl+Shift+R to select region")

    def quit_app(self) -> None:
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
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(18, 8))
        ctk.CTkLabel(
            header,
            text="Screen Read-Aloud",
            font=ctk.CTkFont(family="Segoe UI Semibold", size=26),
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Select a screen region — hear the text once.",
            font=ctk.CTkFont(family="Segoe UI", size=13),
        ).pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=(4, 8))

        self.select_btn = ctk.CTkButton(
            actions,
            text="Select region",
            height=48,
            width=150,
            command=self.start_region_capture,
            fg_color="#216e96",
            hover_color="#1a5878",
        )
        self.select_btn.pack(side="left")

        self.stop_btn = ctk.CTkButton(
            actions,
            text="Stop",
            height=48,
            width=90,
            command=self.stop_reading,
            fg_color="#8b3a3a",
            hover_color="#6e2e2e",
        )
        self.stop_btn.pack(side="left", padx=(10, 0))

        self.options_btn = ctk.CTkButton(
            actions,
            text="Options",
            height=48,
            width=110,
            command=self.open_options,
            fg_color="#4a5a6b",
            hover_color="#3a4856",
        )
        self.options_btn.pack(side="left", padx=(10, 0))

        preview = ctk.CTkFrame(self, fg_color="transparent")
        preview.pack(fill="both", expand=True, padx=20, pady=(2, 6))
        ctk.CTkLabel(preview, text="Recognized text", font=ctk.CTkFont(size=13)).pack(
            anchor="w"
        )
        self.text_box = ctk.CTkTextbox(
            preview,
            font=ctk.CTkFont(family="Consolas", size=int(self.settings.get("font_size", 18))),
            wrap="word",
        )
        self.text_box.pack(fill="both", expand=True, pady=(4, 0))
        self._raw_text = self.text_box._textbox  # noqa: SLF001
        self._raw_text.tag_configure("highlight", background="#ffe08a", foreground="#111111")

        self.hotkey_hint = ctk.CTkLabel(
            self,
            text=(
                f"Hotkeys: region {self.settings.get('hotkey_region')} · "
                f"stop {self.settings.get('hotkey_stop')}"
            ),
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        self.hotkey_hint.pack(fill="x", padx=22, pady=(0, 2))
        self.status_label = ctk.CTkLabel(self, text="Ready", font=ctk.CTkFont(size=13), anchor="w")
        self.status_label.pack(fill="x", padx=22, pady=(0, 14))

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
        self.status_label.configure(text=message)

    def _show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def _on_word(self, start: int, end: int, _word: str) -> None:
        def _apply() -> None:
            try:
                self._raw_text.tag_remove("highlight", "1.0", "end")
                self._raw_text.tag_add("highlight", f"1.0+{start}c", f"1.0+{end}c")
                self._raw_text.see(f"1.0+{start}c")
            except Exception:
                pass

        self._queue_call(_apply)

    def open_options(self) -> None:
        if self._options is not None and self._options.winfo_exists():
            self._options.focus_force()
            return
        self._options = OptionsWindow(self)

    def _register_hotkeys(self) -> None:
        mapping = {
            self.settings.get("hotkey_region", "ctrl+shift+r"): self.request_select_region,
            self.settings.get("hotkey_stop", "ctrl+shift+x"): lambda: self.after(
                0, self.stop_reading
            ),
        }
        try:
            self.hotkeys.register_many(mapping)
            self._set_status("Ready — select a region to read")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Hotkey failed ({exc}). Use the buttons.")

    # ---- capture / speak ----
    def start_region_capture(self) -> None:
        if self._busy:
            return
        if self._speaking or self.tts.is_busy():
            self._set_status("Already reading — press Stop first")
            return
        self._busy = True
        self._set_status("Select a region... (Esc to cancel)")
        self.update_idletasks()
        self.after(150, self._run_capture_flow)

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
            self._set_status(f"Region select failed: {exc}")
            return
        if was_visible:
            self._show_window()
        if image is None:
            self._busy = False
            self._set_status("Selection cancelled")
            return
        self._set_status("Reading text (OCR)...")
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

    def _set_preview_text(self, text: str) -> None:
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", text)
        try:
            self._raw_text.tag_remove("highlight", "1.0", "end")
        except Exception:
            pass

    def _on_text_ready(self, text: str | None, error: str | None) -> None:
        self._busy = False
        if error:
            self._set_status(error)
            return
        assert text is not None
        self._set_preview_text(text)
        self._set_status("Text ready — reading once")
        self._speak_once(text)

    def _speak_once(self, text: str) -> None:
        if self._speaking or self.tts.is_busy():
            self._set_status("Already reading — press Stop first")
            return
        text = (text or "").strip()
        if not text:
            self._set_status("No text to read")
            return

        engine = str(self.settings.get("engine", "edge"))
        voice_id = (
            str(self.settings.get("edge_voice", "en-US-JennyNeural"))
            if engine == "edge"
            else str(self.settings.get("offline_voice", ""))
        )
        self._speaking = True
        self.select_btn.configure(state="disabled")

        def _done() -> None:
            self._queue_call(self._on_speak_done)

        started = self.tts.speak(
            text,
            engine=engine,
            rate=int(self.settings.get("rate", 160)),
            volume=float(self.settings.get("volume", 1.0)),
            voice_id=voice_id,
            highlight=True,
            on_done=_done,
        )
        if not started:
            self._speaking = False
            self.select_btn.configure(state="normal")

    def _on_speak_done(self) -> None:
        self._speaking = False
        self.select_btn.configure(state="normal")
        try:
            self._raw_text.tag_remove("highlight", "1.0", "end")
        except Exception:
            pass

    def stop_reading(self) -> None:
        self.tts.stop()
        self._speaking = False
        self.select_btn.configure(state="normal")
        self._set_status("Stopped")
