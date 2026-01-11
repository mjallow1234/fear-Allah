import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'

export default function SetupPage() {
  const navigate = useNavigate()
  const [adminName, setAdminName] = useState('')
  const [adminEmail, setAdminEmail] = useState('')
  const [adminPassword, setAdminPassword] = useState('')
  const [teamName, setTeamName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const resp = await api.get('/api/system/status')
        if (!mounted) return
        if (resp.data?.initialized) {
          // Already initialized -> redirect to login
          navigate('/login', { replace: true })
        } else {
          setChecking(false)
        }
      } catch (e) {
        // If we can't fetch status, allow user to try setup but show warning
        setChecking(false)
      }
    })()
    return () => {
      mounted = false
    }
  }, [navigate])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await api.post('/api/setup/initialize', {
        admin_name: adminName,
        admin_email: adminEmail,
        admin_password: adminPassword,
        team_name: teamName,
      })
      // On success redirect to login
      navigate('/login', { replace: true })
    } catch (err: any) {
      const status = err?.response?.status
      if (status === 409) {
        setError('System already initialized')
      } else {
        setError(err?.response?.data?.detail || err.message || 'Failed to initialize system')
      }
    } finally {
      setLoading(false)
    }
  }

  if (checking) return <div className="p-8">Checking system state…</div>

  return (
    <div className="p-8 max-w-md mx-auto">
      <h1 className="text-2xl font-bold mb-4">Welcome – Set up your workspace</h1>
      <p className="mb-4">Create your admin user and initial workspace to get started.</p>

      {error && <div className="text-red-600 mb-4">{error}</div>}

      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium">Admin full name</label>
          <input required value={adminName} onChange={(e) => setAdminName(e.target.value)} className="mt-1 block w-full p-2 border rounded" />
        </div>
        <div>
          <label className="block text-sm font-medium">Admin email</label>
          <input required type="email" value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} className="mt-1 block w-full p-2 border rounded" />
        </div>
        <div>
          <label className="block text-sm font-medium">Admin password</label>
          <input required type="password" value={adminPassword} onChange={(e) => setAdminPassword(e.target.value)} className="mt-1 block w-full p-2 border rounded" />
        </div>
        <div>
          <label className="block text-sm font-medium">Team / workspace name</label>
          <input required value={teamName} onChange={(e) => setTeamName(e.target.value)} className="mt-1 block w-full p-2 border rounded" />
        </div>

        <div>
          <button className="px-4 py-2 bg-blue-600 text-white rounded" disabled={loading}>{loading ? 'Creating...' : 'Create workspace'}</button>
        </div>
      </form>
    </div>
  )
}
