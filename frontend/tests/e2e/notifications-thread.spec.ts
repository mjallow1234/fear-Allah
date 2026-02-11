import { test, expect } from '@playwright/test'

const API_BASE = 'http://localhost:18002'

async function registerAndLogin(request: any, email: string, password: string, username: string) {
  // register (ignore failure if already exists)
  try {
    await request.post(`${API_BASE}/api/auth/register`, { data: { email, password, username } })
  } catch (e) {}

  const loginResp = await request.post(`${API_BASE}/api/auth/login`, { data: { identifier: email, password } })
  expect(loginResp.ok()).toBeTruthy()
  const login = await loginResp.json()
  const token = login.access_token

  // fetch "me"
  const meResp = await request.get(`${API_BASE}/api/users/me`, { headers: { authorization: `Bearer ${token}` } })
  const me = meResp.ok() ? await meResp.json() : null
  return { token, me }
}

// DM Reply notification: A posts parent, B replies -> A receives dm_reply and thread opens
test('DM reply notification opens thread and highlights parent', async ({ browser, request }) => {
  const emailA = `e2e-a-${Date.now()}@example.com`
  const emailB = `e2e-b-${Date.now()}@example.com`
  const pw = 'Password123!'

  const a = await registerAndLogin(request, emailA, pw, 'e2e_a')
  const b = await registerAndLogin(request, emailB, pw, 'e2e_b')

  // Create pages for both users
  const contextA = await browser.newContext()
  const pageA = await contextA.newPage()
  await pageA.addInitScript((t, meData) => {
    try { localStorage.setItem('access_token', t) } catch (e) {}
    try { localStorage.setItem('auth-storage', JSON.stringify({ state: { token: t, user: meData, isAuthenticated: true } })) } catch (e) {}
  }, a.token, a.me)

  const contextB = await browser.newContext()
  const pageB = await contextB.newPage()
  await pageB.addInitScript((t, meData) => {
    try { localStorage.setItem('access_token', t) } catch (e) {}
    try { localStorage.setItem('auth-storage', JSON.stringify({ state: { token: t, user: meData, isAuthenticated: true } })) } catch (e) {}
  }, b.token, b.me)

  // Navigate pages
  await pageA.goto('/')
  await pageB.goto('/')

  // Create a direct conversation as A with B
  const convResp = await request.post(`${API_BASE}/api/direct-conversations/`, { headers: { authorization: `Bearer ${a.token}` }, data: { other_user_id: b.me.id } })
  expect(convResp.ok()).toBeTruthy()
  const conv = await convResp.json()

  // A sends parent message via API
  const parentResp = await request.post(`${API_BASE}/api/direct-conversations/${conv.id}/messages`, { headers: { authorization: `Bearer ${a.token}` }, data: { content: 'parent message' } })
  expect(parentResp.ok()).toBeTruthy()
  const parent = await parentResp.json()

  // B should see a dm_message notification (toast) and clicking it navigates to /direct/{id}
  const toastLocator = pageB.locator('div', { hasText: 'New message from' })
  await expect(toastLocator).toBeVisible({ timeout: 5000 })
  await toastLocator.click()

  // B navigates to DM (no message param for dm_message)
  await expect(pageB).toHaveURL(new RegExp(`/direct/${conv.id}$`))

  // Now B replies to parent to generate dm_reply for A
  const replyResp = await request.post(`${API_BASE}/api/direct-conversations/${conv.id}/messages`, { headers: { authorization: `Bearer ${b.token}` }, data: { content: 'reply to parent', parent_id: parent.id } })
  expect(replyResp.ok()).toBeTruthy()
  const reply = await replyResp.json()

  // A should receive dm_reply toast and clicking it navigates to /direct/{id}?message={parent}
  const toastA = pageA.locator('div', { hasText: 'New reply from' })
  await expect(toastA).toBeVisible({ timeout: 5000 })
  await toastA.click()

  await expect(pageA).toHaveURL(new RegExp(`/direct/${conv.id}\?message=${parent.id}`))

  // Thread panel should auto-open and be visible
  await expect(pageA.getByRole('heading', { name: 'Thread' })).toBeVisible({ timeout: 5000 })

  // Parent message should be highlighted (has ring class)
  const parentEl = pageA.locator(`[data-message-id="${parent.id}"]`)
  await expect(parentEl).toBeVisible()
  await expect(parentEl).toHaveClass(/ring-2|ring-blue-400/)

  await contextA.close()
  await contextB.close()
})

