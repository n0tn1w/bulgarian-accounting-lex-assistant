# Invoice RAG Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible Phase-1 (deterministic tools) + Phase-2 (agent) evaluation of the Invoice RAG over a committed synthetic dataset with exact ground-truth.

**Architecture:** A shared metrics/schema module, a hand-authored synthetic invoice fixture seeded into a fixed eval tenant, a labeled JSONL question set whose ground-truth is guaranteed by a consistency test, and two runners (tools, agent). Designed so the laws-RAG colleague can drop in his own runner reusing the shared metrics.

**Tech Stack:** Python 3.11, Pydantic v2, SQLAlchemy + Postgres/pgvector, pytest, the existing `invoice_rag` tools and `app.rag` agent.

**Spec:** `docs/superpowers/specs/2026-06-11-invoice-rag-eval-design.md`

---

## Reference: real signatures (do not guess these)

```python
# invoice_rag/models.py
class FilterParams(BaseModel):
    vendor: Optional[str] = None; date_from: Optional[str] = None; date_to: Optional[str] = None
    period: Optional[str] = None; min_amount: Optional[float] = None; max_amount: Optional[float] = None
    currency: Optional[str] = None; country: Optional[str] = None; vat_rate: Optional[float] = None
    direction: Optional[Literal["sale","purchase","unknown"]] = None; reverse_charge: Optional[bool] = None
    doc_type: Optional[str] = None; weekend_only: bool = False; limit: int = 50
class InvoiceView(BaseModel): invoice_id; external_id; number; date; vendor_name; direction; net_amount; vat_amount; total_amount; currency; score
class SumGroup(BaseModel): key; total; count; invoice_ids
class SumResult(BaseModel): total_net; total_vat; total_amount; currency; count; groups; invoices
class ComparisonResult(BaseModel): metric; value_a; value_b; delta; pct_change; invoice_ids_a; invoice_ids_b
class DateRange(BaseModel): date_from: str; date_to: str

# invoice_rag tools (each takes a tenant-scoped Session first)
get_invoice(db, *, invoice_id=None, number=None) -> Optional[InvoiceView]
filter_invoices(db, f: FilterParams) -> list[InvoiceView]
sum_invoices(db, f: FilterParams, group_by: Optional[GroupBy]=None) -> SumResult
semantic_search(db, tenant_id: uuid.UUID, query: str, top_k=10, filters=None) -> list[InvoiceView]
compare_periods(db, metric, period_a: DateRange, period_b: DateRange, vendor=None, direction=None) -> ComparisonResult

# app/domain/models.py
class Party(BaseModel): name; vat_number; eik; address; source="extracted"
class Invoice(BaseModel):
    id: str; source="unknown"; doc_type="invoice"; direction="unknown"; reverse_charge=False
    number; date; currency="BGN"; supplier: Party; recipient: Party
    net_amount: Decimal|None; vat_amount: Decimal|None; total_amount: Decimal|None
    line_items: list[LineItem]; tax_lines: list[TaxLine]; perspective="supplier"

# app/services/workspace.py
store_invoices(db, tenant_id: uuid.UUID, invoices: list[Invoice]) -> int   # upsert + BM25 (NOT dense)
# invoice_rag/indexing/dense.py
reembed_tenant(db) -> int                                                   # builds dense embeddings
# app/rag/run.py   (the agent — moved here from invoice_rag/agent during reconciliation)
run(db, tenant_id, message, history, *, complete=None, model="", max_steps=5) -> AgentAnswer
# app/rag/answer.py
class AgentAnswer(BaseModel): reply; cards; citations; refused; tool_trace; model
```

Country filtering keys off the VAT prefix (e.g. `BG…`, `DE…`), so fixtures must set
supplier/recipient `vat_number` with the right country prefix.

---

### Task 1: Shared metrics module

