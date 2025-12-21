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

test('chat WS stability', async ({ page }) => {
  const consoleMessages: string[] = []
  page.on('console', (msg) => {
    const text = msg.text()
    consoleMessages.push(text)
    console.log('PAGE LOG:', text)
  })

  // Login
  await page.goto('/login')
  await page.getByLabel(/Email or Username/i).fill('admin@fearallah.com')
  await page.getByLabel(/Password/i).fill('admin123')
  await page.getByRole('button', { name: /sign in/i }).click()

  // Navigate to channel 1
  await page.goto('/channels/1')

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

  // Assert exactly one initial connect/onopen
  expect(connectCount, 'Expected exactly one initial connect').toBe(1)
  expect(onopenCount, 'Expected exactly one initial onopen').toBe(1)

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
  expect(newConnects, 'Expected exactly one new connect after channel switch').toBe(1)
  expect(newOnopens, 'Expected exactly one new onopen after channel switch').toBe(1)

  // Ensure there were no onclose events earlier (without channel change)
  // We asserted none during presence updates; ensure total oncloses equals baseline+1
  const finalOncloses = consoleMessages.filter((m) => m.includes('[ChatSocket] onclose')).length
  expect(finalOncloses, 'Unexpected onclose count (should be baseline + 1 for channel switch)').toBe(baselineOnclose + 1)
})