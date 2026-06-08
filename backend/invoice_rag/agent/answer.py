"""Assemble the agent's response from the loop's tool-call log.

The model's prose is the narrative; every figure and citation is rendered from
the tool *results* here — the model never produces a number. Cards mirror the
frontend ChatCard shapes (sum / comparison / invoices). No tool calls at all =>
refusal (the model either declined an out-of-scope question, or tried to answer
a data question ungrounded, which we do not trust).
"""
from __future__ import annotations

from datetime import date as _date
from typing import Any

from pydantic import BaseModel, Field

from invoice_rag.agent.loop import LoopResult
from invoice_rag.models import Citation


class AgentAnswer(BaseModel):
    reply: str
    cards: list[dict] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    refused: bool = False
    model: str = ""
    tool_trace: list[dict] = Field(default_factory=list)


def _parse_date(s: Any) -> _date | None:
    try:
        return _date.fromisoformat(s) if isinstance(s, str) else None
    except ValueError:
        return None


def _cite_view(v: dict) -> Citation:
    return Citation(invoice_id=v.get("invoice_id", ""), invoice_number=v.get("number"),
                    vendor_name=v.get("vendor_name"), date=_parse_date(v.get("date")),
                    amount=v.get("total_amount"), relevance="match")


def assemble(loop: LoopResult, *, model: str) -> AgentAnswer:
    cards: list[dict] = []
    citations: list[Citation] = []

    for c in loop.calls:
        r = c.result
        if isinstance(r, dict) and r.get("error"):
            continue  # tool error already surfaced to the model; no card
        if c.name == "sum_invoices":
            invs = r.get("invoices") or []
            cards.append({"type": "sum", **{k: v for k, v in r.items() if k != "invoices"}})
            if invs:  # rich, citable contributors (works for ungrouped totals too)
                citations.extend(_cite_view(v) for v in invs)
            else:     # legacy fallback: ids from groups only
                for g in r.get("groups", []):
                    for iid in g.get("invoice_ids", []):
                        citations.append(Citation(invoice_id=iid, relevance=f"contributed to {g.get('key')}"))
        elif c.name == "compare_periods":
            cards.append({"type": "comparison", **r})
        elif c.name in ("filter_invoices", "semantic_search"):
            items = r if isinstance(r, list) else []
            cards.append({"type": "invoices", "items": items})
            citations.extend(_cite_view(v) for v in items)
        elif c.name == "get_invoice":
            items = [r] if isinstance(r, dict) and r.get("invoice_id") else []
            cards.append({"type": "invoices", "items": items})
            citations.extend(_cite_view(v) for v in items)

    # Aggregate answers (sum/compare) have no row list, so surface the sources as
    # chips — reuses the existing `sources` card. Skip when a list card already
    # shows the rows (filter/semantic/get_invoice).
    has_list = any(card["type"] == "invoices" for card in cards)
    rich = [c for c in citations if c.invoice_number]
    if cards and rich and not has_list:
        cards.append({
            "type": "sources",
            "citations": [
                {"id": c.invoice_id,
                 "source": f"{c.vendor_name or '—'} · {c.invoice_number}",
                 "kind": "invoice"}
                for c in rich
            ],
            "model": model,
        })

    refused = len(loop.calls) == 0
    return AgentAnswer(
        reply=loop.final_text,
        cards=[] if refused else cards,
        citations=citations,
        refused=refused,
        model=model,
        tool_trace=[{"tool": c.name, "args": c.args} for c in loop.calls],
    )
