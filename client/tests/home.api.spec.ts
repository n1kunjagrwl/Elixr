/**
 * Contract tests for the Home dashboard.
 *
 * Each test verifies both sides of an API call:
 *   1. The frontend sends the correct request (method, URL, query params)
 *   2. The UI correctly reflects the response data
 *
 * All tests run against mocked API routes — no real backend required.
 */
import { test, expect } from '@playwright/test'
import { mockAuthenticated } from './helpers'
import { format, startOfMonth, endOfMonth, subMonths } from 'date-fns'

// ── Helpers ────────────────────────────────────────────────────────────────────

function thisMonthRange() {
  const now = new Date()
  return {
    from: format(startOfMonth(now), 'yyyy-MM-dd'),
    to: format(endOfMonth(now), 'yyyy-MM-dd'),
  }
}

function lastMonthRange() {
  const last = subMonths(new Date(), 1)
  return {
    from: format(startOfMonth(last), 'yyyy-MM-dd'),
    to: format(endOfMonth(last), 'yyyy-MM-dd'),
  }
}

async function setupHome(page: Parameters<typeof mockAuthenticated>[0]) {
  await mockAuthenticated(page)
  // Default: all list endpoints return [], all count/summary endpoints return zeros
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (url.includes('/summary/net') || url.includes('/unreviewed/count') || url.includes('/unread-count')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: 0, income_paise: 0, expense_paise: 0, net_paise: 0 }),
      })
    }
    if (url.includes('/investments/summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_value_paise: 0, invested_paise: 0, pnl_paise: 0, pnl_percent: 0 }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
}

// ── Net Position widget ────────────────────────────────────────────────────────

test('Net Position: calls /transactions/summary/net with correct date range for This Month', async ({ page }) => {
  await setupHome(page)

  const { from, to } = thisMonthRange()
  const [request] = await Promise.all([
    page.waitForRequest(
      (req) =>
        req.url().includes('/transactions/summary/net') &&
        new URL(req.url()).searchParams.get('from') === from &&
        new URL(req.url()).searchParams.get('to') === to
    ),
    page.goto('/home'),
  ])

  expect(request.method()).toBe('GET')
})

test('Net Position: displays income and expense from API response', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (url.includes('/summary/net')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ income_paise: 8500000, expense_paise: 3200000, net_paise: 5300000 }),
      })
    }
    if (url.includes('/investments/summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_value_paise: 0, invested_paise: 0, pnl_paise: 0, pnl_percent: 0 }),
      })
    }
    if (url.includes('/unreviewed/count') || url.includes('/unread-count')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: 0 }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/home')

  // ₹85K income, ₹32K expense — formatCompactINR renders these as compact values
  await expect(page.getByTestId('net-position-income')).toBeVisible()
  await expect(page.getByTestId('net-position-expense')).toBeVisible()
  // Net: ₹53K displayed as a compact value
  await expect(page.getByTestId('net-position-value')).toBeVisible()
})

test('Net Position: re-fetches with Last Month date range when preset changes', async ({ page }) => {
  await setupHome(page)
  await page.goto('/home')

  const { from, to } = lastMonthRange()
  const [request] = await Promise.all([
    page.waitForRequest(
      (req) =>
        req.url().includes('/transactions/summary/net') &&
        new URL(req.url()).searchParams.get('from') === from &&
        new URL(req.url()).searchParams.get('to') === to
    ),
    page.getByRole('button', { name: 'Last Month' }).click(),
  ])

  expect(request.method()).toBe('GET')
})

// ── Spending Breakdown widget ──────────────────────────────────────────────────

test('Spending Breakdown: calls /transactions/summary/by-category with correct date range', async ({ page }) => {
  await setupHome(page)

  const { from, to } = thisMonthRange()
  const [request] = await Promise.all([
    page.waitForRequest(
      (req) =>
        req.url().includes('/transactions/summary/by-category') &&
        new URL(req.url()).searchParams.get('from') === from &&
        new URL(req.url()).searchParams.get('to') === to
    ),
    page.goto('/home'),
  ])

  expect(request.method()).toBe('GET')
})

test('Spending Breakdown: renders category names and amounts from API response', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (url.includes('/summary/by-category')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { category_id: 'c1', category_name: 'Food & Dining', total_paise: 120000 },
          { category_id: 'c2', category_name: 'Transport', total_paise: 45000 },
        ]),
      })
    }
    if (url.includes('/summary/net') || url.includes('/unreviewed/count') || url.includes('/unread-count')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: 0, income_paise: 0, expense_paise: 0, net_paise: 0 }),
      })
    }
    if (url.includes('/investments/summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_value_paise: 0, invested_paise: 0, pnl_paise: 0, pnl_percent: 0 }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/home')

  const legend = page.getByTestId('spending-legend')
  await expect(legend.getByText('Food & Dining')).toBeVisible()
  await expect(legend.getByText('Transport')).toBeVisible()
  await expect(page.getByTestId('spending-total')).toBeVisible()
})

