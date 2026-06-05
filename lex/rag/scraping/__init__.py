from .base import BaseScraper
from .lex_bg import LexBgScraper
from .nap import NapScraper
from .sources import TARGET_SOURCES, SourceSpec, get_scraper_for

__all__ = [
    "BaseScraper",
    "LexBgScraper",
    "NapScraper",
    "TARGET_SOURCES",
    "SourceSpec",
    "get_scraper_for",
]
