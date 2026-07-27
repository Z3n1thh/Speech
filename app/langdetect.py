"""Lightweight Swedish/English language detection for voice switching."""

from __future__ import annotations

import re

_SV_CHARS = re.compile(r"[åäöÅÄÖ]")
_SV_WORDS = {
    "och",
    "att",
    "det",
    "som",
    "är",
    "för",
    "med",
    "på",
    "av",
    "den",
    "till",
    "inte",
    "har",
    "om",
    "ett",
    "kan",
    "från",
    "ska",
    "eller",
    "jag",
    "du",
    "vi",
    "de",
    "när",
    "här",
    "där",
    "också",
    "var",
    "vad",
    "hur",
    "vilken",
    "detta",
    "denna",
}
_EN_WORDS = {
    "the",
    "and",
    "that",
    "with",
    "for",
    "you",
    "this",
    "from",
    "have",
    "are",
    "was",
    "were",
    "been",
    "their",
    "which",
    "will",
    "would",
    "about",
    "there",
    "what",
    "when",
    "where",
    "your",
    "they",
    "them",
}


def detect_language(text: str) -> str:
    """Return 'sv' or 'en' based on characters and common words."""
    sample = (text or "")[:4000]
    if not sample.strip():
        return "en"

    sv_char_hits = len(_SV_CHARS.findall(sample))
    words = re.findall(r"[A-Za-zÅÄÖåäö']+", sample.lower())
    if not words and sv_char_hits == 0:
        return "en"

    sv_word_hits = sum(1 for w in words if w in _SV_WORDS)
    en_word_hits = sum(1 for w in words if w in _EN_WORDS)

    sv_score = sv_char_hits * 3 + sv_word_hits
    en_score = en_word_hits

    if sv_score > en_score and sv_score >= 2:
        return "sv"
    if en_score > sv_score:
        return "en"
    # Tie-break: Swedish letters win
    if sv_char_hits > 0:
        return "sv"
    return "en"
