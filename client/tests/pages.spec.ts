/**
 * Content-level tests for each tab page.
 * Each test navigates directly to the page and asserts that meaningful
 * content is visible — catching blank page regressions immediately.
 */
import { test, expect } from '@playwright/test'
import { mockAuthenticated, mockApiEmpty } from './helpers'

test.beforeEach(async ({ page }) => {
  await mockAuthenticated(page)
  await mockApiEmpty(page)
})

// ── Transactions page ──────────────────────────────────────────────────────────

test.describe('Transactions page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/transactions')
  })

  test('renders "Transactions" heading', async ({ page }) => {
    await expect(page.getByText('Transactions')).toBeVisible()
  })

  test('shows search input', async ({ page }) => {
    await expect(page.getByPlaceholder('Search transactions…')).toBeVisible()
  })

  test('"All" category chip is always present and active by default', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'All' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'All' })).toHaveClass(/bg-primary/)
  })

  test('shows empty state when API returns no transactions', async ({ page }) => {
    await expect(page.getByTestId('empty-state')).toBeVisible()
    await expect(page.getByText('No transactions yet')).toBeVisible()
  })

  test('empty search shows "No transactions found" when there is a search term', async ({ page }) => {
    await page.getByPlaceholder('Search transactions…').fill('zzznomatch')
    await expect(page.getByText('No transactions found')).toBeVisible()
  })

  test('does not show blank page on cold direct URL load', async ({ page }) => {
    await page.goto('/transactions')
    await expect(page.getByText('Transactions')).toBeVisible()
    await expect(page.getByTestId('category-chips')).toBeVisible()
  })
})

// ── Investments page ───────────────────────────────────────────────────────────

test.describe('Investments page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/investments')
  })

  test('renders "Investments" heading', async ({ page }) => {
    await expect(page.getByText('Investments')).toBeVisible()
  })

  test('shows Portfolio Value section', async ({ page }) => {
    await expect(page.getByText('Portfolio Value')).toBeVisible()
  })

  test('shows Holdings, SIPs, FDs tabs', async ({ page }) => {
    await expect(page.getByRole('tab', { name: 'Holdings' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'SIPs' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'FDs' })).toBeVisible()
  })

  test('Holdings tab shows empty state when API returns no holdings', async ({ page }) => {
    await expect(page.getByText('No holdings added')).toBeVisible()
  })

  test('switching to SIPs tab shows empty state when API returns no SIPs', async ({ page }) => {
    await page.getByRole('tab', { name: 'SIPs' }).click()
    await expect(page.getByText('No active SIPs')).toBeVisible()
  })

  test('switching to FDs tab shows empty state when API returns no FDs', async ({ page }) => {
    await page.getByRole('tab', { name: 'FDs' }).click()
    await expect(page.getByText('No fixed deposits')).toBeVisible()
  })

  test('does not show blank page on cold direct URL load', async ({ page }) => {
    await page.goto('/investments')
    await expect(page.getByText('Investments')).toBeVisible()
    await expect(page.getByText('Portfolio Value')).toBeVisible()
  })
})

// ── Peers page ─────────────────────────────────────────────────────────────────

test.describe('Peers page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/peers')
  })

  test('renders "Peers" heading', async ({ page }) => {
    await expect(page.getByText('Peers')).toBeVisible()
  })

  test('shows "Owed to you" and "You owe" summary cards', async ({ page }) => {
    await expect(page.getByText('Owed to you')).toBeVisible()
    // "You owe" appears in the summary card and in peer row labels — match first
    await expect(page.getByText('You owe').first()).toBeVisible()
  })

  test('shows peer list with names', async ({ page }) => {
    await expect(page.getByText('Arjun Sharma')).toBeVisible()
    await expect(page.getByText('Priya Mehta')).toBeVisible()
    await expect(page.getByText('Ravi Kumar')).toBeVisible()
  })

  test('shows settle button for peers with non-zero balance', async ({ page }) => {
    const settleButtons = page.getByRole('button', { name: 'Settle' })
    await expect(settleButtons.first()).toBeVisible()
  })

  test('settled peer shows "All settled" label', async ({ page }) => {
    await expect(page.getByText('All settled')).toBeVisible()
  })

  test('does not show blank page on cold direct URL load', async ({ page }) => {
    await page.goto('/peers')
    await expect(page.getByText('Peers')).toBeVisible()
    await expect(page.getByText('Arjun Sharma')).toBeVisible()
  })
})

// ── More page ──────────────────────────────────────────────────────────────────

test.describe('More page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/more')
  })

  test('renders "More" heading', async ({ page }) => {
    await expect(page.getByText('More')).toBeVisible()
  })

  test('shows all menu section items', async ({ page }) => {
    await expect(page.getByText('Budgets')).toBeVisible()
    await expect(page.getByText('Earnings')).toBeVisible()
    // Use exact:true — "Accounts" is case-insensitively substring-matched by default,
    // which also matches "Bank accounts and credit cards" in the description.
    await expect(page.getByText('Accounts', { exact: true })).toBeVisible()
    await expect(page.getByText('Categories & Rules')).toBeVisible()
    await expect(page.getByText('Settings')).toBeVisible()
  })

  test('shows menu item descriptions', async ({ page }) => {
    await expect(page.getByText('Set and track spending limits')).toBeVisible()
    await expect(page.getByText('Appearance, dashboard, notifications')).toBeVisible()
  })

  test('does not show blank page on cold direct URL load', async ({ page }) => {
    await page.goto('/more')
    await expect(page.getByText('More')).toBeVisible()
    await expect(page.getByText('Budgets')).toBeVisible()
  })
})
