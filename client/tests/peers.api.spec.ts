/**
 * Contract tests for the Peers page.
 */
import { test, expect } from '@playwright/test'
import { mockAuthenticated } from './helpers'

const MOCK_PEERS = [
  { id: 'p1', name: 'Arjun Sharma', phone: null, net_balance_paise: 50000 },
  { id: 'p2', name: 'Priya Mehta', phone: null, net_balance_paise: -120000 },
]

async function emptySetup(page: Parameters<typeof mockAuthenticated>[0]) {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  )
}

// ── GET /peers ─────────────────────────────────────────────────────────────────

test('calls GET /peers on page load', async ({ page }) => {
  await emptySetup(page)

  const [request] = await Promise.all([
    page.waitForRequest(
      (req) => /\/api\/v1\/peers$/.test(new URL(req.url()).pathname) && req.method() === 'GET'
    ),
    page.goto('/peers'),
  ])

  expect(request.method()).toBe('GET')
})

test('renders peer names from API response', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (/\/api\/v1\/peers$/.test(new URL(url).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_PEERS),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/peers')

  await expect(page.getByText('Arjun Sharma')).toBeVisible()
  await expect(page.getByText('Priya Mehta')).toBeVisible()
})

test('shows empty state when API returns empty array', async ({ page }) => {
  await emptySetup(page)
  await page.goto('/peers')

  await expect(page.getByTestId('empty-state')).toBeVisible()
})

// ── POST /peers/{id}/settlements (Settle button) ───────────────────────────────

test('clicking Settle calls POST /peers/{id}/settlements', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (/\/api\/v1\/peers$/.test(new URL(url).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_PEERS),
      })
    }
    if (url.includes('/settlements')) {
      return route.fulfill({ status: 201, contentType: 'application/json', body: '{}' })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/peers')
  await page.getByTestId('peer-row-p1').waitFor()

  const [request] = await Promise.all([
    page.waitForRequest((req) => req.url().includes('/peers/p1/settlements')),
    page.getByTestId('peer-row-p1').getByRole('button', { name: 'Settle' }).click(),
  ])

  expect(request.method()).toBe('POST')
})

test('Settle button sends amount_paise equal to absolute net_balance_paise', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (/\/api\/v1\/peers$/.test(new URL(url).pathname)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_PEERS),
      })
    }
    if (url.includes('/peers/') && url.includes('/settlements')) {
      return route.fulfill({ status: 201, contentType: 'application/json', body: '{}' })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/peers')

  const [request] = await Promise.all([
    page.waitForRequest((req) => req.url().includes('/peers/p1/settlements')),
    page.getByTestId('peer-row-p1').getByRole('button', { name: 'Settle' }).click(),
  ])

  const body = JSON.parse(request.postData() ?? '{}')
  // p1 has net_balance_paise: 50000 → settle with amount 50000
  expect(body.amount_paise).toBe(50000)
})
