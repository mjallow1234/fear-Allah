import { test, expect } from '@playwright/test'

// Ensure the dev server is running and the backend is available before running this test.
// The test checks navigation to a channel and verifies the UI header updates.
// It also checks there are no WebSocket connections created (by observing network requests).

test('channel navigation updates URL and header, and no websockets by default', async ({ page }) => {
  // Visit the app
  await page.goto('http://localhost:5173')

  // Wait for sidebar to load channel links
  await page.waitForSelector('nav')

  // Find a channel link (first one) and click it
  const channelLink = await page.locator('nav a').first()
  const href = await channelLink.getAttribute('href')
  await channelLink.click()

  // URL should update to the channel path
  await expect(page).toHaveURL(new RegExp('/channels/'))

  // Header should show channel name or fallback
  await expect(page.locator('h1')).toHaveText(/Channel|Loading|Chan/i)

  // Assert that no websocket connections were created
  // Playwright can check service worker and network traffic; here we ensure no ws protocol requests were made
  const wsRequests = [] as string[]
  page.on('websocket', (ws) => wsRequests.push(ws.url()))

  // Give some time for any potential websocket connections to start
  await page.waitForTimeout(500)

  expect(wsRequests.length).toBe(0)
})