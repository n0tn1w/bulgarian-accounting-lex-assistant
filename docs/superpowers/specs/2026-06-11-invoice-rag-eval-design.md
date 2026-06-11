# Invoice RAG — Evaluation Design

> Spec for building out the Phase-1 + Phase-2 evaluation of the Invoice RAG +
> Query Agent module. Supersedes the 5-row stub in `backend/eval/`.

**Date:** 2026-06-11
**Owner:** Maya (Invoice RAG + Query Agent)
**Status:** approved design, pre-implementation

## Goal

Produce a reproducible, committable evaluation that quantifies how well the
invoice tools and the tool-calling agent answer real accounting questions —
covering exact numeric accuracy, retrieval quality, agent routing/refusal, and
(new) the cross-RAG invoice+law compliance path.

## Decisions (locked)

1. **Data source: synthetic fixtures.** ~60 hand-authored invoices with known,
   controlled properties. Ground-truth (sums, relevant ids, VAT correctness) is
   exact by construction. Reproducible, committable (no PII), guarantees coverage.
2. **Scope: full eval minus the naive baseline.** Phase-1 tool correctness +
   Phase-2 agent (routing, refusal, compliance). The naive-`/chat` baseline is
   *out of scope for now* but the harness is structured so it can slot in later
   (the existing `_no_model_reply` retrieve-and-summarize path is ~90% of a
   baseline).
3. **Cross-RAG compliance is in scope** as a distinct category — it is the only
   category that exercises the invoice+law synthesis, and it measures the
   false-positive "VAT is correct per ЗДДС" failure mode directly.
4. **Extensible for the laws RAG colleague** via a shared metrics/schema module
   and a per-subsystem runner (he adds `eval_set_laws.jsonl` + `run_eval_laws.py`).

## A. Synthetic dataset — `eval/fixtures/invoices.py`

~60 hand-authored invoices (explicit, eyeball-verifiable — not random) seeded
into a fixed **eval tenant UUID**. Dimensions deliberately spanned:

- **Vendors** (~12): AWS, Microsoft, Google Cloud, a DE vendor, a local BG
  vendor, an ad agency, a consultancy, etc. A few carry BG/EN/Cyrillic name
  variants (to test fuzzy vendor collapse).
- **Dates**: spread across 2024–2025, multiple quarters/months (period + trend).
- **Amounts**: mixed; several deliberately > 5000 BGN.
- **Currencies**: BGN + EUR. **Countries**: BG, DE, other-EU (reverse-charge /
  VAT-reclaim).
- **Flags**: some weekend-issued, some reverse-charge, both directions
  (sale/purchase).
- **Implicit categories**: cloud (AWS/Azure/GCP), marketing (ad agencies),
  consulting — so semantic search has real signal.
- **Compliance**: a handful with *deliberately wrong VAT* (e.g. base 100.00, VAT
  15.00 where 20.00 is correct) alongside correct ones.

Seeded via a new `scripts/seed_eval_tenant.py` (extract → persist → rebuild BM25
+ dense index for the eval tenant).

## B. Question set — `eval/eval_set.jsonl` (~56 cases)

| Category | Count |
|---|---|
| lookup | 5 |
| filter | 10 |
| aggregation | 15 |
| semantic | 10 |
| trend/compare | 5 |
| compliance/cross-RAG | 6 (3 correct VAT, 3 wrong) |
| refuse | 5 |

Total: 56. Aggregation is weighted heaviest — it is the killer use case and where
the numeric-accuracy story is most decisive (and ~3 of the 15 are the
implicit-category hybrid cases described below).

**Case schema** (one JSONL row) — drives both phases from one record:

```json
{
  "id": 12,
  "category": "aggregation",
  "question": "Общо ДДС за Q2 2025?",
  "tool": "sum_invoices",
  "params": {"filters": {"period": "Q2 2025"}, "group_by": null},
  "expected": {"total": "4250.00", "currency": "BGN"},
  "relevant_ids": ["inv-014", "inv-021", "inv-022"]
}
```

- `params` + `expected` → Phase-1 (run the tool directly, check the math).
- `question` + `tool` → Phase-2 (did the agent route NL → the right tool?).

`params.filters` only uses fields `FilterParams` actually supports (vendor,
period, amount range, currency, country, vat_rate, direction, reverse_charge,
doc_type, weekend_only) — there is **no** "category" filter.

### Implicit-category aggregation = the semantic→aggregate hybrid

