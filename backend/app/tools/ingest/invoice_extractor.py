"""Bulgarian invoice field extraction from OCR/plain text.

Locale-aware regex for Фактура / ЕИК / ДДС / Доставчик / Получател etc., returning
each field with a confidence score and building a typed Invoice. A labelled-pattern
match scores ~0.9, a positional fallback ~0.5, a miss 0.0. The low scores are where
an LLM extraction fallback can kick in.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.domain import ExtractedField, Invoice, Party, TaxLine

from .bg_amount_words import total_from_words
from .company import tag_company
from .currency import detect_currency_text
from .document_types import detect_direction, detect_document_type, detect_reverse_charge

_HIGH = 0.9
_LOW = 0.5


def clean_amount(raw: str) -> Decimal | None:
    """Normalize a localized amount string to a Decimal.

    Handles thousands separators and EU decimal commas: "16 143,38" -> 16143.38.
    """
    if not raw:
        return None
    s = raw.replace(" ", "").replace(" ", "")
    if "," in s and "." in s:
        # Last separator is the decimal point.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    s = re.sub(r"[^\d.]", "", s)
    if not s:
        return None
    try:
        value = Decimal(s)
    except InvalidOperation:
        return None
    # Preserve sign: credit notes carry negative amounts; (123) is also negative.
    r = raw.strip()
    if r.startswith("-") or (r.startswith("(") and r.endswith(")")):
        value = -value
    return value


def normalize_date(raw: str) -> str:
    """Normalize ``dd.mm.yyyy`` / ``dd/mm/yyyy`` / ``yyyy-mm-dd`` to ISO ``yyyy-mm-dd``."""
    m = re.match(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", raw)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    m = re.match(r"(\d{4})[-.](\d{2})[-.](\d{2})", raw)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{mo}-{d}"
    return raw


# field extractors


def _all_eik(text: str) -> set[str]:
    return set(re.findall(r"ЕИК\s*[:\-]?\s*(\d{9})", text, re.IGNORECASE))


def _all_vat(text: str) -> list[str]:
    return [m.replace(" ", "").upper() for m in re.findall(r"BG\s*\d{9,10}", text, re.IGNORECASE)]


def extract_invoice_number(text: str) -> ExtractedField:
    exclude = _all_eik(text) | {v.removeprefix("BG") for v in _all_vat(text)}
    # OCR often garbles "№" into "Ne", "Ме", "No", "N°", so allow a few non-digit
    # characters between the label and the number rather than a fixed marker.
    labelled = [
        # any document-type label (фактура / кредитно-дебитно известие / проформа /
        # протокол) followed by the number; tolerant of a garbled № marker
        r"(?:Фактура|Кредитно\s+известие|Дебитно\s+известие|Проформа(?:\s+фактура)?|"
        r"Опростена\s+фактура|Протокол)[^\d\n]{0,6}(\d{7,15})",
        r"Invoice[^\d\n]{0,6}(\d{6,15})",
        r"№\s*[:\-]?\s*(\d{10,15})",
    ]
    for pat in labelled:
        m = re.search(pat, text, re.IGNORECASE)
        if m and m.group(1) not in exclude:
            return ExtractedField(value=m.group(1), confidence=_HIGH)
    # fallback: a standalone 10-digit number (common BG invoice shape)
    for m in re.finditer(r"\b(\d{10})\b", text):
        if m.group(1) not in exclude:
            return ExtractedField(value=m.group(1), confidence=_LOW)
    return ExtractedField(value=None, confidence=0.0)


def extract_date(text: str) -> ExtractedField:
    labelled = [
        r"Дата\s*[:\-]?\s*(\d{1,2}[./]\d{1,2}[./]\d{4})",
        r"Date\s*[:\-]?\s*(\d{1,2}[./]\d{1,2}[./]\d{4})",
    ]
    for pat in labelled:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return ExtractedField(value=normalize_date(m.group(1)), confidence=_HIGH)
    m = re.search(r"(\d{1,2}[./]\d{1,2}[./]\d{4}|\d{4}[-.]\d{2}[-.]\d{2})", text)
    if m:
        return ExtractedField(value=normalize_date(m.group(1)), confidence=_LOW)
    return ExtractedField(value=None, confidence=0.0)


_COMPANY_SUFFIX = r"(?:ЕООД|ООД|ЕТ|АД|СД|ЕАД|Ltd|LLC|ЛТД)"
# Party-role labels that can leak into a captured name and must be trimmed.
_LEADING_LABEL = re.compile(
    r"^(?:доставчик|получател|продавач|купувач|клиент|изпълнител)\b[\s:.\-]*",
    re.IGNORECASE,
)


def _clean_name(raw: str) -> str:
    name = " ".join(raw.split()).strip(" .,;:-\"'")
    prev = None
    while prev != name:  # strip repeated leading role labels
        prev = name
        name = _LEADING_LABEL.sub("", name).strip(" .,;:-\"'")
    return name


def _extract_party_name(text: str, labels: str) -> ExtractedField:
    pat = rf"(?:{labels})\s*[:\-]?\s*([А-Яа-яA-Za-z0-9\s\-\"'.,]+?{_COMPANY_SUFFIX})"
    m = re.search(pat, text, re.IGNORECASE)
    if m:
        name = _clean_name(m.group(1))
        return ExtractedField(value=name or None, confidence=_HIGH if name else 0.0)
    return ExtractedField(value=None, confidence=0.0)


def extract_supplier_name(text: str) -> ExtractedField:
    return _extract_party_name(text, "Доставчик|ДОСТАВЧИК|Продавач|Изпълнител")


def extract_recipient_name(text: str) -> ExtractedField:
    return _extract_party_name(text, "Получател|ПОЛУЧАТЕЛ|Купувач|Клиент")


# Tolerant separator: optional colon/dash, optional currency (BGN / лв / EUR), then amount.
# Handles real layouts like "ОБЩА СТОЙНОСТ: BGN 141.60".
_CUR = r"(?:BGN|лв\.?|лева|EUR|€|евро)?"
_SEP = rf"\s*[:\-]?\s*{_CUR}\s*[:\-]?\s*"
_AMT = r"(-?[\d  ]+[.,]\d{2})"


def _extract_amount(text: str, labels: list[str]) -> ExtractedField:
    for label in labels:
        m = re.search(label + _SEP + _AMT, text, re.IGNORECASE)
        if m:
            amt = clean_amount(m.group(1))
            if amt is not None:
                return ExtractedField(value=str(amt), confidence=_HIGH)
    return ExtractedField(value=None, confidence=0.0)


def extract_net_amount(text: str) -> ExtractedField:
    return _extract_amount(text, [
        r"Данъчна\s+основа",
        r"Сума\s+без\s+ДДС",
        r"Нето",
        r"ОБЩО",  # subtotal line on standard BG invoices
    ])


def extract_vat_amount(text: str) -> ExtractedField:
    # only the explicitly labelled VAT amount; a bare "ДДС 20%" would capture the
    # rate, not the amount. when absent, the value is derived from total - net.
    return _extract_amount(text, [
        r"Размер\s+на\s+данъка",
        r"Начислен\s+ДДС",
        r"Сума\s+на\s+ДДС",
    ])


def extract_total_amount(text: str) -> ExtractedField:
    return _extract_amount(text, [
        r"Обща\s+стойност",
        r"Всичко\s+за\s+плащане",
        r"Сума\s+за\s+плащане",
        r"Крайна\s+сума",
        r"Общо\s+за\s+плащане",
    ])


def _identify_vat_owners(text: str, vats: list[str]) -> tuple[str | None, str | None]:
    """Best-effort split of VAT numbers between supplier and recipient by section."""
    if not vats:
        return None, None
    if len(vats) == 1:
        return vats[0], None
    supplier = recipient = None
    sup = re.search(
        r"(?:Доставчик|ДОСТАВЧИК|Продавач|Изпълнител).*?(?=Получател|ПОЛУЧАТЕЛ|Купувач|$)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if sup:
        sect = sup.group(0).replace(" ", "")
        supplier = next((v for v in vats if v in sect), None)
    recipient = next((v for v in vats if v != supplier), None)
    return supplier, recipient


def parse_invoice_fields(text: str) -> dict[str, ExtractedField]:
    """Extract all known fields with confidence. Keys are stable field names."""
    fields = {
        "number": extract_invoice_number(text),
        "date": extract_date(text),
        "supplier_name": extract_supplier_name(text),
        "recipient_name": extract_recipient_name(text),
        "net_amount": extract_net_amount(text),
        "vat_amount": extract_vat_amount(text),
        "total_amount": extract_total_amount(text),
    }

    vats = _all_vat(text)
    sup_vat, rec_vat = _identify_vat_owners(text, vats)
    fields["supplier_vat"] = ExtractedField(value=sup_vat, confidence=_LOW if sup_vat else 0.0)
    fields["recipient_vat"] = ExtractedField(value=rec_vat, confidence=_LOW if rec_vat else 0.0)

    eiks = sorted(_all_eik(text))
    fields["supplier_eik"] = ExtractedField(
        value=eiks[0] if eiks else None, confidence=_HIGH if eiks else 0.0
    )
    return fields


def extract_invoice_from_text(text: str, doc_id: str, source: str = "ocr") -> Invoice:
    """Build a typed Invoice from raw OCR/plain text."""
    f = parse_invoice_fields(text)

    def amt(key: str) -> Decimal | None:
        v = f[key].value
        return Decimal(v) if v else None

    invoice = Invoice(
        id=doc_id,
        source=source,
        currency=detect_currency_text(text) or "BGN",
        number=f["number"].value,
        date=f["date"].value,
        supplier=Party(
            name=f["supplier_name"].value,
            vat_number=f["supplier_vat"].value,
            eik=f["supplier_eik"].value,
        ),
        recipient=Party(
            name=f["recipient_name"].value,
            vat_number=f["recipient_vat"].value,
        ),
        net_amount=amt("net_amount"),
        vat_amount=amt("vat_amount"),
        total_amount=amt("total_amount"),
        field_confidence={k: v.confidence for k, v in f.items()},
        doc_type=detect_document_type(text).value,
        direction=detect_direction(text).value,
        reverse_charge=detect_reverse_charge(text),
    )

    # Recover the total from the "Словом:" words line when the numeric one is garbled.
    if invoice.total_amount is None:
        words_total = total_from_words(text)
        if words_total is not None:
            invoice.total_amount = words_total
            invoice.field_confidence["total_amount"] = _LOW

    # Fill in the missing leg when two of net/VAT/total are known.
    net, vat, total = invoice.net_amount, invoice.vat_amount, invoice.total_amount
    if total is None and net is not None and vat is not None:
        invoice.total_amount = net + vat
    elif net is None and total is not None and vat is not None:
        invoice.net_amount = total - vat
    elif vat is None and total is not None and net is not None:
        invoice.vat_amount = total - net

    # Derive a VAT tax line when we have base + amount.
    if invoice.net_amount and invoice.vat_amount and invoice.net_amount > 0:
        rate = (invoice.vat_amount / invoice.net_amount).quantize(Decimal("0.01"))
        invoice.tax_lines.append(
            TaxLine(rate=rate, base=invoice.net_amount, amount=invoice.vat_amount)
        )
    return tag_company(invoice)
