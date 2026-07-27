"""Offline Windows SAPI TTS via pyttsx3 (free, local, open-source library)."""

from __future__ import annotations

import re
import threading
from typing import Callable

StatusCallback = Callable[[str], None]
WordCallback = Callable[[int, int, str], None]


def tokenize(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group()) for m in re.finditer(r"\S+", text)]


class TextToSpeech:
    def __init__(
        self,
        on_status: StatusCallback | None = None,
        on_word: WordCallback | None = None,
    ) -> None:
        self._on_status = on_status or (lambda _msg: None)
        self._on_word = on_word
        self._stop_flag = threading.Event()
        self._paused = threading.Event()
        self._worker: threading.Thread | None = None
        self._rate = 160
        self._volume = 1.0
        self._voice_id = ""
        self._rate_lock = threading.Lock()

    def _status(self, message: str) -> None:
        self._on_status(message)

    def list_voices(self) -> list[dict[str, str]]:
        import pyttsx3

        engine = pyttsx3.init()
        try:
            voices = engine.getProperty("voices") or []
            return [
                {
                    "id": getattr(voice, "id", ""),
                    "name": getattr(voice, "name", "Unknown"),
                }
                for voice in voices
            ]
        finally:
            try:
                engine.stop()
            except Exception:
                pass

    def prefer_voice_for_lang(self, lang: str) -> str:
        """Pick a voice id matching language code when possible (e.g. sv, en)."""
        lang = (lang or "en").lower()
        needles = {
            "sv": ("swedish", "svenska", "sv-", "sv_"),
            "en": ("english", "en-", "en_"),
        }.get(lang, (lang,))
        for voice in self.list_voices():
            blob = f'{voice["name"]} {voice["id"]}'.lower()
            if any(n in blob for n in needles):
                return voice["id"]
        return ""

    def stop(self, *, silent: bool = False) -> None:
        self._stop_flag.set()
        self._paused.clear()
        if not silent:
            self._status("Stopped")

    def pause(self) -> None:
        self._paused.set()
        self._status("Paused")

    def resume(self) -> None:
        if self._paused.is_set():
            self._paused.clear()
            self._status("Speaking...")

    def is_paused(self) -> bool:
        return self._paused.is_set()

    def is_busy(self) -> bool:
        worker = self._worker
        return worker is not None and worker.is_alive()

    def set_rate(self, rate: int) -> None:
        with self._rate_lock:
            self._rate = int(rate)

    def adjust_rate(self, delta: int) -> int:
        with self._rate_lock:
            self._rate = max(80, min(260, self._rate + int(delta)))
            return self._rate

    def speak(
        self,
        text: str,
        *,
        rate: int = 160,
        volume: float = 1.0,
        voice_id: str = "",
        highlight: bool = True,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        text = (text or "").strip()
        if not text:
            self._status("Nothing to read")
            return

        self.stop(silent=True)
        self._stop_flag.clear()
        self._paused.clear()
        with self._rate_lock:
            self._rate = int(rate)
        self._volume = max(0.0, min(1.0, float(volume)))
        self._voice_id = voice_id or ""

        tokens = tokenize(text) if highlight else [(0, len(text), text)]

        def _run() -> None:
            try:
                self._speak_tokens(tokens)
            except Exception as exc:  # noqa: BLE001
                if not self._stop_flag.is_set():
                    self._status(f"Speech failed: {exc}")
            finally:
                if on_done:
                    on_done()

        self._worker = threading.Thread(target=_run, daemon=True)
        self._worker.start()

    def _speak_tokens(self, tokens: list[tuple[int, int, str]]) -> None:
        import pyttsx3

        self._status("Speaking...")
        engine = pyttsx3.init()
        try:
            engine.setProperty("volume", self._volume)
            if self._voice_id:
                engine.setProperty("voice", self._voice_id)

            for start, end, word in tokens:
                while self._paused.is_set() and not self._stop_flag.is_set():
                    threading.Event().wait(0.05)
                if self._stop_flag.is_set():
                    break

                if self._on_word:
                    self._on_word(start, end, word)

                with self._rate_lock:
                    engine.setProperty("rate", self._rate)

                engine.say(word)
                engine.startLoop(False)
                while engine.isBusy():
                    if self._stop_flag.is_set():
                        engine.stop()
                        break
                    # Allow pause mid-word by stopping current utterance
                    if self._paused.is_set():
                        engine.stop()
                        break
                    engine.iterate()
                try:
                    engine.endLoop()
                except Exception:
                    pass

                if self._stop_flag.is_set():
                    break
                # If paused mid-word, wait then re-speak same word
                if self._paused.is_set():
                    while self._paused.is_set() and not self._stop_flag.is_set():
                        threading.Event().wait(0.05)
                    if self._stop_flag.is_set():
                        break
                    # re-queue current word once after resume
                    engine.say(word)
                    engine.startLoop(False)
                    while engine.isBusy():
                        if self._stop_flag.is_set() or self._paused.is_set():
                            engine.stop()
                            break
                        engine.iterate()
                    try:
                        engine.endLoop()
                    except Exception:
                        pass

            if not self._stop_flag.is_set() and not self._paused.is_set():
                self._status("Done")
        finally:
            try:
                engine.stop()
            except Exception:
                pass