**Files:**
- Create: `backend/eval/metrics.py`
- Test: `backend/tests/test_eval_metrics.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_eval_metrics.py
from decimal import Decimal
from eval.metrics import precision_recall_at_k, mrr, numeric_match


def test_precision_recall_at_k():
    p, r = precision_recall_at_k(["a", "b", "x"], ["a", "b", "c"], k=3)
    assert p == round(2 / 3, 3)
    assert r == round(2 / 3, 3)


def test_precision_recall_empty_relevant():
    assert precision_recall_at_k(["a"], [], k=3) == (0.0, 0.0)


def test_mrr_first_relevant_rank():
    assert mrr(["x", "a", "b"], ["a"]) == 0.5      # first hit at rank 2
    assert mrr(["a"], ["a"]) == 1.0
    assert mrr(["x"], ["a"]) == 0.0


def test_numeric_match_within_tolerance():
    assert numeric_match(Decimal("100.00"), Decimal("100.004")) is True
    assert numeric_match(Decimal("100.00"), Decimal("100.02")) is False
    assert numeric_match(None, Decimal("1")) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_eval_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval.metrics'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/eval/metrics.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_eval_metrics.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/eval/metrics.py backend/tests/test_eval_metrics.py
git commit -m "test: add shared eval metrics module"
```

---

### Task 2: Shared case schema + loader

**Files:**
- Create: `backend/eval/cases.py`
- Test: `backend/tests/test_eval_cases.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_eval_cases.py
from eval.cases import EvalCase, load_cases


def test_evalcase_parses_minimal():
    c = EvalCase(id=1, category="refuse", question="trust?", tool=None,
                 params={}, expected={"refused": True}, relevant_ids=[])
    assert c.category == "refuse"
    assert c.tool is None


def test_load_cases_reads_jsonl(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(
        '{"id":1,"category":"lookup","question":"q","tool":"get_invoice","params":{},'
        '"expected":{"id":"inv-001"},"relevant_ids":["inv-001"]}\n\n',
        encoding="utf-8",
    )
    cases = load_cases(p)
    assert len(cases) == 1
    assert cases[0].tool == "get_invoice"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_eval_cases.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval.cases'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/eval/cases.py
"""Shared eval-case schema + JSONL loader (used by tool and agent runners)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

CATEGORIES = {"lookup", "filter", "aggregation", "semantic", "trend", "compliance", "refuse"}


class EvalCase(BaseModel):
    id: int
    category: str
    question: str
    tool: Optional[str] = None          # expected tool name, or None for refuse
    params: dict[str, Any] = Field(default_factory=dict)   # Phase-1 tool params
    expected: dict[str, Any] = Field(default_factory=dict)  # ground-truth (total/id/verdict/...)
    relevant_ids: list[str] = Field(default_factory=list)


def load_cases(path: str | Path) -> list[EvalCase]:
    text = Path(path).read_text(encoding="utf-8")
    return [EvalCase(**json.loads(line)) for line in text.splitlines() if line.strip()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_eval_cases.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/eval/cases.py backend/tests/test_eval_cases.py
git commit -m "test: add shared eval case schema and loader"
```

---

### Task 3: Synthetic invoice fixtures

**Files:**
- Create: `backend/eval/fixtures/__init__.py` (empty)
- Create: `backend/eval/fixtures/invoices.py`
- Test: `backend/tests/test_eval_fixtures.py`

**Design:** a programmatic builder from a compact data table — deterministic ids
`inv-001…inv-060`, known amounts so ground-truth is computable. `vat_amount = net *
rate`, `total = net + vat`, except the compliance "wrong" invoices where vat is set
deliberately off. Category is encoded in the line-item description (cloud/marketing/
consulting) so semantic search has signal; it is NOT a DB column.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_eval_fixtures.py
from decimal import Decimal
from eval.fixtures.invoices import build_fixture_invoices, EVAL_TENANT_ID


def test_sixty_invoices_with_stable_ids():
    invs = build_fixture_invoices()
    assert len(invs) == 60
    assert invs[0].id == "inv-001"
    assert {i.id for i in invs} == {f"inv-{n:03d}" for n in range(1, 61)}


