"""Windows built-in OCR via winocr."""

from __future__ import annotations

from PIL import Image


class OcrError(Exception):
    """Raised when OCR fails or is unavailable."""


def recognize_image(image: Image.Image, lang: str = "en") -> str:
    """Return recognized text from a PIL image using Windows OCR."""
    if image.mode not in ("RGB", "RGBA", "L"):
        image = image.convert("RGB")

    # Upscale small regions — Windows OCR works better on larger glyphs
    width, height = image.size
    min_side = min(width, height)
    if min_side < 400:
        scale = max(2, int(400 / max(min_side, 1)))
        image = image.resize(
            (width * scale, height * scale),
            Image.Resampling.LANCZOS,
        )

    try:
        from winocr import recognize_pil_sync
    except ImportError as exc:
        raise OcrError(
            "winocr is not installed. Run: pip install winocr"
        ) from exc

    try:
        result = recognize_pil_sync(image, lang)
    except Exception as exc:  # noqa: BLE001 — surface OCR failures clearly
        message = str(exc).strip() or exc.__class__.__name__
        raise OcrError(
            f"OCR failed ({message}). "
            "Install a Windows OCR language pack, e.g. in Admin PowerShell:\n"
            'Add-WindowsCapability -Online -Name "Language.OCR~~~en-US~0.0.1.0"'
        ) from exc

    if isinstance(result, dict):
        text = result.get("text") or ""
    else:
        text = getattr(result, "text", "") or ""

    text = str(text).strip()
    if not text:
        raise OcrError(
            "No text found in the selected region. Try a larger or clearer area."
        )
    return text
