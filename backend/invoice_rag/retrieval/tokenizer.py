"""Bulgarian word tokenizer for the BM25 (sparse) side of retrieval.

Standalone (does not import lex internals): Cyrillic-aware splitting, a curated
Bulgarian stop-word list, and optional simplemma lemmatization with graceful
fallback — so "услугите" and "услуги" collide on the same term.
"""
from __future__ import annotations

import re
from typing import List

_STOPWORDS = {
    "и", "в", "във", "на", "за", "с", "със", "от", "до", "по", "при", "като",
    "че", "да", "не", "се", "е", "са", "съм", "си", "то", "той", "тя", "те",
    "този", "тази", "това", "тези", "който", "която", "което", "които",
    "а", "но", "или", "ако", "така", "където", "когато", "защото", "ще",
    "през", "между", "след", "преди", "над", "под", "без", "около",
}

_TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁёЇ-ӹ]+", re.UNICODE)

try:  # optional; improves recall but not required
    import simplemma  # type: ignore

    def _lemmatize(token: str) -> str:
        try:
            return simplemma.lemmatize(token, lang="bg")
        except Exception:
            return token

    _HAS_LEMMA = True
except Exception:  # pragma: no cover
    def _lemmatize(token: str) -> str:
        return token

    _HAS_LEMMA = False


class BgTokenizer:
    def __init__(self, use_lemmatizer: bool = True, drop_stopwords: bool = True):
        self.use_lemmatizer = use_lemmatizer and _HAS_LEMMA
        self.drop_stopwords = drop_stopwords

    def tokenize(self, text: str) -> List[str]:
        out: List[str] = []
        for raw in _TOKEN_RE.findall(text or ""):
            tok = raw.lower()
            if self.drop_stopwords and tok in _STOPWORDS:
                continue
            if len(tok) < 2:
                continue
            if self.use_lemmatizer:
                tok = _lemmatize(tok)
            out.append(tok)
        return out
