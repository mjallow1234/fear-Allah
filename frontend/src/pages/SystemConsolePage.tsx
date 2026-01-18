/**
 * System Console Page
 * Phase 8.4 - Mattermost-style System Console
 * Phase 8.6 - Permission Enforcement
 * 
 * Admin-only page with tabs for:
 * - Users management
 * - Roles & Permissions
 * - System Settings
 * - Audit Log
 */
import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Users,
  Shield,
  Settings,
  FileText,
  BarChart3,
  Search,
  RefreshCw,
  Loader2,
  ChevronLeft,
  ChevronRight,
  MoreVertical,
  UserX,
  UserCheck,
  Key,
  LogOut,
  X,
  Check,
  AlertTriangle,
  Copy,
  Eye,
  Plus,
  Trash2,
  Edit,
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
  UserPlus,
  ToggleLeft,
  ToggleRight,
  Lock
} from 'lucide-react'
import clsx from 'clsx'
import { useAuthStore } from '../stores/authStore'
import { useSystemStore, SystemUser, RoleInfo, PermissionInfo } from '../stores/systemStore'
import { usePermissions, PERMISSIONS } from '../hooks/usePermissions'
import { extractAxiosError } from '../utils/errorUtils'
import api from '../services/api'

// === Tab Types ===
type TabId = 'overview' | 'users' | 'roles' | 'settings' | 'audit'

interface Tab {
  id: TabId
  label: string
  icon: React.ReactNode
  requiredPermission?: string  // Phase 8.6: Permission required to see tab
}

const ALL_TABS: Tab[] = [
  { id: 'overview', label: 'Overview', icon: <BarChart3 size={18} /> },
  { id: 'users', label: 'Users', icon: <Users size={18} />, requiredPermission: PERMISSIONS.MANAGE_USERS },
  { id: 'roles', label: 'Roles & Permissions', icon: <Shield size={18} />, requiredPermission: PERMISSIONS.MANAGE_ROLES },
  { id: 'settings', label: 'System Settings', icon: <Settings size={18} />, requiredPermission: PERMISSIONS.MANAGE_SETTINGS },
  { id: 'audit', label: 'Audit Log', icon: <FileText size={18} />, requiredPermission: PERMISSIONS.VIEW_AUDIT },
]

// === Helper Components ===

function StatCard({ label, value, subtext, color = 'blue' }: { 
  label: string
  value: number | string
  subtext?: string
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple'
}) {
  const colorClasses = {
    blue: 'text-blue-400 bg-blue-500/20',
    green: 'text-green-400 bg-green-500/20',
    yellow: 'text-yellow-400 bg-yellow-500/20',
    red: 'text-red-400 bg-red-500/20',
    purple: 'text-purple-400 bg-purple-500/20',
  }
  
  return (
    <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
      <div className="text-sm text-gray-400 mb-1">{label}</div>
      <div className={clsx('text-2xl font-bold', colorClasses[color].split(' ')[0])}>
        {value}
      </div>
      {subtext && <div className="text-xs text-gray-500 mt-1">{subtext}</div>}
    </div>
  )
}

// Phase 8.6: Read-only placeholder for tabs without permission
function ReadOnlyTab({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-center">
      <Lock className="text-gray-500 mb-4" size={48} />
      <h3 className="text-lg font-semibold text-gray-300 mb-2">Read-Only</h3>
      <p className="text-gray-500 max-w-md">{message}</p>
    </div>
  )
}

// === Overview Tab ===

function OverviewTab() {
  const { stats, statsLoading, fetchStats } = useSystemStore()
  
  useEffect(() => {
    fetchStats()
  }, [fetchStats])
  
  if (statsLoading || !stats) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-blue-500" size={32} />
      </div>
    )
  }
  
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-200">System Overview</h2>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard 
          label="Total Users" 
          value={stats.users.total} 
          color="blue"
        />
        <StatCard 
          label="Active Users" 
          value={stats.users.active}
          subtext={`${Math.round((stats.users.active / stats.users.total) * 100)}% of total`}
          color="green"
        />
        <StatCard 
          label="Administrators" 
          value={stats.users.admins} 
          color="purple"
        />
        <StatCard 
          label="Banned Users" 
          value={stats.users.banned} 
          color="red"
        />
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard 
          label="Channels" 
          value={stats.channels.total} 
          color="blue"
        />
        <StatCard 
          label="Messages" 
          value={stats.messages.total.toLocaleString()} 
          color="green"
        />
        <StatCard 
          label="Teams" 
          value={stats.teams.total} 
          color="yellow"
        />
        <StatCard 
          label="Audit Events (24h)" 
          value={stats.audit.last_24h} 
          color="purple"
        />
      </div>
    </div>
  )
}

// === Users Tab ===

