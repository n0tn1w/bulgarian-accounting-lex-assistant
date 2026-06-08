import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import create_access_token
from app.db.base import admin_engine
from app.main import app


@pytest.fixture()
def auth_client():
    tid, uid = uuid.uuid4(), uuid.uuid4()
    with admin_engine.begin() as c:
        c.execute(text("INSERT INTO tenants (id, name) VALUES (:i,'t')"), {"i": str(tid)})
        c.execute(text("INSERT INTO users (id, tenant_id, email, password_hash, role) "
                       "VALUES (:u,:t,:e,'x','owner')"),
                  {"u": str(uid), "t": str(tid), "e": f"{uid}@t.io"})
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {create_access_token(str(uid), str(tid))}"})
    yield client, tid
    with admin_engine.begin() as c:
        c.execute(text("DELETE FROM stored_invoices WHERE tenant_id=:t"), {"t": str(tid)})
        c.execute(text("DELETE FROM users WHERE tenant_id=:t"), {"t": str(tid)})
        c.execute(text("DELETE FROM tenants WHERE id=:t"), {"t": str(tid)})


@pytest.mark.db
def test_chat_agent_returns_cards(auth_client, monkeypatch):
    client, _ = auth_client
    client.post("/workspace/invoices", json={"invoices": [
        {"id": "a", "number": "a", "date": "2026-03-01", "currency": "BGN",
         "supplier": {"name": "AWS"}, "total_amount": 120}]})

    # Patch the agent's LLM so the route needs no real model. Resolve the run
    # submodule via importlib (the package re-exports `run`, which would shadow
    # the submodule under plain attribute access).
    import importlib
    run_mod = importlib.import_module("app.rag.run")
    box = [
        {"content": None, "tool_calls": [
            {"id": "1", "type": "function",
             "function": {"name": "sum_invoices", "arguments": json.dumps({"vendor": "AWS"})}}]},
        {"content": "Total below.", "tool_calls": None},
    ]
    monkeypatch.setattr(run_mod, "litellm_complete", lambda messages, tools: box.pop(0))
    # ensure a model is "configured" so /chat takes the agent path
    monkeypatch.setenv("LLM_MODEL", "fake")
    from app.core import get_settings
    get_settings.cache_clear()

    r = client.post("/chat", json={"message": "how much on AWS?", "history": []})
    assert r.status_code == 200
    body = r.json()
    assert body["refused"] is False
    assert body["cards"][0]["type"] == "sum"
    assert body["cards"][0]["total_amount"] == 120.0
