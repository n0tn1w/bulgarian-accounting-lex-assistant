# lex — Bulgarian legal-text retrieval

The **legal-knowledge half** of a larger Bulgarian accounting/legal AI assistant
(see [idea/idea.md](../idea/idea.md)). The full system envisions two RAG agents
(invoices + legislation) feeding an LLM; this module is the **legislation**
agent, and only its **retrieval** portion.

Given a **hardcoded** Bulgarian query (e.g. *„какви са осигуровките за СОЛ през
2026"*) it scrapes Bulgarian legislation, splits it by **член/алинея**, indexes
it, and returns the most relevant **passages with precise citations** (закон,
чл., ал., source URL).

> **Scope (MVP):** pure retrieval — **no** LLM answer generation, **no** UI,
> **no** interactive input. Output is ranked, cited law passages (the *извличане*
> step, not *генериране*). Generation/refusal lives in a downstream module.

Covers course topics **L3** (Bulgarian tokenization for BM25), **L6** (data
quality: cleaning/dedup/normalization), **L11** (vector DB, hybrid retrieval +
reranking).

## Pipeline

```
scrape (lex.bg)
  -> clean HTML
  -> chunk by Чл. N / ал. M           (precise Citation per chunk)
  -> embed (bge-m3)  +  BM25 (Bulgarian tokenizer)
  -> hybrid retrieval (RRF fusion)
  -> cross-encoder rerank (bge-reranker-v2-m3)
  -> top-N passages + citations
```

## Key design decisions

- **Language:** Python.
- **Ingestion:** live scraping of lex.bg (pluggable per-site adapters; an
  `nra.bg` adapter exists as a fallback).
- **Retrieval:** hybrid (dense + BM25) fused with **Reciprocal Rank Fusion**,
  then **cross-encoder rerank**.
- **Models (local, swappable):** `BAAI/bge-m3` (dense embeddings, strong
  multilingual incl. Bulgarian) + `BAAI/bge-reranker-v2-m3` (cross-encoder). No
  API keys, runs offline after the first model download. Swap via the `Embedder`
  interface.
- **Vector store:** ChromaDB (persistent, local, zero-infra).

## Layout

| Path | Responsibility |
|------|----------------|
| `config.py` | All tunables (paths, model names, top-k, RRF/rerank thresholds). |
| `rag/models.py` | Dataclasses: `SourceDoc`, `Citation`, `Chunk`, `RetrievedChunk`. |
| `rag/scraping/` | `BaseScraper` (headers, retry/backoff, disk cache) + `LexBgScraper`, `NapScraper`, `sources.py` registry. |
| `rag/parsing/` | `HtmlCleaner` (strip nav/scripts, normalize), `ArticleChunker` (split by Чл./ал.). |
| `rag/text/` | `BgTokenizer` — Cyrillic-aware tokenizer + Bulgarian stopwords (+ optional `simplemma` lemmatization) for BM25. |
| `rag/embedding/` | `Embedder` ABC + `BgeEmbedder`. |
| `rag/store/` | `ChromaVectorStore` (dense), `Bm25Store` (sparse, pickled). |
| `rag/retrieval/` | `HybridRetriever` (RRF), `CrossEncoderReranker`, `RetrievalPipeline`. |
| `rag/ingest.py` | `IngestPipeline` — end-to-end scrape → chunk → embed → index. |
| `run_ingest.py` / `run_query.py` | CLI entrypoints. |

### Data model (`models.py`)
- `Citation`: `law_abbr` (ЗДДС), `law_name`, `source_site`, `url`, `article`
  (Чл. 96), `paragraph` (ал. 1), `point` (т. 2), `version_date`. `label()`
  renders e.g. `ЗДДС, Чл. 96, ал. 1`.
- `Chunk`: `id`, `text`, `citation`.
- `RetrievedChunk`: `chunk`, `dense_rank`, `bm25_rank`, `fused_score`, `rerank_score`.

### Logic notes
- **Chunker** detects `Чл. N` and `(N)` алинеи; one chunk per алинея (fallback:
  per член) for precise citations. Over-long алинеи are sentence-windowed with
  overlap. Each chunk is prefixed with its citation label so it is
  self-describing for search.
- **L6 data quality:** decompose scripts/nav/ads, normalize whitespace, map Latin
  look-alike letters to Cyrillic, drop too-short fragments, dedup identical chunks.
- **Hybrid + RRF:** dense and BM25 candidates are fused by rank
  (`score = Σ 1/(k0 + rank)`), sidestepping incomparable score scales; the
  cross-encoder then reranks the fused candidates.
- **No-source guard:** if the best rerank score is below
  `settings.min_rerank_score`, the result is flagged `has_confident_source=False`
  — the retrieval-side analog of „отказ при липса на източник".

## Sources

`TARGET_SOURCES` in [rag/scraping/sources.py](rag/scraping/sources.py) —
all verified to fetch + parse on lex.bg:

| Abbr | Document |
|------|----------|
| ЗДДС | Закон за данък върху добавената стойност |
| ЗКПО | Закон за корпоративното подоходно облагане |
| ЗДДФЛ | Закон за данъците върху доходите на физическите лица |
| КСО | Кодекс за социално осигуряване |
| ЗСч | Закон за счетоводството |
| ДОПК | Данъчно-осигурителен процесуален кодекс |
| ЗМДТ | Закон за местните данъци и такси |
| ЗЗО | Закон за здравното осигуряване |
| ППЗДДС | Правилник за прилагане на ЗДДС |
| ППЗАДС | Правилник за прилагане на ЗАДС |
| КТ | Кодекс на труда |

Each law lists candidate URLs (lex.bg primary, optional нра.bg fallback) tried in
order. To add a law, append a `SourceSpec` — nothing else changes.

## Setup & CLI usage

```bash
pip install -r lex/requirements.txt

# 1) Build the index (scrapes sources; caches raw HTML under data/raw/)
python lex/run_ingest.py

# 2) Run the hardcoded query and print cited passages
python lex/run_query.py
```

First run downloads the bge-m3 + reranker models (~2 GB) into
`~/.cache/huggingface/` and runs on CPU by default (ingest of ~4.5k chunks takes
tens of minutes on CPU). Inspect `data/processed/chunks.jsonl` to verify citations.

`run_ingest.py` defaults to `reset=True`, so it is **idempotent** — re-running
rebuilds the index from scratch (no duplicate rows).

## Programmatic use from another module

Another module in the system (e.g. the LLM generation agent or an orchestrator)
should **import the pipeline classes** rather than shell out. The entrypoints
`run_ingest.py` / `run_query.py` are thin CLI wrappers around these same classes.

> **Import note:** the `rag` package imports `from config import settings`, so
> the `lex/` directory must be on `sys.path` (or `PYTHONPATH`). The two
> entrypoints do `sys.path.insert(0, <lex dir>)`; do the same from an external
> caller, or install the project so `lex/` is importable.

### Building / refreshing the index

```python
import sys; sys.path.insert(0, "/path/to/lex")   # see import note above
from rag.ingest import IngestPipeline

# Scrape -> chunk -> embed -> index. reset=True rebuilds from scratch.
n_chunks = IngestPipeline().run(reset=True)
```

This is exactly what [run_ingest.py](run_ingest.py) calls. Run it once up front,
or on a schedule when legislation changes.

### Querying (the typical integration point)

```python
import sys; sys.path.insert(0, "/path/to/lex")
from rag.retrieval.pipeline import RetrievalPipeline

# Loads Chroma + BM25 + both models ONCE. Reuse this instance across queries.
pipeline = RetrievalPipeline()

result = pipeline.retrieve("какви са осигуровките за СОЛ през 2026")

if not result.has_confident_source:
    ...   # downstream module should refuse / ask to rephrase

for rc in result.results:                 # list[RetrievedChunk], best first
    cit = rc.chunk.citation
    print(cit.label(), cit.url, rc.rerank_score)
    context_text = rc.chunk.text          # feed this to the LLM as grounded context
```

`retrieve()` returns a `RetrievalResult` with:
- `results: list[RetrievedChunk]` — ranked passages; each has `.chunk.text`,
  `.chunk.citation` (with `.label()` and `.url`) and the scores.
- `has_confident_source: bool` — whether the top hit cleared the rerank threshold.

A generation agent would typically: call `retrieve()`, check
`has_confident_source`, then build an LLM prompt from the `results`' `chunk.text`
+ `citation.label()` so the answer can cite primary sources (and refuse when the
flag is `False`).

**Performance:** construct `RetrievalPipeline` **once** and reuse it — the
constructor loads ~2 GB of models and opens the stores. Per-query cost is just
embedding the query + a rerank over the candidates.

### Alternative: invoke as a subprocess

If the caller is not Python, run the scripts and parse stdout, or import
`data/processed/chunks.jsonl`. For a real cross-language integration, prefer
wrapping `RetrievalPipeline` behind a small HTTP/RPC service (out of scope here).

## Where everything is saved

| Artifact | Path | Used at query time? |
|----------|------|:---:|
| Scraped HTML cache | `lex/data/raw/` | no |
| Parsed chunks (debug) | `lex/data/processed/chunks.jsonl` | no |
| Dense vector index | `lex/storage/chroma/` | **yes** |
| Keyword (BM25) index | `lex/storage/bm25.pkl` | **yes** |
| Embedding/rerank models | `~/.cache/huggingface/` | **yes** |

`data/` and `storage/` are gitignored and fully regenerated by `run_ingest.py`.
The "database" to back up or delete-to-rebuild is `lex/storage/`.

## Swapping models / sources

- **Embeddings backend:** implement the `Embedder` interface in
  [rag/embedding/embedder.py](rag/embedding/embedder.py) (e.g. an OpenAI
  backend) — the stores and retrieval pipeline are unchanged.
- **Source URLs / laws:** edit `TARGET_SOURCES` in
  [rag/scraping/sources.py](rag/scraping/sources.py).
- **Retrieval depths / thresholds:** all in [config.py](config.py)
  (`dense_top_k`, `bm25_top_k`, `fused_candidates`, `final_top_n`,
  `min_rerank_score`, `rrf_k0`).

## Known limitations (MVP)

- lex.bg has anti-bot protection; the scraper sends browser-like headers. If a
  source fails, ingestion logs it and falls back to the next candidate URL.
  `ldoc` IDs may need re-verification over time.
- Chunking targets the standard `Чл. N (M)` layout; unusual formatting (tables,
  appendices, transitional provisions) may chunk imperfectly.
- No freshness/re-ingestion scheduling, no evaluation harness (citation accuracy,
  groundedness), and no answer generation — all explicitly deferred to other
  modules / later work.
```
