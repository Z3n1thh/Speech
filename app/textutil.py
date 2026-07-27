"""Text helpers: sentences and cursor-based reading ranges."""

from __future__ import annotations

import re


_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]+|[^.!?\n]+$", re.MULTILINE)


def split_sentences(text: str) -> list[tuple[int, int, str]]:
    """Return (start, end, sentence) spans for non-empty sentences."""
    results: list[tuple[int, int, str]] = []
    for match in _SENTENCE_RE.finditer(text or ""):
        chunk = match.group().strip()
        if not chunk:
            continue
        # trim leading whitespace in span for cleaner highlight
        raw = match.group()
        lead = len(raw) - len(raw.lstrip())
        start = match.start() + lead
        end = start + len(chunk)
        results.append((start, end, chunk))
    return results


def sentence_at_or_after(text: str, index: int) -> tuple[int, int, str] | None:
    sentences = split_sentences(text)
    if not sentences:
        return None
    for start, end, sentence in sentences:
        if end > index:
            return start, end, sentence
    return sentences[-1]


def next_sentence_after(text: str, index: int) -> tuple[int, int, str] | None:
    sentences = split_sentences(text)
    for start, end, sentence in sentences:
        if start > index:
            return start, end, sentence
    return None
