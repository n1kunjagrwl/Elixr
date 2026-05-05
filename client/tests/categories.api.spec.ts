/**
 * Contract tests for the Categories & Rules sub-page.
 */
import { test, expect } from '@playwright/test'
import { mockAuthenticated } from './helpers'

const MOCK_CATEGORIES = [
  { id: 'c1', name: 'Food & Dining', icon: '🍔', color: '#f97316', is_system: true },
  { id: 'c2', name: 'Transport', icon: '🚗', color: '#3b82f6', is_system: false },
]

const MOCK_RULES = [
  { id: 'r1', pattern: 'SWIGGY', category_id: 'c1', category_name: 'Food & Dining' },
  { id: 'r2', pattern: 'UBER', category_id: 'c2', category_name: 'Transport' },
]

async function emptySetup(page: Parameters<typeof mockAuthenticated>[0]) {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  )
}

// ── GET /categories ────────────────────────────────────────────────────────────

test('calls GET /categories on page load', async ({ page }) => {
  await emptySetup(page)

  const [request] = await Promise.all([
    page.waitForRequest(
      (req) => /\/api\/v1\/categories$/.test(new URL(req.url()).pathname) && req.method() === 'GET'
    ),
    page.goto('/more/categories'),
  ])

  expect(request.method()).toBe('GET')
})

// ── GET /categorization-rules ─────────────────────────────────────────────────

test('calls GET /categorization-rules on page load', async ({ page }) => {
  await emptySetup(page)

  const [request] = await Promise.all([
    page.waitForRequest(
      (req) =>
        /\/api\/v1\/categorization-rules$/.test(new URL(req.url()).pathname) &&
        req.method() === 'GET'
    ),
    page.goto('/more/categories'),
  ])

  expect(request.method()).toBe('GET')
})

test('renders category names from API response', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const pathname = new URL(route.request().url()).pathname
    if (/\/api\/v1\/categories$/.test(pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CATEGORIES),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/more/categories')

  await expect(page.getByTestId('category-row-c1')).toBeVisible()
  await expect(page.getByText('Food & Dining')).toBeVisible()
  await expect(page.getByTestId('category-row-c2')).toBeVisible()
  await expect(page.getByText('Transport')).toBeVisible()
})

test('renders rule patterns from API response', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const pathname = new URL(route.request().url()).pathname
    if (/\/api\/v1\/categorization-rules$/.test(pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_RULES),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/more/categories')

  await expect(page.getByTestId('rule-row-r1')).toBeVisible()
  await expect(page.getByText('SWIGGY')).toBeVisible()
  await expect(page.getByTestId('rule-row-r2')).toBeVisible()
  await expect(page.getByText('UBER')).toBeVisible()
})

test('shows empty states when API returns empty arrays', async ({ page }) => {
  await emptySetup(page)
  await page.goto('/more/categories')

  await expect(page.getByTestId('categories-empty-state')).toBeVisible()
  await expect(page.getByTestId('rules-empty-state')).toBeVisible()
})
