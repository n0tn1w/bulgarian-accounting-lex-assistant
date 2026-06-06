"""Scraper for НАП (nra.bg) law pages and становища (guidance opinions).

nra.bg serves consolidated law texts and interpretive opinions. The fetch logic
is identical to the base; the per-site class exists so site-specific quirks
(encoding, redirects, portal wrappers) can be handled in one place later.
"""
from __future__ import annotations

from typing import List

from ..models import SourceDoc
from .base import BaseScraper


class NapScraper(BaseScraper):
    site_name = "nra.bg"

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
