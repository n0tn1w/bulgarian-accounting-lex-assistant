"""Entrypoint: run a HARDCODED query against the index and print cited passages.

    python lex/run_query.py

This is the "pure retrieval" demo: no LLM generation, no UI. It prints the
top passages with their citation (закон, чл., ал.), source URL and scores.
Edit ``QUERY`` below to try another question.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Cyrillic output on Windows consoles (cp1252) would crash; force UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag.retrieval.pipeline import RetrievalPipeline

#QUERY  = "Кои лица са самоосигуряващи се лица по Кодекса за социално осигуряване"
#QUERY = "Върху какъв осигурителен доход се дължат осигурителни вноски от самоосигуряващите се лица"
QUERY = "За кои социални рискове са задължително осигурени самоосигуряващите се лица"

#QUERY = "как се готви мусака"


def main() -> None:
    pipeline = RetrievalPipeline()
    result = pipeline.retrieve(QUERY)

    print("\n" + "=" * 78)
    print(f"Заявка: {result.query}")
    print("=" * 78)

    if not result.has_confident_source:
        print("\nНяма достатъчно надежден източник за тази заявка .")
        return

    if not result.results:
        print("Няма намерени резултати.")
        return

    for i, rc in enumerate(result.results, 1):
        cit = rc.chunk.citation
        print(f"\n[{i}] {cit.label()}  —  {cit.law_name}")
        print(f"    източник: {cit.source_site} | {cit.url}")
        print(f"    rerank={rc.rerank_score:.4f}  fused={rc.fused_score:.4f}  "
              f"dense_rank={rc.dense_rank}  bm25_rank={rc.bm25_rank}")
        text = rc.chunk.text
        snippet = text if len(text) <= 600 else text[:600] + " ..."
        print(f"    {snippet}")


if __name__ == "__main__":
    main()
