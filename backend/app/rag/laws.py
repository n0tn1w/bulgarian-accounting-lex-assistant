"""Laws RAG seam.

The laws retriever is provided by the lex engine (repo-root `lex/`: scrapes lex.bg,
hybrid BM25 + dense retrieval with reranking and article-level citations). Until that
wiring lands this returns nothing, so /chat answers from the invoices RAG alone.

Next step: implement retrieve() to call lex's RetrievalPipeline and map its results
to RetrievedChunk.
"""

from __future__ import annotations

from app.rag.base import RetrievedChunk


class LawsRetriever:
    name = "laws"

    def __init__(self, db=None):
        self.db = db

    def retrieve(self, query: str, top_k: int = 6, **_: object) -> list[RetrievedChunk]:
        return []
