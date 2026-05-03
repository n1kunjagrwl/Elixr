/**
 * Contract tests for the Investments page.
 * Verifies correct API calls are made and responses are rendered.
 */
import { test, expect } from '@playwright/test'
import { mockAuthenticated } from './helpers'

async function emptySetup(page: Parameters<typeof mockAuthenticated>[0]) {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (url.includes('/investments/summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_value_paise: 0, invested_paise: 0, pnl_paise: 0, pnl_percent: 0 }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
}

test('calls GET /investments/summary on load', async ({ page }) => {
  await emptySetup(page)

  const [request] = await Promise.all([
    page.waitForRequest((req) => req.url().includes('/investments/summary') && req.method() === 'GET'),
    page.goto('/investments'),
  ])

  expect(request.method()).toBe('GET')
})

test('calls GET /investments/holdings on load', async ({ page }) => {
  await emptySetup(page)

  const [request] = await Promise.all([
    page.waitForRequest((req) => req.url().includes('/investments/holdings') && req.method() === 'GET'),
    page.goto('/investments'),
  ])

  expect(request.method()).toBe('GET')
})

test('calls GET /investments/sips on load', async ({ page }) => {
  await emptySetup(page)

  const [request] = await Promise.all([
    page.waitForRequest((req) => req.url().includes('/investments/sips') && req.method() === 'GET'),
    page.goto('/investments'),
  ])

  expect(request.method()).toBe('GET')
})

test('calls GET /investments/fds on load', async ({ page }) => {
  await emptySetup(page)

  const [request] = await Promise.all([
    page.waitForRequest((req) => req.url().includes('/investments/fds') && req.method() === 'GET'),
    page.goto('/investments'),
  ])

  expect(request.method()).toBe('GET')
})

test('portfolio value reflects total_value_paise from summary response', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (url.includes('/investments/summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_value_paise: 38500000, invested_paise: 32000000, pnl_paise: 6500000, pnl_percent: 20.3 }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/investments')

  // 38500000 paise = ₹385,000 → formatCompactINR renders as ₹385.0K
  await expect(page.getByTestId('portfolio-value')).toContainText('₹385.0K')
})

test('negative PnL renders with destructive colour class', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (url.includes('/investments/summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_value_paise: 5000000, invested_paise: 6000000, pnl_paise: -1000000, pnl_percent: -16.7 }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/investments')

  const pnl = page.getByTestId('portfolio-pnl')
  await expect(pnl).toBeVisible()
  await expect(pnl).toHaveClass(/text-destructive/)
})

test('holdings tab renders name and current value for each holding', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (url.includes('/investments/summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_value_paise: 10000000, invested_paise: 8000000, pnl_paise: 2000000, pnl_percent: 25 }),
      })
    }
    if (url.includes('/investments/holdings')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'hx', name: 'Bitcoin ETF', type: 'crypto', units: 0.5, avg_buy_price_paise: 1600000, current_value_paise: 10000000, pnl_paise: 2000000, pnl_percent: 25 },
        ]),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/investments')

  await expect(page.getByTestId('holding-row-hx')).toBeVisible()
  await expect(page.getByText('Bitcoin ETF')).toBeVisible()
  await expect(page.getByText('Crypto')).toBeVisible()
  await expect(page.getByText('+25.0%')).toBeVisible()
})

test('SIPs tab renders name and monthly amount for each SIP', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (url.includes('/investments/summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_value_paise: 0, invested_paise: 0, pnl_paise: 0, pnl_percent: 0 }),
      })
    }
    if (url.includes('/investments/sips')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'sx', name: 'Nifty Index Fund', amount_paise: 1000000, next_date: '2026-06-01', status: 'active' },
        ]),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/investments')
  await page.getByRole('tab', { name: 'SIPs' }).click()

  await expect(page.getByTestId('sip-row-sx')).toBeVisible()
  await expect(page.getByText('Nifty Index Fund')).toBeVisible()
  await expect(page.getByTestId('sip-row-sx')).toContainText('/mo')
})

test('FDs tab renders bank name and maturity amount', async ({ page }) => {
  await mockAuthenticated(page)
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (url.includes('/investments/summary')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_value_paise: 0, invested_paise: 0, pnl_paise: 0, pnl_percent: 0 }),
      })
    }
    if (url.includes('/investments/fds')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'fx', bank: 'HDFC', principal_paise: 10000000, rate: 6.5, maturity_date: '2028-01-01', maturity_paise: 13000000 },
        ]),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.goto('/investments')
  await page.getByRole('tab', { name: 'FDs' }).click()

  await expect(page.getByTestId('fd-row-fx')).toBeVisible()
  await expect(page.getByText('HDFC FD')).toBeVisible()
  await expect(page.getByText('6.5%')).toBeVisible()
  await expect(page.getByText('at maturity')).toBeVisible()
})
