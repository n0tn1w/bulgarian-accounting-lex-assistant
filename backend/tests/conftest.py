"""Shared pytest fixtures.

`tenant_db` yields a tenant-scoped SQLAlchemy Session against the local Postgres
(infra/docker-compose.yml), mirroring app.api.deps.get_tenant_db: it creates a
throwaway tenant, sets app.current_tenant so RLS isolates it, and rolls back at
the end so tests never persist data.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.db import init_db
from app.db.base import SessionLocal, admin_engine
from invoice_rag.indexing.sparse import Bm25InvoiceIndex


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_db():
    init_db()  # extension, tables, RLS, column migration


@pytest.fixture()
def tenant_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def tenant_db(tenant_id):
    # Insert the tenant as admin (bypasses RLS), then open an app-role session
    # scoped to it. Roll back everything at teardown.
    with admin_engine.begin() as conn:
        conn.execute(
            text("INSERT INTO tenants (id, name) VALUES (:id, :name)"),
            {"id": str(tenant_id), "name": "test"},
        )
    db = SessionLocal()
    db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    try:
        yield db
    finally:
        db.rollback()
        db.close()
        with admin_engine.begin() as conn:
            conn.execute(text("DELETE FROM stored_invoices WHERE tenant_id = :t"), {"t": str(tenant_id)})
            conn.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": str(tenant_id)})
        Bm25InvoiceIndex.path_for(str(tenant_id)).unlink(missing_ok=True)
