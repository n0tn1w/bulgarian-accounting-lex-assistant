"""Bulgarian invoice field extraction from OCR/plain text.

Locale-aware regex for Фактура / ЕИК / ДДС / Доставчик / Получател etc., returning
each field with a confidence score and building a typed Invoice. A labelled-pattern
match scores ~0.9, a positional fallback ~0.5, a miss 0.0. The low scores are where
an LLM extraction fallback can kick in.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.core import get_settings
from app.domain import ExtractedField, Invoice, Party, TaxLine

from .bg_amount_words import total_from_words
from .company import tag_company
from .company_lookup import lookup_company
from .currency import detect_currency_text
from .document_types import (
    Direction,
    classify_document_type,
    detect_direction,
    detect_reverse_charge,
)
from .eik import validate_eik
from .ocr import normalize_token

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


_EIK_RE = re.compile(r"(?:ЕИК|ЕИН|БУЛСТАТ)\s*[:\-№]?\s*(\d{9}(?:\d{4})?)(?!\d)", re.IGNORECASE)


def _eik_list(text: str) -> list[str]:
    """EIKs in order of appearance (deduped). ЕИК / ЕИН / БУЛСТАТ are interchangeable
    labels for the company id (9 or 13 digits); the lookahead stops the match from
    swallowing an adjacent column's digits."""
    out: list[str] = []
    for m in _EIK_RE.findall(text):
        if m not in out:
            out.append(m)
    return out


def _all_eik(text: str) -> set[str]:
    return set(_eik_list(text))


def _all_vat(text: str) -> list[str]:
    # BG VAT is BG + exactly 9 or 10 digits; the lookahead prevents grabbing trailing
    # digits from an adjacent number (which would corrupt the company key).
    return [m.replace(" ", "").upper()
            for m in re.findall(r"BG\s*\d{9,10}(?!\d)", text, re.IGNORECASE)]


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
    # The legal-form suffix must be its own token (a space before it, a boundary after),
    # otherwise a short suffix like "ЕТ" would match inside a name such as "БЕТА".
    pat = rf"(?:{labels})\s*[:\-]?\s*([А-Яа-яA-Za-z0-9\s\-\"'.,]+?)\s+({_COMPANY_SUFFIX})\b"
    m = re.search(pat, text, re.IGNORECASE)
    if m:
        name = _clean_name(f"{m.group(1)} {m.group(2)}")
        return ExtractedField(value=name or None, confidence=_HIGH if name else 0.0)
    return ExtractedField(value=None, confidence=0.0)


_SUPPLIER_LABELS = "Доставчик|ДОСТАВЧИК|Продавач|Изпълнител"
_RECIPIENT_LABELS = "Получател|ПОЛУЧАТЕЛ|Купувач|Клиент"


def extract_supplier_name(text: str) -> ExtractedField:
    return _extract_party_name(text, _SUPPLIER_LABELS)


def extract_recipient_name(text: str) -> ExtractedField:
    return _extract_party_name(text, _RECIPIENT_LABELS)


def _split_party_blocks(text: str) -> tuple[str, str]:
    """Split the document into the supplier and recipient sections by their role labels.

    Handles either ordering on the page; returns ("", "") for a block that has no label.
    """
    sup = re.search(_SUPPLIER_LABELS, text, re.IGNORECASE)
    rec = re.search(_RECIPIENT_LABELS, text, re.IGNORECASE)
    if sup and rec:
        if sup.start() < rec.start():
            return text[sup.start():rec.start()], text[rec.start():]
        return text[sup.start():], text[rec.start():sup.start()]
    if sup:
        return text[sup.start():], ""
    if rec:
        return "", text[rec.start():]
    return "", ""


def _assign_owners(
    sup_block: str, rec_block: str, all_values: list[str], finder
) -> tuple[str | None, str | None]:
    """Assign extracted values (EIKs/VATs) to supplier vs recipient by block, with a
    global best-effort fallback when the sections didn't separate them."""
    sup = next(iter(finder(sup_block)), None)
    rec = next(iter(finder(rec_block)), None)
    if sup is None and rec is None and all_values:
        sup = all_values[0]
        rec = all_values[1] if len(all_values) > 1 else None
    elif sup is None and rec is not None:
        sup = next((v for v in all_values if v != rec), None)
    elif rec is None and sup is not None:
        rec = next((v for v in all_values if v != sup), None)
    return sup, rec


def _apply_low_conf(field: ExtractedField, low_conf_tokens: set[str] | None) -> ExtractedField:
    """Down-weight a captured field if any of its words were recognised with low OCR
    confidence, so recovery (register / vision) knows to revisit it."""
    if not low_conf_tokens or not field.value:
        return field
    tokens = {normalize_token(t) for t in field.value.split()}
    if tokens & low_conf_tokens:
        field.confidence = min(field.confidence, _LOW)
    return field


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


