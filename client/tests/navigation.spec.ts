import { test, expect } from '@playwright/test'
import { mockAuthenticated, mockApiEmpty } from './helpers'

test.beforeEach(async ({ page }) => {
  await mockAuthenticated(page)
  await mockApiEmpty(page)
  await page.goto('/home')
})

test('Home tab is active on /home', async ({ page }) => {
  const homeLink = page.getByRole('link', { name: /home/i })
  // Active tab has text-primary class via NavLink isActive
  await expect(homeLink).toHaveClass(/text-primary/)
})

test('clicking Transactions tab navigates to /transactions', async ({ page }) => {
  await page.getByRole('link', { name: /transactions/i }).click()
  await expect(page).toHaveURL('/transactions')
})

test('clicking Invest tab navigates to /investments', async ({ page }) => {
  await page.getByRole('link', { name: /invest/i }).click()
  await expect(page).toHaveURL('/investments')
})

test('clicking Peers tab navigates to /peers', async ({ page }) => {
  await page.getByRole('link', { name: /peers/i }).click()
  await expect(page).toHaveURL('/peers')
})

test('clicking More tab navigates to /more', async ({ page }) => {
  await page.getByRole('link', { name: /more/i }).click()
  await expect(page).toHaveURL('/more')
})

test('active tab updates when navigating', async ({ page }) => {
  await page.getByRole('link', { name: /transactions/i }).click()
  await expect(page).toHaveURL('/transactions')

  const txLink = page.getByRole('link', { name: /transactions/i })
  await expect(txLink).toHaveClass(/text-primary/)

  const homeLink = page.getByRole('link', { name: /home/i })
  await expect(homeLink).not.toHaveClass(/text-primary/)
})

test('bottom nav stays visible across all tab pages', async ({ page }) => {
  const tabs = ['/transactions', '/investments', '/peers', '/more', '/home']
  for (const url of tabs) {
    await page.goto(url)
    await expect(page.getByRole('navigation')).toBeVisible()
  }
})
