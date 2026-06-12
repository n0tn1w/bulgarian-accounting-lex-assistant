"""Tool: SQL aggregation over filtered invoices, with optional group_by.

Every number is citable: each group carries the contributing invoice ids.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import StoredInvoice
from invoice_rag.models import FilterParams, GroupBy, SumGroup, SumResult
from invoice_rag.retrieval.hybrid import _row_to_view
from invoice_rag.tools.filter import apply_filters, effective_direction


def _group_key(r: StoredInvoice, group_by: GroupBy) -> str:
    if group_by == "vendor":
        return r.supplier_name or r.company_name or "unknown"
    if group_by == "month":
        return (r.date or "")[:7]
    if group_by == "quarter":
        if not r.date:
            return "unknown"
        q = (int(r.date[5:7]) - 1) // 3 + 1
        return f"{r.date[:4]}-Q{q}"
    if group_by == "currency":
        return r.currency or "unknown"
    if group_by == "vat_rate":
        return str(r.payload.get("tax_lines", [{}])[0].get("rate", "unknown"))
    if group_by == "country":
        return (r.supplier_vat or "")[:2] or "unknown"
    if group_by == "direction":
        return effective_direction(r.payload)
    return "all"


def _filtered_rows(db: Session, f: FilterParams) -> list[StoredInvoice]:
    return list(db.execute(apply_filters(select(StoredInvoice), f)).scalars().all())


def sum_invoices(
    db: Session, f: FilterParams, group_by: Optional[GroupBy] = None
) -> SumResult:
    rows = _filtered_rows(db, f)
    z = Decimal("0")
    tot_net = sum((r.net_amount or z for r in rows), z)
    tot_vat = sum((r.vat_amount or z for r in rows), z)
    tot_amt = sum((r.total_amount or z for r in rows), z)
    currency = rows[0].currency if rows else None

    groups: list[SumGroup] = []
    if group_by:
        buckets: dict[str, list[StoredInvoice]] = defaultdict(list)
        for r in rows:
            buckets[_group_key(r, group_by)].append(r)
        for key, items in buckets.items():
            gt = sum((it.total_amount or z for it in items), z)
            groups.append(SumGroup(key=key, total=float(gt), count=len(items),
                                   invoice_ids=[str(it.id) for it in items]))
        groups.sort(key=lambda g: g.total, reverse=True)

    return SumResult(
        total_net=float(tot_net), total_vat=float(tot_vat), total_amount=float(tot_amt),
        currency=currency, count=len(rows), groups=groups,
        invoices=[_row_to_view(r) for r in rows],
    )
