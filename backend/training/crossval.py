"""Honest, held-out evaluation of the learned field selectors via document-level k-fold
cross-validation: for each fold, train the selectors on the other folds and run the full
extractor on the held-out documents. Reports per-field accuracy held-out, next to the
deterministic regex baseline, so we see whether each learned field actually generalizes.

    cd backend && python -m training.crossval --data <DIR> [<DIR> ...] [--folds 5]
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def _blank_report():
    from training.evaluate import Report, Tally

    r = Report()
    r.fields = {}
    r.supplier, r.recipient, r.pair_undirected = Tally(), Tally(), Tally()
    return r


def _accumulate(agg, rep) -> None:
    from training.evaluate import Tally

    agg.n += rep.n
    agg.doc_type_correct += rep.doc_type_correct
    for k, t in rep.fields.items():
        a = agg.fields.setdefault(k, Tally())
        a.matched += t.matched; a.applicable += t.applicable
    for name in ("supplier", "recipient", "pair_undirected"):
        a, t = getattr(agg, name), getattr(rep, name)
        a.matched += t.matched; a.applicable += t.applicable
    agg.swaps += rep.swaps


def main() -> None:
    ap = argparse.ArgumentParser(description="K-fold cross-validation of the field selectors.")
    ap.add_argument("--data", type=Path, nargs="+", default=None)
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()

    # Isolate the field selectors: regex + selectors only (no classifier / LLM / lookup).
    os.environ["FIELD_MODELS_ENABLED"] = "true"
    os.environ["DOCTYPE_CLASSIFIER_ENABLED"] = "false"
    os.environ["LLM_ASSIST_ENABLED"] = "false"
    os.environ["OCR_VISION_FALLBACK"] = "false"
    os.environ["COMPANY_LOOKUP_ENABLED"] = "false"
    from app.core import get_settings
    get_settings.cache_clear()

    from sklearn.model_selection import KFold

    from app.tools.ingest import classifier, field_models as FM
    from training.dataset import data_root, load_dataset
    from training.evaluate import _print, evaluate
    from training.train_extractors import build_rows

    dirs = args.data or [data_root()]
    examples = [ex for d in dirs for ex in load_dataset(d)]
    if len(examples) < args.folds:
        print(f"Need at least {args.folds} labeled docs; have {len(examples)}."); return
    print(f"{len(examples)} docs, {args.folds}-fold CV\n")

    # baseline: regex only (selectors off)
    FM.set_models({})
    baseline = evaluate(examples)

    # held-out: train selectors per fold, evaluate the held-out fold
    agg = _blank_report()
    kf = KFold(n_splits=args.folds, shuffle=True, random_state=0)
    idx = list(range(len(examples)))
    for fold, (tr, te) in enumerate(kf.split(idx), 1):
        rows, labels = build_rows([examples[i] for i in tr])
        bundle = {}
        for group in ("amounts", "party", "number", "date"):
            if len(set(labels[group])) >= 2:
                m = FM.build_selector(); m.fit(rows[group], labels[group]); bundle[group] = m
        if len(set(labels["direction"])) >= 2:
            m = classifier.build_model(); m.fit(rows["direction"], labels["direction"]); bundle["direction"] = m
        FM.set_models(bundle)
        _accumulate(agg, evaluate([examples[i] for i in te]))
        print(f"  fold {fold}: trained {sorted(bundle)} on {len(tr)} docs, evaluated {len(te)}")
    FM.reset()

    print("\n=== REGEX BASELINE (selectors off) ===")
    _print(baseline)
    print("\n=== HELD-OUT (k-fold, selectors trained on other folds) ===")
    _print(agg)


if __name__ == "__main__":
    main()
