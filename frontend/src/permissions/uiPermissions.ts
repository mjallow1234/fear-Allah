export const NO_ACCESS = { tabs: [] } as const

export const UI_PERMISSIONS = {
  admin:        { tabs: ["orders", "sales", "tasks"] },
  agent:        { tabs: ["orders", "tasks"] },
  sales_agent:  { tabs: ["orders", "sales", "tasks"] },
  storekeeper:  { tabs: ["orders", "sales", "tasks"] },
  foreman:      { tabs: ["sales", "tasks"] },
  delivery:     { tabs: ["tasks"] },
} as const;
