"""Extract readable text from PDF files (free/open-source via pypdf)."""

from __future__ import annotations

from pathlib import Path


class PdfError(Exception):
    """Raised when a PDF cannot be read."""


def extract_pdf_text(path: str | Path, *, max_pages: int = 100) -> str:
    path = Path(path)
    if not path.exists():
        raise PdfError(f"File not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise PdfError("Please choose a .pdf file")

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise PdfError("pypdf is not installed. Run: pip install pypdf") from exc

    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # noqa: BLE001
        raise PdfError(f"Could not open PDF: {exc}") from exc

    parts: list[str] = []
    for i, page in enumerate(reader.pages):
        if i >= max_pages:
            parts.append(f"\n[Stopped after {max_pages} pages]")
            break
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = text.strip()
        if text:
            parts.append(text)

    joined = "\n\n".join(parts).strip()
    if not joined:
        raise PdfError(
            "No extractable text in this PDF. "
            "It may be scanned images — use Select region (OCR) on the page instead."
        )
    return joined
