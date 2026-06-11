"""Re-embed invoices (BGE-M3) and rebuild the per-tenant BM25 index from the DB.

Usage:
    python scripts/rebuild_invoice_index.py <tenant_uuid>
Runs as the app role with app.current_tenant set, so RLS scopes the work.
"""
from __future__ import annotations

import sys
import uuid

from sqlalchemy import text

from app.db.base import SessionLocal
from invoice_rag.indexing.dense import reembed_tenant
from invoice_rag.indexing.pipeline import build_bm25_for_tenant


def main(tenant_id: str) -> None:
    tid = uuid.UUID(tenant_id)
    db = SessionLocal()
    try:
        db.execute(text("SELECT set_config('app.current_tenant', :t, true)"), {"t": tenant_id})
        n = reembed_tenant(db)
        build_bm25_for_tenant(db, tid)
        db.commit()
        print(f"re-embedded {n} invoices and rebuilt BM25 for tenant {tenant_id}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/rebuild_invoice_index.py <tenant_uuid>")
    main(sys.argv[1])
