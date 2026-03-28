export const CATEGORY_COLORS: Record<string, string> = {
  compute: '#f59e0b',     // amber
  storage: '#3b82f6',     // blue
  database: '#8b5cf6',    // violet
  network: '#6b7280',     // gray
  security: '#ef4444',    // red
  monitoring: '#10b981',  // emerald
  integration: '#f97316', // orange
  cdn: '#06b6d4',         // cyan
  dns: '#14b8a6',         // teal
  container: '#ec4899',   // pink
  serverless: '#fbbf24',  // yellow
  queue: '#a78bfa',       // light violet
  other: '#9ca3af',       // gray-400
}

export const EDGE_COLORS: Record<string, string> = {
  triggers: '#f97316',     // orange
  reads_from: '#3b82f6',   // blue
  writes_to: '#22c55e',    // green
  routes_to: '#6b7280',    // gray
  references: '#4b5563',   // gray-600
  contains: '#374151',     // gray-700
  authenticates: '#ef4444', // red
}

export const CATEGORY_ICONS: Record<string, string> = {
  compute: 'M',       // Lambda / function
  storage: '⬡',       // S3 bucket
  database: '⊡',      // Database
  network: '◈',       // Network
  security: '⊘',      // Shield
  monitoring: '◎',    // Eye
  integration: '⬡',   // API
  cdn: '◇',           // Cloud
  dns: '⊕',           // DNS
  container: '⬢',     // Container
  serverless: '⚡',    // Bolt
  queue: '≡',         // Queue
  other: '○',         // Circle
}

export function truncate(str: string, maxLen: number = 22): string {
  if (str.length <= maxLen) return str
  return str.slice(0, maxLen - 1) + '…'
}

export function useGraph() {
  return {
    CATEGORY_COLORS,
    EDGE_COLORS,
    CATEGORY_ICONS,
    truncate,
  }
}
