/**
 * OrderFormDetails Component
 * Renders order form_payload as a clean, human-readable definition list.
 */

interface OrderFormDetailsProps {
  formPayload: Record<string, unknown> | null | undefined
}

// Humanize field labels: delivery_date → Delivery Date
const humanize = (key: string): string =>
  key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase())

// Fields to hide (shown elsewhere or internal)
const HIDDEN_FIELDS = new Set([
  'order_type',
  'form_id',
  'form_version',
  'form_submission_id',
])

// Grouping rules for visual organization
const GROUPS: Record<string, string[]> = {
  'Order Information': ['priority', 'delivery_date', 'notes', 'reference_number'],
  'Product': ['product_id', 'product_name', 'quantity', 'unit', 'items'],
  'Customer': ['customer_name', 'customer_phone', 'customer_id'],
  'Delivery': ['delivery_location', 'delivery_address', 'delivery_notes'],
}

// Get all grouped field keys
const GROUPED_KEYS = new Set(Object.values(GROUPS).flat())

// Format value for display
const formatValue = (value: unknown): string => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) {
    // Handle items array specially
    if (value.length === 0) return ''
    if (typeof value[0] === 'object') {
      return value
        .map((item, i) => {
          const name = (item as Record<string, unknown>).name || (item as Record<string, unknown>).product_name || `Item ${i + 1}`
          const qty = (item as Record<string, unknown>).quantity || (item as Record<string, unknown>).qty
          return qty ? `${name} (×${qty})` : String(name)
        })
        .join(', ')
    }
    return value.join(', ')
  }
  if (typeof value === 'object') {
    // Try to extract meaningful string from nested object
    const obj = value as Record<string, unknown>
    return String(obj.name || obj.label || obj.value || JSON.stringify(value))
  }
  return String(value)
}

// Check if a value should be rendered
const shouldRender = (key: string, value: unknown): boolean => {
  if (HIDDEN_FIELDS.has(key)) return false
  if (value === null || value === undefined || value === '') return false
  if (Array.isArray(value) && value.length === 0) return false
  return true
}

export default function OrderFormDetails({ formPayload }: OrderFormDetailsProps) {
  if (!formPayload || typeof formPayload !== 'object') {
    return null
  }

  // Flatten nested form_payload if present
  const data: Record<string, unknown> =
    'form_payload' in formPayload && typeof formPayload.form_payload === 'object'
      ? { ...formPayload, ...(formPayload.form_payload as Record<string, unknown>) }
      : { ...formPayload }

  // Build grouped entries
  const groupedEntries: Record<string, Array<[string, unknown]>> = {}
  const ungroupedEntries: Array<[string, unknown]> = []

  for (const [key, value] of Object.entries(data)) {
    if (!shouldRender(key, value)) continue

    let placed = false
    for (const [groupName, groupKeys] of Object.entries(GROUPS)) {
      if (groupKeys.includes(key)) {
        if (!groupedEntries[groupName]) groupedEntries[groupName] = []
        groupedEntries[groupName].push([key, value])
        placed = true
        break
      }
    }
    if (!placed && !GROUPED_KEYS.has(key)) {
      ungroupedEntries.push([key, value])
    }
  }

  // Check if we have anything to render
  const hasGrouped = Object.values(groupedEntries).some((arr) => arr.length > 0)
  const hasUngrouped = ungroupedEntries.length > 0

  if (!hasGrouped && !hasUngrouped) {
    return null
  }

  return (
    <div className="space-y-4">
      {/* Render grouped sections */}
      {Object.entries(GROUPS).map(([groupName]) => {
        const entries = groupedEntries[groupName]
        if (!entries || entries.length === 0) return null

        return (
          <div key={groupName}>
            <h5 className="text-xs font-semibold text-[#949ba4] uppercase tracking-wide mb-2">
              {groupName}
            </h5>
            <dl className="space-y-2">
              {entries.map(([key, value]) => (
                <div key={key} className="flex flex-col sm:flex-row sm:gap-4">
                  <dt className="text-sm text-[#949ba4] sm:w-32 flex-shrink-0">
                    {humanize(key)}
                  </dt>
                  <dd className="text-sm text-white">
                    {formatValue(value)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )
      })}

      {/* Render ungrouped fields */}
      {hasUngrouped && (
        <div>
          <h5 className="text-xs font-semibold text-[#949ba4] uppercase tracking-wide mb-2">
            Other Details
          </h5>
          <dl className="space-y-2">
            {ungroupedEntries.map(([key, value]) => (
              <div key={key} className="flex flex-col sm:flex-row sm:gap-4">
                <dt className="text-sm text-[#949ba4] sm:w-32 flex-shrink-0">
                  {humanize(key)}
                </dt>
                <dd className="text-sm text-white">
                  {formatValue(value)}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  )
}
