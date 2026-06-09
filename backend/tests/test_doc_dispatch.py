import pytest

from app.tools.ingest import extract_document, extract_invoice_from_text


@pytest.fixture(autouse=True)
def _no_register(monkeypatch):
    monkeypatch.setattr("app.tools.ingest.invoice_extractor.lookup_company", lambda eik: None)
    # keep extraction deterministic/offline + independent of any locally-trained model:
    # no register lookup, no LLM assist, no doc-type classifier.
    monkeypatch.setattr("app.tools.ingest.extract.should_assist", lambda inv: False)
    monkeypatch.setattr("app.tools.ingest.classifier.predict", lambda text: None)
    monkeypatch.setattr("app.tools.ingest.field_models.available", lambda: False)


def test_invoice_family_matches_invoice_extractor():
    text = "ФАКТУРА № 1000000123\nДоставчик: АЛФА ООД\nЕИК: 000694037\nОбща стойност: 120.00"
    assert (
        extract_document(text, "d", "manual").model_dump()
        == extract_invoice_from_text(text, "d", "manual").model_dump()
    )


def test_fiscal_receipt():
    inv = extract_document("КАСОВ БОН\nФУ ED123456\nОбща стойност: 12.00", "r", "ocr")
    assert inv.doc_type == "fiscal_receipt"
    assert inv.extra.get("fiscal_device") == "ED123456"


def test_bank_statement():
    inv = extract_document(
        "БАНКОВО ИЗВЛЕЧЕНИЕ\nIBAN: BG80BNBG96611020345678\n"
        "Начално салдо: 100.00\nКрайно салдо: 250.00",
        "b",
        "ocr",
    )
    assert inv.doc_type == "bank_statement"
    assert inv.extra.get("iban") == "BG80BNBG96611020345678"
    assert inv.extra.get("closing_balance") == "250.00"


def test_customs_declaration():
    inv = extract_document("МИТНИЧЕСКА ДЕКЛАРАЦИЯ\nMRN: 24BG00123456789012", "c", "ocr")
    assert inv.doc_type == "customs_declaration"
    assert inv.extra.get("mrn") == "24BG00123456789012"


def test_protocol_reverse_charge():
    inv = extract_document(
        "ПРОТОКОЛ по чл. 117 ЗДДС\nобратно начисляване\nОбща стойност: 1000.00", "p", "ocr"
    )
    assert inv.doc_type == "protocol"
    assert inv.reverse_charge is True
    assert inv.extra.get("article") == "чл. 117"


def test_unknown_falls_back_to_generic():
    inv = extract_document("Случаен документ\nДата: 01.01.2026", "o", "ocr")
    assert inv.doc_type == "other"
    assert inv.date == "2026-01-01"  # generic still reads common fields
