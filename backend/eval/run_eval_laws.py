"""Laws-RAG retrieval eval (owned by the laws-RAG colleague). Reuses the shared
metrics. Each case: {"query": ..., "relevant": ["ЗДДС Чл. 66", ...]}.

Usage:  python eval/run_eval_laws.py [k]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.rag.laws import LawsRetriever
from eval.metrics import mrr, precision_recall_at_k, report

EVAL_PATH = "eval/eval_set_laws.jsonl"


def main(k: int = 8) -> None:
    cases = [json.loads(l) for l in Path(EVAL_PATH).read_text(encoding="utf-8").splitlines() if l.strip()]
    retr = LawsRetriever()
    rows = []
    for i, c in enumerate(cases, 1):
        hits = [h.source for h in retr.retrieve(c["query"], top_k=k)]
        pr, rc = precision_recall_at_k(hits, c["relevant"], k=k)
        rows.append({"category": "laws", "id": i, "metric": "P/R/MRR",
                     "value": (pr, rc, mrr(hits, c["relevant"])), "passed": rc > 0})
    print(report(rows))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
