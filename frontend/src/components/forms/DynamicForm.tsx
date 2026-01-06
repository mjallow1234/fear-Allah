/**
 * DynamicForm Component - Form Runtime Engine
 * Phase 8 - Form Builder
 * 
 * Renders forms dynamically from API definitions.
 * Handles validation, submission, and service routing.
 * 
 * Usage:
 * <DynamicForm 
 *   formSlug="sales" 
 *   onSuccess={(result) => console.log('Submitted!', result)}
 *   onError={(error) => console.error(error)}
 * />
 */
import { useState, useEffect, useCallback } from 'react'
import { 
  Loader2, 
  AlertCircle, 
  CheckCircle,
  Calendar,
  ChevronDown,
  X
} from 'lucide-react'
import clsx from 'clsx'
import formsApi from '../../services/formsApi'
import type { Form, FormField, FormValues, FormSubmission } from '../../types/forms'
import { extractAxiosError } from '../../utils/errorUtils'

interface DynamicFormProps {
  formSlug: string
  initialValues?: FormValues
  onSuccess?: (result: FormSubmission) => void
  onError?: (error: string) => void
  onCancel?: () => void
  submitButtonText?: string
  className?: string
}

interface FieldProps {
  field: FormField
  value: any
  onChange: (key: string, value: any) => void
  error?: string
  disabled?: boolean
}

// ============================================================================
// Field Components
// ============================================================================