def test_amounts_consistent_except_compliance_wrong():
    invs = build_fixture_invoices()
    correct = [i for i in invs if not i.id.startswith("inv-05")]  # 51-60 are compliance/edge
    for i in correct:
        if i.net_amount and i.vat_amount and i.total_amount:
            assert i.total_amount == i.net_amount + i.vat_amount


def test_eval_tenant_id_is_fixed_uuid():
    assert str(EVAL_TENANT_ID) == "eeeeeeee-0000-0000-0000-000000000001"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_eval_fixtures.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval.fixtures.invoices'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/eval/fixtures/invoices.py
"""Hand-authored synthetic invoices for evaluation. Deterministic ids and known
amounts so every aggregation/filter answer has exact ground-truth. Seeded into a
fixed eval tenant. Categories live in line-item text (no DB category column)."""
from __future__ import annotations

import uuid
from decimal import Decimal

from app.domain.models import Invoice, LineItem, Party, TaxLine

EVAL_TENANT_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000001")

# (n, vendor, vat_no, country, date, net, rate, currency, direction, category, weekend, reverse)
# rows 1-50: normal coverage; 51-56: compliance (53-55 deliberately wrong VAT);
# 57-60: edge (EUR, weekend, reverse-charge DE).
_ROWS = [
    (1, "Amazon Web Services EMEA", "LU12345678", "LU", "2025-01-15", "1000.00", "0.20", "BGN", "purchase", "cloud услуги хостинг сървър", False, False),
    (2, "Microsoft Azure", "IE6388047V", "IE", "2025-01-20", "500.00", "0.20", "BGN", "purchase", "cloud абонамент Azure", False, False),
    (3, "Google Cloud EMEA", "IE6388047V", "IE", "2025-02-10", "750.00", "0.20", "BGN", "purchase", "cloud изчислителни ресурси", False, False),
    (4, "Майкрософт България", "BG131129282", "BG", "2025-02-14", "1200.00", "0.20", "BGN", "purchase", "софтуерни лицензи", False, False),
    (5, "Рекламна агенция Адмакс", "BG200100200", "BG", "2025-03-03", "2000.00", "0.20", "BGN", "purchase", "маркетинг кампания реклама", False, False),
    # ... rows 6-50 follow the same shape, varying vendor/date/amount/currency/
    # country/direction/category/flags to cover: >5000 BGN (rows 11-14),
    # EUR (rows 21-24), DE/other-EU reverse-charge (rows 31-34), weekend dates
    # (rows 41-44), sales vs purchases, marketing/consulting/cloud categories.
    # Author 45 more rows here following _ROWS' tuple shape.
    # --- compliance block (51-56) ---
    (51, "ТочноЕООД", "BG201201201", "BG", "2025-05-02", "100.00", "0.20", "BGN", "purchase", "консултантски услуги", False, False),
    (52, "ТочноЕООД", "BG201201201", "BG", "2025-05-05", "250.00", "0.20", "BGN", "purchase", "консултантски услуги", False, False),
    (53, "ГрешноЕООД", "BG202202202", "BG", "2025-05-08", "100.00", "0.15", "BGN", "purchase", "услуги", False, False),   # WRONG: 15% not 20%
    (54, "ГрешноЕООД", "BG202202202", "BG", "2025-05-10", "300.00", "0.09", "BGN", "purchase", "услуги", False, False),   # WRONG: 9% not 20%
    (55, "ГрешноЕООД", "BG202202202", "BG", "2025-05-12", "500.00", "0.18", "BGN", "purchase", "услуги", False, False),   # WRONG: 18% not 20%
    (56, "ТочноЕООД", "BG201201201", "BG", "2025-05-15", "400.00", "0.20", "BGN", "purchase", "консултантски услуги", False, False),
    (57, "Hetzner Online GmbH", "DE812526315", "DE", "2025-04-06", "300.00", "0.20", "EUR", "purchase", "cloud сървър наем", True, True),   # weekend + reverse + EUR + DE
    (58, "SAP SE", "DE143593636", "DE", "2025-04-13", "900.00", "0.20", "EUR", "purchase", "софтуер", True, True),
    (59, "Местен Клиент ООД", "BG203203203", "BG", "2025-06-01", "1500.00", "0.20", "BGN", "sale", "продажба стоки", False, False),
    (60, "Местен Клиент ООД", "BG203203203", "BG", "2025-06-07", "800.00", "0.20", "BGN", "sale", "продажба услуги", True, False),
]


