"""Train the assist-only document-type classifier on the labeled dataset.

    cd backend && python -m training.train_doctype [--data DIR] [--out PATH]

Writes a gitignored joblib model that the pipeline loads to break `other` ties only.
Run training/evaluate.py before and after to see the lift.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from training.dataset import data_root, load_dataset


def main() -> None:
    ap = argparse.ArgumentParser(description="Train the doc-type classifier.")
    ap.add_argument("--data", type=Path, nargs="+", default=None, help="one or more dataset dirs")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    from app.core import get_settings
    from app.tools.ingest import classifier

    dirs = args.data or [data_root()]
    examples = [ex for d in dirs for ex in load_dataset(d)]
    texts = [ex.text() for ex in examples]
    labels = [ex.label.doc_type for ex in examples]
    counts = Counter(labels)
    if len(counts) < 2:
        print(f"Need >=2 document types to train; found {dict(counts)}. Add more labeled files.")
        return
    print(f"Training on {len(texts)} documents, {len(counts)} types: {dict(counts)}")

    # Cross-validated accuracy when every class has enough samples.
    k = min(5, min(counts.values()))
    if k >= 2:
        try:
            from sklearn.model_selection import cross_val_score

            scores = cross_val_score(classifier.build_model(), texts, labels, cv=k)
            print(f"{k}-fold CV accuracy: {scores.mean() * 100:.1f}% (+/- {scores.std() * 100:.1f})")
        except Exception as exc:  # pragma: no cover
            print("cross-val skipped:", exc)
    else:
        print("cross-val skipped: a class has <2 samples")

    model = classifier.train(texts, labels)
    out = args.out or Path(get_settings().doctype_model_path)
    classifier.save(model, out)
    classifier.reset()
    print(f"Saved model -> {out}")


if __name__ == "__main__":
    main()
