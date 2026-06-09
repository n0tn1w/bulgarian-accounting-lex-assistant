import pytest

from app.core import get_settings
from app.domain import CompanyInfo
from app.tools.ingest import company_lookup as cl
from app.tools.ingest import invoice_extractor as ie

CANNED_HTML = """<html><body>
<h1>АЛФА ТРЕЙД</h1>
<div>Правна форма</div><div class="value">Дружество с ограничена отговорност</div>
<div>Адрес</div><div class="value">БЪЛГАРИЯ, гр. София, 1000, ул. Тест 1</div>
<div>Актуален статус на лицето</div><div class="value">Действащ</div>
<div class="col-md-4"><div class="text-right">ДДС: Да</div></div>
</body></html>"""


@pytest.fixture(autouse=True)
def _fresh():
    cl._cache.clear()
    get_settings.cache_clear()
    yield
    cl._cache.clear()
    get_settings.cache_clear()


def test_invalid_eik_short_circuits_without_network(monkeypatch):
    calls = {"n": 0}

    def boom(eik, settings):
        calls["n"] += 1

    monkeypatch.setattr(cl, "_scrape", boom)
    assert cl.lookup_company("123456789") is None  # checksum fails
    assert calls["n"] == 0


def test_disabled_returns_none(monkeypatch):
    monkeypatch.setenv("COMPANY_LOOKUP_ENABLED", "false")
    get_settings.cache_clear()
    monkeypatch.setattr(cl, "_scrape", lambda e, s: CompanyInfo(eik=e, name="X"))
    assert cl.lookup_company("000694037") is None


def test_parses_canned_html(monkeypatch):
    if not cl._LOOKUP_IMPORTED:
        pytest.skip("requests/bs4 not installed")

    class _Resp:
        status_code = 200
        text = CANNED_HTML

    monkeypatch.setenv("COMPANY_LOOKUP_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(cl.requests, "get", lambda *a, **k: _Resp())
    info = cl.lookup_company("000694037")
    assert info is not None
    assert info.name == "АЛФА ТРЕЙД ООД"
    assert info.vat_number == "BG000694037"  # "Да" flag -> standard BG+EIK
    assert info.city == "гр. София"
    assert info.status == "Действащ"


def test_recovery_fills_missing_name(monkeypatch):
    monkeypatch.setenv("COMPANY_LOOKUP_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(
        ie,
        "lookup_company",
        lambda eik: CompanyInfo(eik=eik, name="АЛФА ТРЕЙД ЕООД", vat_number="BG000694037"),
    )
    inv = ie.extract_invoice_from_text(
        "Доставчик:\nЕИК: 000694037\nОбща стойност: 1.00", "d", "ocr"
    )
    assert inv.supplier.name == "АЛФА ТРЕЙД ЕООД"
    assert inv.supplier.source == "merged"
    assert "name" in inv.supplier.recovered_fields
    assert inv.field_confidence["supplier_name"] == pytest.approx(0.95)
