"""Split clean law text into citeable chunks (one per алинея where possible).

Bulgarian statutes are structured as:

    Чл. 96. (1) Всяко данъчно задължено лице ... текст на алинея 1.
    (2) ... текст на алинея 2.
    Чл. 97. ...

We segment by ``Чл. N`` (article) and ``(N)`` (алинея), producing one Chunk per
алинея with a precise Citation. Articles without алинеи become a single chunk.
Over-long алинеи are sentence-windowed with overlap so embeddings stay focused
while every sub-chunk keeps the same citation.
"""
from __future__ import annotations

import hashlib
import re
from typing import Iterator, List, Optional

from config import settings
from ..models import Chunk, Citation, SourceDoc

# "Чл. 96." / "Чл. 96а." / "Чл.96." at start of a line
_ARTICLE_RE = re.compile(r"^Чл\.\s*(\d+[а-я]?)\.?", re.IGNORECASE)
# "(1)" / "(12)" alinea marker at start of a line
_ALINEA_RE = re.compile(r"^\((\d+)\)\s*")
# sentence boundary (period/!/? followed by space + capital-ish Cyrillic)
_SENT_RE = re.compile(r"(?<=[\.!?])\s+(?=[А-ЯA-Z0-9])")


class ArticleChunker:
    def chunk_document(self, doc: SourceDoc, clean_text: str) -> List[Chunk]:
        chunks: List[Chunk] = []
        for art_no, art_text in self._iter_articles(clean_text):
            for paragraph, body in self._iter_alineas(art_text):
                for piece in self._split_long(body):
                    if len(piece) < settings.min_chunk_chars:
                        continue
                    cit = Citation(
                        law_abbr=doc.law_abbr,
                        law_name=doc.law_name,
                        source_site=doc.source_site,
                        url=doc.url,
                        article=f"Чл. {art_no}" if art_no else None,
                        paragraph=f"ал. {paragraph}" if paragraph else None,
                        version_date=doc.version_date,
                    )
                    text = self._with_header(cit, piece)
                    chunks.append(Chunk(id=self._mk_id(text, cit), text=text, citation=cit))
        return chunks

    # -- segmentation -------------------------------------------------------
    def _iter_articles(self, text: str) -> Iterator[tuple[Optional[str], str]]:
        """Yield (article_number, article_body). Skips preamble before Чл. 1."""
        lines = text.split("\n")
        current_no: Optional[str] = None
        buf: List[str] = []
        for line in lines:
            m = _ARTICLE_RE.match(line)
            if m:
                if current_no is not None and buf:
                    yield current_no, "\n".join(buf).strip()
                current_no = m.group(1)
                buf = [line[m.end():].strip()]
            elif current_no is not None:
                buf.append(line)
        if current_no is not None and buf:
            yield current_no, "\n".join(buf).strip()

    def _iter_alineas(self, art_text: str) -> Iterator[tuple[Optional[str], str]]:
        """Yield (alinea_number_or_None, body) for an article body."""
        lines = art_text.split("\n")
        current_no: Optional[str] = None
        buf: List[str] = []
        any_alinea = False
        for line in lines:
            m = _ALINEA_RE.match(line)
            if m:
                any_alinea = True
                if buf:
                    yield current_no, "\n".join(buf).strip()
                current_no = m.group(1)
                buf = [line[m.end():].strip()]
            else:
                buf.append(line)
        tail = "\n".join(buf).strip()
        if tail:
            yield (current_no if any_alinea else None), tail

    def _split_long(self, body: str) -> List[str]:
        body = body.strip()
        if len(body) <= settings.max_chunk_chars:
            return [body] if body else []
        sentences = _SENT_RE.split(body)
        pieces: List[str] = []
        cur = ""
        for s in sentences:
            if len(cur) + len(s) + 1 > settings.max_chunk_chars and cur:
                pieces.append(cur.strip())
                # overlap tail of previous piece for context continuity
                cur = cur[-settings.chunk_overlap_chars:] + " " + s
            else:
                cur = (cur + " " + s) if cur else s
        if cur.strip():
            pieces.append(cur.strip())
        return pieces

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _with_header(cit: Citation, body: str) -> str:
        """Prefix the citation label so each chunk is self-describing for search."""
        return f"[{cit.label()}] {body}"

    @staticmethod
    def _mk_id(text: str, cit: Citation) -> str:
        h = hashlib.sha1((cit.url + "|" + text).encode("utf-8")).hexdigest()[:20]
        return f"{cit.law_abbr}_{h}"