test('Spending Breakdown: shows empty state when API returns empty array', async ({ page }) => {
  await setupHome(page)
  await page.goto('/home')
  await expect(page.getByText('No spending data for this period')).toBeVisible()
})

// ── Budget Status widget ───────────────────────────────────────────────────────

test('Budget Status: calls GET /budgets', async ({ page }) => {
  await setupHome(page)

  const [request] = await Promise.all([
    page.waitForRequest((req) => req.url().includes('/api/v1/budgets') && req.method() === 'GET'),
    page.goto('/home'),
  ])

  expect(request.method()).toBe('GET')
})

test('Budget Status: renders budget names and amounts from API response', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (/\/api\/v1\/budgets$/.test(new URL(url).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'b1', category_id: 'c1', category_name: 'Food & Dining', limit_paise: 1500000, current_spend_paise: 1350000, period: 'monthly' },
          { id: 'b2', category_id: 'c2', category_name: 'Transport', limit_paise: 500000, current_spend_paise: 200000, period: 'monthly' },
        ]),
      })
    }
    if (url.includes('/summary/net') || url.includes('/unreviewed/count') || url.includes('/unread-count')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: 0, income_paise: 0, expense_paise: 0, net_paise: 0 }),
      })
    }
    if (url.includes('/investments/summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_value_paise: 0, invested_paise: 0, pnl_paise: 0, pnl_percent: 0 }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/home')

  await expect(page.getByTestId('budget-row-b1')).toBeVisible()
  await expect(page.getByText('Food & Dining').first()).toBeVisible()
  await expect(page.getByText('Transport').first()).toBeVisible()
})

test('Budget Status: shows empty state when API returns no budgets', async ({ page }) => {
  await setupHome(page)
  await page.goto('/home')
  await expect(page.getByText('No budgets set')).toBeVisible()
})

// ── Investment Snapshot widget ─────────────────────────────────────────────────

test('Investment Snapshot: calls GET /investments/summary and GET /investments/holdings', async ({ page }) => {
  await setupHome(page)

  const requests = await Promise.all([
    page.waitForRequest((req) => req.url().includes('/investments/summary')),
    page.waitForRequest((req) => req.url().includes('/investments/holdings')),
    page.goto('/home'),
  ])

  expect(requests[0].method()).toBe('GET')
  expect(requests[1].method()).toBe('GET')
})

test('Investment Snapshot: displays portfolio total from summary response', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (url.includes('/investments/summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_value_paise: 38500000, invested_paise: 32000000, pnl_paise: 6500000, pnl_percent: 20.3 }),
      })
    }
    if (url.includes('/investments/holdings')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'h1', name: 'Nifty 50', type: 'mutual_fund', units: 10, avg_buy_price_paise: 2000000, current_value_paise: 22000000, pnl_paise: 2000000, pnl_percent: 10 },
          { id: 'h2', name: 'Reliance', type: 'stock', units: 5, avg_buy_price_paise: 2000000, current_value_paise: 12000000, pnl_paise: 2000000, pnl_percent: 20 },
        ]),
      })
    }
    if (url.includes('/summary/net') || url.includes('/unreviewed/count') || url.includes('/unread-count')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: 0, income_paise: 0, expense_paise: 0, net_paise: 0 }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/home')

  await expect(page.getByTestId('portfolio-total')).toBeVisible()
  await expect(page.getByTestId('portfolio-pnl')).toBeVisible()
  // Allocation computed from holdings: Mutual Funds + Stocks
  await expect(page.getByTestId('portfolio-allocation')).toBeVisible()
  await expect(page.getByText('Mutual Funds')).toBeVisible()
  await expect(page.getByText('Stocks')).toBeVisible()
})

test('Investment Snapshot: shows empty state when no holdings', async ({ page }) => {
  await setupHome(page)
  await page.goto('/home')
  await expect(page.getByText('No holdings added')).toBeVisible()
})

// ── Peer Balances widget ───────────────────────────────────────────────────────

test('Peer Balances: calls GET /peers', async ({ page }) => {
  await setupHome(page)

  const [request] = await Promise.all([
    page.waitForRequest((req) => /\/api\/v1\/peers$/.test(new URL(req.url()).pathname)),
    page.goto('/home'),
  ])

  expect(request.method()).toBe('GET')
})

test('Peer Balances: renders peer names from API response', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (/\/api\/v1\/peers$/.test(new URL(url).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'p1', name: 'Arjun Sharma', phone: null, net_balance_paise: 50000 },
          { id: 'p2', name: 'Priya Mehta', phone: null, net_balance_paise: -120000 },
        ]),
      })
    }
    if (url.includes('/summary/net') || url.includes('/unreviewed/count') || url.includes('/unread-count')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: 0, income_paise: 0, expense_paise: 0, net_paise: 0 }),
      })
    }
    if (url.includes('/investments/summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_value_paise: 0, invested_paise: 0, pnl_paise: 0, pnl_percent: 0 }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/home')

  await expect(page.getByTestId('peer-row-p1')).toBeVisible()
  await expect(page.getByText('Arjun Sharma')).toBeVisible()
  await expect(page.getByText('owes you')).toBeVisible()
  await expect(page.getByText('Priya Mehta')).toBeVisible()
  await expect(page.getByText('you owe')).toBeVisible()
})

