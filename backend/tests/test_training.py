import json
from decimal import Decimal

import pytest

from app.core import get_settings


def _clear():
    get_settings.cache_clear()


# --- doc-type classifier (assist-only) ---

def test_classifier_train_predict_roundtrip(tmp_path, monkeypatch):
    pytest.importorskip("sklearn")
    from app.tools.ingest import classifier

    texts = (
        ["фактура номер дата доставчик получател обща стойност"] * 4
        + ["касов бон фискално устройство касова бележка сума"] * 4
        + ["банково извлечение IBAN начално салдо крайно салдо"] * 4
    )
    labels = ["invoice"] * 4 + ["fiscal_receipt"] * 4 + ["bank_statement"] * 4
    model = classifier.train(texts, labels)
    out = tmp_path / "doctype.joblib"
    classifier.save(model, out)

    monkeypatch.setenv("DOCTYPE_MODEL_PATH", str(out))
    _clear()
    classifier.reset()
    pred = classifier.predict("касов бон фискално устройство, обща сума 12.00")
    assert pred and pred[0] == "fiscal_receipt" and pred[1] > 0.4
    classifier.reset()


def test_classifier_assists_only_on_other(monkeypatch):
    from app.tools.ingest import document_types as dt

    monkeypatch.setattr("app.tools.ingest.classifier.predict", lambda t: ("bank_statement", 0.99))
    monkeypatch.setenv("DOCTYPE_CLASSIFIER_ENABLED", "true")
    _clear()
    # decisive keyword wins, model ignored
    assert dt.classify_document_type("Стандартна митническа декларация") is dt.DocumentType.CUSTOMS_DECLARATION
    # keyword OTHER + confident model -> model label
    assert dt.classify_document_type("случаен текст без ключови думи") is dt.DocumentType.BANK_STATEMENT
    # low confidence -> stays OTHER
    monkeypatch.setattr("app.tools.ingest.classifier.predict", lambda t: ("bank_statement", 0.30))
    assert dt.classify_document_type("случаен текст без ключови думи") is dt.DocumentType.OTHER


# --- LLM assist: fills non-amount fields, never amounts ---

def test_llm_assist_fills_nonamount_leaves_amounts(monkeypatch):
    from app.domain import Invoice, Party
    from app.tools.ingest import llm_assist as la

    monkeypatch.setenv("LLM_ASSIST_ENABLED", "true")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "ollama/mistral")
    _clear()

    fake = lambda messages: '{"supplier_name":"АЛФА ООД","supplier_eik":"000694037","total_amount":"999.00"}'
    fields = la.assist_fields("some garbled text", "invoice", complete=fake)
    assert fields["supplier_name"].value == "АЛФА ООД"
    assert "total_amount" not in fields  # amounts are never returned for override

    inv = Invoice(id="d", supplier=Party(), recipient=Party())
    inv.net_amount, inv.total_amount = Decimal("100"), Decimal("120")
    inv.field_confidence = {"supplier_name": 0.0}
    la.merge_fields(inv, fields)
    assert inv.supplier.name == "АЛФА ООД" and inv.supplier.eik == "000694037"
    assert inv.total_amount == Decimal("120")  # untouched


def test_llm_assist_noop_without_model(monkeypatch):
    from app.tools.ingest import llm_assist as la

    monkeypatch.setenv("LLM_ASSIST_ENABLED", "true")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("LLM_FALLBACK_ENABLED", "false")
    _clear()
    assert la.is_available() is False
    assert la.assist_fields("text", "invoice", complete=lambda m: "{}") is None


# --- eval harness on a tiny synthetic dataset ---

def test_eval_harness_synthetic(tmp_path, monkeypatch):
    monkeypatch.setenv("PREPROCESSING_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("COMPANY_LOOKUP_ENABLED", "false")
    monkeypatch.setenv("LLM_ASSIST_ENABLED", "false")
    _clear()

    (tmp_path / "a.txt").write_text(
        "ФАКТУРА № 100\nДоставчик: АЛФА ООД\nЕИК: 000694037\n"
        "Получател: БЕТА ЕООД\nЕИК: 131272596\nОбща стойност: 120.00",
        encoding="utf-8",
    )
    (tmp_path / "a.label.json").write_text(json.dumps({
        "doc_type": "invoice", "number": "100",
        "supplier": {"name": "АЛФА ООД", "eik": "000694037"},
        "recipient": {"name": "БЕТА ЕООД", "eik": "131272596"},
    }), encoding="utf-8")

    from training.dataset import load_dataset
    from training.evaluate import evaluate

    examples = load_dataset(tmp_path)
    assert len(examples) == 1
    rep = evaluate(examples)
    assert rep.n == 1
    assert rep.doc_type_correct == 1
    assert rep.supplier.matched == 1   # АЛФА correctly the supplier
    assert rep.recipient.matched == 1  # БЕТА correctly the recipient
    assert rep.swaps == 0
