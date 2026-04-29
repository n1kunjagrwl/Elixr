import { test, expect } from '@playwright/test'
import { mockUnauthenticated } from './helpers'

// Reusable locators
const phoneInput = (page: ReturnType<typeof test['info']> extends never ? never : Parameters<Parameters<typeof test>[1]>[0]) =>
  page.locator('input[type="tel"]')

test.beforeEach(async ({ page }) => {
  await mockUnauthenticated(page)
})

test('renders phone input on load', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByText('Elixir')).toBeVisible()
  await expect(page.getByText('Your personal finance companion')).toBeVisible()
  await expect(page.locator('input[type="tel"]')).toBeVisible()
  await expect(page.getByRole('button', { name: /send otp/i })).toBeVisible()
})

test('shows +91 country code prefix', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByText('+91')).toBeVisible()
})

test('rejects phone number shorter than 10 digits', async ({ page }) => {
  await page.goto('/login')
  await page.locator('input[type="tel"]').fill('98765')
  await page.getByRole('button', { name: /send otp/i }).click()
  await expect(page.getByText('Enter a valid 10-digit mobile number')).toBeVisible()
})

test('proceeds to OTP step after entering 10-digit phone', async ({ page }) => {
  await page.route(/\/api\/v1\/auth\/request-otp/, (route) =>
    route.fulfill({ status: 200, body: '{"message":"OTP sent"}' })
  )

  await page.goto('/login')
  await page.locator('input[type="tel"]').fill('9876543210')
  await page.getByRole('button', { name: /send otp/i }).click()

  await expect(page.getByText(/enter otp sent to/i)).toBeVisible()
  await expect(page.getByRole('button', { name: /verify & sign in/i })).toBeVisible()
  await expect(page.getByRole('button', { name: /change number/i })).toBeVisible()
})

test('shows error when OTP request fails', async ({ page }) => {
  await page.route(/\/api\/v1\/auth\/request-otp/, (route) =>
    route.fulfill({ status: 500, body: '{"detail":"Server error"}' })
  )

  await page.goto('/login')
  await page.locator('input[type="tel"]').fill('9876543210')
  await page.getByRole('button', { name: /send otp/i }).click()

  await expect(page.getByText('Could not send OTP. Please try again.')).toBeVisible()
})

test('rejects OTP shorter than 6 digits', async ({ page }) => {
  await page.route(/\/api\/v1\/auth\/request-otp/, (route) =>
    route.fulfill({ status: 200, body: '{"message":"OTP sent"}' })
  )

  await page.goto('/login')
  await page.locator('input[type="tel"]').fill('9876543210')
  await page.getByRole('button', { name: /send otp/i }).click()

  // The OTP input appears after the phone step
  await page.locator('input[inputmode="numeric"][maxlength="6"]').fill('123')
  await page.getByRole('button', { name: /verify & sign in/i }).click()

  await expect(page.getByText('Enter the 6-digit OTP')).toBeVisible()
})

test('shows error when OTP verification fails', async ({ page }) => {
  await page.route(/\/api\/v1\/auth\/request-otp/, (route) =>
    route.fulfill({ status: 200, body: '{"message":"OTP sent"}' })
  )
  await page.route(/\/api\/v1\/auth\/verify-otp/, (route) =>
    route.fulfill({ status: 401, body: '{"detail":"Invalid OTP"}' })
  )

  await page.goto('/login')
  await page.locator('input[type="tel"]').fill('9876543210')
  await page.getByRole('button', { name: /send otp/i }).click()
  await page.locator('input[inputmode="numeric"][maxlength="6"]').fill('999999')
  await page.getByRole('button', { name: /verify & sign in/i }).click()

  await expect(page.getByText('Invalid OTP. Please try again.')).toBeVisible()
})

test('navigates to home after successful login', async ({ page }) => {
  await page.route(/\/api\/v1\/auth\/request-otp/, (route) =>
    route.fulfill({ status: 200, body: '{"message":"OTP sent"}' })
  )
  await page.route(/\/api\/v1\/auth\/verify-otp/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'test-access-token' }),
    })
  )
  // AuthGuard bootstrap after redirect to /home
  await page.route(/\/api\/v1\/auth\/refresh/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'test-access-token' }),
    })
  )
  await page.route(/\/api\/v1\//, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  )

  await page.goto('/login')
  await page.locator('input[type="tel"]').fill('9876543210')
  await page.getByRole('button', { name: /send otp/i }).click()
  await page.locator('input[inputmode="numeric"][maxlength="6"]').fill('123456')
  await page.getByRole('button', { name: /verify & sign in/i }).click()

  await expect(page).toHaveURL('/home')
})

test('change number button returns to phone step', async ({ page }) => {
  await page.route(/\/api\/v1\/auth\/request-otp/, (route) =>
    route.fulfill({ status: 200, body: '{"message":"OTP sent"}' })
  )

  await page.goto('/login')
  await page.locator('input[type="tel"]').fill('9876543210')
  await page.getByRole('button', { name: /send otp/i }).click()
  await expect(page.getByRole('button', { name: /verify & sign in/i })).toBeVisible()

  await page.getByRole('button', { name: /change number/i }).click()

  await expect(page.locator('input[type="tel"]')).toBeVisible()
  await expect(page.getByRole('button', { name: /send otp/i })).toBeVisible()
})
