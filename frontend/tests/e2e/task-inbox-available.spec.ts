import { test, expect } from '@playwright/test'

// Minimal e2e to verify Available Tasks network behavior
test('Available Tasks tab fetches available-tasks and Claim triggers POST claim', async ({ page }) => {
  // Intercept available-tasks GET and provide a sample task belonging to role foreman
  let getCalled = false
  await page.route('**/api/automation/available-tasks**', route => {
    getCalled = true
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ tasks: [{ id: 9999, title: 'Avail Task', description: 'Test', required_role: 'foreman', status: 'PENDING', created_by_id: 1, assignments: [], created_at: new Date().toISOString() }] })
    })
  })

  // Intercept claim POST
  let postCalled = false
  await page.route('**/api/automation/tasks/9999/claim', async route => {
    postCalled = true
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 9999 }) })
  })

  // Navigate to the Task Inbox page
  await page.goto('/')
  // Click Available tab
  await page.click('text=Available')

  // Verify GET was called
  expect(getCalled).toBe(true)

  // Wait for rendered Claim button and click it
  await page.waitForSelector('text=Claim')
  await page.click('text=Claim')

  // Verify POST was called
  expect(postCalled).toBe(true)
})