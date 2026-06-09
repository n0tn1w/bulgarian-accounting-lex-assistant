from decimal import Decimal

import pytest

from app.core import get_settings


def _clear():
    get_settings.cache_clear()


def test_amount_candidates_features():
    from app.tools.ingest import candidates as C

    text = "Данъчна основа: 100.00\nРазмер на данъка: 20.00\nОБЩА СТОЙНОСТ: 120.00"
    cands = C.amount_candidates(text)
    vals = [str(c.value) for c in cands]
    assert {"100.00", "20.00", "120.00"} <= set(vals)
    largest = [c for c in cands if c.features()["is_largest"] == 1.0]
    assert largest and str(largest[0].value) == "120.00"
    total = next(c for c in cands if str(c.value) == "120.00")
    assert total.features().get("w:обща") == 1.0  # label context captured


def test_party_candidates():
    from app.tools.ingest import candidates as C

    text = "Доставчик: АЛФА ООД ЕИК: 000694037 ДДС: BG000694037\nПолучател: БЕТА ЕООД"
    cands = C.party_candidates(text)
    by_name = {c.name: c for c in cands}
    assert "АЛФА ООД" in by_name and by_name["АЛФА ООД"].label == "доставчик"
    assert by_name["АЛФА ООД"].eik == "000694037"


def test_selector_value_is_verbatim(tmp_path, monkeypatch):
    pytest.importorskip("sklearn")
    from app.tools.ingest import candidates as C
    from app.tools.ingest import field_models as FM

    docs = [
        ("Данъчна основа 100.00 Размер на данъка 20.00 ОБЩА СТОЙНОСТ 120.00", ("100.00", "20.00", "120.00")),
        ("Данъчна основа 50.00 Размер на данъка 10.00 ОБЩА СТОЙНОСТ 60.00", ("50.00", "10.00", "60.00")),
        ("Данъчна основа 200.00 Размер на данъка 40.00 ОБЩА СТОЙНОСТ 240.00", ("200.00", "40.00", "240.00")),
    ]
    rows, labels = [], []
    for d, (n, v, t) in docs:
        for c in C.amount_candidates(d):
            cls = ("net" if c.value == Decimal(n) else "vat" if c.value == Decimal(v)
                   else "total" if c.value == Decimal(t) else "none")
            rows.append(c.features()); labels.append(cls)
    model = FM.build_selector(); model.fit(rows, labels)
    FM.save_selector(model, "amounts", tmp_path)

    monkeypatch.setenv("FIELD_MODELS_DIR", str(tmp_path))
    monkeypatch.setenv("FIELD_MODELS_ENABLED", "true")
    _clear(); FM.reset()

    target = "Данъчна основа 77.00 Размер на данъка 15.40 ОБЩА СТОЙНОСТ 92.40"
    sel = FM.select_amounts(target)
    cand_vals = {str(c.value) for c in C.amount_candidates(target)}
    assert sel, "selector should pick at least one amount"
    # every selected value is a verbatim candidate from the document (never invented)
    assert all(v in cand_vals for v in sel.values())
    FM.reset()


def test_runtime_override_only_when_weak(monkeypatch):
    from app.domain import ExtractedField, Invoice, Party
    from app.tools.ingest import field_models, invoice_extractor as ie

    monkeypatch.setattr(field_models, "available", lambda: True)
    monkeypatch.setattr(field_models, "select_amounts", lambda t: {"total": "999.00"})
    monkeypatch.setattr(field_models, "select_parties", lambda t: {})
    monkeypatch.setattr(field_models, "select_number", lambda t, e=None: None)
    monkeypatch.setattr(field_models, "select_date", lambda t: None)
    monkeypatch.setattr(field_models, "select_direction", lambda t: None)

    inv = Invoice(id="d", supplier=Party(), recipient=Party())
    inv.total_amount = Decimal("120.00")
    f = {k: ExtractedField(confidence=0.9) for k in
         ("net_amount", "vat_amount", "total_amount", "supplier_name", "recipient_name", "number", "date")}

    ie._apply_field_models(inv, "text", f)
    assert str(inv.total_amount) == "120.00"  # high-confidence total kept

    f["total_amount"] = ExtractedField(confidence=0.5)
    ie._apply_field_models(inv, "text", f)
    assert str(inv.total_amount) == "999.00"  # weak -> overridden with the verbatim pick


def test_no_models_means_unchanged(tmp_path, monkeypatch):
    from app.tools.ingest import field_models as FM

    monkeypatch.setenv("FIELD_MODELS_DIR", str(tmp_path))  # empty dir, no artifacts
    monkeypatch.setenv("FIELD_MODELS_ENABLED", "true")
    _clear(); FM.reset()
    assert FM.available() is False
    assert FM.select_amounts("ОБЩА СТОЙНОСТ 10.00") == {}
    FM.reset()
