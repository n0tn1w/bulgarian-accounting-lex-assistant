"""Invoice embeddings for vector search.

A deterministic, offline embedder (hashed n-grams) so search works without GPUs or API
keys. Kept behind one function so a transformer/LLM embedder can replace it.
"""

from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer

from app.core import get_settings
from app.domain import Invoice

_DIM = get_settings().embedding_dim
_vectorizer = HashingVectorizer(
    n_features=_DIM, alternate_sign=False, norm=None, ngram_range=(1, 2)
)


def embed_text(text: str) -> list[float]:
    vec = np.asarray(_vectorizer.transform([text or ""]).todense()).ravel()
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec = vec / norm
    return vec.astype(float).tolist()


def invoice_to_text(inv: Invoice) -> str:
    """Text we embed for an invoice: identity, parties, amounts."""
    parts = [
        inv.number,
        inv.date,
        inv.company_name,
        inv.supplier.name,
        inv.supplier.vat_number,
        inv.recipient.name,
        str(inv.total_amount) if inv.total_amount is not None else None,
        inv.currency,
    ]
    return " ".join(p for p in parts if p)


def embed_invoice(inv: Invoice) -> list[float]:
    return embed_text(invoice_to_text(inv))
