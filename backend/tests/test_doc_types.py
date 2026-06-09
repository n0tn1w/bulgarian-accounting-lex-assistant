from app.tools.ingest.document_types import (
    Direction,
    DocumentType,
    detect_direction,
    detect_document_type,
)
from app.tools.ingest.ocr import _looks_like_text


def test_plain_invoice():
    t = "ФАКТУРА № 1000000123\nДанъчна основа 100.00\nДоставчик: X ООД\nПолучател: Y ЕООД"
    assert detect_document_type(t) is DocumentType.INVOICE


def test_customs_with_primary_phrase():
    t = "A - за стандартна митническа декларация (по член 162). Обща фактурирана стойност"
    assert detect_document_type(t) is DocumentType.CUSTOMS_DECLARATION


def test_customs_not_confused_by_referenced_invoice():
    # A customs declaration references commercial invoices ("N380 Търговска фактура")
    # but must classify as customs, not invoice.
    t = (
        "Декларация за допускане за свободно обращение. N380 - Търговска фактура. "
        "Митническа стойност EUR 100. Вносител ДИЗМА ЕООД. Износител МИРО ЛТД."
    )
    assert detect_document_type(t) is DocumentType.CUSTOMS_DECLARATION


def test_customs_via_mrn_when_header_garbled():
    # No clean "митническа декларация" phrase; the MRN + secondary signals carry it.
    t = "Вдигане на стоки 26BG003009337276R6. Митническа стойност EUR 100. Износител X"
    assert detect_document_type(t) is DocumentType.CUSTOMS_DECLARATION


def test_import_declaration_is_purchase():
    t = "Декларация за допускане за свободно обращение. Незабавна продажба/покупка"
    assert detect_direction(t) is Direction.PURCHASE


def test_unknown_is_other():
    assert detect_document_type("Случаен текст без ключови думи тук") is DocumentType.OTHER


def test_looks_like_text_threshold():
    assert _looks_like_text("буква " * 60)       # real text layer
    assert not _looks_like_text("  \n\f  12 .  ")  # scanned PDF: almost no letters
