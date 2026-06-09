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
- `backend/lex/` - the laws RAG engine: scrapes lex.bg, chunks by член/алинея, and
  runs hybrid BM25 + dense (bge-m3) retrieval with cross-encoder reranking to return
  cited law passages. The backend's `/chat` reaches it through `LawsRetriever`. See
  `backend/lex/README.md`.
- `infra/` - local Postgres + pgvector for development.

`/chat` runs two RAGs - the tenant's invoices and the laws (lex) - and feeds both to
the LLM for a grounded, cited answer. With a hosted `LLM_MODEL` + key it uses that;
otherwise it falls back to the containerized Mistral (the `ollama` compose service),
and only echoes the context when no model is reachable. The laws RAG needs a built
index; until that index is built it returns nothing and `/chat` answers from invoices alone.

## Run the app (Docker)

```bash
docker compose up --build
# frontend + API on http://localhost:8080
```

Set `LLM_MODEL` and the matching provider key for a hosted model (Claude/OpenAI/Gemini).
Left empty, the stack uses the bundled `ollama` Mistral container automatically, and
only echoes the retrieved context if no model is reachable. See `docker-compose.yml`.

## Local development

- Backend: `backend/README.md` (uvicorn on :8000, Postgres via `infra/`).
- Frontend: `frontend/README.md` (`npm start` on :4200).
- Laws index (one-time, enables the laws RAG): `cd backend && python lex/run_ingest.py` (scrapes lex.bg, downloads the bge models, ~2GB). In Docker: `docker compose run --rm backend python lex/run_ingest.py`.
