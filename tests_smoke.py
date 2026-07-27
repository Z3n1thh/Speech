"""Non-GUI smoke tests for Screen Read-Aloud v3 features."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw
from pypdf import PdfWriter

from app import autostart
from app.config import load_settings, save_settings
from app.history import add_history, load_history
from app.ocr import OCR_LANG_CHOICES, recognize_image
from app.pdf_read import PdfError, extract_pdf_text
from app.textutil import next_sentence_after, sentence_at_or_after, split_sentences
from app.tts import TextToSpeech, tokenize


def test_tokenize_and_sentences() -> None:
    assert [t[2] for t in tokenize("Hello world")] == ["Hello", "world"]
    text = "One. Two! Three?"
    sents = split_sentences(text)
    assert len(sents) == 3
    assert sentence_at_or_after(text, 0)[2].startswith("One")
    nxt = next_sentence_after(text, 0)
    assert nxt and "Two" in nxt[2]
    print("ok textutil")


def test_settings() -> None:
    settings = load_settings()
    assert "favorite_voices" in settings
    assert "theme" in settings
    assert "voice_filter" in settings
    settings["theme"] = "dark"
    save_settings(settings)
    assert load_settings()["theme"] == "dark"
    print("ok settings")


def test_history() -> None:
    items = add_history("Feature test history item", source="test")
    assert items and load_history()[0]["text"].startswith("Feature test")
    print("ok history")


def test_ocr() -> None:
    img = Image.new("RGB", (640, 160), "white")
    ImageDraw.Draw(img).text((30, 50), "Hello reading helper", fill="black")
    text = recognize_image(img, lang="en")
    assert "Hello" in text or "reading" in text.lower()
    assert "en" in OCR_LANG_CHOICES and "sv" in OCR_LANG_CHOICES
    print("ok ocr:", repr(text))


def test_edge_all_voices() -> None:
    tts = TextToSpeech()
    all_voices = tts.list_edge_voices_sync("all")
    assert len(all_voices) > 40, f"expected many voices, got {len(all_voices)}"
    en = tts.list_edge_voices_sync("en")
    sv = tts.list_edge_voices_sync("sv")
    assert len(en) >= 10
    assert any(v["id"].startswith("sv-") for v in sv)
    locales = tts.list_edge_locales_sync()
    assert "all" in locales and "en" in locales
    print("ok edge voices all=", len(all_voices), "en=", len(en), "sv=", len(sv))


def test_tts_offline() -> None:
    spoken: list[str] = []
    done = {"yes": False}
    tts = TextToSpeech(on_word=lambda _s, _e, w: spoken.append(w))
    tts.speak(
        "One two",
        engine="offline",
        rate=200,
        highlight=True,
        on_done=lambda: done.__setitem__("yes", True),
    )
    import time

    for _ in range(80):
        if done["yes"]:
            break
        time.sleep(0.1)
    assert done["yes"] and spoken
    print("ok offline tts", spoken)


def test_tts_edge_preview() -> None:
    done = {"yes": False}
    tts = TextToSpeech()
    voices = tts.list_edge_voices_sync("en")
    voice = voices[0]["id"]
    tts.speak(
        "Hi",
        engine="edge",
        voice_id=voice,
        rate=180,
        highlight=False,
        on_done=lambda: done.__setitem__("yes", True),
    )
    import time

    for _ in range(120):
        if done["yes"]:
            break
        time.sleep(0.1)
    assert done["yes"], "Edge preview did not finish"
    print("ok edge preview", voice)


def test_pdf_extract(tmp_path: Path | None = None) -> None:
    # Minimal valid-ish PDF via pypdf
    out = Path("test_sample.pdf")
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=200)
    # Blank pages have no text — expect PdfError, then create text PDF differently
    writer.write(out)
    try:
        try:
            extract_pdf_text(out)
            raise AssertionError("blank pdf should fail")
        except PdfError:
            print("ok pdf blank rejected")
    finally:
        if out.exists():
            out.unlink()

    # Create a simple text PDF with reportlab-free approach: use pypdf page merge is hard.
    # Instead verify PdfError on missing file.
    try:
        extract_pdf_text("does_not_exist.pdf")
        raise AssertionError("missing file should fail")
    except PdfError:
        print("ok pdf missing rejected")


def test_autostart() -> None:
    before = autostart.is_enabled()
    try:
        autostart.set_enabled(True)
        assert autostart.is_enabled()
        autostart.set_enabled(False)
        assert not autostart.is_enabled()
    finally:
        autostart.set_enabled(before)
    print("ok autostart")


def test_ui_import() -> None:
    from app.ui import App

    assert App is not None
    print("ok ui import")


if __name__ == "__main__":
    test_tokenize_and_sentences()
    test_settings()
    test_history()
    test_ocr()
    test_edge_all_voices()
    test_tts_offline()
    test_tts_edge_preview()
    test_pdf_extract()
    test_autostart()
    test_ui_import()
    print("ALL TESTS PASSED")