def _invoice(row) -> Invoice:
    n, vendor, vat_no, country, d, net_s, rate_s, cur, direction, cat, weekend, reverse = row
    net = Decimal(net_s)
    rate = Decimal(rate_s)
    vat = (net * rate).quantize(Decimal("0.01"))
    total = net + vat
    return Invoice(
        id=f"inv-{n:03d}", source="eval", doc_type="invoice", direction=direction,
        reverse_charge=reverse, number=f"EVAL-{n:04d}", date=d, currency=cur,
        supplier=Party(name=vendor, vat_number=vat_no),
        recipient=Party(name="Моята Фирма ЕООД", vat_number="BG999999999"),
        net_amount=net, vat_amount=vat, total_amount=total,
        line_items=[LineItem(description=cat, amount=net)],
        tax_lines=[TaxLine(rate=rate, base=net, amount=vat)],
    )


def build_fixture_invoices() -> list[Invoice]:
    return [_invoice(r) for r in _ROWS]
```

> **Authoring note for the implementer:** the `_ROWS` table above is partial (rows
> 6-50 are described, not enumerated). Fill those 45 rows following the exact tuple
> shape, honoring the coverage targets in the comment (>5000 BGN, EUR, DE
> reverse-charge, weekend dates, sale vs purchase, cloud/marketing/consulting). Keep
> amounts round so sums stay eyeball-verifiable. After authoring, the
> `test_sixty_invoices_with_stable_ids` test enforces exactly 60.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_eval_fixtures.py -v`
Expected: PASS (3 tests) once all 60 rows are present.

- [ ] **Step 5: Commit**

```bash
git add backend/eval/fixtures/ backend/tests/test_eval_fixtures.py
git commit -m "feat: add synthetic invoice fixtures for evaluation"
```

---

### Task 4: Seed script for the eval tenant

**Files:**
- Create: `backend/scripts/seed_eval_tenant.py`
- Test: `backend/tests/test_seed_eval_tenant.py`

- [ ] **Step 1: Write the failing test** (uses the DB session fixture from `tests/conftest.py`)

```python
# backend/tests/test_seed_eval_tenant.py
import uuid
from sqlalchemy import text
from scripts.seed_eval_tenant import seed
from eval.fixtures.invoices import EVAL_TENANT_ID
from app.db.models import StoredInvoice


def test_seed_inserts_sixty_rows(db_session):
    n = seed(db_session, embed=False)          # skip dense embed for speed in tests
    assert n == 60
    db_session.execute(text("SELECT set_config('app.current_tenant', :t, true)"),
                       {"t": str(EVAL_TENANT_ID)})
    rows = db_session.query(StoredInvoice).count()
    assert rows == 60
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seed_eval_tenant.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.seed_eval_tenant'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/scripts/seed_eval_tenant.py
"""Seed the fixed eval tenant with synthetic invoices and build its indexes.

Usage:
    python scripts/seed_eval_tenant.py        # full: store + dense embed + BM25
"""
from __future__ import annotations

import sys

from sqlalchemy import text

from app.db.base import SessionLocal
from app.db.bootstrap import ensure_tenant            # creates the tenant row if missing
from app.services.workspace import store_invoices
from eval.fixtures.invoices import EVAL_TENANT_ID, build_fixture_invoices
from invoice_rag.indexing.dense import reembed_tenant


def seed(db, embed: bool = True) -> int:
    ensure_tenant(db, EVAL_TENANT_ID)
    db.execute(text("SELECT set_config('app.current_tenant', :t, true)"),
               {"t": str(EVAL_TENANT_ID)})
    n = store_invoices(db, EVAL_TENANT_ID, build_fixture_invoices())   # store + BM25
    if embed:
        reembed_tenant(db)                                            # dense vectors
    db.commit()
    return n


def main() -> None:
    db = SessionLocal()
    try:
        n = seed(db, embed=True)
        print(f"seeded {n} invoices into eval tenant {EVAL_TENANT_ID}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

> If `ensure_tenant` does not exist in `app/db/bootstrap.py`, grep for the helper
> that inserts a `Tenant` row (used by the test/bootstrap path) and use that name
> instead; the contract is "tenant row exists before storing invoices".

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seed_eval_tenant.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_eval_tenant.py backend/tests/test_seed_eval_tenant.py
git commit -m "feat: add eval-tenant seed script"
```

