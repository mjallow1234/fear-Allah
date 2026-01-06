/**
 * Form Editor Component
 * Phase 8 - Form Builder
 * 
 * Edit form properties and manage fields.
 */
import { useState } from 'react'
import { 
  Save, 
  Trash2, 
  Copy, 
  Plus,
  ChevronDown,
  ChevronUp,
  Edit2,
  X,
  Loader2,
  Settings,
  List,
  History,
  AlertCircle
} from 'lucide-react'
import clsx from 'clsx'
import formsApi from '../../services/formsApi'
import type { 
  Form, 
  FormField, 
  FormCategory
} from '../../types/forms'
import FieldEditor from './FieldEditor'
import { extractAxiosError } from '../../utils/errorUtils'

// ============================================================================
// Types
// ============================================================================

interface FormEditorProps {
  form?: Form
  isNew?: boolean
  onSave: (data: Partial<Form>) => Promise<void>
  onClose: () => void
  onDelete?: () => void
  onDuplicate?: () => void
}

type TabType = 'settings' | 'fields' | 'versions'

// ============================================================================
// Constants
// ============================================================================

const CATEGORIES: { value: FormCategory; label: string }[] = [
  { value: 'order', label: 'Order' },
  { value: 'sale', label: 'Sale' },
  { value: 'inventory', label: 'Inventory' },
  { value: 'raw_material', label: 'Raw Material' },
  { value: 'production', label: 'Production' },
  { value: 'custom', label: 'Custom' },
]

const SERVICE_TARGETS = [
  { value: '', label: 'None (No service routing)' },
  { value: 'sales', label: 'Sales Service' },
  { value: 'orders', label: 'Orders Service' },
  { value: 'inventory', label: 'Inventory Service' },
  { value: 'raw_materials', label: 'Raw Materials Service' },
  { value: 'production', label: 'Production Service' },
]

// ============================================================================
// Form Settings Tab
// ============================================================================

interface FormSettingsProps {
  name: string
  slug: string
  category: FormCategory
  description: string
  allowedRoles: string[]
  serviceTarget: string
  fieldMapping: Record<string, string>
  isNew?: boolean
  onChange: (field: string, value: any) => void
}

