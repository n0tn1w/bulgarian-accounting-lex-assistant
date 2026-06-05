"""Ingestion pipeline: scrape -> clean -> chunk -> dedup -> embed -> index.

Fault-tolerant per law: each SourceSpec's candidate URLs are tried in order and
the first that yields chunks wins; a failing source is logged and skipped so the
rest of the corpus still builds. Produces a persisted Chroma collection + BM25
index, and writes chunks.jsonl for inspection (L6 data-quality visibility).
"""
from __future__ import annotations

import json
from typing import List

from tqdm import tqdm

from config import settings
from .embedding.embedder import BgeEmbedder, Embedder
from .models import Chunk, SourceDoc
from .parsing.chunker import ArticleChunker
from .parsing.cleaner import HtmlCleaner
from .scraping.sources import TARGET_SOURCES, SourceSpec, get_scraper_for
from .store.bm25_store import Bm25Store
from .store.vector_store import ChromaVectorStore


class IngestPipeline:
    def __init__(self, embedder: Embedder | None = None):
        settings.ensure_dirs()
        self.cleaner = HtmlCleaner()
        self.chunker = ArticleChunker()
        self.embedder = embedder or BgeEmbedder()

    # -- stages -------------------------------------------------------------
    def _scrape_and_chunk(self, spec: SourceSpec) -> List[Chunk]:
        for site, url in spec.candidates:
            try:
                scraper = get_scraper_for(site)
                docs = scraper.scrape(spec.for_candidate(site, url))
            except Exception as exc:
                print(f"  [skip] {spec.law_abbr} via {site}: fetch failed: {exc}")
                continue
            chunks: List[Chunk] = []
            for doc in docs:
                clean = self.cleaner.clean(doc.html)
                chunks.extend(self.chunker.chunk_document(doc, clean))
            if chunks:
                print(f"  [ok] {spec.law_abbr} via {site}: {len(chunks)} chunks")
                return chunks
            print(f"  [skip] {spec.law_abbr} via {site}: 0 chunks parsed")
        print(f"  [FAIL] {spec.law_abbr}: no candidate produced chunks")
        return []

    @staticmethod
    def _dedup(chunks: List[Chunk]) -> List[Chunk]:
        """Drop exact-text duplicates (L6 data quality)."""
        seen: set[str] = set()
        out: List[Chunk] = []
        for c in chunks:
            key = c.text.strip()
            if key in seen:
                continue
            seen.add(key)
            out.append(c)
        return out

    def run(self, reset: bool = True) -> int:
        all_chunks: List[Chunk] = []
        print("== Scraping & chunking ==")
        for spec in TARGET_SOURCES:
            all_chunks.extend(self._scrape_and_chunk(spec))

        before = len(all_chunks)
        all_chunks = self._dedup(all_chunks)
        print(f"== Chunks: {before} parsed -> {len(all_chunks)} after dedup ==")
        if not all_chunks:
            print("No chunks produced. Check source URLs in scraping/sources.py.")
            return 0

        self._write_jsonl(all_chunks)

        # --- dense index ---
        print("== Embedding & indexing (dense) ==")
        vector_store = ChromaVectorStore()
        if reset:
            vector_store.reset()
        for i in tqdm(range(0, len(all_chunks), settings.embedding_batch_size)):
            batch = all_chunks[i:i + settings.embedding_batch_size]
            vectors = self.embedder.embed_documents([c.text for c in batch])
            vector_store.upsert(batch, vectors)

        # --- sparse     ---
        print("== Building BM25 index (sparse) ==")
        bm25 = Bm25Store()
        bm25.build(all_chunks)
        bm25.save()

        print(f"== Done. Indexed {len(all_chunks)} chunks "
              f"(Chroma count={vector_store.count()}). ==")
        return len(all_chunks)

    @staticmethod
    def _write_jsonl(chunks: List[Chunk]) -> None:
        with open(settings.chunks_path, "w", encoding="utf-8") as fh:
            for c in chunks:
                fh.write(json.dumps(c.to_record(), ensure_ascii=False) + "\n")
        print(f"  wrote {settings.chunks_path}")
