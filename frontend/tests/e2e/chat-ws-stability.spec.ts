import { test, expect } from '@playwright/test'

// This test validates that chat WebSocket is stable and not closed by presence updates
// Steps:
// 1. Login
// 2. Navigate to channel 1
// 3. Record console logs and assert exactly one connect + onopen
// 4. Trigger presence updates for ~12s (open/close presence WS from page)
// 5. Assert NO onclose occurred during presence bombardment
// 6. Switch to channel 4
// 7. Assert exactly one onclose and one new connect+onopen after channel switch

test('chat WS stability', async ({ page, request }) => {
  test.setTimeout(120000)
  const consoleMessages: string[] = []
  page.on('console', (msg) => {
    const text = msg.text()
    consoleMessages.push(text)
    console.log('PAGE LOG:', text)
  })

  // Ensure we're logged out and show login
  await page.goto('/')
  await page.context().clearCookies()
  await page.evaluate(() => localStorage.clear())
  // Prefer API-based login to avoid flakiness from HMR or UI changes (Option A)
  // Use test.request fixture to POST login to backend
  const loginResp = await request.post('/api/auth/login', {
    data: { identifier: 'admin@fearallah.com', password: 'admin123' },
  })
  expect(loginResp.ok(), 'Login API call failed').toBeTruthy()
  const loginJson = await loginResp.json()
  const token = loginJson.access_token

  // Sanity check: ensure the token works against the API
  const meResp = await request.get('http://localhost:18002/api/users/me', {
    headers: { authorization: `Bearer ${token}` },
  })
  console.log('ME STATUS:', meResp.status())
  const meJson = await meResp.json()
  console.log('ME JSON:', JSON.stringify(meJson))

  // Seed localStorage BEFORE the app loads to avoid hydrate/routing race
  const authPayload = JSON.stringify({ state: { token, user: loginJson.user, isAuthenticated: true } })
  await page.addInitScript((auth) => {
    try {
      localStorage.setItem('auth-storage', auth)
    } catch (e) {
      // no-op
    }
  }, authPayload)

  // Navigate directly to channel which should pick up the persisted auth immediately
  await page.goto('/channels/1')
  await page.waitForLoadState('networkidle')

  // Diagnostic info after navigation
  console.log('PAGE URL after nav:', page.url())
  const authAfter = await page.evaluate(() => localStorage.getItem('auth-storage'))
  console.log('AUTH after nav:', authAfter)
  const bodyLen = await page.evaluate(() => document.body.innerHTML.length)
  console.log('BODY LENGTH', bodyLen)

  // If we're on the login page due to an initial routing redirect, reload once to let the app hydrate
  if (page.url().includes('/login')) {
    console.log('On login page; reloading to pick up persisted auth state')
    await page.reload()
    await page.waitForLoadState('networkidle')
    console.log('After reload URL:', page.url())
  }

  await page.waitForSelector('text=Channels', { timeout: 60000 })

  // Wait for connect and onopen (give up to 10s)
  await page.waitForTimeout(2000)
  const start = Date.now()
  let connectCount = 0
  let onopenCount = 0
  while (Date.now() - start < 10000) {
    connectCount = consoleMessages.filter((m) => m.includes('[ChatSocket] connect')).length
    onopenCount = consoleMessages.filter((m) => m.includes('[ChatSocket] onopen')).length
    if (connectCount >= 1 && onopenCount >= 1) break
    await page.waitForTimeout(200)
  }

  // Assert at least one connect attempt and exactly one initial onopen (stable connection)
  expect(onopenCount, 'Expected exactly one initial onopen').toBe(1)
  expect(connectCount, 'Expected at least one connect attempt').toBeGreaterThanOrEqual(1)

  // Capture baseline onclose count
  let baselineOnclose = consoleMessages.filter((m) => m.includes('[ChatSocket] onclose')).length

  // Trigger presence updates from the page context for ~12 seconds
  // We open and close a presence WebSocket repeatedly using the token from localStorage
  await page.evaluate(async () => {
    const stateRaw = localStorage.getItem('auth-storage')
    if (!stateRaw) return
    let token = null
    try {
      const parsed = JSON.parse(stateRaw)
      token = parsed.state?.token || parsed.token
    } catch (e) {
      return
    }
    if (!token) return

    const wsBase = 'ws://localhost:18002'
    const end = Date.now() + 12000
    while (Date.now() < end) {
      const ws = new WebSocket(`${wsBase}/ws/presence?token=${encodeURIComponent(token)}`)
      // open then close quickly to simulate a presence update
      await new Promise((resolve) => {
        ws.onopen = () => {
          setTimeout(() => {
            try { ws.close() } catch (e) {}
            resolve(null)
          }, 150)
        }
        // In case it fails to open, resolve after 300ms
        setTimeout(resolve, 300)
      })
      // small pause before next burst
      await new Promise((r) => setTimeout(r, 200))
    }
  })

  // After presence bombardment, ensure no onclose beyond baseline
  await page.waitForTimeout(1000)
  const oncloseAfterPresence = consoleMessages.filter((m) => m.includes('[ChatSocket] onclose')).length
  expect(oncloseAfterPresence - baselineOnclose, 'WebSocket onclose occurred during presence updates').toBe(0)

  // Remember counts so far
  const beforeSwitchConnects = consoleMessages.filter((m) => m.includes('[ChatSocket] connect')).length
  const beforeSwitchOnopens = consoleMessages.filter((m) => m.includes('[ChatSocket] onopen')).length

  // Switch to channel 4
  await page.goto('/channels/4')

  // Wait for onclose and new connect/onopen (up to 10s)
  const switchStart = Date.now()
  let sawOnclose = false
  let newConnects = 0
  let newOnopens = 0
  while (Date.now() - switchStart < 10000) {
    const totalOncloses = consoleMessages.filter((m) => m.includes('[ChatSocket] onclose')).length
    const totalConnects = consoleMessages.filter((m) => m.includes('[ChatSocket] connect')).length
    const totalOnopens = consoleMessages.filter((m) => m.includes('[ChatSocket] onopen')).length
    if (totalOncloses > baselineOnclose) sawOnclose = true
    newConnects = totalConnects - beforeSwitchConnects
    newOnopens = totalOnopens - beforeSwitchOnopens
    if (sawOnclose && newConnects >= 1 && newOnopens >= 1) break
    await page.waitForTimeout(200)
  }

  expect(sawOnclose, 'Expected an onclose when switching channels').toBe(true)
  expect(newConnects, 'Expected at least one new connect after channel switch').toBeGreaterThanOrEqual(1)
  expect(newOnopens, 'Expected at least one new onopen after channel switch').toBeGreaterThanOrEqual(1)

  // Ensure there were no onclose events earlier (without channel change)
  // We asserted none during presence updates; ensure total oncloses equals baseline+1
  const finalOncloses = consoleMessages.filter((m) => m.includes('[ChatSocket] onclose')).length
  expect(finalOncloses, 'Unexpected onclose count (should be baseline + 1 for channel switch)').toBe(baselineOnclose + 1)
})