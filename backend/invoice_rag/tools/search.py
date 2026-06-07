"""Tool: hybrid semantic search with optional structured pre-filter.

When filters are given, restrict the candidate set first (SQL WHERE), then rank
only within it — the semantic->filter hybrid.
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from invoice_rag.models import FilterParams, InvoiceView
from invoice_rag.retrieval.hybrid import semantic_search as _hybrid
from invoice_rag.tools.filter import filter_invoices


def semantic_search(
    db: Session,
    tenant_id: uuid.UUID,
    query: str,
    top_k: int = 10,
    filters: Optional[FilterParams] = None,
) -> list[InvoiceView]:
    if filters is None:
        return _hybrid(db, tenant_id, query, top_k=top_k)
    allowed = {v.invoice_id for v in filter_invoices(db, filters.model_copy(update={"limit": 10_000}))}
    ranked = _hybrid(db, tenant_id, query, top_k=top_k * 3)
    return [v for v in ranked if v.invoice_id in allowed][:top_k]
