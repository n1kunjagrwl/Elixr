import { test, expect } from '@playwright/test'
import { mockAuthenticated, mockApiEmpty } from './helpers'

test.beforeEach(async ({ page }) => {
  await mockAuthenticated(page)
  await mockApiEmpty(page)
  await page.goto('/home')
})

test('Home tab is active on /home', async ({ page }) => {
  const homeLink = page.getByRole('link', { name: /home/i })
  await expect(homeLink).toHaveClass(/text-primary/)
})

test('clicking Transactions tab navigates to /transactions and renders content', async ({ page }) => {
  await page.getByRole('link', { name: /transactions/i }).click()
  await expect(page).toHaveURL('/transactions')
  await page.waitForLoadState('networkidle')
  await expect(page.getByRole('heading', { name: 'Transactions' })).toBeVisible()
  await expect(page.getByPlaceholder('Search transactions…')).toBeVisible()
})

test('clicking Invest tab navigates to /investments and renders content', async ({ page }) => {
  await page.getByRole('link', { name: /invest/i }).click()
  await expect(page).toHaveURL('/investments')
  await page.waitForLoadState('networkidle')
  await expect(page.getByRole('heading', { name: 'Investments' })).toBeVisible()
  await expect(page.getByText('Portfolio Value')).toBeVisible()
})

test('clicking Peers tab navigates to /peers and renders content', async ({ page }) => {
  await page.getByRole('link', { name: /peers/i }).click()
  await expect(page).toHaveURL('/peers')
  await page.waitForLoadState('networkidle')
  await expect(page.getByRole('heading', { name: 'Peers' })).toBeVisible()
  await expect(page.getByText('Owed to you')).toBeVisible()
})

test('clicking More tab navigates to /more and renders content', async ({ page }) => {
  await page.getByRole('link', { name: 'More', exact: true }).click()
  await expect(page).toHaveURL('/more')
  await page.waitForLoadState('networkidle')
  await expect(page.getByRole('heading', { name: 'More' })).toBeVisible()
  await expect(page.getByText('Budgets')).toBeVisible()
})

test('active tab updates when navigating', async ({ page }) => {
  await page.getByRole('link', { name: /transactions/i }).click()
  await expect(page).toHaveURL('/transactions')

  await expect(page.getByRole('link', { name: /transactions/i })).toHaveClass(/text-primary/)
  await expect(page.getByRole('link', { name: /home/i })).not.toHaveClass(/text-primary/)
})

test('navigating back to Home shows home content', async ({ page }) => {
  await page.getByRole('link', { name: /transactions/i }).click()
  await expect(page).toHaveURL('/transactions')

  await page.getByRole('link', { name: /home/i }).click()
  await expect(page).toHaveURL('/home')
  await page.waitForLoadState('networkidle')
  await expect(page.getByText('Net Position')).toBeVisible()
})

test('bottom nav stays visible across all tab pages', async ({ page }) => {
  const tabs = ['/transactions', '/investments', '/peers', '/more', '/home']
  for (const url of tabs) {
    await page.goto(url)
    await expect(page.getByRole('navigation')).toBeVisible()
  }
})
