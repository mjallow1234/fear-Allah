/**
 * Field Editor Component
 * Phase 8 - Form Builder
 * 
 * Modal for creating/editing form fields.
 */
import { useState } from 'react'
import { 
  Save, 
  X, 
  Plus, 
  Trash2,
  Loader2,
  AlertCircle
} from 'lucide-react'
import clsx from 'clsx'
import type { FormField, FormFieldType, FormFieldOption } from '../../types/forms'

// ============================================================================
// Types
// ============================================================================

interface FieldEditorProps {
  field?: FormField
  onSave: (data: Partial<FormField>) => Promise<void>
  onCancel: () => void
}

// ============================================================================
// Constants
// ============================================================================

const FIELD_TYPES: { value: FormFieldType; label: string; description: string }[] = [
  { value: 'text', label: 'Text', description: 'Single-line text input' },
  { value: 'number', label: 'Number', description: 'Numeric input with optional min/max' },
  { value: 'textarea', label: 'Text Area', description: 'Multi-line text input' },
  { value: 'date', label: 'Date', description: 'Date picker' },
  { value: 'datetime', label: 'Date & Time', description: 'Date and time picker' },
  { value: 'select', label: 'Select', description: 'Dropdown with single selection' },
  { value: 'multiselect', label: 'Multi-Select', description: 'Multiple selection dropdown' },
  { value: 'checkbox', label: 'Checkbox', description: 'Boolean true/false toggle' },
  { value: 'hidden', label: 'Hidden', description: 'Hidden field (not shown to user)' },
]

// ============================================================================
// Options Editor (for select/multiselect)
// ============================================================================

interface OptionsEditorProps {
  options: FormFieldOption[]
  onChange: (options: FormFieldOption[]) => void
}

function OptionsEditor({ options, onChange }: OptionsEditorProps) {
  const addOption = () => {
    onChange([...options, { label: '', value: '' }])
  }
  
  const updateOption = (index: number, field: keyof FormFieldOption, value: string) => {
    const updated = [...options]
    updated[index] = { ...updated[index], [field]: value }
    onChange(updated)
  }
  
  const removeOption = (index: number) => {
    onChange(options.filter((_, i) => i !== index))
  }
  
  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-[#b5bac1]">Options</label>
      
      {options.map((opt, index) => (
        <div key={index} className="flex items-center gap-2">
          <input
            type="text"
            value={opt.label}
            onChange={(e) => updateOption(index, 'label', e.target.value)}
            placeholder="Label"
            className="flex-1 px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] text-sm focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
          />
          <input
            type="text"
            value={String(opt.value)}
            onChange={(e) => updateOption(index, 'value', e.target.value)}
            placeholder="Value"
            className="flex-1 px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] text-sm focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
          />
          <button
            type="button"
            onClick={() => removeOption(index)}
            className="p-2 text-[#72767d] hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
          >
            <Trash2 size={16} />
          </button>
        </div>
      ))}
      
      <button
        type="button"
        onClick={addOption}
        className="flex items-center gap-2 px-3 py-2 text-sm text-[#5865f2] hover:bg-[#5865f2]/10 rounded-lg transition-colors"
      >
        <Plus size={16} />
        Add Option
      </button>
    </div>
  )
}

// ============================================================================
// Main Field Editor Component
// ============================================================================

