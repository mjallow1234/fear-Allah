import { test } from '@playwright/test'

test.describe('U3.2: Channel metadata tests', () => {
  test.skip(
    'Channel metadata loads correctly (U3.2)',
    'Flaky in CI: channel header rendered asynchronously via TopBar without stable selectors. Covered by create-channel.spec.ts.'
  )
})
