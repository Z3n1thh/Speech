"""Non-GUI smoke tests for Screen Read-Aloud."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from app import autostart
from app.config import DEFAULTS, load_settings, save_settings
from app.history import add_history, load_history
from app.ocr import preprocess_image, recognize_image
from app.tts import TextToSpeech, tokenize


def test_tokenize() -> None:
    tokens = tokenize("Hello world")
    assert [t[2] for t in tokens] == ["Hello", "world"]
    assert tokens[0][0] == 0
    print("ok tokenize")


def test_settings_roundtrip() -> None:
    settings = load_settings()
    assert "hotkey_region" in settings
    assert settings.get("engine") in ("edge", "offline")
    settings["rate"] = 170
    save_settings(settings)
    again = load_settings()
    assert again["rate"] == 170
    print("ok settings")


def test_history() -> None:
    items = add_history("Detta ar ett test", source="test")
    assert items
    assert load_history()[0]["text"] == "Detta ar ett test"
    print("ok history")


def test_ocr_preprocess_and_recognize() -> None:
    img = Image.new("RGB", (640, 160), "white")
    draw = ImageDraw.Draw(img)
    draw.text((30, 50), "Hello reading helper", fill="black")
    processed = preprocess_image(img)
    assert processed.size[0] >= img.size[0]
    text = recognize_image(img, lang="en")
    assert "Hello" in text or "reading" in text.lower()
    print("ok ocr:", repr(text))


def test_tts_voices_and_speak() -> None:
    spoken: list[str] = []
    tts = TextToSpeech(on_word=lambda _s, _e, w: spoken.append(w))
    offline = tts.list_offline_voices()
    assert isinstance(offline, list)
    edge = tts.list_edge_voices_sync("en")
    assert edge, "Expected Edge neural voices"
    print("ok edge voices:", len(edge))
    done = {"yes": False}

    def _done() -> None:
        done["yes"] = True

    tts.speak("One two", engine="offline", rate=200, highlight=True, on_done=_done)
    import time

    for _ in range(80):
        if done["yes"]:
            break
        time.sleep(0.1)
    assert done["yes"], "TTS did not finish"
    assert spoken, "No words spoken"
    print("ok tts words:", spoken)


def test_autostart_toggle() -> None:
    before = autostart.is_enabled()
    try:
        autostart.set_enabled(True)
        assert autostart.is_enabled() is True
        autostart.set_enabled(False)
        assert autostart.is_enabled() is False
    finally:
        autostart.set_enabled(before)
    print("ok autostart")


def test_ui_import() -> None:
    from app.ui import App

    assert App is not None
    print("ok ui import")


if __name__ == "__main__":
    test_tokenize()
    test_settings_roundtrip()
    test_history()
    test_ocr_preprocess_and_recognize()
    test_tts_voices_and_speak()
    test_autostart_toggle()
    test_ui_import()
    print("ALL TESTS PASSED")