// Phase 8.5.3: Enhanced User Action Menu with safety guards
// Phase 8.6: Permission enforcement
function UserActionMenu({ user, onClose }: { user: SystemUser; onClose: () => void }) {
  const { setUserStatus, setUserAdmin, resetUserPassword, forceLogoutUser, stats } = useSystemStore()
  const currentUser = useAuthStore(s => s.user)
  const [tempPassword, setTempPassword] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmAction, setConfirmAction] = useState<string | null>(null)
  
  // Phase 8.6: Permission check
  const { hasPermission } = usePermissions()
  const canManageUsers = hasPermission(PERMISSIONS.MANAGE_USERS)
  
  const isSelf = currentUser?.id === user.id
  const isLastAdmin = stats?.users.admins === 1 && user.is_system_admin
  
  const handleToggleActive = async () => {
    if (confirmAction !== 'toggle-active') {
      setConfirmAction('toggle-active')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await setUserStatus(user.id, !user.is_active)
      onClose()
    } catch (err: unknown) {
      setError(extractAxiosError(err, 'Failed to update user status'))
    } finally {
      setLoading(false)
      setConfirmAction(null)
    }
  }
  
  const handleToggleAdmin = async () => {
    if (confirmAction !== 'toggle-admin') {
      setConfirmAction('toggle-admin')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await setUserAdmin(user.id, !user.is_system_admin)
      onClose()
    } catch (err: unknown) {
      setError(extractAxiosError(err, 'Failed to update admin status'))
    } finally {
      setLoading(false)
      setConfirmAction(null)
    }
  }
  
  const handleResetPassword = async () => {
    if (confirmAction !== 'reset-password') {
      setConfirmAction('reset-password')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const password = await resetUserPassword(user.id)
      setTempPassword(password)
    } catch (err: unknown) {
      setError(extractAxiosError(err, 'Failed to reset password'))
    } finally {
      setLoading(false)
      setConfirmAction(null)
    }
  }
  
  const handleForceLogout = async () => {
    if (confirmAction !== 'force-logout') {
      setConfirmAction('force-logout')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await forceLogoutUser(user.id)
      onClose()
    } catch (err: unknown) {
      setError(extractAxiosError(err, 'Failed to force logout'))
    } finally {
      setLoading(false)
      setConfirmAction(null)
    }
  }

  // --- Operational Role management ---
  const { operationalRoles, fetchOperationalRoles, assignOperationalRole } = useSystemStore()
  const [showOpModal, setShowOpModal] = useState(false)
  const [selectedOpRole, setSelectedOpRole] = useState<number | null>(null)
  const openOpModal = async () => {
    setError(null)
    setLoading(true)
    try {
      await fetchOperationalRoles(true)
      // Fetch user detail to get current operational role
      const resp = await api.get(`/api/system/users/${user.id}`)
      setSelectedOpRole(resp.data.operational_role_id || null)
      setShowOpModal(true)
    } catch (err: unknown) {
      setError(extractAxiosError(err, 'Failed to load operational roles'))
    } finally {
      setLoading(false)
    }
  }

  const handleSaveOperationalRole = async () => {
    setLoading(true)
    setError(null)
    try {
      await assignOperationalRole(user.id, selectedOpRole)
      setShowOpModal(false)
      onClose()
    } catch (err: unknown) {
      setError(extractAxiosError(err, 'Failed to set operational role'))
    } finally {
      setLoading(false)
    }
  }
  
  const copyToClipboard = () => {
    if (tempPassword) {
      navigator.clipboard.writeText(tempPassword)
    }
  }
  
  // Password reset success view
  if (tempPassword) {
    return (
      <div className="absolute right-0 top-full mt-1 w-80 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50 p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-green-400 flex items-center gap-2">
            <Check size={16} />
            Password Reset
          </span>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X size={16} />
          </button>
        </div>
        <div className="text-xs text-gray-400 mb-2">
          Temporary password for <span className="text-gray-200">{user.username}</span>:
        </div>
        <div className="flex items-center gap-2 bg-gray-900 rounded p-2">
          <code className="flex-1 text-green-400 font-mono text-sm break-all">{tempPassword}</code>
          <button 
            onClick={copyToClipboard}
            className="text-gray-400 hover:text-white p-1"
            title="Copy to clipboard"
          >
            <Copy size={14} />
          </button>
        </div>
        <div className="text-xs text-yellow-400 mt-2 flex items-center gap-1">
          <AlertTriangle size={12} />
          User must change password on next login.
        </div>
      </div>
    )
  }
  
  // Confirmation dialog
  if (confirmAction) {
    const confirmMessages: Record<string, { title: string; message: string; color: string }> = {
      'toggle-active': {
        title: user.is_active ? 'Deactivate User?' : 'Activate User?',
        message: user.is_active 
          ? `${user.username} will be unable to log in.`
          : `${user.username} will be able to log in again.`,
        color: user.is_active ? 'red' : 'green'
      },
      'toggle-admin': {
        title: user.is_system_admin ? 'Remove Admin?' : 'Make Admin?',
        message: user.is_system_admin
          ? `${user.username} will lose system admin privileges.`
          : `${user.username} will gain full system admin access.`,
        color: user.is_system_admin ? 'yellow' : 'purple'
      },
      'reset-password': {
        title: 'Reset Password?',
        message: `A new temporary password will be generated for ${user.username}.`,
        color: 'blue'
      },
      'force-logout': {
        title: 'Force Logout?',
        message: `${user.username} will be logged out of all sessions.`,
        color: 'yellow'
      }
    }
    
    const config = confirmMessages[confirmAction]
    
    return (
      <div className="absolute right-0 top-full mt-1 w-72 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50 p-4">
        <div className="flex items-center justify-between mb-3">
          <span className={clsx(
            'text-sm font-medium',
            config.color === 'red' && 'text-red-400',
            config.color === 'yellow' && 'text-yellow-400',
            config.color === 'green' && 'text-green-400',
            config.color === 'blue' && 'text-blue-400',
            config.color === 'purple' && 'text-purple-400'
          )}>
            {config.title}
          </span>
          <button onClick={() => setConfirmAction(null)} className="text-gray-400 hover:text-white">
            <X size={16} />
          </button>
        </div>
        <p className="text-sm text-gray-400 mb-4">{config.message}</p>
        {error && (
          <div className="mb-3 p-2 bg-red-500/20 border border-red-500/50 rounded text-xs text-red-400">
            {error}
          </div>
        )}
        <div className="flex gap-2">
          <button
            onClick={() => setConfirmAction(null)}
            className="flex-1 px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm"
            disabled={loading}
          >
            Cancel
          </button>
          <button
            onClick={
              confirmAction === 'toggle-active' ? handleToggleActive :
              confirmAction === 'toggle-admin' ? handleToggleAdmin :
              confirmAction === 'reset-password' ? handleResetPassword :
              handleForceLogout
            }
            disabled={loading}
            className={clsx(
              'flex-1 px-3 py-2 rounded text-sm font-medium flex items-center justify-center gap-2',
              config.color === 'red' && 'bg-red-600 hover:bg-red-700',
              config.color === 'yellow' && 'bg-yellow-600 hover:bg-yellow-700',
              config.color === 'green' && 'bg-green-600 hover:bg-green-700',
              config.color === 'blue' && 'bg-blue-600 hover:bg-blue-700',
              config.color === 'purple' && 'bg-purple-600 hover:bg-purple-700'
            )}
          >
            {loading && <Loader2 className="animate-spin" size={14} />}
            Confirm
          </button>
        </div>
      </div>
    )
  }
  
  return (
    <div className="absolute right-0 top-full mt-1 w-56 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50 overflow-hidden">
      {loading && (
        <div className="absolute inset-0 bg-gray-900/50 flex items-center justify-center z-10">
          <Loader2 className="animate-spin text-blue-500" size={20} />
        </div>
      )}
      
      {error && (
        <div className="p-2 bg-red-500/20 border-b border-red-500/50 text-xs text-red-400">
          {error}
        </div>
      )}
      
      {/* Phase 8.6: Show read-only message if no permission */}
      {!canManageUsers && (
        <div className="px-3 py-2.5 text-sm text-gray-500 flex items-center gap-2 border-b border-gray-700/50">
          <Lock size={14} />
          <span>Read-only access</span>
        </div>
      )}
      
      {/* Activate/Deactivate */}
      <button
        onClick={handleToggleActive}
        disabled={!canManageUsers || isSelf}
        title={!canManageUsers ? "No permission" : isSelf ? "Cannot deactivate yourself" : undefined}
        className={clsx(
          'w-full px-3 py-2.5 text-left text-sm flex items-center gap-2 hover:bg-gray-700/50 transition-colors',
          (!canManageUsers || isSelf) && 'opacity-50 cursor-not-allowed'
        )}
      >
        {user.is_active ? <UserX size={14} className="text-red-400" /> : <UserCheck size={14} className="text-green-400" />}
        <span>{user.is_active ? 'Deactivate User' : 'Activate User'}</span>
      </button>
      
      {/* Promote/Demote Admin */}
      <button
        onClick={handleToggleAdmin}
        disabled={!canManageUsers || isSelf || (isLastAdmin && user.is_system_admin)}
        title={
          !canManageUsers ? "No permission" :
          isSelf ? "Cannot change your own admin status" :
          isLastAdmin && user.is_system_admin ? "Cannot demote last admin" :
          undefined
        }
        className={clsx(
          'w-full px-3 py-2.5 text-left text-sm flex items-center gap-2 hover:bg-gray-700/50 transition-colors',
          (!canManageUsers || isSelf || (isLastAdmin && user.is_system_admin)) && 'opacity-50 cursor-not-allowed'
        )}
      >
        {user.is_system_admin ? (
          <>
            <ShieldOff size={14} className="text-yellow-400" />
            <span>Remove Admin</span>
          </>
        ) : (
          <>
            <ShieldCheck size={14} className="text-purple-400" />
            <span>Make Admin</span>
          </>
        )}
        {isLastAdmin && user.is_system_admin && (
          <span className="ml-auto text-xs text-yellow-500">Last admin</span>
        )}
      </button>
      
      <div className="border-t border-gray-700/50" />
      
      {/* Reset Password */}
      <button
        onClick={handleResetPassword}
        disabled={!canManageUsers}
        title={!canManageUsers ? "No permission" : undefined}
        className={clsx(
          'w-full px-3 py-2.5 text-left text-sm flex items-center gap-2 hover:bg-gray-700/50 transition-colors',
          !canManageUsers && 'opacity-50 cursor-not-allowed'
        )}
      >
        <Key size={14} className="text-blue-400" />
        <span>Reset Password</span>
      </button>

      {/* Change Operational Role */}
      <button
        onClick={openOpModal}
        disabled={!canManageUsers}
        title={!canManageUsers ? "No permission" : undefined}
        className={clsx(
          'w-full px-3 py-2.5 text-left text-sm flex items-center gap-2 hover:bg-gray-700/50 transition-colors',
          !canManageUsers && 'opacity-50 cursor-not-allowed'
        )}
      >
        <Edit size={14} className="text-gray-400" />
        <span>Change Operational Role</span>
      </button>

      {/* Force Logout */}
      <button
        onClick={handleForceLogout}
        disabled={!canManageUsers || isSelf}
        title={!canManageUsers ? "No permission" : isSelf ? "Cannot force logout yourself" : undefined}
        className={clsx(
          'w-full px-3 py-2.5 text-left text-sm flex items-center gap-2 hover:bg-gray-700/50 transition-colors',
          (!canManageUsers || isSelf) && 'opacity-50 cursor-not-allowed'
        )}
      >
        <LogOut size={14} className="text-yellow-400" />
        <span>Force Logout</span>
      </button>

      {/* Operational Role Modal */}
      {showOpModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 rounded-lg border border-gray-700 w-full max-w-md overflow-hidden p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-semibold text-gray-200">Change Operational Role</h3>
              <button onClick={() => setShowOpModal(false)} className="text-gray-400 hover:text-white">Cancel</button>
            </div>
            {error && <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-sm text-red-400 mb-3">{error}</div>}
            <div className="mb-3">
              <label className="block text-sm font-medium text-gray-300 mb-1">Operational Role</label>
              <select value={selectedOpRole || ''} onChange={e => setSelectedOpRole(e.target.value ? Number(e.target.value) : null)} className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-blue-500">
                <option value="">None</option>
                {operationalRoles.map(r => (
                  <option key={r.id} value={r.id}>{r.name.replace(/_/g,' ').replace(/\b\w/g, c => c.toUpperCase())}</option>
                ))}
              </select>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowOpModal(false)} className="px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm">Cancel</button>
              <button onClick={handleSaveOperationalRole} className="px-3 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm">Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function UserRow({ user }: { user: SystemUser }) {
  const [showMenu, setShowMenu] = useState(false)
  
  return (
    <tr className="border-b border-gray-700/50 hover:bg-gray-800/30">
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400 font-medium">
            {user.username[0].toUpperCase()}
          </div>
          <div>
            <div className="font-medium text-gray-200">{user.username}</div>
            <div className="text-xs text-gray-500">{user.email}</div>
          </div>
        </div>
      </td>
      <td className="px-4 py-3">
        <span className={clsx(
          'px-2 py-0.5 rounded text-xs font-medium',
          user.role === 'system_admin' && 'bg-purple-500/20 text-purple-400',
          user.role === 'team_admin' && 'bg-blue-500/20 text-blue-400',
          user.role === 'member' && 'bg-gray-500/20 text-gray-400',
          user.role === 'guest' && 'bg-yellow-500/20 text-yellow-400',
        )}>
          {user.role}
        </span>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          {user.is_system_admin && (
            <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-400 text-xs">
              Admin
            </span>
          )}
          {user.is_active && !user.is_banned ? (
            <span className="px-2 py-0.5 rounded bg-green-500/20 text-green-400 text-xs">
              Active
            </span>
          ) : user.is_banned ? (
            <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs">
              Banned
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded bg-gray-500/20 text-gray-400 text-xs">
              Inactive
            </span>
          )}
        </div>
      </td>
      <td className="px-4 py-3 text-xs text-gray-500">
        {user.created_at ? new Date(user.created_at).toLocaleDateString() : '-'}
      </td>
      <td className="px-4 py-3 relative">
        <button
          onClick={() => setShowMenu(!showMenu)}
          className="p-1.5 hover:bg-gray-700 rounded text-gray-400 hover:text-white"
        >
          <MoreVertical size={16} />
        </button>
        {showMenu && <UserActionMenu user={user} onClose={() => setShowMenu(false)} />}
      </td>
    </tr>
  )
}

// === Phase 8.5.5: Create User Modal ===
interface CreateUserFormData {
  username: string
  email: string
  role_id: number | null
  operational_role_id: number | null
  is_system_admin: boolean
  active: boolean
}

interface CreatedUserResult {
  user: {
    id: number
    username: string
    email: string
    active: boolean
    is_system_admin: boolean
    role_id: number
    role_name: string
    operational_role_id?: number | null
    operational_role_name?: string | null
  }
  temporary_password: string
}

function CreateUserModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: (result: CreatedUserResult) => void }) {
const { createUser, roles, operationalRoles, fetchRoles, fetchOperationalRoles } = useSystemStore()
  const [formData, setFormData] = useState<CreateUserFormData>({
    username: '',
    email: '',
    role_id: null,
    operational_role_id: null,
    is_system_admin: false,
    active: true,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  useEffect(() => {
    fetchRoles()
    fetchOperationalRoles()
  }, [fetchRoles, fetchOperationalRoles])
  
  useEffect(() => {
    if (!formData.operational_role_id && operationalRoles && operationalRoles.length) {
      const agent = operationalRoles.find(r => r.name === 'agent')
      if (agent) setFormData(d => ({ ...d, operational_role_id: agent.id }))
    }
    // Default system role to the first available if not selected
    if (!formData.role_id && roles && roles.length) {
      setFormData(d => ({ ...d, role_id: roles[0].id }))
    }
  }, [operationalRoles, roles])
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validation
    if (!formData.username.trim()) {
      setError('Username is required')
      return
    }
    if (formData.username.length < 3) {
      setError('Username must be at least 3 characters')
      return
    }
    if (!formData.role_id) {
      setError('Please select a role')
      return
    }
    
    setLoading(true)
    setError(null)
    
    try {
      const result = await createUser({
        username: formData.username.trim(),
        email: formData.email.trim() || null,
        role_id: formData.role_id,
        operational_role_id: formData.operational_role_id,
        is_system_admin: formData.is_system_admin,
        active: formData.active,
      })
      onSuccess(result)
    } catch (err: unknown) {
      setError(extractAxiosError(err, 'Failed to create user'))
    } finally {
      setLoading(false)
    }
  }
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-lg border border-gray-700 w-full max-w-md overflow-hidden">
        <div className="p-4 border-b border-gray-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center">
              <UserPlus className="text-blue-400" size={20} />
            </div>
            <h3 className="text-lg font-semibold text-gray-200">Create New User</h3>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X size={20} />
          </button>
        </div>
        
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {error && (
            <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-sm text-red-400 flex items-center gap-2">
              <AlertTriangle size={16} />
              {error}
            </div>
          )}
          
          {/* Username */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Username <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={formData.username}
              onChange={e => setFormData({ ...formData, username: e.target.value })}
              placeholder="e.g., john_doe"
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-blue-500"
              autoFocus
            />
            <p className="text-xs text-gray-500 mt-1">3-50 characters</p>
          </div>
          
          {/* Email */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Email
            </label>
            <input
              type="email"
              value={formData.email}
              onChange={e => setFormData({ ...formData, email: e.target.value })}
              placeholder="john@example.com"
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">Optional but recommended</p>
          </div>
          
          {/* System Role Dropdown (unchanged) */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              System Role <span className="text-red-400">*</span>
            </label>
            <select
              value={formData.role_id || ''}
              onChange={e => setFormData({ ...formData, role_id: e.target.value ? Number(e.target.value) : null })}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-blue-500"
            >
              <option value="">Select a system role...</option>
              {roles.map(role => (
                <option key={role.id} value={role.id}>
                  {role.name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())} {role.is_system && '(System)'}
                </option>
              ))}
            </select>
          </div>

          {/* Operational Role Dropdown (new) */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Operational Role
            </label>
            <select
              value={formData.operational_role_id || ''}
              onChange={e => setFormData({ ...formData, operational_role_id: e.target.value ? Number(e.target.value) : null })}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-blue-500"
            >
              <option value="">None</option>
              {operationalRoles.map(role => (
                <option key={role.id} value={role.id}>
                  {role.name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                </option>
              ))}
            </select>
          </div>
          
          {/* Toggles */}
          <div className="space-y-3 pt-2">
            {/* System Admin Toggle */}
            <div className="flex items-center justify-between p-3 bg-gray-900/50 rounded-lg border border-gray-700">
              <div>
                <div className="text-sm font-medium text-gray-300 flex items-center gap-2">
                  <Shield size={14} className="text-purple-400" />
                  System Admin
                </div>
                <p className="text-xs text-gray-500">Full system access</p>
              </div>
              <button
                type="button"
                onClick={() => setFormData({ ...formData, is_system_admin: !formData.is_system_admin })}
                className="focus:outline-none"
              >
                {formData.is_system_admin ? (
                  <ToggleRight size={28} className="text-purple-400" />
                ) : (
                  <ToggleLeft size={28} className="text-gray-500" />
                )}
              </button>
            </div>
            
            {/* Active Toggle */}
            <div className="flex items-center justify-between p-3 bg-gray-900/50 rounded-lg border border-gray-700">
              <div>
                <div className="text-sm font-medium text-gray-300 flex items-center gap-2">
                  <UserCheck size={14} className="text-green-400" />
                  Active
                </div>
                <p className="text-xs text-gray-500">User can log in</p>
              </div>
              <button
                type="button"
                onClick={() => setFormData({ ...formData, active: !formData.active })}
                className="focus:outline-none"
              >
                {formData.active ? (
                  <ToggleRight size={28} className="text-green-400" />
                ) : (
                  <ToggleLeft size={28} className="text-gray-500" />
                )}
              </button>
            </div>
            
            {/* Warning for inactive admin */}
            {formData.is_system_admin && !formData.active && (
              <div className="p-2 bg-yellow-500/20 border border-yellow-500/50 rounded text-xs text-yellow-400 flex items-center gap-2">
                <AlertTriangle size={14} />
                Creating an inactive admin user
              </div>
            )}
          </div>
        </form>
        
        <div className="p-4 border-t border-gray-700 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading || !formData.username.trim() || !formData.role_id}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium flex items-center gap-2"
          >
            {loading && <Loader2 className="animate-spin" size={14} />}
            Create User
          </button>
        </div>
      </div>
    </div>
  )
}

// === Phase 8.5.5: User Created Success Modal ===
function UserCreatedSuccessModal({ result, onClose }: { result: CreatedUserResult; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  
  const handleCopyPassword = async () => {
    try {
      await navigator.clipboard.writeText(result.temporary_password)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-lg border border-gray-700 w-full max-w-md overflow-hidden">
        <div className="p-4 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center">
              <Check className="text-green-400" size={20} />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-200">User Created Successfully</h3>
              <p className="text-sm text-gray-400">@{result.user.username}</p>
            </div>
          </div>
        </div>
        
        <div className="p-4 space-y-4">
          {/* Warning Banner */}
          <div className="p-3 bg-yellow-500/20 border border-yellow-500/50 rounded-lg">
            <div className="flex items-center gap-2 text-yellow-400 font-medium mb-1">
              <AlertTriangle size={16} />
              Important: Save this password now
            </div>
            <p className="text-xs text-yellow-400/80">
              This password is shown once and cannot be retrieved later.
            </p>
          </div>
          
          {/* User Details */}
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between py-2 border-b border-gray-700">
              <span className="text-gray-400">Username</span>
              <span className="text-gray-200 font-medium">{result.user.username}</span>
            </div>
            {result.user.email && (
              <div className="flex items-center justify-between py-2 border-b border-gray-700">
                <span className="text-gray-400">Email</span>
                <span className="text-gray-200">{result.user.email}</span>
              </div>
            )}
            <div className="flex items-center justify-between py-2 border-b border-gray-700">
              <span className="text-gray-400">System Role</span>
              <span className="text-gray-200">{result.user.role_name.replace(/_/g, ' ')}</span>
            </div>
            {result.user.operational_role_name && (
              <div className="flex items-center justify-between py-2 border-b border-gray-700">
                <span className="text-gray-400">Operational Role</span>
                <span className="text-gray-200">{result.user.operational_role_name.replace(/_/g, ' ')}</span>
              </div>
            )}
            <div className="flex items-center justify-between py-2 border-b border-gray-700">
              <span className="text-gray-400">System Admin</span>
              <span className={result.user.is_system_admin ? 'text-purple-400' : 'text-gray-500'}>
                {result.user.is_system_admin ? 'Yes' : 'No'}
              </span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-700">
              <span className="text-gray-400">Status</span>
              <span className={result.user.active ? 'text-green-400' : 'text-gray-500'}>
                {result.user.active ? 'Active' : 'Inactive'}
              </span>
            </div>
          </div>
          
          {/* Temporary Password */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              <Key size={14} className="inline mr-1" />
              Temporary Password
            </label>
            <div className="flex items-center gap-2">
              <code className="flex-1 px-3 py-2.5 bg-gray-900 border border-gray-700 rounded-lg text-sm font-mono text-green-400 select-all">
                {result.temporary_password}
              </code>
              <button
                onClick={handleCopyPassword}
                className={clsx(
                  'px-3 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors',
                  copied 
                    ? 'bg-green-600 text-white' 
                    : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                )}
              >
                {copied ? <Check size={16} /> : <Copy size={16} />}
                {copied ? 'Copied!' : 'Copy'}
              </button>
            </div>
          </div>
        </div>
        
        <div className="p-4 border-t border-gray-700">
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}

function UsersTab() {
  const {
    users, usersTotal, usersPage, usersLimit, userFilters,
    usersLoading, setUsersPage, setUserFilters, clearUserFilters, fetchUsers
  } = useSystemStore()
  const [searchInput, setSearchInput] = useState(userFilters.search || '')
  
  // Phase 8.6: Permission check for user management
  const { hasPermission } = usePermissions()
  const canManageUsers = hasPermission(PERMISSIONS.MANAGE_USERS)
  
  // Phase 8.5.5: Create user modal state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createdUser, setCreatedUser] = useState<CreatedUserResult | null>(null)
  
  useEffect(() => {
    fetchUsers()
  }, [fetchUsers])
  
  const handleSearch = () => {
    setUserFilters({ search: searchInput })
  }
  
  const handleUserCreated = (result: CreatedUserResult) => {
    setShowCreateModal(false)
    setCreatedUser(result)
  }
  
  const totalPages = Math.ceil(usersTotal / usersLimit)
  
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-semibold text-gray-200">User Management</h2>
          {/* Phase 8.6: Show read-only or actions enabled badge */}
          {canManageUsers ? (
            <span className="px-2 py-0.5 bg-green-500/20 rounded text-xs text-green-400 flex items-center gap-1">
              <Check className="w-3 h-3" />
              Actions Enabled
            </span>
          ) : (
            <span className="px-2 py-0.5 bg-gray-500/20 rounded text-xs text-gray-400 flex items-center gap-1">
              <Lock className="w-3 h-3" />
              Read-only
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchUsers(true)}
            disabled={usersLoading}
            className="p-2 hover:bg-gray-700 rounded text-gray-400 hover:text-white"
            title="Refresh"
          >
            <RefreshCw size={18} className={clsx(usersLoading && 'animate-spin')} />
          </button>
          {/* Phase 8.6: Only show Create User button if has permission */}
          {canManageUsers && (
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-3 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium flex items-center gap-2"
            >
              <UserPlus size={16} />
              Create User
            </button>
          )}
        </div>
      </div>
      
      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex-1 min-w-[200px] max-w-md relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={16} />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search users..."
            className="w-full pl-9 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-blue-500"
          />
        </div>
        
        <select
          value={userFilters.role || ''}
          onChange={(e) => setUserFilters({ role: e.target.value })}
          className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-blue-500"
        >
          <option value="">All Roles</option>
          <option value="system_admin">System Admin</option>
          <option value="team_admin">Team Admin</option>
          <option value="member">Member</option>
          <option value="guest">Guest</option>
        </select>
        
        <select
          value={userFilters.status || ''}
          onChange={(e) => setUserFilters({ status: e.target.value })}
          className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-blue-500"
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="banned">Banned</option>
        </select>
        
        {(userFilters.search || userFilters.role || userFilters.status) && (
          <button
            onClick={clearUserFilters}
            className="px-3 py-2 text-sm text-gray-400 hover:text-white"
          >
            Clear Filters
          </button>
        )}
      </div>
      
      {/* Table */}
      <div className="bg-gray-800/50 rounded-lg border border-gray-700/50 overflow-hidden">
        {usersLoading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="animate-spin text-blue-500" size={32} />
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-900/50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">User</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Role</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Created</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase w-12"></th>
              </tr>
            </thead>
            <tbody>
              {users.map(user => (
                <UserRow key={user.id} user={user} />
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                    No users found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
      
      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-400">
          <span>
            Showing {((usersPage - 1) * usersLimit) + 1} - {Math.min(usersPage * usersLimit, usersTotal)} of {usersTotal}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setUsersPage(usersPage - 1)}
              disabled={usersPage === 1}
              className="p-1.5 hover:bg-gray-700 rounded disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={18} />
            </button>
            <span>Page {usersPage} of {totalPages}</span>
            <button
              onClick={() => setUsersPage(usersPage + 1)}
              disabled={usersPage >= totalPages}
              className="p-1.5 hover:bg-gray-700 rounded disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronRight size={18} />
            </button>
          </div>
        </div>
      )}
      
      {/* Phase 8.5.5: Create User Modal */}
      {showCreateModal && (
        <CreateUserModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={handleUserCreated}
        />
      )}
      
      {/* Phase 8.5.5: User Created Success Modal */}
      {createdUser && (
        <UserCreatedSuccessModal
          result={createdUser}
          onClose={() => setCreatedUser(null)}
        />
      )}
    </div>
  )
}

// === Roles & Permissions Tab ===

// Phase 8.5.3: Permission categories for grouped display
const PERMISSION_CATEGORIES: Record<string, { label: string; color: string }> = {
  system: { label: 'System', color: 'purple' },
  user: { label: 'Users', color: 'blue' },
  channel: { label: 'Channels', color: 'green' },
  message: { label: 'Messages', color: 'cyan' },
  sales: { label: 'Sales', color: 'orange' },
  orders: { label: 'Orders', color: 'yellow' },
}

function getPermissionCategory(key: string): string {
  const parts = key.split('.')
  return parts[0] || 'other'
}

function groupPermissionsByCategory(permissions: PermissionInfo[]): Record<string, PermissionInfo[]> {
  const groups: Record<string, PermissionInfo[]> = {}
  permissions.forEach(perm => {
    const category = getPermissionCategory(perm.key)
    if (!groups[category]) groups[category] = []
    groups[category].push(perm)
  })
  return groups
}

// Phase 8.5.3: Create Role Modal
function CreateRoleModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const { createRole, permissions } = useSystemStore()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const groupedPermissions = groupPermissionsByCategory(permissions)
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Role name is required')
      return
    }
    
    setLoading(true)
    setError(null)
    try {
      await createRole(name.toLowerCase().replace(/\s+/g, '_'), description, selectedPermissions)
      onSuccess()
      onClose()
    } catch (err: unknown) {
      setError(extractAxiosError(err, 'Failed to create role'))
    } finally {
      setLoading(false)
    }
  }
  
  const togglePermission = (key: string) => {
    setSelectedPermissions(prev => 
      prev.includes(key) ? prev.filter(p => p !== key) : [...prev, key]
    )
  }
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-lg border border-gray-700 w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="p-4 border-b border-gray-700 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-200">Create New Role</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X size={20} />
          </button>
        </div>
        
        <form onSubmit={handleSubmit} className="flex-1 overflow-auto p-4 space-y-4">
          {error && (
            <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-sm text-red-400 flex items-center gap-2">
              <AlertTriangle size={16} />
              {error}
            </div>
          )}
          
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Role Name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g., sales_manager"
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">Lowercase letters, numbers, and underscores only</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Description</label>
            <input
              type="text"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Brief description of this role"
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Permissions ({selectedPermissions.length} selected)
            </label>
            <div className="space-y-4 max-h-64 overflow-auto p-3 bg-gray-900/50 rounded-lg border border-gray-700">
              {Object.entries(groupedPermissions).map(([category, perms]) => (
                <div key={category}>
                  <div className="text-xs font-medium text-gray-400 uppercase mb-2">
                    {PERMISSION_CATEGORIES[category]?.label || category}
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {perms.map(perm => (
                      <label
                        key={perm.key}
                        className={clsx(
                          'flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors',
                          selectedPermissions.includes(perm.key)
                            ? 'bg-blue-500/20 text-blue-300'
                            : 'hover:bg-gray-800 text-gray-400'
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={selectedPermissions.includes(perm.key)}
                          onChange={() => togglePermission(perm.key)}
                          className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
                        />
                        <span className="text-sm">{perm.key}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </form>
        
        <div className="p-4 border-t border-gray-700 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading || !name.trim()}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium flex items-center gap-2"
          >
            {loading && <Loader2 className="animate-spin" size={14} />}
            Create Role
          </button>
        </div>
      </div>
    </div>
  )
}

// Phase 8.5.3: Edit Permissions Modal
function EditPermissionsModal({ role, onClose, onSuccess }: { role: RoleInfo; onClose: () => void; onSuccess: () => void }) {
  const { updateRolePermissionsById, permissions } = useSystemStore()
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>(role.permissions)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<{ added: string[]; removed: string[] } | null>(null)
  
  const groupedPermissions = groupPermissionsByCategory(permissions)
  
  // Required permissions for system_admin
  const requiredPermissions = role.name === 'system_admin' 
    ? ['system.manage_users', 'system.manage_roles', 'system.view_audit', 'system.manage_settings']
    : []
  
  const handleSave = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await updateRolePermissionsById(role.id, selectedPermissions)
      if (res.changed) {
        setResult({ added: res.added, removed: res.removed })
      } else {
        onClose()
      }
    } catch (err: unknown) {
      setError(extractAxiosError(err, 'Failed to update permissions'))
    } finally {
      setLoading(false)
    }
  }
  
  const togglePermission = (key: string) => {
    // Don't allow removing required permissions
    if (requiredPermissions.includes(key) && selectedPermissions.includes(key)) {
      return
    }
    setSelectedPermissions(prev => 
      prev.includes(key) ? prev.filter(p => p !== key) : [...prev, key]
    )
  }
  
  // Success view
  if (result) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div className="bg-gray-800 rounded-lg border border-gray-700 w-full max-w-md p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center">
              <Check className="text-green-400" size={20} />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-200">Permissions Updated</h3>
              <p className="text-sm text-gray-400">Changes to {role.name}</p>
            </div>
          </div>
          
          {result.added.length > 0 && (
            <div className="mb-3">
              <div className="text-xs text-green-400 font-medium mb-1">+ Added ({result.added.length})</div>
              <div className="flex flex-wrap gap-1">
                {result.added.map(p => (
                  <span key={p} className="px-2 py-0.5 bg-green-500/20 text-green-300 rounded text-xs">{p}</span>
                ))}
              </div>
            </div>
          )}
          
          {result.removed.length > 0 && (
            <div className="mb-3">
              <div className="text-xs text-red-400 font-medium mb-1">- Removed ({result.removed.length})</div>
              <div className="flex flex-wrap gap-1">
                {result.removed.map(p => (
                  <span key={p} className="px-2 py-0.5 bg-red-500/20 text-red-300 rounded text-xs">{p}</span>
                ))}
              </div>
            </div>
          )}
          
          <button
            onClick={() => { onSuccess(); onClose(); }}
            className="w-full mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium"
          >
            Done
          </button>
        </div>
      </div>
    )
  }
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-lg border border-gray-700 w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="p-4 border-b border-gray-700 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-200">Edit Permissions</h3>
            <p className="text-sm text-gray-400">Role: {role.name}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X size={20} />
          </button>
        </div>
        
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {error && (
            <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-sm text-red-400 flex items-center gap-2">
              <AlertTriangle size={16} />
              {error}
            </div>
          )}
          
          {role.is_system && role.name === 'system_admin' && (
            <div className="p-3 bg-yellow-500/20 border border-yellow-500/50 rounded-lg text-sm text-yellow-400 flex items-center gap-2">
              <ShieldAlert size={16} />
              System admin role must retain core system permissions.
            </div>
          )}
          
          <div className="space-y-4">
            {Object.entries(groupedPermissions).map(([category, perms]) => (
              <div key={category} className="p-3 bg-gray-900/50 rounded-lg border border-gray-700">
                <div className="text-xs font-medium text-gray-400 uppercase mb-3 flex items-center gap-2">
                  <Shield size={12} />
                  {PERMISSION_CATEGORIES[category]?.label || category}
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {perms.map(perm => {
                    const isRequired = requiredPermissions.includes(perm.key)
                    const isSelected = selectedPermissions.includes(perm.key)
                    return (
                      <label
                        key={perm.key}
                        className={clsx(
                          'flex items-center gap-2 px-2 py-1.5 rounded transition-colors',
                          isRequired ? 'cursor-not-allowed' : 'cursor-pointer',
                          isSelected
                            ? 'bg-blue-500/20 text-blue-300'
                            : 'hover:bg-gray-800 text-gray-400'
                        )}
                        title={isRequired ? 'Required for system admin' : perm.description || undefined}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => togglePermission(perm.key)}
                          disabled={isRequired}
                          className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 disabled:opacity-50"
                        />
                        <span className="text-sm flex-1">{perm.key}</span>
                        {isRequired && (
                          <span className="text-xs text-yellow-500">Required</span>
                        )}
                      </label>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
        
        <div className="p-4 border-t border-gray-700 flex items-center justify-between">
          <div className="text-sm text-gray-400">
            {selectedPermissions.length} permissions selected
          </div>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg text-sm font-medium flex items-center gap-2"
            >
              {loading && <Loader2 className="animate-spin" size={14} />}
              Save Changes
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// Phase 8.5.3: Enhanced Role Card
function RoleCard({ role, onEdit, onDelete, canManage = true }: { role: RoleInfo; onEdit: () => void; onDelete: () => void; canManage?: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const { deleteRole } = useSystemStore()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const handleDelete = async () => {
    setLoading(true)
    setError(null)
    try {
      await deleteRole(role.id)
      setShowDeleteConfirm(false)
      onDelete()
    } catch (err: unknown) {
      setError(extractAxiosError(err, 'Failed to delete role'))
    } finally {
      setLoading(false)
    }
  }
  
  return (
    <div className="bg-gray-800/50 rounded-lg border border-gray-700/50 overflow-hidden">
      <div className="px-4 py-3 flex items-center justify-between">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-3 flex-1 text-left"
        >
          <Shield className={clsx(
            'text-gray-400',
            role.name === 'system_admin' && 'text-purple-400',
            role.name === 'default' && 'text-green-400'
          )} size={18} />
          <div>
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-200">{role.name.replace(/_/g, ' ')}</span>
              {role.is_system && (
                <span className="px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 rounded text-xs">System</span>
              )}
            </div>
            {role.description && (
              <div className="text-xs text-gray-500">{role.description}</div>
            )}
          </div>
          <span className="text-xs text-gray-500 ml-2">({role.permissions.length} permissions)</span>
        </button>
        
        <div className="flex items-center gap-2">
          {/* Phase 8.6: Only show Edit button if has permission */}
          {canManage && (
            <button
              onClick={(e) => { e.stopPropagation(); onEdit(); }}
              className="p-1.5 hover:bg-gray-700 rounded text-gray-400 hover:text-white"
              title="Edit permissions"
            >
              <Edit size={14} />
            </button>
          )}
          
          {/* Phase 8.6: Only show Delete button if has permission and not system role */}
          {canManage && !role.is_system && (
            <button
              onClick={(e) => { e.stopPropagation(); setShowDeleteConfirm(true); }}
              className="p-1.5 hover:bg-red-500/20 rounded text-gray-400 hover:text-red-400"
              title="Delete role"
            >
              <Trash2 size={14} />
            </button>
          )}
          
          <ChevronRight
            size={18}
            className={clsx('text-gray-500 transition-transform ml-2', expanded && 'rotate-90')}
          />
        </div>
      </div>
      
      {expanded && (
        <div className="px-4 py-3 border-t border-gray-700/50 bg-gray-900/30">
          <div className="text-xs text-gray-400 mb-2">Permissions:</div>
          <div className="flex flex-wrap gap-2">
            {role.permissions.map(perm => (
              <span
                key={perm}
                className={clsx(
                  'px-2 py-1 rounded text-xs',
                  perm.startsWith('system.') && 'bg-purple-500/20 text-purple-300',
                  perm.startsWith('user.') && 'bg-blue-500/20 text-blue-300',
                  perm.startsWith('channel.') && 'bg-green-500/20 text-green-300',
                  perm.startsWith('message.') && 'bg-cyan-500/20 text-cyan-300',
                  perm.startsWith('sales.') && 'bg-orange-500/20 text-orange-300',
                  perm.startsWith('orders.') && 'bg-yellow-500/20 text-yellow-300',
                  !['system.', 'user.', 'channel.', 'message.', 'sales.', 'orders.'].some(p => perm.startsWith(p)) && 'bg-gray-700/50 text-gray-300'
                )}
              >
                {perm}
              </span>
            ))}
            {role.permissions.length === 0 && (
              <span className="text-gray-500 text-sm">No permissions assigned</span>
            )}
          </div>
        </div>
      )}
      
      {/* Delete Confirmation Dialog */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 rounded-lg border border-gray-700 w-full max-w-sm p-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center">
                <Trash2 className="text-red-400" size={20} />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-200">Delete Role?</h3>
                <p className="text-sm text-gray-400">{role.name}</p>
              </div>
            </div>
            
            {error && (
              <div className="mb-4 p-2 bg-red-500/20 border border-red-500/50 rounded text-xs text-red-400">
                {error}
              </div>
            )}
            
            <p className="text-sm text-gray-400 mb-4">
              This action cannot be undone. Users assigned to this role will need to be reassigned.
            </p>
            
            <div className="flex gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                disabled={loading}
                className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={loading}
                className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-sm font-medium flex items-center justify-center gap-2"
              >
                {loading && <Loader2 className="animate-spin" size={14} />}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function RolesTab() {
  const { roles, permissions, rolesLoading, fetchRoles, fetchPermissions } = useSystemStore()
  const { hasPermission } = usePermissions()
  const canManageRoles = hasPermission(PERMISSIONS.MANAGE_ROLES)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingRole, setEditingRole] = useState<RoleInfo | null>(null)
  
  useEffect(() => {
    fetchRoles()
    fetchPermissions()
  }, [fetchRoles, fetchPermissions])
  
  const handleRefresh = () => {
    fetchRoles(true)
    fetchPermissions(true)
  }
  
  if (rolesLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-blue-500" size={32} />
      </div>
    )
  }
  
  // Separate system and custom roles
  const systemRoles = roles.filter(r => r.is_system)
  const customRoles = roles.filter(r => !r.is_system)
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-semibold text-gray-200">Roles & Permissions</h2>
          {/* Phase 8.6: Show read-only badge if no manage permission */}
          {canManageRoles ? (
            <span className="px-2 py-0.5 bg-green-500/20 rounded text-xs text-green-400 flex items-center gap-1">
              <Check className="w-3 h-3" />
              Management Enabled
            </span>
          ) : (
            <span className="px-2 py-0.5 bg-gray-500/20 rounded text-xs text-gray-400 flex items-center gap-1">
              <Lock className="w-3 h-3" />
              Read-only
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRefresh}
            className="p-2 hover:bg-gray-700 rounded text-gray-400 hover:text-white"
            title="Refresh"
          >
            <RefreshCw size={18} />
          </button>
          {/* Phase 8.6: Only show Create Role button if has permission */}
          {canManageRoles && (
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-3 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium flex items-center gap-2"
            >
              <Plus size={16} />
              Create Role
            </button>
          )}
        </div>
      </div>
      
      {/* System Roles */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-gray-400 uppercase">System Roles</h3>
          <span className="px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 rounded text-xs">Protected</span>
        </div>
        {systemRoles.map(role => (
          <RoleCard
            key={role.id}
            role={role}
            onEdit={() => setEditingRole(role)}
            onDelete={handleRefresh}
            canManage={canManageRoles}
          />
        ))}
      </div>
      
      {/* Custom Roles */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-gray-400 uppercase">Custom Roles</h3>
        {customRoles.length === 0 ? (
          <div className="p-8 bg-gray-800/50 rounded-lg border border-gray-700/50 text-center">
            <Shield className="mx-auto text-gray-500 mb-3" size={32} />
            <p className="text-gray-400 text-sm mb-3">No custom roles yet</p>
            {/* Phase 8.6: Only show Create button if has permission */}
            {canManageRoles && (
              <button
                onClick={() => setShowCreateModal(true)}
                className="px-3 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium inline-flex items-center gap-2"
              >
                <Plus size={16} />
                Create Your First Role
              </button>
            )}
          </div>
        ) : (
          customRoles.map(role => (
            <RoleCard
              key={role.id}
              role={role}
              onEdit={() => setEditingRole(role)}
              onDelete={handleRefresh}
              canManage={canManageRoles}
            />
          ))
        )}
      </div>
      
      {/* All Permissions Reference */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-gray-400 uppercase">Available Permissions</h3>
        <div className="bg-gray-800/50 rounded-lg border border-gray-700/50 p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(groupPermissionsByCategory(permissions)).map(([category, perms]) => (
              <div key={category} className="p-3 bg-gray-900/50 rounded border border-gray-700/50">
                <div className="text-xs font-medium text-gray-400 uppercase mb-2 flex items-center gap-2">
                  <div className={clsx(
                    'w-2 h-2 rounded-full',
                    category === 'system' && 'bg-purple-400',
                    category === 'user' && 'bg-blue-400',
                    category === 'channel' && 'bg-green-400',
                    category === 'message' && 'bg-cyan-400',
                    category === 'sales' && 'bg-orange-400',
                    category === 'orders' && 'bg-yellow-400'
                  )} />
                  {PERMISSION_CATEGORIES[category]?.label || category}
                </div>
                <div className="space-y-1">
                  {perms.map(perm => (
                    <div key={perm.key} className="text-sm text-gray-300" title={perm.description || ''}>
                      {perm.key}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      {/* Modals */}
      {showCreateModal && (
        <CreateRoleModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={handleRefresh}
        />
      )}
      
      {editingRole && (
        <EditPermissionsModal
          role={editingRole}
          onClose={() => setEditingRole(null)}
          onSuccess={handleRefresh}
        />
      )}
    </div>
  )
}

// === Settings Tab ===

function SettingsTab() {
  const { settings, settingsLoading, fetchSettings } = useSystemStore()
  
  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])
  
  if (settingsLoading || !settings) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-blue-500" size={32} />
      </div>
    )
  }
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-200">System Settings</h2>
        <span className="text-xs text-gray-500">(Read-only view)</span>
      </div>
      
      {/* General */}
      <div className="bg-gray-800/50 rounded-lg border border-gray-700/50 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-700/50 bg-gray-900/30">
          <h3 className="font-medium text-gray-300">General</h3>
        </div>
        <div className="p-4 space-y-3">
          <div className="flex justify-between">
            <span className="text-gray-400">Application Name</span>
            <span className="text-gray-200">{settings.app_name}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Environment</span>
            <span className={clsx(
              'px-2 py-0.5 rounded text-xs font-medium',
              settings.environment === 'production' && 'bg-green-500/20 text-green-400',
              settings.environment === 'staging' && 'bg-yellow-500/20 text-yellow-400',
              settings.environment === 'development' && 'bg-blue-500/20 text-blue-400',
            )}>
              {settings.environment}
            </span>
          </div>
        </div>
      </div>
      
      {/* Feature Flags */}
      <div className="bg-gray-800/50 rounded-lg border border-gray-700/50 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-700/50 bg-gray-900/30">
          <h3 className="font-medium text-gray-300">Feature Flags</h3>
        </div>
        <div className="p-4 space-y-3">
          {Object.entries(settings.features).map(([key, value]) => (
            <div key={key} className="flex justify-between items-center">
              <span className="text-gray-400">{key.replace(/_/g, ' ')}</span>
              {value ? (
                <span className="flex items-center gap-1 text-green-400 text-sm">
                  <Check size={14} /> Enabled
                </span>
              ) : (
                <span className="flex items-center gap-1 text-gray-500 text-sm">
                  <X size={14} /> Disabled
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
      
      {/* Upload Limits */}
      <div className="bg-gray-800/50 rounded-lg border border-gray-700/50 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-700/50 bg-gray-900/30">
          <h3 className="font-medium text-gray-300">Upload Limits</h3>
        </div>
        <div className="p-4 space-y-3">
          <div className="flex justify-between">
            <span className="text-gray-400">Max Upload Size</span>
            <span className="text-gray-200">{settings.upload_limits.max_upload_mb} MB</span>
          </div>
        </div>
      </div>
      
      {/* Rate Limits */}
      <div className="bg-gray-800/50 rounded-lg border border-gray-700/50 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-700/50 bg-gray-900/30">
          <h3 className="font-medium text-gray-300">Rate Limits</h3>
        </div>
        <div className="p-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-400 text-left">
                <th className="pb-2">Endpoint</th>
                <th className="pb-2">Anonymous</th>
                <th className="pb-2">Authenticated</th>
                <th className="pb-2">Admin</th>
              </tr>
            </thead>
            <tbody className="text-gray-300">
              {Object.entries(settings.rate_limits).map(([endpoint, limits]) => (
                <tr key={endpoint} className="border-t border-gray-700/50">
                  <td className="py-2 capitalize">{endpoint}</td>
                  <td className="py-2 font-mono text-xs">{limits.anonymous}</td>
                  <td className="py-2 font-mono text-xs">{limits.authenticated}</td>
                  <td className="py-2 font-mono text-xs">{limits.admin}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// === Audit Tab (Link to existing page) ===

function AuditTab() {
  const navigate = useNavigate()
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-200">Audit Log</h2>
        {/* Read-only badge (Phase 8.4.2) */}
        <span className="px-2 py-1 bg-gray-700/50 rounded text-xs text-gray-400 flex items-center gap-1">
          <Eye className="w-3 h-3" />
          Read-only (Phase 8.4)
        </span>
      </div>
      
      <div className="bg-gray-800/50 rounded-lg border border-gray-700/50 p-8 text-center">
        <FileText className="mx-auto text-gray-500 mb-4" size={48} />
        <p className="text-gray-400 mb-4">
          View detailed audit logs with filtering and pagination.
        </p>
        <button
          onClick={() => navigate('/system/audit')}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-medium transition-colors"
        >
          Open Audit Log
        </button>
      </div>
    </div>
  )
}

// === Main Page ===

export default function SystemConsolePage() {
  const navigate = useNavigate()
  const user = useAuthStore(s => s.user)
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  
  // Phase 8.6: Permission enforcement
  const { hasPermission, isSystemAdmin, isLoaded: permissionsLoaded } = usePermissions()
  
  // Phase 8.6: Filter tabs based on permissions
  const availableTabs = useMemo(() => {
    return ALL_TABS.filter(tab => {
      // Overview is always visible
      if (!tab.requiredPermission) return true
      // Check permission
      return hasPermission(tab.requiredPermission)
    })
  }, [hasPermission, permissionsLoaded])
  
  // Phase 8.4.4: Rate limit state from store
  const { rateLimited, rateLimitRetryAt, resetSessionFlags } = useSystemStore()
  
  // Calculate time remaining for rate limit
  const [retryCountdown, setRetryCountdown] = useState<number | null>(null)
  
  useEffect(() => {
    if (!rateLimited || !rateLimitRetryAt) {
      setRetryCountdown(null)
      return
    }
    
    const updateCountdown = () => {
      const remaining = Math.max(0, Math.ceil((rateLimitRetryAt - Date.now()) / 1000))
      setRetryCountdown(remaining > 0 ? remaining : null)
    }
    
    updateCountdown()
    const interval = setInterval(updateCountdown, 1000)
    return () => clearInterval(interval)
  }, [rateLimited, rateLimitRetryAt])
  
  // Check admin access - system admins always allowed, others need at least one permission
  useEffect(() => {
    if (!user?.is_system_admin && permissionsLoaded && availableTabs.length <= 1) {
      navigate('/')
    }
  }, [user, navigate, permissionsLoaded, availableTabs])
  
  // Phase 8.6: If active tab is no longer available, switch to first available
  useEffect(() => {
    if (permissionsLoaded && !availableTabs.find(t => t.id === activeTab)) {
      setActiveTab(availableTabs[0]?.id || 'overview')
    }
  }, [availableTabs, activeTab, permissionsLoaded])
  
  // Loading state while permissions load
  if (!permissionsLoaded) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900">
        <div className="text-center">
          <Loader2 className="mx-auto text-blue-500 animate-spin mb-4" size={32} />
          <p className="text-gray-400">Loading permissions...</p>
        </div>
      </div>
    )
  }
  
  // Access denied for non-admins with no permissions
  if (!isSystemAdmin && availableTabs.length <= 1) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900">
        <div className="text-center">
          <AlertTriangle className="mx-auto text-yellow-500 mb-4" size={48} />
          <h2 className="text-xl font-bold text-gray-200 mb-2">Access Denied</h2>
          <p className="text-gray-400">You don't have permission to access the System Console.</p>
        </div>
      </div>
    )
  }
  
  const handleManualRefresh = () => {
    resetSessionFlags()
    // Trigger re-fetch by changing tab momentarily
    const currentTab = activeTab
    setActiveTab('overview')
    setTimeout(() => setActiveTab(currentTab), 0)
  }
  
  // Phase 8.6: Check permission before rendering tab content
  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return <OverviewTab />
      case 'users':
        return hasPermission(PERMISSIONS.MANAGE_USERS) ? <UsersTab /> : <ReadOnlyTab message="You don't have permission to manage users." />
      case 'roles':
        return hasPermission(PERMISSIONS.MANAGE_ROLES) ? <RolesTab /> : <ReadOnlyTab message="You don't have permission to manage roles." />
      case 'settings':
        return hasPermission(PERMISSIONS.MANAGE_SETTINGS) ? <SettingsTab /> : <ReadOnlyTab message="You don't have permission to manage settings." />
      case 'audit':
        return hasPermission(PERMISSIONS.VIEW_AUDIT) ? <AuditTab /> : <ReadOnlyTab message="You don't have permission to view audit logs." />
      default:
        return null
    }
  }
  
  return (
    <div className="flex h-full bg-gray-900">
      {/* Sidebar */}
      <div className="w-64 flex-shrink-0 bg-gray-800/50 border-r border-gray-700/50">
        <div className="p-4 border-b border-gray-700/50">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 text-gray-400 hover:text-white text-sm"
          >
            <ArrowLeft size={16} />
            Back to Chat
          </button>
        </div>
        
        <div className="p-4">
          <h1 className="text-lg font-bold text-gray-200 mb-1">System Console</h1>
          <p className="text-xs text-gray-500">Manage your workspace</p>
        </div>
        
        <nav className="p-2">
          {availableTabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors',
                activeTab === tab.id
                  ? 'bg-blue-600/20 text-blue-400'
                  : 'text-gray-400 hover:bg-gray-700/50 hover:text-white'
              )}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </nav>
        
        {/* Manual Refresh Button */}
        <div className="p-2 mt-4 border-t border-gray-700/50">
          <button
            onClick={handleManualRefresh}
            disabled={rateLimited && retryCountdown !== null}
            className={clsx(
              'w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors',
              rateLimited && retryCountdown !== null
                ? 'bg-gray-700/30 text-gray-500 cursor-not-allowed'
                : 'bg-gray-700/50 text-gray-300 hover:bg-gray-700 hover:text-white'
            )}
          >
            <RefreshCw size={14} />
            Refresh Data
          </button>
        </div>
      </div>
      
      {/* Main Content */}
      <div className="flex-1 overflow-auto">
        <div className="max-w-5xl mx-auto p-6">
          {/* Phase 8.4.4: Rate Limit Banner */}
          {rateLimited && (
            <div className="mb-4 p-3 bg-yellow-500/20 border border-yellow-500/50 rounded-lg flex items-center gap-3">
              <AlertTriangle className="text-yellow-500 flex-shrink-0" size={20} />
              <div className="flex-1">
                <span className="text-yellow-200 text-sm">
                  System data temporarily rate-limited. Please wait a moment.
                </span>
                {retryCountdown !== null && (
                  <span className="text-yellow-400 text-xs ml-2">
                    ({retryCountdown}s remaining)
                  </span>
                )}
              </div>
            </div>
          )}
          
          {renderTabContent()}
        </div>
      </div>
    </div>
  )
}
