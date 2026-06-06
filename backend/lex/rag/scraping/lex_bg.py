"""Scraper for lex.bg consolidated law pages (URL pattern /bg/laws/ldoc/<id>)."""
from __future__ import annotations

from typing import List

from ..models import SourceDoc
from .base import BaseScraper


class LexBgScraper(BaseScraper):
    site_name = "lex.bg"

    def scrape(self, spec) -> List[SourceDoc]:
        html = self.fetch(spec.url)
        return [
            SourceDoc(
                law_abbr=spec.law_abbr,
                law_name=spec.law_name,
                source_site=self.site_name,
                url=spec.url,
                html=html,
            )
        ]
