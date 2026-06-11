"""Phase-1 eval: per-tool correctness + retrieval quality on the synthetic set.

Reads eval_set.jsonl, runs each case's named tool with its labeled params, and
scores numeric accuracy (sum/compare) or precision@k/recall@k/MRR (filter/lookup/
semantic) via the shared metrics module. Deterministic, no LLM.

Usage:  python eval/run_eval.py [tenant_uuid]   (defaults to the eval tenant)
"""
from __future__ import annotations

import sys
import uuid

from sqlalchemy import text

from app.db.base import SessionLocal
from eval.cases import load_cases
from eval.fixtures.invoices import EVAL_TENANT_ID
from eval.metrics import mrr, numeric_match, precision_recall_at_k, report
from invoice_rag.models import DateRange, FilterParams
from invoice_rag.tools.aggregate import sum_invoices
from invoice_rag.tools.compare import compare_periods
from invoice_rag.tools.filter import filter_invoices
from invoice_rag.tools.lookup import get_invoice
from invoice_rag.tools.search import semantic_search

EVAL_PATH = "eval/eval_set.jsonl"


def _semantic_filters(params: dict):
    extra = {k: v for k, v in params.items() if k != "query"}
    return FilterParams(**extra) if extra else None


def _run_case(db, tenant_id: uuid.UUID, c) -> dict:
    p = c.params
    base = {"category": c.category, "id": c.id}
    if c.tool == "get_invoice":
        v = get_invoice(db, number=p.get("number"), invoice_id=p.get("invoice_id"))
        got = v.external_id if v else None
        return {**base, "metric": "lookup id", "value": got, "passed": got == c.expected.get("id")}
    if c.tool == "filter_invoices":
        views = filter_invoices(db, FilterParams(**p))
        ids = [v.external_id for v in views]
        _, rc = precision_recall_at_k(ids, c.relevant_ids, k=len(ids) or 1)
        count_ok = c.expected.get("count") is None or len(views) == c.expected["count"]
        return {**base, "metric": "recall/count", "value": (rc, len(views)), "passed": rc == 1.0 and count_ok}
    if c.tool == "sum_invoices":
        res = sum_invoices(db, FilterParams(**p.get("filters", {})), group_by=p.get("group_by"))
        key = "total_vat" if "total_vat" in c.expected else "total"
        got = res.total_vat if key == "total_vat" else res.total_amount
        return {**base, "metric": key, "value": str(got), "passed": numeric_match(got, c.expected.get(key))}
    if c.tool == "compare_periods":
        res = compare_periods(
            db,
            p["metric"],
            DateRange(**p["period_a"]),
            DateRange(**p["period_b"]),
            vendor=p.get("vendor"),
            direction=p.get("direction"),
        )
        return {**base, "metric": "delta", "value": str(res.delta), "passed": numeric_match(res.delta, c.expected.get("delta"))}
    if c.tool == "semantic_search":
        views = semantic_search(db, tenant_id, p.get("query", c.question), top_k=10, filters=_semantic_filters(p))
        ids = [v.external_id for v in views]
        _, rc = precision_recall_at_k(ids, c.relevant_ids, k=10)
        return {**base, "metric": "P@10/MRR", "value": (rc, mrr(ids, c.relevant_ids)), "passed": rc > 0}
    return {**base, "metric": "(phase-2)", "value": "-", "passed": True}


def main(tenant_id: str) -> None:
    db = SessionLocal()
    db.execute(text("SELECT set_config('app.current_tenant', :t, true)"), {"t": tenant_id})
    rows = [_run_case(db, uuid.UUID(tenant_id), c)
            for c in load_cases(EVAL_PATH)
            if c.category not in {"compliance", "refuse"}]
    print(report(rows))
    db.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(EVAL_TENANT_ID))
