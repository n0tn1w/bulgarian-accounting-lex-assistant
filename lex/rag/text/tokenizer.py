"""Bulgarian tokenizer for the sparse (BM25) side of retrieval (course topic L3).

Dense retrieval uses bge-m3's own subword tokenizer, but BM25 needs explicit,
language-aware word tokenization. We:
  * lower-case and split on non-letter/digit boundaries (Cyrillic-aware),
  * map a few Latin look-alike letters to Cyrillic,
  * drop a curated Bulgarian stop-word list,
  * optionally lemmatize via ``simplemma`` (graceful fallback if unavailable),
so that "осигуровките" and "осигуровки" collide on the same term.
"""
from __future__ import annotations

import re
from typing import List

from ..parsing.cleaner import HtmlCleaner

# Compact but practical Bulgarian stop-word list.
_STOPWORDS = {
    "и", "в", "във", "на", "за", "с", "със", "от", "до", "по", "при", "като",
    "че", "да", "не", "се", "е", "са", "съм", "си", "то", "той", "тя", "те",
    "този", "тази", "това", "тези", "който", "която", "което", "които",
    "а", "но", "или", "ако", "то", "така", "където", "когато", "защото",
    "ще", "би", "бъде", "беше", "съответно", "т", "ал", "чл", "пр", "вр",
    "г", "бр", "стр", "ли", "още", "много", "по", "най", "през", "между",
    "след", "преди", "над", "под", "без", "около", "спрямо", "чрез",
}

_TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁёЇ-ӹ]+", re.UNICODE)

try:  # optional dependency; lemmatization improves recall but isn't required
    import simplemma  # type: ignore

    def _lemmatize(token: str) -> str:
        try:
            return simplemma.lemmatize(token, lang="bg")
        except Exception:
            return token

    _HAS_LEMMA = True
except Exception:  # pragma: no cover - environment without simplemma
    def _lemmatize(token: str) -> str:
        return token

    _HAS_LEMMA = False


class BgTokenizer:
    def __init__(self, use_lemmatizer: bool = True, drop_stopwords: bool = True):
        self.use_lemmatizer = use_lemmatizer and _HAS_LEMMA
        self.drop_stopwords = drop_stopwords

    def tokenize(self, text: str) -> List[str]:
        out: List[str] = []
        for raw in _TOKEN_RE.findall(text):
            tok = HtmlCleaner.fix_lookalikes(raw).lower()
            if self.drop_stopwords and tok in _STOPWORDS:
                continue
            if len(tok) < 2:
                continue
            if self.use_lemmatizer:
                tok = _lemmatize(tok)
            out.append(tok)
        return out
