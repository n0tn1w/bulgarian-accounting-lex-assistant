"""Persistent dense vector store backed by ChromaDB.

Stores chunk text + citation metadata alongside precomputed embeddings, and
returns ranked ``Chunk`` objects for a query vector. Persistence lives under
``storage/chroma`` so the index survives between ingest and query runs.
"""
from __future__ import annotations

from typing import List, Tuple

from config import settings
from ..models import Chunk


class ChromaVectorStore:
    def __init__(self, collection_name: str | None = None):
        import chromadb

        self.client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        self.collection = self.client.get_or_create_collection(
            name=collection_name or settings.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        return self.collection.count()

    def reset(self) -> None:
        name = self.collection.name
        self.client.delete_collection(name)
        self.collection = self.client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"}
        )

    def upsert(self, chunks: List[Chunk], vectors: List[List[float]]) -> None:
        if not chunks:
            return
        ids = [c.id for c in chunks]
        docs = [c.text for c in chunks]
        metadatas = []
        for c in chunks:
            rec = c.to_record()
            rec.pop("text", None)
            rec.pop("id", None)
            # Chroma rejects None metadata values -> coerce to empty string.
            metadatas.append({k: (v if v is not None else "") for k, v in rec.items()})
        self.collection.upsert(ids=ids, documents=docs, embeddings=vectors, metadatas=metadatas)

    def query(self, vector: List[float], k: int) -> List[Tuple[Chunk, float]]:
        res = self.collection.query(
            query_embeddings=[vector],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        out: List[Tuple[Chunk, float]] = []
        ids = res["ids"][0]
        docs = res["documents"][0]
        metas = res["metadatas"][0]
        dists = res["distances"][0]
        for cid, doc, meta, dist in zip(ids, docs, metas, dists):
            rec = dict(meta)
            rec["id"] = cid
            rec["text"] = doc
            # cosine distance -> similarity
            out.append((Chunk.from_record(rec), 1.0 - float(dist)))
        return out
