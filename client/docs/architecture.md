# Frontend Architecture

## What This Is

The `client/` directory is the Elixir PWA frontend — a mobile-first React application that connects to the FastAPI backend over HTTPS and SSE. It lives as a sibling to `src/` and is deployed as a static build served by any CDN or the same host.

It is **not** a server-rendered app, has **no** backend responsibilities, and must never talk directly to any external API (Twilio, AMFI, etc.) — all data flows through the Elixir backend.

---

## Tech Stack

| Concern | Choice | Version |
|---|---|---|
| Framework | React | 18 |
| Language | TypeScript | strict mode |
| Build tool | Vite | latest |
| Styling | Tailwind CSS | v4 |
| Component primitives | shadcn/ui (Radix UI) | copy-owned |
| Charts | Recharts | latest |
| Server state | TanStack Query | v5 |
| Client state | Zustand | latest |
| Routing | React Router | v6 |
| Animations | Framer Motion | latest |
| PWA | vite-plugin-pwa | latest |

**Why these choices:**
- shadcn/ui components are copy-owned (not a dependency) — full control over styling, no version lock-in
- TanStack Query handles caching, background refetch, and SSE subscription lifecycle
- Zustand is used only for UI-local state (dashboard layout, theme preference) — nothing that belongs on the server
- Recharts is composable and renders well at mobile viewport widths with INR formatting

---

## Folder Structure

```
client/
├── public/
│   ├── manifest.json           # PWA manifest
│   └── icons/                  # App icons (192, 512)
├── src/
│   ├── main.tsx                # Entry point
│   ├── App.tsx                 # Router + providers
│   ├── api/                    # Typed API client functions, one file per backend domain
│   │   ├── client.ts           # Axios/fetch base, auth token injection
│   │   ├── transactions.ts
│   │   ├── investments.ts
│   │   ├── budgets.ts
│   │   ├── peers.ts
│   │   ├── earnings.ts
│   │   ├── accounts.ts
│   │   ├── categories.ts
│   │   ├── statements.ts
│   │   ├── notifications.ts
│   │   └── identity.ts
│   ├── components/
│   │   ├── ui/                 # shadcn base components (Button, Card, Sheet, Badge, Dialog…)
│   │   ├── layout/             # BottomNav, FAB, PageShell, Header, AttentionBar
│   │   ├── charts/             # Recharts wrappers (SpendingDonut, NetFlowBar, BudgetBar…)
│   │   └── widgets/            # Dashboard widget components (one file per widget)
│   ├── pages/
│   │   ├── home/               # Dashboard
│   │   ├── transactions/       # Browse, filter, detail, manual add
│   │   ├── investments/        # Portfolio, holdings, SIP, FD
│   │   ├── peers/              # Contacts, balances, settlements
│   │   └── more/
│   │       ├── budgets/
│   │       ├── earnings/
│   │       ├── accounts/
│   │       ├── categories/
│   │       └── settings/
│   ├── hooks/                  # Custom hooks (useNotifications, useDashboardLayout, …)
│   ├── store/                  # Zustand stores
│   │   ├── theme.ts            # light/dark + accent color
│   │   └── dashboard.ts        # Widget order + visibility prefs
│   ├── types/                  # TypeScript types mirroring backend Pydantic schemas
│   └── lib/
│       ├── format.ts           # INR formatter, date helpers
│       └── constants.ts
├── docs/                       # This folder — frontend reference docs
├── index.html
├── vite.config.ts
├── tailwind.config.ts
└── tsconfig.json
```

---

## Layer Rules

| Layer | May import | Must NOT import |
|---|---|---|
| `pages/` | `components/`, `hooks/`, `api/`, `store/`, `types/`, `lib/` | Other pages directly |
| `components/widgets/` | `components/ui/`, `components/charts/`, `hooks/`, `types/`, `lib/` | `api/` directly — data comes via props or hooks |
| `components/charts/` | `lib/`, `types/` | `api/`, `store/` |
| `components/ui/` | `lib/` | Everything else |
| `hooks/` | `api/`, `store/`, `types/`, `lib/` | `components/`, `pages/` |
| `api/` | `lib/`, `types/` | `store/`, `components/`, `pages/` |
| `store/` | `types/`, `lib/` | `api/`, `components/`, `pages/` |

---

## API Communication

- All requests go to `/api/v1/...` — Vite proxies this to `http://localhost:8000` in development
- Auth tokens (JWT) are stored in memory (not localStorage) and injected via an Axios request interceptor
- Refresh token is stored in an httpOnly cookie — the `client.ts` base handles 401 → refresh → retry
- SSE streams (AI classification progress, notification push) are managed via TanStack Query's `subscribeToQuery` or a dedicated `useSSE` hook

---

## PWA Behaviour

- App shell is cached on first load — navigation works offline
- Data queries are not cached offline (finance data must be fresh)
- Install prompt is surfaced once after the user completes first statement upload
- Push notifications are not used — the backend uses SSE for real-time delivery

---

## Conventions

- **File names**: `kebab-case.tsx` for components, `camelCase.ts` for non-component modules
- **Component exports**: one named export per file, no default exports
- **Types**: all API response types live in `types/` and are generated from backend schemas or maintained by hand; never use `any`
- **Currency**: all amounts stored as integers (paise) from the API; `lib/format.ts` handles display conversion
- **Dates**: always `Date` objects internally; `lib/format.ts` handles display; never format inline
- **No inline styles**: Tailwind classes only; no `style={{}}` except for dynamic values Tailwind cannot express (e.g., chart colors)
