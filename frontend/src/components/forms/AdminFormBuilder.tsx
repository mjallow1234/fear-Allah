/**
 * Admin Form Builder - Form Management Page
 * Phase 8 - Form Builder
 * 
 * Allows admins to create, edit, and manage dynamic forms.
 */
import { useState, useEffect } from 'react'
import { 
  Plus, 
  Search, 
  ChevronRight,
  Loader2,
  AlertCircle,
  FileText,
  Wand2
} from 'lucide-react'
import clsx from 'clsx'
import formsApi from '../../services/formsApi'
import type { Form, FormListItem } from '../../types/forms'
import FormEditor from './FormEditor'
import { extractAxiosError } from '../../utils/errorUtils'

// ============================================================================
// Types
// ============================================================================

interface FormListProps {
  forms: FormListItem[]
  selectedId?: number
  onSelect: (form: FormListItem) => void
  loading?: boolean
}

// ============================================================================
// Form List Component
// ============================================================================

function FormList({ forms, selectedId, onSelect, loading }: FormListProps) {
  const [search, setSearch] = useState('')
  
  const filteredForms = forms.filter(f => 
    f.name.toLowerCase().includes(search.toLowerCase()) ||
    f.slug.toLowerCase().includes(search.toLowerCase())
  )
  
  const categoryColors: Record<string, string> = {
    order: 'bg-blue-500/20 text-blue-400',
    sale: 'bg-green-500/20 text-green-400',
    inventory: 'bg-amber-500/20 text-amber-400',
    raw_material: 'bg-orange-500/20 text-orange-400',
    production: 'bg-purple-500/20 text-purple-400',
    custom: 'bg-gray-500/20 text-gray-400',
  }
  
  return (
    <div className="flex flex-col h-full">
      {/* Search */}
      <div className="p-3 border-b border-[#3f4147]">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#72767d]" />
          <input
            type="text"
            placeholder="Search forms..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] text-sm focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
          />
        </div>
      </div>
      
      {/* Form list */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center p-8">
            <Loader2 className="animate-spin text-[#5865f2]" size={24} />
          </div>
        ) : filteredForms.length === 0 ? (
          <div className="p-4 text-center text-[#72767d]">
            {search ? 'No forms match your search' : 'No forms yet'}
          </div>
        ) : (
          <ul className="p-2 space-y-1">
            {filteredForms.map((form) => (
              <li key={form.id}>
                <button
                  onClick={() => onSelect(form)}
                  className={clsx(
                    'w-full flex items-center gap-3 p-3 rounded-lg text-left transition-colors',
                    selectedId === form.id
                      ? 'bg-[#5865f2]/20 text-white'
                      : 'hover:bg-[#35373c] text-[#b5bac1]'
                  )}
                >
                  <FileText size={18} />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{form.name}</div>
                    <div className="text-xs text-[#72767d] truncate">{form.slug}</div>
                  </div>
                  <span className={clsx(
                    'text-xs px-2 py-0.5 rounded',
                    categoryColors[form.category] || categoryColors.custom
                  )}>
                    {form.category}
                  </span>
                  <ChevronRight size={16} className="text-[#72767d]" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

// ============================================================================
// Main Admin Form Builder Component
// ============================================================================

interface AdminFormBuilderProps {
  initialFormId?: number
}

export default function AdminFormBuilder({ initialFormId }: AdminFormBuilderProps) {
  const [forms, setForms] = useState<FormListItem[]>([])
  const [selectedForm, setSelectedForm] = useState<Form | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [seeding, setSeeding] = useState(false)
  
  // Fetch forms list
  const fetchForms = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await formsApi.adminListForms()
      setForms(data)
      return data
    } catch (err: any) {
      setError(extractAxiosError(err, 'Failed to load forms'))
      return []
    } finally {
      setLoading(false)
    }
  }
  
  // Seed default forms
  const handleSeedForms = async () => {
    try {
      setSeeding(true)
      setError(null)
      const result = await formsApi.adminSeedForms()
      console.log('Seed result:', result)
      await fetchForms()
    } catch (err: any) {
      setError(extractAxiosError(err, 'Failed to seed forms'))
    } finally {
      setSeeding(false)
    }
  }
  
  // On mount: fetch forms and optionally select initial form
  useEffect(() => {
    const init = async () => {
      const loadedForms = await fetchForms()
      if (initialFormId && loadedForms.length > 0) {
        // Load the specified form
        try {
          const fullForm = await formsApi.adminGetForm(initialFormId)
          setSelectedForm(fullForm)
        } catch (err: any) {
          setError(extractAxiosError(err, 'Failed to load form'))
        }
      }
    }
    init()
  }, [initialFormId])
  
  // Select form for editing
  const handleSelectForm = async (form: FormListItem) => {
    try {
      const fullForm = await formsApi.adminGetForm(form.id)
      setSelectedForm(fullForm)
      setCreating(false)
    } catch (err: any) {
      setError(extractAxiosError(err, 'Failed to load form'))
    }
  }
  
  // Create new form
  const handleCreate = () => {
    setSelectedForm(null)
    setCreating(true)
  }
  
  // Save form (create or update)
  const handleSave = async (formData: Partial<Form>) => {
    try {
      if (creating) {
        const newForm = await formsApi.adminCreateForm({
          name: formData.name!,
          slug: formData.slug!,
          category: formData.category!,
          description: formData.description,
          allowed_roles: formData.allowed_roles,
          service_target: formData.service_target,
          field_mapping: formData.field_mapping,
        })
        setSelectedForm(newForm)
        setCreating(false)
      } else if (selectedForm) {
        const updated = await formsApi.adminUpdateForm(selectedForm.id, formData)
        setSelectedForm(updated)
      }
      await fetchForms()
    } catch (err: any) {
      throw new Error(extractAxiosError(err, 'Failed to save form'))
    }
  }
  
  // Delete form
  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this form?')) return
    
    try {
      await formsApi.adminDeleteForm(id)
      if (selectedForm?.id === id) {
        setSelectedForm(null)
      }
      await fetchForms()
    } catch (err: any) {
      setError(extractAxiosError(err, 'Failed to delete form'))
    }
  }
  
  // Duplicate form
  const handleDuplicate = async (id: number) => {
    try {
      const form = await formsApi.adminGetForm(id)
      const newForm = await formsApi.adminCreateForm({
        name: `${form.name} (Copy)`,
        slug: `${form.slug}-copy`,
        category: form.category,
        description: form.description,
        allowed_roles: form.allowed_roles,
        service_target: form.service_target,
        field_mapping: form.field_mapping,
      })
      
      // Copy fields
      for (const field of form.fields) {
        await formsApi.adminAddField(newForm.id, {
          key: field.key,
          label: field.label,
          field_type: field.field_type,
          required: field.required,
          options: field.options,
          default_value: field.default_value,
          placeholder: field.placeholder,
          help_text: field.help_text,
          order_index: field.order_index,
          role_visibility: field.role_visibility,
          field_group: field.field_group,
          min_value: field.min_value,
          max_value: field.max_value,
          min_length: field.min_length,
          max_length: field.max_length,
          pattern: field.pattern,
        })
      }
      
      await fetchForms()
      setSelectedForm(await formsApi.adminGetForm(newForm.id))
    } catch (err: any) {
      setError(extractAxiosError(err, 'Failed to duplicate form'))
    }
  }
  
  // Close editor
  const handleClose = () => {
    setSelectedForm(null)
    setCreating(false)
  }
  
  return (
    <div className="flex h-full bg-[#2b2d31]">
      {/* Sidebar - Form List */}
      <div className="w-80 flex flex-col border-r border-[#3f4147] bg-[#313338]">
        <div className="p-4 border-b border-[#3f4147] flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Forms</h2>
          <button
            onClick={handleCreate}
            className="p-2 rounded-lg bg-[#5865f2] hover:bg-[#4752c4] text-white transition-colors"
            title="Create new form"
          >
            <Plus size={18} />
          </button>
        </div>
        
        <FormList
          forms={forms}
          selectedId={selectedForm?.id}
          onSelect={handleSelectForm}
          loading={loading}
        />
      </div>
      
      {/* Main content - Form Editor */}
      <div className="flex-1 overflow-hidden">
        {error && (
          <div className="m-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-2 text-red-400">
            <AlertCircle size={20} />
            <span>{error}</span>
            <button onClick={() => setError(null)} className="ml-auto hover:text-red-300">×</button>
          </div>
        )}
        
        {creating ? (
          <FormEditor
            isNew
            onSave={handleSave}
            onClose={handleClose}
          />
        ) : selectedForm ? (
          <FormEditor
            form={selectedForm}
            onSave={handleSave}
            onClose={handleClose}
            onDelete={() => handleDelete(selectedForm.id)}
            onDuplicate={() => handleDuplicate(selectedForm.id)}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-[#72767d]">
            <div className="text-center">
              <FileText size={48} className="mx-auto mb-4 opacity-50" />
              <p className="mb-4">Select a form to edit or create a new one</p>
              {forms.length === 0 && !loading && (
                <button
                  onClick={handleSeedForms}
                  disabled={seeding}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#5865f2] hover:bg-[#4752c4] text-white transition-colors disabled:opacity-50"
                >
                  {seeding ? (
                    <Loader2 size={18} className="animate-spin" />
                  ) : (
                    <Wand2 size={18} />
                  )}
                  {seeding ? 'Seeding...' : 'Seed Default Forms'}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
