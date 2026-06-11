"""Integration test for seed_eval_tenant.seed().

Uses the same DB-session pattern as conftest.py:
  - admin_engine inserts the eval tenant row (bypasses RLS)
  - SessionLocal opens an app-role session
  - set_config sets app.current_tenant so RLS allows the writes
  - rollback + admin DELETE at teardown so the fixed EVAL_TENANT_ID can be re-used

`embed=False` skips the slow BGE-M3 model load; dense vectors are left NULL.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.base import SessionLocal, admin_engine
from app.db.models import StoredInvoice
from eval.fixtures.invoices import EVAL_TENANT_ID
from invoice_rag.indexing.sparse import Bm25InvoiceIndex
from scripts.seed_eval_tenant import seed


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
def test_seed_returns_60(eval_tenant_db):
    count = seed(eval_tenant_db, embed=False)
    assert count == 60


@pytest.mark.db
def test_seed_stores_60_rows(eval_tenant_db):
    seed(eval_tenant_db, embed=False)
    # seed() calls db.commit(), which ends the transaction and clears the
    # transaction-local set_config. Re-scope to the eval tenant for the count.
    eval_tenant_db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(EVAL_TENANT_ID)},
    )
    assert eval_tenant_db.query(StoredInvoice).count() == 60
