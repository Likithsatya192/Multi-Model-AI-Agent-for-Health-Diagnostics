# Health AI — Universal Blood Report Analyzer

An AI-powered blood report analyzer that handles **any blood test panel** from any lab worldwide. Upload a PDF or image, get a full multi-model clinical analysis, then ask follow-up questions via an intelligent chat interface.

---

## Features

- **Universal Report Support** — Analyzes CBC, LFT, KFT/RFT, Lipid Panel, Thyroid, Coagulation, Iron Studies, HbA1c/Diabetes, Electrolytes, and mixed/comprehensive panels. Not limited to CBC.
- **Worldwide Lab Format Compatibility** — Handles Indian path labs (NABL), US (CLIA), European (ISO 15189), and other regional formats with different number conventions (incl. Indian lakh `3,41,000`), unit styles, and table layouts.
- **Vision-First Extraction** — Phone photos of lab reports bypass Tesseract entirely and go to a multimodal Groq model (`llama-4-scout-17b-16e-instruct`). OCR is auto-detected as garbage via medical-token density and the pipeline falls over to the vision path; no user toggle needed.
- **Anti-Hallucination Safeguards** — Deterministic extractor system prompt (no clinical persona), hard rules that forbid inventing/imputing/"correcting" values, post-extraction value-in-text verification, OCR-garbage name filter. Eliminates fabricated parameters (Creatinine, Sodium, etc.) that generic medical LLMs often add.
- **Pediatric-Aware Validation** — Age parsed from the report header (`8 Month(s)`, `2y 3m`, `45 Years`) into buckets (newborn / infant / toddler / child / adolescent / adult). Pediatric buckets override adult-gender ranges for CBC parameters (Hgb, RBC, PCV, MCV, MCH, MCHC, WBC, Neutrophils, Lymphocytes) so an 8-month-old is never flagged against adult thresholds.
- **Dynamic Parameter Extraction** — 483-alias dictionary maps every known raw lab name variant (SGPT→ALT, TLC→Total WBC, FBS→Fasting Blood Glucose, etc.) to canonical names. Unknown parameters pass through only when supported by an embedded reference range AND unit — prevents OCR gibberish from reaching the UI.
- **Gender + Age-Adjusted Reference Database** — Curated reference ranges for CBC, LFT, KFT, Lipid, Thyroid, Diabetes, Iron Studies, Coagulation, Electrolytes, Vitamins, and more.
- **Multi-Model Clinical Analysis** — Severity classification (mild/moderate/severe/critical), percent deviation from reference midpoint, pattern detection across all panels, risk scoring (1–10), age/gender-adjusted contextual analysis, and prioritized recommendations.
- **Enhanced OCR Fallback** — Otsu binarization, deskew correction, multi-PSM Tesseract strategy (PSM 6/4/11), 300 DPI rendering. Used for native-text PDFs or when vision path is unavailable.
- **Dual-Key Groq Routing** — Primary key for heavy reasoning (synthesis/context/recommendations/RAG), secondary key for extraction + vision. Doubles effective TPM, isolates rate-limit cascades.
- **RAG Chatbot** — Ask natural-language questions about your report; answers grounded in your specific results via FAISS vector search + conversation history (last 10 turns). Chat history persisted to Supabase per report.
- **Secure Authentication** — Clerk-based auth (Google + email/password) protecting all routes. Landing page is publicly accessible.
- **Rate Limiting** — `/analyze` capped at 10 req/min, `/chat` at 30 req/min per IP.
- **User History** — Report metadata and chat history stored in Supabase (PostgreSQL).
- **Production Hardened** — Dockerized backend on Render, Next.js frontend on Vercel. Structured JSON logging, health check endpoint, session TTL cleanup, file type + size validation, SHA-256-hashed FAISS indexes.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 15 (App Router) + TypeScript |
| **UI** | Tailwind CSS v3 + Framer Motion + Plus Jakarta Sans |
| **Authentication** | Clerk (`@clerk/nextjs`) |
| **Metadata DB** | Supabase (PostgreSQL) |
| **Backend** | FastAPI + Uvicorn |
| **Pipeline** | LangGraph (8-node DAG) |
| **LLM — Medical Reasoning** | Groq `llama-3.3-70b-versatile` (text extraction fallback, interpretation, patterns, context, synthesis, recommendations, RAG) |
| **LLM — Vision** | Groq `meta-llama/llama-4-scout-17b-16e-instruct` (image/photo lab-report extraction) |
| **Embeddings** | HuggingFace `sentence-transformers/all-MiniLM-L6-v2` |
| **Vector Store** | FAISS (in-process, persisted to Docker volume, SHA-256 integrity-verified) |
| **OCR (fallback)** | Tesseract + PyMuPDF (fitz) |
| **Containerization** | Docker + Docker Compose |
| **Backend hosting** | Render (Docker) |
| **Frontend hosting** | Vercel |

