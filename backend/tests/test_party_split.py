import pytest

from app.tools.ingest import extract_invoice_from_text, parse_invoice_fields, swap_parties

TWO_PARTY = """ФАКТУРА № 1000000123
Доставчик: АЛФА ООД
ЕИК: 000694037
ДДС №: BG000694037
Получател: БЕТА ЕООД
ЕИК: 131272596
ДДС №: BG131272596
Обща стойност: 120.00"""


@pytest.fixture(autouse=True)
def _no_register(monkeypatch):
    monkeypatch.setattr("app.tools.ingest.invoice_extractor.lookup_company", lambda eik: None)
    # deterministic + independent of any locally-trained models
    monkeypatch.setattr("app.tools.ingest.classifier.predict", lambda text: None)
    monkeypatch.setattr("app.tools.ingest.field_models.available", lambda: False)


def test_both_eiks_assigned_by_block():
    f = parse_invoice_fields(TWO_PARTY)
    assert f["supplier_eik"].value == "000694037"
    assert f["recipient_eik"].value == "131272596"


def test_both_vats_assigned_by_block():
    f = parse_invoice_fields(TWO_PARTY)
    assert f["supplier_vat"].value == "BG000694037"
    assert f["recipient_vat"].value == "BG131272596"


def test_names_not_mangled_by_short_suffix():
    inv = extract_invoice_from_text(TWO_PARTY, "d", "manual")
    assert inv.supplier.name == "АЛФА ООД"
    assert inv.recipient.name == "БЕТА ЕООД"  # not "БЕТ" (the ЕТ suffix is a whole token)


def test_swap_round_trips():
    inv = extract_invoice_from_text(TWO_PARTY, "d", "manual")
    sup, rec = inv.supplier.name, inv.recipient.name
    swap_parties(inv)
    assert (inv.supplier.name, inv.recipient.name) == (rec, sup)
    swap_parties(inv)
    assert (inv.supplier.name, inv.recipient.name) == (sup, rec)


def test_low_conf_token_lowers_name_confidence():
    f = parse_invoice_fields(TWO_PARTY, low_conf_tokens={"алфа"})
    assert f["supplier_name"].confidence <= 0.5


def test_auto_perspective_follows_direction():
    sale = TWO_PARTY + "\nпродажба"
    purchase = TWO_PARTY + "\nпокупка"
    assert extract_invoice_from_text(sale, "d", "manual").perspective == "supplier"
    assert extract_invoice_from_text(purchase, "d", "manual").perspective == "recipient"
