/**
 * Integration tests for the Categories & Rules sub-page.
 */
import { test, expect } from '@playwright/test'
import { mockAuthenticated } from './helpers'

const MOCK_CATEGORIES = [
  { id: 'c1', name: 'Food & Dining', icon: '🍔', color: '#f97316', is_system: true },
  { id: 'c2', name: 'Transport', icon: '🚗', color: '#3b82f6', is_system: false },
  { id: 'c3', name: 'Entertainment', icon: '🎬', color: '#a855f7', is_system: false },
]

const MOCK_RULES = [
  { id: 'r1', pattern: 'SWIGGY', category_id: 'c1', category_name: 'Food & Dining' },
  { id: 'r2', pattern: 'UBER', category_id: 'c2', category_name: 'Transport' },
]

async function setupCategories(
  page: Parameters<typeof mockAuthenticated>[0],
  categories = MOCK_CATEGORIES,
  rules = MOCK_RULES
) {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const pathname = new URL(route.request().url()).pathname
    if (/\/api\/v1\/categories$/.test(pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(categories),
      })
    }
    if (/\/api\/v1\/categorization-rules$/.test(pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(rules),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
}

// ── Rendering ─────────────────────────────────────────────────────────────────

test('renders the Categories & Rules heading', async ({ page }) => {
  await setupCategories(page)
  await page.goto('/more/categories')

  await expect(page.getByRole('heading', { name: 'Categories & Rules' })).toBeVisible()
})

test('renders all category names', async ({ page }) => {
  await setupCategories(page)
  await page.goto('/more/categories')

  await expect(page.getByTestId('category-row-c1')).toBeVisible()
  await expect(page.getByTestId('category-row-c1').getByText('Food & Dining')).toBeVisible()
  await expect(page.getByTestId('category-row-c2')).toBeVisible()
  await expect(page.getByTestId('category-row-c2').getByText('Transport')).toBeVisible()
  await expect(page.getByTestId('category-row-c3')).toBeVisible()
  await expect(page.getByTestId('category-row-c3').getByText('Entertainment')).toBeVisible()
})

test('system category shows "System" label', async ({ page }) => {
  await setupCategories(page)
  await page.goto('/more/categories')

  const row = page.getByTestId('category-row-c1')
  await expect(row).toContainText('System')
})

test('renders all rule patterns', async ({ page }) => {
  await setupCategories(page)
  await page.goto('/more/categories')

  await expect(page.getByTestId('rule-row-r1')).toBeVisible()
  await expect(page.getByText('SWIGGY')).toBeVisible()
  await expect(page.getByTestId('rule-row-r2')).toBeVisible()
  await expect(page.getByText('UBER')).toBeVisible()
})

test('rule row shows category name it maps to', async ({ page }) => {
  await setupCategories(page)
  await page.goto('/more/categories')

  const row = page.getByTestId('rule-row-r1')
  await expect(row).toContainText('Food & Dining')
})

// ── Empty states ───────────────────────────────────────────────────────────────

test('shows empty state for categories when API returns empty array', async ({ page }) => {
  await setupCategories(page, [], MOCK_RULES)
  await page.goto('/more/categories')

  await expect(page.getByTestId('categories-empty-state')).toBeVisible()
  await expect(page.getByText('No custom categories yet.')).toBeVisible()
})

test('shows empty state for rules when API returns empty array', async ({ page }) => {
  await setupCategories(page, MOCK_CATEGORIES, [])
  await page.goto('/more/categories')

  await expect(page.getByTestId('rules-empty-state')).toBeVisible()
  await expect(page.getByText('No auto-tagging rules yet.')).toBeVisible()
})

// ── Navigation ─────────────────────────────────────────────────────────────────

test('back button returns to More page', async ({ page }) => {
  await setupCategories(page)
  await page.goto('/more/categories')

  await page.getByRole('button', { name: 'Back' }).click()
  await expect(page).toHaveURL('/more')
})