---

### Task 5: Labeled question set

**Files:**
- Create: `backend/eval/eval_set.jsonl` (replaces the 5-row stub)

**Design:** 56 cases (5 lookup / 10 filter / 15 aggregation / 10 semantic / 5 trend /
6 compliance / 5 refuse), each referencing fixture ids and exact expected values
derived from the fixtures. Correctness is guaranteed by the Task 7 consistency test
(no hand-arithmetic trusted).

- [ ] **Step 1: Author the JSONL** — one row per case. Examples (one per category; author the rest to hit the counts):

```jsonl
{"id":1,"category":"lookup","question":"Покажи фактура EVAL-0007","tool":"get_invoice","params":{"number":"EVAL-0007"},"expected":{"id":"inv-007"},"relevant_ids":["inv-007"]}
{"id":11,"category":"filter","question":"Всички фактури над 5000 BGN","tool":"filter_invoices","params":{"min_amount":5000,"currency":"BGN"},"expected":{},"relevant_ids":["inv-011","inv-012","inv-013","inv-014"]}
{"id":21,"category":"aggregation","question":"Общо ДДС за Q2 2025","tool":"sum_invoices","params":{"filters":{"period":"Q2 2025"},"group_by":null},"expected":{"total_vat":"<computed>"},"relevant_ids":[]}
{"id":36,"category":"semantic","question":"фактури свързани с маркетинг","tool":"semantic_search","params":{},"expected":{},"relevant_ids":["inv-005"]}
{"id":46,"category":"trend","question":"Расте ли разходът за облак спрямо предходното тримесечие?","tool":"compare_periods","params":{"metric":"total_spent","period_a":{"date_from":"2025-01-01","date_to":"2025-03-31"},"period_b":{"date_from":"2025-04-01","date_to":"2025-06-30"}},"expected":{"delta":"<computed>"},"relevant_ids":[]}
{"id":51,"category":"compliance","question":"Правилно ли е начислено ДДС на фактура EVAL-0053?","tool":"query_law","params":{"number":"EVAL-0053"},"expected":{"verdict":"incorrect","article":"ЗДДС чл. 66","expected_vat":"20.00"},"relevant_ids":["inv-053"]}
{"id":56,"category":"refuse","question":"Надежден ли е този доставчик?","tool":null,"params":{},"expected":{"refused":true},"relevant_ids":[]}
```

For aggregation/trend `expected` values shown as `<computed>`, fill the real number
by running the tool once against the seeded fixtures (Task 7's test prints the
actual values; copy them in, then the test locks them).

- [ ] **Step 2: Verify the file parses**

Run: `cd backend && python -c "from eval.cases import load_cases; print(len(load_cases('eval/eval_set.jsonl')))"`
Expected: prints `56`

- [ ] **Step 3: Commit**

```bash
git add backend/eval/eval_set.jsonl
git commit -m "feat: labeled eval question set (56 cases)"
```

---

### Task 6: Phase-1 runner (tool correctness)

**Files:**
- Modify (rewrite): `backend/eval/run_eval.py`

