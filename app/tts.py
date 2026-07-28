"""TTS: offline Windows SAPI (pyttsx3) + optional free Edge neural voices."""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
import threading
import time
from typing import Callable

StatusCallback = Callable[[str], None]
WordCallback = Callable[[int, int, str], None]


def tokenize(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group()) for m in re.finditer(r"\S+", text)]


def rate_to_edge(rate: int) -> str:
    pct = int((int(rate) - 160) / 160 * 100)
    pct = max(-50, min(100, pct))
    return f"{'+' if pct >= 0 else ''}{pct}%"


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
        self._engine_name = "edge"
        self._rate_lock = threading.Lock()
        self._wmp = None
        self._temp_file: str | None = None
        self._session = 0
        self._speak_lock = threading.Lock()

    def _status(self, message: str) -> None:
        self._on_status(message)

    def list_offline_voices(self) -> list[dict[str, str]]:
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

    def list_voices(self) -> list[dict[str, str]]:
        return self.list_offline_voices()

    def list_edge_voices_sync(self, lang: str = "all") -> list[dict[str, str]]:
        import edge_tts

        lang_code = (lang or "all").lower().strip()

        async def _load() -> list[dict[str, str]]:
            voices = await edge_tts.list_voices()
            filtered = []
            for voice in voices:
                short = str(voice.get("ShortName", ""))
                locale = str(voice.get("Locale", ""))
                friendly = str(voice.get("FriendlyName", ""))
                short_l = short.lower()
                locale_l = locale.lower()
                if lang_code in ("", "all", "*"):
                    match = True
                else:
                    match = locale_l.startswith(lang_code) or short_l.startswith(
                        f"{lang_code}-"
                    )
                if not match:
                    continue
                gender = voice.get("Gender", "")
                label = friendly or f"{short} ({locale}, {gender})"
                filtered.append(
                    {
                        "id": short,
                        "name": label,
                        "locale": locale,
                        "gender": str(gender),
                    }
                )
            if not filtered and lang_code not in ("", "all", "*"):
                for voice in voices:
                    short = str(voice.get("ShortName", ""))
                    locale = str(voice.get("Locale", ""))
                    if short.lower().startswith("en-"):
                        filtered.append(
                            {
                                "id": short,
                                "name": str(
                                    voice.get("FriendlyName")
                                    or f"{short} ({locale})"
                                ),
                                "locale": locale,
                                "gender": str(voice.get("Gender", "")),
                            }
                        )
            filtered.sort(key=lambda v: (0 if "Neural" in v["id"] else 1, v["name"]))
            return filtered

        try:
            return asyncio.run(_load())
        except Exception:
            if lang_code.startswith("sv"):
                return [
                    {
                        "id": "sv-SE-SofieNeural",
                        "name": "Microsoft Sofie Online (Natural) - Swedish (Sweden)",
                        "locale": "sv-SE",
                        "gender": "Female",
                    },
                    {
                        "id": "sv-SE-MattiasNeural",
                        "name": "Microsoft Mattias Online (Natural) - Swedish (Sweden)",
                        "locale": "sv-SE",
                        "gender": "Male",
                    },
                ]
            return [
                {
                    "id": "en-US-JennyNeural",
                    "name": "Microsoft Jenny Online (Natural) - English (United States)",
                    "locale": "en-US",
                    "gender": "Female",
                },
                {
                    "id": "en-US-GuyNeural",
                    "name": "Microsoft Guy Online (Natural) - English (United States)",
                    "locale": "en-US",
                    "gender": "Male",
                },
            ]

    def list_edge_locales_sync(self) -> list[str]:
        voices = self.list_edge_voices_sync("all")
        locales = sorted(
            {
                str(v.get("locale", "")).split("-")[0].lower()
                for v in voices
                if v.get("locale")
            }
        )
        return ["all", *locales]

    def prefer_voice_for_lang(self, lang: str, engine: str = "offline") -> str:
        lang = (lang or "en").lower()
        if engine == "edge":
            voices = self.list_edge_voices_sync(lang)
            return voices[0]["id"] if voices else ""
        needles = {
            "sv": ("swedish", "svenska", "sv-", "sv_"),
            "en": ("english", "en-", "en_"),
        }.get(lang, (lang,))
        for voice in self.list_offline_voices():
            blob = f'{voice["name"]} {voice["id"]}'.lower()
            if any(n in blob for n in needles):
                return voice["id"]
        return ""

    def stop(self, *, silent: bool = False) -> None:
        with self._speak_lock:
            self._session += 1
            self._stop_flag.set()
            self._paused.clear()
            self._stop_wmp()
        if not silent:
            self._status("Stopped")

    def pause(self) -> None:
        if self._engine_name == "edge" and self._wmp is not None:
            try:
                self._wmp.controls.pause()
                self._paused.set()
                self._status("Paused")
                return
            except Exception:
                pass
        self._paused.set()
        self._status("Paused")

    def resume(self) -> None:
        if self._engine_name == "edge" and self._wmp is not None and self._paused.is_set():
            try:
                self._wmp.controls.play()
                self._paused.clear()
                self._status("Speaking...")
                return
            except Exception:
                pass
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
        engine: str = "edge",
        rate: int = 160,
        volume: float = 1.0,
        voice_id: str = "",
        highlight: bool = True,
        start_offset: int = 0,
        on_progress: Callable[[int], None] | None = None,
        on_done: Callable[[], None] | None = None,
    ) -> bool:
        """Start speaking. Returns False if already busy (ignored)."""
        text = text or ""
        if not text.strip():
            self._status("Nothing to read")
            return False

        start_offset = max(0, min(int(start_offset), len(text)))

        with self._speak_lock:
            # Only one playback at a time — ignore extra clicks while busy
            if self.is_busy() and not self._stop_flag.is_set():
                self._status("Already reading — press Stop first")
                return False

            self._session += 1
            session = self._session
            self._stop_flag.set()
            self._stop_wmp()
            old = self._worker

        if old is not None and old.is_alive() and old is not threading.current_thread():
            old.join(timeout=0.4)

        with self._speak_lock:
            if session != self._session:
                return False
            self._stop_flag.clear()
            self._paused.clear()
            with self._rate_lock:
                self._rate = int(rate)
            self._volume = max(0.0, min(1.0, float(volume)))
            self._voice_id = voice_id or ""
            self._engine_name = "edge" if engine == "edge" else "offline"
            self._on_progress = on_progress

        def _run() -> None:
            try:
                if session != self._session or self._stop_flag.is_set():
                    return
                if self._engine_name == "edge":
                    self._speak_edge(
                        text,
                        highlight=highlight,
                        session=session,
                        start_offset=start_offset,
                    )
                else:
                    tokens = tokenize(text) if (highlight or on_progress or start_offset) else [
                        (0, len(text), text)
                    ]
                    if start_offset:
                        tokens = [(s, e, w) for s, e, w in tokens if e > start_offset]
                    self._speak_offline_tokens(tokens, session=session)
            except Exception as exc:  # noqa: BLE001
                if session != self._session or self._stop_flag.is_set():
                    return
                if self._engine_name == "edge":
                    self._status(f"Neural voice failed ({exc}); using offline voice")
                    try:
                        tokens = tokenize(text)
                        if start_offset:
                            tokens = [(s, e, w) for s, e, w in tokens if e > start_offset]
                        self._speak_offline_tokens(tokens, session=session)
                    except Exception as offline_exc:  # noqa: BLE001
                        self._status(f"Speech failed: {offline_exc}")
                else:
                    self._status(f"Speech failed: {exc}")
            finally:
                if session == self._session:
                    self._cleanup_temp()
                if on_done and session == self._session:
                    on_done()

        self._worker = threading.Thread(target=_run, daemon=True)
        self._worker.start()
        return True

    def _report_progress(self, offset: int) -> None:
        cb = getattr(self, "_on_progress", None)
        if cb is None:
            return
        try:
            cb(int(offset))
        except Exception:
            pass

    def _speak_offline_tokens(
        self, tokens: list[tuple[int, int, str]], *, session: int
    ) -> None:
        import pyttsx3

        if session != self._session:
            return
        self._status("Speaking (offline)...")
        engine = pyttsx3.init()
        try:
            engine.setProperty("volume", self._volume)
            if self._voice_id:
                engine.setProperty("voice", self._voice_id)

            for start, end, word in tokens:
                if session != self._session or self._stop_flag.is_set():
                    break
                while self._paused.is_set() and not self._stop_flag.is_set():
                    if session != self._session:
                        break
                    time.sleep(0.05)
                if session != self._session or self._stop_flag.is_set():
                    break

                if self._on_word:
                    self._on_word(start, end, word)
                self._report_progress(start)

                with self._rate_lock:
                    engine.setProperty("rate", self._rate)

                engine.say(word)
                engine.startLoop(False)
                while engine.isBusy():
                    if session != self._session or self._stop_flag.is_set() or self._paused.is_set():
                        engine.stop()
                        break
                    engine.iterate()
                try:
                    engine.endLoop()
                except Exception:
                    pass

            if session == self._session and not self._stop_flag.is_set() and not self._paused.is_set():
                self._status("Done")
        finally:
            try:
                engine.stop()
            except Exception:
                pass

    def _stop_wmp(self) -> None:
        if self._wmp is not None:
            try:
                self._wmp.controls.stop()
            except Exception:
                pass
            try:
                self._wmp.close()
            except Exception:
                pass
            self._wmp = None

    def _cleanup_temp(self) -> None:
        if self._temp_file and os.path.exists(self._temp_file):
            try:
                os.remove(self._temp_file)
            except OSError:
                pass
        self._temp_file = None

    def _speak_edge(
        self,
        text: str,
        *,
        highlight: bool,
        session: int,
        start_offset: int = 0,
    ) -> None:
        from app.textutil import split_sentences

        sentences = split_sentences(text)
        if start_offset:
            sentences = [(s, e, t) for s, e, t in sentences if e > start_offset]
        if not sentences:
            chunk = text[start_offset:].strip()
            if not chunk:
                self._status("Nothing left to read")
                return
            sentences = [(start_offset, len(text), chunk)]

        # Sentence-by-sentence so Stop/Continue can remember position
        for index, (start, end, sentence) in enumerate(sentences, start=1):
            if session != self._session or self._stop_flag.is_set():
                break
            while self._paused.is_set() and not self._stop_flag.is_set():
                if session != self._session:
                    return
                time.sleep(0.05)
            if session != self._session or self._stop_flag.is_set():
                break
            if highlight and self._on_word:
                self._on_word(start, end, sentence)
            self._report_progress(start)
            self._status(f"Speaking… {index}/{len(sentences)}")
            self._play_edge_clip(sentence, session=session)
        if session == self._session and not self._stop_flag.is_set():
            self._report_progress(len(text))
            self._status("Done")

    def _play_edge_clip(self, text: str, *, session: int) -> None:
        import edge_tts
        import win32com.client

        if session != self._session or self._stop_flag.is_set():
            return

        voice = self._voice_id or "en-US-JennyNeural"
        with self._rate_lock:
            edge_rate = rate_to_edge(self._rate)

        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        self._cleanup_temp()
        self._temp_file = path

        async def _synthesize() -> None:
            communicate = edge_tts.Communicate(text, voice=voice, rate=edge_rate)
            await communicate.save(path)

        asyncio.run(_synthesize())
        if session != self._session or self._stop_flag.is_set():
            return

        player = win32com.client.Dispatch("WMPlayer.OCX")
        self._wmp = player
        player.settings.volume = int(self._volume * 100)
        player.URL = path
        player.controls.play()
        self._status("Speaking...")

        while True:
            if session != self._session or (self._stop_flag.is_set() and not self._paused.is_set()):
                try:
                    player.controls.stop()
                except Exception:
                    pass
                break
            try:
                state = int(player.playState)
            except Exception:
                break
            if state in (1, 8) and not self._paused.is_set():
                break
            time.sleep(0.05)

        if self._wmp is player:
            self._wmp = None
