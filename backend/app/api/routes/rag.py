"""Retrieval endpoints and the chat orchestrator.

`/chat` is the tool-calling agent (`app.rag.run`) when a model is configured
(``LLM_MODEL``). With no model — or if the agent call fails — it degrades to the
no-model fallback: retrieve invoices (via invoice_rag's hybrid search) and laws,
then summarize the context without an LLM, so the endpoint always responds.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_principal, get_tenant_db
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    RetrieveRequest,
    RetrieveResponse,
)
from app.core import get_settings
from app.rag import Citation, EchoLLMClient, LawsRetriever, RetrievedChunk
from app.rag import run as run_agent
from invoice_rag.models import InvoiceView
from invoice_rag.tools.search import semantic_search

router = APIRouter(tags=["rag"])
logger = logging.getLogger(__name__)


def _invoice_chunks(db: Session, tenant_id: uuid.UUID, query: str, top_k: int) -> list[RetrievedChunk]:
    """Hybrid-retrieve invoices (no LLM) and adapt to the shared RetrievedChunk."""
    views: list[InvoiceView] = semantic_search(db, tenant_id, query, top_k=top_k)
    return [
        RetrievedChunk(
            id=f"invoice:{v.invoice_id}",
            text=f"Invoice {v.number or v.invoice_id} · {v.vendor_name or '—'} · "
                 f"{v.date or '—'} · total {v.total_amount} {v.currency or ''}".strip(),
            source=f"{v.vendor_name or '—'} · {v.number or v.invoice_id}",
            score=v.score or 0.0,
            kind="invoice",
        )
        for v in views
    ]


@router.post("/rag/invoices/retrieve", response_model=RetrieveResponse)
def retrieve_invoices(req: RetrieveRequest, principal: Principal = Depends(get_principal),
                      db: Session = Depends(get_tenant_db)) -> RetrieveResponse:
    return RetrieveResponse(chunks=_invoice_chunks(db, principal.tenant_id, req.query, req.top_k))


@router.post("/rag/laws/retrieve", response_model=RetrieveResponse)
def retrieve_laws(req: RetrieveRequest, db: Session = Depends(get_tenant_db)) -> RetrieveResponse:
    return RetrieveResponse(chunks=LawsRetriever(db).retrieve(req.query, req.top_k))


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, principal: Principal = Depends(get_principal),
         db: Session = Depends(get_tenant_db)) -> ChatResponse:
    settings = get_settings()
    if settings.llm_model:                       # the agent needs a model
        try:
            history = [t.model_dump() for t in req.history]
            ans = run_agent(db, principal.tenant_id, req.message, history, model=settings.llm_model)
            return ChatResponse(reply=ans.reply, citations=[], model=ans.model,
                                cards=ans.cards, refused=ans.refused, tool_trace=ans.tool_trace)
        except Exception as exc:  # provider/network error -> degrade to retrieval echo
            logger.warning("agent failed (%s); falling back to no-model retrieval echo", exc)
    return _no_model_reply(req, db, principal.tenant_id)


def _no_model_reply(req: ChatRequest, db: Session, tenant_id: uuid.UUID) -> ChatResponse:
    """No-model fallback: retrieve invoices + laws and summarize without an LLM."""
    invoices = _invoice_chunks(db, tenant_id, req.message, req.top_k)
    laws = LawsRetriever(db).retrieve(req.message, req.top_k)
    context = sorted([*invoices, *laws], key=lambda c: c.score, reverse=True)
    history = [t.model_dump() for t in req.history]
    reply = EchoLLMClient().answer(req.message, context, history)
    citations = [Citation(id=c.id, source=c.source, kind=c.kind) for c in context]
    return ChatResponse(reply=reply, citations=citations, model=EchoLLMClient.name, context=context)
