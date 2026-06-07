"""Per-tenant Okapi BM25 over invoice text.

Holds (invoice_id, tokens) so it can be queried and pickled per tenant to
storage/invoice_bm25/<tenant_id>.pkl. Rebuildable from the DB at any time.
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import List, Tuple

from rank_bm25 import BM25Okapi

from invoice_rag.config import settings
from invoice_rag.retrieval.tokenizer import BgTokenizer


class Bm25InvoiceIndex:
    def __init__(self, tokenizer: BgTokenizer | None = None):
        self.tokenizer = tokenizer or BgTokenizer()
        self.ids: List[str] = []
        self._tokenized: List[List[str]] = []
        self._bm25: BM25Okapi | None = None

    def build(self, items: List[Tuple[str, str]]) -> None:
        """items = [(invoice_id, text), ...]"""
        self.ids = [i for i, _ in items]
        self._tokenized = [self.tokenizer.tokenize(t) for _, t in items]
        safe = [toks if toks else ["∅"] for toks in self._tokenized]
        self._bm25 = BM25Okapi(safe) if safe else None

    def query(self, query_text: str, k: int) -> List[Tuple[str, float]]:
        if self._bm25 is None or not self.ids:
            return []
        q = self.tokenizer.tokenize(query_text) or ["∅"]
        scores = self._bm25.get_scores(q)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(self.ids[i], float(scores[i])) for i in ranked if scores[i] > 0]

    @staticmethod
    def path_for(tenant_id: str) -> Path:
        return settings.bm25_dir / f"{tenant_id}.pkl"

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fh:
            pickle.dump({"ids": self.ids, "tokenized": self._tokenized}, fh,
                        protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def load(cls, path: Path, tokenizer: BgTokenizer | None = None) -> "Bm25InvoiceIndex":
        idx = cls(tokenizer=tokenizer)
        with open(path, "rb") as fh:
            data = pickle.load(fh)
        idx.ids = data["ids"]
        idx._tokenized = data["tokenized"]
        safe = [toks if toks else ["∅"] for toks in idx._tokenized]
        idx._bm25 = BM25Okapi(safe) if safe else None
        return idx
