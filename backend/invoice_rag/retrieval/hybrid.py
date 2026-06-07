"""Hybrid retrieval: dense (pgvector) + sparse (BM25) fused with RRF.

All DB access is on a tenant-scoped Session, so RLS restricts every row to the
caller's tenant.
"""
from __future__ import annotations

import uuid
from typing import List, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import StoredInvoice
from invoice_rag.config import settings
from invoice_rag.indexing.dense import embed_text
from invoice_rag.indexing.sparse import Bm25InvoiceIndex
from invoice_rag.models import InvoiceView
from invoice_rag.retrieval.fusion import rrf_fuse


def _row_to_view(r: StoredInvoice, score: float | None = None) -> InvoiceView:
    def f(x):
        return float(x) if x is not None else None

    return InvoiceView(
        invoice_id=str(r.id),
        external_id=r.external_id,
        number=r.number,
        date=r.date,
        vendor_name=r.supplier_name or r.company_name,
        direction=None,
        net_amount=f(r.net_amount),
        vat_amount=f(r.vat_amount),
        total_amount=f(r.total_amount),
        currency=r.currency,
        score=score,
    )


def _dense_search(db: Session, query: str, k: int) -> List[Tuple[str, float]]:
    qvec = embed_text(query)
    distance = StoredInvoice.embedding.cosine_distance(qvec).label("distance")
    stmt = (
        select(StoredInvoice.id, distance)
        .where(StoredInvoice.embedding.is_not(None))
        .order_by(distance)
        .limit(k)
    )
    return [(str(rid), max(0.0, 1.0 - float(d))) for rid, d in db.execute(stmt).all()]


def semantic_search(
    db: Session,
    tenant_id: uuid.UUID,
    query: str,
    top_k: int = 10,
) -> List[InvoiceView]:
    dense = _dense_search(db, query, settings.dense_top_k)

    sparse: List[Tuple[str, float]] = []
    bm25_path = Bm25InvoiceIndex.path_for(str(tenant_id))
    if bm25_path.exists():
        sparse = Bm25InvoiceIndex.load(bm25_path).query(query, settings.bm25_top_k)

    fused = rrf_fuse(dense, sparse, settings.rrf_k0, top_k)
    if not fused:
        return []

    order = {doc_id: i for i, (doc_id, _) in enumerate(fused)}
    ids = [uuid.UUID(doc_id) for doc_id, _ in fused]
    rows = db.execute(select(StoredInvoice).where(StoredInvoice.id.in_(ids))).scalars().all()
    rows.sort(key=lambda r: order[str(r.id)])
    return [_row_to_view(r, score=fused[order[str(r.id)]][1]) for r in rows]
