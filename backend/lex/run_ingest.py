"""Entrypoint: build the legal-text index.

    python lex/run_ingest.py

Scrapes the target laws, splits them by член/алинея, embeds and indexes them
into the persisted Chroma + BM25 stores under ``storage/``.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Cyrillic output on Windows consoles (cp1252) would crash; force UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Make the package importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag.ingest import IngestPipeline


def main() -> None: 
    n = IngestPipeline().run(reset=True)
    print(f"== IngestPipeline. Ended with {n} chunks ")

if __name__ == "__main__":
    main()
