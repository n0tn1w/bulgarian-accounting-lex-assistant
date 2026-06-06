"""Base HTTP scraper: browser-like headers, retries, polite delays, on-disk cache.

lex.bg (and some НАП pages) reject naive clients with HTTP 403, so we send a
realistic User-Agent and Accept headers. Fetched HTML is cached under
``data/raw/`` keyed by URL hash so repeated ingests don't re-hit the sites.
"""
from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

import requests

from config import settings
from ..models import SourceDoc

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "bg,en;q=0.8",
    "Connection": "keep-alive",
}


class BaseScraper(ABC):
    """Abstract scraper. Subclasses implement :meth:`scrape` per site."""

    site_name: str = "base"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self._last_request_ts: float = 0.0

    # -- networking ---------------------------------------------------------
    def _cache_path(self, url: str) -> Path:
        h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
        return settings.raw_dir / f"{self.site_name}_{h}.html"

    def fetch(self, url: str, use_cache: bool = True) -> str:
        """GET a URL with retry/backoff and disk caching; returns HTML text."""
        cache = self._cache_path(url)
        if use_cache and cache.exists():
            return cache.read_text(encoding="utf-8")

        last_err: Optional[Exception] = None
        for attempt in range(1, settings.max_retries + 1):
            self._respect_delay()
            try:
                resp = self.session.get(url, timeout=settings.request_timeout)
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding or "utf-8"
                html = resp.text
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(html, encoding="utf-8")
                return html
            except requests.RequestException as exc:  # noqa: PERF203
                last_err = exc
                backoff = settings.polite_delay_sec * (2 ** (attempt - 1))
                print(f"  [warn] fetch failed ({attempt}/{settings.max_retries}) {url}: {exc}; "
                      f"retrying in {backoff:.1f}s")
                time.sleep(backoff)
        raise RuntimeError(f"Failed to fetch {url}: {last_err}")

    def _respect_delay(self) -> None:
        elapsed = time.time() - self._last_request_ts
        if elapsed < settings.polite_delay_sec:
            time.sleep(settings.polite_delay_sec - elapsed)
        self._last_request_ts = time.time()

    # -- contract -----------------------------------------------------------
    @abstractmethod
    def scrape(self, spec) -> List[SourceDoc]:
        """Fetch the document(s) described by a SourceSpec into SourceDoc(s)."""
        raise NotImplementedError
