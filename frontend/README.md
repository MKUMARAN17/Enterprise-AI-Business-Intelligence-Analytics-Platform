# Enterprise BI — Frontend

The web workspace for the Enterprise AI BI Platform. Business users ask a question
in plain English and get back a **business insight + KPI cards + chart + data
table + optional export**. Consumes the backend `POST /api/v1/ask` contract.

Built in the same stack as the reference `tensaw-health-promptql-frontend`:
**React 18 · TypeScript · Vite · Tailwind · TanStack Query · axios · zod ·
recharts · react-router**. It is self-contained — the reference's proprietary
`@tensaw/*` design-system packages are replaced by a small in-repo UI kit
(`src/components/ui/primitives.tsx`).

## Run

```bash
cd frontend
npm install
cp .env.example .env.local        # point VITE_API_BASE_URL at the backend
npm run dev                        # http://localhost:5174
```

The backend must be running with **`BI_ALLOW_DEV_LOGIN=true`** and a
`BI_JWT_SECRET`, and its CORS must allow `http://localhost:5174` (both are set in
`backend/.env`). Then sign in by picking a role — the backend mints a JWT for it.

```bash
npm run build       # tsc + vite build → dist/
npm run typecheck
```

## How it maps to the backend

| UI piece | Backend source |
|---|---|
| Sign-in role picker | `POST /api/v1/dev/login` (dev only) |
| Prompt → answer | `POST /api/v1/ask` |
| Insight summary / recommendations | `insight` (Insight Agent) |
| KPI cards | `analytics.kpis` (Analytics Agent) |
| Chart (line/bar/pie/scatter) | `visualization.kind` + `x`/`y` (Visualization Agent) |
| Data table | `columns` / `rows` |
| "Blocked" banner | `status="BLOCKED"` (guardrail / SQL guard / RBAC) |
| Generated SQL panel | `generated_sql` |
| Export badge | `export` |

## Structure

```
src/
├── config/env.ts          typed Vite env
├── api/
│   ├── schemas.ts          zod schemas mirroring the backend contract
│   └── client.ts           axios client (bearer token + problem-details errors)
├── auth/
│   ├── session.ts          token storage
│   ├── AuthContext.tsx      reactive session store
│   └── RequireAuth.tsx      route guard
├── lib/roles.ts            role vocabulary (mirrors bi_auth.Role)
├── components/
│   ├── ui/primitives.tsx    Button/Card/Badge/Spinner
│   └── result/              ChartRenderer, ResultTable, InsightPanel, SqlPanel
├── pages/
│   ├── sign-in/SignInPage.tsx
│   └── workspace/AskWorkspace.tsx
├── AppLayout.tsx  AppTheme.tsx  routes.tsx  main.tsx
```

> Security note: role gating in the UI is cosmetic. The authoritative access
> control is server-side (JWT → RBAC allow-list → SQL guard) — a user only ever
> receives data their role is granted, regardless of what the UI offers.
