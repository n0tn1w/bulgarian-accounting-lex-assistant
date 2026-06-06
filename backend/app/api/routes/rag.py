"""Retrieval endpoints and the chat orchestrator.

`/chat` retrieves from both RAGs (the tenant's invoices + Bulgarian legislation),
merges the context, and hands it to the LLM (Ollama / Claude / OpenAI via LiteLLM,
selected by LLM_MODEL). If no model is configured or the call fails, it falls back to
the echo client so the endpoint always responds.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_db
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    RetrieveRequest,
    RetrieveResponse,
)
from app.rag import Citation, EchoLLMClient, InvoiceRetriever, LawsRetriever, get_llm_client

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
def chat(req: ChatRequest, db: Session = Depends(get_tenant_db)) -> ChatResponse:
    invoices = InvoiceRetriever(db).retrieve(req.message, req.top_k, company_key=req.company_key)
    laws = LawsRetriever(db).retrieve(req.message, req.top_k)
    context = sorted([*invoices, *laws], key=lambda c: c.score, reverse=True)
    history = [t.model_dump() for t in req.history]

    client = get_llm_client()
    try:
        reply = client.answer(req.message, context, history)
        model = client.name
    except Exception as exc:  # model unavailable or network error, degrade gracefully
        logger.warning("LLM call failed (%s); falling back to echo", exc)
        reply = EchoLLMClient().answer(req.message, context, history)
        model = f"{client.name} (unavailable) → echo"

    citations = [Citation(id=c.id, source=c.source, kind=c.kind) for c in context]
    return ChatResponse(reply=reply, citations=citations, model=model, context=context)
