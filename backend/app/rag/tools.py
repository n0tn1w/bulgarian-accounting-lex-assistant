"""Combined tool registry for the orchestrator.

Schemas = the invoice tools (imported from invoice_rag) + query_law (the laws RAG).
dispatch delegates invoice tool names to invoice_rag's tenant-bound dispatch and
handles query_law via the LawsRetriever (lex). This is the only place that wires
the two RAGs together — invoice_rag stays free of the laws RAG.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.rag.laws import LawsRetriever
from invoice_rag.agent.tools import INVOICE_TOOL_SCHEMAS, make_invoice_dispatch

_QUERY_LAW_SCHEMA = {
    "type": "function",
    "function": {
        "name": "query_law",
        "description": (
            "Answer questions about Bulgarian tax/accounting LAW — what the law says or requires "
            "(ЗДДС, ЗКПО, ДОПК, rates, rules, deadlines). Retrieves the relevant legal articles. "
            "Use for legal/regulatory questions, NOT for the company's own invoice data. A question "
            "may need this AND an invoice tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "the legal question, in the user's words"}},
            "required": ["query"],
        },
    },
}

TOOL_SCHEMAS = [*INVOICE_TOOL_SCHEMAS, _QUERY_LAW_SCHEMA]

# Tools whose params carry a `direction` (sale|purchase) filter.
_DIRECTION_TOOLS = frozenset({"filter_invoices", "sum_invoices", "compare_periods"})
# Word stems that unambiguously signal a direction in BG/EN. Stems (not whole
# words) so inflections are covered: продажба/продажби/продажбите, разход/разходи…
_SALE_STEMS = ("продажб", "приход", "издаден", "sale", "revenue", "income")
_PURCHASE_STEMS = ("покупк", "разход", "похарч", "получен", "purchase", "expense", "spent")


def _infer_direction(message: str) -> str | None:
    """Backstop for weak models that drop `direction` from tool calls: read it
    from the user's own words. Returns None unless exactly one side is present,
    so a question naming both (or neither) leaves the filter open."""
    m = (message or "").lower()
    sale = any(s in m for s in _SALE_STEMS)
    purchase = any(s in m for s in _PURCHASE_STEMS)
    if sale and not purchase:
        return "sale"
    if purchase and not sale:
        return "purchase"
    return None


def make_dispatch(db: Session, tenant_id: uuid.UUID, message: str = ""):
    """dispatch(name, args) over invoices + laws, bound to this tenant session.

    `message` is the user's question; used only to backfill `direction` on invoice
    tools when the model omits it (never to override a direction it did set)."""
    invoice_dispatch = make_invoice_dispatch(db, tenant_id)
    inferred_direction = _infer_direction(message)

    def dispatch(name: str, args: dict) -> Any:
        if name == "query_law":
            try:
                chunks = LawsRetriever(db).retrieve(args["query"], top_k=5)
                return [c.model_dump() for c in chunks]
            except Exception as exc:
                return {"error": f"{type(exc).__name__}: {exc}"}
        if name in _DIRECTION_TOOLS and inferred_direction and not args.get("direction"):
            args = {**args, "direction": inferred_direction}
        return invoice_dispatch(name, args)

    return dispatch
