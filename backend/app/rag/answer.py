"""Assemble the chat answer from the loop's tool-call log.

Splits the calls into invoice tools (cards built by invoice_rag) and query_law
(law source citations), adds the refusal verdict, and produces one AgentAnswer.
No tool calls at all => refusal (the model declined, or tried to answer ungrounded
— which we do not trust). Numbers/citations come only from tool results.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.rag.loop import LoopResult
from invoice_rag.agent import cards as invoice_cards
from invoice_rag.agent.tools import INVOICE_TOOL_NAMES
from invoice_rag.models import Citation


class AgentAnswer(BaseModel):
    reply: str
    cards: list[dict] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    refused: bool = False
    model: str = ""
    tool_trace: list[dict] = Field(default_factory=list)


def _law_sources_card(chunks: list, model: str) -> dict | None:
    """A `sources` card of law citations (non-clickable, styled as law)."""
    laws = [c for c in chunks if isinstance(c, dict)]
    if not laws:
        return None
    return {
        "type": "sources",
        "citations": [{"id": c.get("id", ""), "source": c.get("source", ""), "kind": "law"} for c in laws],
        "model": model,
    }


def assemble(loop: LoopResult, *, model: str) -> AgentAnswer:
    # Drop errored tool results (already surfaced to the model; no card).
    good = [c for c in loop.calls if not (isinstance(c.result, dict) and c.result.get("error"))]

    invoice_calls = [(c.name, c.result) for c in good if c.name in INVOICE_TOOL_NAMES]
    cards, citations = invoice_cards.assemble(invoice_calls, model=model)

    for c in good:
        if c.name == "query_law":
            law_card = _law_sources_card(c.result if isinstance(c.result, list) else [], model)
            if law_card:
                cards.append(law_card)

    refused = len(loop.calls) == 0
    return AgentAnswer(
        reply=loop.final_text,
        cards=[] if refused else cards,
        citations=citations,
        refused=refused,
        model=model,
        tool_trace=[{"tool": c.name, "args": c.args} for c in loop.calls],
    )
