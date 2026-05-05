/**
 * Integration tests for the Accounts sub-page.
 */
import { test, expect } from '@playwright/test'
import { mockAuthenticated } from './helpers'

const MOCK_ACCOUNTS = [
  { id: 'a1', type: 'bank', label: 'HDFC Savings', bank_name: 'HDFC', last4: '1234', is_active: true },
  { id: 'a2', type: 'credit_card', label: 'Axis Credit', bank_name: 'Axis', last4: '5678', is_active: true },
  { id: 'a3', type: 'bank', label: 'SBI Primary', bank_name: 'SBI', last4: '9012', is_active: false },
]

async function setupAccounts(
  page: Parameters<typeof mockAuthenticated>[0],
  accounts = MOCK_ACCOUNTS
) {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    if (/\/api\/v1\/accounts$/.test(new URL(route.request().url()).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(accounts),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
}

// ── Rendering ─────────────────────────────────────────────────────────────────

test('renders the Accounts heading', async ({ page }) => {
  await setupAccounts(page)
  await page.goto('/more/accounts')

  await expect(page.getByRole('heading', { name: 'Accounts' })).toBeVisible()
})

test('renders all account labels', async ({ page }) => {
  await setupAccounts(page)
  await page.goto('/more/accounts')

  await expect(page.getByTestId('account-row-a1')).toBeVisible()
  await expect(page.getByText('HDFC Savings')).toBeVisible()
  await expect(page.getByTestId('account-row-a2')).toBeVisible()
  await expect(page.getByText('Axis Credit')).toBeVisible()
  await expect(page.getByTestId('account-row-a3')).toBeVisible()
  await expect(page.getByText('SBI Primary')).toBeVisible()
})

test('shows last4 digits masked with dots', async ({ page }) => {
  await setupAccounts(page)
  await page.goto('/more/accounts')

  const row = page.getByTestId('account-row-a1')
  await expect(row).toContainText('••••1234')
})

test('shows bank name in account row', async ({ page }) => {
  await setupAccounts(page)
  await page.goto('/more/accounts')

  const row = page.getByTestId('account-row-a1')
  await expect(row).toContainText('HDFC')
})

test('shows account type label', async ({ page }) => {
  await setupAccounts(page)
  await page.goto('/more/accounts')

  await expect(page.getByTestId('account-row-a1')).toContainText('Bank Account')
  await expect(page.getByTestId('account-row-a2')).toContainText('Credit Card')
})

// ── Empty state ────────────────────────────────────────────────────────────────

test('shows empty state when no accounts', async ({ page }) => {
  await setupAccounts(page, [])
  await page.goto('/more/accounts')

  await expect(page.getByTestId('empty-state')).toBeVisible()
  await expect(page.getByText('No accounts linked yet.')).toBeVisible()
})

// ── Navigation ─────────────────────────────────────────────────────────────────

test('back button returns to More page', async ({ page }) => {
  await setupAccounts(page)
  await page.goto('/more/accounts')

  await page.getByRole('button', { name: 'Back' }).click()
  await expect(page).toHaveURL('/more')
})