---

## Architecture

### Request Flow

```
Browser → Nginx → Next.js (frontend:3000)
                    ├── POST /api/upload  → Clerk auth → FastAPI /analyze → LangGraph pipeline → RAG indexing (FAISS)
                    ├── GET  /api/reports → Clerk auth → Supabase query (user's past reports)
                    ├── GET  /api/reports/[id] → Clerk auth → Supabase query (specific report)
                    └── POST /api/query   → Clerk auth → FastAPI /chat → RAG retrieval + Groq LLM → save to Supabase
```

### LangGraph Pipeline (8-node DAG)

```mermaid
flowchart TD
    A([File Upload]) --> B[ingest_and_ocr\nPyMuPDF native → multi-page OCR fallback\nOtsu binarize · deskew · multi-PSM · 300 DPI]
    B --> C[extract_parameters\nVision-first for images/photos · Groq llama-4-scout\nText fallback · 483 aliases · anti-hallucination gates]
    C --> D[validate_standardize\nAge bucket parsing · pediatric ranges · gender-adjusted\nreport-embedded ranges · pass-through]
    D --> E[model1_interpretation\nSeverity · critical thresholds · % deviation]
    E --> F[model2_patterns\nCBC + LFT + KFT + Lipid + Thyroid patterns\nRisk score 1–10]
    F --> G[model3_context\nAge/gender-adjusted · urgency level]
    G --> H[synthesis\nPatient-friendly narrative · AI disclaimer]
    H --> I[recommendations\ncritical → urgent → follow-up → lifestyle]
    I --> K([ReportState → API])
    K --> J[rag_indexing\nChunk → Embed → FAISS · SHA-256 integrity hash]

    style A fill:#4ade80,color:#000
    style K fill:#4ade80,color:#000
    style J fill:#fbbf24,color:#000
```

#### Node responsibilities

| Node | Output |
|---|---|
| `ingest_and_ocr` | `raw_text` — native PDF text or multi-page Tesseract OCR (used for PDFs with embedded text; vision path bypasses this for photos) |
| `extract_parameters` | `extracted_params`, `patient_info`, `report_type` — all lab values + demographics. Vision-first for images; text LLM fallback. Anti-hallucination filters applied |
| `validate_standardize` | `validated_params` — pediatric- + gender-adjusted LOW/NORMAL/HIGH flags, scale-normalized, unit-converted |
| `model1_interpretation` | `param_interpretation` — severity, % deviation, critical alerts |
| `model2_patterns` | `patterns`, `risk_assessment` — clinical syndromes + risk score |
| `model3_context` | `context_analysis` — demographic context, adjusted concerns, urgency |
| `synthesis` | `synthesis_report` — patient-friendly narrative with disclaimer |
| `recommendations` | `recommendations` — prioritized action list with clinical rationale |

### Supported Blood Test Panels

| Panel | Parameters Extracted |
|---|---|
| **CBC / FBC** | Hb, RBC, PCV/HCT, MCV, MCH, MCHC, RDW, WBC/TLC, Platelets, Differential (N/L/M/E/B %), Absolute counts, ESR, MPV, PDW, PCT |
| **LFT** | ALT/SGPT, AST/SGOT, ALP, GGT, Total/Direct/Indirect Bilirubin, Total Protein, Albumin, Globulin, A/G Ratio, LDH |
| **KFT / RFT** | Creatinine, BUN, Blood Urea, Uric Acid, eGFR |
| **Electrolytes** | Na, K, Cl, HCO₃, Ca, Phosphorus, Mg |
| **Lipid Panel** | Total Cholesterol, Triglycerides, HDL, LDL, VLDL, Non-HDL, TC/HDL Ratio |
| **Thyroid** | TSH, Free T3, Total T3, Free T4, Total T4 |
| **Diabetes** | FBS/FPG, PPBS, Random Glucose, HbA1c |
| **Iron Studies** | Serum Iron, TIBC, Transferrin Saturation, Ferritin |
| **Coagulation** | PT, INR, aPTT, Fibrinogen, D-Dimer, Bleeding/Clotting Time |
| **Inflammatory** | CRP, hsCRP |
| **Vitamins** | Vitamin D, Vitamin B12, Folate |
| **Other** | Amylase, Lipase, PSA |

