# Backend - Accounting AI Assistant

Python/FastAPI backend: invoice ingestion (XXE-safe XML, OCR, BG field extraction),
comparison/dedup and a deterministic validation engine, JWT auth with multi-tenant
Postgres/pgvector storage, and a LiteLLM `/chat` orchestrator over two RAGs - the
tenant's invoices and Bulgarian legislation (the lex engine under `lex/`).

## Layout

```
app/
  core/      config (pydantic-settings)
  domain/    Pydantic domain models (Invoice, LineItem, Party, TaxLine, ...)
  rag/       invoices + laws retrievers and the LLM client behind /chat
  tools/
    nlp/       identifier tokenizer + normalizer (Cyrillic-aware)
    ingest/    XXE-safe XML parser, OCR (Tesseract bul+eng), BG invoice extractor
    compare/   TF-IDF (word+char) + cosine + linear fusion -> compare & find_duplicates
    validate/  deterministic rule engine (arithmetic, VAT, format, completeness)
  api/       FastAPI routers + request/response schemas
lex/         laws RAG engine (scrape lex.bg -> hybrid retrieve + cross-encoder rerank)
```

## Setup

```bash
# 1) Start Postgres + pgvector (multi-tenant store + vector search)
docker compose -f ../infra/docker-compose.yml up -d

# 2) Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # everything + lint/test tools
# OCR also needs the system Tesseract + Poppler + `bul` language pack:
#   brew install tesseract tesseract-lang poppler                    # macOS
#   apt-get install tesseract-ocr tesseract-ocr-bul poppler-utils    # Debian/Ubuntu
# laws RAG (lex): build the index once (scrapes lex.bg, downloads ~2GB models)
python lex/run_ingest.py
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
# docs: http://localhost:8000/docs
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
| POST | `/rag/invoices/retrieve` | semantic search over the tenant's invoices |
| POST | `/rag/laws/retrieve` | cited law passages from lex |
| POST | `/chat` | merge both RAGs and answer via the LLM (cited) |

The laws RAG (`/rag/laws/*` and the laws half of `/chat`) is the lex engine; it needs
the index built (`python lex/run_ingest.py`). Without the index it returns nothing and
`/chat` answers from invoices alone.

## Design rules from the architecture docs

- Money is `Decimal`, never `float`. All arithmetic validation is exact.
- The validation engine is deterministic: no LLM in the math.
- XML is parsed with `defusedxml` (XXE/billion-laughs blocked).
- OCR deps are optional and import-guarded; the core API runs without them.
