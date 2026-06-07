"""Tool: direct invoice lookup by internal id or invoice number."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import StoredInvoice
from invoice_rag.models import InvoiceView
from invoice_rag.retrieval.hybrid import _row_to_view


def get_invoice(
    db: Session, *, invoice_id: Optional[str] = None, number: Optional[str] = None
) -> Optional[InvoiceView]:
    stmt = select(StoredInvoice)
    if invoice_id:
        stmt = stmt.where(StoredInvoice.id == uuid.UUID(invoice_id))
    elif number:
        stmt = stmt.where(StoredInvoice.number == number)
    else:
        return None
    row = db.execute(stmt.limit(1)).scalars().first()
    return _row_to_view(row) if row else None
