"""Phase-2 eval: routing + refusal calibration for the agent, vs the naive baseline.

Runs each labeled question through the AGENT (needs LLM_MODEL set) k times and
reports routing accuracy (did it call the labeled tool) and refusal calibration.
Compare against the naive baseline via the existing run_eval.py / /chat/baseline.

Usage:  LLM_MODEL=... python eval/run_eval_agent.py <tenant_uuid> [k]
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import text

from app.db.base import SessionLocal
from invoice_rag.agent import run as run_agent

EVAL_PATH = Path(__file__).parent / "eval_set.jsonl"


def main(tenant_id: str, k: int = 1) -> None:
    db = SessionLocal()
    db.execute(text("SELECT set_config('app.current_tenant', :t, true)"), {"t": tenant_id})
    rows = [json.loads(l) for l in EVAL_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    routing_hits = total = refusal_ok = refusal_total = 0
    for r in rows:
        expected_tool, should_refuse = r.get("tool"), r["category"] == "refuse"
        for _ in range(k):
            ans = run_agent(db, uuid.UUID(tenant_id), r["question"], history=[], model="eval")
            called = [t["tool"] for t in ans.tool_trace]
            if should_refuse:
                refusal_total += 1
                refusal_ok += 1 if ans.refused else 0
            elif expected_tool:
                total += 1
                routing_hits += 1 if expected_tool in called else 0
            print(f"[{r['category']}] {r['question']!r} -> tools={called} refused={ans.refused}")
    if total:
        print(f"\nrouting accuracy: {routing_hits}/{total} = {routing_hits/total:.0%}")
    if refusal_total:
        print(f"refusal calibration: {refusal_ok}/{refusal_total} = {refusal_ok/refusal_total:.0%}")
    db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: LLM_MODEL=... python eval/run_eval_agent.py <tenant_uuid> [k]")
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 1)
