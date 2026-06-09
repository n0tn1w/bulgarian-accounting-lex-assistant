"""Train the field selectors (amounts / parties / number / date / direction) from the
labeled dataset by auto-labeling deterministic candidates against the ground truth.

    cd backend && python -m training.train_extractors [--data DIR]

Each candidate's *value* is verbatim; we only learn which candidate is which. Writes
gitignored joblib models; run training/evaluate.py before/after to see the per-field lift.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

from training.dataset import LabeledParty, data_root, load_dataset


def _amount(label: str | None):
    if label is None:
        return None
    try:
        return Decimal(str(label))
    except (InvalidOperation, TypeError):
        return None


def _identity_keys(p: LabeledParty) -> set[str]:
    keys: set[str] = set()
    if p.vat_number:
        keys.add("v:" + re.sub(r"\s", "", p.vat_number).upper())
    if p.eik:
        keys.add("e:" + re.sub(r"\D", "", p.eik))
    if p.name:
        from app.tools.ingest.company import normalize_company_name

        n = normalize_company_name(p.name)
        if n:
            keys.add("n:" + n)
    return keys


def _cand_party_keys(name, eik, vat) -> set[str]:
    keys: set[str] = set()
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


def build_rows(examples) -> tuple[dict, dict]:
    """Auto-label every candidate against the ground truth, grouped by field. Returns
    (rows, labels) dicts keyed by group. Reused by training and cross-validation."""
    from app.tools.ingest import candidates as C

    rows = {"amounts": [], "party": [], "number": [], "date": [], "direction": []}
    labels = {k: [] for k in rows}
    for ex in examples:
        text = ex.text()
        lab = ex.label

        targets = {"net": _amount(lab.net_amount), "vat": _amount(lab.vat_amount), "total": _amount(lab.total_amount)}
        for c in C.amount_candidates(text):
            cls = "none"
            for name, tv in targets.items():
                if tv is not None and c.value == tv:
                    cls = name
                    break
            rows["amounts"].append(c.features()); labels["amounts"].append(cls)

        sup_keys, rec_keys = _identity_keys(lab.supplier), _identity_keys(lab.recipient)
        for c in C.party_candidates(text):
            ck = _cand_party_keys(c.name, c.eik, c.vat)
            cls = "supplier" if (sup_keys and ck & sup_keys) else "recipient" if (rec_keys and ck & rec_keys) else "none"
            rows["party"].append(c.features()); labels["party"].append(cls)

        for c in C.number_candidates(text, set()):
            rows["number"].append(c.features()); labels["number"].append("yes" if c.value == lab.number else "no")
        for c in C.date_candidates(text):
            rows["date"].append(c.features()); labels["date"].append("yes" if c.value == lab.date else "no")

        if lab.direction:
            rows["direction"].append(text); labels["direction"].append(lab.direction)
    return rows, labels


def main() -> None:
    ap = argparse.ArgumentParser(description="Train the field selectors.")
    ap.add_argument("--data", type=Path, nargs="+", default=None, help="one or more dataset dirs")
    args = ap.parse_args()

    from app.tools.ingest import field_models as FM

    dirs = args.data or [data_root()]
    examples = [ex for d in dirs for ex in load_dataset(d)]
    if not examples:
        print("No labeled examples found."); return
    print(f"Loaded {len(examples)} labeled documents from {len(dirs)} dir(s)")

    rows, labels = build_rows(examples)

    for group in ("amounts", "party", "number", "date"):
        ls = labels[group]
        if len(set(ls)) < 2:
            print(f"[{group}] skipped: only classes {set(ls)} ({len(ls)} candidates)")
            continue
        model = FM.build_selector()
        model.fit(rows[group], ls)
        FM.save_selector(model, group)
        print(f"[{group}] trained on {len(ls)} candidates, classes {dict(Counter(ls))} -> saved")

    # direction uses the text classifier shape
    dl = labels["direction"]
    if len(set(dl)) >= 2:
        from app.tools.ingest import classifier

        model = classifier.build_model()
        model.fit(rows["direction"], dl)
        FM.save_selector(model, "direction")
        print(f"[direction] trained on {len(dl)} docs, classes {dict(Counter(dl))} -> saved")
    else:
        print(f"[direction] skipped: classes {set(dl)}")

    FM.reset()
    from app.core import get_settings
    print("Field selectors saved to", get_settings().field_models_dir)


if __name__ == "__main__":
    main()
