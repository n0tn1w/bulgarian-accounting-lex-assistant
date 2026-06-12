"""Tool: parameterized SQL filter over the tenant's invoices."""
from __future__ import annotations

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import StoredInvoice
from invoice_rag.dates import parse_period
from invoice_rag.models import FilterParams, InvoiceView
from invoice_rag.retrieval.hybrid import _row_to_view


def effective_direction(payload: dict) -> str:
    """Direction with a fallback: when ingest left it 'unknown', derive it from the
    invoice perspective — if our own company is the supplier the invoice is a SALE,
    if we're the recipient it's a PURCHASE. (perspective: supplier|recipient|auto.)"""
    d = (payload or {}).get("direction")
    if d in ("sale", "purchase"):
        return d
    p = (payload or {}).get("perspective")
    if p == "supplier":
        return "sale"
    if p == "recipient":
        return "purchase"
    return "unknown"


def _direction_expr():
    """SQL mirror of effective_direction() for use in WHERE/filters."""
    d = StoredInvoice.payload["direction"].astext
    p = StoredInvoice.payload["perspective"].astext
    return case(
        (d.in_(["sale", "purchase"]), d),
        (p == "supplier", "sale"),
        (p == "recipient", "purchase"),
        else_="unknown",
    )


def _resolve_dates(f: FilterParams) -> tuple[str | None, str | None]:
    if f.period:
        from datetime import date as _date
        r = parse_period(f.period, ref=_date.today())
        if r:
            return r.date_from, r.date_to
    return f.date_from, f.date_to


def apply_filters(stmt, f: FilterParams):
    """Apply every FilterParams predicate (NOT limit/order) to a select() stmt.

    Shared by filter_invoices and sum_invoices so aggregation honors the same
    filters. Note: `country` and `vat_rate` are intentionally NOT applied in
    Phase 1 (they need VAT-prefix / JSONB tax_lines queries) — add later if eval
    shows a gap.
    """
    if f.vendor:
        # Match the counterparty wherever extraction put it: on a purchase that's
        # the supplier; on a sale (our own invoice) it's the recipient. company_name
        # is the ingest-normalized counterparty and covers both.
        like = f"%{f.vendor}%"
        stmt = stmt.where(
            or_(
                StoredInvoice.supplier_name.ilike(like),
                StoredInvoice.recipient_name.ilike(like),
                StoredInvoice.company_name.ilike(like),
            )
        )
    date_from, date_to = _resolve_dates(f)
    if date_from:
        stmt = stmt.where(StoredInvoice.date >= date_from)
    if date_to:
        stmt = stmt.where(StoredInvoice.date <= date_to)
    if f.min_amount is not None:
        stmt = stmt.where(StoredInvoice.total_amount >= f.min_amount)
    if f.max_amount is not None:
        stmt = stmt.where(StoredInvoice.total_amount <= f.max_amount)
    if f.currency:
        stmt = stmt.where(StoredInvoice.currency == f.currency)
    if f.doc_type:
        stmt = stmt.where(StoredInvoice.payload["doc_type"].astext == f.doc_type)
    if f.direction:
        # Match on the DERIVED direction so invoices ingest left 'unknown' are
        # resolved from perspective (supplier=sale, recipient=purchase) instead of
        # being silently dropped — which looked like "company not found".
        stmt = stmt.where(_direction_expr() == f.direction)
    if f.reverse_charge is not None:
        val = "true" if f.reverse_charge else "false"
        stmt = stmt.where(StoredInvoice.payload["reverse_charge"].astext == val)
    if f.weekend_only:
        # ISO date string -> dow via Postgres (0=Sun..6=Sat); 0 or 6 is weekend.
        dow = func.extract("dow", func.to_date(StoredInvoice.date, "YYYY-MM-DD"))
        stmt = stmt.where(dow.in_([0, 6]))
    return stmt


def filter_invoices(db: Session, f: FilterParams) -> list[InvoiceView]:
    stmt = apply_filters(select(StoredInvoice), f).order_by(StoredInvoice.date).limit(f.limit)
    return [_row_to_view(r) for r in db.execute(stmt).scalars().all()]
