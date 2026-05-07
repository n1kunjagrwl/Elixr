/**
 * Contract tests for the Transactions page.
 * Verifies the correct requests are sent to the backend and the UI
 * correctly reflects each response variant.
 */
import { test, expect } from '@playwright/test'
import { mockAuthenticated } from './helpers'

// Backend format — mapTransaction() transforms these into the frontend Transaction type
const BASE_TRANSACTIONS = [
  { id: 't1', account_id: 'a1', account_kind: 'bank', account_name: 'HDFC', date: new Date().toISOString(), raw_description: 'Swiggy Order', amount: '450.00', currency: 'INR', type: 'debit', source: 'manual', notes: null, primary_category_id: 'c-food', primary_category_name: 'Food & Dining', primary_category_icon: '🍔', created_at: null, updated_at: null },
  { id: 't2', account_id: 'a1', account_kind: 'bank', account_name: 'HDFC', date: new Date().toISOString(), raw_description: 'Uber Ride', amount: '180.00', currency: 'INR', type: 'debit', source: 'manual', notes: null, primary_category_id: null, primary_category_name: null, primary_category_icon: null, created_at: null, updated_at: null },
]

const BASE_CATEGORIES = [
  { id: 'c-food', name: 'Food & Dining', icon: '🍔', color: '#f97316', is_system: true },
  { id: 'c-transport', name: 'Transport', icon: '🚗', color: '#3b82f6', is_system: true },
]

// ── GET /transactions ──────────────────────────────────────────────────────────

test('calls GET /transactions on page load', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })

  const [request] = await Promise.all([
    page.waitForRequest(
      (req) => /\/api\/v1\/transactions$/.test(new URL(req.url()).pathname) && req.method() === 'GET'
    ),
    page.goto('/transactions'),
  ])

  expect(request.method()).toBe('GET')
})

test('GET /transactions includes page_size=50 query param', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })

  const [request] = await Promise.all([
    page.waitForRequest((req) => /\/api\/v1\/transactions$/.test(new URL(req.url()).pathname)),
    page.goto('/transactions'),
  ])

  expect(new URL(request.url()).searchParams.get('page_size')).toBe('50')
})

test('calls GET /categories on page load', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })

  const [request] = await Promise.all([
    page.waitForRequest((req) => /\/api\/v1\/categories$/.test(new URL(req.url()).pathname)),
    page.goto('/transactions'),
  ])

  expect(request.method()).toBe('GET')
})

// ── Category filter sends category_id to API ───────────────────────────────────

test('selecting a category chip adds category_id to the transactions request', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (/\/api\/v1\/categories$/.test(new URL(url).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(BASE_CATEGORIES),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/transactions')

  // Wait for category chips to appear before clicking
  await page.getByRole('button', { name: 'Food & Dining' }).waitFor()

  const [request] = await Promise.all([
    page.waitForRequest(
      (req) =>
        /\/api\/v1\/transactions$/.test(new URL(req.url()).pathname) &&
        new URL(req.url()).searchParams.get('category_id') === 'c-food'
    ),
    page.getByRole('button', { name: 'Food & Dining' }).click(),
  ])

  expect(new URL(request.url()).searchParams.get('category_id')).toBe('c-food')
})

test('clicking "All" chip makes it the active chip and deactivates the selected category', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (/\/api\/v1\/categories$/.test(new URL(url).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(BASE_CATEGORIES),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/transactions')

  await page.getByRole('button', { name: 'Food & Dining' }).waitFor()
  await page.getByRole('button', { name: 'Food & Dining' }).click()
  await expect(page.getByRole('button', { name: 'Food & Dining' })).toHaveClass(/bg-primary/)

  await page.getByRole('button', { name: 'All' }).click()
  await expect(page.getByRole('button', { name: 'All' })).toHaveClass(/bg-primary/)
  await expect(page.getByRole('button', { name: 'Food & Dining' })).not.toHaveClass(/bg-primary/)
})

// ── Unreviewed filter ──────────────────────────────────────────────────────────

test('?unreviewed=true URL param sends unreviewed=true to the API', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })

  const [request] = await Promise.all([
    page.waitForRequest(
      (req) =>
        /\/api\/v1\/transactions$/.test(new URL(req.url()).pathname) &&
        new URL(req.url()).searchParams.get('unreviewed') === 'true'
    ),
    page.goto('/transactions?unreviewed=true'),
  ])

  expect(new URL(request.url()).searchParams.get('unreviewed')).toBe('true')
})

// ── Response data rendered ─────────────────────────────────────────────────────

test('renders transaction description and formatted amount from API response', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (/\/api\/v1\/transactions$/.test(new URL(url).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'tx-a', account_id: 'a1', account_kind: 'bank', account_name: 'HDFC', date: new Date().toISOString(), raw_description: 'Zomato Delivery', amount: '380.00', currency: 'INR', type: 'debit', source: 'manual', notes: null, primary_category_id: 'c-food', primary_category_name: 'Food & Dining', primary_category_icon: '🍕', created_at: null, updated_at: null },
        ]),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/transactions')

  await expect(page.getByTestId('tx-row-tx-a')).toBeVisible()
  await expect(page.getByText('Zomato Delivery')).toBeVisible()
  await expect(page.getByText(/₹380/)).toBeVisible()
})

test('handles paginated response envelope { items: [...] }', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (/\/api\/v1\/transactions$/.test(new URL(url).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [
            { id: 'tx-p', account_id: 'a1', account_kind: 'bank', account_name: 'HDFC', date: new Date().toISOString(), raw_description: 'Paginated TX', amount: '100.00', currency: 'INR', type: 'debit', source: 'manual', notes: null, primary_category_id: null, primary_category_name: null, primary_category_icon: null, created_at: null, updated_at: null },
          ],
          total: 1,
          page: 1,
          page_size: 50,
        }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/transactions')

  // API client unwraps paginated envelopes — the page should render the item
  await expect(page.getByTestId('tx-row-tx-p')).toBeVisible()
  await expect(page.getByText('Paginated TX')).toBeVisible()
})

test('shows empty state when API returns empty array', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/transactions')

  await expect(page.getByTestId('empty-state')).toBeVisible()
  await expect(page.getByText('No transactions yet')).toBeVisible()
})

test('shows "No transactions found" after text search with no results', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (/\/api\/v1\/transactions$/.test(new URL(url).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(BASE_TRANSACTIONS),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/transactions')
  await page.getByTestId('search-input').fill('xyzNothingMatchesThis')

  await expect(page.getByText('No transactions found')).toBeVisible()
})
