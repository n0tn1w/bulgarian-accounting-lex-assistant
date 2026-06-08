# Invoice RAG — Phase 1 evaluation

1. Ingest real sample invoices into a dedicated eval tenant (via the existing
   `/documents/extract-*` + `/workspace/invoices` endpoints, or a seed script).
2. Rebuild the index: `python scripts/rebuild_invoice_index.py <tenant_uuid>`.
3. Label `eval_set.jsonl` (~50 Qs): for each, set `tool`, `relevant_ids`, and
   `expected_total` where applicable. Distribution: 10 lookup / 10 filter /
   10 aggregation / 10 semantic / 5 trend-compare / 5 refuse.
4. Run: `python eval/run_eval.py <tenant_uuid>`.
5. Baseline: compare against the naive `/chat` on the same questions.

Metrics: numeric accuracy (sum/compare/filter exact-match), retrieval P@k/R@k/MRR
(semantic), citation precision/recall.

## Phase 2 — agent eval

With `LLM_MODEL` set and the index built:
`LLM_MODEL=<model> python eval/run_eval_agent.py <tenant_uuid> 3`

Reports routing accuracy (did the agent call the labeled tool), refusal calibration,
and prints the tools called per question. The LLM is non-deterministic — `k`>1 runs
each question multiple times. Compare against the naive retrieve-and-stuff baseline
via the existing `run_eval.py`.
