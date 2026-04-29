import { test, expect } from '@playwright/test'
import { mockAuthenticated, mockUnauthenticated, mockApiEmpty } from './helpers'

test('unauthenticated user is redirected from / to /login', async ({ page }) => {
  await mockUnauthenticated(page)
  await page.goto('/')
  await expect(page).toHaveURL('/login')
})

test('unauthenticated user is redirected from /home to /login', async ({ page }) => {
  await mockUnauthenticated(page)
  await page.goto('/home')
  await expect(page).toHaveURL('/login')
})

test('unauthenticated user is redirected from /transactions to /login', async ({ page }) => {
  await mockUnauthenticated(page)
  await page.goto('/transactions')
  await expect(page).toHaveURL('/login')
})

test('authenticated user can access /home', async ({ page }) => {
  await mockAuthenticated(page)
  await mockApiEmpty(page)
  await page.goto('/home')
  await expect(page).toHaveURL('/home')
  await expect(page.getByRole('navigation')).toBeVisible()
})

test('authenticated user sees the bottom navigation bar', async ({ page }) => {
  await mockAuthenticated(page)
  await mockApiEmpty(page)
  await page.goto('/home')

  const nav = page.getByRole('navigation')
  await expect(nav.getByText('Home')).toBeVisible()
  await expect(nav.getByText('Transactions')).toBeVisible()
  await expect(nav.getByText('Invest')).toBeVisible()
  await expect(nav.getByText('Peers')).toBeVisible()
  await expect(nav.getByText('More')).toBeVisible()
})

test('login page is accessible without auth', async ({ page }) => {
  await mockUnauthenticated(page)
  await page.goto('/login')
  await expect(page).toHaveURL('/login')
  await expect(page.locator('input[type="tel"]')).toBeVisible()
})
