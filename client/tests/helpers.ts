import { Page } from '@playwright/test'

/** Mock the refresh endpoint to return a valid token — simulates a logged-in user. */
export async function mockAuthenticated(page: Page) {
  await page.route(/\/api\/v1\/auth\/refresh/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'test-access-token' }),
    })
  )
}

/** Mock the refresh endpoint to return 401 — simulates a logged-out user. */
export async function mockUnauthenticated(page: Page) {
  await page.route(/\/api\/v1\/auth\/refresh/, (route) =>
    route.fulfill({ status: 401, body: '{"detail":"Unauthorized"}' })
  )
}

/** Stub all non-auth API calls so widgets don't crash with network errors. */
export async function mockApiEmpty(page: Page) {
  // Exclude /auth/* so specific auth mocks registered after this still fire first (LIFO).
  await page.route(/\/api\/v1\/(?!auth\/)/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  )
}
