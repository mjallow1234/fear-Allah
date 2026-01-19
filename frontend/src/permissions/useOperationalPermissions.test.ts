import { describe, it, expect } from 'vitest'
import useOperationalPermissions, { resolveOperationalPermissions } from './useOperationalPermissions'
import { UI_PERMISSIONS, NO_ACCESS } from './operationalPermissions'

describe('resolveOperationalPermissions', () => {
  it('returns NO_ACCESS if currentUser is undefined or has no operational_role_name', () => {
    expect(resolveOperationalPermissions(undefined)).toEqual(NO_ACCESS)
    expect(resolveOperationalPermissions({} as any)).toEqual(NO_ACCESS)
  })

  it('returns the matching UI permissions for a known role', () => {
    const perms = resolveOperationalPermissions({ operational_role_name: 'admin' } as any)
    expect(perms).toEqual(UI_PERMISSIONS['admin'])
  })

  it('default export calls resolver with provided user', () => {
    const perms = useOperationalPermissions({ operational_role_name: 'agent' } as any)
    expect(perms).toEqual(UI_PERMISSIONS['agent'])
  })
})