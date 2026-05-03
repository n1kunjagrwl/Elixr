/**
 * Integration tests for the Investments page.
 */
import { test, expect } from '@playwright/test'
import { mockAuthenticated } from './helpers'

const MOCK_SUMMARY = {
  total_value_paise: 21800000,
  invested_paise: 18000000,
  pnl_paise: 3800000,
  pnl_percent: 21.1,
}

const MOCK_HOLDINGS = [
  { id: 'h1', name: 'Mirae Asset Large Cap', type: 'mutual_fund', units: 245.3, avg_buy_price_paise: 2000000, current_value_paise: 8500000, pnl_paise: 1200000, pnl_percent: 16.4 },
  { id: 'h2', name: 'HDFC Bank', type: 'stock', units: 50, avg_buy_price_paise: 1400000, current_value_paise: 7800000, pnl_paise: 650000, pnl_percent: 9.1 },
]

const MOCK_SIPS = [
  { id: 's1', name: 'Axis Bluechip Fund', amount_paise: 500000, next_date: '2026-05-01', status: 'active' },
]

const MOCK_FDS = [
  { id: 'f1', bank: 'SBI', principal_paise: 5000000, rate: 7.1, maturity_date: '2027-04-15', maturity_paise: 5710000 },
]

async function setupInvestments(
  page: Parameters<typeof mockAuthenticated>[0],
  opts: { summary?: typeof MOCK_SUMMARY; holdings?: typeof MOCK_HOLDINGS; sips?: typeof MOCK_SIPS; fds?: typeof MOCK_FDS } = {}
) {
  await mockAuthenticated(page)
  const summary = opts.summary ?? MOCK_SUMMARY
  const holdings = opts.holdings ?? MOCK_HOLDINGS
  const sips = opts.sips ?? MOCK_SIPS
  const fds = opts.fds ?? MOCK_FDS

  await page.route(/\/api\/v1\/(?!auth\/)/, (route) => {
    const url = route.request().url()
    if (url.includes('/investments/summary')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(summary) })
    }
    if (url.includes('/investments/holdings')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(holdings) })
    }
    if (url.includes('/investments/sips')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(sips) })
    }
    if (url.includes('/investments/fds')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(fds) })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
}

// ── Portfolio summary header ───────────────────────────────────────────────────

test('displays portfolio total value from API summary', async ({ page }) => {
  await setupInvestments(page)
  await page.goto('/investments')

  await expect(page.getByTestId('portfolio-value')).toBeVisible()
  // MOCK_SUMMARY.total_value_paise = 21800000 → ₹2.18L
  await expect(page.getByTestId('portfolio-value')).toContainText('₹')
})

test('displays overall PnL when pnl_paise is non-zero', async ({ page }) => {
  await setupInvestments(page)
  await page.goto('/investments')

  await expect(page.getByTestId('portfolio-pnl')).toBeVisible()
  await expect(page.getByTestId('portfolio-pnl')).toContainText('overall')
})

test('does not show PnL when summary pnl_paise is 0', async ({ page }) => {
  await setupInvestments(page, {
    summary: { total_value_paise: 5000000, invested_paise: 5000000, pnl_paise: 0, pnl_percent: 0 },
  })
  await page.goto('/investments')

  await expect(page.getByTestId('portfolio-pnl')).not.toBeVisible()
})

// ── Holdings tab ───────────────────────────────────────────────────────────────

test('Holdings tab renders holding names from API', async ({ page }) => {
  await setupInvestments(page)
  await page.goto('/investments')

  await expect(page.getByTestId('holding-row-h1')).toBeVisible()
  await expect(page.getByText('Mirae Asset Large Cap')).toBeVisible()
  await expect(page.getByTestId('holding-row-h2')).toBeVisible()
  await expect(page.getByText('HDFC Bank')).toBeVisible()
})

test('Holdings tab maps type enum to display label', async ({ page }) => {
  await setupInvestments(page)
  await page.goto('/investments')

  await expect(page.getByTestId('holding-row-h1')).toContainText('Mutual Fund')
  await expect(page.getByTestId('holding-row-h2')).toContainText('Stock')
})

test('Holdings tab shows current value and pnl percent per holding', async ({ page }) => {
  await setupInvestments(page)
  await page.goto('/investments')

  const h1 = page.getByTestId('holding-row-h1')
  await expect(h1).toContainText('₹')   // current value
  await expect(h1).toContainText('16.4%')
})

test('Holdings tab shows empty state when API returns no holdings', async ({ page }) => {
  await setupInvestments(page, { holdings: [] })
  await page.goto('/investments')

  await expect(page.getByText('No holdings added')).toBeVisible()
})

// ── SIPs tab ───────────────────────────────────────────────────────────────────

test('SIPs tab renders SIP name and amount from API', async ({ page }) => {
  await setupInvestments(page)
  await page.goto('/investments')
  await page.getByRole('tab', { name: 'SIPs' }).click()

  await expect(page.getByTestId('sip-row-s1')).toBeVisible()
  await expect(page.getByText('Axis Bluechip Fund')).toBeVisible()
  await expect(page.getByTestId('sip-row-s1')).toContainText('/mo')
  await expect(page.getByTestId('sip-row-s1')).toContainText('active')
})

test('SIPs tab shows empty state when API returns no SIPs', async ({ page }) => {
  await setupInvestments(page, { sips: [] })
  await page.goto('/investments')
  await page.getByRole('tab', { name: 'SIPs' }).click()

  await expect(page.getByText('No active SIPs')).toBeVisible()
})

// ── FDs tab ────────────────────────────────────────────────────────────────────

test('FDs tab renders FD bank and maturity amount from API', async ({ page }) => {
  await setupInvestments(page)
  await page.goto('/investments')
  await page.getByRole('tab', { name: 'FDs' }).click()

  await expect(page.getByTestId('fd-row-f1')).toBeVisible()
  await expect(page.getByText('SBI FD')).toBeVisible()
  await expect(page.getByTestId('fd-row-f1')).toContainText('7.1%')
  await expect(page.getByTestId('fd-row-f1')).toContainText('at maturity')
})

test('FDs tab shows empty state when API returns no FDs', async ({ page }) => {
  await setupInvestments(page, { fds: [] })
  await page.goto('/investments')
  await page.getByRole('tab', { name: 'FDs' }).click()

  await expect(page.getByText('No fixed deposits')).toBeVisible()
})
