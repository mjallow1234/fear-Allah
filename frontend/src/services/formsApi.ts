/**
 * Form Service - API calls for dynamic forms.
 * Phase 8 - Form Builder
 */
import api from './api'
import type { Form, FormListItem, FormSubmission, FormValues } from '../types/forms'

const formsApi = {
  /**
   * List forms available to current user.
   */
  listForms: async (category?: string): Promise<FormListItem[]> => {
    const params = category ? { category } : {}
    const response = await api.get('/api/forms/', { params })
    return response.data
  },

  /**
   * Get form definition by slug.
   */
  getForm: async (slug: string): Promise<Form> => {
    const response = await api.get(`/api/forms/${slug}`)
    return response.data
  },

  /**
   * Submit a form.
   */
  submitForm: async (slug: string, data: FormValues): Promise<FormSubmission> => {
    const response = await api.post(`/api/forms/${slug}/submit`, { data })
    return response.data
  },

  // === Admin APIs ===

  /**
   * List all forms (admin).
   */
  adminListForms: async (params?: { category?: string; is_active?: boolean }): Promise<any[]> => {
    const response = await api.get('/api/forms/admin', { params })
    return response.data
  },

  /**
   * Get form by ID (admin).
   */
  adminGetForm: async (formId: number): Promise<Form> => {
    const response = await api.get(`/api/forms/admin/${formId}`)
    return response.data
  },

  /**
   * Create a new form (admin).
   */
  adminCreateForm: async (data: {
    slug: string
    name: string
    description?: string
    category: string
    allowed_roles?: string[]
    service_target?: string
    field_mapping?: Record<string, string>
    is_active?: boolean
  }): Promise<Form> => {
    const response = await api.post('/api/forms/admin', data)
    return response.data
  },

  /**
   * Update a form (admin).
   */
  adminUpdateForm: async (formId: number, data: Partial<Form>): Promise<Form> => {
    const response = await api.patch(`/api/forms/admin/${formId}`, data)
    return response.data
  },

  /**
   * Delete a form (admin).
   */
  adminDeleteForm: async (formId: number): Promise<void> => {
    await api.delete(`/api/forms/admin/${formId}`)
  },

  /**
   * Add a field to a form (admin).
   */
  adminAddField: async (formId: number, field: any): Promise<any> => {
    const response = await api.post(`/api/forms/admin/${formId}/fields`, field)
    return response.data
  },

  /**
   * Update a field (admin).
   */
  adminUpdateField: async (formId: number, fieldId: number, data: any): Promise<any> => {
    const response = await api.patch(`/api/forms/admin/${formId}/fields/${fieldId}`, data)
    return response.data
  },

  /**
   * Delete a field (admin).
   */
  adminDeleteField: async (formId: number, fieldId: number): Promise<void> => {
    await api.delete(`/api/forms/admin/${formId}/fields/${fieldId}`)
  },

  /**
   * Reorder fields (admin).
   */
  adminReorderFields: async (formId: number, fieldOrder: number[]): Promise<Form> => {
    const response = await api.post(`/api/forms/admin/${formId}/fields/reorder`, fieldOrder)
    return response.data
  },

  /**
   * List form versions (admin).
   */
  adminListVersions: async (formId: number): Promise<any[]> => {
    const response = await api.get(`/api/forms/admin/${formId}/versions`)
    return response.data
  },

  /**
   * Restore a form version (admin).
   */
  adminRestoreVersion: async (formId: number, versionId: number): Promise<Form> => {
    const response = await api.post(`/api/forms/admin/${formId}/versions/${versionId}/restore`)
    return response.data
  },

  /**
   * List form submissions (admin).
   */
  adminListSubmissions: async (slug: string, params?: { limit?: number; offset?: number }): Promise<FormSubmission[]> => {
    const response = await api.get(`/api/forms/${slug}/submissions`, { params })
    return response.data
  },

  /**
   * Seed initial forms (admin).
   * Creates Sales, Orders, Inventory, Raw Materials forms if they don't exist.
   */
  adminSeedForms: async (): Promise<{ message: string; created: string[]; skipped: string[] }> => {
    const response = await api.post('/api/forms/admin/seed')
    return response.data
  },
}

export default formsApi
