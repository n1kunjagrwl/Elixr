/**
 * Contract tests for the Accounts sub-page.
 */
import { test, expect } from '@playwright/test'
import { mockAuthenticated } from './helpers'

const MOCK_ACCOUNTS = [
  { id: 'a1', type: 'bank', label: 'HDFC Savings', bank_name: 'HDFC', last4: '1234', is_active: true },
  { id: 'a2', type: 'credit_card', label: 'Axis Credit', bank_name: 'Axis', last4: '5678', is_active: true },
]

async function emptySetup(page: Parameters<typeof mockAuthenticated>[0]) {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  )
}

// ── GET /accounts ──────────────────────────────────────────────────────────────

test('calls GET /accounts on page load', async ({ page }) => {
  await emptySetup(page)

  const [request] = await Promise.all([
    page.waitForRequest(
      (req) => /\/api\/v1\/accounts$/.test(new URL(req.url()).pathname) && req.method() === 'GET'
    ),
    page.goto('/more/accounts'),
  ])

  expect(request.method()).toBe('GET')
})

test('renders account labels from API response', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    if (/\/api\/v1\/accounts$/.test(new URL(route.request().url()).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_ACCOUNTS),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/more/accounts')

  await expect(page.getByText('HDFC Savings')).toBeVisible()
  await expect(page.getByText('Axis Credit')).toBeVisible()
})

test('shows empty state when API returns empty array', async ({ page }) => {
  await emptySetup(page)
  await page.goto('/more/accounts')

  await expect(page.getByTestId('empty-state')).toBeVisible()
})
