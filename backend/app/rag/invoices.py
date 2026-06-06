"""Invoices RAG: retrieval over the tenant's own invoices (pgvector).

Reuses the tenant-scoped vector search, so results are already isolated by RLS.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain import Invoice
from app.rag.base import RetrievedChunk
from app.services.workspace import search_invoices


def render_invoice(inv: Invoice) -> str:
    """A compact, LLM-friendly textual rendering of an invoice."""
    bits = [
        f"{inv.doc_type} {inv.number or inv.id}",
        f"date {inv.date}" if inv.date else "",
        f"supplier {inv.supplier.name}" if inv.supplier.name else "",
        f"VAT {inv.supplier.vat_number}" if inv.supplier.vat_number else "",
        f"recipient {inv.recipient.name}" if inv.recipient.name else "",
        f"net {inv.net_amount}" if inv.net_amount is not None else "",
        f"VAT amount {inv.vat_amount}" if inv.vat_amount is not None else "",
        f"total {inv.total_amount} {inv.currency}" if inv.total_amount is not None else "",
        "reverse charge" if inv.reverse_charge else "",
    ]
    return ", ".join(b for b in bits if b)


class InvoiceRetriever:
    name = "invoices"

    def __init__(self, db: Session):
        self.db = db

    def retrieve(
        self, query: str, top_k: int = 6, company_key: str | None = None
    ) -> list[RetrievedChunk]:
        hits = search_invoices(self.db, query, top_k=top_k, company_key=company_key)
        chunks: list[RetrievedChunk] = []
        for inv, score in hits:
            chunks.append(
                RetrievedChunk(
                    id=f"invoice:{inv.id}",
                    text=render_invoice(inv),
                    source=f"{inv.company_name or 'invoice'} · {inv.number or inv.id}",
                    score=score,
                    kind="invoice",
                    metadata={
                        "company_key": inv.company_key,
                        "company_name": inv.company_name,
                        "number": inv.number,
                        "doc_type": inv.doc_type,
                        "direction": inv.direction,
                        "total": str(inv.total_amount) if inv.total_amount is not None else None,
                    },
                )
            )
        return chunks
