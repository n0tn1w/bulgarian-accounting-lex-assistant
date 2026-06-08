import pytest

from app.domain import Invoice, Party
from app.services.workspace import store_invoices
from invoice_rag.agent.tools import make_invoice_dispatch as make_dispatch


def _inv(ext, vendor, total, date="2026-03-10", currency="BGN"):
    return Invoice(id=ext, number=ext, date=date, currency=currency,
                   supplier=Party(name=vendor), total_amount=total)


@pytest.mark.db
def test_dispatch_sum_returns_total(tenant_db, tenant_id):
    store_invoices(tenant_db, tenant_id, [_inv("a", "AWS", 100), _inv("b", "AWS", 200)])
    tenant_db.flush()
    dispatch = make_dispatch(tenant_db, tenant_id)
    res = dispatch("sum_invoices", {"vendor": "AWS"})
    assert res["total_amount"] == 300.0 and res["count"] == 2


@pytest.mark.db
def test_dispatch_filter_returns_list(tenant_db, tenant_id):
    store_invoices(tenant_db, tenant_id, [_inv("a", "AWS", 6000), _inv("b", "OVH", 50)])
    tenant_db.flush()
    dispatch = make_dispatch(tenant_db, tenant_id)
    res = dispatch("filter_invoices", {"min_amount": 5000})
    assert isinstance(res, list) and [r["number"] for r in res] == ["a"]


@pytest.mark.db
def test_dispatch_bad_args_returns_error_not_raise(tenant_db, tenant_id):
    dispatch = make_dispatch(tenant_db, tenant_id)
    res = dispatch("sum_invoices", {"min_amount": "not-a-number"})
    assert "error" in res            # surfaced, not raised


@pytest.mark.db
def test_dispatch_unknown_tool_returns_error(tenant_db, tenant_id):
    dispatch = make_dispatch(tenant_db, tenant_id)
    assert "error" in dispatch("nope", {})
