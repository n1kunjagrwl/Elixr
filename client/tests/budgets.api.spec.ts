/**
 * Contract tests for the Budgets sub-page.
 */
import { test, expect } from '@playwright/test'
import { mockAuthenticated } from './helpers'

const MOCK_BUDGETS = [
  { id: 'b1', category_id: 'c1', category_name: 'Food', limit_paise: 500000, period: 'monthly', current_spend_paise: 200000 },
  { id: 'b2', category_id: 'c2', category_name: 'Transport', limit_paise: 200000, period: 'monthly', current_spend_paise: 250000 },
]

async function emptySetup(page: Parameters<typeof mockAuthenticated>[0]) {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  )
}

// ── GET /budgets ───────────────────────────────────────────────────────────────

test('calls GET /budgets on page load', async ({ page }) => {
  await emptySetup(page)

  const [request] = await Promise.all([
    page.waitForRequest(
      (req) => /\/api\/v1\/budgets$/.test(new URL(req.url()).pathname) && req.method() === 'GET'
    ),
    page.goto('/more/budgets'),
  ])

  expect(request.method()).toBe('GET')
})

test('renders budget category names from API response', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    if (/\/api\/v1\/budgets$/.test(new URL(route.request().url()).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_BUDGETS),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/more/budgets')

  await expect(page.getByTestId('budget-row-b1')).toBeVisible()
  await expect(page.getByText('Food')).toBeVisible()
  await expect(page.getByTestId('budget-row-b2')).toBeVisible()
  await expect(page.getByText('Transport')).toBeVisible()
})

test('shows empty state when API returns empty array', async ({ page }) => {
  await emptySetup(page)
  await page.goto('/more/budgets')

  await expect(page.getByTestId('empty-state')).toBeVisible()
})
