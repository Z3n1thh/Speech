"""Dual TTS: offline Windows SAPI (pyttsx3) and optional Edge neural voices."""

from __future__ import annotations

import asyncio
import os
import tempfile
import threading
import time
from typing import Callable


StatusCallback = Callable[[str], None]


class TextToSpeech:
    def __init__(self, on_status: StatusCallback | None = None) -> None:
        self._on_status = on_status or (lambda _msg: None)
        self._stop_flag = threading.Event()
        self._paused = threading.Event()
        self._worker: threading.Thread | None = None
        self._temp_file: str | None = None
        self._engine_name = "offline"
        self._wmp = None

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

    async def list_edge_voices(self, locale_prefix: str = "en") -> list[dict[str, str]]:
        import edge_tts

        voices = await edge_tts.list_voices()
        filtered = [
            {"id": v["ShortName"], "name": f'{v["ShortName"]} ({v.get("Locale", "")})'}
            for v in voices
            if str(v.get("Locale", "")).lower().startswith(locale_prefix.lower())
            or str(v.get("ShortName", "")).lower().startswith(locale_prefix.lower())
        ]
        if not filtered:
            filtered = [
                {
                    "id": v["ShortName"],
                    "name": f'{v["ShortName"]} ({v.get("Locale", "")})',
                }
                for v in voices
            ]
        return filtered

    def list_edge_voices_sync(self, locale_prefix: str = "en") -> list[dict[str, str]]:
        try:
            return asyncio.run(self.list_edge_voices(locale_prefix))
        except Exception:
            return [{"id": "en-US-JennyNeural", "name": "en-US-JennyNeural (en-US)"}]

    def stop(self, *, silent: bool = False) -> None:
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
        self._stop_flag.set()
        self._paused.set()
        self._status("Paused (offline resumes from start)")

    def resume(self) -> None:
        if self._engine_name == "edge" and self._wmp is not None and self._paused.is_set():
            try:
                self._wmp.controls.play()
                self._paused.clear()
                self._status("Speaking...")
                return
            except Exception:
                pass

    def is_busy(self) -> bool:
        worker = self._worker
        return worker is not None and worker.is_alive()

    def speak(
        self,
        text: str,
        *,
        engine: str = "offline",
        rate: int = 160,
        volume: float = 1.0,
        offline_voice: str = "",
        edge_voice: str = "en-US-JennyNeural",
        edge_rate: str = "+0%",
        on_done: Callable[[], None] | None = None,
    ) -> None:
        text = (text or "").strip()
        if not text:
            self._status("Nothing to read")
            return

        self.stop(silent=True)
        self._stop_flag.clear()
        self._paused.clear()
        self._engine_name = "edge" if engine == "edge" else "offline"

        def _run() -> None:
            try:
                if self._engine_name == "edge":
                    self._speak_edge(text, edge_voice, edge_rate, volume)
                else:
                    self._speak_offline(text, rate, volume, offline_voice)
            except Exception as exc:  # noqa: BLE001
                if self._engine_name == "edge" and not self._stop_flag.is_set():
                    self._status(f"Edge TTS failed ({exc}); falling back to offline")
                    try:
                        self._speak_offline(text, rate, volume, offline_voice)
                    except Exception as offline_exc:  # noqa: BLE001
                        self._status(f"Speech failed: {offline_exc}")
                elif not self._stop_flag.is_set():
                    self._status(f"Speech failed: {exc}")
            finally:
                self._cleanup_temp()
                if on_done:
                    on_done()

        self._worker = threading.Thread(target=_run, daemon=True)
        self._worker.start()

    def _speak_offline(
        self, text: str, rate: int, volume: float, voice_id: str
    ) -> None:
        import pyttsx3

        self._status("Speaking (offline)...")
        engine = pyttsx3.init()
        try:
            engine.setProperty("rate", int(rate))
            engine.setProperty("volume", max(0.0, min(1.0, float(volume))))
            if voice_id:
                engine.setProperty("voice", voice_id)

            if self._stop_flag.is_set():
                return

            engine.say(text)
            engine.startLoop(False)
            while engine.isBusy():
                if self._stop_flag.is_set():
                    engine.stop()
                    break
                engine.iterate()
            engine.endLoop()
            if not self._stop_flag.is_set():
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

    def _cleanup_temp(self) -> None:
        if self._temp_file and os.path.exists(self._temp_file):
            try:
                os.remove(self._temp_file)
            except OSError:
                pass
        self._temp_file = None

    def _speak_edge(
        self, text: str, voice: str, rate: str, volume: float
    ) -> None:
        import edge_tts
        import win32com.client

        self._status("Synthesizing (Edge)...")
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        self._temp_file = path

        async def _synthesize() -> None:
            communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
            await communicate.save(path)

        asyncio.run(_synthesize())
        if self._stop_flag.is_set():
            return

        player = win32com.client.Dispatch("WMPlayer.OCX")
        self._wmp = player
        player.settings.volume = int(max(0.0, min(1.0, float(volume))) * 100)
        player.URL = path
        player.controls.play()
        self._status("Speaking (Edge)...")

        # playState: 1=stopped, 2=paused, 3=playing, 6=buffering, 8=mediaended, 9=transitioning, 10=ready
        while True:
            if self._stop_flag.is_set() and not self._paused.is_set():
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

        self._wmp = None
        if not self._stop_flag.is_set():
            self._status("Done")
