/**
 * Admin Form Builder Page
 * Phase 8 - Form Builder Routing
 * 
 * Admin-only page wrapper for the Form Builder.
 * Protects access and renders AdminFormBuilder/FormEditor components.
 */
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, AlertTriangle } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import AdminFormBuilder from '../components/forms/AdminFormBuilder'

export default function AdminFormBuilderPage() {
  const navigate = useNavigate()
  const { formId } = useParams<{ formId: string }>()
  const user = useAuthStore((state) => state.user)
  
  // Admin-only access check (system admins only)
  if (!user?.is_system_admin) {
    return (
      <div className="flex items-center justify-center h-full bg-[#313338]">
        <div className="text-center">
          <AlertTriangle className="mx-auto text-yellow-500 mb-4" size={48} />
          <h2 className="text-xl font-bold text-gray-200 mb-2">Access Denied</h2>
          <p className="text-gray-400 mb-4">You don't have permission to access the Form Builder.</p>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-[#5865f2] text-white rounded-lg hover:bg-[#4752c4] transition-colors"
          >
            Go Back
          </button>
        </div>
      </div>
    )
  }
  
  return (
    <div className="h-full flex flex-col bg-[#313338]">
      {/* Header */}
      <div className="h-12 px-4 flex items-center gap-4 border-b border-[#1f2023] bg-[#2b2d31]">
        <button
          onClick={() => navigate(-1)}
          className="p-1.5 text-[#b5bac1] hover:text-white transition-colors rounded hover:bg-[#35373c]"
        >
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-lg font-semibold text-white">Form Builder</h1>
      </div>
      
      {/* Content */}
      <div className="flex-1 overflow-hidden">
        <AdminFormBuilder initialFormId={formId ? parseInt(formId, 10) : undefined} />
      </div>
    </div>
  )
}
