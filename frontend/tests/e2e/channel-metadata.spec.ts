import { test, expect } from '@playwright/test'

// U3.2: Channel metadata loads correctly (sidebar list + single detail fetch, no websockets)

test('Channel metadata loads correctly (U3.2)', async ({ page, request }) => {
  const API_BASE = '/api'

  // A) Auth: use injected E2E token if available, otherwise perform API login as fallback
  let token = process.env.E2E_TOKEN
  if (!token) {
    const loginResp = await request.post(`${API_BASE}/api/auth/login`, {
      data: { identifier: 'admin@fearallah.com', password: 'admin123' },
    })
    expect(loginResp.ok()).toBeTruthy()
    const loginBody = await loginResp.json()
    token = loginBody.access_token
  }

  // Add auth to localStorage before app loads (per instruction use access_token key)
  // Also fetch /api/users/me and set a full `auth-storage` so the app knows the current user on load.
  let me: any = null
  try {
    const meResp = await request.get(`${API_BASE}/api/users/me`, { headers: { authorization: `Bearer ${token}` } })
    if (meResp.ok()) me = await meResp.json()
  } catch (e) {}

  // Disable WebSockets explicitly for this test so we verify behavior without WS
  await page.addInitScript(() => { try { (window as any).__ENABLE_WEBSOCKETS__ = false } catch (e) {} })

  await page.addInitScript((t, meData) => {
    try { localStorage.setItem('access_token', t) } catch (e) {}
    try { localStorage.setItem('auth-storage', JSON.stringify({ state: { token: t, user: meData, isAuthenticated: true } })) } catch (e) {}
  }, token, me)

  // Intercept network activity
  const channelsCalls: string[] = []
  const channelCalls: string[] = []
  const wsConnections: string[] = []
  const consoleErrors: string[] = []

  page.on('request', (req) => {
    const url = req.url()
    const path = url.replace(/^https?:\/\/[^/]+/, '')
    if (path.endsWith('/api/channels/') || path.endsWith('/api/channels')) channelsCalls.push(url)
    if (path.match(/\/api\/channels\/\d+$/)) channelCalls.push(url)
  })

  page.on('websocket', (ws) => {
    const url = ws.url()
    // Ignore dev server / Vite HMR websockets (commonly on 5173/5174) and only record backend WS connections
    if (/:\/\/localhost:(5173|5174|4173)\//.test(url) || url.includes('/__webpack_hmr') || url.includes('vite')) return
    if (/\/ws/.test(url) || /\/api\/ws/.test(url) || url.startsWith('ws://localhost:18002')) {
      wsConnections.push(url)
    }
  })
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()) })

  // Ensure there's at least one channel available to click
  const createResp = await request.post(`${API_BASE}/api/channels/`, {
    headers: { authorization: `Bearer ${token}` },
    data: { name: `e2e-channel-${Date.now()}`, display_name: 'E2E Channel', type: 'public', team_id: null },
  })
  expect(createResp.ok()).toBeTruthy()
  const created = await createResp.json()

  // B) Navigate to app root — prefer simple '/' but fall back to probing common dev/preview ports if needed
  let navigated = false
  try {
    await page.goto('/')
    await page.waitForTimeout(500)
    navigated = true
  } catch (e) {
    // fall through to probe candidate hosts
  }

  if (!navigated) {
    const candidates = ['http://localhost:5173', 'http://localhost:5174', 'http://localhost:4173']
    for (const c of candidates) {
      try {
        const probe = await request.get(c)
        if (probe.ok()) {
          await page.goto(c)
          await page.waitForTimeout(500)
          navigated = true
          break
        }
      } catch (e) {
        // try next
      }
    }
    if (!navigated) throw new Error('Unable to open frontend app; ensure dev server or preview is running')
  }

  // C) Wait for Sidebar using role-based or text-based selector
  let sidebar = page.getByRole('navigation')
  if (await sidebar.count() === 0) {
    // Fallback: ensure the 'Channels' section header is visible (use exact match to avoid matching 'No channels yet')
    await expect(page.getByText('Channels', { exact: true }).first()).toBeVisible({ timeout: 15000 })
    sidebar = page.getByText('Channels', { exact: true }).first()
  } else {
    await expect(sidebar).toBeVisible({ timeout: 15000 })
  }

  // D) Click a channel using text-based selection; fallback to first link role
  let channelItem = page.getByText(/general/i)
  if (await channelItem.count() === 0) {
    channelItem = page.getByRole('link').first()
  }
  await expect(channelItem).toBeVisible({ timeout: 15000 })
  await channelItem.click()

  // E) Assert metadata header renders (heading OR created OR description/purpose)
  const headerVisible = await (async () => {
    try { await page.getByRole('heading', { level: 1 }).waitFor({ timeout: 4000 }); return true } catch (e) {}
    try { await page.getByRole('heading', { level: 2 }).waitFor({ timeout: 4000 }); return true } catch (e) {}
    try { await page.getByText(/created/i).waitFor({ timeout: 4000 }); return true } catch (e) {}
    try { await page.getByText(/description|purpose/i, { exact: false }).waitFor({ timeout: 4000 }); return true } catch (e) {}
    return false
  })()
  expect(headerVisible).toBe(true)

  // F) Assert network behavior
  // Allow time for requests
  await page.waitForTimeout(500)
  expect(channelsCalls.length).toBeGreaterThanOrEqual(1)
  expect(channelCalls.length).toBe(1)

  // G) Assert NO WebSockets were opened
  expect(wsConnections.length).toBe(0)

  // No console errors
  expect(consoleErrors.length).toBe(0)
})