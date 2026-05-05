/**
 * Integration tests for the Budgets sub-page.
 */
import { test, expect } from '@playwright/test'
import { mockAuthenticated } from './helpers'

const MOCK_BUDGETS = [
  { id: 'b1', category_id: 'c1', category_name: 'Food', limit_paise: 500000, period: 'monthly', current_spend_paise: 200000 },
  { id: 'b2', category_id: 'c2', category_name: 'Transport', limit_paise: 200000, period: 'monthly', current_spend_paise: 250000 },
  { id: 'b3', category_id: 'c3', category_name: 'Entertainment', limit_paise: 100000, period: 'weekly', current_spend_paise: 0 },
]

async function setupBudgets(
  page: Parameters<typeof mockAuthenticated>[0],
  budgets = MOCK_BUDGETS
) {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    if (/\/api\/v1\/budgets$/.test(new URL(route.request().url()).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(budgets),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
}

// ── Rendering ─────────────────────────────────────────────────────────────────

test('renders the Budgets heading', async ({ page }) => {
  await setupBudgets(page)
  await page.goto('/more/budgets')

  await expect(page.getByRole('heading', { name: 'Budgets' })).toBeVisible()
})

test('renders all budget category names', async ({ page }) => {
  await setupBudgets(page)
  await page.goto('/more/budgets')

  await expect(page.getByTestId('budget-row-b1')).toBeVisible()
  await expect(page.getByText('Food')).toBeVisible()
  await expect(page.getByTestId('budget-row-b2')).toBeVisible()
  await expect(page.getByText('Transport')).toBeVisible()
  await expect(page.getByTestId('budget-row-b3')).toBeVisible()
  await expect(page.getByText('Entertainment')).toBeVisible()
})

test('shows period label on budget row', async ({ page }) => {
  await setupBudgets(page)
  await page.goto('/more/budgets')

  await expect(page.getByTestId('budget-row-b3')).toContainText('weekly')
})

test('over-budget bar uses destructive color class', async ({ page }) => {
  await setupBudgets(page)
  await page.goto('/more/budgets')

  // b2: current_spend 250000 > limit 200000 → over budget
  const bar = page.getByTestId('budget-bar-b2')
  await expect(bar).toBeVisible()
  await expect(bar).toHaveClass(/bg-destructive/)
})

test('under-budget bar uses primary color class', async ({ page }) => {
  await setupBudgets(page)
  await page.goto('/more/budgets')

  // b1: current_spend 200000 < limit 500000 → under budget
  const bar = page.getByTestId('budget-bar-b1')
  await expect(bar).toBeVisible()
  await expect(bar).toHaveClass(/bg-primary/)
})

// ── Empty state ────────────────────────────────────────────────────────────────

test('shows empty state when no budgets', async ({ page }) => {
  await setupBudgets(page, [])
  await page.goto('/more/budgets')

  await expect(page.getByTestId('empty-state')).toBeVisible()
  await expect(page.getByText('No budgets set yet.')).toBeVisible()
})

// ── Navigation ─────────────────────────────────────────────────────────────────

test('back button returns to More page', async ({ page }) => {
  await setupBudgets(page)
  await page.goto('/more/budgets')

  await page.getByRole('button', { name: 'Back' }).click()
  await expect(page).toHaveURL('/more')
})