function FormSettings({
  name,
  slug,
  category,
  description,
  allowedRoles,
  serviceTarget,
  fieldMapping,
  isNew,
  onChange
}: FormSettingsProps) {
  const [rolesInput, setRolesInput] = useState(allowedRoles.join(', '))
  const [mappingJson, setMappingJson] = useState(JSON.stringify(fieldMapping || {}, null, 2))
  const [mappingError, setMappingError] = useState<string | null>(null)
  
  const handleRolesChange = (value: string) => {
    setRolesInput(value)
    const roles = value.split(',').map(r => r.trim()).filter(Boolean)
    onChange('allowed_roles', roles)
  }
  
  const handleMappingChange = (value: string) => {
    setMappingJson(value)
    try {
      const parsed = JSON.parse(value)
      setMappingError(null)
      onChange('field_mapping', parsed)
    } catch {
      setMappingError('Invalid JSON')
    }
  }
  
  return (
    <div className="space-y-6 p-6">
      <div className="grid grid-cols-2 gap-6">
        {/* Name */}
        <div>
          <label className="block text-sm font-medium text-[#b5bac1] mb-1">
            Form Name <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => onChange('name', e.target.value)}
            placeholder="Sales Order Form"
            className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
          />
        </div>
        
        {/* Slug */}
        <div>
          <label className="block text-sm font-medium text-[#b5bac1] mb-1">
            Slug <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={slug}
            onChange={(e) => onChange('slug', e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, '-'))}
            placeholder="sales-order"
            disabled={!isNew}
            className={clsx(
              'w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]',
              !isNew && 'opacity-50 cursor-not-allowed'
            )}
          />
          <p className="text-xs text-[#72767d] mt-1">URL-safe identifier (cannot be changed after creation)</p>
        </div>
        
        {/* Category */}
        <div>
          <label className="block text-sm font-medium text-[#b5bac1] mb-1">
            Category <span className="text-red-400">*</span>
          </label>
          <select
            value={category}
            onChange={(e) => onChange('category', e.target.value)}
            className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-[#5865f2] appearance-none"
          >
            {CATEGORIES.map((cat) => (
              <option key={cat.value} value={cat.value}>{cat.label}</option>
            ))}
          </select>
        </div>
        
        {/* Service Target */}
        <div>
          <label className="block text-sm font-medium text-[#b5bac1] mb-1">
            Service Target
          </label>
          <select
            value={serviceTarget || ''}
            onChange={(e) => onChange('service_target', e.target.value || null)}
            className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-[#5865f2] appearance-none"
          >
            {SERVICE_TARGETS.map((target) => (
              <option key={target.value} value={target.value}>{target.label}</option>
            ))}
          </select>
          <p className="text-xs text-[#72767d] mt-1">Where form submissions are routed</p>
        </div>
      </div>
      
      {/* Description */}
      <div>
        <label className="block text-sm font-medium text-[#b5bac1] mb-1">
          Description
        </label>
        <textarea
          value={description}
          onChange={(e) => onChange('description', e.target.value)}
          placeholder="Form description shown to users..."
          rows={3}
          className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2] resize-y"
        />
      </div>
      
      {/* Allowed Roles */}
      <div>
        <label className="block text-sm font-medium text-[#b5bac1] mb-1">
          Allowed Roles
        </label>
        <input
          type="text"
          value={rolesInput}
          onChange={(e) => handleRolesChange(e.target.value)}
          placeholder="admin, manager, sales (comma-separated, empty = all roles)"
          className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
        />
        <p className="text-xs text-[#72767d] mt-1">Leave empty to allow all roles</p>
      </div>
      
      {/* Field Mapping */}
      <div>
        <label className="block text-sm font-medium text-[#b5bac1] mb-1">
          Field Mapping (JSON)
        </label>
        <textarea
          value={mappingJson}
          onChange={(e) => handleMappingChange(e.target.value)}
          placeholder='{"form_field_key": "service_field_name"}'
          rows={5}
          className={clsx(
            'w-full px-3 py-2 bg-[#1e1f22] border rounded-lg text-white placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2] resize-y font-mono text-sm',
            mappingError ? 'border-red-500' : 'border-[#3f4147]'
          )}
        />
        {mappingError && (
          <p className="text-xs text-red-400 mt-1">{mappingError}</p>
        )}
        <p className="text-xs text-[#72767d] mt-1">Maps form field keys to service field names</p>
      </div>
    </div>
  )
}

// ============================================================================
// Fields Tab
// ============================================================================

interface FieldsListProps {
  formId: number
  fields: FormField[]
  onFieldsChange: () => void
}

