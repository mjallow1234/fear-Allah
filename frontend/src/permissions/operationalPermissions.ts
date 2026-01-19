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
  admin: {
    tabs: ['Orders', 'Sales', 'Tasks'],
    sales: { salesForm: true, overview: true, inventory: true, transactions: true, agentPerformance: true },
  },
  agent: {
    tabs: ['Sales'],
    sales: { salesForm: false, overview: true, inventory: false, transactions: false, agentPerformance: false },
  },
  sales_agent: {
    tabs: ['Sales'],
    sales: { salesForm: true, overview: true, inventory: false, transactions: true, agentPerformance: false },
  },
  storekeeper: {
    tabs: [],
    sales: { salesForm: false, overview: false, inventory: true, transactions: false, agentPerformance: false },
  },
  foreman: {
    tabs: ['Tasks'],
    sales: { salesForm: false, overview: false, inventory: false, transactions: false, agentPerformance: false },
  },
  delivery: {
    tabs: [],
    sales: { salesForm: false, overview: false, inventory: false, transactions: false, agentPerformance: false },
  },
}