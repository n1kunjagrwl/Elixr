import { test, expect } from '@playwright/test'
import { mockAuthenticated, mockApiEmpty } from './helpers'

// Each test gets a logged-in session with all API endpoints returning empty/zero data.
// This tests that the page renders correctly with no data (empty states, no crashes).
test.beforeEach(async ({ page }) => {
  await mockAuthenticated(page)
  await mockApiEmpty(page)
  await page.goto('/home')
})

// ── Page structure ─────────────────────────────────────────────────────────────

test('renders the current month and year in the header', async ({ page }) => {
  const month = new Date().toLocaleString('en-US', { month: 'long' })
  const year = new Date().getFullYear().toString()
  await expect(page.getByText(new RegExp(`${month}.*${year}`))).toBeVisible()
})

test('shows all four time preset filter buttons', async ({ page }) => {
  await expect(page.getByRole('button', { name: 'This Month' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Last Month' })).toBeVisible()
  await expect(page.getByRole('button', { name: '3 Months' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'This Year' })).toBeVisible()
})

test('"This Month" preset is active by default', async ({ page }) => {
  await expect(page.getByRole('button', { name: 'This Month' })).toHaveClass(/bg-primary/)
})

test('inactive presets do not have primary background', async ({ page }) => {
  await expect(page.getByRole('button', { name: 'Last Month' })).not.toHaveClass(/bg-primary/)
  await expect(page.getByRole('button', { name: '3 Months' })).not.toHaveClass(/bg-primary/)
})

test('clicking a preset updates active state', async ({ page }) => {
  await page.getByRole('button', { name: 'Last Month' }).click()
  await expect(page.getByRole('button', { name: 'Last Month' })).toHaveClass(/bg-primary/)
  await expect(page.getByRole('button', { name: 'This Month' })).not.toHaveClass(/bg-primary/)
})

// ── Widget headings visible ────────────────────────────────────────────────────

test('all widget headings render', async ({ page }) => {
  await expect(page.getByRole('heading', { name: 'Net Position' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Spending Breakdown' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Budgets' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Recent Transactions' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Investments' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Peer Balances' })).toBeVisible()
})

// ── Empty states (no data from API) ───────────────────────────────────────────

test('Spending Breakdown shows empty state when API returns no categories', async ({ page }) => {
  await expect(page.getByText('No spending data for this period')).toBeVisible()
})

test('Budgets widget shows empty state when API returns no budgets', async ({ page }) => {
  await expect(page.getByText('No budgets set')).toBeVisible()
})

test('Investments widget shows empty state when API returns no holdings', async ({ page }) => {
  await expect(page.getByText('No holdings added')).toBeVisible()
})

test('Peer Balances widget shows empty state when API returns no peers', async ({ page }) => {
  await expect(page.getByText('No peer balances')).toBeVisible()
})

test('attention strip is hidden when there are no unreviewed transactions or notifications', async ({ page }) => {
  await expect(page.getByTestId('attention-strip')).not.toBeVisible()
})

// ── Attention strip appears when there are unreviewed transactions ─────────────

test('attention strip shows review notice when unreviewed transactions exist', async ({ page }) => {
  // Override the unreviewed count endpoint after the catch-all empty mock
  await page.route(/\/api\/v1\/transactions\/unreviewed\/count/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ count: 5 }),
    })
  )
  await page.reload()
  await expect(page.getByTestId('attention-strip')).toBeVisible()
  await expect(page.getByText(/5 transactions need your review/i)).toBeVisible()
})

test('attention strip shows singular "transaction" for count of 1', async ({ page }) => {
  await page.route(/\/api\/v1\/transactions\/unreviewed\/count/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ count: 1 }),
    })
  )
  await page.reload()
  await expect(page.getByText(/1 transaction need your review/i)).toBeVisible()
})

test('dismissing an attention item hides it', async ({ page }) => {
  await page.route(/\/api\/v1\/transactions\/unreviewed\/count/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ count: 3 }),
    })
  )
  await page.reload()
  await page.getByLabel('Dismiss').first().click()
  await expect(page.getByTestId('attention-strip')).not.toBeVisible()
})

// ── Navigation ─────────────────────────────────────────────────────────────────

test('"See all" in Recent Transactions navigates to /transactions', async ({ page }) => {
  await page.getByRole('button', { name: /see all/i }).first().click()
  await expect(page).toHaveURL('/transactions')
})

test('"View all" in Investments navigates to /investments', async ({ page }) => {
  await page.getByRole('button', { name: /view all/i }).click()
  await expect(page).toHaveURL('/investments')
})

test('"See all" in Peer Balances navigates to /peers', async ({ page }) => {
  // Multiple "See all" buttons may exist — find the one in the Peer Balances card
  const peerCard = page.getByText('Peer Balances').locator('../..')
  await peerCard.getByRole('button', { name: /see all/i }).click()
  await expect(page).toHaveURL('/peers')
})

// ── Net Position widget labels ─────────────────────────────────────────────────

test('Net Position widget shows Income and Expenses labels', async ({ page }) => {
  await expect(page.getByText('Income')).toBeVisible()
  await expect(page.getByText('Expenses')).toBeVisible()
})

// ── Cold load ──────────────────────────────────────────────────────────────────

test('renders correctly on cold load (direct URL navigation)', async ({ page }) => {
  await page.goto('/home')
  await expect(page.getByText('Net Position')).toBeVisible()
  await expect(page.getByText('Recent Transactions')).toBeVisible()
})

test('main content area is not blank', async ({ page }) => {
  const main = page.locator('.space-y-3.px-4.pb-4')
  await expect(main).toBeVisible()
  await expect(main.locator('[class*="rounded"]').first()).toBeVisible()
})