### Pattern Detection (model2_patterns)

| Panel | Patterns Detected |
|---|---|
| **CBC** | Microcytic/Macrocytic/Normocytic Anemia, Iron Deficiency Anemia, Leukopenia/Leukocytosis, Neutropenia, Lymphopenia, Pancytopenia, Acute Infection, Thrombocytopenia/cytosis, Polycythemia |
| **LFT** | Hepatocellular Injury, Cholestatic Pattern, Obstructive Jaundice, Hepatic Synthetic Defect, Mixed Liver Disease |
| **KFT** | Acute/Chronic Kidney Disease, Hyperuricemia, Hyponatremia, Hyperkalemia |
| **Lipid** | Dyslipidemia, Hypertriglyceridemia, Low HDL Syndrome, Metabolic Syndrome |
| **Thyroid** | Hypothyroidism, Hyperthyroidism, Subclinical Hypo/Hyperthyroid |
| **Diabetes** | Impaired Fasting Glucose, Diabetes Mellitus, Poor Glycemic Control |

### RAG Chat Flow

```mermaid
flowchart LR
    U([User Question]) --> Q[Next.js /api/query]
    Q --> F[FastAPI /chat]
    F --> R[rag_retrieve_and_answer]
    R --> V[(FAISS Index)]
    V --> E[Top-k similar chunks]
    E --> L[Groq llama-3.3-70b + context + history]
    L --> A([Answer + saved to Supabase])
```

---

## Project Structure

```
health_ai_project/
├── api.py                        # FastAPI app (/analyze, /chat, /health)
├── app.py                        # Streamlit alternative UI
├── requirements.txt
├── Dockerfile
├── docker-compose.yml            # Dev stack
├── docker-compose.prod.yml       # Production stack
│
├── graph/
│   ├── graph_builder.py          # 8-node LangGraph DAG
│   ├── graph_state.py            # ReportState (includes report_type field)
│   ├── run_pipeline.py           # Pipeline entry point
│   ├── rag_graph_builder.py
│   └── rag_pipeline.py
│
├── nodes/
│   ├── ingest_and_ocr.py         # PDF/image ingestion
│   ├── extract_parameters.py     # Universal extraction · 483 aliases · dynamic schema
│   ├── validate_standardize.py   # 84-param DB + report ref range fallback
│   ├── model1_interpretation.py  # Severity + critical alerts
│   ├── model2_patterns.py        # Multi-panel pattern detection (CBC/LFT/KFT/Lipid/Thyroid/Diabetes)
│   ├── model3_context.py         # Demographic context + urgency
│   ├── synthesis.py              # Narrative report
│   ├── recommendations.py        # Prioritized recommendations
│   └── rag_node.py               # FAISS indexing + RAG query
│
├── utils/
│   ├── llm_utils.py              # get_llm (70b quality) + get_fast_llm (8b fast)
│   ├── ocr_utils.py              # Otsu · deskew · multi-PSM · 400 DPI
│   └── reference_ranges.py
│
├── configs/
│   └── reference_ranges.json     # 84 parameters across all panels (gender-adjusted)
│
└── frontend/
    ├── app/
    │   ├── layout.tsx            # Root layout (Clerk, afterSignOutUrl="/")
    │   ├── page.tsx              # Landing page (publicly accessible)
    │   └── api/
    │       ├── upload/route.ts   # POST → /analyze (authenticated)
    │       ├── query/route.ts    # POST → /chat + chat history saved to Supabase
    │       ├── reports/route.ts
    │       └── reports/[id]/route.ts
    ├── components/
    │   ├── Dashboard.tsx         # Main app UI (logo → home link, chat full-height layout)
    │   ├── ChatComponent.tsx     # Chat UI (initialChat prop, history persistence)
    │   └── ui/
    │       ├── AnalysisProgress.tsx
    │       ├── CbcChart.tsx
    │       ├── ConfirmModal.tsx
    │       └── Toast.tsx
    ├── lib/
    │   ├── supabase.ts
    │   └── sanitize.ts
    ├── middleware.ts              # Clerk auth middleware
    ├── proxy.ts                  # Route matcher (/ is public)
    ├── Dockerfile
    └── nginx.conf
```

---

## Local Development Setup

### Prerequisites

