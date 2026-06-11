# Invoice RAG — Evaluation

Synthetic, reproducible eval over 60 hand-authored invoices in a fixed eval tenant.
Phase-1 (deterministic tools) + Phase-2 (the tool-calling agent).

## Setup (once)
    python scripts/seed_eval_tenant.py        # seeds 60 synthetic invoices + indexes (~2-3 min)

## Phase 1 — tool correctness (deterministic, ~2 min)
    python eval/run_eval.py
Numeric accuracy (sum/compare) + retrieval P@k/R@k/MRR (filter/lookup/semantic).
`tests/test_eval_phase1_consistency.py` guards the labels against fixture drift.

## Phase 2 — agent (needs a model; ~10-20 min at k=1)
    LLM_MODEL=groq/llama-3.3-70b-versatile python eval/run_eval_agent.py "" 1
Routing accuracy, refusal calibration, compliance accuracy (correct verdict + cited article).

## Laws RAG (Partner B's extension point)
    python eval/run_eval_laws.py
Add cases to `eval_set_laws.jsonl` (`{"query": ..., "relevant": ["ЗДДС Чл. 66"]}`);
the runner reuses `eval/metrics.py`, so results print in the same format.

## Files
- `metrics.py`, `cases.py` — shared (also imported by the laws runner)
- `fixtures/invoices.py` — the 60 synthetic invoices
- `eval_set.jsonl` — 56 labeled invoice + compliance questions
- `eval_set_laws.jsonl` — laws-retrieval cases (Partner B)
- `run_eval.py` / `run_eval_agent.py` / `run_eval_laws.py` — the three runners