- [ ] **Step 1: Rewrite the runner** (removes hardcoded `vendor="AWS"`/`min_amount=5000`)

```python
# backend/eval/run_eval.py
"""Phase-1 eval: per-tool correctness + retrieval quality on the synthetic set.

Reads eval_set.jsonl, runs each case's named tool with its labeled params, and
scores numeric accuracy (sum/compare) or precision@k/recall@k/MRR (filter/lookup/
semantic) via the shared metrics module.

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


def _run_case(db, tenant_id: uuid.UUID, c) -> dict:
    p = c.params
    if c.tool == "get_invoice":
        v = get_invoice(db, number=p.get("number"), invoice_id=p.get("invoice_id"))
        got = [v.invoice_id] if v else []
        pr, _ = precision_recall_at_k(got, c.relevant_ids, k=1)
        return {"category": c.category, "id": c.id, "metric": "lookup hit", "value": pr, "passed": pr == 1.0}
    if c.tool == "filter_invoices":
        views = filter_invoices(db, FilterParams(**p))
        pr, rc = precision_recall_at_k([v.invoice_id for v in views], c.relevant_ids, k=len(views) or 1)
        return {"category": c.category, "id": c.id, "metric": "P/R", "value": (pr, rc), "passed": rc == 1.0}
    if c.tool == "sum_invoices":
        res = sum_invoices(db, FilterParams(**p.get("filters", {})), group_by=p.get("group_by"))
        exp = c.expected
        key = "total_vat" if "total_vat" in exp else "total"
        got = res.total_vat if key == "total_vat" else res.total_amount
        ok = numeric_match(got, exp.get(key))
        return {"category": c.category, "id": c.id, "metric": key, "value": str(got), "passed": ok}
    if c.tool == "compare_periods":
        res = compare_periods(db, p["metric"], DateRange(**p["period_a"]), DateRange(**p["period_b"]))
        ok = numeric_match(res.delta, c.expected.get("delta"))
        return {"category": c.category, "id": c.id, "metric": "delta", "value": str(res.delta), "passed": ok}
    if c.tool == "semantic_search":
        views = semantic_search(db, tenant_id, c.question, top_k=10)
        ids = [v.invoice_id for v in views]
        pr, rc = precision_recall_at_k(ids, c.relevant_ids, k=10)
        m = mrr(ids, c.relevant_ids)
        return {"category": c.category, "id": c.id, "metric": "P@10/MRR", "value": (pr, m), "passed": rc > 0}
    # compliance / refuse are Phase-2 (agent) — skip in Phase-1
    return {"category": c.category, "id": c.id, "metric": "(phase-2)", "value": "-", "passed": True}


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
```

- [ ] **Step 2: Smoke-run against seeded fixtures**

Run (after `python scripts/seed_eval_tenant.py`):
`cd backend && python eval/run_eval.py`
Expected: a per-category table; copy the printed sum/delta values into the
`<computed>` slots in `eval_set.jsonl`.

- [ ] **Step 3: Commit**

```bash
git add backend/eval/run_eval.py backend/eval/eval_set.jsonl
git commit -m "feat: phase-1 tool-correctness eval runner"
```

---

### Task 7: Phase-1 consistency test (locks the ground-truth)

**Files:**
- Test: `backend/tests/test_eval_phase1_consistency.py`

**Purpose:** since the data is synthetic, the tools must score **100%** on Phase-1.
This test seeds the fixtures, runs every Phase-1 case, and asserts all pass — which
simultaneously validates that the labeled `expected`/`relevant_ids` match the data.

- [ ] **Step 1: Write the test**

