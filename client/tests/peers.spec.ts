/**
 * Integration tests for the Peers page.
 */
import { test, expect } from '@playwright/test'
import { mockAuthenticated } from './helpers'

const MOCK_PEERS = [
  { id: 'p1', name: 'Arjun Sharma', phone: null, net_balance_paise: 50000 },
  { id: 'p2', name: 'Priya Mehta', phone: null, net_balance_paise: -120000 },
  { id: 'p3', name: 'Ravi Kumar', phone: null, net_balance_paise: 35000 },
  { id: 'p4', name: 'Sneha Patel', phone: null, net_balance_paise: 0 },
]

async function setupPeers(
  page: Parameters<typeof mockAuthenticated>[0],
  peers = MOCK_PEERS
) {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (/\/api\/v1\/peers$/.test(new URL(url).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(peers),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
}

// ── Rendering ─────────────────────────────────────────────────────────────────

test('renders all peer names from API response', async ({ page }) => {
  await setupPeers(page)
  await page.goto('/peers')

  await expect(page.getByTestId('peer-row-p1')).toBeVisible()
  await expect(page.getByText('Arjun Sharma')).toBeVisible()
  await expect(page.getByTestId('peer-row-p2')).toBeVisible()
  await expect(page.getByText('Priya Mehta')).toBeVisible()
  await expect(page.getByTestId('peer-row-p3')).toBeVisible()
  await expect(page.getByText('Ravi Kumar')).toBeVisible()
})

test('computes initials from peer name (first letters of each word)', async ({ page }) => {
  await setupPeers(page)
  await page.goto('/peers')

  const arjunRow = page.getByTestId('peer-row-p1')
  await expect(arjunRow.getByText('AS')).toBeVisible()

  const priyaRow = page.getByTestId('peer-row-p2')
  await expect(priyaRow.getByText('PM')).toBeVisible()
})

// ── Summary cards ──────────────────────────────────────────────────────────────

test('summary cards show totals computed from API response', async ({ page }) => {
  await setupPeers(page)
  await page.goto('/peers')

  // totalOwedToYou = p1 (50000) + p3 (35000) = 85000 paise = ₹850
  await expect(page.getByTestId('owed-to-you')).toBeVisible()
  // totalYouOwe = p2 (120000) paise = ₹1,200
  await expect(page.getByTestId('you-owe')).toBeVisible()
})

test('summary totals are zero when all peers are settled', async ({ page }) => {
  await setupPeers(page, [
    { id: 'px', name: 'Zero Balance', phone: null, net_balance_paise: 0 },
  ])
  await page.goto('/peers')

  await expect(page.getByTestId('owed-to-you')).toContainText('₹0')
  await expect(page.getByTestId('you-owe')).toContainText('₹0')
})

// ── Peer row states ────────────────────────────────────────────────────────────

test('peer with positive balance shows "Owes you" label and green amount', async ({ page }) => {
  await setupPeers(page)
  await page.goto('/peers')

  const row = page.getByTestId('peer-row-p1')
  await expect(row.getByText('Owes you')).toBeVisible()
  // Amount should be green
  const amountEl = row.locator('.text-green-600, .text-green-400').first()
  await expect(amountEl).toBeVisible()
})

test('peer with negative balance shows "You owe" label', async ({ page }) => {
  await setupPeers(page)
  await page.goto('/peers')

  const row = page.getByTestId('peer-row-p2')
  await expect(row.getByText('You owe')).toBeVisible()
})

test('peer with zero balance shows "All settled" and no Settle button', async ({ page }) => {
  await setupPeers(page)
  await page.goto('/peers')

  const row = page.getByTestId('peer-row-p4')
  await expect(row.getByText('All settled')).toBeVisible()
  await expect(row.getByRole('button', { name: 'Settle' })).not.toBeVisible()
})

test('peer with non-zero balance shows Settle button', async ({ page }) => {
  await setupPeers(page)
  await page.goto('/peers')

  const row = page.getByTestId('peer-row-p1')
  await expect(row.getByRole('button', { name: 'Settle' })).toBeVisible()
})

// ── Empty state ────────────────────────────────────────────────────────────────

test('shows empty state when API returns no peers', async ({ page }) => {
  await setupPeers(page, [])
  await page.goto('/peers')

  await expect(page.getByTestId('empty-state')).toBeVisible()
  await expect(page.getByText('No peers added yet')).toBeVisible()
})
