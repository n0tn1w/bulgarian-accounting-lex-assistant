"""Canonical 'what text represents an invoice' — shared by dense + sparse indexing."""
from __future__ import annotations

from app.domain import Invoice


def invoice_to_text(inv: Invoice) -> str:
    """Identity, parties (+ variants), line items, amounts. Vendor-name variants are
    concatenated so 'Microsoft' collapses with 'Майкрософт Ирландия' at retrieval."""
    parts: list[str | None] = [
        inv.number, inv.date, inv.doc_type, inv.direction, inv.company_name,
        inv.supplier.name, inv.supplier.vat_number,
        inv.recipient.name, inv.recipient.vat_number,
    ]
    parts += [li.description for li in inv.line_items]
    parts += [str(inv.total_amount) if inv.total_amount is not None else None, inv.currency]
    return " ".join(p for p in parts if p)
