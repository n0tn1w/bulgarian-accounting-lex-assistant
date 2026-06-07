# invoice_rag

Hybrid retrieval engine and query tools for tenant-scoped invoice data.

## Pipeline

```
indexing/  →  retrieval/  →  tools/
```

- **indexing/**: Converts invoices to text (`text.py`), computes dense BGE-M3 embeddings stored in pgvector (`dense.py`), and builds/loads a per-tenant BM25 index serialised to disk (`sparse.py` + `pipeline.py`).
- **retrieval/**: Bulgarian-aware tokenizer for BM25 queries (`tokenizer.py`), Reciprocal Rank Fusion to merge dense and sparse result lists (`fusion.py`), and the hybrid search entry-point that calls both indices and fuses them (`hybrid.py`).
- **tools/**: Agent-ready tool functions — direct lookup (`lookup.py`), structured filtering (`filter.py`), aggregation and grouping (`aggregate.py`), period-over-period comparison (`compare.py`), and hybrid semantic search with optional pre-filter (`search.py`).

Dense retrieval uses **pgvector** cosine similarity; sparse retrieval uses **Okapi BM25**; results are merged with **RRF** (Reciprocal Rank Fusion). The index is fully rebuildable from the database at any time via `scripts/rebuild_invoice_index.py`.
