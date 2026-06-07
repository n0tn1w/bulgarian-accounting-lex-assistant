"""Dense index: BGE-M3 embeddings (the same model the laws RAG uses), loaded lazily
as a process singleton. Owns embedding the invoices (the dense index) and the query."""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import StoredInvoice
from app.domain import Invoice
from invoice_rag.config import settings
from invoice_rag.indexing.text import invoice_to_text


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


def embed_text(text: str) -> list[float]:
    vec = _model().encode([text or ""], normalize_embeddings=True, convert_to_numpy=True)[0]
    return vec.astype(float).tolist()


def embed_invoice(inv: Invoice) -> list[float]:
    return embed_text(invoice_to_text(inv))


def reembed_tenant(db: Session) -> int:
    """Recompute embeddings for every invoice in the tenant session (maintenance)."""
    rows = db.execute(select(StoredInvoice)).scalars().all()
    for r in rows:
        r.embedding = embed_invoice(Invoice.model_validate(r.payload))
    db.flush()
    return len(rows)
