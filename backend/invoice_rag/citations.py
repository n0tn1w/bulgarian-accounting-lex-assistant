"""Build uniform Citation[] from any tool result.

Phase 1 returns citations alongside tool output; Phase 2's agent reuses these to
ground its prose. For sums, every contributing invoice is citable.
"""
from __future__ import annotations

from datetime import date as _date
from typing import Optional

from invoice_rag.models import Citation, InvoiceView, SumGroup


def _parse_date(s: Optional[str]) -> Optional[_date]:
    try:
        return _date.fromisoformat(s) if s else None
    except ValueError:
        return None


def citations_from_views(views: list[InvoiceView]) -> list[Citation]:
    return [
        Citation(
            invoice_id=v.invoice_id, invoice_number=v.number, vendor_name=v.vendor_name,
            date=_parse_date(v.date), amount=v.total_amount,
            relevance=f"score={v.score:.3f}" if v.score is not None else "match",
        )
        for v in views
    ]


def citation_from_sum_group(group: SumGroup) -> list[Citation]:
    return [
        Citation(invoice_id=iid, relevance=f"contributed to {group.key} (total {group.total})")
        for iid in group.invoice_ids
    ]
