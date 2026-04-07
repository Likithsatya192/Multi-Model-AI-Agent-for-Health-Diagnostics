# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Health AI is a CBC (Complete Blood Count) report analyzer with RAG-based Q&A. Users upload blood reports (PDF/image), the backend runs an 8-node LangGraph pipeline to extract and analyze parameters, and users can then ask questions via chat backed by FAISS vector search.

## Commands

### Backend (Python/FastAPI)

```bash
# Install dependencies
pip install -r requirements.txt

# Run FastAPI server (development)
uvicorn api:app --reload

# Run alternative Streamlit UI
streamlit run app.py
```

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev     # Development server at http://localhost:3000
npm run build   # Production build
npm run lint    # ESLint
```

### Docker (Full Stack)

```bash
# Development (builds from source)
docker-compose up --build

# Production (uses pre-built images from Docker Hub)
docker-compose -f docker-compose.prod.yml up -d
```

Access points when running via Docker:
- Frontend: `http://localhost:3000`
- Backend API + Swagger: `http://localhost:8000/docs`

## Architecture

### Request Flow

```
Browser → Nginx → Next.js (frontend:3000)
                    ├── POST /api/upload → FastAPI /analyze → LangGraph pipeline
                    └── POST /api/query  → FastAPI /chat    → FAISS + Groq LLM
```

Nginx (in `frontend/nginx.conf`) proxies all traffic to the Next.js server on port 3000. Next.js API routes (`app/api/`) handle auth via Clerk middleware before forwarding to the FastAPI backend (`FASTAPI_URL` env var).

### LangGraph Pipeline (`graph/`)

The analysis pipeline is an 8-node DAG defined in `graph/graph_builder.py`. Shared state flows through all nodes via `graph/graph_state.py` (`ReportState` Pydantic model).

Node execution order:
1. `ingest_and_ocr` — PDF/image → text (PyMuPDF + Tesseract)
2. `extract_parameters` — text → CBC values (Groq LLM)
3. `validate_standardize` — validate against `configs/reference_ranges.json`
4. `model1_interpretation` — per-parameter LOW/NORMAL/HIGH classification
5. `model2_patterns` — pattern recognition + risk assessment
6. `model3_context` — contextual analysis (patient age/gender)
7. `synthesis` — generate comprehensive report
8. `recommendations` — clinical recommendations
9. `rag_node` — chunk report → embed (HuggingFace sentence-transformers) → index in Pinecone

### RAG / Chat

- `nodes/rag_node.py` handles both indexing (after analysis) and querying (on `/chat` requests)
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2` via HuggingFace
- Vector store: FAISS, persisted to `faiss_index/<namespace>/` on disk (Docker volume: `faiss_data`)
- In-memory cache (`_faiss_stores` dict) avoids re-loading from disk within the same process
- Chat history is stored in-memory per `session_id` (not persisted across server restarts)

### Key Technologies

| Component | Technology |
|-----------|-----------|
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind CSS + Framer Motion |
| Auth | Clerk (`@clerk/nextjs`) |
| Metadata DB | Supabase (PostgreSQL) |
| Backend | FastAPI + Uvicorn |
| Pipeline | LangGraph |
| LLM | Groq API (LLaMA models) |
| Embeddings | HuggingFace sentence-transformers |
| Vector DB | FAISS (in-process, persisted to Docker volume) |
| OCR | Tesseract + PyMuPDF (fitz) |
| Container | Docker + Nginx |
| CI/CD | GitHub Actions → Docker Hub → AWS EC2 |

## Environment Variables

**Root `.env`** (backend only):
```
GROQ_API_KEY=
```

**`frontend/.env.local`** (Next.js — copy from `.env.local.example`):
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
FASTAPI_URL=http://localhost:8000   # http://backend:8000 in Docker
```

## Key Files

- `api.py` — FastAPI app with `/analyze` and `/chat` endpoints
- `app.py` — Streamlit alternative UI (same backend logic, no Docker needed)
- `graph/graph_builder.py` — LangGraph DAG definition
- `graph/graph_state.py` — `ReportState` shared state model
- `nodes/rag_node.py` — FAISS indexing + RAG query logic
- `utils/llm_utils.py` — Groq LLM wrapper used by all nodes
- `configs/reference_ranges.json` — CBC normal ranges for validation
- `frontend/middleware.ts` — Clerk auth middleware (protects all routes except sign-in/sign-up)
- `frontend/app/api/upload/route.ts` — Authenticated proxy to FastAPI `/analyze`
- `frontend/app/api/query/route.ts` — Authenticated proxy to FastAPI `/chat`
- `frontend/components/Dashboard.tsx` — Main client component (uses `useUser`, `useClerk`)
- `frontend/lib/supabase.ts` — Supabase client initialisation

## Deployment

CI/CD via `.github/workflows/deploy.yml`:
1. Push to `main` → GitHub Actions builds Docker images
2. Images pushed to Docker Hub (secrets: `DOCKER_USERNAME`, `DOCKER_PASSWORD`)
3. SSH into AWS EC2 (secrets: `EC2_HOST`, `EC2_USERNAME`, `EC2_KEY`) and runs `docker-compose -f docker-compose.prod.yml up -d`

## Notes

- No backend test suite exists; test manually via Swagger UI (`/docs`) or Streamlit
- The old `frontend/src/` React+Vite source is superseded by the new Next.js `frontend/app/` + `frontend/components/` structure and can be deleted
- Chat history is in-memory only; restarting the backend clears all sessions
- FAISS indexes are persisted to `faiss_index/<namespace>/` on the backend container; the Docker volume `faiss_data` keeps them across restarts
- Supabase tables (`users`, `documents`, `embeddings_metadata`) are defined in the migration guide — run the SQL in the Supabase SQL editor to set them up
- GitHub Secrets to add: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`; remove the old `VITE_FIREBASE_*` and `PINECONE_*` secrets
