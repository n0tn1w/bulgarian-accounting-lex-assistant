"""Currency detection from the document's own data.

Bulgaria's euro adoption means invoices may be in EUR or BGN (and transition documents
often show both), so currency is never assumed. It is derived per document from explicit
currency fields, amount field-name suffixes (...BGN/...EUR), the "Словом:" words line, or
currency tokens next to the totals.
"""

from __future__ import annotations

import re

# token (substring, lowercased) to ISO code; EUR checked before BGN.
_TOKENS: list[tuple[tuple[str, ...], str]] = [
    (("eur", "€", "евро", "евр", "цент", "ευρ"), "EUR"),
    (("bgn", "bgl", "лева", "лев", "лв"), "BGN"),
]


def normalize_currency(value: str | None) -> str | None:
    if not value:
        return None
    t = value.strip().lower()
    for tokens, code in _TOKENS:
        if any(tok in t for tok in tokens):
            return code
    return None


def currency_from_field_name(name: str | None) -> str | None:
    """Currency implied by an amount field name, e.g. netAmountBGN / totalAmountEUR."""
    if not name:
        return None
    n = name.lower()
    if "eur" in n or "евро" in n:
        return "EUR"
    if "bgn" in n or "bgl" in n or "лева" in n or n.endswith("лв"):
        return "BGN"
    return None


def detect_currency_text(text: str) -> str | None:
    """Currency of an OCR/plain-text invoice. The 'Словом:' unit is authoritative
    (it spells out the legal amount), then the labelled total lines."""
    if not text:
        return None
    m = re.search(r"словом[^\n]*", text, re.IGNORECASE)
    if m:
        c = normalize_currency(m.group(0))
        if c:
            return c
    for m in re.finditer(
        r"(обща\s+стойност|всичко\s+за\s+плащане|сума\s+за\s+плащане|крайна\s+сума)[^\n]*",
        text, re.IGNORECASE,
    ):
        c = normalize_currency(m.group(0))
        if c:
            return c
    return normalize_currency(text)


def file_currency_hint(xml: str) -> str | None:
    """A file-level currency (e.g. SAP <Currency>EUR</Currency> or a currency attr)."""
    for pat in (r"<Currency>\s*([^<]+?)\s*</Currency>", r'currency(?:code)?="([^"]+)"'):
        m = re.search(pat, xml, re.IGNORECASE)
        if m:
            c = normalize_currency(m.group(1))
            if c:
                return c
    return None
