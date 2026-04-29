# Frontend ↔ Backend Integration

This document describes how the frontend connects to the FastAPI backend — routing, auth, data fetching, deployment, and the patterns every future feature must follow.

---

## API Base URL and Routing

All backend routes live under `/api/v1`. This prefix is added by the FastAPI `_mount_routers` function in `runtime/app.py` via a parent `APIRouter(prefix="/api/v1")`.

The frontend Axios client has `baseURL: '/api/v1'`, so callers write relative paths:

```ts
api.get('/transactions')         // → GET /api/v1/transactions
api.post('/auth/request-otp')   // → POST /api/v1/auth/request-otp
```

### Route map

| Frontend call | Full URL | Backend router |
|---|---|---|
| `/auth/request-otp` | `/api/v1/auth/request-otp` | `identity` |
| `/auth/verify-otp` | `/api/v1/auth/verify-otp` | `identity` |
| `/auth/refresh` | `/api/v1/auth/refresh` | `identity` |
| `/auth/logout` | `/api/v1/auth/logout` | `identity` |
| `/accounts` | `/api/v1/accounts` | `accounts` |
| `/transactions` | `/api/v1/transactions` | `transactions` |
| `/categories` | `/api/v1/categories` | `categorization` |
| `/categorization-rules` | `/api/v1/categorization-rules` | `categorization` |
| `/investments/...` | `/api/v1/investments/...` | `investments` |
| `/earnings` | `/api/v1/earnings` | `earnings` |
| `/budgets` | `/api/v1/budgets` | `budgets` |
| `/peers` | `/api/v1/peers` | `peers` |
| `/notifications` | `/api/v1/notifications` | `notifications` |
| `/fx` | `/api/v1/fx` | `fx` |
| `/statements` | `/api/v1/statements` | `statements` |
| `/import` | `/api/v1/import` | `import_` |

---

## Auth Flow

Authentication is OTP-based (Twilio). The full flow:

```
LoginPage
  ├─ Step 1: user enters phone → POST /api/v1/auth/request-otp
  └─ Step 2: user enters OTP  → POST /api/v1/auth/verify-otp
                                     → returns { access_token }
                                     → httpOnly refresh_token cookie set by backend
```

**Token storage:**
- `access_token` — stored in memory only (Zustand `auth` store + Axios `client.ts` module var). Never persisted to localStorage/sessionStorage (XSS mitigation).
- `refresh_token` — stored as an httpOnly Secure cookie by the backend. Automatically sent on all API requests.

**Bootstrap on page load (`AuthGuard`):**
1. Mounts before any protected page renders
2. Calls `POST /api/v1/auth/refresh` — succeeds silently if cookie exists
3. On success: stores access token in memory, renders the app
4. On failure: redirects to `/login`

**401 handling (Axios interceptor in `api/client.ts`):**
1. Any 401 response triggers one automatic refresh attempt
2. If refresh succeeds: retries the original request transparently
3. If refresh fails: dispatches `elixir:auth:expired` window event
4. `AuthEventListener` in `App.tsx` catches the event → clears auth store → navigates to `/login`

---

## Data Fetching Pattern

Use TanStack Query for all server state. Never fetch in `useEffect` directly.

### Structure

```
src/api/{domain}.ts      ← plain async functions that call the Axios client
src/hooks/use{Domain}.ts ← TanStack Query wrappers (useQuery / useMutation)
src/components/widgets/  ← consume hooks, never call api/* directly
src/pages/               ← consume hooks, never call api/* directly
```

### Example

```ts
// src/api/transactions.ts
export async function listTransactions(filters = {}) {
  const { data } = await api.get('/transactions', { params: filters })
  return data
}

// src/hooks/useTransactions.ts
export function useRecentTransactions(limit = 5) {
  return useQuery({
    queryKey: ['transactions', 'recent', limit],
    queryFn: () => listTransactions({ limit }),
    enabled: useAuthStore.getState().isAuthenticated,
  })
}

// src/components/widgets/RecentTransactionsWidget.tsx
const { data, isLoading, isError } = useRecentTransactions(5)
```

