/**
 * Form Types - Dynamic Forms System (Phase 8)
 * Type definitions for form builder and runtime.
 */

export type FormFieldType = 
  | 'text' 
  | 'number' 
  | 'date' 
  | 'datetime' 
  | 'select' 
  | 'multiselect' 
  | 'checkbox' 
  | 'textarea' 
  | 'hidden'

export type FormCategory = 
  | 'order' 
  | 'sale' 
  | 'inventory' 
  | 'raw_material' 
  | 'production' 
  | 'custom'

export interface FormFieldOption {
  value: string | number
  label: string
}

export interface FormField {
  id: number
  key: string
  label: string
  field_type: FormFieldType
  placeholder?: string
  help_text?: string
  required: boolean
  min_value?: number
  max_value?: number
  min_length?: number
  max_length?: number
  pattern?: string
  options?: FormFieldOption[]
  options_source?: string
  default_value?: string
  role_visibility?: string[]
  conditional_visibility?: Record<string, any>
  order_index: number
  field_group?: string
}

export interface Form {
  id: number
  slug: string
  name: string
  description?: string
  category: FormCategory
  allowed_roles?: string[]
  service_target?: string
  field_mapping?: Record<string, string>
  is_active: boolean
  current_version: number
  fields: FormField[]
  created_at?: string
  updated_at?: string
}

export interface FormListItem {
  id: number
  slug: string
  name: string
  category: FormCategory
  description?: string
}

export interface FormSubmission {
  id: number
  form_id: number
  form_version: number
  status: 'pending' | 'processed' | 'failed'
  result_id?: number
  result_type?: string
  error_message?: string
  created_at?: string
}

export interface FormValues {
  [key: string]: any
}