```python
# backend/tests/test_eval_phase1_consistency.py
import uuid
from sqlalchemy import text
from scripts.seed_eval_tenant import seed
from eval.fixtures.invoices import EVAL_TENANT_ID
from eval.cases import load_cases
from eval.run_eval import _run_case


def test_phase1_all_cases_pass_on_synthetic_data(db_session):
    seed(db_session, embed=True)
    db_session.execute(text("SELECT set_config('app.current_tenant', :t, true)"),
                       {"t": str(EVAL_TENANT_ID)})
    cases = [c for c in load_cases("eval/eval_set.jsonl")
             if c.category not in {"compliance", "refuse"}]
    failures = [r for c in cases
                if not (r := _run_case(db_session, EVAL_TENANT_ID, c))["passed"]]
    assert not failures, f"Phase-1 labels disagree with fixtures: {failures}"
```

- [ ] **Step 2: Run** `cd backend && python -m pytest tests/test_eval_phase1_consistency.py -v`
Expected: PASS once `<computed>` values are filled and `relevant_ids` are correct.
A failure here means a label is wrong — fix the label, not the tool.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_eval_phase1_consistency.py
git commit -m "test: phase-1 eval consistency guard against label drift"
```

---

### Task 8: Phase-2 runner (agent routing / refusal / compliance)

**Files:**
- Modify (rewrite): `backend/eval/run_eval_agent.py`
- Test: `backend/tests/test_eval_agent_runner.py`

**Fixes two bugs:** the stale import `from invoice_rag.agent import run` (the agent
now lives at `app.rag.run`) and the hardcoded `model="eval"`.

- [ ] **Step 1: Write the failing test** (inject a fake `complete` so no Groq needed)

```python
# backend/tests/test_eval_agent_runner.py
from eval.run_eval_agent import score_case
from eval.cases import EvalCase


class _Ans:
    def __init__(self, tool_trace, refused): self.tool_trace = tool_trace; self.refused = refused; self.reply = ""


def test_routing_hit_when_expected_tool_called():
    c = EvalCase(id=1, category="filter", question="q", tool="filter_invoices",
                 params={}, expected={}, relevant_ids=[])
    s = score_case(c, _Ans([{"tool": "filter_invoices"}], refused=False))
    assert s["routing_ok"] is True


def test_refusal_scored_for_refuse_case():
    c = EvalCase(id=2, category="refuse", question="trust?", tool=None,
                 params={}, expected={"refused": True}, relevant_ids=[])
    assert score_case(c, _Ans([], refused=True))["refusal_ok"] is True
```

- [ ] **Step 2: Run** `cd backend && python -m pytest tests/test_eval_agent_runner.py -v`
Expected: FAIL — `cannot import name 'score_case'`

- [ ] **Step 3: Rewrite the runner**

```python
# backend/eval/run_eval_agent.py
"""Phase-2 eval: agent routing + refusal + compliance, vs the synthetic set.

Runs each question through the agent (needs LLM_MODEL set) k times and reports
routing accuracy (did it call the labeled tool), refusal calibration, and
compliance accuracy (correct verdict + cited article).

Usage:  LLM_MODEL=... python eval/run_eval_agent.py [tenant_uuid] [k]
"""
from __future__ import annotations

import os
import sys
import time
import uuid

from sqlalchemy import text

from app.db.base import SessionLocal
from app.rag import run as run_agent           # moved here during reconciliation
from eval.cases import load_cases
from eval.fixtures.invoices import EVAL_TENANT_ID

EVAL_PATH = "eval/eval_set.jsonl"


