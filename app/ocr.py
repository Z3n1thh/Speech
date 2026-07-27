"""Windows built-in OCR via winocr, with free local image preprocessing."""

from __future__ import annotations

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


class OcrError(Exception):
    """Raised when OCR fails or is unavailable."""


# Common Windows OCR language tags -> capability hint
OCR_LANG_PACKS: dict[str, str] = {
    "en": "Language.OCR~~~en-US~0.0.1.0",
    "sv": "Language.OCR~~~sv-SE~0.0.1.0",
    "de": "Language.OCR~~~de-DE~0.0.1.0",
    "fr": "Language.OCR~~~fr-FR~0.0.1.0",
    "es": "Language.OCR~~~es-ES~0.0.1.0",
    "it": "Language.OCR~~~it-IT~0.0.1.0",
    "nl": "Language.OCR~~~nl-NL~0.0.1.0",
    "pl": "Language.OCR~~~pl-PL~0.0.1.0",
    "fi": "Language.OCR~~~fi-FI~0.0.1.0",
    "da": "Language.OCR~~~da-DK~0.0.1.0",
    "nb": "Language.OCR~~~nb-NO~0.0.1.0",
    "pt": "Language.OCR~~~pt-BR~0.0.1.0",
}

OCR_LANG_CHOICES = list(OCR_LANG_PACKS.keys())


def pack_hint(lang: str) -> str:
    code = OCR_LANG_PACKS.get(lang, OCR_LANG_PACKS["en"])
    return f'Add-WindowsCapability -Online -Name "{code}"'


def preprocess_image(image: Image.Image) -> Image.Image:
    """Improve contrast/sharpness for small or low-contrast screen text."""
    if image.mode not in ("RGB", "RGBA", "L"):
        image = image.convert("RGB")
    elif image.mode == "RGBA":
        image = image.convert("RGB")

    width, height = image.size
    min_side = min(width, height)
    if min_side < 500:
        scale = max(2, int(500 / max(min_side, 1)))
        image = image.resize(
            (width * scale, height * scale),
            Image.Resampling.LANCZOS,
        )

    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    gray = ImageEnhance.Contrast(gray).enhance(1.35)
    gray = gray.filter(ImageFilter.SHARPEN)
    return gray.convert("RGB")


def recognize_image(image: Image.Image, lang: str = "en") -> str:
    """Return recognized text from a PIL image using Windows OCR."""
    image = preprocess_image(image)
    lang = (lang or "en").lower().strip()

    try:
        from winocr import recognize_pil_sync
    except ImportError as exc:
        raise OcrError(
            "winocr is not installed. Run: pip install winocr"
        ) from exc

    languages = [lang]
    if lang != "en":
        languages.append("en")

    last_error: Exception | None = None
    text = ""
    for code in languages:
        try:
            result = recognize_pil_sync(image, code)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
        if isinstance(result, dict):
            text = result.get("text") or ""
        else:
            text = getattr(result, "text", "") or ""
        text = str(text).strip()
        if text:
            return text

    if last_error is not None and not text:
        message = str(last_error).strip() or last_error.__class__.__name__
        raise OcrError(
            f"OCR failed for language '{lang}' ({message}).\n"
            f"Install the Windows OCR pack in Admin PowerShell:\n{pack_hint(lang)}"
        ) from last_error

    raise OcrError(
        "No text found in the selected region. Try a larger/clearer area, "
        f"or install OCR language '{lang}':\n{pack_hint(lang)}"
    )
