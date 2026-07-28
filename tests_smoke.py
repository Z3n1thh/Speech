"""Smoke tests for simplified Screen Read-Aloud v6."""

from __future__ import annotations

from PIL import Image, ImageDraw

from app.memory import clear_memory, has_memory, load_memory, save_memory
from app.config import APP_VERSION, load_settings, save_settings
from app.ocr import recognize_image
from app.tts import TextToSpeech, tokenize


def test_tokenize() -> None:
    assert [t[2] for t in tokenize("Hello world")] == ["Hello", "world"]
    print("ok tokenize")


def test_settings() -> None:
    settings = load_settings()
    assert "volume" in settings
    assert "theme" in settings
    assert "edge_voice" in settings
    assert APP_VERSION.startswith("6.")
    settings["theme"] = "dark"
    save_settings(settings)
    assert load_settings()["theme"] == "dark"
    print("ok settings")


def test_ocr() -> None:
    img = Image.new("RGB", (640, 160), "white")
    ImageDraw.Draw(img).text((30, 50), "Hello reading helper", fill="black")
    text = recognize_image(img, lang="en")
    assert "Hello" in text or "reading" in text.lower()
    print("ok ocr:", repr(text))


def test_speak_ignores_while_busy() -> None:
    done = {"n": 0}
    tts = TextToSpeech()
    started1 = tts.speak(
        "One two three four five",
        engine="offline",
        rate=220,
        highlight=False,
        on_done=lambda: done.__setitem__("n", done["n"] + 1),
    )
    started2 = tts.speak(
        "Should be ignored",
        engine="offline",
        rate=220,
        highlight=False,
        on_done=lambda: done.__setitem__("n", done["n"] + 1),
    )
    assert started1 is True
    assert started2 is False
    import time

    for _ in range(80):
        if done["n"] >= 1 and not tts.is_busy():
            break
        time.sleep(0.1)
    assert done["n"] == 1
    print("ok no echo while busy")


def test_memory_continue() -> None:
    clear_memory()
    assert not has_memory()
    save_memory("One. Two. Three.", offset=5, source="test")
    mem = load_memory()
    assert mem and mem["offset"] == 5 and has_memory()
    clear_memory()
    print("ok memory")


def test_speak_start_offset_progress() -> None:
    progressed: list[int] = []
    done = {"yes": False}
    tts = TextToSpeech()
    text = "Alpha word. Beta word. Gamma word."
    started = tts.speak(
        text,
        engine="offline",
        rate=240,
        highlight=False,
        start_offset=12,
        on_progress=lambda o: progressed.append(o),
        on_done=lambda: done.__setitem__("yes", True),
    )
    assert started
    import time

    for _ in range(100):
        if done["yes"]:
            break
        time.sleep(0.1)
    assert done["yes"]
    assert progressed and min(progressed) >= 12
    print("ok start_offset progress", progressed[:5])


def test_ui_import() -> None:
    from app.ui import App, OptionsWindow
    from app.uninstall import install_dir, launch_uninstall

    assert App is not None and OptionsWindow is not None
    assert install_dir().name == "ScreenReadAloud"
    assert callable(launch_uninstall)
    print("ok ui import")


if __name__ == "__main__":
    test_tokenize()
    test_settings()
    test_memory_continue()
    test_ocr()
    test_speak_ignores_while_busy()
    test_speak_start_offset_progress()
    test_ui_import()
    print("ALL TESTS PASSED")
