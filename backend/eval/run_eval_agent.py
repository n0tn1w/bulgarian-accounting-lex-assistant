"""Phase-2 eval: agent routing + refusal + compliance, vs the synthetic set.

Runs each labeled question through the AGENT (needs LLM_MODEL set) k times and
reports routing accuracy (did it call the labeled tool), refusal calibration, and
compliance accuracy (correct verdict + cited article).

Usage:  LLM_MODEL=... python eval/run_eval_agent.py [tenant_uuid] [k]
"""
from __future__ import annotations

import os
import random
import sys
import time
import uuid

from sqlalchemy import text

from app.db.base import SessionLocal
from app.rag import run as run_agent
from eval.cases import load_cases
from eval.fixtures.invoices import EVAL_TENANT_ID

EVAL_PATH = "eval/eval_set.jsonl"


def _agent_call(db, tenant_id: str, question: str, model: str, retries: int = 6):
    """Run the agent, backing off only on a normalized rate-limit error (any provider,
    via LiteLLM) if LiteLLM's own per-call retries are still exhausted. Honors the
    provider's Retry-After when present. Real errors propagate immediately."""
    import litellm

    for attempt in range(retries):
        try:
            return run_agent(db, uuid.UUID(tenant_id), question, [], model=model)
        except litellm.RateLimitError as exc:
            if attempt == retries - 1:
                raise
            wait = getattr(exc, "retry_after", None) or min(2 ** attempt + random.random(), 60)
            time.sleep(wait)


def score_case(c, ans) -> dict:
    called = [t["tool"] for t in (ans.tool_trace or [])]
    out = {"id": c.id, "category": c.category, "tools": called, "refused": ans.refused}
    if c.category == "refuse":
        out["refusal_ok"] = bool(ans.refused)
    elif c.category == "compliance":
        article_token = c.expected.get("article", "").split()[-1].lower()
        cited = article_token in (ans.reply or "").lower()
        out["routing_ok"] = "query_law" in called
        out["compliance_ok"] = ("query_law" in called) and cited
    elif c.tool:
        out["routing_ok"] = c.tool in called
    return out


def main(tenant_id: str, k: int = 1) -> None:
    model = os.environ.get("LLM_MODEL", "")
    if not model:
        raise SystemExit("set LLM_MODEL for the agent eval")
    db = SessionLocal()
    db.execute(text("SELECT set_config('app.current_tenant', :t, true)"), {"t": tenant_id})
    delay = float(os.environ.get("EVAL_REQUEST_DELAY", "0"))  # proactive pacing for tight tiers
    route_hit = route_tot = ref_ok = ref_tot = comp_ok = comp_tot = 0
    for c in load_cases(EVAL_PATH):
        for _ in range(k):
            ans = _agent_call(db, tenant_id, c.question, model)
            s = score_case(c, ans)
            if "refusal_ok" in s: ref_tot += 1; ref_ok += s["refusal_ok"]
            if "compliance_ok" in s: comp_tot += 1; comp_ok += s["compliance_ok"]
            if "routing_ok" in s: route_tot += 1; route_hit += s["routing_ok"]
            print(f"[{c.category}] #{c.id} tools={s.get('tools')} refused={s.get('refused')}")
            if delay:
                time.sleep(delay)
    if route_tot: print(f"\nrouting accuracy:   {route_hit}/{route_tot} = {route_hit/route_tot:.0%}")
    if ref_tot:   print(f"refusal calibration:{ref_ok}/{ref_tot} = {ref_ok/ref_tot:.0%}")
    if comp_tot:  print(f"compliance accuracy:{comp_ok}/{comp_tot} = {comp_ok/comp_tot:.0%}")
    db.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(EVAL_TENANT_ID),
         int(sys.argv[2]) if len(sys.argv) > 2 else 1)
