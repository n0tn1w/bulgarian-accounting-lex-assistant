"""Detection of Bulgarian accounting document types and VAT direction."""

from __future__ import annotations

from enum import Enum


class DocumentType(str, Enum):
    INVOICE = "invoice"                      # Фактура
    CREDIT_NOTE = "credit_note"              # Кредитно известие
    DEBIT_NOTE = "debit_note"                # Дебитно известие
    PROFORMA = "proforma"                    # Проформа фактура
    SIMPLIFIED_INVOICE = "simplified_invoice"  # Опростена фактура
    PROTOCOL = "protocol"                    # Протокол (напр. по чл. 117 ЗДДС)
    FISCAL_RECEIPT = "fiscal_receipt"        # Касов / фискален бон
    CUSTOMS_DECLARATION = "customs_declaration"  # Митническа декларация
    BANK_STATEMENT = "bank_statement"        # Банково извлечение
    GOODS_RECEIPT = "goods_receipt"          # Стокова / складова разписка
    EXPENSE_REPORT = "expense_report"        # Авансов отчет
    OTHER = "other"


class Direction(str, Enum):
    SALE = "sale"          # Продажба (издадена) - изходящо ДДС
    PURCHASE = "purchase"  # Покупка (получена) - входящо ДДС
    UNKNOWN = "unknown"


# most specific first; credit/debit notes and proformas also contain "фактура"
_TYPE_KEYWORDS: list[tuple[DocumentType, tuple[str, ...]]] = [
    (DocumentType.CREDIT_NOTE, ("кредитно известие", "кредитно изв", "credit note")),
    (DocumentType.DEBIT_NOTE, ("дебитно известие", "дебитно изв", "debit note")),
    (DocumentType.PROFORMA, ("проформа", "pro-forma", "proforma")),
    (DocumentType.SIMPLIFIED_INVOICE, ("опростена фактура",)),
    (DocumentType.PROTOCOL, ("протокол по чл", "протокол №", "протокол no", "protocol")),
    (DocumentType.FISCAL_RECEIPT,
     ("фискален бон", "касов бон", "касова бележка", "фискална касова", "fiscal receipt")),
    (DocumentType.CUSTOMS_DECLARATION,
     ("митническа декларация", "single administrative document", "ескд", "mrn")),
    (DocumentType.BANK_STATEMENT,
     ("банково извлечение", "извлечение по сметка", "движение по сметка", "bank statement")),
    (DocumentType.GOODS_RECEIPT,
     ("стокова разписка", "складова разписка", "delivery note", "приемо-предавателен")),
    (DocumentType.EXPENSE_REPORT, ("авансов отчет", "отчет за разходи", "expense report")),
    (DocumentType.INVOICE, ("фактура", "ф-ра", "invoice", "факт. №")),
]

_SALE_HINTS = ("продажб", "prodajb", "издадена фактура", "издадени фактури", "изх. фактура", "sales")
_PURCHASE_HINTS = ("покупк", "pokupk", "получена фактура", "получени фактури", "вх. фактура", "purchase")
_REVERSE_CHARGE = (
    "чл. 117", "чл.117", "чл 117", "чл. 163", "чл.163",
    "обратно начисляване", "обратно начисление", "reverse charge",
    "вътреобщностно придобиване",
)


def detect_document_type(text: str) -> DocumentType:
    t = (text or "").lower()
    for doc_type, keywords in _TYPE_KEYWORDS:
        if any(k in t for k in keywords):
            return doc_type
    return DocumentType.OTHER


def detect_direction(text: str, hint: str = "") -> Direction:
    t = f"{text or ''} {hint or ''}".lower()
    if any(k in t for k in _SALE_HINTS):
        return Direction.SALE
    if any(k in t for k in _PURCHASE_HINTS):
        return Direction.PURCHASE
    return Direction.UNKNOWN


def detect_reverse_charge(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in _REVERSE_CHARGE)
