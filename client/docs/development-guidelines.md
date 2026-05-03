# Frontend Development Guidelines

These guidelines govern how every screen in the Elixir frontend is built, integrated with the backend, and verified. Follow them in order for every screen.

---

## One Screen at a Time

Do not start a new screen until the current one is fully wired to the backend and its tests pass. "Done" means:

1. UI components render correctly
2. All API calls use real backend endpoints (no mock data in component/page code)
3. Playwright E2E tests pass against the live backend

---

## Step-by-Step Screen Development

### Step 1 — Design the screen

Before writing a single component, confirm the screen layout matches `docs/design.md`. Identify:
- Every data point displayed
- Every user action (taps, form submissions, navigation)
- Every state the screen can be in (loading, empty, error, populated)

### Step 2 — Build the UI shell

Build all components with realistic placeholder data. This is the only stage where hardcoded data is acceptable. Keep it isolated to the component file — never commit placeholder data to `src/api/` or `src/hooks/`.

### Step 3 — Plan the API integration

Stop before wiring any API call. Answer these questions:

1. Which endpoint(s) does this screen call? (reference `docs/integration.md` route map)
2. What is the exact request schema — path params, query params, body?
3. What does the response look like? (reference backend `schemas.py` for the domain)
4. What loading / empty / error states must the UI handle?
5. Are there mutations? What query keys must be invalidated on success?

Document the answers as a brief comment at the top of the relevant `src/api/{domain}.ts` function before coding it.

### Step 4 — Wire the real API

Replace all placeholder data with live TanStack Query hooks. Rules:
- Add the API function to `src/api/{domain}.ts`
- Add/extend the hook in `src/hooks/use{Domain}.ts`
- Consume the hook in the page/component — never call `api.*` directly from a component
- Update `src/types/` to match the backend Pydantic schema exactly; never use `any`

After this step there must be zero hardcoded data in component/page code.

### Step 5 — Write Playwright E2E tests

Write tests **before** you consider the screen done. See the Testing section below.

### Step 6 — Visual verification

Use Playwright screenshots to verify the screen looks correct at 390px, 768px, and 1280px. Fix layout issues before moving on.

### Step 7 — Final integration checklist

- [ ] No placeholder/mock data in `src/pages/` or `src/components/`
- [ ] Loading skeletons shown while queries are in flight
- [ ] Empty state handled explicitly (not a blank screen)
- [ ] Error state shows a user-facing message
- [ ] Mutations invalidate correct query keys in `onSuccess`
- [ ] Screen works after hard reload (auth bootstrap)
- [ ] No `console.error` or unhandled rejections during normal use
- [ ] All Playwright tests pass against the real running backend

---

## Testing Protocol

### Write tests first

Every change to a screen — new feature, bug fix, refactor — must have a Playwright test written before the implementation. Watch it fail, then make it pass.

### What every screen's tests must cover

**Request/response contracts:**
- Every API call the screen makes is exercised by at least one test
- The correct request is sent: method, URL, query params, body shape
- The UI correctly reflects each response variant: data, empty list, 4xx error, network failure

**User journeys:**
- The golden path (most common action)
- Key edge cases for the screen

**Auth:**
- Unauthenticated access redirects to `/login`
- Mid-session 401 triggers refresh-and-retry or logout

### Test file layout

```
client/tests/
└── {screen-name}/
    ├── {screen-name}.spec.ts       # user journey tests
    └── {screen-name}.api.spec.ts   # request/response contract tests
```

### Asserting network calls

```ts
// Assert the frontend sends the right request
const [request] = await Promise.all([
  page.waitForRequest(
    req => req.url().includes('/api/v1/transactions') && req.method() === 'GET'
  ),
  page.goto('/transactions'),
])
expect(new URL(request.url()).searchParams.get('limit')).toBe('20')

// Assert the response is rendered
await expect(page.getByTestId('transaction-list')).toBeVisible()
await expect(page.getByText('Swiggy')).toBeVisible()
```

Use `page.route()` to stub API responses in tests — this is the only place mock data is allowed.

---

## Visual Testing with Playwright

After functional tests pass, capture screenshots and review:

```ts
await page.setViewportSize({ width: 390, height: 844 })  // mobile
await page.screenshot({ path: 'tests/screenshots/transactions-mobile.png' })
```

Check for:
- No overflow or truncation
- Loading skeletons appear before data
- Empty and error states are visible and informative
- All tap targets ≥ 44px height
- INR currency formatted with ₹ prefix and comma separation
- Dates consistent with `lib/format.ts`

Fix any visual issues found. Re-screenshot after fixes.

---

## Mock Data Policy

| Location | Mock data allowed? |
|---|---|
| `src/pages/`, `src/components/` | **No** |
| `src/hooks/` | **No** |
| `src/api/` | **No** |
| `client/tests/` via `page.route()` | **Yes** |

If a backend endpoint does not yet exist, do not build the screen. Either build the endpoint first, or agree on a contract and stub it only within tests.