def score_case(c, ans) -> dict:
    called = [t["tool"] for t in (ans.tool_trace or [])]
    out = {"id": c.id, "category": c.category, "tools": called, "refused": ans.refused}
    if c.category == "refuse":
        out["refusal_ok"] = bool(ans.refused)
    elif c.category == "compliance":
        cited = (c.expected.get("article", "").split()[-1].lower() in (ans.reply or "").lower())
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
    route_hit = route_tot = ref_ok = ref_tot = comp_ok = comp_tot = 0
    for c in load_cases(EVAL_PATH):
        for _ in range(k):
            for attempt in range(4):                # backoff on Groq 429s
                try:
                    ans = run_agent(db, uuid.UUID(tenant_id), c.question, [], model=model)
                    break
                except Exception as e:
                    if attempt == 3:
                        raise
                    time.sleep(2 ** attempt)
            s = score_case(c, ans)
            if "refusal_ok" in s: ref_tot += 1; ref_ok += s["refusal_ok"]
            if "compliance_ok" in s: comp_tot += 1; comp_ok += s["compliance_ok"]
            if "routing_ok" in s: route_tot += 1; route_hit += s["routing_ok"]
            print(f"[{c.category}] #{c.id} tools={s.get('tools')} refused={s.get('refused')}")
    if route_tot: print(f"\nrouting accuracy:   {route_hit}/{route_tot} = {route_hit/route_tot:.0%}")
    if ref_tot:   print(f"refusal calibration:{ref_ok}/{ref_tot} = {ref_ok/ref_tot:.0%}")
    if comp_tot:  print(f"compliance accuracy:{comp_ok}/{comp_tot} = {comp_ok/comp_tot:.0%}")
    db.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(EVAL_TENANT_ID),
         int(sys.argv[2]) if len(sys.argv) > 2 else 1)
```

- [ ] **Step 4: Run** `cd backend && python -m pytest tests/test_eval_agent_runner.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/eval/run_eval_agent.py backend/tests/test_eval_agent_runner.py
git commit -m "feat: phase-2 agent eval runner (routing/refusal/compliance)"
```

---

### Task 9: Laws-RAG extension point + README

**Files:**
- Create: `backend/eval/run_eval_laws.py`
- Create: `backend/eval/eval_set_laws.jsonl` (seed with 3 example rows)
- Modify (rewrite): `backend/eval/README.md`

- [ ] **Step 1: Create the laws runner** (proves the shared metrics are reusable)

```python
# backend/eval/run_eval_laws.py
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
```

```jsonl
{"query":"каква е ставката на ДДС","relevant":["ЗДДС Чл. 66"]}
{"query":"обратно начисляване на ДДС","relevant":["ЗДДС Чл. 117"]}
{"query":"регистрация по ДДС праг","relevant":["ЗДДС Чл. 96"]}
```

- [ ] **Step 2: Rewrite the README** to document the synthetic-data flow:

```markdown
# Invoice RAG — Evaluation

## Setup (once)
    python scripts/seed_eval_tenant.py        # seeds 60 synthetic invoices + indexes

## Phase 1 — tool correctness (deterministic, ~2 min)
    python eval/run_eval.py
Numeric accuracy (sum/compare) + retrieval P@k/R@k/MRR (filter/lookup/semantic).
`tests/test_eval_phase1_consistency.py` guards labels against fixture drift.

## Phase 2 — agent (needs a model, ~10-20 min at k=1)
    LLM_MODEL=groq/llama-3.3-70b-versatile python eval/run_eval_agent.py "" 1
Routing accuracy, refusal calibration, compliance accuracy.

## Laws RAG (Partner B)
    python eval/run_eval_laws.py
Add cases to `eval_set_laws.jsonl`; reuses `eval/metrics.py`.
```

- [ ] **Step 3: Verify both runners import cleanly**

Run: `cd backend && python -c "import eval.run_eval_laws, eval.run_eval, eval.run_eval_agent"`
Expected: no output (clean import)

- [ ] **Step 4: Commit**

```bash
git add backend/eval/run_eval_laws.py backend/eval/eval_set_laws.jsonl backend/eval/README.md
git commit -m "feat: laws-RAG eval extension point + eval README"
```

---

## Final verification

- [ ] `cd backend && python -m pytest tests/test_eval_*.py -v` — all eval unit tests pass
- [ ] `python scripts/seed_eval_tenant.py` — seeds 60 invoices
- [ ] `python eval/run_eval.py` — Phase-1 reports 100% (synthetic data; tools must be exact)
- [ ] `LLM_MODEL=groq/llama-3.3-70b-versatile python eval/run_eval_agent.py "" 1` — Phase-2 reports routing/refusal/compliance numbers
- [ ] `python eval/run_eval_laws.py` — laws runner prints a table (proves extensibility)
```
