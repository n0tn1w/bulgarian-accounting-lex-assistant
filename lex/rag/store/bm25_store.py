"""Sparse keyword index (BM25) over Bulgarian-tokenized chunks.

Holds the chunks + their tokenized form so it can be rebuilt/queried and
pickled to ``storage/bm25.pkl``. Pairs with the dense store in the hybrid
retriever.
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import List, Tuple

from rank_bm25 import BM25Okapi

from config import settings
from ..models import Chunk
from ..text.tokenizer import BgTokenizer


class Bm25Store:
    def __init__(self, tokenizer: BgTokenizer | None = None):
        self.tokenizer = tokenizer or BgTokenizer()
        self.chunks: List[Chunk] = []
        self._tokenized: List[List[str]] = []
        self._bm25: BM25Okapi | None = None

    def build(self, chunks: List[Chunk]) -> None:
        self.chunks = list(chunks)
        self._tokenized = [self.tokenizer.tokenize(c.text) for c in self.chunks]
        # BM25Okapi needs at least one non-empty doc.
        safe = [toks if toks else ["∅"] for toks in self._tokenized]
        self._bm25 = BM25Okapi(safe)

    def query(self, query_text: str, k: int) -> List[Tuple[Chunk, float]]:
        if self._bm25 is None or not self.chunks:
            return []
        q_tokens = self.tokenizer.tokenize(query_text) or ["∅"]
        scores = self._bm25.get_scores(q_tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(self.chunks[i], float(scores[i])) for i in ranked if scores[i] > 0]

    # -- persistence --------------------------------------------------------
    def save(self, path: Path | None = None) -> None:
        path = path or settings.bm25_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fh:
            pickle.dump(
                {"chunks": self.chunks, "tokenized": self._tokenized},
                fh,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

    @classmethod
    def load(cls, path: Path | None = None, tokenizer: BgTokenizer | None = None) -> "Bm25Store":
        path = path or settings.bm25_path
        store = cls(tokenizer=tokenizer)
        with open(path, "rb") as fh:
            data = pickle.load(fh)
        store.chunks = data["chunks"]
        store._tokenized = data["tokenized"]
        safe = [toks if toks else ["∅"] for toks in store._tokenized]
        store._bm25 = BM25Okapi(safe)
        return store