def parse_invoice_fields(
    text: str, low_conf_tokens: set[str] | None = None
) -> dict[str, ExtractedField]:
    """Extract all known fields with confidence. Keys are stable field names.

    Each party's name/VAT/EIK is read from its own block so a single party never mixes
    two companies' data; names fall back to a whole-document scan when a block is empty.
    """
    sup_block, rec_block = _split_party_blocks(text)

    fields = {
        "number": extract_invoice_number(text),
        "date": extract_date(text),
        "supplier_name": _apply_low_conf(extract_supplier_name(sup_block or text), low_conf_tokens),
        "recipient_name": _apply_low_conf(extract_recipient_name(rec_block or text), low_conf_tokens),
        "net_amount": extract_net_amount(text),
        "vat_amount": extract_vat_amount(text),
        "total_amount": extract_total_amount(text),
    }

    sup_vat, rec_vat = _assign_owners(sup_block, rec_block, _all_vat(text), _all_vat)
    fields["supplier_vat"] = ExtractedField(value=sup_vat, confidence=_LOW if sup_vat else 0.0)
    fields["recipient_vat"] = ExtractedField(value=rec_vat, confidence=_LOW if rec_vat else 0.0)

    sup_eik, rec_eik = _assign_owners(sup_block, rec_block, _eik_list(text), _eik_list)
    fields["supplier_eik"] = ExtractedField(value=sup_eik, confidence=_HIGH if sup_eik else 0.0)
    fields["recipient_eik"] = ExtractedField(value=rec_eik, confidence=_HIGH if rec_eik else 0.0)
    return fields


def resolve_perspective(perspective: str, direction: str) -> str:
    """Resolve the party-of-interest. "auto" follows the VAT direction; an explicit
    "supplier"/"recipient" is kept as-is."""
    if perspective in ("supplier", "recipient"):
        return perspective
    if direction == Direction.SALE.value:
        return "supplier"
    if direction == Direction.PURCHASE.value:
        return "recipient"
    return "supplier"


def swap_parties(invoice: Invoice) -> Invoice:
    """Swap supplier and recipient, including their per-field confidences. Used as the
    manual override when the roles were captured the wrong way round."""
    invoice.supplier, invoice.recipient = invoice.recipient, invoice.supplier
    fc = invoice.field_confidence
    for a, b in (
        ("supplier_name", "recipient_name"),
        ("supplier_vat", "recipient_vat"),
        ("supplier_eik", "recipient_eik"),
    ):
        if a in fc or b in fc:
            fc[a], fc[b] = fc.get(b, 0.0), fc.get(a, 0.0)
    return invoice


def recover_parties(invoice: Invoice) -> Invoice:
    """Fill or correct counterparty fields from the commercial register, keyed by a
    checksum-valid EIK. A name is overridden only when missing or low-confidence, so a
    clean reading from the document is trusted over the register."""
    if not get_settings().company_lookup_enabled:
        return invoice
    for party, name_key, vat_key in (
        (invoice.supplier, "supplier_name", "supplier_vat"),
        (invoice.recipient, "recipient_name", "recipient_vat"),
    ):
        if not validate_eik(party.eik or ""):
            continue
        info = lookup_company(party.eik)
        if info is None:
            continue
        recovered: list[str] = []
        name_conf = invoice.field_confidence.get(name_key, 0.0)
        if info.name and (not party.name or name_conf < _HIGH):
            party.name = info.name
            invoice.field_confidence[name_key] = 0.95
            recovered.append("name")
        if info.vat_number and not party.vat_number:
            party.vat_number = info.vat_number
            invoice.field_confidence[vat_key] = 0.95
            recovered.append("vat_number")
        if info.address_line1 and not party.address:
            party.address = info.address_line1
            recovered.append("address")
        if recovered:
            party.source = "merged"
            party.recovered_fields = recovered
    return invoice


def extract_invoice_from_text(
    text: str,
    doc_id: str,
    source: str = "ocr",
    *,
    perspective: str = "auto",
    low_conf_tokens: set[str] | None = None,
) -> Invoice:
    """Build a typed Invoice from raw OCR/plain text."""
    f = parse_invoice_fields(text, low_conf_tokens)

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
            eik=f["recipient_eik"].value,
        ),
        net_amount=amt("net_amount"),
        vat_amount=amt("vat_amount"),
        total_amount=amt("total_amount"),
        field_confidence={k: v.confidence for k, v in f.items()},
        doc_type=classify_document_type(text).value,
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

    invoice.perspective = resolve_perspective(perspective, invoice.direction)
    recover_parties(invoice)
    return tag_company(invoice)
