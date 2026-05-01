import { test, expect } from '@playwright/test'
import { mockAuthenticated, mockApiEmpty } from './helpers'

test.beforeEach(async ({ page }) => {
  await mockAuthenticated(page)
  await mockApiEmpty(page)
})

const SUB_PAGES = [
  { path: '/more/budgets',    heading: 'Budgets' },
  { path: '/more/earnings',   heading: 'Earnings' },
  { path: '/more/accounts',   heading: 'Accounts' },
  { path: '/more/categories', heading: 'Categories & Rules' },
  { path: '/more/settings',   heading: 'Settings' },
]

for (const { path, heading } of SUB_PAGES) {
  test(`${heading} page renders and back button returns to More`, async ({ page }) => {
    await page.goto(path)
    await page.waitForLoadState('networkidle')
    await expect(page.getByRole('heading', { name: heading })).toBeVisible()

    await page.getByRole('button').first().click()
    await expect(page).toHaveURL('/more')
    await expect(page.getByRole('heading', { name: 'More' })).toBeVisible()
  })
}

test('clicking Budgets from More page navigates correctly', async ({ page }) => {
  await page.goto('/more')
  await page.waitForLoadState('networkidle')
  await page.getByText('Budgets').click()
  await expect(page).toHaveURL('/more/budgets')
  await expect(page.getByRole('heading', { name: 'Budgets' })).toBeVisible()
})

test('clicking Settings from More page navigates correctly', async ({ page }) => {
  await page.goto('/more')
  await page.waitForLoadState('networkidle')
  await page.getByText('Settings').click()
  await expect(page).toHaveURL('/more/settings')
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()
})
