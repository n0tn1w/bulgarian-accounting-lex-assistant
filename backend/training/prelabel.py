"""Pre-label a folder of documents into a training-ready dataset.

Runs the DETERMINISTIC extractor (learned models / LLM / register lookup all OFF) over
each file and writes a `<stem>.label.json` keeping only the fields it is CONFIDENT about
(silver labels) — uncertain fields are left null. This bootstraps a labeled set for a
folder with no matching exports; the labels are plain JSON, meant to be reviewed/corrected
before they're trusted as ground truth.

    cd backend && python -m training.prelabel --data <DIR> [--min-conf 0.7] [--overwrite]
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from training.dataset import _SOURCE_EXTS, document_text


def main() -> None:
    ap = argparse.ArgumentParser(description="Auto-pre-label a folder (silver labels).")
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--min-conf", type=float, default=0.7)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    # Deterministic only: no learned models, no LLM, no register lookup.
    for var in ("FIELD_MODELS_ENABLED", "DOCTYPE_CLASSIFIER_ENABLED",
                "LLM_ASSIST_ENABLED", "OCR_VISION_FALLBACK", "COMPANY_LOOKUP_ENABLED"):
        os.environ[var] = "false"
    from app.core import get_settings
    get_settings.cache_clear()
    from app.tools.ingest import extract_document

    written = skipped = failed = 0
    for path in sorted(args.data.rglob("*")):
        if path.suffix.lower() not in _SOURCE_EXTS or ".cache" in path.parts:
            continue
        label_path = path.with_name(path.stem + ".label.json")
        if label_path.exists() and not args.overwrite:
            skipped += 1
            continue
        try:
            inv = extract_document(document_text(path, args.data), path.stem, source="ocr")
        except Exception as exc:
            print(f"  skip {path.name}: {exc}")
            failed += 1
            continue

        fc = inv.field_confidence
        keep = lambda k, v: v if (v is not None and fc.get(k, 0.0) >= args.min_conf) else None

        def party(prefix, p) -> dict:
            return {
                "name": keep(f"{prefix}_name", p.name),
                "vat_number": p.vat_number if fc.get(f"{prefix}_vat", 0.0) >= args.min_conf else None,
                "eik": p.eik if fc.get(f"{prefix}_eik", 0.0) >= args.min_conf else None,
            }

        def amt(k, v) -> str | None:
            return str(v) if (v is not None and fc.get(k, 0.0) >= args.min_conf) else None

        label = {
            "doc_type": inv.doc_type,
            "direction": inv.direction if inv.direction != "unknown" else None,
            "number": keep("number", inv.number),
            "date": keep("date", inv.date),
            "currency": inv.currency,
            "supplier": party("supplier", inv.supplier),
            "recipient": party("recipient", inv.recipient),
            "net_amount": amt("net_amount", inv.net_amount),
            "vat_amount": amt("vat_amount", inv.vat_amount),
            "total_amount": amt("total_amount", inv.total_amount),
            "extra": inv.extra,
        }
        label_path.write_text(json.dumps(label, ensure_ascii=False, indent=2), encoding="utf-8")
        written += 1

    print(f"Pre-labeled {written}, skipped {skipped} existing, {failed} failed, under {args.data}")
    print("Review/correct the *.label.json, then: python -m training.train_extractors --data <dir>")


if __name__ == "__main__":
    main()
