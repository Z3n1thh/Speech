"""Extract readable text from PDF files (text layer or page OCR)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PIL import Image

from app.ocr import OcrError, recognize_image

ProgressCb = Callable[[str], None]


class PdfError(Exception):
    """Raised when a PDF cannot be read."""


def _page_text(page) -> str:
    try:
        text = page.extract_text() or ""
    except Exception:
        text = ""
    return text.strip()


def _extract_text_layer(path: Path, *, max_pages: int) -> tuple[str, int, int]:
    """Return (joined_text, pages_with_text, total_pages_scanned)."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise PdfError("pypdf is not installed. Run: pip install pypdf") from exc

    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # noqa: BLE001
        raise PdfError(f"Could not open PDF: {exc}") from exc

    parts: list[str] = []
    with_text = 0
    total = 0
    for i, page in enumerate(reader.pages):
        if i >= max_pages:
            break
        total += 1
        text = _page_text(page)
        if text:
            with_text += 1
            parts.append(text)

    return "\n\n".join(parts).strip(), with_text, total


def _render_page_image(doc, page_index: int, *, dpi: int = 200) -> Image.Image:
    page = doc.load_page(page_index)
    zoom = dpi / 72.0
    mat = __import__("pymupdf").Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    mode = "RGB" if pix.n < 4 else "RGBA"
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples).convert("RGB")


def _ocr_pdf_pages(
    path: Path,
    *,
    max_pages: int,
    ocr_lang: str,
    on_progress: ProgressCb | None,
) -> str:
    try:
        import pymupdf
    except ImportError as exc:
        raise PdfError(
            "Scanned PDF OCR needs pymupdf. Run: pip install pymupdf"
        ) from exc

    try:
        doc = pymupdf.open(str(path))
    except Exception as exc:  # noqa: BLE001
        raise PdfError(f"Could not open PDF for OCR: {exc}") from exc

    parts: list[str] = []
    try:
        page_count = min(len(doc), max_pages)
        for i in range(page_count):
            if on_progress:
                on_progress(f"OCR PDF page {i + 1}/{page_count}...")
            try:
                image = _render_page_image(doc, i)
                text = recognize_image(image, lang=ocr_lang)
            except OcrError as exc:
                parts.append(f"[Page {i + 1}: OCR failed — {exc}]")
                continue
            except Exception as exc:  # noqa: BLE001
                parts.append(f"[Page {i + 1}: OCR error — {exc}]")
                continue
            text = (text or "").strip()
            if text:
                parts.append(text)
            else:
                parts.append(f"[Page {i + 1}: no text found]")
        if page_count < len(doc):
            parts.append(f"\n[Stopped after {max_pages} pages]")
    finally:
        doc.close()

    joined = "\n\n".join(parts).strip()
    real = [
        p
        for p in parts
        if p
        and not p.startswith("[Page ")
        and not p.startswith("\n[")
    ]
    if not real:
        raise PdfError(
            "OCR found no text in this PDF. Try another OCR language, "
            "or use Select region on a page."
        )
    return joined


def extract_pdf_text(
    path: str | Path,
    *,
    max_pages: int = 100,
    ocr_lang: str = "en",
    force_ocr: bool = False,
    on_progress: ProgressCb | None = None,
) -> str:
    """Extract text from a PDF. Falls back to page OCR for scanned/image PDFs."""
    path = Path(path)
    if not path.exists():
        raise PdfError(f"File not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise PdfError("Please choose a .pdf file")

    if on_progress:
        on_progress("Reading PDF text layer...")

    if not force_ocr:
        joined, with_text, total = _extract_text_layer(path, max_pages=max_pages)
        # Prefer text layer when most pages have extractable text
        if joined and total > 0 and with_text / total >= 0.4:
            if total >= max_pages:
                joined = joined + f"\n\n[Stopped after {max_pages} pages]"
            return joined
        if joined and with_text > 0:
            # Sparse text — still try OCR for better coverage of scanned pages
            if on_progress:
                on_progress("Sparse text layer — trying page OCR...")
            try:
                ocr_text = _ocr_pdf_pages(
                    path, max_pages=max_pages, ocr_lang=ocr_lang, on_progress=on_progress
                )
                # Prefer longer result (OCR often better on mixed/scanned docs)
                if len(ocr_text) > len(joined) * 1.2:
                    return ocr_text
                return joined
            except PdfError:
                return joined

    if on_progress:
        on_progress("No text layer — OCR page by page...")
    return _ocr_pdf_pages(
        path, max_pages=max_pages, ocr_lang=ocr_lang, on_progress=on_progress
    )