export default function FieldEditor({ field, onSave, onCancel }: FieldEditorProps) {
  const isNew = !field
  
  // Form state
  const [key, setKey] = useState(field?.key || '')
  const [label, setLabel] = useState(field?.label || '')
  const [fieldType, setFieldType] = useState<FormFieldType>(field?.field_type || 'text')
  const [required, setRequired] = useState(field?.required || false)
  const [options, setOptions] = useState<FormFieldOption[]>(field?.options || [])
  const [defaultValue, setDefaultValue] = useState(field?.default_value || '')
  const [placeholder, setPlaceholder] = useState(field?.placeholder || '')
  const [helpText, setHelpText] = useState(field?.help_text || '')
  const [fieldGroup, setFieldGroup] = useState(field?.field_group || '')
  const [roleVisibility, setRoleVisibility] = useState<string[]>(field?.role_visibility || [])
  const [minValue, setMinValue] = useState<number | ''>(field?.min_value ?? '')
  const [maxValue, setMaxValue] = useState<number | ''>(field?.max_value ?? '')
  const [minLength, setMinLength] = useState<number | ''>(field?.min_length ?? '')
  const [maxLength, setMaxLength] = useState<number | ''>(field?.max_length ?? '')
  const [pattern, setPattern] = useState(field?.pattern || '')
  
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [rolesInput, setRolesInput] = useState(roleVisibility.join(', '))
  
  // Auto-generate key from label
  const handleLabelChange = (value: string) => {
    setLabel(value)
    if (isNew) {
      // Auto-generate key from label
      setKey(value.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, ''))
    }
  }
  
  const handleRolesChange = (value: string) => {
    setRolesInput(value)
    const roles = value.split(',').map(r => r.trim()).filter(Boolean)
    setRoleVisibility(roles)
  }
  
  const hasOptions = fieldType === 'select' || fieldType === 'multiselect'
  const hasNumericValidation = fieldType === 'number'
  const hasTextValidation = fieldType === 'text' || fieldType === 'textarea'
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validation
    if (!key.trim()) {
      setError('Key is required')
      return
    }
    if (!label.trim()) {
      setError('Label is required')
      return
    }
    if (hasOptions && options.length === 0) {
      setError('At least one option is required for select fields')
      return
    }
    
    try {
      setSaving(true)
      setError(null)
      
      const data: Partial<FormField> = {
        key,
        label,
        field_type: fieldType,
        required,
        placeholder: placeholder || undefined,
        help_text: helpText || undefined,
        default_value: defaultValue || undefined,
        field_group: fieldGroup || undefined,
        role_visibility: roleVisibility.length > 0 ? roleVisibility : undefined,
      }
      
      if (hasOptions) {
        data.options = options.filter(o => o.label && o.value)
      }
      
      if (hasNumericValidation) {
        if (minValue !== '') data.min_value = Number(minValue)
        if (maxValue !== '') data.max_value = Number(maxValue)
      }
      
      if (hasTextValidation) {
        if (minLength !== '') data.min_length = Number(minLength)
        if (maxLength !== '') data.max_length = Number(maxLength)
        if (pattern) data.pattern = pattern
      }
      
      await onSave(data)
    } catch (err: any) {
      setError(err.message || 'Failed to save field')
    } finally {
      setSaving(false)
    }
  }
  
  return (
    <form onSubmit={handleSubmit}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[#3f4147]">
        <h3 className="text-lg font-semibold text-white">
          {isNew ? 'Add Field' : 'Edit Field'}
        </h3>
        <button
          type="button"
          onClick={onCancel}
          className="p-2 text-[#b5bac1] hover:text-white hover:bg-[#35373c] rounded-lg transition-colors"
        >
          <X size={18} />
        </button>
      </div>
      
      {/* Error */}
      {error && (
        <div className="m-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-2 text-red-400">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}
      
      {/* Content */}
      <div className="p-4 space-y-4 max-h-[60vh] overflow-y-auto">
        {/* Basic fields */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-1">
              Label <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={label}
              onChange={(e) => handleLabelChange(e.target.value)}
              placeholder="Field Label"
              className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-1">
              Key <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={key}
              onChange={(e) => setKey(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
              placeholder="field_key"
              className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white font-mono placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
            />
            <p className="text-xs text-[#72767d] mt-1">Unique identifier (lowercase, underscores)</p>
          </div>
        </div>
        
        {/* Field Type */}
        <div>
          <label className="block text-sm font-medium text-[#b5bac1] mb-1">
            Field Type
          </label>
          <select
            value={fieldType}
            onChange={(e) => setFieldType(e.target.value as FormFieldType)}
            className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-[#5865f2] appearance-none"
          >
            {FIELD_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label} - {type.description}
              </option>
            ))}
          </select>
        </div>
        
        {/* Required checkbox */}
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={required}
            onChange={(e) => setRequired(e.target.checked)}
            className="w-5 h-5 bg-[#1e1f22] border border-[#3f4147] rounded text-[#5865f2] focus:ring-2 focus:ring-[#5865f2]"
          />
          <span className="text-[#b5bac1]">Required field</span>
        </label>
        
        {/* Options (for select/multiselect) */}
        {hasOptions && (
          <OptionsEditor options={options} onChange={setOptions} />
        )}
        
        {/* Numeric validation */}
        {hasNumericValidation && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                Min Value
              </label>
              <input
                type="number"
                value={minValue}
                onChange={(e) => setMinValue(e.target.value ? Number(e.target.value) : '')}
                placeholder="No minimum"
                className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                Max Value
              </label>
              <input
                type="number"
                value={maxValue}
                onChange={(e) => setMaxValue(e.target.value ? Number(e.target.value) : '')}
                placeholder="No maximum"
                className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
              />
            </div>
          </div>
        )}
        
        {/* Text validation */}
        {hasTextValidation && (
          <>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Min Length
                </label>
                <input
                  type="number"
                  value={minLength}
                  onChange={(e) => setMinLength(e.target.value ? Number(e.target.value) : '')}
                  placeholder="No minimum"
                  min={0}
                  className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                  Max Length
                </label>
                <input
                  type="number"
                  value={maxLength}
                  onChange={(e) => setMaxLength(e.target.value ? Number(e.target.value) : '')}
                  placeholder="No maximum"
                  min={0}
                  className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
                />
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-[#b5bac1] mb-1">
                Regex Pattern
              </label>
              <input
                type="text"
                value={pattern}
                onChange={(e) => setPattern(e.target.value)}
                placeholder="^[a-zA-Z0-9]+$"
                className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white font-mono placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
              />
              <p className="text-xs text-[#72767d] mt-1">Validation regex pattern</p>
            </div>
          </>
        )}
        
        {/* Placeholder & Help Text */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-1">
              Placeholder
            </label>
            <input
              type="text"
              value={placeholder}
              onChange={(e) => setPlaceholder(e.target.value)}
              placeholder="Enter placeholder text..."
              className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-1">
              Default Value
            </label>
            <input
              type="text"
              value={defaultValue}
              onChange={(e) => setDefaultValue(e.target.value)}
              placeholder="Default value"
              className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
            />
          </div>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-[#b5bac1] mb-1">
            Help Text
          </label>
          <input
            type="text"
            value={helpText}
            onChange={(e) => setHelpText(e.target.value)}
            placeholder="Additional instructions shown below field"
            className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
          />
        </div>
        
        {/* Grouping & Role Visibility */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-1">
              Field Group
            </label>
            <input
              type="text"
              value={fieldGroup}
              onChange={(e) => setFieldGroup(e.target.value)}
              placeholder="Optional group name"
              className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
            />
            <p className="text-xs text-[#72767d] mt-1">Groups fields together in the form</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-[#b5bac1] mb-1">
              Role Visibility
            </label>
            <input
              type="text"
              value={rolesInput}
              onChange={(e) => handleRolesChange(e.target.value)}
              placeholder="admin, manager (comma-separated)"
              className="w-full px-3 py-2 bg-[#1e1f22] border border-[#3f4147] rounded-lg text-white placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]"
            />
            <p className="text-xs text-[#72767d] mt-1">Empty = visible to all</p>
          </div>
        </div>
      </div>
      
      {/* Footer */}
      <div className="flex items-center justify-end gap-3 p-4 border-t border-[#3f4147]">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-[#b5bac1] hover:text-white hover:bg-[#35373c] rounded-lg transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
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
              {isNew ? 'Add Field' : 'Save Field'}
            </>
          )}
        </button>
      </div>
    </form>
  )
}