- Node.js 18+
- Python 3.10+
- Docker & Docker Compose
- Tesseract OCR (`sudo apt install tesseract-ocr` on Linux; installer on Windows)
- Optional: `scipy` (`pip install scipy`) enables OCR deskew correction

### 1. Clone

```bash
git clone https://github.com/Likithsatya192/AI-Powered-CBC-Analyzer.git
cd health_ai_project
```

### 2. Environment Variables

**Root `.env`** (backend):
```env
# Primary Groq key — used by heavy reasoning nodes
# (synthesis, context, recommendations, RAG chat)
GROQ_API_KEY=your_groq_api_key

# Secondary Groq key — used by extraction + vision + as fallback for primary
# failures. Doubles effective TPM, isolates rate-limit cascades.
# If unset, the code falls back to GROQ_API_KEY for all calls.
GROQ_API_KEY_2=your_second_groq_api_key

# Optional vision-model override (default: meta-llama/llama-4-scout-17b-16e-instruct)
GROQ_VISION_MODEL=meta-llama/llama-4-scout-17b-16e-instruct

ALLOWED_ORIGINS=http://localhost:3000,https://your-app.vercel.app
FAISS_INDEX_DIR=faiss_index           # optional, default: faiss_index/
TESSERACT_CMD=/usr/bin/tesseract      # optional, auto-detected on Windows
HUGGINGFACE_API_KEY=hf_...            # optional, higher rate limits during build
```

**`frontend/.env.local`**:
```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
CLERK_SECRET_KEY=sk_...
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
FASTAPI_URL=http://localhost:8000     # http://backend:8000 inside Docker
```

> **Security:** Never commit `.env` or `frontend/.env.local`. Both are in `.gitignore`.

### 3. Run with Docker (recommended)

```bash
docker-compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |

### 4. Run without Docker

```bash
# Backend
pip install -r requirements.txt
uvicorn api:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

---

## Supabase Setup

### Create `reports` table

```sql
create table reports (
  id                   uuid primary key default gen_random_uuid(),
  user_id              text not null,
  filename             text not null,
  title                text,
  rag_collection_name  text,
  risk_score           integer,
  analysis_data        jsonb not null,
  created_at           timestamptz default now()
);

create index reports_user_id_idx    on reports(user_id);
create index reports_created_at_idx on reports(created_at desc);
```

The `analysis_data.chat_history` key is updated in-place by `/api/query` after each chat message.

### Disable RLS

```sql
alter table reports disable row level security;
```

---

## Deployment

Backend → **Render** (Docker service, `render.yaml` blueprint). Frontend → **Vercel** (Git-linked, `frontend/vercel.json`). Both redeploy automatically on push to `main`.

### Render (backend)

Blueprint file: `render.yaml`. First deploy creates the `health-ai-backend` web service from the root `Dockerfile`. Health check: `/health`. Free plan spins down after 15 min idle — use UptimeRobot to ping `/health` every 5 min.

Environment variables to set in Render → Service → **Environment**:

| Key | Value | Notes |
|---|---|---|
| `GROQ_API_KEY` | `gsk_...` | Primary Groq key |
| `GROQ_API_KEY_2` | `gsk_...` | Secondary Groq key (extraction + vision + fallback) |
| `GROQ_VISION_MODEL` | `meta-llama/llama-4-scout-17b-16e-instruct` | Optional — only set to override default |
| `ALLOWED_ORIGINS` | `https://your-app.vercel.app` | Comma-separate multiple origins |
| `HF_TOKEN` | `hf_...` | Optional — higher HuggingFace rate limits during image build |
| `PORT` | `8000` | Already set by `render.yaml` |

### Vercel (frontend)

Project root: `frontend/`. `frontend/vercel.json` controls build. Environment variables to set in Vercel → Project → **Settings → Environment Variables** (Production + Preview):

| Key | Value |
|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | `pk_live_...` (use `pk_test_...` for Preview) |
| `CLERK_SECRET_KEY` | `sk_live_...` (use `sk_test_...` for Preview) |
| `NEXT_PUBLIC_SUPABASE_URL` | `https://xxx.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `eyJ...` |
| `FASTAPI_URL` | `https://health-ai-backend.onrender.com` (your Render service URL) |

> **Clerk Production vs Development** — If the deployed frontend still shows a "Development mode" banner, you are using `pk_test_...` in Production. Switch both Clerk values to the `pk_live_` / `sk_live_` pair from the Clerk → Production instance.

---

## API Reference

