/**
 * Contract tests for the Earnings sub-page.
 */
import { test, expect } from '@playwright/test'
import { mockAuthenticated } from './helpers'

const MOCK_EARNINGS = [
  {
    id: 'e1',
    transaction_id: null,
    source_id: null,
    source_type: 'salary',
    source_label: 'Think41',
    source_name: null,
    amount: 150000,
    currency: 'INR',
    date: '2026-04-30',
    notes: null,
    created_at: null,
    updated_at: null,
  },
  {
    id: 'e2',
    transaction_id: null,
    source_id: null,
    source_type: 'freelance',
    source_label: 'Acme Corp',
    source_name: null,
    amount: 50000,
    currency: 'INR',
    date: '2026-04-15',
    notes: null,
    created_at: null,
    updated_at: null,
  },
]

async function emptySetup(page: Parameters<typeof mockAuthenticated>[0]) {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  )
}

// ── GET /earnings ──────────────────────────────────────────────────────────────

test('calls GET /earnings on page load', async ({ page }) => {
  await emptySetup(page)

  const [request] = await Promise.all([
    page.waitForRequest(
      (req) => /\/api\/v1\/earnings$/.test(new URL(req.url()).pathname) && req.method() === 'GET'
    ),
    page.goto('/more/earnings'),
  ])

  expect(request.method()).toBe('GET')
})

test('renders earning source labels from API response', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    if (/\/api\/v1\/earnings$/.test(new URL(route.request().url()).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_EARNINGS),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/more/earnings')

  await expect(page.getByTestId('earning-row-e1')).toBeVisible()
  await expect(page.getByText('Think41')).toBeVisible()
  await expect(page.getByTestId('earning-row-e2')).toBeVisible()
  await expect(page.getByText('Acme Corp')).toBeVisible()
})

test('shows empty state when API returns empty array', async ({ page }) => {
  await emptySetup(page)
  await page.goto('/more/earnings')

  await expect(page.getByTestId('empty-state')).toBeVisible()
})
