# Backend - Accounting AI Assistant

Python/FastAPI backend. This first slice implements the rebuilt core features
(ingestion, comparison/dedup, validation) as a typed tool layer behind a stateless
HTTP API. Auth, multi-tenancy, persistence, RAG, and LLM orchestration are layered on
in later phases.

## Layout

```
app/
  core/      config (pydantic-settings)
  domain/    Pydantic domain models (Invoice, LineItem, Party, TaxLine, ...)
  tools/
    nlp/       identifier tokenizer + normalizer (Cyrillic-aware)
    ingest/    XXE-safe XML parser, OCR (Tesseract bul+eng), BG invoice extractor
    compare/   TF-IDF (word+char) + cosine + linear fusion -> compare & find_duplicates
    validate/  deterministic rule engine (arithmetic, VAT, format, completeness)
  api/       FastAPI routers + request/response schemas
tests/       pytest suite (no OCR system deps needed)
```

## Setup

```bash
# 1) Start Postgres + pgvector (multi-tenant store + vector search)
docker compose -f ../infra/docker-compose.yml up -d

# 2) Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # core + test deps
# optional OCR (needs system Tesseract + Poppler + `bul` language pack):
#   brew install tesseract tesseract-lang poppler   # macOS
pip install -r requirements-ocr.txt
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
# docs: http://localhost:8000/docs
```

## Test

```bash
pytest                 # whole suite
pytest tests/test_validate.py::test_arithmetic_mismatch_fails   # single test
```

## API (current)

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health` | status + OCR availability |
| POST | `/documents/extract-xml` | any XML -> DocCandidate[] (XXE-safe) |
| POST | `/documents/extract-text` | raw/OCR text -> structured Invoice |
| POST | `/documents/extract-pdf` | PDF upload -> OCR -> Invoice (needs OCR deps) |
| POST | `/compare` | pairwise similarity + evidence |
| POST | `/compare/duplicates` | rank candidates, flag duplicates |
| POST | `/validate` | run rule suite over an Invoice |

## Design rules from the architecture docs

- Money is `Decimal`, never `float`. All arithmetic validation is exact.
- The validation engine is deterministic: no LLM in the math.
- XML is parsed with `defusedxml` (XXE/billion-laughs blocked).
- OCR deps are optional and import-guarded; the core API runs without them.
