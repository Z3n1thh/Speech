"""Windows built-in OCR via winocr, with free local image preprocessing."""

from __future__ import annotations

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


class OcrError(Exception):
    """Raised when OCR fails or is unavailable."""


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

    try:
        from winocr import recognize_pil_sync
    except ImportError as exc:
        raise OcrError(
            "winocr is not installed. Run: pip install winocr"
        ) from exc

    # Try requested language, then English fallback
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
        pack = (
            'Add-WindowsCapability -Online -Name "Language.OCR~~~sv-SE~0.0.1.0"'
            if lang.startswith("sv")
            else 'Add-WindowsCapability -Online -Name "Language.OCR~~~en-US~0.0.1.0"'
        )
        raise OcrError(
            f"OCR failed ({message}). Install a Windows OCR language pack, e.g.:\n{pack}"
        ) from last_error

    raise OcrError(
        "No text found in the selected region. Try a larger or clearer area."
    )
