# Bulgarian Accounting & Legal AI Assistant

An AI assistant for Bulgarian accountants. It ingests accounting documents (XML
exports, OCR'd PDF invoices), validates and deduplicates them, and answers
questions grounded in the firm's own data and Bulgarian tax/accounting law.

## Repository layout

- `backend/` - FastAPI service: invoice ingestion (XXE-safe XML, OCR, Bulgarian
  field extraction), comparison/duplicate detection, a deterministic validation
  engine, JWT auth with multi-tenant Postgres/pgvector storage, and a
  LiteLLM-backed `/chat` orchestrator over an invoices + laws RAG. See
  `backend/README.md`.
- `frontend/` - Angular 19 workspace, also buildable as an embeddable
  `<ledgerly-assistant>` web component. See `frontend/README.md`.
- `lex/` - standalone Bulgarian legislation retrieval engine: scrapes lex.bg,
  chunks by член/алинея, runs hybrid BM25 + dense (bge-m3) retrieval with RRF
  fusion and cross-encoder reranking, and returns cited passages. See
  `lex/README.md`.
- `infra/` - local Postgres + pgvector for development.

`lex/` is the stronger legislation-retrieval engine. Wiring it into the backend
`/chat` orchestrator, in place of the curated laws corpus, is the next
integration step.

## Run the app (Docker)

```bash
docker compose up --build
# frontend + API on http://localhost:8080
```

Set `LLM_MODEL` and the matching provider key to enable real chat answers; left
empty, the chat falls back to a deterministic echo. See `docker-compose.yml`.

## Local development

- Backend: `backend/README.md` (uvicorn on :8000, Postgres via `infra/`).
- Frontend: `frontend/README.md` (`npm start` on :4200).
- Legislation retrieval: `lex/README.md` (`python lex/run_ingest.py`, then `run_query.py`).
