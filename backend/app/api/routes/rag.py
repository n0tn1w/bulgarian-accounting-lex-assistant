"""Retrieval endpoints and the chat orchestrator.

`/chat` uses the invoice query agent when a model is configured (``LLM_MODEL``
env-var).  If no model is set, or the agent call fails, it falls back to the
naive baseline (retrieve-then-stuff-into-prompt).  The baseline is also
available at the dedicated ``/chat/baseline`` endpoint for evaluation comparisons.
"""
from __future__ import annotations

import logging

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
from app.rag import Citation, EchoLLMClient, InvoiceRetriever, LawsRetriever, get_llm_client
from invoice_rag.agent import run as run_agent

router = APIRouter(tags=["rag"])
logger = logging.getLogger(__name__)


@router.post("/rag/invoices/retrieve", response_model=RetrieveResponse)
def retrieve_invoices(req: RetrieveRequest, db: Session = Depends(get_tenant_db)) -> RetrieveResponse:
    chunks = InvoiceRetriever(db).retrieve(req.query, req.top_k, company_key=req.company_key)
    return RetrieveResponse(chunks=chunks)


@router.post("/rag/laws/retrieve", response_model=RetrieveResponse)
def retrieve_laws(req: RetrieveRequest, db: Session = Depends(get_tenant_db)) -> RetrieveResponse:
    return RetrieveResponse(chunks=LawsRetriever(db).retrieve(req.query, req.top_k))


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, principal: Principal = Depends(get_principal),
         db: Session = Depends(get_tenant_db)) -> ChatResponse:
    settings = get_settings()
    history = [t.model_dump() for t in req.history]
    if settings.llm_model:                       # agent path needs a model
        try:
            ans = run_agent(db, principal.tenant_id, req.message, history, model=settings.llm_model)
            return ChatResponse(reply=ans.reply, citations=[], model=ans.model,
                                cards=ans.cards, refused=ans.refused, tool_trace=ans.tool_trace)
        except Exception as exc:  # provider/network error -> naive fallback
            logger.warning("agent failed (%s); falling back to naive baseline", exc)
    return _chat_baseline(req, db)


@router.post("/chat/baseline", response_model=ChatResponse)
def chat_baseline(req: ChatRequest, db: Session = Depends(get_tenant_db)) -> ChatResponse:
    return _chat_baseline(req, db)


def _chat_baseline(req: ChatRequest, db: Session) -> ChatResponse:
    invoices = InvoiceRetriever(db).retrieve(req.message, req.top_k, company_key=req.company_key)
    laws = LawsRetriever(db).retrieve(req.message, req.top_k)
    context = sorted([*invoices, *laws], key=lambda c: c.score, reverse=True)
    history = [t.model_dump() for t in req.history]
    client = get_llm_client()
    try:
        reply, model = client.answer(req.message, context, history), client.name
    except Exception as exc:
        logger.warning("LLM call failed (%s); echo", exc)
        reply = EchoLLMClient().answer(req.message, context, history)
        model = f"{client.name} (unavailable) → echo"
    citations = [Citation(id=c.id, source=c.source, kind=c.kind) for c in context]
    return ChatResponse(reply=reply, citations=citations, model=model, context=context)