Questions like *"how much on cloud services?"* have no DB column to filter on —
they require the hybrid pipeline (`semantic_search` to identify the invoices →
`sum` them), which is currently **not wired as a chained capability**. These
cases are labeled with explicit `relevant_ids` (the cloud invoices) + an
`expected.total`, and split across two checks:
- **Phase-1**: sum the labeled `relevant_ids` directly → confirms the *arithmetic*
  is exact once the right invoices are chosen.
- **Phase-2**: does the agent actually chain semantic_search → sum and reach
  `expected.total`? This is where the eval **surfaces the missing hybrid** — a
  low score here is the empirical case for building it (the rubric-defensible
  contribution per CLAUDE.md). Counted as ~3 of the 10 aggregation cases.

Per-category label shapes:
- **lookup**: `tool:get_invoice`, `expected.id`
- **filter**: `tool:filter_invoices`, `params`, `relevant_ids`
- **aggregation**: `tool:sum_invoices`, `params`, `expected.total`
- **semantic**: `tool:semantic_search`, `relevant_ids`
- **trend**: `tool:compare_periods`, `params`, `expected.delta`
- **compliance**: `tool:query_law` (+invoice), `expected={verdict, article, expected_vat}`
- **refuse**: `tool:null`, `expected.refused=true`

## C. Runners + shared metrics

**`eval/metrics.py`** (shared — imported by the laws-RAG runner too):
- `precision_recall_at_k(retrieved, relevant, k)`
- `mrr(retrieved, relevant)`
- `numeric_match(got, expected, tol=0.01)` — Decimal compare, cent tolerance
- `report(rows)` — per-category table + aggregate summary

**`eval/cases.py`** (shared): `EvalCase` pydantic model + `load_cases(path)`.

**`run_eval.py` (Phase-1, rewritten)** — removes the hardcoded
`vendor="AWS"`/`min_amount=5000` placeholders. Reads `case.params`, invokes the
named tool, scores via `metrics.py`:
- aggregation/compare → `numeric_match(result.total, expected.total)`
- filter/lookup → `precision_recall_at_k(result_ids, relevant_ids)`
- semantic → `precision_recall_at_k` + `mrr`

Deterministic, no LLM — produces the exact-accuracy headline numbers.

**`run_eval_agent.py` (Phase-2)** — runs each `question` through the live agent
(`LLM_MODEL=groq`); scores routing accuracy, refusal calibration, and compliance
accuracy (correct verdict + cited `expected_article`). Fixes the current bug of
passing `model="eval"` hardcoded instead of the configured model.

## D. Agent-eval practicalities (Groq + CPU)

- **Rate limits**: default `k=1`; exponential backoff on 429s; optional `k=3`
  for the headline categories only.
- **CPU slowness**: warm the laws pipeline once at start; treat the agent run as
  an offline batch job (~10–20 min at k=1).
- **Non-determinism**: report over `k` runs (k=1 fast; k=3 stable).
- Lean on Phase-1 for exact numbers; Phase-2 for routing/refusal/cross-RAG.

**Estimated run time:** seed ~2–3 min (one-time); Phase-1 ~1–2 min; Phase-2
~10–20 min (k=1) or ~30–60 min (k=3).

## Extensibility — laws RAG colleague

Each subsystem owns its eval set + runner; they share `metrics.py` + `cases.py`.

```
backend/eval/
├── metrics.py           # SHARED
├── cases.py             # SHARED
├── eval_set.jsonl       # invoice + compliance (Maya)
├── eval_set_laws.jsonl  # legal queries → relevant article refs (Partner B)
├── run_eval.py          # invoice tools (Maya)
├── run_eval_agent.py    # agent (Maya)
├── run_eval_laws.py     # LawsRetriever retrieval quality (Partner B)
└── fixtures/            # synthetic invoices (Maya)
```

Partner B adds `eval_set_laws.jsonl` (`{"query": ..., "relevant": ["ЗДДС Чл. 66"]}`)
and a ~30-line `run_eval_laws.py` that imports `metrics.py`, calls
`LawsRetriever().retrieve(q, k)`, matches returned chunk `source`s against
`relevant`, and prints the same report table. Shared touchpoint: the compliance
cases' `expected_article` labels are co-owned (agreed jointly).

## Out of scope

- Naive-`/chat` baseline comparison (deferred; harness leaves room).
- Re-evaluating the laws retrieval itself (Partner B's runner).
- Multi-turn coherence (Phase-2 stretch, not covered here).

## Success criteria

- Phase-1 reports exact numeric accuracy per category over the synthetic set.
- Phase-2 reports routing accuracy, refusal calibration, compliance accuracy.
- One `python eval/run_eval.py <tenant>` + `LLM_MODEL=… python eval/run_eval_agent.py <tenant>`
  reproduces all numbers from committed fixtures.
- Colleague can add a laws runner without touching invoice code.
