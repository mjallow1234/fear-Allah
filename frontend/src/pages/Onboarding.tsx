import React, { useState } from 'react'
import api from '../services/api'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function OnboardingPage() {
  const navigate = useNavigate()
  const updateUser = useAuthStore((s) => s.updateUser)
  const [name, setName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const userTeamId = useAuthStore((s: any) => s.user?.team_id)

  // If user already has a team, navigate into app. This avoids polling or recheck loops.
  React.useEffect(() => {
    if (userTeamId) {
      navigate('/', { replace: true })
    }
  }, [userTeamId])

  // Check whether any teams exist in the system - if teams exist, creating the "first team"
  // is not allowed by the backend. Show an informative message instead of the create form.
  const [teamsExist, setTeamsExist] = React.useState<boolean | null>(null)
  React.useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const resp = await api.get('/api/teams')
        const list = Array.isArray(resp.data) ? resp.data : []
        if (mounted) setTeamsExist(list.length > 0)
      } catch (e) {
        // If we fail to fetch teams, treat as unknown and keep form available
        if (mounted) setTeamsExist(null)
      }
    })()
    return () => {
      mounted = false
    }
  }, [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const resp = await api.post('/api/onboarding/first-team', {
        name,
        display_name: displayName || undefined,
      })
      // Promote current user as system admin and set team_id from backend response
      const teamId = resp?.data?.id
      // Hotfix: cast update payload to any to avoid TS errors on environments where team_id is not yet in User type
      updateUser({ is_system_admin: true, team_id: teamId } as any)

      // Navigate into main app and stop further bootstrap checks
      navigate('/', { replace: true })
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to create team')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8 max-w-md mx-auto">
      <h1 className="text-2xl font-bold mb-4">Welcome — Create your first team</h1>
      <p className="mb-4">Create the organization team to get started. You will be made the system and team admin.</p>

      {teamsExist === true ? (
        <div className="p-4 bg-yellow-100 rounded text-sm">
          An organization already exists. You cannot create the first team here — please ask an existing
          organization administrator to add you to a team, or request an invitation.
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium">Team key (machine name)</label>
            <input value={name} onChange={(e) => setName(e.target.value)} required className="mt-1 block w-full p-2 border rounded" />
          </div>
          <div>
            <label className="block text-sm font-medium">Display name</label>
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} className="mt-1 block w-full p-2 border rounded" />
          </div>
          {error && <div className="text-red-600">{error}</div>}
          <div>
            <button className="px-4 py-2 bg-blue-600 text-white rounded" disabled={loading}>{loading ? 'Creating...' : 'Create team'}</button>
          </div>
        </form>
      )}
    </div>
  )
}
