export const NO_ACCESS = {
  tabs: [],
  sales: {
    salesForm: false,
    overview: false,
    inventory: false,
    transactions: false,
    agentPerformance: false,
  },
}

export const UI_PERMISSIONS: Record<string, any> = {
  admin: { tabs: ["orders", "sales", "tasks"] },
  agent: { tabs: ["orders", "tasks"] },
  sales_agent: { tabs: ["orders", "sales", "tasks"] },
  storekeeper: { tabs: ["orders", "sales", "tasks"] },
  foreman: { tabs: ["sales", "tasks"] },
  delivery: { tabs: ["tasks"] },
} as const;
