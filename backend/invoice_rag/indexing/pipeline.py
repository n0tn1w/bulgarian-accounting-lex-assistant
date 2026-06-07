"""Build the per-tenant BM25 index from the DB.

The dense vectors live in stored_invoices.embedding (written at store time by
app.services.workspace). This module (re)builds the sparse index from the same
canonical invoice_to_text. reembed_tenant lives in invoice_rag.indexing.dense.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import StoredInvoice
from app.domain import Invoice
from invoice_rag.indexing.sparse import Bm25InvoiceIndex
from invoice_rag.indexing.text import invoice_to_text


def build_bm25_for_tenant(db: Session, tenant_id: uuid.UUID) -> Bm25InvoiceIndex:
    rows = db.execute(select(StoredInvoice)).scalars().all()
    items = [(str(r.id), invoice_to_text(Invoice.model_validate(r.payload))) for r in rows]
    idx = Bm25InvoiceIndex()
    idx.build(items)
    idx.save(Bm25InvoiceIndex.path_for(str(tenant_id)))
    return idx
