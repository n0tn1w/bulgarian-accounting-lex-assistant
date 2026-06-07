"""Deterministic natural-language date-range parsing (BG + EN).

Date arithmetic must never be done by the LLM: a misparsed range yields a
confidently-wrong sum. This module maps a phrase + reference date to an exact,
inclusive ISO DateRange, and is fully unit-testable.
"""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from typing import Optional

from invoice_rag.models import DateRange


def _iso(d: date) -> str:
    return d.isoformat()


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _quarter_bounds(year: int, q: int) -> tuple[date, date]:
    start_month = 3 * (q - 1) + 1
    return date(year, start_month, 1), _month_end(year, start_month + 2)


def parse_period(expression: str, ref: date) -> Optional[DateRange]:
    """Resolve a natural-language period against `ref`. Returns None if unparseable."""
    s = (expression or "").strip().lower()
    if not s:
        return None

    # last N days (inclusive of ref): [ref - N, ref]
    m = re.search(r"last\s+(\d+)\s+days|последните\s+(\d+)\s+дни", s)
    if m:
        n = int(next(g for g in m.groups() if g))
        return DateRange(date_from=_iso(ref - timedelta(days=n)), date_to=_iso(ref))

    cur_q = (ref.month - 1) // 3 + 1

    table: dict[tuple[str, ...], tuple[date, date]] = {
        ("this year", "тази година", "current year"): (date(ref.year, 1, 1), date(ref.year, 12, 31)),
        ("ytd", "year to date", "от началото на годината"): (date(ref.year, 1, 1), ref),
        ("last year", "миналата година", "previous year"): (date(ref.year - 1, 1, 1), date(ref.year - 1, 12, 31)),
        ("this month", "този месец", "current month"): (date(ref.year, ref.month, 1), _month_end(ref.year, ref.month)),
    }
    for keys, bounds in table.items():
        if s in keys:
            return DateRange(date_from=_iso(bounds[0]), date_to=_iso(bounds[1]))

    if s in ("last month", "миналия месец", "предходния месец"):
        y, mth = (ref.year - 1, 12) if ref.month == 1 else (ref.year, ref.month - 1)
        return DateRange(date_from=_iso(date(y, mth, 1)), date_to=_iso(_month_end(y, mth)))

    if s in ("this quarter", "това тримесечие", "current quarter"):
        a, b = _quarter_bounds(ref.year, cur_q)
        return DateRange(date_from=_iso(a), date_to=_iso(b))

    if s in ("last quarter", "миналото тримесечие", "предходното тримесечие"):
        y, q = (ref.year - 1, 4) if cur_q == 1 else (ref.year, cur_q - 1)
        a, b = _quarter_bounds(y, q)
        return DateRange(date_from=_iso(a), date_to=_iso(b))

    return None
