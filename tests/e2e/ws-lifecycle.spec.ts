import { test, expect } from '@playwright/test'

test.skip('WebSocket lifecycle stays open (client-side)', async ({ page }) => {
  const consoleMessages: string[] = []
  page.on('console', (msg) => {
    const text = msg.text()
    consoleMessages.push(text)
    console.log('PAGE LOG:', text)
  })

  // Login (same steps as existing auth tests)
  await page.goto('http://localhost:5173/login')
  await page.getByLabel(/email/i).fill('test@example.com')
  await page.getByLabel(/password/i).fill('testpassword')
  await page.getByRole('button', { name: /sign in/i }).click()

  // Navigate to a channel (general)
  await page.getByText('general').click()

  // Wait for the client to open a WS connection for up to 10s
  let openMsg: string | undefined
  await page.waitForFunction(() => {
    // Collect console entries from within the page is not directly available,
    // so rely on the outer console handler to capture messages.
    return true
  })

  // Wait up to 15s for onopen console message
  const start = Date.now()
  while (Date.now() - start < 15000) {
    const msg = consoleMessages.find((m) => /onopen/.test(m) && /WS/.test(m))
    if (msg) {
      openMsg = msg
      break
    }
    await new Promise((r) => setTimeout(r, 200))
  }

  expect(openMsg, 'Expected a WS onopen log').toBeTruthy()

  // Extract connection id from the open message
  const match = openMsg!.match(/WS (\w+)/)
  expect(match).toBeTruthy()
  const id = match![1]

  // Now watch for 30s and ensure no onclose for the same id appears
  const end = Date.now() + 30000
  let sawClose = false
  while (Date.now() < end) {
    const closeMsg = consoleMessages.find((m) => m.includes(`onclose`) && m.includes(id))
    if (closeMsg) {
      sawClose = true
      break
    }
    await new Promise((r) => setTimeout(r, 250))
  }

  expect(sawClose, `WebSocket ${id} was closed unexpectedly`).toBe(false)

  // Also ensure we saw at least one heartbeat_ack within the window
  const sawHeartbeat = consoleMessages.some((m) => m.includes('heartbeat_ack'))
  expect(sawHeartbeat, 'Expected at least one heartbeat_ack').toBe(true)
})
