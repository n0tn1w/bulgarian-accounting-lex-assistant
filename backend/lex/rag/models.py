"""Core data structures passed between pipeline stages.

These are deliberately plain dataclasses (no ORM, no pydantic) to keep the MVP
dependency-light and the data flow obvious.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class SourceDoc:
    """A single raw legal document fetched from a source site."""
    law_abbr: str            # e.g. "ЗДДС"
    law_name: str            # full title
    source_site: str         # e.g. "lex.bg"
    url: str
    html: str                # raw HTML as fetched
    version_date: Optional[str] = None   # ДВ revision date if discoverable


@dataclass
class Citation:
    """Precise pointer back to the primary source for a chunk."""
    law_abbr: str
    law_name: str
    source_site: str
    url: str
    article: Optional[str] = None     # "Чл. 96"
    paragraph: Optional[str] = None   # "ал. 1"
    point: Optional[str] = None       # "т. 2"
    version_date: Optional[str] = None

    def label(self) -> str:
        """Human-readable citation, e.g. 'ЗДДС, Чл. 96, ал. 1, т. 2'."""
        parts = [self.law_abbr]
        for p in (self.article, self.paragraph, self.point):
            if p:
                parts.append(p)
        return ", ".join(parts)


@dataclass
class Chunk:
    """An indexed unit of legal text (ideally one алинея) with its citation."""
    id: str
    text: str
    citation: Citation

    def to_record(self) -> dict:
        rec = {"id": self.id, "text": self.text}
        rec.update({f"cit_{k}": v for k, v in asdict(self.citation).items()})
        return rec

    @classmethod
    def from_record(cls, rec: dict) -> "Chunk":
        cit = Citation(
            law_abbr=rec.get("cit_law_abbr", ""),
            law_name=rec.get("cit_law_name", ""),
            source_site=rec.get("cit_source_site", ""),
            url=rec.get("cit_url", ""),
            article=rec.get("cit_article"),
            paragraph=rec.get("cit_paragraph"),
            point=rec.get("cit_point"),
            version_date=rec.get("cit_version_date"),
        )
        return cls(id=rec["id"], text=rec["text"], citation=cit)


@dataclass
class RetrievedChunk:
    """A chunk returned by retrieval, annotated with scoring provenance."""
    chunk: Chunk
    dense_rank: Optional[int] = None
    bm25_rank: Optional[int] = None
    fused_score: float = 0.0
    rerank_score: Optional[float] = None
