"""Central configuration for the lex retrieval module.

All tunables (paths, model names, retrieval depths, fusion/rerank settings) live
here so the rest of the package stays free of magic numbers. Import the module
level ``settings`` singleton, e.g. ``from config import settings``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Repo-relative anchor: lex/
BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    # --- filesystem layout -------------------------------------------------
    base_dir: Path = BASE_DIR
    raw_dir: Path = BASE_DIR / "data" / "raw"
    processed_dir: Path = BASE_DIR / "data" / "processed"
    chunks_path: Path = BASE_DIR / "data" / "processed" / "chunks.jsonl"
    storage_dir: Path = BASE_DIR / "storage"
    chroma_dir: Path = BASE_DIR / "storage" / "chroma"
    bm25_path: Path = BASE_DIR / "storage" / "bm25.pkl"

    # --- models ------------------------------------------------------------
    # bge-m3 has strong multilingual coverage incl. Bulgarian. Swap freely;
    # the Embedder interface decouples the rest of the code from this choice.
    embedding_model: str = "BAAI/bge-m3"
    embedding_batch_size: int = 16
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # Chroma collection
    collection_name: str = "bg_legislation"

    # --- scraping ----------------------------------------------------------
    request_timeout: int = 30
    polite_delay_sec: float = 1.5      # delay between requests to the same host
    max_retries: int = 3

    # --- chunking ----------------------------------------------------------
    min_chunk_chars: int = 40          # drop tiny fragments (L6 data quality)
    max_chunk_chars: int = 1500        # long алинеи get sentence-window split
    chunk_overlap_chars: int = 200

    # --- retrieval ---------------------------------------------------------
    dense_top_k: int = 30              # candidates from vector search
    bm25_top_k: int = 30               # candidates from sparse search
    rrf_k0: int = 60                   # RRF smoothing constant
    fused_candidates: int = 40         # candidates handed to the reranker
    final_top_n: int = 5               # passages returned to the caller
    # Below this rerank score we consider that no confident source was found
    # (retrieval-side analog of "отказ при липса на източник").
    min_rerank_score: float = 0.3

    def ensure_dirs(self) -> None:
        for d in (self.raw_dir, self.processed_dir, self.storage_dir, self.chroma_dir):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
