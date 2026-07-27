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


def ui_lang_tip(lang: str) -> str:
    """Short tip shown in the status bar for OCR language packs."""
    return (
        f"OCR tip: if results look wrong, install Windows OCR for '{lang}' "
        f"(Admin PowerShell): {pack_hint(lang)}"
    )


def _ensure_rgb(image: Image.Image) -> Image.Image:
    if image.mode not in ("RGB", "RGBA", "L"):
        return image.convert("RGB")
    if image.mode == "RGBA":
        return image.convert("RGB")
    return image


def _scale_min(image: Image.Image, min_side: int) -> Image.Image:
    width, height = image.size
    side = min(width, height)
    if side >= min_side:
        return image
    scale = max(2, int(min_side / max(side, 1)))
    return image.resize((width * scale, height * scale), Image.Resampling.LANCZOS)


def preprocess_variants(image: Image.Image) -> list[Image.Image]:
    """Several preprocessing passes — pick the best OCR result later."""
    base = _ensure_rgb(image)
    variants: list[Image.Image] = []

    # 1) Default: upscale + autocontrast + sharpen
    v1 = _scale_min(base, 500)
    g1 = ImageOps.grayscale(v1)
    g1 = ImageOps.autocontrast(g1)
    g1 = ImageEnhance.Contrast(g1).enhance(1.35)
    g1 = g1.filter(ImageFilter.SHARPEN)
    variants.append(g1.convert("RGB"))

    # 2) Stronger contrast, larger upscale
    v2 = _scale_min(base, 700)
    g2 = ImageOps.grayscale(v2)
    g2 = ImageOps.autocontrast(g2)
    g2 = ImageEnhance.Contrast(g2).enhance(1.8)
    g2 = ImageEnhance.Sharpness(g2).enhance(2.0)
    variants.append(g2.convert("RGB"))

    # 3) Inverted (light text on dark UI)
    v3 = _scale_min(base, 500)
    g3 = ImageOps.grayscale(v3)
    g3 = ImageOps.invert(g3)
    g3 = ImageOps.autocontrast(g3)
    g3 = ImageEnhance.Contrast(g3).enhance(1.4)
    variants.append(g3.convert("RGB"))

    # 4) Threshold-ish via point
    v4 = _scale_min(base, 600)
    g4 = ImageOps.grayscale(v4)
    g4 = ImageOps.autocontrast(g4)
    g4 = g4.point(lambda p: 255 if p > 160 else 0)
    variants.append(g4.convert("RGB"))

    return variants


def preprocess_image(image: Image.Image) -> Image.Image:
    """Improve contrast/sharpness for small or low-contrast screen text."""
    return preprocess_variants(image)[0]


def _ocr_once(image: Image.Image, lang: str) -> str:
    from winocr import recognize_pil_sync

    result = recognize_pil_sync(image, lang)
    if isinstance(result, dict):
        text = result.get("text") or ""
    else:
        text = getattr(result, "text", "") or ""
    return str(text).strip()


def recognize_image(image: Image.Image, lang: str = "en") -> str:
    """Return recognized text from a PIL image using Windows OCR (multi-try)."""
    lang = (lang or "en").lower().strip()

    try:
        from winocr import recognize_pil_sync  # noqa: F401
    except ImportError as exc:
        raise OcrError(
            "winocr is not installed. Run: pip install winocr"
        ) from exc

    languages = [lang]
    if lang != "en":
        languages.append("en")

    variants = preprocess_variants(image)
    last_error: Exception | None = None
    best = ""

    for prepared in variants:
        for code in languages:
            try:
                text = _ocr_once(prepared, code)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue
            if len(text) > len(best):
                best = text
            # Good enough early exit
            if len(best) >= 24:
                return best

    if best:
        return best

    if last_error is not None:
        message = str(last_error).strip() or last_error.__class__.__name__
        raise OcrError(
            f"OCR failed for language '{lang}' ({message}).\n"
            f"Install the Windows OCR pack in Admin PowerShell:\n{pack_hint(lang)}\n"
            f"Tip: try switching OCR language in the app (sv/en/…)."
        ) from last_error

    raise OcrError(
        "No text found in the selected region. Try a larger/clearer area, "
        f"or install OCR language '{lang}':\n{pack_hint(lang)}\n"
        "Tip: dark UI text may need a bigger selection; try OCR lang sv or en."
    )
