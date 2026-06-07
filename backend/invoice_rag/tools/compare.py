"""Tool: compare a metric between two date ranges."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from invoice_rag.models import ComparisonResult, DateRange, FilterParams, Metric
from invoice_rag.tools.filter import filter_invoices


def _metric_value(rows, metric: Metric) -> float:
    if metric == "invoice_count":
        return float(len(rows))
    totals = [v.total_amount or 0.0 for v in rows]
    if metric == "avg_amount":
        return float(sum(totals) / len(totals)) if totals else 0.0
    return float(sum(totals))  # total_spent


def compare_periods(
    db: Session,
    metric: Metric,
    period_a: DateRange,
    period_b: DateRange,
    vendor: Optional[str] = None,
    direction: Optional[str] = None,
) -> ComparisonResult:
    rows_a = filter_invoices(db, FilterParams(vendor=vendor, direction=direction,
                                              date_from=period_a.date_from,
                                              date_to=period_a.date_to, limit=10000))
    rows_b = filter_invoices(db, FilterParams(vendor=vendor, direction=direction,
                                              date_from=period_b.date_from,
                                              date_to=period_b.date_to, limit=10000))
    va, vb = _metric_value(rows_a, metric), _metric_value(rows_b, metric)
    pct = round((vb - va) / va * 100, 2) if va else None
    return ComparisonResult(
        metric=metric, value_a=va, value_b=vb, delta=round(vb - va, 2), pct_change=pct,
        invoice_ids_a=[v.invoice_id for v in rows_a],
        invoice_ids_b=[v.invoice_id for v in rows_b],
    )
