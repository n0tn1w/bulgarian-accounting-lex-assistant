"""Measure the preprocessing pipeline against a labeled dataset.

    cd backend && python -m training.evaluate [--data DIR] [--no-classifier] [--no-llm]

Reports per-field exact-match accuracy, the supplier/recipient swap rate (directed vs
undirected party match), and a doc-type confusion matrix. This is the regression gate:
run it before and after any change to prove a real improvement and no amount regression.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from training.dataset import Example, LabeledParty, data_root, load_dataset


@dataclass
class Tally:
    matched: int = 0
    applicable: int = 0

    def add(self, ok: bool, applicable: bool = True) -> None:
        if applicable:
            self.applicable += 1
            self.matched += int(ok)

    def pct(self) -> float:
        return 100.0 * self.matched / self.applicable if self.applicable else 0.0


@dataclass
class Report:
    n: int = 0
    fields: dict[str, Tally] = field(default_factory=lambda: Counter())  # type: ignore
    doc_type_correct: int = 0
    confusion: Counter = field(default_factory=Counter)
    supplier: Tally = field(default_factory=Tally)
    recipient: Tally = field(default_factory=Tally)
    pair_undirected: Tally = field(default_factory=Tally)
    swaps: int = 0
    misses: list[str] = field(default_factory=list)


def _amount_eq(label: str | None, value) -> bool:
    if label is None:
        return True  # not labelled -> not scored elsewhere
    try:
        return value is not None and Decimal(str(value)) == Decimal(str(label))
    except (InvalidOperation, TypeError):
        return False


def _identity_keys(p: LabeledParty | object) -> set[str]:
    keys: set[str] = set()
    vat = getattr(p, "vat_number", None)
    eik = getattr(p, "eik", None)
    name = getattr(p, "name", None)
    if vat:
        keys.add("v:" + re.sub(r"\s", "", vat).upper())
    if eik:
        keys.add("e:" + re.sub(r"\D", "", eik))
    if name:
        from app.tools.ingest.company import normalize_company_name

        n = normalize_company_name(name)
        if n:
            keys.add("n:" + n)
    return keys


def _match(pred, label: LabeledParty) -> bool:
    lk = _identity_keys(label)
    return bool(lk) and bool(_identity_keys(pred) & lk)


def evaluate(examples: list[Example]) -> Report:
    from app.tools.ingest import extract_document

    rep = Report(n=len(examples))
    fields: dict[str, Tally] = {k: Tally() for k in
                               ("number", "date", "currency", "net_amount", "vat_amount", "total_amount")}
    for ex in examples:
        label = ex.label
        try:
            inv = extract_document(ex.text(), ex.doc_id, source="ocr")
        except Exception as exc:  # a single bad file shouldn't abort the run
            rep.misses.append(f"{ex.doc_id}: extract error: {exc}")
            continue

        rep.confusion[(label.doc_type, inv.doc_type)] += 1
        if inv.doc_type == label.doc_type:
            rep.doc_type_correct += 1
        else:
            rep.misses.append(f"{ex.doc_id}: doc_type {inv.doc_type} != {label.doc_type}")

        fields["number"].add(inv.number == label.number, label.number is not None)
        fields["date"].add(inv.date == label.date, label.date is not None)
        fields["currency"].add(inv.currency == label.currency, label.currency is not None)
        for key in ("net_amount", "vat_amount", "total_amount"):
            lv = getattr(label, key)
            fields[key].add(_amount_eq(lv, getattr(inv, key)), lv is not None)

        # parties: directed (right slot) vs undirected (right pair, any slot)
        sup_ok = _match(inv.supplier, label.supplier)
        rec_ok = _match(inv.recipient, label.recipient)
        rep.supplier.add(sup_ok, bool(_identity_keys(label.supplier)))
        rep.recipient.add(rec_ok, bool(_identity_keys(label.recipient)))
        if _identity_keys(label.supplier) and _identity_keys(label.recipient):
            directed = sup_ok and rec_ok
            undirected = _match(inv.supplier, label.recipient) and _match(inv.recipient, label.supplier)
            rep.pair_undirected.add(directed or undirected)
            if undirected and not directed:
                rep.swaps += 1
                rep.misses.append(f"{ex.doc_id}: supplier/recipient SWAPPED")

    rep.fields = fields  # type: ignore
    return rep


def _print(rep: Report) -> None:
    print(f"\nEvaluated {rep.n} documents\n" + "-" * 48)
    print(f"  doc_type accuracy   {100.0 * rep.doc_type_correct / rep.n if rep.n else 0:6.1f}%  "
          f"({rep.doc_type_correct}/{rep.n})")
    for name, t in rep.fields.items():  # type: ignore
        print(f"  {name:<18} {t.pct():6.1f}%  ({t.matched}/{t.applicable})")
    print(f"  supplier (directed) {rep.supplier.pct():6.1f}%  ({rep.supplier.matched}/{rep.supplier.applicable})")
    print(f"  recipient(directed) {rep.recipient.pct():6.1f}%  ({rep.recipient.matched}/{rep.recipient.applicable})")
    print(f"  party pair (undir.) {rep.pair_undirected.pct():6.1f}%  "
          f"({rep.pair_undirected.matched}/{rep.pair_undirected.applicable})  swaps={rep.swaps}")
    wrong = {k: v for k, v in rep.confusion.items() if k[0] != k[1]}
    if wrong:
        print("\n  doc_type confusion (true -> predicted):")
        for (true, pred), c in sorted(wrong.items(), key=lambda kv: -kv[1]):
            print(f"    {true:<22} -> {pred:<22} x{c}")
    if rep.misses:
        print(f"\n  misses ({len(rep.misses)}):")
        for m in rep.misses[:40]:
            print("    -", m)


def _report_dict(rep: Report) -> dict:
    return {
        "documents": rep.n,
        "doc_type_accuracy": round(100.0 * rep.doc_type_correct / rep.n, 2) if rep.n else 0,
        "fields": {k: {"pct": round(v.pct(), 2), "matched": v.matched, "applicable": v.applicable}
                   for k, v in rep.fields.items()},  # type: ignore
        "supplier_directed_pct": round(rep.supplier.pct(), 2),
        "recipient_directed_pct": round(rep.recipient.pct(), 2),
        "party_pair_undirected_pct": round(rep.pair_undirected.pct(), 2),
        "swaps": rep.swaps,
        "confusion": {f"{t}->{p}": c for (t, p), c in rep.confusion.items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate preprocessing on a labeled dataset.")
    ap.add_argument("--data", type=Path, default=None)
    ap.add_argument("--no-classifier", action="store_true", help="disable the doc-type classifier")
    ap.add_argument("--no-fieldmodels", action="store_true", help="disable the learned field selectors")
    ap.add_argument("--no-llm", action="store_true", help="disable the LLM field assist")
    args = ap.parse_args()

    if args.no_classifier:
        os.environ["DOCTYPE_CLASSIFIER_ENABLED"] = "false"
    if args.no_fieldmodels:
        os.environ["FIELD_MODELS_ENABLED"] = "false"
    if args.no_llm:
        os.environ["LLM_ASSIST_ENABLED"] = "false"
        os.environ["OCR_VISION_FALLBACK"] = "false"
    from app.core import get_settings
    get_settings.cache_clear()

    root = args.data or data_root()
    examples = load_dataset(root)
    if not examples:
        print(f"No labeled examples found under {root}. "
              f"Add <file> + <file>.label.json pairs (see training/dataset.label_template).")
        return
    rep = evaluate(examples)
    _print(rep)

    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    out = reports / "latest.json"
    out.write_text(json.dumps(_report_dict(rep), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport written to {out}")


if __name__ == "__main__":
    main()
