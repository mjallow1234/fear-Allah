/**
 * DynamicFormModal Component
 * Phase 8 - Form Builder Integration
 * 
 * Modal wrapper for DynamicForm to replace hardcoded forms.
 * Provides the same interface as SalesForm, OrderForm, etc.
 */
import { useState, useEffect } from 'react'
import { X, Loader2, AlertCircle, Wand2 } from 'lucide-react'
import DynamicForm from './DynamicForm'
import formsApi from '../../services/formsApi'
import type { FormSubmission } from '../../types/forms'
import { extractAxiosError } from '../../utils/errorUtils'

interface DynamicFormModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: (result: FormSubmission) => void
  formSlug: string
  title?: string
  fallbackComponent?: React.ReactNode
}

export default function DynamicFormModal({ 
  isOpen, 
  onClose, 
  onSuccess,
  formSlug,
  title,
  fallbackComponent
}: DynamicFormModalProps) {
  const [formExists, setFormExists] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Check if the dynamic form exists
  useEffect(() => {
    if (!isOpen) return
    
    const checkForm = async () => {
      setLoading(true)
      setError(null)
      try {
        await formsApi.getForm(formSlug)
        setFormExists(true)
      } catch (err: any) {
        if (err.response?.status === 404) {
          setFormExists(false)
        } else {
          setError(extractAxiosError(err, 'Failed to load form'))
          setFormExists(false)
        }
      } finally {
        setLoading(false)
      }
    }
    
    checkForm()
  }, [isOpen, formSlug])
  
  const handleSuccess = (result: FormSubmission) => {
    onSuccess?.(result)
    onClose()
  }
  
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/70" 
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative w-full max-w-lg max-h-[90vh] overflow-y-auto bg-[#313338] rounded-xl shadow-2xl">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between p-4 border-b border-[#3f4147] bg-[#313338]">
          <div className="flex items-center gap-2">
            <Wand2 size={20} className="text-[#5865f2]" />
            <h2 className="text-lg font-semibold text-white">
              {title || formSlug.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-[#b5bac1] hover:text-white rounded hover:bg-[#35373c] transition-colors"
          >
            <X size={20} />
          </button>
        </div>
        
        {/* Content */}
        <div className="p-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="animate-spin text-[#5865f2]" size={32} />
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <AlertCircle className="text-red-400 mb-4" size={48} />
              <p className="text-red-400 mb-2">{error}</p>
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm text-white bg-[#5865f2] rounded-lg hover:bg-[#4752c4] transition-colors"
              >
                Close
              </button>
            </div>
          ) : formExists ? (
            <DynamicForm
              formSlug={formSlug}
              onSuccess={handleSuccess}
              onError={(msg) => setError(msg)}
              onCancel={onClose}
              submitButtonText="Submit"
            />
          ) : fallbackComponent ? (
            // Render fallback if form doesn't exist yet
            <>{fallbackComponent}</>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <AlertCircle className="text-yellow-400 mb-4" size={48} />
              <p className="text-[#b5bac1] mb-2">
                Dynamic form "{formSlug}" is not configured yet.
              </p>
              <p className="text-[#72767d] text-sm mb-4">
                An administrator needs to create this form in the Form Builder.
              </p>
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm text-white bg-[#5865f2] rounded-lg hover:bg-[#4752c4] transition-colors"
              >
                Close
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
