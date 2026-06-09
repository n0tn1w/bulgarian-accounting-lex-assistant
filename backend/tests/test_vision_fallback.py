import pytest

from app.core import get_settings
from app.domain import Invoice, Party
from app.tools.ingest import vision_extract as ve

_FENCED = '```json\n{"number":"INV-9","supplier_name":"АЛФА ООД","total_amount":"120.00"}\n```'


@pytest.fixture(autouse=True)
def _fresh():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_no_model_is_noop(monkeypatch):
    monkeypatch.setenv("OCR_VISION_MODEL", "")
    monkeypatch.setenv("LLM_MODEL", "")
    get_settings.cache_clear()
    assert ve.extract_invoice_via_vision([b"x"], complete=lambda m, i: "{}") is None
    assert ve.should_use_vision(Invoice(id="d"), 0.0) is False


def test_parses_fenced_json(monkeypatch):
    monkeypatch.setenv("OCR_VISION_MODEL", "gpt-4o")
    get_settings.cache_clear()
    fields = ve.extract_invoice_via_vision([b"x"], complete=lambda m, i: _FENCED)
    assert fields["number"].value == "INV-9"
    assert fields["supplier_name"].value == "АЛФА ООД"


def test_merge_overrides_only_weak_fields():
    inv = Invoice(id="d", supplier=Party(), recipient=Party())
    inv.field_confidence = {"number": 0.9, "supplier_name": 0.5}
    inv.number = "KEEP"
    fields = {
        "number": __ef("INV-9"),
        "supplier_name": __ef("АЛФА ООД"),
        "total_amount": __ef("120.00"),
    }
    ve.merge_into_invoice(inv, fields)
    assert inv.number == "KEEP"  # clean high-confidence value preserved
    assert inv.supplier.name == "АЛФА ООД"  # weak value overridden
    assert inv.supplier.source == "vision"
    assert inv.total_amount is not None


def test_should_use_vision_on_low_mean_conf(monkeypatch):
    monkeypatch.setenv("OCR_VISION_MODEL", "gpt-4o")
    get_settings.cache_clear()
    assert ve.should_use_vision(Invoice(id="d"), 0.1) is True


def __ef(value):
    from app.domain import ExtractedField

    return ExtractedField(value=value, confidence=0.85)
