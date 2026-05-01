import { test, expect } from '@playwright/test'
import { mockAuthenticated, mockApiEmpty } from './helpers'

test.beforeEach(async ({ page }) => {
  await mockAuthenticated(page)
  await mockApiEmpty(page)
  await page.goto('/home')
})

// ── Page renders (blank page detection) ───────────────────────────────────────

test('home page renders month/year header', async ({ page }) => {
  const month = new Date().toLocaleString('en-US', { month: 'long' })
  await expect(page.getByText(new RegExp(month))).toBeVisible()
})

test('home page shows time preset filter buttons', async ({ page }) => {
  await expect(page.getByRole('button', { name: 'This Month' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Last Month' })).toBeVisible()
  await expect(page.getByRole('button', { name: '3 Months' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'This Year' })).toBeVisible()
})

test('"This Month" preset is active by default', async ({ page }) => {
  const btn = page.getByRole('button', { name: 'This Month' })
  await expect(btn).toHaveClass(/bg-primary/)
})

test('inactive presets do not have primary background', async ({ page }) => {
  const lastMonth = page.getByRole('button', { name: 'Last Month' })
  await expect(lastMonth).not.toHaveClass(/bg-primary/)
})

test('clicking a preset changes active state', async ({ page }) => {
  await page.getByRole('button', { name: 'Last Month' }).click()
  await expect(page.getByRole('button', { name: 'Last Month' })).toHaveClass(/bg-primary/)
  await expect(page.getByRole('button', { name: 'This Month' })).not.toHaveClass(/bg-primary/)
})

// ── Widget headings visible (blank page / render failure detection) ────────────

test('Net Position widget heading is visible', async ({ page }) => {
  await expect(page.getByText('Net Position')).toBeVisible()
})

test('Spending Breakdown widget heading is visible', async ({ page }) => {
  await expect(page.getByText('Spending Breakdown')).toBeVisible()
})

test('Budgets widget heading is visible', async ({ page }) => {
  await expect(page.getByText('Budgets')).toBeVisible()
})

test('Recent Transactions widget heading is visible', async ({ page }) => {
  await expect(page.getByText('Recent Transactions')).toBeVisible()
})

// ── Widget content ─────────────────────────────────────────────────────────────

test('Net Position widget shows income and expense breakdown', async ({ page }) => {
  // Placeholder data: income ₹85K, expense ₹32K
  await expect(page.getByText('Income')).toBeVisible()
  await expect(page.getByText('Expenses')).toBeVisible()
})

test('Spending Breakdown widget shows category legend', async ({ page }) => {
  // Food & Dining appears in Spending Breakdown legend and Budget Status — match first
  await expect(page.getByText('Food & Dining').first()).toBeVisible()
  await expect(page.getByText('Transport').first()).toBeVisible()
})

test('Budgets widget shows category budget rows', async ({ page }) => {
  // Shopping appears in Spending Breakdown and Budget Status — match first
  await expect(page.getByText('Shopping').first()).toBeVisible()
})

test('attention strip shows pending review notice', async ({ page }) => {
  await expect(page.getByText(/transactions need your review/i)).toBeVisible()
})

test('"See all" link in Recent Transactions navigates to /transactions', async ({ page }) => {
  // Multiple "See all" buttons could exist — use the one inside the Recent Transactions card
  await page.getByRole('button', { name: /see all/i }).first().click()
  await expect(page).toHaveURL('/transactions')
})

// ── Cold load (direct URL navigation) ─────────────────────────────────────────

test('home page content renders on cold load (direct URL)', async ({ page }) => {
  // Navigate away and come back via direct URL to simulate page reload scenario
  await page.goto('/home')
  await expect(page.getByText('Net Position')).toBeVisible()
  await expect(page.getByText('Recent Transactions')).toBeVisible()
  await expect(page.getByText('Spending Breakdown')).toBeVisible()
})

test('home page does not show blank content area', async ({ page }) => {
  // Fail if the main scrollable area has no visible children
  const mainContent = page.locator('.space-y-3.px-4.pb-4')
  await expect(mainContent).toBeVisible()
  // At least one widget card must be present
  const cards = mainContent.locator('[class*="rounded"]')
  await expect(cards.first()).toBeVisible()
})
