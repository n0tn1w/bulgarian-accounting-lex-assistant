"""Labeled-document dataset: pair each source file with its ground-truth label, and
provide the document's text (cached, so OCR runs once per file).

Layout under PREPROCESSING_DATA_DIR (gitignored):
    <any>/45.pdf            source (pdf | txt | csv | png | jpg)
    <any>/45.label.json     ground truth (same stem)
    .cache/<sha1>.txt       cached extracted text
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from app.core import get_settings

_SOURCE_EXTS = {".pdf", ".txt", ".csv", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


class LabeledParty(BaseModel):
    name: Optional[str] = None
    vat_number: Optional[str] = None
    eik: Optional[str] = None


class LabeledFields(BaseModel):
    """Ground truth for one document. Only doc_type is required."""

    doc_type: str
    direction: Optional[str] = None  # sale | purchase | unknown
    number: Optional[str] = None
    date: Optional[str] = None
    currency: Optional[str] = None
    supplier: LabeledParty = Field(default_factory=LabeledParty)
    recipient: LabeledParty = Field(default_factory=LabeledParty)
    net_amount: Optional[str] = None
    vat_amount: Optional[str] = None
    total_amount: Optional[str] = None
    extra: dict[str, str] = Field(default_factory=dict)


@dataclass
class Example:
    path: Path
    label: LabeledFields

    @property
    def doc_id(self) -> str:
        return self.path.stem

    def text(self, data_dir: Path | None = None) -> str:
        return document_text(self.path, data_dir or data_root())


def data_root() -> Path:
    return Path(get_settings().preprocessing_data_dir)


def load_dataset(data_dir: Path | None = None) -> list[Example]:
    """Load every source file that has a sibling <stem>.label.json."""
    root = data_dir or data_root()
    examples: list[Example] = []
    if not root.exists():
        return examples
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in _SOURCE_EXTS or ".cache" in path.parts:
            continue
        label_path = path.with_suffix(path.suffix + ".label.json")
        if not label_path.exists():
            label_path = path.with_name(path.stem + ".label.json")
        if not label_path.exists():
            continue
        try:
            label = LabeledFields.model_validate_json(label_path.read_text(encoding="utf-8"))
        except Exception:  # malformed label -> skip, don't crash the run
            continue
        examples.append(Example(path=path, label=label))
    return examples


def document_text(path: Path, data_dir: Path | None = None) -> str:
    """Extracted text for a source file, cached by content hash so OCR runs once."""
    root = data_dir or data_root()
    cache_dir = root / ".cache"
    digest = hashlib.sha1(path.read_bytes()).hexdigest()
    cached = cache_dir / f"{digest}.txt"
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    text = _raw_text(path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached.write_text(text, encoding="utf-8")
    return text


def _raw_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        from app.tools.ingest.ocr import extract_ocr_from_pdf_bytes

        return extract_ocr_from_pdf_bytes(path.read_bytes()).text
    if ext in (".txt", ".csv"):
        return path.read_text(encoding="utf-8", errors="replace")
    if ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
        from app.tools.ingest.ocr import extract_ocr_from_image_bytes

        return extract_ocr_from_image_bytes(path.read_bytes()).text
    raise ValueError(f"unsupported source file type: {ext}")


def label_template(doc_id: str = "") -> str:
    """A blank label.json to hand-fill for a new example."""
    return json.dumps(
        LabeledFields(doc_type="invoice").model_dump(), ensure_ascii=False, indent=2
    )