### Rules
- All queries must include `enabled: useAuthStore.getState().isAuthenticated` — prevents firing before auth bootstraps.
- Query keys must be specific enough to invalidate correctly. Format: `[domain, entity, ...filters]`
- Mutations must invalidate their domain's query keys in `onSuccess`
- Widgets may use a placeholder dataset when `isError` is true — this keeps the UI usable during development when the backend is not running

---

## Widget Integration Status

| Widget | API connected | Hook |
|---|---|---|
| AttentionStrip | Placeholder | — |
| NetPositionWidget | Placeholder | `useNetPosition` (ready to wire) |
| SpendingBreakdownWidget | Placeholder | `useSpendingByCategory` (ready to wire) |
| BudgetStatusWidget | Placeholder | `useBudgets` (ready to wire) |
| **RecentTransactionsWidget** | **✓ Live** | `useRecentTransactions` |
| InvestmentSnapshotWidget | Placeholder | `usePortfolioSummary` + `useHoldings` (ready to wire) |
| PeerBalancesWidget | Placeholder | `usePeers` (ready to wire) |

Widgets not yet wired fall back to placeholder data when `isError === true`, so the UI works even without a running backend. Wire each widget by swapping the placeholder constant for the hook result.

---

## Deployment Architecture

### Production (Docker Compose + PM2)

```
Browser
  │
  ▼ port 80
┌─────────────────────────────────┐
│  nginx (client Docker service)  │
│                                 │
│  /assets/*   → static files     │
│  /api/v1/*   → proxy → api:8000 │
│  /*          → index.html (SPA) │
└─────────────────────────────────┘
        │ (internal docker network)
        ▼ port 8000
┌────────────────┐
│  api service   │  FastAPI + uvicorn
│  /api/v1/...   │
└────────────────┘
```

**PM2 process**: `pm2 start ecosystem.config.js` runs `docker compose up --build`, which builds both the Python API image and the React client nginx image, then starts all services.

**Client Docker build** (`client/Dockerfile`):
1. Stage 1: `node:20-alpine` — `npm ci && npm run build`
2. Stage 2: `nginx:alpine` — serves `dist/` + `client/nginx.conf`

### Development (local)

Two terminals (or use PM2):

```bash
make dev          # terminal 1: Temporal dev-server + FastAPI on :8000
make client-dev   # terminal 2: Vite dev server on :5173
```

Vite proxies `/api` requests to `http://localhost:8000` (configured in `vite.config.ts`). No nginx needed locally.

```bash
# Or use PM2 for the client:
pm2 start ecosystem.config.js --only elixir-client --env development
make dev
```

---

## CORS

The backend `Settings.cors_origins` already includes `http://localhost:5173` (Vite dev) and `http://localhost:3000`. In production the single origin is the nginx host — no CORS issues because browser and API share the same origin (`/api/v1/` on the same port 80).

If you add a custom production domain, add it to `CORS_ORIGINS` in `.env`.

---

## SSE (Server-Sent Events)

The AI classification workflow streams progress via SSE. nginx is configured with:
```nginx
proxy_buffering off;
proxy_cache    off;
proxy_read_timeout 3600s;
```

The frontend will use a `useSSE` hook (not yet built). Pattern:
```ts
const es = new EventSource('/api/v1/statements/{jobId}/stream')
es.onmessage = (e) => { ... }
```

---

## Adding a New Feature — Checklist

1. Add API function to `src/api/{domain}.ts`
2. Add TanStack Query hook to `src/hooks/use{Domain}.ts`
3. Use hook in the component — never call `api.*` directly from a component
4. If it's a new mutation: call `queryClient.invalidateQueries` in `onSuccess`
5. If it needs a new route: add to `App.tsx` and `BottomNav.tsx` if it's a tab
6. If the backend adds a new endpoint: check that it's inside `_mount_routers` under the `v1` router
