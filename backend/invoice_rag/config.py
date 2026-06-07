"""Tunables for the invoice RAG engine (mirrors lex/config.py style)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    # dense embedder — multilingual incl. Bulgarian; same model the laws RAG uses
    embedding_model: str = "BAAI/bge-m3"
    bm25_dir: Path = BASE_DIR / "storage" / "invoice_bm25"
    dense_top_k: int = 30
    bm25_top_k: int = 30
    rrf_k0: int = 60
    final_top_k: int = 10


settings = Settings()
