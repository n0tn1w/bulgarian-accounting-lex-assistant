"""Seed the evaluation tenant with the 60 synthetic fixture invoices and build indexes.

Usage:
    python scripts/seed_eval_tenant.py

Idempotent: the tenant row is created if it does not exist (admin role bypasses RLS),
then store_invoices upserts the 60 invoices (delete-then-insert by external_id) and
rebuilds the per-tenant BM25 index. Optionally recomputes dense BGE-M3 embeddings
(slow, ~2 GB model load — skip with embed=False for unit/integration tests).
"""
from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.base import SessionLocal, admin_engine
from app.services.workspace import store_invoices
from eval.fixtures.invoices import EVAL_TENANT_ID, build_fixture_invoices


def _ensure_tenant(tenant_id: uuid.UUID, name: str = "eval") -> None:
    """Insert the tenant row if it does not already exist (runs as admin, bypasses RLS)."""
    with admin_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO tenants (id, name) VALUES (:id, :name) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": str(tenant_id), "name": name},
        )


def seed(db: Session, embed: bool = True) -> int:
    """Seed the eval tenant and optionally build dense embeddings.

    Parameters
    ----------
    db:
        A tenant-scoped SQLAlchemy session. The caller is responsible for setting
        ``app.current_tenant`` on this session before calling ``seed()``, or for
        passing a session that has not yet had the tenant configured (in which case
        this function sets it).
    embed:
        If True (default) call ``reembed_tenant`` to build BGE-M3 dense vectors.
        Set False to skip the ~2 GB model load during tests.

    Returns
    -------
    int
        Number of invoices stored (always 60).
    """
    # 1. Ensure the tenant row exists (admin path, bypasses RLS).
    _ensure_tenant(EVAL_TENANT_ID)

    # 2. Scope this session to the eval tenant so RLS allows the writes.
    db.execute(
        text("SELECT set_config('app.current_tenant', :t, true)"),
        {"t": str(EVAL_TENANT_ID)},
    )

    # 3. Upsert the 60 fixture invoices and rebuild BM25.
    count = store_invoices(db, EVAL_TENANT_ID, build_fixture_invoices())

    # 4. Optionally recompute dense (BGE-M3) embeddings.
    if embed:
        from invoice_rag.indexing.dense import reembed_tenant
        reembed_tenant(db)

    # 5. Commit everything.
    db.commit()

    return count


def main() -> None:
    """Open a session, seed the eval tenant, then close the session."""
    db = SessionLocal()
    try:
        n = seed(db, embed=True)
        print(f"Seeded eval tenant {EVAL_TENANT_ID} with {n} invoices.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
