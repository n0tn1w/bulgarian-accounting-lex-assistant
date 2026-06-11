"""Shared evaluation metrics + report formatting. Imported by every runner
(invoice tools, agent, and the laws-RAG colleague's runner) so numbers are
computed identically and printed the same way."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional


def precision_recall_at_k(retrieved: list[str], relevant: list[str], k: int) -> tuple[float, float]:
    """Precision@k and recall@k over id lists. Empty relevant -> (0, 0)."""
    if not relevant:
        return (0.0, 0.0)
    topk = retrieved[:k]
    hit = len(set(topk) & set(relevant))
    precision = hit / len(topk) if topk else 0.0
    recall = hit / len(relevant)
    return (round(precision, 3), round(recall, 3))


def mrr(retrieved: list[str], relevant: list[str]) -> float:
    """Reciprocal rank of the first relevant id (0 if none retrieved)."""
    rel = set(relevant)
    for i, rid in enumerate(retrieved, start=1):
        if rid in rel:
            return round(1.0 / i, 3)
    return 0.0


def numeric_match(got: Optional[Decimal | float], expected: Optional[Decimal | float],
                  tol: float = 0.01) -> bool:
    """Decimal-safe equality within `tol` (default one cent)."""
    if got is None or expected is None:
        return False
    return abs(Decimal(str(got)) - Decimal(str(expected))) <= Decimal(str(tol))


def report(rows: list[dict]) -> str:
    """Render per-row results and per-category aggregates as a printable table.
    Each row: {category, id, metric, value, passed: bool}."""
    lines = ["", "=== eval results ==="]
    by_cat: dict[str, list[bool]] = {}
    for r in rows:
        status = "PASS" if r.get("passed") else "FAIL"
        lines.append(f"[{r['category']:<11}] #{r['id']:<3} {r['metric']:<22} {r['value']}  {status}")
        by_cat.setdefault(r["category"], []).append(bool(r.get("passed")))
    lines.append("--- summary ---")
    for cat, results in by_cat.items():
        passed = sum(results)
        lines.append(f"{cat:<13} {passed}/{len(results)} = {passed / len(results):.0%}")
    return "\n".join(lines)
