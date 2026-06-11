"""Guard Phase-1 eval labels against drift.

Every non-compliance / non-refuse case in eval_set.jsonl MUST pass _run_case().
If a future fixture or label change breaks any case this test catches it.

DB-session setup mirrors test_seed_eval_tenant.py exactly:
  - admin_engine inserts the eval tenant row (bypasses RLS)
  - SessionLocal opens an app-role session
  - set_config scopes the session to EVAL_TENANT_ID
  - rollback + admin DELETE at teardown so the fixed EVAL_TENANT_ID can be re-used
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.db.base import SessionLocal, admin_engine
from eval.cases import load_cases
from eval.fixtures.invoices import EVAL_TENANT_ID
from eval.run_eval import _run_case
from invoice_rag.indexing.sparse import Bm25InvoiceIndex
from scripts.seed_eval_tenant import seed

EVAL_PATH = "eval/eval_set.jsonl"
SKIP_CATEGORIES = {"compliance", "refuse"}


@pytest.fixture()
def eval_tenant_db():
    """Create the eval tenant row as admin, yield an app-role session scoped to it,
    then clean up everything so the test is fully isolated."""
    tid = str(EVAL_TENANT_ID)
    with admin_engine.begin() as conn:
        # idempotent: delete any leftover row from a previous interrupted run
        conn.execute(text("DELETE FROM stored_invoices WHERE tenant_id = :t"), {"t": tid})
        conn.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})
        conn.execute(
            text("INSERT INTO tenants (id, name) VALUES (:id, :name)"),
            {"id": tid, "name": "eval"},
        )
    db = SessionLocal()
    db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tid},
    )
    try:
        yield db
    finally:
        db.rollback()
        db.close()
        with admin_engine.begin() as conn:
            conn.execute(text("DELETE FROM stored_invoices WHERE tenant_id = :t"), {"t": tid})
            conn.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})
        Bm25InvoiceIndex.path_for(tid).unlink(missing_ok=True)


@pytest.mark.db
def test_phase1_all_cases_pass(eval_tenant_db):
    """Seed the eval tenant (with dense embeddings) and assert every Phase-1
    case returns passed=True.  Compliance and refuse cases are excluded because
    they are Phase-2 (query_law / refusal) — they trivially return passed=True
    from _run_case already, but filtering them avoids confusion."""
    db = eval_tenant_db
    tid = str(EVAL_TENANT_ID)

    # seed() calls db.commit(), which ends the transaction and clears the
    # transaction-local set_config.  We re-scope afterwards (same pattern as
    # test_seed_eval_tenant.py::test_seed_stores_60_rows).
    seed(db, embed=True)
    db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tid},
    )

    cases = [c for c in load_cases(EVAL_PATH) if c.category not in SKIP_CATEGORIES]

    failures = [
        r
        for c in cases
        if not (r := _run_case(db, uuid.UUID(tid), c))["passed"]
    ]

    assert not failures, (
        f"{len(failures)} Phase-1 case(s) failed:\n"
        + "\n".join(
            f"  id={r['id']} category={r['category']} metric={r['metric']} value={r['value']}"
            for r in failures
        )
    )
