import { test, expect } from '@playwright/test'

test('create channel flow (admin)', async ({ page, request }) => {
  test.setTimeout(120000)

  // Login via API and seed localStorage
  const loginResp = await request.post('/api/auth/login', {
    data: { identifier: 'admin@fearallah.com', password: 'admin123' },
  })
  expect(loginResp.ok()).toBeTruthy()
  const loginJson = await loginResp.json()
  const token = loginJson.access_token

  const authPayload = JSON.stringify({ state: { token, user: loginJson.user, isAuthenticated: true } })
  await page.addInitScript((auth) => { try { localStorage.setItem('auth-storage', auth) } catch (e) {} }, authPayload)

  await page.goto('/channels/1')
  await page.waitForSelector('text=Channels')

  // Click the + to open create modal
  await page.click('button[title="Add Channel"]')
  await page.waitForSelector('text=Create Channel')

  // Fill display name and wait for slug to populate
  await page.getByLabel('Display Name').fill('Testing Channel')
  // Wait a little for auto-slug to be generated
  await page.waitForTimeout(200)
  const channelName = await page.getByLabel('Channel Name').inputValue()
  expect(channelName.length).toBeGreaterThan(0)

  // Submit and wait for POST to /api/channels
  const [, postResp] = await Promise.all([
    page.click('button:has-text("Create")'),
    page.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes('/api/channels') && r.status() >= 200 && r.status() < 300, { timeout: 5000 }),
  ])
  expect(postResp.status()).toBe(201)
  const postJson = await postResp.json()
  expect(postJson.display_name).toBe('Testing Channel')

  // Wait for navigation and sidebar update
  await page.waitForURL(/\/channels\/\d+/, { timeout: 10000 })
  const url = page.url()
  expect(url).toMatch(/\/channels\/\d+/)

  // Verify server created the channel
  const matches = url.match(/\/channels\/(\d+)/)
  expect(matches).toBeTruthy()
  const channelId = matches![1]
  const chResp = await request.get(`/api/channels/${channelId}`, { headers: { Authorization: `Bearer ${token}` } })
  console.log('GET channel status:', chResp.status())
  console.log('GET channel body:', await chResp.text())
  expect(chResp.ok()).toBeTruthy()
  const chJson = await chResp.json()
  expect(chJson.display_name).toBe('Testing Channel')

  // Confirm channel display name visible in sidebar (allow a bit more time for UI update)
  await page.waitForSelector(`text=Testing Channel`, { timeout: 10000 })
})


test('create channel flow (non-admin) - + button disabled', async ({ page, request }) => {
  // Register a fresh non-admin user and seed localStorage
  const email = `user+${Date.now()}@example.com`
  const registerResp = await request.post('/api/auth/register', {
    data: { email, password: 'pass123', username: `user${Date.now()}` },
  })
  expect(registerResp.ok()).toBeTruthy()

  const loginResp = await request.post('/api/auth/login', {
    data: { identifier: email, password: 'pass123' },
  })
  expect(loginResp.ok()).toBeTruthy()
  const loginJson = await loginResp.json()
  const token = loginJson.access_token

  const authPayload = JSON.stringify({ state: { token, user: loginJson.user, isAuthenticated: true } })
  await page.addInitScript((auth) => { try { localStorage.setItem('auth-storage', auth) } catch (e) {} }, authPayload)

  await page.goto('/channels/1')
  await page.waitForSelector('text=Channels')

  // + button should be disabled and have a tooltip indicating admin-only
  const addButton = page.locator('button[title="Only admins can create channels"]')
  await expect(addButton).toBeVisible()
  await expect(addButton).toBeDisabled()
})
