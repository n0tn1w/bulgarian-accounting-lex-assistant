"""Hybrid retrieval: dense (vectors) + sparse (BM25) fused via Reciprocal Rank Fusion.

RRF is rank-based, so it sidesteps the incomparable score scales of cosine
similarity vs BM25. For each candidate: score = Σ 1/(k0 + rank_in_list).
Returns fused RetrievedChunk candidates (pre-rerank).
"""
from __future__ import annotations

from typing import Dict, List

from config import settings
from ..embedding.embedder import Embedder
from ..models import Chunk, RetrievedChunk
from ..store.bm25_store import Bm25Store
from ..store.vector_store import ChromaVectorStore


class HybridRetriever:
    def __init__(self, embedder: Embedder, vector_store: ChromaVectorStore, bm25_store: Bm25Store):
        self.embedder = embedder
        self.vector_store = vector_store
        self.bm25_store = bm25_store

    def retrieve(self, query: str) -> List[RetrievedChunk]:
        q_vec = self.embedder.embed_query(query)
        dense = self.vector_store.query(q_vec, settings.dense_top_k)
        sparse = self.bm25_store.query(query, settings.bm25_top_k)

        fused: Dict[str, RetrievedChunk] = {}

        for rank, (chunk, _sim) in enumerate(dense):
            rc = fused.setdefault(chunk.id, RetrievedChunk(chunk=chunk))
            rc.dense_rank = rank
            rc.fused_score += 1.0 / (settings.rrf_k0 + rank)

        for rank, (chunk, _score) in enumerate(sparse):
            rc = fused.setdefault(chunk.id, RetrievedChunk(chunk=chunk))
            rc.bm25_rank = rank
            rc.fused_score += 1.0 / (settings.rrf_k0 + rank)

        ranked = sorted(fused.values(), key=lambda r: r.fused_score, reverse=True)
        return ranked[: settings.fused_candidates]
