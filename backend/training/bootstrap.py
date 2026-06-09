"""Bootstrap ground-truth labels from structured exports (Controlisy / VAT-ledger XML).

The structured export is reliable truth; the matching PDF is the OCR input. This writes a
`<stem>.label.json` next to each PDF whose invoice number matches an exported document, so
the eval can measure the OCR pipeline against real numbers — no hand-labeling.

    cd backend && python -m training.bootstrap --xml <XML_DIR> --pdf <PDF_DIR>

Labels are written next to the PDFs (outside the repo); nothing is committed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from training.dataset import LabeledFields, LabeledParty


def _invoices_from_dir(xml_dir: Path) -> dict[str, object]:
    """Parse every XML under xml_dir into invoices, keyed by document number."""
    from app.tools.ingest import invoices_from_xml_content

    by_number: dict[str, object] = {}
    for path in sorted(xml_dir.rglob("*.xml")):
        try:
            invoices = invoices_from_xml_content(path.read_text(encoding="utf-8", errors="replace"), path.stem)
        except Exception:
            continue
        for inv in invoices:
            if inv.number:
                by_number[str(inv.number)] = inv
    return by_number


def _match(stem: str, by_number: dict[str, object]) -> object | None:
    """A PDF named '2484' matches export number '5000002484' (filename is the suffix)."""
    if stem in by_number:
        return by_number[stem]
    digits = stem.lstrip("0") or stem
    cands = [inv for num, inv in by_number.items() if num.endswith(digits) and num[: -len(digits) or None].strip("0") == ""]
    if len(cands) == 1:
        return cands[0]
    # looser: unique number that simply ends with the stem
    cands = [inv for num, inv in by_number.items() if num.endswith(digits)]
    return cands[0] if len(cands) == 1 else None


def _label_from_invoice(inv) -> LabeledFields:
    def party(p) -> LabeledParty:
        return LabeledParty(name=p.name, vat_number=p.vat_number, eik=p.eik)

    def s(v) -> str | None:
        return None if v is None else str(v)

    return LabeledFields(
        doc_type=inv.doc_type or "invoice",
        direction=inv.direction,
        number=inv.number, date=inv.date, currency=inv.currency,
        supplier=party(inv.supplier), recipient=party(inv.recipient),
        net_amount=s(inv.net_amount), vat_amount=s(inv.vat_amount), total_amount=s(inv.total_amount),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Bootstrap labels from XML exports for matching PDFs.")
    ap.add_argument("--xml", type=Path, required=True, help="directory of structured XML exports")
    ap.add_argument("--pdf", type=Path, required=True, help="directory of PDF documents to label")
    ap.add_argument("--overwrite", action="store_true", help="replace existing label files")
    args = ap.parse_args()

    by_number = _invoices_from_dir(args.xml)
    print(f"Parsed {len(by_number)} exported documents from {args.xml}")

    written = skipped = unmatched = 0
    for pdf in sorted(args.pdf.glob("*.pdf")):
        label_path = pdf.with_name(pdf.stem + ".label.json")
        if label_path.exists() and not args.overwrite:
            skipped += 1
            continue
        inv = _match(pdf.stem, by_number)
        if inv is None:
            unmatched += 1
            continue
        label = _label_from_invoice(inv)
        label_path.write_text(
            json.dumps(label.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        written += 1

    print(f"Wrote {written} labels, skipped {skipped} existing, {unmatched} PDFs had no match.")
    print(f"Now run:  python -m training.evaluate --data \"{args.pdf}\"")


if __name__ == "__main__":
    main()
