"""Invoice tool registry: LLM tool-schemas + tenant-bound dispatch.

This is the INVOICE half of the agent — the five structured tools over the
tenant's own invoices. The orchestrator (app/rag/agent) imports these schemas and
this dispatch, combines them with the laws tool, and drives the loop. Nothing here
knows about laws, routing, or the LLM loop.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from invoice_rag.models import DateRange, FilterParams
from invoice_rag.tools.aggregate import sum_invoices
from invoice_rag.tools.compare import compare_periods
from invoice_rag.tools.filter import filter_invoices
from invoice_rag.tools.lookup import get_invoice
from invoice_rag.tools.search import semantic_search


def _fn(name: str, description: str, parameters: dict) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description, "parameters": parameters}}


def _object(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties, "required": required or []}


_FILTER_PROPS = {
    "vendor": {"type": "string", "description": "counterparty name, partial match"},
    "period": {"type": "string", "description": "natural-language date range, e.g. 'this quarter', 'last month', 'ytd', 'last year'"},
    "date_from": {"type": "string", "description": "ISO YYYY-MM-DD (use instead of period for exact ranges)"},
    "date_to": {"type": "string", "description": "ISO YYYY-MM-DD"},
    "min_amount": {"type": "number"},
    "max_amount": {"type": "number"},
    "currency": {"type": "string", "description": "e.g. BGN, EUR"},
    "country": {"type": "string", "description": "supplier country, e.g. 'Germany', 'DE'"},
    "vat_rate": {"type": "number", "description": "exact VAT rate as a fraction, e.g. 0.20 for 20%"},
    "direction": {"type": "string", "enum": ["purchase", "sale"], "description": "purchase = money out, sale = money in"},
    "reverse_charge": {"type": "boolean"},
    "doc_type": {"type": "string"},
    "weekend_only": {"type": "boolean", "description": "invoices issued on a weekend"},
}

_DATERANGE = _object({
    "date_from": {"type": "string", "description": "ISO YYYY-MM-DD"},
    "date_to": {"type": "string", "description": "ISO YYYY-MM-DD"},
}, ["date_from", "date_to"])

INVOICE_TOOL_SCHEMAS = [
    _fn("get_invoice", "Look up a single invoice by its number.",
        _object({"number": {"type": "string", "description": "invoice number"}}, ["number"])),
    _fn("filter_invoices",
        "List invoices matching structured criteria (vendor, amount range, currency, period, direction, reverse-charge, weekend). Use for 'show me / which invoices…'.",
        _object(_FILTER_PROPS)),
    _fn("sum_invoices",
        "Total amounts over filtered invoices, optionally grouped. Use for 'how much / total…'. group_by one of vendor|month|quarter|vat_rate|country|currency|direction.",
        _object({**_FILTER_PROPS,
                 "group_by": {"type": "string",
                              "enum": ["vendor", "month", "quarter", "vat_rate", "country", "currency", "direction"]}})),
    _fn("compare_periods",
        "Compare a metric between two date ranges. metric one of total_spent|invoice_count|avg_amount.",
        _object({"metric": {"type": "string", "enum": ["total_spent", "invoice_count", "avg_amount"]},
                 "period_a": _DATERANGE, "period_b": _DATERANGE,
                 "vendor": {"type": "string"},
                 "direction": {"type": "string", "enum": ["purchase", "sale"]}},
                ["metric", "period_a", "period_b"])),
    _fn("semantic_search",
        "Find invoices by fuzzy topic/category (e.g. 'cloud services', 'marketing') when no exact field matches. Optional structured pre-filter.",
        _object({"query": {"type": "string"}, "top_k": {"type": "integer"}}, ["query"])),
]

INVOICE_TOOL_NAMES = frozenset(t["function"]["name"] for t in INVOICE_TOOL_SCHEMAS)


def _dump(obj: Any) -> Any:
    """Pydantic model(s) -> JSON-able dict/list. Carries numbers verbatim."""
    if isinstance(obj, list):
        return [o.model_dump(mode="json") for o in obj]
    return obj.model_dump(mode="json") if obj is not None else None


def make_invoice_dispatch(db: Session, tenant_id: uuid.UUID):
    """Return dispatch(name, args) over the invoice tools, bound to this tenant
    session (RLS-scoped). Errors are surfaced as {"error": ...}, never raised."""

    def dispatch(name: str, args: dict) -> Any:
        try:
            if name == "get_invoice":
                return _dump(get_invoice(db, number=args.get("number")))
            if name == "filter_invoices":
                return _dump(filter_invoices(db, FilterParams(**args)))
            if name == "sum_invoices":
                group_by = args.pop("group_by", None)
                return _dump(sum_invoices(db, FilterParams(**args), group_by=group_by))
            if name == "compare_periods":
                return _dump(compare_periods(
                    db,
                    metric=args["metric"],
                    period_a=DateRange(**args["period_a"]),
                    period_b=DateRange(**args["period_b"]),
                    vendor=args.get("vendor"),
                    direction=args.get("direction"),
                ))
            if name == "semantic_search":
                return _dump(semantic_search(db, tenant_id, args["query"],
                                             top_k=args.get("top_k", 10)))
            return {"error": f"unknown invoice tool: {name}"}
        except Exception as exc:  # bad args / tool failure -> surfaced to the model
            return {"error": f"{type(exc).__name__}: {exc}"}

    return dispatch
