"""Non-GUI smoke tests for Screen Read-Aloud v5 features."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw
from pypdf import PdfWriter

from app import autostart
from app.config import APP_VERSION, load_settings, save_settings
from app.history import add_history, load_history
from app.langdetect import detect_language
from app.memory import clear_memory, has_memory, load_memory, save_memory
from app.ocr import OCR_LANG_CHOICES, preprocess_variants, recognize_image, ui_lang_tip
from app.pdf_read import PdfError, extract_pdf_text
from app.profiles import (
    apply_profile,
    delete_profile,
    find_profile,
    normalize_profiles,
    snapshot_from_settings,
    upsert_profile,
)
from app.textutil import next_sentence_after, sentence_at_or_after, split_sentences
from app.tts import TextToSpeech, tokenize
from app.updatecheck import is_newer


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
    assert "profiles" in settings
    assert "pdf_max_pages" in settings
    assert "auto_detect_lang" in settings
    assert "reading_mode" in settings
    assert APP_VERSION.startswith("5.")
    settings["theme"] = "dark"
    save_settings(settings)
    assert load_settings()["theme"] == "dark"
    print("ok settings")


def test_langdetect() -> None:
    assert detect_language("Hej, det här är en svensk text och jag kan läsa.") == "sv"
    assert detect_language("Hello, this is an English paragraph about reading.") == "en"
    print("ok langdetect")


def test_update_version_compare() -> None:
    assert is_newer("v5.0.1", "5.0.0")
    assert not is_newer("v4.0.0", "5.0.0")
    assert not is_newer("v5.0.0", "5.0.0")
    print("ok update compare")


def test_ocr_variants_and_tip() -> None:
    img = Image.new("RGB", (100, 40), "white")
    variants = preprocess_variants(img)
    assert len(variants) >= 3
    tip = ui_lang_tip("sv")
    assert "sv" in tip.lower() or "OCR" in tip
    print("ok ocr variants")


def test_history() -> None:
    items = add_history("Feature test history item", source="test")
    assert items and load_history()[0]["text"].startswith("Feature test")
    print("ok history")


def test_memory() -> None:
    clear_memory()
    assert not has_memory()
    save_memory("Hello world. Continue here.", offset=13, source="test")
    mem = load_memory()
    assert mem and mem["offset"] == 13
    assert has_memory()
    clear_memory()
    print("ok memory")


def test_profiles() -> None:
    profiles = normalize_profiles([])
    assert any(p["name"] == "Svenska långsam" for p in profiles)
    settings = load_settings()
    snap = snapshot_from_settings(settings, "Test profile")
    profiles = upsert_profile(profiles, snap)
    found = find_profile(profiles, "Test profile")
    assert found and found["name"] == "Test profile"
    applied = apply_profile(settings, found)
    assert applied["active_profile"] == "Test profile"
    profiles = delete_profile(profiles, "Test profile")
    assert find_profile(profiles, "Test profile") is None
    print("ok profiles")


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
    spoken: list[str] = []
    tts = TextToSpeech(on_word=lambda s, e, w: spoken.append(w))
    voices = tts.list_edge_voices_sync("en")
    voice = voices[0]["id"]
    tts.speak(
        "One. Two.",
        engine="edge",
        voice_id=voice,
        rate=180,
        highlight=True,
        on_done=lambda: done.__setitem__("yes", True),
    )
    import time

    for _ in range(180):
        if done["yes"]:
            break
        time.sleep(0.1)
    assert done["yes"], "Edge preview did not finish"
    assert spoken, "expected sentence highlights for Edge"
    print("ok edge sentence highlight", voice, spoken)


def test_mp3_export() -> None:
    out = Path("test_export.mp3")
    if out.exists():
        out.unlink()
    tts = TextToSpeech()
    voices = tts.list_edge_voices_sync("en")
    voice = voices[0]["id"]
    tts.export_mp3("Hello export test.", str(out), voice_id=voice, rate=180)
    assert out.exists() and out.stat().st_size > 500
    out.unlink()
    print("ok mp3 export")


def test_pdf_extract() -> None:
    out = Path("test_sample.pdf")
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=200)
    writer.write(out)
    try:
        try:
            extract_pdf_text(out, force_ocr=False)
            # Blank page may OCR to empty and raise, or succeed with notes — either ok if handled
        except PdfError:
            print("ok pdf blank rejected/ocr-empty")
        else:
            print("ok pdf blank handled")
    finally:
        if out.exists():
            out.unlink()

    try:
        extract_pdf_text("does_not_exist.pdf")
        raise AssertionError("missing file should fail")
    except PdfError:
        print("ok pdf missing rejected")


def test_pdf_ocr_image_page() -> None:
    """Create a one-page PDF from an image and OCR it."""
    import pymupdf

    img = Image.new("RGB", (800, 200), "white")
    ImageDraw.Draw(img).text((40, 70), "Scanned PDF hello world", fill="black")
    png = Path("test_scan_page.png")
    pdf = Path("test_scan.pdf")
    img.save(png)
    try:
        doc = pymupdf.open()
        page = doc.new_page(width=800, height=200)
        page.insert_image(page.rect, filename=str(png))
        doc.save(pdf)
        doc.close()

        text = extract_pdf_text(pdf, max_pages=1, ocr_lang="en", force_ocr=True)
        assert "Hello" in text or "hello" in text.lower() or "world" in text.lower() or "PDF" in text or "Scanned" in text
        print("ok pdf ocr:", repr(text[:120]))
    finally:
        for p in (png, pdf):
            if p.exists():
                p.unlink()


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
    test_langdetect()
    test_update_version_compare()
    test_ocr_variants_and_tip()
    test_history()
    test_memory()
    test_profiles()
    test_ocr()
    test_edge_all_voices()
    test_tts_offline()
    test_tts_edge_preview()
    test_mp3_export()
    test_pdf_extract()
    test_pdf_ocr_image_page()
    test_autostart()
    test_ui_import()
    print("ALL TESTS PASSED")
