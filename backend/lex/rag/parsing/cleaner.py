"""HTML -> clean plain text.

Strips scripts/styles/nav, collapses whitespace, and fixes a couple of common
Cyrillic/encoding nuisances. The goal is a clean linear text stream the
ArticleChunker can reliably segment by член/алинея/точка (L6: data quality).
"""
from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup

# Latin look-alikes that sometimes appear inside Cyrillic legal text, mapped to
# their Cyrillic counterparts so tokenization/search behaves consistently.
_LOOKALIKE = str.maketrans({
    "A": "А", "B": "В", "E": "Е", "K": "К", "M": "М", "H": "Н",
    "O": "О", "P": "Р", "C": "С", "T": "Т", "X": "Х", "Y": "У",
    "a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "y": "у", "x": "х",
})

_STRIP_TAGS = ("script", "style", "noscript", "header", "footer", "nav",
               "form", "button", "svg", "iframe")


class HtmlCleaner:
    def clean(self, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(self._strip_tags()):
            tag.decompose()

        # Pick the densest article container (most "Чл." markers); fall back to
        # <body>. Relying on class names is fragile across sites, so we measure
        # actual legal-text content instead.
        container = soup.body or soup
        best_count = container.get_text().count("Чл.")
        for div in soup.find_all("div"):
            cnt = div.get_text().count("Чл.")
            if cnt > best_count:
                container, best_count = div, cnt

        text = container.get_text(separator="\n")
        return self._normalize(text)

    @staticmethod
    def _strip_tags():
        return list(_STRIP_TAGS)

    @staticmethod
    def _normalize(text: str) -> str:
        text = unicodedata.normalize("NFKC", text)
        # Normalize newlines/whitespace
        text = text.replace("\r", "\n")
        text = re.sub(r"[ \t ]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n", text)
        lines = [ln.strip() for ln in text.split("\n")]
        lines = [ln for ln in lines if ln]
        return "\n".join(lines)

    @staticmethod
    def fix_lookalikes(token: str) -> str:
        """Map Latin look-alike letters to Cyrillic (use on tokens, not full text)."""
        return token.translate(_LOOKALIKE)