// Channel reply notification: reply in channel -> notification opens thread
test('Channel reply notification opens channel thread and highlights parent', async ({ browser, request }) => {
  const emailA = `e2e-ca-${Date.now()}@example.com`
  const emailB = `e2e-cb-${Date.now()}@example.com`
  const pw = 'Password123!'

  const a = await registerAndLogin(request, emailA, pw, 'e2e_ca')
  const b = await registerAndLogin(request, emailB, pw, 'e2e_cb')

  const contextA = await browser.newContext()
  const pageA = await contextA.newPage()
  await pageA.addInitScript((t, meData) => {
    try { localStorage.setItem('access_token', t) } catch (e) {}
    try { localStorage.setItem('auth-storage', JSON.stringify({ state: { token: t, user: meData, isAuthenticated: true } })) } catch (e) {}
  }, a.token, a.me)

  const contextB = await browser.newContext()
  const pageB = await contextB.newPage()
  await pageB.addInitScript((t, meData) => {
    try { localStorage.setItem('access_token', t) } catch (e) {}
    try { localStorage.setItem('auth-storage', JSON.stringify({ state: { token: t, user: meData, isAuthenticated: true } })) } catch (e) {}
  }, b.token, b.me)

  await pageA.goto('/')
  await pageB.goto('/')

  // Create channel as A
  const createCh = await request.post(`${API_BASE}/api/channels/`, { headers: { authorization: `Bearer ${a.token}` }, data: { name: `e2e-channel-${Date.now()}`, display_name: 'E2E Channel', type: 'public', team_id: null } })
  expect(createCh.ok()).toBeTruthy()
  const ch = await createCh.json()

  // A posts parent message
  const parentResp = await request.post(`${API_BASE}/api/messages/`, { headers: { authorization: `Bearer ${a.token}` }, data: { content: 'channel parent', channel_id: ch.id } })
  expect(parentResp.ok()).toBeTruthy()
  const parent = await parentResp.json()

  // B replies to parent
  const replyResp = await request.post(`${API_BASE}/api/messages/`, { headers: { authorization: `Bearer ${b.token}` }, data: { content: 'channel reply', channel_id: ch.id, parent_id: parent.id } })
  expect(replyResp.ok()).toBeTruthy()
  const reply = await replyResp.json()

  // A should receive channel_reply toast
  const toastA = pageA.locator('div', { hasText: 'New reply from' })
  await expect(toastA).toBeVisible({ timeout: 5000 })
  await toastA.click()

  await expect(pageA).toHaveURL(new RegExp(`/channels/${ch.id}\?message=${parent.id}`))
  await expect(pageA.getByRole('heading', { name: 'Thread' })).toBeVisible({ timeout: 5000 })
  const parentEl = pageA.locator(`[data-message-id="${parent.id}"]`)
  await expect(parentEl).toBeVisible()
  await expect(parentEl).toHaveClass(/ring-2|ring-blue-400/)

  await contextA.close()
  await contextB.close()
})

// Suppression: if user already viewing same thread, no toast appears
test('Suppression: no toast if already viewing same thread', async ({ browser, request }) => {
  const emailA = `e2e-sa-${Date.now()}@example.com`
  const emailB = `e2e-sb-${Date.now()}@example.com`
  const pw = 'Password123!'

  const a = await registerAndLogin(request, emailA, pw, 'e2e_sa')
  const b = await registerAndLogin(request, emailB, pw, 'e2e_sb')

  const contextA = await browser.newContext()
  const pageA = await contextA.newPage()
  await pageA.addInitScript((t, meData) => {
    try { localStorage.setItem('access_token', t) } catch (e) {}
    try { localStorage.setItem('auth-storage', JSON.stringify({ state: { token: t, user: meData, isAuthenticated: true } })) } catch (e) {}
  }, a.token, a.me)

  const contextB = await browser.newContext()
  const pageB = await contextB.newPage()
  await pageB.addInitScript((t, meData) => {
    try { localStorage.setItem('access_token', t) } catch (e) {}
    try { localStorage.setItem('auth-storage', JSON.stringify({ state: { token: t, user: meData, isAuthenticated: true } })) } catch (e) {}
  }, b.token, b.me)

  await pageA.goto('/')
  await pageB.goto('/')

  // Create DM conv and parent message by A
  const convResp = await request.post(`${API_BASE}/api/direct-conversations/`, { headers: { authorization: `Bearer ${a.token}` }, data: { other_user_id: b.me.id } })
  expect(convResp.ok()).toBeTruthy()
  const conv = await convResp.json()

  const parentResp = await request.post(`${API_BASE}/api/direct-conversations/${conv.id}/messages`, { headers: { authorization: `Bearer ${a.token}` }, data: { content: 'suppress parent' } })
  expect(parentResp.ok()).toBeTruthy()
  const parent = await parentResp.json()

  // A navigates to the thread view for parent
  await pageA.goto(`/direct/${conv.id}?message=${parent.id}`)
  await expect(pageA.getByRole('heading', { name: 'Thread' })).toBeVisible()

  // B replies - A should NOT see a toast
  const replyResp = await request.post(`${API_BASE}/api/direct-conversations/${conv.id}/messages`, { headers: { authorization: `Bearer ${b.token}` }, data: { content: 'reply for suppression', parent_id: parent.id } })
  expect(replyResp.ok()).toBeTruthy()

  // Ensure no toast appears for A
  const toastA = pageA.locator('div', { hasText: 'New reply from' })
  await expect(toastA).toHaveCount(0)

  await contextA.close()
  await contextB.close()
})