function TextField({ field, value, onChange, error, disabled }: FieldProps) {
  return (
    <input
      type="text"
      id={field.key}
      value={value || ''}
      onChange={(e) => onChange(field.key, e.target.value)}
      placeholder={field.placeholder}
      disabled={disabled}
      minLength={field.min_length}
      maxLength={field.max_length}
      pattern={field.pattern}
      className={clsx(
        'w-full px-3 py-2 bg-[#1e1f22] border rounded-lg text-white placeholder-[#72767d]',
        'focus:outline-none focus:ring-2 focus:ring-[#5865f2] focus:border-transparent',
        error ? 'border-red-500' : 'border-[#3f4147]',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
    />
  )
}

function NumberField({ field, value, onChange, error, disabled }: FieldProps) {
  return (
    <input
      type="number"
      id={field.key}
      value={value ?? ''}
      onChange={(e) => onChange(field.key, e.target.value ? Number(e.target.value) : null)}
      placeholder={field.placeholder}
      disabled={disabled}
      min={field.min_value}
      max={field.max_value}
      className={clsx(
        'w-full px-3 py-2 bg-[#1e1f22] border rounded-lg text-white placeholder-[#72767d]',
        'focus:outline-none focus:ring-2 focus:ring-[#5865f2] focus:border-transparent',
        error ? 'border-red-500' : 'border-[#3f4147]',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
    />
  )
}

function TextareaField({ field, value, onChange, error, disabled }: FieldProps) {
  return (
    <textarea
      id={field.key}
      value={value || ''}
      onChange={(e) => onChange(field.key, e.target.value)}
      placeholder={field.placeholder}
      disabled={disabled}
      minLength={field.min_length}
      maxLength={field.max_length}
      rows={4}
      className={clsx(
        'w-full px-3 py-2 bg-[#1e1f22] border rounded-lg text-white placeholder-[#72767d] resize-y',
        'focus:outline-none focus:ring-2 focus:ring-[#5865f2] focus:border-transparent',
        error ? 'border-red-500' : 'border-[#3f4147]',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
    />
  )
}

function DateField({ field, value, onChange, error, disabled }: FieldProps) {
  const inputType = field.field_type === 'datetime' ? 'datetime-local' : 'date'
  
  return (
    <div className="relative">
      <input
        type={inputType}
        id={field.key}
        value={value || ''}
        onChange={(e) => onChange(field.key, e.target.value)}
        disabled={disabled}
        className={clsx(
          'w-full px-3 py-2 bg-[#1e1f22] border rounded-lg text-white',
          'focus:outline-none focus:ring-2 focus:ring-[#5865f2] focus:border-transparent',
          error ? 'border-red-500' : 'border-[#3f4147]',
          disabled && 'opacity-50 cursor-not-allowed',
          '[color-scheme:dark]'
        )}
      />
      <Calendar 
        size={16} 
        className="absolute right-3 top-1/2 -translate-y-1/2 text-[#72767d] pointer-events-none" 
      />
    </div>
  )
}

function SelectField({ field, value, onChange, error, disabled }: FieldProps) {
  const options = field.options || []
  
  return (
    <div className="relative">
      <select
        id={field.key}
        value={value || ''}
        onChange={(e) => onChange(field.key, e.target.value)}
        disabled={disabled}
        className={clsx(
          'w-full px-3 py-2 bg-[#1e1f22] border rounded-lg text-white appearance-none',
          'focus:outline-none focus:ring-2 focus:ring-[#5865f2] focus:border-transparent',
          error ? 'border-red-500' : 'border-[#3f4147]',
          disabled && 'opacity-50 cursor-not-allowed',
          !value && 'text-[#72767d]'
        )}
      >
        <option value="">{field.placeholder || 'Select...'}</option>
        {options.map((opt) => (
          <option key={String(opt.value)} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      <ChevronDown 
        size={16} 
        className="absolute right-3 top-1/2 -translate-y-1/2 text-[#72767d] pointer-events-none" 
      />
    </div>
  )
}

function MultiSelectField({ field, value, onChange, error, disabled }: FieldProps) {
  const options = field.options || []
  const selectedValues: string[] = Array.isArray(value) ? value : []
  
  const toggleValue = (optValue: string | number) => {
    const strValue = String(optValue)
    if (selectedValues.includes(strValue)) {
      onChange(field.key, selectedValues.filter(v => v !== strValue))
    } else {
      onChange(field.key, [...selectedValues, strValue])
    }
  }
  
  return (
    <div className={clsx(
      'w-full p-2 bg-[#1e1f22] border rounded-lg',
      error ? 'border-red-500' : 'border-[#3f4147]',
      disabled && 'opacity-50 cursor-not-allowed'
    )}>
      <div className="flex flex-wrap gap-2 mb-2">
        {selectedValues.map((v) => {
          const opt = options.find(o => String(o.value) === v)
          return (
            <span 
              key={v}
              className="inline-flex items-center gap-1 px-2 py-1 bg-[#5865f2] text-white text-sm rounded"
            >
              {opt?.label || v}
              <button
                type="button"
                onClick={() => toggleValue(v)}
                disabled={disabled}
                className="hover:bg-white/20 rounded p-0.5"
              >
                <X size={12} />
              </button>
            </span>
          )
        })}
      </div>
      <div className="max-h-32 overflow-y-auto">
        {options.filter(opt => !selectedValues.includes(String(opt.value))).map((opt) => (
          <button
            key={String(opt.value)}
            type="button"
            onClick={() => toggleValue(opt.value)}
            disabled={disabled}
            className="block w-full text-left px-2 py-1 text-[#b5bac1] hover:bg-[#35373c] rounded text-sm"
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function CheckboxField({ field, value, onChange, error, disabled }: FieldProps) {
  return (
    <label className={clsx(
      'flex items-center gap-3 cursor-pointer',
      disabled && 'opacity-50 cursor-not-allowed'
    )}>
      <input
        type="checkbox"
        id={field.key}
        checked={Boolean(value)}
        onChange={(e) => onChange(field.key, e.target.checked)}
        disabled={disabled}
        className={clsx(
          'w-5 h-5 bg-[#1e1f22] border rounded text-[#5865f2]',
          'focus:ring-2 focus:ring-[#5865f2] focus:ring-offset-0',
          error ? 'border-red-500' : 'border-[#3f4147]'
        )}
      />
      <span className="text-[#b5bac1]">{field.label}</span>
    </label>
  )
}

// ============================================================================
// Field Renderer
// ============================================================================

function FormFieldRenderer({ field, value, onChange, error, disabled }: FieldProps) {
  // Hidden fields
  if (field.field_type === 'hidden') {
    return <input type="hidden" name={field.key} value={value || ''} />
  }
  
  // Checkbox has different layout (label is part of component)
  if (field.field_type === 'checkbox') {
    return (
      <div className="mb-4">
        <CheckboxField 
          field={field} 
          value={value} 
          onChange={onChange} 
          error={error}
          disabled={disabled}
        />
        {field.help_text && (
          <p className="text-xs text-[#72767d] mt-1 ml-8">{field.help_text}</p>
        )}
        {error && (
          <p className="text-xs text-red-400 mt-1 ml-8">{error}</p>
        )}
      </div>
    )
  }
  
  // Standard field with label
  return (
    <div className="mb-4">
      <label htmlFor={field.key} className="block text-sm font-medium text-[#b5bac1] mb-1">
        {field.label}
        {field.required && <span className="text-red-400 ml-1">*</span>}
      </label>
      
      {field.field_type === 'text' && (
        <TextField field={field} value={value} onChange={onChange} error={error} disabled={disabled} />
      )}
      {field.field_type === 'number' && (
        <NumberField field={field} value={value} onChange={onChange} error={error} disabled={disabled} />
      )}
      {field.field_type === 'textarea' && (
        <TextareaField field={field} value={value} onChange={onChange} error={error} disabled={disabled} />
      )}
      {(field.field_type === 'date' || field.field_type === 'datetime') && (
        <DateField field={field} value={value} onChange={onChange} error={error} disabled={disabled} />
      )}
      {field.field_type === 'select' && (
        <SelectField field={field} value={value} onChange={onChange} error={error} disabled={disabled} />
      )}
      {field.field_type === 'multiselect' && (
        <MultiSelectField field={field} value={value} onChange={onChange} error={error} disabled={disabled} />
      )}
      
      {field.help_text && (
        <p className="text-xs text-[#72767d] mt-1">{field.help_text}</p>
      )}
      {error && (
        <p className="text-xs text-red-400 mt-1">{error}</p>
      )}
    </div>
  )
}

// ============================================================================
// Main DynamicForm Component
// ============================================================================

export default function DynamicForm({
  formSlug,
  initialValues = {},
  onSuccess,
  onError,
  onCancel,
  submitButtonText = 'Submit',
  className,
}: DynamicFormProps) {
  const [form, setForm] = useState<Form | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [values, setValues] = useState<FormValues>(initialValues)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  
  // Fetch form definition
  useEffect(() => {
    const fetchForm = async () => {
      try {
        setLoading(true)
        setError(null)
        const formData = await formsApi.getForm(formSlug)
        setForm(formData)
        
        // Set default values
        const defaults: FormValues = { ...initialValues }
        for (const field of formData.fields) {
          if (field.default_value && !(field.key in defaults)) {
            try {
              // Try to parse JSON default value
              defaults[field.key] = JSON.parse(field.default_value)
            } catch {
              defaults[field.key] = field.default_value
            }
          }
        }
        setValues(defaults)
      } catch (err: any) {
        const message = extractAxiosError(err, 'Failed to load form')
        setError(message)
        onError?.(message)
      } finally {
        setLoading(false)
      }
    }
    
    fetchForm()
  }, [formSlug])
  
  // Handle field value change
  const handleChange = useCallback((key: string, value: any) => {
    setValues(prev => ({ ...prev, [key]: value }))
    // Clear field error on change
    setFieldErrors(prev => {
      const next = { ...prev }
      delete next[key]
      return next
    })
  }, [])
  
  // Validate form
  const validate = useCallback((): boolean => {
    if (!form) return false
    
    const errors: Record<string, string> = {}
    
    for (const field of form.fields) {
      const value = values[field.key]
      
      // Required check
      if (field.required) {
        if (value === undefined || value === null || value === '' || (Array.isArray(value) && value.length === 0)) {
          errors[field.key] = 'This field is required'
          continue
        }
      }
      
      // Skip further validation if empty and not required
      if (value === undefined || value === null || value === '') continue
      
      // Number validation
      if (field.field_type === 'number') {
        if (field.min_value !== undefined && field.min_value !== null && value < field.min_value) {
          errors[field.key] = `Minimum value is ${field.min_value}`
        }
        if (field.max_value !== undefined && field.max_value !== null && value > field.max_value) {
          errors[field.key] = `Maximum value is ${field.max_value}`
        }
      }
      
      // String length validation
      if (field.field_type === 'text' || field.field_type === 'textarea') {
        const strValue = String(value)
        if (field.min_length !== undefined && field.min_length !== null && strValue.length < field.min_length) {
          errors[field.key] = `Minimum length is ${field.min_length} characters`
        }
        if (field.max_length !== undefined && field.max_length !== null && strValue.length > field.max_length) {
          errors[field.key] = `Maximum length is ${field.max_length} characters`
        }
      }
      
      // Pattern validation
      if (field.pattern && (field.field_type === 'text' || field.field_type === 'textarea')) {
        const regex = new RegExp(field.pattern)
        if (!regex.test(String(value))) {
          errors[field.key] = 'Invalid format'
        }
      }
    }
    
    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }, [form, values])
  
  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!form) return
    
    // Validate
    if (!validate()) {
      return
    }
    
    try {
      setSubmitting(true)
      setError(null)
      
      const result = await formsApi.submitForm(formSlug, values)
      
      setSuccess(true)
      onSuccess?.(result)
      
      // Reset form after success
      setTimeout(() => {
        setSuccess(false)
      }, 3000)
    } catch (err: any) {
      const message = extractAxiosError(err, 'Failed to submit form')
      setError(message)
      onError?.(message)
    } finally {
      setSubmitting(false)
    }
  }
  
  // Loading state
  if (loading) {
    return (
      <div className={clsx('flex items-center justify-center p-8', className)}>
        <Loader2 className="animate-spin text-[#5865f2]" size={32} />
      </div>
    )
  }
  
  // Error state
  if (error && !form) {
    return (
      <div className={clsx('p-4 bg-red-500/10 border border-red-500/30 rounded-lg', className)}>
        <div className="flex items-center gap-2 text-red-400">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      </div>
    )
  }
  
  // No form
  if (!form) {
    return null
  }
  
  // Group fields by field_group
  const groupedFields = form.fields.reduce((acc, field) => {
    const group = field.field_group || '_default'
    if (!acc[group]) acc[group] = []
    acc[group].push(field)
    return acc
  }, {} as Record<string, FormField[]>)
  
  const groups = Object.keys(groupedFields)
  const hasGroups = groups.length > 1 || !groups.includes('_default')
  
  return (
    <form onSubmit={handleSubmit} className={clsx('space-y-6', className)}>
      {/* Form title & description */}
      <div>
        <h3 className="text-lg font-semibold text-white">{form.name}</h3>
        {form.description && (
          <p className="text-sm text-[#949ba4] mt-1">{form.description}</p>
        )}
      </div>
      
      {/* Success message */}
      {success && (
        <div className="p-3 bg-green-500/10 border border-green-500/30 rounded-lg flex items-center gap-2 text-green-400">
          <CheckCircle size={20} />
          <span>Form submitted successfully!</span>
        </div>
      )}
      
      {/* Error message */}
      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-2 text-red-400">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}
      
      {/* Fields */}
      {hasGroups ? (
        // Render with groups
        groups.map((group) => (
          <div key={group} className="space-y-4">
            {group !== '_default' && (
              <h4 className="text-sm font-medium text-[#b5bac1] border-b border-[#3f4147] pb-2">
                {group}
              </h4>
            )}
            {groupedFields[group].map((field) => (
              <FormFieldRenderer
                key={field.id}
                field={field}
                value={values[field.key]}
                onChange={handleChange}
                error={fieldErrors[field.key]}
                disabled={submitting}
              />
            ))}
          </div>
        ))
      ) : (
        // Render flat
        form.fields.map((field) => (
          <FormFieldRenderer
            key={field.id}
            field={field}
            value={values[field.key]}
            onChange={handleChange}
            error={fieldErrors[field.key]}
            disabled={submitting}
          />
        ))
      )}
      
      {/* Actions */}
      <div className="flex items-center gap-3 pt-4 border-t border-[#3f4147]">
        <button
          type="submit"
          disabled={submitting}
          className={clsx(
            'px-4 py-2 rounded-lg font-medium transition-colors',
            'bg-[#5865f2] hover:bg-[#4752c4] text-white',
            submitting && 'opacity-50 cursor-not-allowed'
          )}
        >
          {submitting ? (
            <span className="flex items-center gap-2">
              <Loader2 className="animate-spin" size={16} />
              Submitting...
            </span>
          ) : (
            submitButtonText
          )}
        </button>
        
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            className="px-4 py-2 rounded-lg font-medium text-[#b5bac1] hover:bg-[#35373c] transition-colors"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  )
}
