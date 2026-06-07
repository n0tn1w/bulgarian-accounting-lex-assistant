"""Reciprocal Rank Fusion for combining dense and sparse retrieval results."""
from __future__ import annotations

from typing import List, Tuple


def rrf_fuse(
    dense: List[Tuple[str, float]],
    sparse: List[Tuple[str, float]],
    k0: int,
    top_k: int,
) -> List[Tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranked in (dense, sparse):
        for rank, (doc_id, _) in enumerate(ranked):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k0 + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
