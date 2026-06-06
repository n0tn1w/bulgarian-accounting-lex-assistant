"""Registry of target legal documents and the scraper that handles each site.

Each law lists *candidate* URLs (primary + fallbacks across sites). Ingestion
tries them in order and keeps the first that yields usable text, so a single
blocked or moved page doesn't sink the whole corpus.

NOTE: lex.bg ``ldoc`` IDs and НАП portal URLs change over time and should be
verified. They are easy to update here without touching any other code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from .base import BaseScraper
from .lex_bg import LexBgScraper
from .nap import NapScraper

# site name -> scraper class
_SCRAPERS = {
    LexBgScraper.site_name: LexBgScraper,
    NapScraper.site_name: NapScraper,
}


@dataclass
class SourceSpec:
    law_abbr: str
    law_name: str
    # ordered candidates: (site_name, url)
    candidates: List[Tuple[str, str]] = field(default_factory=list)
    # convenience accessors used by scrapers (set per-candidate during ingest)
    url: str = ""

    def for_candidate(self, site: str, url: str) -> "SourceSpec":
        return SourceSpec(self.law_abbr, self.law_name, self.candidates, url=url)


def get_scraper_for(site: str) -> BaseScraper:
    if site not in _SCRAPERS:
        raise KeyError(f"No scraper registered for site '{site}'")
    return _SCRAPERS[site]()


# --- the four core laws + room for НАП становища ---------------------------
TARGET_SOURCES: List[SourceSpec] = [
    SourceSpec(
        law_abbr="ЗДДС",
        law_name="Закон за данък върху добавената стойност",
        candidates=[
            ("lex.bg", "https://lex.bg/laws/ldoc/2135533201"),
            ("nra.bg", "https://nra.bg/wps/portal/nra/zakonodatelstvo/zakonodatelstvo_priority/11e9f37c-163e-4951-a43b-6018591e6fa7"),
        ],
    ),
    SourceSpec(
        law_abbr="ЗКПО",
        law_name="Закон за корпоративното подоходно облагане",
        candidates=[
            ("lex.bg", "https://lex.bg/laws/ldoc/2135540562"),
            ("nra.bg", "https://nra.bg/wps/portal/nra/zakonodatelstvo/zakonodatelstvo_priority/f29dc4c4-a8ec-4ba0-86ba-a35ea75f2e51"),
        ],
    ),
    SourceSpec(
        law_abbr="ЗДДФЛ",
        law_name="Закон за данъците върху доходите на физическите лица",
        candidates=[
            ("lex.bg", "https://lex.bg/laws/ldoc/2135538631"),
            ("nra.bg", "https://nra.bg/wps/portal/nra/zakonodatelstvo/zakonodatelstvo_priority/da0cc1aa-c4b2-4863-b1de-5f2f94d9f2d6"),
        ],
    ),
    SourceSpec(
        law_abbr="КСО",
        law_name="Кодекс за социално осигуряване",
        candidates=[
            ("lex.bg", "https://lex.bg/laws/ldoc/1597824512"),
        ],
    ),
    # --- related accounting / tax / labour legislation ---------------------
    SourceSpec(
        law_abbr="ЗСч",
        law_name="Закон за счетоводството",
        candidates=[
            ("lex.bg", "https://lex.bg/laws/ldoc/2136697598"),
        ],
    ),
    SourceSpec(
        law_abbr="ДОПК",
        law_name="Данъчно-осигурителен процесуален кодекс",
        candidates=[
            ("lex.bg", "https://lex.bg/laws/ldoc/2135514513"),
            ("nra.bg", "https://nra.bg/wps/portal/nra/zakonodatelstvo/zakonodatelstvo_priority/8294b9c1-f6aa-4253-8027-39184715ba3b"),
        ],
    ),
    SourceSpec(
        law_abbr="ЗМДТ",
        law_name="Закон за местните данъци и такси",
        candidates=[
            ("lex.bg", "https://lex.bg/laws/ldoc/2134174720"),
        ],
    ),
    SourceSpec(
        law_abbr="ЗЗО",
        law_name="Закон за здравното осигуряване",
        candidates=[
            ("lex.bg", "https://lex.bg/laws/ldoc/2134412800"),
        ],
    ),
    SourceSpec(
        law_abbr="ППЗДДС",
        law_name="Правилник за прилагане на Закона за данък върху добавената стойност",
        candidates=[
            ("lex.bg", "https://lex.bg/laws/ldoc/2135534826"),
        ],
    ),
    SourceSpec(
        law_abbr="ППЗАДС",
        law_name="Правилник за прилагане на Закона за акцизите и данъчните складове",
        candidates=[
            ("lex.bg", "https://lex.bg/laws/ldoc/2135526226"),
        ],
    ),
    SourceSpec(
        law_abbr="КТ",
        law_name="Кодекс на труда",
        candidates=[
            ("lex.bg", "https://lex.bg/laws/ldoc/1594373121"),
        ],
    ),
]
