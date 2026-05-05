/**
 * Integration tests for the Earnings sub-page.
 */
import { test, expect } from '@playwright/test'
import { mockAuthenticated } from './helpers'

const MOCK_EARNINGS = [
  {
    id: 'e1',
    transaction_id: null,
    source_id: null,
    source_type: 'salary',
    source_label: 'Think41 Salary',
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
    source_label: null,
    source_name: 'Acme Corp',
    amount: 50000,
    currency: 'INR',
    date: '2026-04-15',
    notes: null,
    created_at: null,
    updated_at: null,
  },
  {
    id: 'e3',
    transaction_id: null,
    source_id: null,
    source_type: 'other',
    source_label: null,
    source_name: null,
    amount: 1000,
    currency: 'INR',
    date: '2026-04-01',
    notes: null,
    created_at: null,
    updated_at: null,
  },
]

async function setupEarnings(
  page: Parameters<typeof mockAuthenticated>[0],
  earnings = MOCK_EARNINGS
) {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    if (/\/api\/v1\/earnings$/.test(new URL(route.request().url()).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(earnings),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
}

// ── Rendering ─────────────────────────────────────────────────────────────────

test('renders the Earnings heading', async ({ page }) => {
  await setupEarnings(page)
  await page.goto('/more/earnings')

  await expect(page.getByRole('heading', { name: 'Earnings' })).toBeVisible()
})

test('renders source_label as the display name when present', async ({ page }) => {
  await setupEarnings(page)
  await page.goto('/more/earnings')

  await expect(page.getByTestId('earning-row-e1')).toBeVisible()
  await expect(page.getByText('Think41 Salary')).toBeVisible()
})

test('renders source_name as the display name when source_label is null', async ({ page }) => {
  await setupEarnings(page)
  await page.goto('/more/earnings')

  await expect(page.getByTestId('earning-row-e2')).toBeVisible()
  await expect(page.getByText('Acme Corp')).toBeVisible()
})

test('falls back to source_type label when both source_label and source_name are null', async ({ page }) => {
  await setupEarnings(page)
  await page.goto('/more/earnings')

  const row = page.getByTestId('earning-row-e3')
  await expect(row).toBeVisible()
  await expect(row).toContainText('Other')
})

test('shows source_type in the row subtitle', async ({ page }) => {
  await setupEarnings(page)
  await page.goto('/more/earnings')

  const row = page.getByTestId('earning-row-e1')
  await expect(row).toContainText('Salary')
})

test('shows date in the row subtitle', async ({ page }) => {
  await setupEarnings(page)
  await page.goto('/more/earnings')

  const row = page.getByTestId('earning-row-e1')
  await expect(row).toContainText('30 Apr 2026')
})

// ── Empty state ────────────────────────────────────────────────────────────────

test('shows empty state when no earnings', async ({ page }) => {
  await setupEarnings(page, [])
  await page.goto('/more/earnings')

  await expect(page.getByTestId('empty-state')).toBeVisible()
  await expect(page.getByText('No income sources added yet.')).toBeVisible()
})

// ── Navigation ─────────────────────────────────────────────────────────────────

test('back button returns to More page', async ({ page }) => {
  await setupEarnings(page)
  await page.goto('/more/earnings')

  await page.getByRole('button', { name: 'Back' }).click()
  await expect(page).toHaveURL('/more')
})
