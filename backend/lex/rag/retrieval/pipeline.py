"""End-to-end retrieval orchestration: load stores -> hybrid -> rerank.

This is the public entry point for querying. It loads the persisted indexes,
runs hybrid retrieval + cross-encoder reranking, and applies the
no-confident-source guard (retrieval-side analog of "отказ при липса на източник").
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from config import settings
from ..embedding.embedder import BgeEmbedder, Embedder
from ..models import RetrievedChunk
from ..store.bm25_store import Bm25Store
from ..store.vector_store import ChromaVectorStore
from .hybrid import HybridRetriever
from .reranker import CrossEncoderReranker


@dataclass
class RetrievalResult:
    query: str
    results: List[RetrievedChunk]
    has_confident_source: bool


class RetrievalPipeline:
    def __init__(
        self,
        embedder: Embedder | None = None,
        vector_store: ChromaVectorStore | None = None,
        bm25_store: Bm25Store | None = None,
        reranker: CrossEncoderReranker | None = None,
    ):
        self.embedder = embedder or BgeEmbedder()
        self.vector_store = vector_store or ChromaVectorStore()
        self.bm25_store = bm25_store or Bm25Store.load()
        self.reranker = reranker or CrossEncoderReranker()
        self.hybrid = HybridRetriever(self.embedder, self.vector_store, self.bm25_store)

    def retrieve(self, query: str) -> RetrievalResult:
        candidates = self.hybrid.retrieve(query)
        reranked = self.reranker.rerank(query, candidates)
        confident = bool(reranked) and reranked[0].rerank_score is not None \
            and reranked[0].rerank_score >= settings.min_rerank_score
        return RetrievalResult(query=query, results=reranked, has_confident_source=confident)
