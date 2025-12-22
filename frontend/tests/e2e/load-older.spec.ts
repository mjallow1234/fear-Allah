import { test, expect } from '@playwright/test'

test('load older messages (U3.4)', async ({ page, request }) => {
  test.setTimeout(120000)

  // Login as admin
  const loginResp = await request.post('http://localhost:18002/api/auth/login', {
    data: { identifier: 'admin@fearallah.com', password: 'admin123' },
  })
  expect(loginResp.ok()).toBeTruthy()
  const loginJson = await loginResp.json()
  const token = loginJson.access_token

  // Create a fresh channel
  const chName = `u34-${Date.now()}`
  const createResp = await request.post('http://localhost:18002/api/channels', {
    data: { name: chName, display_name: chName, type: 'O' },
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(createResp.ok()).toBeTruthy()
  const chJson = await createResp.json()
  const channelId = chJson.id

  // Post many messages to force pagination (more than default 50)
  for (let i = 1; i <= 55; i++) {
    const msg = { content: `msg-${i}`, channel_id: channelId }
    const r = await request.post('http://localhost:18002/api/messages', { data: msg, headers: { Authorization: `Bearer ${token}` } })
    expect(r.ok()).toBeTruthy()
  }

  // Seed localStorage for browser with auth
  const authPayload = JSON.stringify({ state: { token, user: loginJson.user, isAuthenticated: true } })
  await page.addInitScript((auth) => { try { localStorage.setItem('auth-storage', auth) } catch (e) {} }, authPayload)

  // Open channel page
  await page.goto(`/channels/${channelId}`)

  // Wait for messages to load and Load older button to appear
  await page.waitForSelector('text=Load older messages', { timeout: 10000 })

  // Click load older
  await page.click('text=Load older messages')

  // Wait for an older message (e.g., msg-1) to appear
  await page.waitForSelector('text=msg-1', { timeout: 10000 })

  // Verify older message visible
  expect(await page.isVisible('text=msg-1')).toBeTruthy()
})