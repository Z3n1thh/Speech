"""Main CustomTkinter window for Screen Read-Aloud."""

from __future__ import annotations

import threading
from typing import Callable

import customtkinter as ctk

from app import autostart
from app.config import load_settings, save_settings
from app.history import add_history, load_history
from app.hotkey import HotkeyManager
from app.ocr import OcrError, recognize_image
from app.region import select_region
from app.selection import get_selected_text
from app.tts import TextToSpeech


ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Screen Read-Aloud")
        self.geometry("760x700")
        self.minsize(580, 560)

        self.settings = load_settings()
        self.tts = TextToSpeech(
            on_status=self._queue_status,
            on_word=self._on_word,
        )
        self.hotkeys = HotkeyManager()
        self._busy = False
        self._on_quit_callbacks: list[Callable[[], None]] = []
        self._ui_queue: list[Callable[[], None]] = []
        self._history = load_history()
        self._voice_map: dict[str, str] = {"(default)": ""}

        self._build_ui()
        self._apply_settings_to_widgets()
        self._refresh_voices()
        self._refresh_history_menu()
        self._register_hotkeys()
        self._apply_simple_mode()
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.after(100, self._drain_ui_queue)

    # ---- public API for tray ----
    def add_quit_callback(self, callback: Callable[[], None]) -> None:
        self._on_quit_callbacks.append(callback)

    def show_window(self) -> None:
        self.after(0, self._show_window)

    def request_select_region(self) -> None:
        self.after(0, self.start_region_capture)

    def request_read_selection(self) -> None:
        self.after(0, self.start_selection_capture)

    def request_quit(self) -> None:
        self.after(0, self.quit_app)

    def hide_to_tray(self) -> None:
        self.withdraw()
        self._set_status("Running in tray — use hotkeys or tray menu")

    def quit_app(self) -> None:
        self._persist_from_widgets()
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
            text="Mark text on screen (or select it), then hear it read aloud.",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=("#4a5560", "#b0b8c0"),
        ).pack(anchor="w", pady=(4, 0))

        self.actions = ctk.CTkFrame(self, fg_color="transparent")
        self.actions.pack(fill="x", padx=20, pady=(4, 8))

        self.select_btn = ctk.CTkButton(
            self.actions,
            text="Select region",
            height=48,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            command=self.start_region_capture,
            fg_color="#216e96",
            hover_color="#1a5878",
        )
        self.select_btn.pack(side="left")

        self.selection_btn = ctk.CTkButton(
            self.actions,
            text="Read selection",
            height=48,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            command=self.start_selection_capture,
            fg_color="#3a6e8b",
            hover_color="#2f5a72",
        )
        self.selection_btn.pack(side="left", padx=(10, 0))

        self.read_btn = ctk.CTkButton(
            self.actions,
            text="Read",
            height=48,
            width=110,
            font=ctk.CTkFont(family="Segoe UI", size=15),
            command=self.read_text,
            fg_color="#2f6b4f",
            hover_color="#24553e",
        )
        self.read_btn.pack(side="left", padx=(10, 0))

        self.pause_btn = ctk.CTkButton(
            self.actions,
            text="Pause",
            height=48,
            width=110,
            font=ctk.CTkFont(family="Segoe UI", size=15),
            command=self._toggle_pause,
            fg_color="#6b6b6b",
            hover_color="#555555",
        )
        self.pause_btn.pack(side="left", padx=(10, 0))

        self.stop_btn = ctk.CTkButton(
            self.actions,
            text="Stop",
            height=48,
            width=110,
            font=ctk.CTkFont(family="Segoe UI", size=15),
            command=lambda: self.tts.stop(),
            fg_color="#8b3a3a",
            hover_color="#6e2e2e",
        )
        self.stop_btn.pack(side="left", padx=(10, 0))

        preview_frame = ctk.CTkFrame(self, fg_color="transparent")
        preview_frame.pack(fill="both", expand=True, padx=20, pady=(4, 8))
        ctk.CTkLabel(
            preview_frame,
            text="Text preview (editable) — current word is highlighted",
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
        # Underlying tk Text for highlight tags
        self._raw_text = self.text_box._textbox  # noqa: SLF001
        self._raw_text.tag_configure("highlight", background="#ffe08a", foreground="#111111")

        self.controls = ctk.CTkFrame(self, fg_color=("#ebe6dc", "#2a2a2a"), corner_radius=10)
        self.controls.pack(fill="x", padx=20, pady=(4, 8))

        row1 = ctk.CTkFrame(self.controls, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkLabel(row1, text="Engine", font=ctk.CTkFont(size=13)).pack(side="left")
        self.engine_var = ctk.StringVar(value=str(self.settings.get("engine", "edge")))
        self.engine_menu = ctk.CTkOptionMenu(
            row1,
            values=["edge", "offline"],
            variable=self.engine_var,
            width=110,
            command=self._on_engine_change,
        )
        self.engine_menu.pack(side="left", padx=(8, 12))

        ctk.CTkLabel(row1, text="Voice", font=ctk.CTkFont(size=13)).pack(side="left")
        self.voice_var = ctk.StringVar(value="(default)")
        self.voice_menu = ctk.CTkOptionMenu(
            row1,
            values=["(default)"],
            variable=self.voice_var,
            width=280,
            command=lambda _v: self._persist_from_widgets(),
        )
        self.voice_menu.pack(side="left", padx=(8, 12))

        ctk.CTkLabel(row1, text="OCR lang", font=ctk.CTkFont(size=13)).pack(side="left")
        self.lang_var = ctk.StringVar(value=str(self.settings.get("ocr_lang", "en")))
        self.lang_menu = ctk.CTkOptionMenu(
            row1,
            values=["en", "sv"],
            variable=self.lang_var,
            width=80,
            command=lambda _v: self._on_lang_change(),
        )
        self.lang_menu.pack(side="left", padx=(8, 0))

        row2 = ctk.CTkFrame(self.controls, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(row2, text="Rate", font=ctk.CTkFont(size=13)).pack(side="left")
        self.rate_slider = ctk.CTkSlider(
            row2, from_=80, to=260, number_of_steps=36, command=self._on_rate_change, width=180
        )
        self.rate_slider.pack(side="left", padx=(8, 8))
        self.rate_label = ctk.CTkLabel(row2, text="160", width=40)
        self.rate_label.pack(side="left")
        ctk.CTkLabel(row2, text="Volume", font=ctk.CTkFont(size=13)).pack(side="left", padx=(16, 0))
        self.volume_slider = ctk.CTkSlider(
            row2, from_=0, to=1, number_of_steps=20, command=self._on_volume_change, width=140
        )
        self.volume_slider.pack(side="left", padx=(8, 8))
        self.volume_label = ctk.CTkLabel(row2, text="100%", width=48)
        self.volume_label.pack(side="left")

        row3 = ctk.CTkFrame(self.controls, fg_color="transparent")
        row3.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(row3, text="Text size", font=ctk.CTkFont(size=13)).pack(side="left")
        self.font_slider = ctk.CTkSlider(
            row3, from_=14, to=36, number_of_steps=22, command=self._on_font_change, width=140
        )
        self.font_slider.pack(side="left", padx=(8, 8))
        self.font_label = ctk.CTkLabel(row3, text="18", width=36)
        self.font_label.pack(side="left")

        self.auto_speak_var = ctk.BooleanVar(value=bool(self.settings["auto_speak"]))
        ctk.CTkCheckBox(
            row3,
            text="Auto-speak",
            variable=self.auto_speak_var,
            command=self._persist_from_widgets,
        ).pack(side="left", padx=(16, 0))

        self.highlight_var = ctk.BooleanVar(value=bool(self.settings.get("word_highlight", True)))
        ctk.CTkCheckBox(
            row3,
            text="Highlight words",
            variable=self.highlight_var,
            command=self._persist_from_widgets,
        ).pack(side="left", padx=(12, 0))

        row4 = ctk.CTkFrame(self.controls, fg_color="transparent")
        row4.pack(fill="x", padx=12, pady=6)
        self.simple_mode_var = ctk.BooleanVar(value=bool(self.settings.get("simple_mode", False)))
        ctk.CTkCheckBox(
            row4,
            text="Simple mode (big buttons)",
            variable=self.simple_mode_var,
            command=self._on_simple_mode_toggle,
        ).pack(side="left")

        self.autostart_var = ctk.BooleanVar(
            value=bool(self.settings.get("autostart", False)) or autostart.is_enabled()
        )
        ctk.CTkCheckBox(
            row4,
            text="Start with Windows",
            variable=self.autostart_var,
            command=self._on_autostart_toggle,
        ).pack(side="left", padx=(16, 0))

        row5 = ctk.CTkFrame(self.controls, fg_color="transparent")
        row5.pack(fill="x", padx=12, pady=(6, 12))
        ctk.CTkLabel(row5, text="History", font=ctk.CTkFont(size=13)).pack(side="left")
        self.history_var = ctk.StringVar(value="(empty)")
        self.history_menu = ctk.CTkOptionMenu(
            row5,
            values=["(empty)"],
            variable=self.history_var,
            width=320,
            command=self._on_history_pick,
        )
        self.history_menu.pack(side="left", padx=(8, 8))
        ctk.CTkButton(row5, text="Apply hotkeys", width=120, command=self._apply_hotkeys).pack(
            side="left"
        )

        self.hotkey_hint = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("#5a6570", "#a8b2ba"),
            anchor="w",
            justify="left",
        )
        self.hotkey_hint.pack(fill="x", padx=22, pady=(0, 2))

        self.status_label = ctk.CTkLabel(
            self,
            text="Ready",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=("#2f4f5f", "#c5d4dc"),
            anchor="w",
        )
        self.status_label.pack(fill="x", padx=22, pady=(0, 14))

    def _apply_settings_to_widgets(self) -> None:
        engine = str(self.settings.get("engine", "edge"))
        self.engine_var.set(engine if engine in ("edge", "offline") else "edge")
        self.rate_slider.set(float(self.settings.get("rate", 160)))
        self.rate_label.configure(text=str(int(self.rate_slider.get())))
        self.volume_slider.set(float(self.settings.get("volume", 1.0)))
        self.volume_label.configure(text=f"{int(self.volume_slider.get() * 100)}%")
        self.font_slider.set(float(self.settings.get("font_size", 18)))
        self.font_label.configure(text=str(int(self.font_slider.get())))
        self.auto_speak_var.set(bool(self.settings.get("auto_speak", True)))
        self.highlight_var.set(bool(self.settings.get("word_highlight", True)))
        self.simple_mode_var.set(bool(self.settings.get("simple_mode", False)))
        lang = str(self.settings.get("ocr_lang", "en"))
        self.lang_var.set(lang if lang in ("en", "sv") else "en")
        # Prefer Swedish neural voice when OCR lang is Swedish and none saved
        if self.lang_var.get() == "sv" and self.settings.get("edge_voice", "").startswith("en-"):
            self.settings["edge_voice"] = "sv-SE-SofieNeural"
        self._update_text_font()
        self._update_hotkey_hint()

    def _update_hotkey_hint(self) -> None:
        s = self.settings
        self.hotkey_hint.configure(
            text=(
                f"Hotkeys: region {s.get('hotkey_region')} · selection {s.get('hotkey_selection')} · "
                f"stop {s.get('hotkey_stop')} · faster {s.get('hotkey_faster')} · slower {s.get('hotkey_slower')}"
            )
        )

    # ---- queue / highlight ----
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
        if not self.highlight_var.get():
            return

        def _apply() -> None:
            try:
                self._raw_text.tag_remove("highlight", "1.0", "end")
                start_idx = f"1.0+{start}c"
                end_idx = f"1.0+{end}c"
                self._raw_text.tag_add("highlight", start_idx, end_idx)
                self._raw_text.see(start_idx)
            except Exception:
                pass

        self._queue_call(_apply)

    # ---- settings ----
    def _persist_from_widgets(self) -> None:
        self.settings["engine"] = self.engine_var.get()
        self.settings["rate"] = int(self.rate_slider.get())
        self.settings["volume"] = float(self.volume_slider.get())
        self.settings["font_size"] = int(self.font_slider.get())
        self.settings["auto_speak"] = bool(self.auto_speak_var.get())
        self.settings["word_highlight"] = bool(self.highlight_var.get())
        self.settings["simple_mode"] = bool(self.simple_mode_var.get())
        self.settings["autostart"] = bool(self.autostart_var.get())
        self.settings["ocr_lang"] = self.lang_var.get()
        voice = self.voice_var.get()
        voice_id = self._voice_map.get(voice, "")
        if self.settings["engine"] == "edge":
            if voice_id:
                self.settings["edge_voice"] = voice_id
        else:
            self.settings["offline_voice"] = "" if voice in ("(default)", "") else voice_id
        save_settings(self.settings)

    def _on_engine_change(self, _value: str) -> None:
        self._persist_from_widgets()
        self._refresh_voices()
        self._set_status(
            "Neural Edge voices (needs internet)"
            if self.engine_var.get() == "edge"
            else "Offline Windows voices"
        )

    def _on_rate_change(self, value: float) -> None:
        rate = int(value)
        self.rate_label.configure(text=str(rate))
        self.tts.set_rate(rate)
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

    def _on_lang_change(self) -> None:
        self._persist_from_widgets()
        engine = self.engine_var.get()
        preferred = self.tts.prefer_voice_for_lang(self.lang_var.get(), engine=engine)
        if preferred:
            if engine == "edge":
                self.settings["edge_voice"] = preferred
            else:
                self.settings["offline_voice"] = preferred
            save_settings(self.settings)
        self._refresh_voices()

    def _on_simple_mode_toggle(self) -> None:
        self._persist_from_widgets()
        self._apply_simple_mode()

    def _apply_simple_mode(self) -> None:
        simple = bool(self.simple_mode_var.get())
        if simple:
            self.controls.pack_forget()
            self.hotkey_hint.pack_forget()
            for btn in (
                self.select_btn,
                self.selection_btn,
                self.read_btn,
                self.pause_btn,
                self.stop_btn,
            ):
                btn.configure(height=64, font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"))
            self.geometry("700x520")
        else:
            self.controls.pack(fill="x", padx=20, pady=(4, 8))
            self.hotkey_hint.pack(fill="x", padx=22, pady=(0, 2))
            self.status_label.pack_forget()
            self.status_label.pack(fill="x", padx=22, pady=(0, 14))
            for btn, h, size in (
                (self.select_btn, 48, 15),
                (self.selection_btn, 48, 15),
                (self.read_btn, 48, 15),
                (self.pause_btn, 48, 15),
                (self.stop_btn, 48, 15),
            ):
                btn.configure(height=h, font=ctk.CTkFont(family="Segoe UI", size=size, weight="bold"))
            self.geometry("760x700")

    def _on_autostart_toggle(self) -> None:
        enabled = bool(self.autostart_var.get())
        try:
            autostart.set_enabled(enabled)
            self.settings["autostart"] = enabled
            save_settings(self.settings)
            self._set_status("Autostart on" if enabled else "Autostart off")
        except Exception as exc:  # noqa: BLE001
            self.autostart_var.set(autostart.is_enabled())
            self._set_status(f"Autostart failed: {exc}")

    def _refresh_voices(self) -> None:
        self.voice_menu.configure(values=["Loading..."])
        self.voice_var.set("Loading...")
        engine = self.engine_var.get()
        lang = self.lang_var.get()

        def _load() -> None:
            voice_map: dict[str, str] = {}
            labels: list[str] = []
            selected = ""
            try:
                if engine == "edge":
                    voices = self.tts.list_edge_voices_sync(lang)
                    for voice in voices:
                        label = voice["name"]
                        voice_map[label] = voice["id"]
                        labels.append(label)
                    wanted = self.settings.get("edge_voice", "")
                    if not wanted:
                        wanted = self.tts.prefer_voice_for_lang(lang, engine="edge")
                    selected = next(
                        (lbl for lbl, vid in voice_map.items() if vid == wanted),
                        labels[0] if labels else "(default)",
                    )
                else:
                    labels = ["(default)"]
                    voice_map["(default)"] = ""
                    for voice in self.tts.list_offline_voices():
                        label = voice["name"]
                        if label in voice_map:
                            label = f'{voice["name"]} [{voice["id"][-12:]}]'
                        voice_map[label] = voice["id"]
                        labels.append(label)
                    wanted = self.settings.get("offline_voice", "")
                    if not wanted:
                        wanted = self.tts.prefer_voice_for_lang(lang, engine="offline")
                    selected = next(
                        (lbl for lbl, vid in voice_map.items() if vid == wanted),
                        "(default)",
                    )
            except Exception as exc:  # noqa: BLE001
                labels = ["(default)"]
                voice_map = {"(default)": ""}
                selected = "(default)"
                self._queue_status(f"Could not load voices: {exc}")

            def _apply() -> None:
                self._voice_map = voice_map
                if not labels:
                    labels = ["(default)"]
                self.voice_menu.configure(values=labels)
                self.voice_var.set(selected if selected in labels else labels[0])

            self._queue_call(_apply)

        threading.Thread(target=_load, daemon=True).start()

    def _refresh_history_menu(self) -> None:
        if not self._history:
            self.history_menu.configure(values=["(empty)"])
            self.history_var.set("(empty)")
            return
        labels = [item.get("preview", "item") for item in self._history]
        self.history_menu.configure(values=labels)
        self.history_var.set(labels[0])

    def _on_history_pick(self, preview: str) -> None:
        for item in self._history:
            if item.get("preview") == preview:
                self._set_preview_text(item.get("text", ""))
                self._set_status("Loaded from history")
                return

    def _register_hotkeys(self) -> None:
        mapping = {
            self.settings.get("hotkey_region", "ctrl+shift+r"): self.request_select_region,
            self.settings.get("hotkey_selection", "ctrl+shift+s"): self.request_read_selection,
            self.settings.get("hotkey_stop", "ctrl+shift+x"): lambda: self.after(0, self.tts.stop),
            self.settings.get("hotkey_faster", "ctrl+shift+up"): lambda: self.after(
                0, lambda: self._nudge_rate(10)
            ),
            self.settings.get("hotkey_slower", "ctrl+shift+down"): lambda: self.after(
                0, lambda: self._nudge_rate(-10)
            ),
        }
        try:
            self.hotkeys.register_many(mapping)
            self._update_hotkey_hint()
            self._set_status("Ready — hotkeys active")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Hotkey failed ({exc}). Use the buttons.")

    def _apply_hotkeys(self) -> None:
        self._persist_from_widgets()
        self._register_hotkeys()

    def _nudge_rate(self, delta: int) -> None:
        rate = self.tts.adjust_rate(delta)
        self.rate_slider.set(rate)
        self.rate_label.configure(text=str(rate))
        self.settings["rate"] = rate
        save_settings(self.settings)
        self._set_status(f"Rate: {rate}")

    # ---- capture flows ----
    def start_region_capture(self) -> None:
        if self._busy:
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
        lang = self.lang_var.get() or "en"

        def _ocr() -> None:
            try:
                text = recognize_image(image, lang=lang)
            except OcrError as exc:
                self._queue_call(lambda: self._on_text_ready(None, str(exc), "ocr"))
                return
            except Exception as exc:  # noqa: BLE001
                self._queue_call(lambda: self._on_text_ready(None, f"OCR error: {exc}", "ocr"))
                return
            self._queue_call(lambda: self._on_text_ready(text, None, "ocr"))

        threading.Thread(target=_ocr, daemon=True).start()

    def start_selection_capture(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._set_status("Reading highlighted selection...")

        def _run() -> None:
            try:
                text = get_selected_text()
            except Exception as exc:  # noqa: BLE001
                self._queue_call(
                    lambda: self._on_text_ready(None, f"Selection failed: {exc}", "selection")
                )
                return
            if not text:
                self._queue_call(
                    lambda: self._on_text_ready(
                        None,
                        "No selected text found. Highlight text first, then press the hotkey.",
                        "selection",
                    )
                )
                return
            self._queue_call(lambda: self._on_text_ready(text, None, "selection"))

        threading.Thread(target=_run, daemon=True).start()

    def _set_preview_text(self, text: str) -> None:
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", text)
        try:
            self._raw_text.tag_remove("highlight", "1.0", "end")
        except Exception:
            pass

    def _on_text_ready(self, text: str | None, error: str | None, source: str) -> None:
        self._busy = False
        if error:
            self._set_status(error)
            return
        assert text is not None
        self._set_preview_text(text)
        self._history = add_history(text, source=source)
        self._refresh_history_menu()
        self._set_status("Text ready")
        if self.auto_speak_var.get():
            self.read_text()

    def get_preview_text(self) -> str:
        return self.text_box.get("1.0", "end").strip()

    def read_text(self) -> None:
        self._persist_from_widgets()
        text = self.get_preview_text()
        if not text:
            self._set_status("Nothing to read — capture text first")
            return
        self.pause_btn.configure(text="Pause")
        engine = str(self.settings.get("engine", "edge"))
        voice_id = (
            str(self.settings.get("edge_voice", "en-US-JennyNeural"))
            if engine == "edge"
            else str(self.settings.get("offline_voice", ""))
        )
        self.tts.speak(
            text,
            engine=engine,
            rate=int(self.settings.get("rate", 160)),
            volume=float(self.settings.get("volume", 1.0)),
            voice_id=voice_id,
            highlight=bool(self.highlight_var.get()),
            on_done=lambda: self._queue_call(lambda: self.pause_btn.configure(text="Pause")),
        )

    def _toggle_pause(self) -> None:
        if self.tts.is_paused():
            self.tts.resume()
            self.pause_btn.configure(text="Pause")
        else:
            self.tts.pause()
            self.pause_btn.configure(text="Resume")
