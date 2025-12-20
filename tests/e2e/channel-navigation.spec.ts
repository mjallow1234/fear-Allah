import { test, expect } from '@playwright/test';

test('clicking a channel updates URL and does not open WebSocket when runtime flag is unset', async ({ page }) => {
  // Listen for any websocket openings
  let sawWs = false
  page.on('websocket', () => {
    sawWs = true
  })

  // Login
  await page.goto('/login')
  await page.getByLabel(/email/i).fill('test@example.com')
  await page.getByLabel(/password/i).fill('testpassword')
  await page.getByRole('button', { name: /sign in/i }).click()
  await expect(page).toHaveURL('/')

  // Sidebar should be visible
  await expect(page.getByTestId('sidebar')).toBeVisible()

  // Ensure runtime flag is not enabled by default
  const flag = await page.evaluate(() => (window as any).__ENABLE_WEBSOCKETS__)
  expect(flag).toBeFalsy()

  // Click a channel: prefer a named channel, fallback to the first channel link
  const chan = page.getByText('general')
  if ((await chan.count()) > 0) {
    await chan.first().click()
  } else {
    await page.locator('a[href^="/channels/"]').first().click()
  }

  // URL should point to a channel id
  await expect(page).toHaveURL(/\/channels\/\d+/)

  // short wait to detect any websocket attempts
  await page.waitForTimeout(200)
  expect(sawWs).toBe(false)
})
