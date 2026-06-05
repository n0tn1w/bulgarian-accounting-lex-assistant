"""Cross-encoder reranking of fused candidates (bge-reranker-v2-m3).

A cross-encoder scores each (query, passage) pair jointly, giving much sharper
relevance ordering than the first-stage retrievers. Loaded lazily.
"""
from __future__ import annotations

from typing import List

from config import settings
from ..models import RetrievedChunk


class CrossEncoderReranker:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.reranker_model
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            print(f"  [rerank] loading model {self.model_name} ...")
            self._model = CrossEncoder(self.model_name)
        return self._model

    def rerank(self, query: str, candidates: List[RetrievedChunk]) -> List[RetrievedChunk]:
        if not candidates:
            return []
        model = self._ensure_model()
        pairs = [[query, rc.chunk.text] for rc in candidates]
        scores = model.predict(pairs)
        for rc, score in zip(candidates, scores):
            rc.rerank_score = float(score)
        ranked = sorted(candidates, key=lambda r: r.rerank_score, reverse=True)
        return ranked[: settings.final_top_n]
