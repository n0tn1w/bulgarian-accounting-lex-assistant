import json

import pytest

from app.domain import Invoice, Party
from app.services.workspace import store_invoices
from app.rag.run import run


def _inv(ext, vendor, total):
    return Invoice(id=ext, number=ext, date="2026-03-01", currency="BGN",
                   supplier=Party(name=vendor), total_amount=total)


def _script(*steps):
    """Return a fake `complete` that yields scripted messages in order."""
    box = list(steps)
    def complete(messages, tools):
        return box.pop(0)
    return complete


@pytest.mark.db
def test_run_routes_to_sum_and_builds_card(tenant_db, tenant_id):
    store_invoices(tenant_db, tenant_id, [_inv("a", "AWS", 100), _inv("b", "AWS", 200)])
    tenant_db.flush()
    fake = _script(
        {"content": None, "tool_calls": [
            {"id": "1", "type": "function",
             "function": {"name": "sum_invoices", "arguments": json.dumps({"vendor": "AWS"})}}]},
        {"content": "Your AWS total is shown below.", "tool_calls": None},
    )
    ans = run(tenant_db, tenant_id, "how much on AWS?", history=[], complete=fake, model="fake")
    assert ans.refused is False
    assert ans.cards[0]["type"] == "sum" and ans.cards[0]["total_amount"] == 300.0
    assert ans.tool_trace[0]["tool"] == "sum_invoices"


@pytest.mark.db
def test_run_refuses_when_no_tool_called(tenant_db, tenant_id):
    fake = _script({"content": "I can't judge a vendor's trustworthiness.", "tool_calls": None})
    ans = run(tenant_db, tenant_id, "is AWS trustworthy?", history=[], complete=fake, model="fake")
    assert ans.refused is True and ans.cards == []
