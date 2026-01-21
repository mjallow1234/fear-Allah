export const NO_ACCESS = { tabs: [], sales: {} } as const

export const UI_PERMISSIONS = {
  admin: {
    tabs: ["orders", "sales", "tasks"],
    sales: {
      overview: true,
      record: true,
      agentPerformance: true,
      inventory: true,
      rawMaterials: true,
      transactions: true,
    },
  },
  sales_agent: {
    tabs: ["orders", "sales", "tasks"],
    sales: {
      overview: true,
      record: true,
      agentPerformance: false,
      inventory: false,
      rawMaterials: false,
      transactions: false,
    },
  },
  storekeeper: {
    tabs: ["orders", "sales", "tasks"],
    sales: {
      overview: true,
      record: true,
      agentPerformance: false,
      inventory: false,
      rawMaterials: false,
      transactions: false,
    },
  },
  foreman: {
    tabs: ["sales", "tasks"],
    sales: {
      overview: false,
      record: false,
      agentPerformance: false,
      inventory: true,
      rawMaterials: true,
      transactions: false,
    },
  },
  agent: {
    tabs: ["orders", "tasks"],
    sales: {
      overview: false,
      record: false,
      agentPerformance: false,
      inventory: false,
      rawMaterials: false,
      transactions: false,
    },
  },
  delivery: {
    tabs: ["tasks"],
    sales: {
      overview: false,
      record: false,
      agentPerformance: false,
      inventory: false,
      rawMaterials: false,
      transactions: false,
    },
  },
} as const;