| Method | Endpoint | Rate Limit | Description |
|---|---|---|---|
| `POST` | `/analyze` | 10/min/IP | Upload blood report file; returns full analysis |
| `POST` | `/chat` | 30/min/IP | RAG-based Q&A about a report |
| `GET` | `/health` | — | Health check; returns `200 ok` or `503 degraded` |
| `GET` | `/docs` | — | Swagger UI |

### `/analyze` Response

```json
{
  "report_type": "CBC",
  "risk_score": 7,
  "risk_rationale": ["Hemoglobin critically low at 6.8 g/dL"],
  "param_interpretation": {
    "Hemoglobin": { "value": 6.8, "unit": "g/dL", "status": "low", "severity": "critical", "is_critical": true, "deviation_pct": -51.0 }
  },
  "synthesis_report": "...",
  "recommendations": ["[CRITICAL] Seek emergency care immediately..."],
  "patterns": ["Microcytic Anemia"],
  "context_analysis": { "urgency": "urgent", "analysis": "...", "adjusted_concerns": "..." },
  "rag_collection_name": "report_abc123",
  "errors": []
}
```

---

## LLM Model Configuration

| Role | Groq Model ID | Used in | API key |
|---|---|---|---|
| Vision extraction | `meta-llama/llama-4-scout-17b-16e-instruct` | `extract_parameters` (image/photo path) | `GROQ_API_KEY_2` |
| Medical reasoning | `llama-3.3-70b-versatile` | `extract_parameters` (text fallback), `model1_interpretation`, `model2_patterns`, `model3_context`, `synthesis`, `recommendations`, `rag_node` | `GROQ_API_KEY` (primary) + `GROQ_API_KEY_2` (fallback) |

Dual-key routing: primary key handles reasoning, secondary key handles extraction + vision and acts as fallback on 429s — prevents rate-limit cascades across the pipeline.

## Anti-Hallucination Safeguards

Medical LLMs tend to "helpfully" fill in missing lab values from memory (e.g. adding a plausible Creatinine or Sodium that wasn't in the report). The pipeline blocks this with five layered defences in `nodes/extract_parameters.py`:

1. **Deterministic extractor system prompt** — the clinical-specialist persona was removed; the model is instructed to act as a pure OCR-to-JSON transformer.
2. **Hard rules A–G** in the user prompt — explicit "never invent", "never impute", "never copy typical values", "never correct implausible-looking digits".
3. **`_value_in_text()`** — every extracted numeric value must appear literally in `raw_text` (comma/whitespace tolerant). Applied on the text-extraction path.
4. **`_canonicalize()` strict matching** — minimum alias length 4 + unit+ref requirement for unrecognized names.
5. **`_looks_like_ocr_garbage()`** — medical-stem/length/token heuristic kills `"Poa"`, `"Copirapams"`, `"Wa ney Lem Yodan Are"`, etc.

## Pediatric Support

`nodes/validate_standardize.py::parse_age_to_years()` handles:
- `"8 Month(s)"` → 0.67 years → `infant` bucket
- `"2y 3m"` → 2.25 years → `toddler` bucket
- `"45 Years"` → 45 years → `adult` bucket
- `"28 days"` → 0.077 years → `newborn` bucket

Buckets: `newborn` (<28 d), `infant` (28 d–1 y), `toddler` (1–5 y), `child` (6–12 y), `adolescent` (13–17 y), `adult` (18+). Pediatric bucket always beats adult-gender range. If a parameter has no pediatric data in the DB, `resolve_reference()` returns `(None, None)` so the pipeline falls back to the report-embedded range instead of misapplying adult thresholds.

---

## Notes

- **Chat History** — Persisted per-report in Supabase (`analysis_data.chat_history`). In-memory RAG session expires after 1 hour of inactivity.
- **FAISS Indexes** — Persisted to `faiss_index/<namespace>/` via Docker volume. SHA-256 hashed on write, verified before load.
- **Multi-page OCR** — All PDF pages processed independently with Otsu binarization + multi-PSM strategy. Best result per page selected by character count.
- **Pass-through Parameters** — Parameters absent from the reference database are validated using the report's own embedded reference ranges. Parameters with neither are passed downstream with `UNKNOWN` flag — still visible in the analysis.
- **AI Disclaimer** — All synthesis reports include a disclaimer that output is AI-generated and does not constitute medical advice.

---

## Author

**Likith Sagar**  
GitHub: [Likithsatya192](https://github.com/Likithsatya192)
