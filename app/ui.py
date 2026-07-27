"""Main CustomTkinter window for Screen Read-Aloud."""

from __future__ import annotations

import threading
from tkinter import filedialog
from typing import Any, Callable

import customtkinter as ctk

from app import autostart
from app.config import load_settings, save_settings
from app.history import add_history, load_history
from app.hotkey import HotkeyManager
from app.memory import load_memory, save_memory
from app.ocr import OCR_LANG_CHOICES, OcrError, recognize_image
from app.pdf_read import PdfError, extract_pdf_text
from app.profiles import (
    apply_profile,
    delete_profile,
    find_profile,
    snapshot_from_settings,
    upsert_profile,
)
from app.region import select_region
from app.selection import get_selected_text
from app.textutil import next_sentence_after, sentence_at_or_after
from app.tts import TextToSpeech


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Screen Read-Aloud")
        self.geometry("820x760")
        self.minsize(620, 600)

        self.settings = load_settings()
        self._apply_theme(self.settings.get("theme", "dark"))

        self.tts = TextToSpeech(on_status=self._queue_status, on_word=self._on_word)
        self.hotkeys = HotkeyManager()
        self._busy = False
        self._on_quit_callbacks: list[Callable[[], None]] = []
        self._ui_queue: list[Callable[[], None]] = []
        self._history = load_history()
        self._voice_map: dict[str, str] = {}
        self._sentence_cursor = 0
        self._current_source = ""
        self._current_path = ""

        self._build_ui()
        self._apply_settings_to_widgets()
        self._refresh_voices()
        self._refresh_history_menu()
        self._refresh_profiles_menu()
        self._register_hotkeys()
        self._apply_simple_mode()
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

    def request_read_selection(self) -> None:
        self.after(0, self.start_selection_capture)

    def request_quit(self) -> None:
        self.after(0, self.quit_app)

    def hide_to_tray(self) -> None:
        self.withdraw()
        self._set_status("Running in tray — use hotkeys or tray menu")

    def quit_app(self) -> None:
        text = self.get_preview_text()
        if text.strip():
            try:
                save_memory(
                    text,
                    self._sentence_cursor,
                    source=self._current_source,
                    path=self._current_path,
                )
            except Exception:
                pass
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
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 6))
        ctk.CTkLabel(
            header,
            text="Screen Read-Aloud",
            font=ctk.CTkFont(family="Segoe UI Semibold", size=26),
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Region OCR · selection · PDF (incl. scanned) — then hear it aloud.",
            font=ctk.CTkFont(family="Segoe UI", size=13),
        ).pack(anchor="w", pady=(2, 0))

        self.actions = ctk.CTkFrame(self, fg_color="transparent")
        self.actions.pack(fill="x", padx=20, pady=(4, 6))

        self.select_btn = ctk.CTkButton(
            self.actions, text="Select region", height=46, width=130,
            command=self.start_region_capture, fg_color="#216e96", hover_color="#1a5878",
        )
        self.select_btn.pack(side="left")
        self.selection_btn = ctk.CTkButton(
            self.actions, text="Read selection", height=46, width=130,
            command=self.start_selection_capture, fg_color="#3a6e8b", hover_color="#2f5a72",
        )
        self.selection_btn.pack(side="left", padx=(8, 0))
        self.pdf_btn = ctk.CTkButton(
            self.actions, text="Open PDF", height=46, width=100,
            command=self.open_pdf, fg_color="#5a4e8c", hover_color="#463c6e",
        )
        self.pdf_btn.pack(side="left", padx=(8, 0))
        self.read_btn = ctk.CTkButton(
            self.actions, text="Read", height=46, width=90,
            command=self.read_text, fg_color="#2f6b4f", hover_color="#24553e",
        )
        self.read_btn.pack(side="left", padx=(8, 0))
        self.continue_btn = ctk.CTkButton(
            self.actions, text="Continue", height=46, width=100,
            command=self.continue_reading, fg_color="#2f6b4f", hover_color="#24553e",
        )
        self.continue_btn.pack(side="left", padx=(8, 0))
        self.from_cursor_btn = ctk.CTkButton(
            self.actions, text="From cursor", height=46, width=110,
            command=self.read_from_cursor, fg_color="#2f6b4f", hover_color="#24553e",
        )
        self.from_cursor_btn.pack(side="left", padx=(8, 0))
        self.next_sent_btn = ctk.CTkButton(
            self.actions, text="Next sentence", height=46, width=120,
            command=self.read_next_sentence, fg_color="#4a6b3a", hover_color="#3a552e",
        )
        self.next_sent_btn.pack(side="left", padx=(8, 0))
        self.pause_btn = ctk.CTkButton(
            self.actions, text="Pause", height=46, width=90,
            command=self._toggle_pause, fg_color="#6b6b6b", hover_color="#555555",
        )
        self.pause_btn.pack(side="left", padx=(8, 0))
        self.stop_btn = ctk.CTkButton(
            self.actions, text="Stop", height=46, width=80,
            command=self._stop_and_remember, fg_color="#8b3a3a", hover_color="#6e2e2e",
        )
        self.stop_btn.pack(side="left", padx=(8, 0))

        preview = ctk.CTkFrame(self, fg_color="transparent")
        preview.pack(fill="both", expand=True, padx=20, pady=(2, 6))
        ctk.CTkLabel(preview, text="Text preview (editable)", font=ctk.CTkFont(size=13)).pack(
            anchor="w"
        )
        self.text_box = ctk.CTkTextbox(
            preview,
            font=ctk.CTkFont(family="Consolas", size=int(self.settings["font_size"])),
            wrap="word",
        )
        self.text_box.pack(fill="both", expand=True, pady=(4, 0))
        self._raw_text = self.text_box._textbox  # noqa: SLF001
        self._raw_text.tag_configure("highlight", background="#ffe08a", foreground="#111111")

        self.controls = ctk.CTkFrame(self, corner_radius=10)
        self.controls.pack(fill="x", padx=20, pady=(2, 6))

        row1 = ctk.CTkFrame(self.controls, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(row1, text="Engine").pack(side="left")
        self.engine_var = ctk.StringVar(value="edge")
        ctk.CTkOptionMenu(
            row1, values=["edge", "offline"], variable=self.engine_var,
            width=100, command=self._on_engine_change,
        ).pack(side="left", padx=(6, 10))

        ctk.CTkLabel(row1, text="Voice lang").pack(side="left")
        self.voice_filter_var = ctk.StringVar(value="all")
        self.voice_filter_menu = ctk.CTkOptionMenu(
            row1, values=["all", "en", "sv", "de", "fr", "es"],
            variable=self.voice_filter_var, width=80,
            command=lambda _v: self._on_voice_filter_change(),
        )
        self.voice_filter_menu.pack(side="left", padx=(6, 10))

        ctk.CTkLabel(row1, text="OCR").pack(side="left")
        self.lang_var = ctk.StringVar(value="en")
        ctk.CTkOptionMenu(
            row1, values=OCR_LANG_CHOICES, variable=self.lang_var, width=70,
            command=lambda _v: self._on_lang_change(),
        ).pack(side="left", padx=(6, 10))

        ctk.CTkLabel(row1, text="Theme").pack(side="left")
        self.theme_var = ctk.StringVar(value="dark")
        ctk.CTkOptionMenu(
            row1, values=["dark", "light"], variable=self.theme_var, width=90,
            command=self._on_theme_change,
        ).pack(side="left", padx=(6, 0))

        row2 = ctk.CTkFrame(self.controls, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row2, text="Voice").pack(side="left")
        self.voice_var = ctk.StringVar(value="")
        self.voice_menu = ctk.CTkComboBox(
            row2, values=["Loading..."], variable=self.voice_var, width=420,
            command=lambda _v: self._persist_from_widgets(),
        )
        self.voice_menu.pack(side="left", padx=(6, 8))
        ctk.CTkButton(row2, text="Preview", width=80, command=self.preview_voice).pack(side="left")
        ctk.CTkButton(row2, text="★ Fav", width=70, command=self.toggle_favorite).pack(
            side="left", padx=(6, 0)
        )

        row3 = ctk.CTkFrame(self.controls, fg_color="transparent")
        row3.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row3, text="Rate").pack(side="left")
        self.rate_slider = ctk.CTkSlider(
            row3, from_=80, to=260, number_of_steps=36, command=self._on_rate_change, width=170
        )
        self.rate_slider.pack(side="left", padx=(6, 6))
        self.rate_label = ctk.CTkLabel(row3, text="160", width=36)
        self.rate_label.pack(side="left")
        ctk.CTkLabel(row3, text="Vol").pack(side="left", padx=(12, 0))
        self.volume_slider = ctk.CTkSlider(
            row3, from_=0, to=1, number_of_steps=20, command=self._on_volume_change, width=120
        )
        self.volume_slider.pack(side="left", padx=(6, 6))
        self.volume_label = ctk.CTkLabel(row3, text="100%", width=44)
        self.volume_label.pack(side="left")
        ctk.CTkLabel(row3, text="Size").pack(side="left", padx=(12, 0))
        self.font_slider = ctk.CTkSlider(
            row3, from_=14, to=36, number_of_steps=22, command=self._on_font_change, width=110
        )
        self.font_slider.pack(side="left", padx=(6, 6))
        self.font_label = ctk.CTkLabel(row3, text="18", width=30)
        self.font_label.pack(side="left")

        row4 = ctk.CTkFrame(self.controls, fg_color="transparent")
        row4.pack(fill="x", padx=12, pady=4)
        self.auto_speak_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            row4, text="Auto-speak", variable=self.auto_speak_var,
            command=self._persist_from_widgets,
        ).pack(side="left")
        self.highlight_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            row4, text="Highlight", variable=self.highlight_var,
            command=self._persist_from_widgets,
        ).pack(side="left", padx=(12, 0))
        self.simple_mode_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            row4, text="Simple mode", variable=self.simple_mode_var,
            command=self._on_simple_mode_toggle,
        ).pack(side="left", padx=(12, 0))
        self.quiet_mode_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            row4, text="Quiet (tray after speak)", variable=self.quiet_mode_var,
            command=self._persist_from_widgets,
        ).pack(side="left", padx=(12, 0))
        self.autostart_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            row4, text="Start with Windows", variable=self.autostart_var,
            command=self._on_autostart_toggle,
        ).pack(side="left", padx=(12, 0))

        row5 = ctk.CTkFrame(self.controls, fg_color="transparent")
        row5.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row5, text="Profile").pack(side="left")
        self.profile_var = ctk.StringVar(value="(none)")
        self.profile_menu = ctk.CTkOptionMenu(
            row5, values=["(none)"], variable=self.profile_var, width=200,
            command=self._on_profile_pick,
        )
        self.profile_menu.pack(side="left", padx=(6, 6))
        ctk.CTkButton(row5, text="Save profile", width=110, command=self.save_current_profile).pack(
            side="left"
        )
        ctk.CTkButton(row5, text="Delete", width=70, command=self.delete_current_profile).pack(
            side="left", padx=(6, 0)
        )

        row6 = ctk.CTkFrame(self.controls, fg_color="transparent")
        row6.pack(fill="x", padx=12, pady=(4, 10))
        ctk.CTkLabel(row6, text="History").pack(side="left")
        self.history_var = ctk.StringVar(value="(empty)")
        self.history_menu = ctk.CTkOptionMenu(
            row6, values=["(empty)"], variable=self.history_var, width=300,
            command=self._on_history_pick,
        )
        self.history_menu.pack(side="left", padx=(6, 8))
        ctk.CTkButton(row6, text="Apply hotkeys", width=120, command=self._apply_hotkeys).pack(
            side="left"
        )
        ctk.CTkButton(row6, text="Remember pos", width=110, command=self.remember_position).pack(
            side="left", padx=(8, 0)
        )

        self.hotkey_hint = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12), anchor="w")
        self.hotkey_hint.pack(fill="x", padx=22, pady=(0, 2))
        self.status_label = ctk.CTkLabel(self, text="Ready", font=ctk.CTkFont(size=13), anchor="w")
        self.status_label.pack(fill="x", padx=22, pady=(0, 12))

    def _apply_settings_to_widgets(self) -> None:
        s = self.settings
        self.engine_var.set(s.get("engine", "edge") if s.get("engine") in ("edge", "offline") else "edge")
        self.voice_filter_var.set(str(s.get("voice_filter", "all")))
        self.rate_slider.set(float(s.get("rate", 160)))
        self.rate_label.configure(text=str(int(self.rate_slider.get())))
        self.volume_slider.set(float(s.get("volume", 1.0)))
        self.volume_label.configure(text=f"{int(self.volume_slider.get() * 100)}%")
        self.font_slider.set(float(s.get("font_size", 18)))
        self.font_label.configure(text=str(int(self.font_slider.get())))
        self.auto_speak_var.set(bool(s.get("auto_speak", True)))
        self.highlight_var.set(bool(s.get("word_highlight", True)))
        self.simple_mode_var.set(bool(s.get("simple_mode", False)))
        self.quiet_mode_var.set(bool(s.get("quiet_mode", False)))
        self.autostart_var.set(bool(s.get("autostart", False)) or autostart.is_enabled())
        lang = str(s.get("ocr_lang", "en"))
        self.lang_var.set(lang if lang in OCR_LANG_CHOICES else "en")
        theme = str(s.get("theme", "dark"))
        self.theme_var.set(theme if theme in ("dark", "light") else "dark")
        active = str(s.get("active_profile", "") or "(none)")
        self.profile_var.set(active)
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
        if not self.highlight_var.get():
            return

        def _apply() -> None:
            try:
                self._raw_text.tag_remove("highlight", "1.0", "end")
                self._raw_text.tag_add("highlight", f"1.0+{start}c", f"1.0+{end}c")
                self._raw_text.see(f"1.0+{start}c")
                self._sentence_cursor = start
                self._maybe_autosave_memory(start)
            except Exception:
                pass

        self._queue_call(_apply)

    def _maybe_autosave_memory(self, offset: int) -> None:
        text = self.get_preview_text()
        if not text.strip():
            return
        # Throttle disk writes: every ~80 characters of progress
        last = getattr(self, "_last_memory_offset", -9999)
        if abs(offset - last) < 80:
            return
        self._last_memory_offset = offset
        try:
            save_memory(
                text,
                offset,
                source=self._current_source,
                path=self._current_path,
            )
        except Exception:
            pass

    # ---- settings ----
    def _selected_voice_id(self) -> str:
        label = self.voice_var.get()
        # strip favorite star prefix
        if label.startswith("★ "):
            label = label[2:]
        return self._voice_map.get(label, "") or self._voice_map.get(self.voice_var.get(), "")

    def _persist_from_widgets(self) -> None:
        self.settings["engine"] = self.engine_var.get()
        self.settings["voice_filter"] = self.voice_filter_var.get()
        self.settings["rate"] = int(self.rate_slider.get())
        self.settings["volume"] = float(self.volume_slider.get())
        self.settings["font_size"] = int(self.font_slider.get())
        self.settings["auto_speak"] = bool(self.auto_speak_var.get())
        self.settings["word_highlight"] = bool(self.highlight_var.get())
        self.settings["simple_mode"] = bool(self.simple_mode_var.get())
        self.settings["quiet_mode"] = bool(self.quiet_mode_var.get())
        self.settings["autostart"] = bool(self.autostart_var.get())
        self.settings["ocr_lang"] = self.lang_var.get()
        self.settings["theme"] = self.theme_var.get()
        self.settings["active_profile"] = self.profile_var.get()
        voice_id = self._selected_voice_id()
        if self.settings["engine"] == "edge":
            if voice_id:
                self.settings["edge_voice"] = voice_id
        else:
            self.settings["offline_voice"] = voice_id
        save_settings(self.settings)

    def _on_engine_change(self, _value: str) -> None:
        self._persist_from_widgets()
        self._refresh_voices()

    def _on_voice_filter_change(self) -> None:
        self._persist_from_widgets()
        self._refresh_voices()

    def _on_theme_change(self, value: str) -> None:
        self._apply_theme(value)
        self._persist_from_widgets()
        self._set_status(f"Theme: {value}")

    def _on_rate_change(self, value: float) -> None:
        self.rate_label.configure(text=str(int(value)))
        self.tts.set_rate(int(value))
        self._persist_from_widgets()

    def _on_volume_change(self, value: float) -> None:
        self.volume_label.configure(text=f"{int(float(value) * 100)}%")
        self._persist_from_widgets()

    def _on_font_change(self, value: float) -> None:
        self.font_label.configure(text=str(int(value)))
        self._update_text_font()
        self._persist_from_widgets()

    def _update_text_font(self) -> None:
        self.text_box.configure(
            font=ctk.CTkFont(family="Consolas", size=int(self.font_slider.get()))
        )

    def _on_lang_change(self) -> None:
        self._persist_from_widgets()
        # Align voice filter with OCR language when useful
        lang = self.lang_var.get()
        if self.engine_var.get() == "edge" and lang:
            self.voice_filter_var.set(lang)
            self.settings["voice_filter"] = lang
            preferred = self.tts.prefer_voice_for_lang(lang, engine="edge")
            if preferred:
                self.settings["edge_voice"] = preferred
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
            self.geometry("780x520")
        else:
            self.controls.pack(fill="x", padx=20, pady=(2, 6))
            self.hotkey_hint.pack(fill="x", padx=22, pady=(0, 2))
            self.status_label.pack_forget()
            self.status_label.pack(fill="x", padx=22, pady=(0, 12))
            self.geometry("820x760")

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

    def _favorite_labels(self) -> list[tuple[str, str]]:
        """Return (display_label, voice_id) for favorites matching current engine."""
        engine = self.engine_var.get()
        out: list[tuple[str, str]] = []
        for item in self.settings.get("favorite_voices", []):
            if not isinstance(item, dict):
                continue
            if item.get("engine") != engine:
                continue
            vid = str(item.get("id", ""))
            label = str(item.get("label", vid))
            if vid:
                out.append((label, vid))
        return out

    def toggle_favorite(self) -> None:
        voice_id = self._selected_voice_id()
        label = self.voice_var.get()
        if label.startswith("★ "):
            label = label[2:]
        if not voice_id:
            self._set_status("Pick a voice first")
            return
        engine = self.engine_var.get()
        favs: list[dict[str, Any]] = list(self.settings.get("favorite_voices", []))
        existing = next(
            (i for i, f in enumerate(favs) if f.get("engine") == engine and f.get("id") == voice_id),
            None,
        )
        if existing is not None:
            favs.pop(existing)
            self._set_status("Removed favorite")
        else:
            favs.insert(0, {"engine": engine, "id": voice_id, "label": label})
            favs = favs[:12]
            self._set_status("Saved favorite")
        self.settings["favorite_voices"] = favs
        save_settings(self.settings)
        self._refresh_voices()

    def preview_voice(self) -> None:
        self._persist_from_widgets()
        engine = self.engine_var.get()
        voice_id = self._selected_voice_id()
        sample = (
            "Hej, det här är en förhandsgranskning av rösten."
            if self.lang_var.get() == "sv"
            else "Hello, this is a preview of the selected voice."
        )
        self._set_status("Previewing voice...")
        self.tts.speak(
            sample,
            engine=engine,
            rate=int(self.settings.get("rate", 160)),
            volume=float(self.settings.get("volume", 1.0)),
            voice_id=voice_id,
            highlight=False,
        )

    def _refresh_voices(self) -> None:
        self.voice_menu.configure(values=["Loading..."])
        self.voice_var.set("Loading...")
        engine = self.engine_var.get()
        filt = self.voice_filter_var.get() or "all"

        def _load() -> None:
            voice_map: dict[str, str] = {}
            labels: list[str] = []
            selected = ""
            try:
                if engine == "edge":
                    # Refresh locale list occasionally
                    locales = self.tts.list_edge_locales_sync()
                    voices = self.tts.list_edge_voices_sync(filt)
                    for label, vid in self._favorite_labels():
                        starred = f"★ {label}"
                        voice_map[starred] = vid
                        voice_map[label] = vid
                        labels.append(starred)
                    for voice in voices:
                        label = voice["name"]
                        if label in voice_map:
                            continue
                        voice_map[label] = voice["id"]
                        labels.append(label)
                    wanted = self.settings.get("edge_voice", "")
                    selected = next(
                        (lbl for lbl, vid in voice_map.items() if vid == wanted and not lbl.startswith("★ ")),
                        labels[0] if labels else "",
                    )
                    # Prefer showing starred version if favorited
                    for lbl in labels:
                        if lbl.startswith("★ ") and voice_map.get(lbl) == wanted:
                            selected = lbl
                            break

                    def _apply_locales() -> None:
                        current = list(self.voice_filter_menu.cget("values") or [])
                        if locales and locales != current:
                            self.voice_filter_menu.configure(values=locales)
                            if self.voice_filter_var.get() not in locales:
                                self.voice_filter_var.set("all")

                    self._queue_call(_apply_locales)
                else:
                    labels = ["(default)"]
                    voice_map["(default)"] = ""
                    for label, vid in self._favorite_labels():
                        starred = f"★ {label}"
                        voice_map[starred] = vid
                        labels.append(starred)
                    for voice in self.tts.list_offline_voices():
                        label = voice["name"]
                        if label in voice_map:
                            label = f'{voice["name"]} [{voice["id"][-12:]}]'
                        voice_map[label] = voice["id"]
                        labels.append(label)
                    wanted = self.settings.get("offline_voice", "")
                    selected = next(
                        (lbl for lbl, vid in voice_map.items() if vid == wanted and not lbl.startswith("★ ")),
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

    def _refresh_profiles_menu(self) -> None:
        profiles = self.settings.get("profiles", [])
        names = [str(p.get("name", "")) for p in profiles if p.get("name")]
        if not names:
            names = ["(none)"]
        current = self.profile_var.get()
        self.profile_menu.configure(values=names)
        if current in names:
            self.profile_var.set(current)
        elif self.settings.get("active_profile") in names:
            self.profile_var.set(str(self.settings.get("active_profile")))
        else:
            self.profile_var.set(names[0])

    def _on_profile_pick(self, name: str) -> None:
        profile = find_profile(self.settings.get("profiles", []), name)
        if not profile:
            return
        self.settings = apply_profile(self.settings, profile)
        save_settings(self.settings)
        self._apply_settings_to_widgets()
        self._refresh_voices()
        self._set_status(f"Profile: {name}")

    def save_current_profile(self) -> None:
        self._persist_from_widgets()
        name = self.profile_var.get().strip()
        if not name or name == "(none)":
            name = "Custom"
        # Ask for a name via simple dialog
        dialog = ctk.CTkInputDialog(text="Profile name:", title="Save profile")
        typed = dialog.get_input()
        if typed is not None and typed.strip():
            name = typed.strip()
        profile = snapshot_from_settings(self.settings, name)
        self.settings["profiles"] = upsert_profile(self.settings.get("profiles", []), profile)
        self.settings["active_profile"] = name
        save_settings(self.settings)
        self._refresh_profiles_menu()
        self.profile_var.set(name)
        self._set_status(f"Saved profile: {name}")

    def delete_current_profile(self) -> None:
        name = self.profile_var.get().strip()
        if not name or name == "(none)":
            self._set_status("No profile selected")
            return
        self.settings["profiles"] = delete_profile(self.settings.get("profiles", []), name)
        self.settings["active_profile"] = ""
        save_settings(self.settings)
        self._refresh_profiles_menu()
        self._set_status(f"Deleted profile: {name}")

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

    # ---- capture / pdf ----
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

    def open_pdf(self) -> None:
        path = filedialog.askopenfilename(
            title="Open PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return
        self._set_status("Reading PDF...")
        lang = self.lang_var.get() or "en"
        max_pages = int(self.settings.get("pdf_max_pages", 40) or 40)

        def _run() -> None:
            try:
                text = extract_pdf_text(
                    path,
                    max_pages=max_pages,
                    ocr_lang=lang,
                    on_progress=lambda msg: self._queue_status(msg),
                )
            except PdfError as exc:
                self._queue_call(lambda: self._on_text_ready(None, str(exc), "pdf", path))
                return
            except Exception as exc:  # noqa: BLE001
                self._queue_call(
                    lambda: self._on_text_ready(None, f"PDF error: {exc}", "pdf", path)
                )
                return
            self._queue_call(lambda: self._on_text_ready(text, None, "pdf", path))

        threading.Thread(target=_run, daemon=True).start()

    def _set_preview_text(self, text: str, *, cursor: int = 0) -> None:
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", text)
        self._sentence_cursor = max(0, min(cursor, len(text)))
        try:
            self._raw_text.tag_remove("highlight", "1.0", "end")
            if cursor > 0:
                self._raw_text.mark_set("insert", f"1.0+{cursor}c")
                self._raw_text.see(f"1.0+{cursor}c")
        except Exception:
            pass

    def _on_text_ready(
        self,
        text: str | None,
        error: str | None,
        source: str,
        path: str = "",
    ) -> None:
        self._busy = False
        if error:
            self._set_status(error)
            return
        assert text is not None
        self._current_source = source
        self._current_path = path
        self._set_preview_text(text)
        self._history = add_history(text, source=source)
        self._refresh_history_menu()
        try:
            save_memory(text, 0, source=source, path=path)
        except Exception:
            pass
        self._set_status("Text ready")
        if self.auto_speak_var.get():
            self.read_text()
            if self.quiet_mode_var.get():
                self.after(400, self.hide_to_tray)

    def remember_position(self) -> None:
        text = self.get_preview_text()
        if not text.strip():
            self._set_status("Nothing to remember")
            return
        offset = self._cursor_index()
        save_memory(text, offset, source=self._current_source, path=self._current_path)
        self._set_status(f"Saved position at character {offset}")

    def continue_reading(self) -> None:
        mem = load_memory()
        if not mem or not mem.get("text"):
            self._set_status("No saved position — use Remember pos or Stop while reading")
            return
        text = str(mem["text"])
        offset = int(mem.get("offset", 0) or 0)
        self._current_source = str(mem.get("source", "") or "")
        self._current_path = str(mem.get("path", "") or "")
        self._set_preview_text(text, cursor=offset)
        self._persist_from_widgets()
        hit = sentence_at_or_after(text, offset)
        if not hit:
            self._set_status("Saved position is at the end")
            return
        start, _, _ = hit
        self._set_status(f"Continuing from character {start}")
        self._speak_range(text, start, len(text))

    def _stop_and_remember(self) -> None:
        text = self.get_preview_text()
        if text.strip():
            try:
                save_memory(
                    text,
                    self._sentence_cursor,
                    source=self._current_source,
                    path=self._current_path,
                )
            except Exception:
                pass
        self.tts.stop()
        self._set_status("Stopped — position saved (Continue to resume)")

    def get_preview_text(self) -> str:
        return self.text_box.get("1.0", "end-1c")

    def _cursor_index(self) -> int:
        try:
            return len(self.text_box.get("1.0", "insert"))
        except Exception:
            return self._sentence_cursor

    def _speak_range(self, text: str, start: int, end: int) -> None:
        chunk = text[start:end].strip()
        if not chunk:
            self._set_status("Nothing to read here")
            return
        self._sentence_cursor = start
        self.pause_btn.configure(text="Pause")
        engine = str(self.settings.get("engine", "edge"))
        voice_id = (
            str(self.settings.get("edge_voice", "en-US-JennyNeural"))
            if engine == "edge"
            else str(self.settings.get("offline_voice", ""))
        )

        def _word(s: int, e: int, w: str) -> None:
            self._on_word(start + s, start + e, w)

        old = self.tts._on_word
        self.tts._on_word = _word

        def _done() -> None:
            self.tts._on_word = old
            self._queue_call(lambda: self.pause_btn.configure(text="Pause"))

        self.tts.speak(
            chunk,
            engine=engine,
            rate=int(self.settings.get("rate", 160)),
            volume=float(self.settings.get("volume", 1.0)),
            voice_id=voice_id,
            highlight=bool(self.highlight_var.get()),
            on_done=_done,
        )

    def read_text(self) -> None:
        self._persist_from_widgets()
        text = self.get_preview_text().strip()
        if not text:
            self._set_status("Nothing to read — capture text first")
            return
        self._sentence_cursor = 0
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

    def read_from_cursor(self) -> None:
        self._persist_from_widgets()
        text = self.get_preview_text()
        idx = self._cursor_index()
        hit = sentence_at_or_after(text, idx)
        if not hit:
            self._set_status("No sentence found")
            return
        start, end, _ = hit
        # Read from this sentence to the end
        self._speak_range(text, start, len(text))

    def read_next_sentence(self) -> None:
        self._persist_from_widgets()
        text = self.get_preview_text()
        hit = next_sentence_after(text, self._sentence_cursor)
        if not hit:
            # If at start, read first sentence
            hit = sentence_at_or_after(text, 0)
        if not hit:
            self._set_status("No next sentence")
            return
        start, end, _ = hit
        self._speak_range(text, start, end)

    def _toggle_pause(self) -> None:
        if self.tts.is_paused():
            self.tts.resume()
            self.pause_btn.configure(text="Pause")
        else:
            self.tts.pause()
            self.pause_btn.configure(text="Resume")
            text = self.get_preview_text()
            if text.strip():
                try:
                    save_memory(
                        text,
                        self._sentence_cursor,
                        source=self._current_source,
                        path=self._current_path,
                    )
                except Exception:
                    pass
