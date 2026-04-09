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
