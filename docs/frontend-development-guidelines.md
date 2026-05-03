# Frontend Development Guidelines

These guidelines govern how every frontend screen is built, integrated, and verified in Elixir. They apply to all work in `client/`.

---

## Core Principle

**Build one screen at a time, end-to-end, before moving to the next.**

A screen is not "done" until its components render correctly, its API calls are wired to the real backend, and its Playwright tests pass. Never carry half-integrated screens forward.

---

## Screen Development Order

1. **Design the screen** — lay out the components, decide the visual hierarchy, and confirm it matches `docs/client/design.md` before writing logic.
2. **Build the UI components** — make all components on that screen render correctly with realistic placeholder data (acceptable only at this stage, never after).
3. **Plan the API integration** — stop before wiring any API call and answer these questions:
   - Which backend endpoint(s) does this screen consume?
   - What is the exact request schema (path params, query params, request body)?
   - What does the response schema look like (reference `docs/domains/` and backend `schemas.py`)?
   - What loading, empty, and error states must the UI handle?
   - Are there any mutations? What queries must be invalidated on success?
   Document the answers briefly as a comment block at the top of the relevant `src/api/{domain}.ts` function.
4. **Wire the real API** — replace all placeholder data with live TanStack Query hooks. No mock data after this step.
5. **Write Playwright E2E tests** — see the Testing section below.
6. **Verify visually with Playwright** — see the Visual Verification section below.
7. **Fix any gaps** — iterate on both UI and integration until every test passes and the screen looks correct.

---

## API Integration Rules

- Never call `api/*` directly from a component. Data always flows through a hook (`src/hooks/use{Domain}.ts`).
- Every new API function in `src/api/{domain}.ts` must have a matching TypeScript type in `src/types/` that mirrors the backend Pydantic schema exactly. Never use `any`.
- Request and response types must be kept in sync with the backend `schemas.py`. When a backend schema changes, update `src/types/` before updating the hook or component.
- Placeholder/mock data is allowed only while the UI shell is being built (step 2 above). Once the backend endpoint exists, wire it immediately.
- Stub data in tests is acceptable — use `msw` or Playwright route interception to mock API responses in tests only.

---

## Testing Protocol

### Rule: write tests before shipping a screen

Every screen must have Playwright E2E tests **written and passing** before the screen is considered done. If you add or change a feature, write the test first, watch it fail, then implement.

### What tests must cover

For each screen, the test suite must cover:

**Request/response flows:**
- Every API call the screen makes (GET, POST, PATCH, DELETE) must be exercised by at least one test.
- Verify the correct request is sent: method, URL, query params, request body shape.
- Verify the UI reflects the correct response: data renders, mutations update the list, errors surface the right message.
- Verify every meaningful response variant: 200 with data, 200 with empty list, 4xx error, network failure.

**User journeys:**
- The golden path: the most common action a user takes on this screen.
- Edge cases specific to the screen (e.g., no transactions yet, budget at 0%, peer with zero balance).

**Auth and access:**
- Unauthenticated access redirects to `/login`.
- A 401 mid-session triggers token refresh and retries, or logs the user out.

### Test file location

```
client/tests/
└── {screen-name}/
    ├── {screen-name}.spec.ts      # main screen tests
    └── {screen-name}.api.spec.ts  # request/response contract tests
```

### Playwright network assertions

Use `page.route()` or `expect(request)` to assert what the frontend sends:

```ts
// Assert the correct request is made
const [request] = await Promise.all([
  page.waitForRequest(req => req.url().includes('/api/v1/transactions') && req.method() === 'GET'),
  page.goto('/transactions'),
])
expect(new URL(request.url()).searchParams.get('limit')).toBe('20')

// Assert the response is rendered
await expect(page.getByTestId('transaction-list')).toBeVisible()
await expect(page.getByText('Swiggy')).toBeVisible()
```

---

## Visual Verification with Playwright

After the functional tests pass, run a visual check on the screen:

1. Use `page.screenshot()` to capture the screen at mobile (390px), tablet (768px), and desktop (1280px) widths.
2. Manually review screenshots for layout issues: overflow, truncation, misaligned elements, missing states.
3. Check these specifically:
   - Empty state renders correctly (not a blank screen).
   - Loading skeletons appear before data loads.
   - Error states are visible and actionable.
   - Tap targets meet minimum 44px height.
   - Currency amounts are formatted as INR (₹ prefix, comma-separated, paise-aware).
   - Dates are formatted consistently per `lib/format.ts`.
4. Fix any issues found. Re-run screenshots after fixes.

---

## Backend Integration Checklist (per screen)

Before marking a screen as integrated, verify all of the following:

- [ ] All placeholder data removed — no hardcoded arrays or fake objects in page/component code
- [ ] Every displayed value comes from a live API response
- [ ] Loading states (skeletons or spinners) are shown while queries are in flight
- [ ] Empty states are handled explicitly (not silent blanks)
- [ ] Error states show a user-facing message, not a raw error object
- [ ] Mutations invalidate the correct query keys on success
- [ ] The screen works after a hard reload (auth bootstrap path)
- [ ] No `console.error` or unhandled promise rejections in the browser dev tools during normal use
- [ ] All Playwright tests pass against the real running backend (not mocked)

---

## No Mock Data in Production Code

Mock data belongs in tests only. Specifically:

| Location | Mock data allowed? |
|---|---|
| `src/pages/`, `src/components/` | No — never |
| `src/hooks/` | No — never |
| `src/api/` | No — never |
| `client/tests/` | Yes — via `page.route()` or fixture files |
| Storybook stories (if added) | Yes — isolated component demos |

If a backend endpoint does not exist yet, do not build the screen. Build and document the endpoint first, or agree on a contract and stub it only in tests.