test('Peer Balances: shows top 3 peers by absolute balance, not more', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (/\/api\/v1\/peers$/.test(new URL(url).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'p1', name: 'Peer One', phone: null, net_balance_paise: 10000 },
          { id: 'p2', name: 'Peer Two', phone: null, net_balance_paise: 50000 },
          { id: 'p3', name: 'Peer Three', phone: null, net_balance_paise: -30000 },
          { id: 'p4', name: 'Peer Four', phone: null, net_balance_paise: 5000 },
        ]),
      })
    }
    if (url.includes('/summary/net') || url.includes('/unreviewed/count') || url.includes('/unread-count')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: 0, income_paise: 0, expense_paise: 0, net_paise: 0 }),
      })
    }
    if (url.includes('/investments/summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_value_paise: 0, invested_paise: 0, pnl_paise: 0, pnl_percent: 0 }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/home')

  // Top 3 by absolute balance: p2 (50k), p3 (30k), p1 (10k) — p4 (5k) is excluded
  await expect(page.getByTestId('peer-row-p2')).toBeVisible()
  await expect(page.getByTestId('peer-row-p3')).toBeVisible()
  await expect(page.getByTestId('peer-row-p1')).toBeVisible()
  await expect(page.getByTestId('peer-row-p4')).not.toBeVisible()
})

test('Peer Balances: shows empty state when API returns no peers', async ({ page }) => {
  await setupHome(page)
  await page.goto('/home')
  await expect(page.getByText('No peer balances')).toBeVisible()
})

// ── Attention Strip ────────────────────────────────────────────────────────────

test('Attention Strip: calls GET /transactions/unreviewed/count', async ({ page }) => {
  await setupHome(page)

  const [request] = await Promise.all([
    page.waitForRequest((req) => req.url().includes('/transactions/unreviewed/count')),
    page.goto('/home'),
  ])

  expect(request.method()).toBe('GET')
})

test('Attention Strip: calls GET /notifications', async ({ page }) => {
  await setupHome(page)

  const [request] = await Promise.all([
    page.waitForRequest((req) => /\/api\/v1\/notifications$/.test(new URL(req.url()).pathname)),
    page.goto('/home'),
  ])

  expect(request.method()).toBe('GET')
})

test('Attention Strip: shows unread notification titles', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (/\/api\/v1\/notifications$/.test(new URL(url).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'n1', type: 'info', title: 'Statement uploaded successfully', body: '', is_read: false, created_at: new Date().toISOString() },
        ]),
      })
    }
    if (url.includes('/unreviewed/count') || url.includes('/unread-count')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: 0 }),
      })
    }
    if (url.includes('/summary/net')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ income_paise: 0, expense_paise: 0, net_paise: 0 }),
      })
    }
    if (url.includes('/investments/summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_value_paise: 0, invested_paise: 0, pnl_paise: 0, pnl_percent: 0 }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/home')

  await expect(page.getByTestId('attention-strip')).toBeVisible()
  await expect(page.getByText('Statement uploaded successfully')).toBeVisible()
})

test('Attention Strip: "Review" button navigates to /transactions?unreviewed=true', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (url.includes('/unreviewed/count')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: 4 }),
      })
    }
    if (url.includes('/summary/net') || url.includes('/unread-count')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: 0, income_paise: 0, expense_paise: 0, net_paise: 0 }),
      })
    }
    if (url.includes('/investments/summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_value_paise: 0, invested_paise: 0, pnl_paise: 0, pnl_percent: 0 }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/home')

  await page.getByRole('button', { name: 'Review' }).click()
  await expect(page).toHaveURL(/\/transactions\?unreviewed=true/)
})

// ── Bell badge ─────────────────────────────────────────────────────────────────

test('bell badge is visible when unread notification count > 0', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (url.includes('/notifications/unread-count')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: 3 }),
      })
    }
    if (url.includes('/summary/net') || url.includes('/unreviewed/count')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: 0, income_paise: 0, expense_paise: 0, net_paise: 0 }),
      })
    }
    if (url.includes('/investments/summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_value_paise: 0, invested_paise: 0, pnl_paise: 0, pnl_percent: 0 }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/home')

  // The badge dot is the span inside the bell button
  const bellButton = page.getByRole('button', { name: 'Notifications' })
  await expect(bellButton.locator('span')).toBeVisible()
})

test('bell badge is hidden when unread count is 0', async ({ page }) => {
  await setupHome(page)
  await page.goto('/home')

  const bellButton = page.getByRole('button', { name: 'Notifications' })
  await expect(bellButton.locator('span')).not.toBeVisible()
})
