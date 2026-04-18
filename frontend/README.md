# Health AI — Frontend

Next.js 16 (App Router) frontend for the AI-powered CBC Report Analyzer.

## Stack

| | |
|---|---|
| Framework | Next.js 16 (App Router, TypeScript) |
| Styling | Tailwind CSS v3 + Framer Motion |
| Auth | Clerk (`@clerk/nextjs` v7) |
| Database | Supabase (report history) |
| Charts | Recharts |
| Font | Plus Jakarta Sans + JetBrains Mono |

## Structure

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout — Clerk provider, ToastProvider
│   ├── page.tsx                # Landing page (animated, auth-aware)
│   ├── globals.css             # Design system, medical animations
│   ├── dashboard/page.tsx      # Protected dashboard shell
│   ├── sign-in/[[...sign-in]]/ # Clerk sign-in (dark theme)
│   ├── sign-up/[[...sign-up]]/ # Clerk sign-up (dark theme)
│   └── api/
│       ├── upload/route.ts     # POST → FastAPI /analyze
│       ├── query/route.ts      # POST → FastAPI /chat
│       ├── reports/route.ts    # GET  → Supabase report list
│       └── reports/[id]/route.ts # GET/DELETE specific report
├── components/
│   ├── Dashboard.tsx           # Main dashboard UI
│   ├── ChatComponent.tsx       # RAG chat interface
│   └── ui/
│       ├── AnalysisProgress.tsx
│       ├── CbcChart.tsx
│       ├── ConfirmModal.tsx
│       └── Toast.tsx
├── lib/
│   ├── supabase.ts
│   └── sanitize.ts
├── middleware.ts               # Clerk auth middleware
└── tailwind.config.js
```

## Local Setup

```bash
# 1. Install dependencies
npm install

# 2. Create frontend/.env.local
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
CLERK_SECRET_KEY=sk_...
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
FASTAPI_URL=http://localhost:8000

# 3. Run dev server
npm run dev        # http://localhost:3000
```

## Environment Variables

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk public key |
| `CLERK_SECRET_KEY` | Clerk secret key (server-side only) |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |
| `FASTAPI_URL` | Backend URL (`http://localhost:8000` locally, `http://backend:8000` in Docker) |

## Vercel Deployment

Auto-redeploys on every push to `main`. Build config lives in `frontend/vercel.json`; project root in Vercel must be set to `frontend`.

### Environment variables (Vercel → Project → Settings → Environment Variables)

Set all five for **Production** and **Preview** scopes:

| Key | Production value | Preview value |
|---|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | `pk_live_...` | `pk_test_...` OK |
| `CLERK_SECRET_KEY` | `sk_live_...` | `sk_test_...` OK |
| `NEXT_PUBLIC_SUPABASE_URL` | `https://xxx.supabase.co` | same |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `eyJ...` | same |
| `FASTAPI_URL` | `https://health-ai-backend.onrender.com` | same |

### Common issues

- **"Development mode" Clerk banner in production** → you are using `pk_test_...` in the Production scope. Replace with `pk_live_...` + `sk_live_...` from the Clerk Production instance and redeploy.
- **502 / network errors from `/api/upload`** → `FASTAPI_URL` is missing or wrong. Must point to the deployed Render URL (no trailing slash). After changing, redeploy (Vercel picks env vars at build time for server routes).
- **CORS errors in browser console** → backend `ALLOWED_ORIGINS` on Render must include the exact Vercel URL (e.g. `https://your-app.vercel.app`). Update the Render env var and redeploy the backend.
- **Render backend spun down (first request slow)** → free plan sleeps after 15 min idle. Configure UptimeRobot to ping `https://health-ai-backend.onrender.com/health` every 5 min.

### Backend reference

The backend is deployed separately on Render using `render.yaml` at the project root. See the project root `README.md` for Render-side env vars (`GROQ_API_KEY`, `GROQ_API_KEY_2`, `ALLOWED_ORIGINS`, etc.).
