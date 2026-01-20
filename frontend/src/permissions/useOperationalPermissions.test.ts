import { describe, it, expect, beforeEach } from 'vitest'
import useOperationalPermissions from './useOperationalPermissions'
import { UI_PERMISSIONS, NO_ACCESS } from './uiPermissions'
import { useAuthStore } from '@/stores/authStore'

beforeEach(() => {
  // Reset auth store between tests
  useAuthStore.setState({ currentUser: null })
})

describe('useOperationalPermissions', () => {
  it('returns NO_ACCESS if currentUser is undefined or has no operational_role_name', () => {
    useAuthStore.setState({ currentUser: null })
    expect(useOperationalPermissions()).toEqual(NO_ACCESS)

    useAuthStore.setState({ currentUser: {} as any })
    expect(useOperationalPermissions()).toEqual(NO_ACCESS)
  })

  it('returns the matching UI permissions for a known role', () => {
    useAuthStore.setState({ currentUser: { operational_role_name: 'admin' } as any })
    expect(useOperationalPermissions()).toEqual(UI_PERMISSIONS['admin'])
  })

  it('returns the correct permissions for agent role', () => {
    useAuthStore.setState({ currentUser: { operational_role_name: 'agent' } as any })
    expect(useOperationalPermissions()).toEqual(UI_PERMISSIONS['agent'])
  })
})