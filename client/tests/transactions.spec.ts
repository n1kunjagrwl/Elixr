/**
 * Integration tests for the Transactions page.
 * All tests mock the API — no real backend required.
 */
import { test, expect } from '@playwright/test'
import { mockAuthenticated } from './helpers'

const MOCK_CATEGORIES = [
  { id: 'c-food', name: 'Food & Dining', icon: '🍔', color: '#f97316', is_system: true },
  { id: 'c-transport', name: 'Transport', icon: '🚗', color: '#3b82f6', is_system: true },
  { id: 'c-salary', name: 'Salary', icon: '💼', color: '#22c55e', is_system: true },
]

const MOCK_TRANSACTIONS = [
  { id: 't1', account_id: 'a1', account_label: 'HDFC', date: new Date().toISOString(), description: 'Swiggy Order', amount_paise: -45000, category_id: 'c-food', category_name: 'Food & Dining', category_icon: '🍔', is_reviewed: true },
  { id: 't2', account_id: 'a1', account_label: 'HDFC', date: new Date().toISOString(), description: 'Salary — Think41', amount_paise: 8500000, category_id: 'c-salary', category_name: 'Salary', category_icon: '💼', is_reviewed: true },
  { id: 't3', account_id: 'a1', account_label: 'HDFC', date: new Date().toISOString(), description: 'Uber Ride', amount_paise: -18000, category_id: 'c-transport', category_name: 'Transport', category_icon: '🚗', is_reviewed: false },
]

async function setupTransactions(page: Parameters<typeof mockAuthenticated>[0], options: {
  transactions?: typeof MOCK_TRANSACTIONS
  categories?: typeof MOCK_CATEGORIES
} = {}) {
  await mockAuthenticated(page)
  const transactions = options.transactions ?? MOCK_TRANSACTIONS
  const categories = options.categories ?? MOCK_CATEGORIES

  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    const pathname = new URL(url).pathname

    if (/\/api\/v1\/transactions$/.test(pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(transactions),
      })
    }
    if (/\/api\/v1\/categories$/.test(pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(categories),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
}

// ── Rendering with data ────────────────────────────────────────────────────────

test('renders transaction list from API response', async ({ page }) => {
  await setupTransactions(page)
  await page.goto('/transactions')

  await expect(page.getByTestId('tx-row-t1')).toBeVisible()
  await expect(page.getByText('Swiggy Order')).toBeVisible()
  await expect(page.getByTestId('tx-row-t2')).toBeVisible()
  await expect(page.getByText('Salary — Think41')).toBeVisible()
  await expect(page.getByTestId('tx-row-t3')).toBeVisible()
  await expect(page.getByText('Uber Ride')).toBeVisible()
})

test('shows category name and formatted amount per transaction', async ({ page }) => {
  await setupTransactions(page)
  await page.goto('/transactions')

  const swiggyRow = page.getByTestId('tx-row-t1')
  await expect(swiggyRow.getByText('Food & Dining')).toBeVisible()
  // amount: −₹450 (45000 paise)
  await expect(swiggyRow.getByText(/₹450/)).toBeVisible()
})

test('credit transactions show positive green amount', async ({ page }) => {
  await setupTransactions(page)
  await page.goto('/transactions')

  const salaryRow = page.getByTestId('tx-row-t2')
  // amount: +₹85K
  await expect(salaryRow.getByText(/\+/)).toBeVisible()
  const amountEl = salaryRow.locator('.text-green-600, .text-green-400').first()
  await expect(amountEl).toBeVisible()
})

test('unreviewed transaction shows "Review" badge', async ({ page }) => {
  await setupTransactions(page)
  await page.goto('/transactions')

  const uberRow = page.getByTestId('tx-row-t3')
  await expect(uberRow.getByText('Review')).toBeVisible()
})

test('reviewed transactions do not show "Review" badge', async ({ page }) => {
  await setupTransactions(page)
  await page.goto('/transactions')

  const swiggyRow = page.getByTestId('tx-row-t1')
  await expect(swiggyRow.getByText('Review')).not.toBeVisible()
})

// ── Category chips from API ────────────────────────────────────────────────────

test('shows category chips from API response', async ({ page }) => {
  await setupTransactions(page)
  await page.goto('/transactions')

  await expect(page.getByRole('button', { name: 'All' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Food & Dining' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Transport' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Salary' })).toBeVisible()
})

test('"All" chip is active by default; selected category chip becomes active', async ({ page }) => {
  await setupTransactions(page)
  await page.goto('/transactions')

  await expect(page.getByRole('button', { name: 'All' })).toHaveClass(/bg-primary/)
  await page.getByRole('button', { name: 'Food & Dining' }).click()
  await expect(page.getByRole('button', { name: 'Food & Dining' })).toHaveClass(/bg-primary/)
  await expect(page.getByRole('button', { name: 'All' })).not.toHaveClass(/bg-primary/)
})

// ── Search (client-side) ───────────────────────────────────────────────────────

test('search input filters transactions client-side by description', async ({ page }) => {
  await setupTransactions(page)
  await page.goto('/transactions')

  await page.getByTestId('search-input').fill('Salary')
  await expect(page.getByTestId('tx-row-t2')).toBeVisible()
  await expect(page.getByTestId('tx-row-t1')).not.toBeVisible()
  await expect(page.getByTestId('tx-row-t3')).not.toBeVisible()
})

test('search is case-insensitive', async ({ page }) => {
  await setupTransactions(page)
  await page.goto('/transactions')

  await page.getByTestId('search-input').fill('swiggy')
  await expect(page.getByTestId('tx-row-t1')).toBeVisible()
  await expect(page.getByTestId('tx-row-t2')).not.toBeVisible()
})

test('non-matching search shows "No transactions found"', async ({ page }) => {
  await setupTransactions(page)
  await page.goto('/transactions')

  await page.getByTestId('search-input').fill('zzznomatch')
  await expect(page.getByTestId('empty-state')).toBeVisible()
  await expect(page.getByText('No transactions found')).toBeVisible()
})

test('clear search button resets the list', async ({ page }) => {
  await setupTransactions(page)
  await page.goto('/transactions')

  await page.getByTestId('search-input').fill('Salary')
  await expect(page.getByTestId('tx-row-t1')).not.toBeVisible()
  await page.getByLabel('Clear search').click()
  await expect(page.getByTestId('tx-row-t1')).toBeVisible()
})

// ── Unreviewed filter from URL ─────────────────────────────────────────────────

test('?unreviewed=true URL param shows "Needs review" filter badge', async ({ page }) => {
  await setupTransactions(page)
  await page.goto('/transactions?unreviewed=true')

  await expect(page.getByTestId('unreviewed-filter-badge')).toBeVisible()
  await expect(page.getByText('Needs review')).toBeVisible()
})

test('clearing the unreviewed filter badge removes it and clears the URL param', async ({ page }) => {
  await setupTransactions(page)
  await page.goto('/transactions?unreviewed=true')

  await expect(page.getByTestId('unreviewed-filter-badge')).toBeVisible()
  await page.getByLabel('Clear unreviewed filter').click()
  await expect(page.getByTestId('unreviewed-filter-badge')).not.toBeVisible()
  await expect(page).not.toHaveURL(/unreviewed/)
})

// ── Empty states ───────────────────────────────────────────────────────────────

test('shows "No transactions yet" when API returns empty list with no filters', async ({ page }) => {
  await setupTransactions(page, { transactions: [] })
  await page.goto('/transactions')

  await expect(page.getByText('No transactions yet')).toBeVisible()
})
