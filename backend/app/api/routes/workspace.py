"""Persistent, tenant-scoped workspace: store invoices, browse per-company sets,
and run vector search. All routes require auth and run under RLS."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_principal, get_tenant_db
from app.api.schemas import (
    GroupResponse,
    PersistRequest,
    PersistResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
    WorkspaceInvoicesResponse,
)
from app.services import workspace as ws

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.post("/invoices", response_model=PersistResponse)
def persist(
    req: PersistRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_tenant_db),
) -> PersistResponse:
    """Persist parsed invoices for the current tenant (embeds + upserts)."""
    n = ws.store_invoices(db, principal.tenant_id, req.invoices)
    return PersistResponse(stored=n)


@router.get("/invoices", response_model=WorkspaceInvoicesResponse)
def list_invoices(db: Session = Depends(get_tenant_db)) -> WorkspaceInvoicesResponse:
    return WorkspaceInvoicesResponse(invoices=ws.list_invoices(db))


@router.get("/companies", response_model=GroupResponse)
def companies(db: Session = Depends(get_tenant_db)) -> GroupResponse:
    return GroupResponse(groups=ws.group_companies(db))


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, db: Session = Depends(get_tenant_db)) -> SearchResponse:
    hits = ws.search_invoices(db, req.query, req.top_k, req.company_key)
    return SearchResponse(hits=[SearchHit(invoice=inv, score=score) for inv, score in hits])


@router.delete("/invoices/{external_id}")
def delete_invoice(external_id: str, db: Session = Depends(get_tenant_db)) -> dict:
    return {"deleted": ws.delete_invoice(db, external_id)}