function FieldsList({ formId, fields, onFieldsChange }: FieldsListProps) {
  const [editingField, setEditingField] = useState<FormField | null>(null)
  const [addingField, setAddingField] = useState(false)
  const [deleting, setDeleting] = useState<number | null>(null)
  
  const handleAddField = async (fieldData: Partial<FormField>) => {
    try {
      await formsApi.adminAddField(formId, fieldData as any)
      setAddingField(false)
      onFieldsChange()
    } catch (err: any) {
      throw new Error(extractAxiosError(err, 'Failed to add field'))
    }
  }
  
  const handleUpdateField = async (fieldData: Partial<FormField>) => {
    if (!editingField) return
    try {
      await formsApi.adminUpdateField(formId, editingField.id, fieldData)
      setEditingField(null)
      onFieldsChange()
    } catch (err: any) {
      throw new Error(extractAxiosError(err, 'Failed to update field'))
    }
  }
  
  const handleDeleteField = async (fieldId: number) => {
    if (!confirm('Are you sure you want to delete this field?')) return
    
    try {
      setDeleting(fieldId)
      await formsApi.adminDeleteField(formId, fieldId)
      onFieldsChange()
    } catch (err: any) {
      alert(extractAxiosError(err, 'Failed to delete field'))
    } finally {
      setDeleting(null)
    }
  }
  
  const handleMoveField = async (fieldId: number, direction: 'up' | 'down') => {
    const currentIndex = fields.findIndex(f => f.id === fieldId)
    if (currentIndex === -1) return
    
    const newIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1
    if (newIndex < 0 || newIndex >= fields.length) return
    
    // Swap order_index values
    const reordered = [...fields]
    const temp = reordered[currentIndex].order_index
    reordered[currentIndex].order_index = reordered[newIndex].order_index
    reordered[newIndex].order_index = temp
    
    // Build new order
    const newOrder = reordered
      .sort((a, b) => a.order_index - b.order_index)
      .map(f => f.id)
    
    try {
      await formsApi.adminReorderFields(formId, newOrder)
      onFieldsChange()
    } catch (err: any) {
      alert(extractAxiosError(err, 'Failed to reorder fields'))
    }
  }
  
  const fieldTypeLabels: Record<string, string> = {
    text: 'Text',
    number: 'Number',
    date: 'Date',
    datetime: 'Date & Time',
    select: 'Select',
    multiselect: 'Multi-Select',
    checkbox: 'Checkbox',
    textarea: 'Text Area',
    hidden: 'Hidden',
  }
  
  return (
    <div className="p-6">
      {/* Add field button */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-white">Form Fields</h3>
        <button
          onClick={() => setAddingField(true)}
          className="flex items-center gap-2 px-3 py-2 bg-[#5865f2] hover:bg-[#4752c4] text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          Add Field
        </button>
      </div>
      
      {/* Field editor modal */}
      {(addingField || editingField) && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[#313338] rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <FieldEditor
              field={editingField || undefined}
              onSave={editingField ? handleUpdateField : handleAddField}
              onCancel={() => {
                setEditingField(null)
                setAddingField(false)
              }}
            />
          </div>
        </div>
      )}
      
      {/* Fields list */}
      {fields.length === 0 ? (
        <div className="text-center py-8 text-[#72767d]">
          <List size={32} className="mx-auto mb-2 opacity-50" />
          <p>No fields yet. Add your first field to get started.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {fields.map((field, index) => (
            <div
              key={field.id}
              className="flex items-center gap-3 p-3 bg-[#2b2d31] rounded-lg border border-[#3f4147] group"
            >
              {/* Reorder buttons */}
              <div className="flex flex-col gap-0.5">
                <button
                  onClick={() => handleMoveField(field.id, 'up')}
                  disabled={index === 0}
                  className={clsx(
                    'p-0.5 rounded transition-colors',
                    index === 0 ? 'text-[#3f4147]' : 'text-[#72767d] hover:text-white hover:bg-[#35373c]'
                  )}
                >
                  <ChevronUp size={14} />
                </button>
                <button
                  onClick={() => handleMoveField(field.id, 'down')}
                  disabled={index === fields.length - 1}
                  className={clsx(
                    'p-0.5 rounded transition-colors',
                    index === fields.length - 1 ? 'text-[#3f4147]' : 'text-[#72767d] hover:text-white hover:bg-[#35373c]'
                  )}
                >
                  <ChevronDown size={14} />
                </button>
              </div>
              
              {/* Field info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-white">{field.label}</span>
                  {field.required && (
                    <span className="text-xs text-red-400">Required</span>
                  )}
                </div>
                <div className="flex items-center gap-2 text-xs text-[#72767d]">
                  <span className="font-mono">{field.key}</span>
                  <span>•</span>
                  <span>{fieldTypeLabels[field.field_type] || field.field_type}</span>
                  {field.field_group && (
                    <>
                      <span>•</span>
                      <span>Group: {field.field_group}</span>
                    </>
                  )}
                </div>
              </div>
              
              {/* Actions */}
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={() => setEditingField(field)}
                  className="p-2 text-[#72767d] hover:text-white hover:bg-[#35373c] rounded transition-colors"
                  title="Edit field"
                >
                  <Edit2 size={16} />
                </button>
                <button
                  onClick={() => handleDeleteField(field.id)}
                  disabled={deleting === field.id}
                  className="p-2 text-[#72767d] hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                  title="Delete field"
                >
                  {deleting === field.id ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Trash2 size={16} />
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Versions Tab
// ============================================================================

interface VersionsListProps {
  formId: number
  currentVersion: number
  onRestore: () => void
}

function VersionsList({ formId, currentVersion, onRestore }: VersionsListProps) {
  const [versions, setVersions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [restoring, setRestoring] = useState<number | null>(null)
  
  const fetchVersions = async () => {
    try {
      setLoading(true)
      const data = await formsApi.adminListVersions(formId)
      setVersions(data)
    } catch (err) {
      console.error('Failed to fetch versions:', err)
    } finally {
      setLoading(false)
    }
  }
  
  useState(() => {
    fetchVersions()
  })
  
  const handleRestore = async (version: number) => {
    if (!confirm(`Restore form to version ${version}? This will create a new version.`)) return
    
    try {
      setRestoring(version)
      await formsApi.adminRestoreVersion(formId, version)
      onRestore()
    } catch (err: any) {
      alert(extractAxiosError(err, 'Failed to restore version'))
    } finally {
      setRestoring(null)
    }
  }
  
  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="animate-spin text-[#5865f2]" size={24} />
      </div>
    )
  }
  
  return (
    <div className="p-6">
      <h3 className="text-lg font-medium text-white mb-4">Version History</h3>
      
      {versions.length === 0 ? (
        <div className="text-center py-8 text-[#72767d]">
          <History size={32} className="mx-auto mb-2 opacity-50" />
          <p>No version history yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {versions.map((v) => (
            <div
              key={v.id}
              className="flex items-center gap-3 p-3 bg-[#2b2d31] rounded-lg border border-[#3f4147]"
            >
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-white">Version {v.version}</span>
                  {v.version === currentVersion && (
                    <span className="text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded">
                      Current
                    </span>
                  )}
                </div>
                <div className="text-xs text-[#72767d]">
                  Created {new Date(v.created_at).toLocaleString()}
                </div>
              </div>
              
              {v.version !== currentVersion && (
                <button
                  onClick={() => handleRestore(v.version)}
                  disabled={restoring === v.version}
                  className="px-3 py-1.5 text-sm text-[#b5bac1] hover:text-white hover:bg-[#35373c] rounded transition-colors"
                >
                  {restoring === v.version ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    'Restore'
                  )}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Main Form Editor Component
// ============================================================================

export default function FormEditor({
  form,
  isNew,
  onSave,
  onClose,
  onDelete,
  onDuplicate
}: FormEditorProps) {
  const [activeTab, setActiveTab] = useState<TabType>('settings')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [localForm, setLocalForm] = useState<Form | null>(form || null)
  
  // Form state
  const [name, setName] = useState(form?.name || '')
  const [slug, setSlug] = useState(form?.slug || '')
  const [category, setCategory] = useState<FormCategory>(form?.category || 'custom')
  const [description, setDescription] = useState(form?.description || '')
  const [allowedRoles, setAllowedRoles] = useState<string[]>(form?.allowed_roles || [])
  const [serviceTarget, setServiceTarget] = useState(form?.service_target || '')
  const [fieldMapping, setFieldMapping] = useState<Record<string, string>>(form?.field_mapping || {})
  
  const handleChange = (field: string, value: any) => {
    switch (field) {
      case 'name': setName(value); break
      case 'slug': setSlug(value); break
      case 'category': setCategory(value); break
      case 'description': setDescription(value); break
      case 'allowed_roles': setAllowedRoles(value); break
      case 'service_target': setServiceTarget(value); break
      case 'field_mapping': setFieldMapping(value); break
    }
  }
  
  const handleSave = async () => {
    if (!name.trim() || !slug.trim()) {
      setError('Name and slug are required')
      return
    }
    
    try {
      setSaving(true)
      setError(null)
      await onSave({
        name,
        slug,
        category,
        description,
        allowed_roles: allowedRoles,
        service_target: serviceTarget || undefined,
        field_mapping: fieldMapping,
      })
    } catch (err: any) {
      setError(err.message || 'Failed to save form')
    } finally {
      setSaving(false)
    }
  }
  
  const handleFieldsChange = async () => {
    if (!form) return
    try {
      const updated = await formsApi.adminGetForm(form.id)
      setLocalForm(updated)
    } catch (err) {
      console.error('Failed to refresh form:', err)
    }
  }
  
  const handleVersionRestore = async () => {
    if (!form) return
    try {
      const updated = await formsApi.adminGetForm(form.id)
      setLocalForm(updated)
      // Update local state
      setName(updated.name)
      setSlug(updated.slug)
      setCategory(updated.category)
      setDescription(updated.description || '')
      setAllowedRoles(updated.allowed_roles || [])
      setServiceTarget(updated.service_target || '')
      setFieldMapping(updated.field_mapping || {})
    } catch (err) {
      console.error('Failed to refresh form:', err)
    }
  }
  
  const tabs: { id: TabType; label: string; icon: React.ReactNode }[] = [
    { id: 'settings', label: 'Settings', icon: <Settings size={16} /> },
    { id: 'fields', label: 'Fields', icon: <List size={16} /> },
    { id: 'versions', label: 'Versions', icon: <History size={16} /> },
  ]
  
  // Don't show fields/versions tabs for new forms
  const visibleTabs = isNew ? tabs.filter(t => t.id === 'settings') : tabs
  
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[#3f4147]">
        <div>
          <h2 className="text-lg font-semibold text-white">
            {isNew ? 'Create New Form' : `Edit: ${form?.name}`}
          </h2>
          {form && (
            <p className="text-sm text-[#72767d]">Version {localForm?.current_version || form.current_version}</p>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          {!isNew && onDuplicate && (
            <button
              onClick={onDuplicate}
              className="p-2 text-[#b5bac1] hover:text-white hover:bg-[#35373c] rounded-lg transition-colors"
              title="Duplicate form"
            >
              <Copy size={18} />
            </button>
          )}
          {!isNew && onDelete && (
            <button
              onClick={onDelete}
              className="p-2 text-[#b5bac1] hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
              title="Delete form"
            >
              <Trash2 size={18} />
            </button>
          )}
          <button
            onClick={onClose}
            className="p-2 text-[#b5bac1] hover:text-white hover:bg-[#35373c] rounded-lg transition-colors"
            title="Close"
          >
            <X size={18} />
          </button>
        </div>
      </div>
      
      {/* Tabs */}
      <div className="flex border-b border-[#3f4147]">
        {visibleTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={clsx(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-[2px]',
              activeTab === tab.id
                ? 'text-white border-[#5865f2]'
                : 'text-[#72767d] hover:text-[#b5bac1] border-transparent'
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>
      
      {/* Error */}
      {error && (
        <div className="m-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-2 text-red-400">
          <AlertCircle size={20} />
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto hover:text-red-300">×</button>
        </div>
      )}
      
      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'settings' && (
          <FormSettings
            name={name}
            slug={slug}
            category={category}
            description={description}
            allowedRoles={allowedRoles}
            serviceTarget={serviceTarget}
            fieldMapping={fieldMapping}
            isNew={isNew}
            onChange={handleChange}
          />
        )}
        
        {activeTab === 'fields' && form && (
          <FieldsList
            formId={form.id}
            fields={localForm?.fields || form.fields}
            onFieldsChange={handleFieldsChange}
          />
        )}
        
        {activeTab === 'versions' && form && (
          <VersionsList
            formId={form.id}
            currentVersion={localForm?.current_version || form.current_version}
            onRestore={handleVersionRestore}
          />
        )}
      </div>
      
      {/* Footer */}
      {activeTab === 'settings' && (
        <div className="flex items-center justify-end gap-3 p-4 border-t border-[#3f4147]">
          <button
            onClick={onClose}
            className="px-4 py-2 text-[#b5bac1] hover:text-white hover:bg-[#35373c] rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 bg-[#5865f2] hover:bg-[#4752c4] text-white rounded-lg font-medium transition-colors',
              saving && 'opacity-50 cursor-not-allowed'
            )}
          >
            {saving ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save size={16} />
                Save
              </>
            )}
          </button>
        </div>
      )}
    </div>
  )
}
