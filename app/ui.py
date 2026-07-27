"""Main CustomTkinter window for Screen Read-Aloud."""

from __future__ import annotations

import threading
from typing import Callable

import customtkinter as ctk

from app.config import load_settings, save_settings
from app.hotkey import HotkeyManager
from app.ocr import OcrError, recognize_image
from app.region import select_region
from app.tts import TextToSpeech


ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Screen Read-Aloud")
        self.geometry("720x640")
        self.minsize(560, 520)

        self.settings = load_settings()
        self.tts = TextToSpeech(on_status=self._queue_status)
        self.hotkeys = HotkeyManager()
        self._busy = False
        self._on_quit_callbacks: list[Callable[[], None]] = []
        self._ui_queue: list[Callable[[], None]] = []

        self._build_ui()
        self._apply_settings_to_widgets()
        self._refresh_voices()
        self._register_hotkey()
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.after(100, self._drain_ui_queue)

    # ---- public API for tray ----
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
        self._set_status("Running in tray — use the hotkey or tray menu")

    def quit_app(self) -> None:
        self._persist_from_widgets()
        try:
            self.hotkeys.unregister()
        except Exception:
            pass
        self.tts.stop()
        for callback in self._on_quit_callbacks:
            try:
                callback()
            except Exception:
                pass
        self.destroy()

    # ---- UI construction ----
    def _build_ui(self) -> None:
        self.configure(fg_color=("#f3f1eb", "#1e1e1e"))

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(18, 8))

        ctk.CTkLabel(
            header,
            text="Screen Read-Aloud",
            font=ctk.CTkFont(family="Segoe UI Semibold", size=26),
            text_color=("#1b3a4b", "#e8f1f5"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text="Mark text on your screen, then hear it read aloud.",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=("#4a5560", "#b0b8c0"),
        ).pack(anchor="w", pady=(4, 0))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=(4, 8))

        self.select_btn = ctk.CTkButton(
            actions,
            text="Select region",
            height=44,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            command=self.start_region_capture,
            fg_color="#216e96",
            hover_color="#1a5878",
        )
        self.select_btn.pack(side="left")

        self.read_btn = ctk.CTkButton(
            actions,
            text="Read",
            height=44,
            width=100,
            font=ctk.CTkFont(family="Segoe UI", size=15),
            command=self.read_text,
            fg_color="#2f6b4f",
            hover_color="#24553e",
        )
        self.read_btn.pack(side="left", padx=(10, 0))

        self.pause_btn = ctk.CTkButton(
            actions,
            text="Pause",
            height=44,
            width=100,
            font=ctk.CTkFont(family="Segoe UI", size=15),
            command=self._toggle_pause,
            fg_color="#6b6b6b",
            hover_color="#555555",
        )
        self.pause_btn.pack(side="left", padx=(10, 0))

        self.stop_btn = ctk.CTkButton(
            actions,
            text="Stop",
            height=44,
            width=100,
            font=ctk.CTkFont(family="Segoe UI", size=15),
            command=self.tts.stop,
            fg_color="#8b3a3a",
            hover_color="#6e2e2e",
        )
        self.stop_btn.pack(side="left", padx=(10, 0))

        preview_frame = ctk.CTkFrame(self, fg_color="transparent")
        preview_frame.pack(fill="both", expand=True, padx=20, pady=(4, 8))

        ctk.CTkLabel(
            preview_frame,
            text="Recognized text (editable)",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=("#4a5560", "#b0b8c0"),
        ).pack(anchor="w")

        self.text_box = ctk.CTkTextbox(
            preview_frame,
            font=ctk.CTkFont(family="Consolas", size=int(self.settings["font_size"])),
            wrap="word",
            fg_color=("#fffdf8", "#2a2a2a"),
            text_color=("#1a1a1a", "#f0f0f0"),
            border_width=1,
            border_color=("#cfc8ba", "#444444"),
        )
        self.text_box.pack(fill="both", expand=True, pady=(6, 0))

        controls = ctk.CTkFrame(self, fg_color=("#ebe6dc", "#2a2a2a"), corner_radius=10)
        controls.pack(fill="x", padx=20, pady=(4, 8))

        row1 = ctk.CTkFrame(controls, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkLabel(row1, text="Engine", font=ctk.CTkFont(size=13)).pack(side="left")
        self.engine_var = ctk.StringVar(value=self.settings["engine"])
        self.engine_menu = ctk.CTkOptionMenu(
            row1,
            values=["offline", "edge"],
            variable=self.engine_var,
            command=self._on_engine_change,
            width=120,
        )
        self.engine_menu.pack(side="left", padx=(8, 16))

        ctk.CTkLabel(row1, text="Voice", font=ctk.CTkFont(size=13)).pack(side="left")
        self.voice_var = ctk.StringVar(value="")
        self.voice_menu = ctk.CTkOptionMenu(
            row1,
            values=["(default)"],
            variable=self.voice_var,
            width=260,
            command=lambda _v: self._persist_from_widgets(),
        )
        self.voice_menu.pack(side="left", padx=(8, 0))

        row2 = ctk.CTkFrame(controls, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=6)

        ctk.CTkLabel(row2, text="Rate", font=ctk.CTkFont(size=13)).pack(side="left")
        self.rate_slider = ctk.CTkSlider(
            row2,
            from_=80,
            to=260,
            number_of_steps=36,
            command=self._on_rate_change,
            width=180,
        )
        self.rate_slider.pack(side="left", padx=(8, 8))
        self.rate_label = ctk.CTkLabel(row2, text="160", width=40)
        self.rate_label.pack(side="left")

        ctk.CTkLabel(row2, text="Volume", font=ctk.CTkFont(size=13)).pack(
            side="left", padx=(16, 0)
        )
        self.volume_slider = ctk.CTkSlider(
            row2,
            from_=0,
            to=1,
            number_of_steps=20,
            command=self._on_volume_change,
            width=140,
        )
        self.volume_slider.pack(side="left", padx=(8, 8))
        self.volume_label = ctk.CTkLabel(row2, text="100%", width=48)
        self.volume_label.pack(side="left")

        row3 = ctk.CTkFrame(controls, fg_color="transparent")
        row3.pack(fill="x", padx=12, pady=6)

        ctk.CTkLabel(row3, text="Text size", font=ctk.CTkFont(size=13)).pack(side="left")
        self.font_slider = ctk.CTkSlider(
            row3,
            from_=14,
            to=32,
            number_of_steps=18,
            command=self._on_font_change,
            width=140,
        )
        self.font_slider.pack(side="left", padx=(8, 8))
        self.font_label = ctk.CTkLabel(row3, text="18", width=36)
        self.font_label.pack(side="left")

        self.auto_speak_var = ctk.BooleanVar(value=bool(self.settings["auto_speak"]))
        self.auto_speak_check = ctk.CTkCheckBox(
            row3,
            text="Auto-speak after OCR",
            variable=self.auto_speak_var,
            command=self._persist_from_widgets,
        )
        self.auto_speak_check.pack(side="left", padx=(20, 0))

        row4 = ctk.CTkFrame(controls, fg_color="transparent")
        row4.pack(fill="x", padx=12, pady=(6, 12))

        ctk.CTkLabel(row4, text="Hotkey", font=ctk.CTkFont(size=13)).pack(side="left")
        self.hotkey_entry = ctk.CTkEntry(row4, width=160, placeholder_text="ctrl+shift+r")
        self.hotkey_entry.pack(side="left", padx=(8, 8))
        ctk.CTkButton(
            row4,
            text="Apply hotkey",
            width=120,
            command=self._apply_hotkey,
        ).pack(side="left")

        ctk.CTkLabel(row4, text="OCR lang", font=ctk.CTkFont(size=13)).pack(
            side="left", padx=(16, 0)
        )
        self.lang_entry = ctk.CTkEntry(row4, width=70, placeholder_text="en")
        self.lang_entry.pack(side="left", padx=(8, 0))
        self.lang_entry.bind("<FocusOut>", lambda _e: self._persist_from_widgets())

        self.status_label = ctk.CTkLabel(
            self,
            text="Ready — press Ctrl+Shift+R or click Select region",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=("#2f4f5f", "#c5d4dc"),
            anchor="w",
        )
        self.status_label.pack(fill="x", padx=22, pady=(0, 14))

    def _apply_settings_to_widgets(self) -> None:
        self.engine_var.set(self.settings.get("engine", "offline"))
        self.rate_slider.set(float(self.settings.get("rate", 160)))
        self.rate_label.configure(text=str(int(self.rate_slider.get())))
        self.volume_slider.set(float(self.settings.get("volume", 1.0)))
        self.volume_label.configure(text=f"{int(self.volume_slider.get() * 100)}%")
        self.font_slider.set(float(self.settings.get("font_size", 18)))
        self.font_label.configure(text=str(int(self.font_slider.get())))
        self.auto_speak_var.set(bool(self.settings.get("auto_speak", True)))
        self.hotkey_entry.delete(0, "end")
        self.hotkey_entry.insert(0, str(self.settings.get("hotkey", "ctrl+shift+r")))
        self.lang_entry.delete(0, "end")
        self.lang_entry.insert(0, str(self.settings.get("ocr_lang", "en")))
        self._update_text_font()

    # ---- queue helpers (thread-safe UI updates) ----
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
        self.after(100, self._drain_ui_queue)

    def _set_status(self, message: str) -> None:
        self.status_label.configure(text=message)

    def _show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    # ---- settings / voices ----
    def _persist_from_widgets(self) -> None:
        self.settings["engine"] = self.engine_var.get()
        self.settings["rate"] = int(self.rate_slider.get())
        self.settings["volume"] = float(self.volume_slider.get())
        self.settings["font_size"] = int(self.font_slider.get())
        self.settings["auto_speak"] = bool(self.auto_speak_var.get())
        self.settings["hotkey"] = self.hotkey_entry.get().strip().lower()
        self.settings["ocr_lang"] = self.lang_entry.get().strip() or "en"

        voice = self.voice_var.get()
        if self.settings["engine"] == "edge":
            # voice menu shows "id (locale)" for edge; store id only when possible
            edge_id = voice.split(" ")[0] if voice else self.settings.get("edge_voice")
            if voice and voice != "(default)":
                # Prefer matching known edge voice ids stored as ShortName
                self.settings["edge_voice"] = self._voice_id_from_label(voice) or edge_id
        else:
            if voice == "(default)" or not voice:
                self.settings["offline_voice"] = ""
            else:
                self.settings["offline_voice"] = self._voice_id_from_label(voice) or ""

        # Map rate slider to edge-tts rate roughly
        offline_rate = int(self.rate_slider.get())
        # 160 is baseline -> +0%
        pct = int((offline_rate - 160) / 160 * 100)
        pct = max(-50, min(100, pct))
        sign = "+" if pct >= 0 else ""
        self.settings["edge_rate"] = f"{sign}{pct}%"

        save_settings(self.settings)

    def _voice_id_from_label(self, label: str) -> str:
        mapping: dict[str, str] = getattr(self, "_voice_map", {})
        return mapping.get(label, "")

    def _on_engine_change(self, _value: str) -> None:
        self._persist_from_widgets()
        self._refresh_voices()

    def _on_rate_change(self, value: float) -> None:
        self.rate_label.configure(text=str(int(value)))
        self._persist_from_widgets()

    def _on_volume_change(self, value: float) -> None:
        self.volume_label.configure(text=f"{int(float(value) * 100)}%")
        self._persist_from_widgets()

    def _on_font_change(self, value: float) -> None:
        self.font_label.configure(text=str(int(value)))
        self._update_text_font()
        self._persist_from_widgets()

    def _update_text_font(self) -> None:
        size = int(self.font_slider.get())
        self.text_box.configure(font=ctk.CTkFont(family="Consolas", size=size))

    def _refresh_voices(self) -> None:
        engine = self.engine_var.get()
        self.voice_menu.configure(values=["Loading…"])
        self.voice_var.set("Loading…")

        def _load() -> None:
            voice_map: dict[str, str] = {}
            labels: list[str] = []
            selected = ""
            try:
                if engine == "edge":
                    voices = self.tts.list_edge_voices_sync("en")
                    for voice in voices:
                        label = voice["name"]
                        voice_map[label] = voice["id"]
                        labels.append(label)
                    wanted = self.settings.get("edge_voice", "en-US-JennyNeural")
                    selected = next(
                        (lbl for lbl, vid in voice_map.items() if vid == wanted),
                        labels[0] if labels else "(default)",
                    )
                else:
                    labels = ["(default)"]
                    voice_map["(default)"] = ""
                    for voice in self.tts.list_offline_voices():
                        label = voice["name"]
                        # ensure unique labels
                        if label in voice_map:
                            label = f'{voice["name"]} [{voice["id"][-12:]}]'
                        voice_map[label] = voice["id"]
                        labels.append(label)
                    wanted = self.settings.get("offline_voice", "")
                    if wanted:
                        selected = next(
                            (lbl for lbl, vid in voice_map.items() if vid == wanted),
                            "(default)",
                        )
                    else:
                        selected = "(default)"
            except Exception as exc:  # noqa: BLE001
                labels = ["(default)"]
                voice_map = {"(default)": ""}
                selected = "(default)"
                self._queue_status(f"Could not load voices: {exc}")

            def _apply() -> None:
                self._voice_map = voice_map
                if not labels:
                    labels.append("(default)")
                self.voice_menu.configure(values=labels)
                self.voice_var.set(selected if selected in labels else labels[0])

            self._queue_call(_apply)

        threading.Thread(target=_load, daemon=True).start()

    def _register_hotkey(self) -> None:
        hotkey = self.settings.get("hotkey", "ctrl+shift+r")
        try:
            self.hotkeys.register(hotkey, self.request_select_region)
            self._set_status(f"Ready — hotkey: {hotkey}")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Hotkey failed ({exc}). Use the Select region button.")

    def _apply_hotkey(self) -> None:
        self._persist_from_widgets()
        self._register_hotkey()

    # ---- core actions ----
    def start_region_capture(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._set_status("Select a region… (Esc to cancel)")
        self.update_idletasks()

        # Slight delay so the button release / hotkey doesn't affect the overlay
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

        self._set_status("Reading text (OCR)…")
        lang = self.lang_entry.get().strip() or "en"

        def _ocr() -> None:
            try:
                text = recognize_image(image, lang=lang)
            except OcrError as exc:
                self._queue_call(lambda: self._on_ocr_done(None, str(exc)))
                return
            except Exception as exc:  # noqa: BLE001
                self._queue_call(lambda: self._on_ocr_done(None, f"OCR error: {exc}"))
                return
            self._queue_call(lambda: self._on_ocr_done(text, None))

        threading.Thread(target=_ocr, daemon=True).start()

    def _on_ocr_done(self, text: str | None, error: str | None) -> None:
        self._busy = False
        if error:
            self._set_status(error)
            return
        assert text is not None
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", text)
        self._set_status("Text recognized")
        if self.auto_speak_var.get():
            self.read_text()

    def get_preview_text(self) -> str:
        return self.text_box.get("1.0", "end").strip()

    def read_text(self) -> None:
        self._persist_from_widgets()
        text = self.get_preview_text()
        if not text:
            self._set_status("Nothing to read — select a region first")
            return
        self.pause_btn.configure(text="Pause")
        self.tts.speak(
            text,
            engine=self.settings.get("engine", "offline"),
            rate=int(self.settings.get("rate", 160)),
            volume=float(self.settings.get("volume", 1.0)),
            offline_voice=str(self.settings.get("offline_voice", "")),
            edge_voice=str(self.settings.get("edge_voice", "en-US-JennyNeural")),
            edge_rate=str(self.settings.get("edge_rate", "+0%")),
        )

    def _toggle_pause(self) -> None:
        if self.pause_btn.cget("text") == "Pause":
            self.tts.pause()
            if self.engine_var.get() == "edge":
                self.pause_btn.configure(text="Resume")
        else:
            self.tts.resume()
            self.pause_btn.configure(text="Pause")
