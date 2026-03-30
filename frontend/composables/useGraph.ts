import type { StackMapNode } from '~/stores/graph'

export const CATEGORY_COLORS: Record<string, string> = {
  compute: '#f59e0b',
  storage: '#3b82f6',
  database: '#8b5cf6',
  network: '#6b7280',
  security: '#ef4444',
  monitoring: '#10b981',
  integration: '#f97316',
  cdn: '#06b6d4',
  dns: '#14b8a6',
  container: '#ec4899',
  serverless: '#fbbf24',
  queue: '#a78bfa',
  other: '#9ca3af',
}

export const EDGE_COLORS: Record<string, string> = {
  triggers: '#f97316',
  reads_from: '#3b82f6',
  writes_to: '#22c55e',
  routes_to: '#94a3b8',
  references: '#64748b',
  contains: '#475569',
  authenticates: '#ef4444',
}

export const CATEGORY_ICONS: Record<string, string> = {
  compute:
    '<rect x="3.5" y="3.5" width="17" height="17" rx="4" stroke="currentColor" stroke-width="2" fill="none"/><path d="M9 15.5h2.2l1.2-7h2.4l1.2 7H18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  storage:
    '<ellipse cx="12" cy="6" rx="6.5" ry="2.8" stroke="currentColor" stroke-width="2" fill="none"/><path d="M5.5 6v9c0 1.6 2.9 2.8 6.5 2.8s6.5-1.2 6.5-2.8V6" stroke="currentColor" stroke-width="2" fill="none"/><path d="M5.5 10c0 1.6 2.9 2.8 6.5 2.8s6.5-1.2 6.5-2.8" stroke="currentColor" stroke-width="2" fill="none"/>',
  database:
    '<ellipse cx="12" cy="5.8" rx="6.8" ry="2.8" stroke="currentColor" stroke-width="2" fill="none"/><path d="M5.2 5.8v11.6c0 1.6 3 2.9 6.8 2.9s6.8-1.3 6.8-2.9V5.8" stroke="currentColor" stroke-width="2" fill="none"/><path d="M6.3 10.2h11.4M6.3 14.4h11.4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  network:
    '<circle cx="6.5" cy="7" r="2.5" stroke="currentColor" stroke-width="2" fill="none"/><circle cx="17.5" cy="7" r="2.5" stroke="currentColor" stroke-width="2" fill="none"/><circle cx="12" cy="17" r="2.8" stroke="currentColor" stroke-width="2" fill="none"/><path d="M8.7 8.3l2.3 6M15.3 8.3l-2.3 6M9 7h6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  security:
    '<path d="M12 3.2l7 2.8v5.8c0 4.1-2.8 7.7-7 8.9-4.2-1.2-7-4.8-7-8.9V6l7-2.8z" stroke="currentColor" stroke-width="2" fill="none"/><path d="M8.6 12.2l2.2 2.2 4.6-4.6" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  monitoring:
    '<path d="M3.5 12c1.8-4.5 5-6.8 8.5-6.8s6.7 2.3 8.5 6.8c-1.8 4.5-5 6.8-8.5 6.8S5.3 16.5 3.5 12z" stroke="currentColor" stroke-width="2" fill="none"/><path d="M7 12h2.8l1.3-3.2 2.2 6 1.2-2.8H17" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  integration:
    '<path d="M4 8h9" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M10 5l3 3-3 3" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/><path d="M20 16h-9" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M14 13l-3 3 3 3" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  cdn:
    '<circle cx="12" cy="12" r="7.5" stroke="currentColor" stroke-width="2" fill="none"/><path d="M4.5 12h15M12 4.5a12 12 0 0 1 0 15M12 4.5a12 12 0 0 0 0 15M18.8 7.5l2.4-.8M19 11.5l2.8-.2M18.8 15.5l2.4.8" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>',
  dns:
    '<rect x="4" y="6" width="11" height="12" rx="2.8" stroke="currentColor" stroke-width="2" fill="none"/><path d="M7 10h5M7 14h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M15 12h5M18 9l3 3-3 3" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  container:
    '<rect x="3.5" y="6" width="17" height="12" rx="2.5" stroke="currentColor" stroke-width="2" fill="none"/><path d="M8 6v12M16 6v12M3.5 10h17M3.5 14h17" stroke="currentColor" stroke-width="2"/>',
  serverless:
    '<path d="M13.8 3.5L6.5 13.2h4.3l-1 7.3 7.7-10h-4.4l.7-7z" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round"/>',
  queue:
    '<rect x="4" y="6" width="14" height="3" rx="1.5" stroke="currentColor" stroke-width="2" fill="none"/><rect x="4" y="11" width="14" height="3" rx="1.5" stroke="currentColor" stroke-width="2" fill="none"/><rect x="4" y="16" width="14" height="3" rx="1.5" stroke="currentColor" stroke-width="2" fill="none"/><path d="M18 12h3M19.8 10.2l1.8 1.8-1.8 1.8" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  other:
    '<circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="2" fill="none"/><path d="M9.8 9.2a2.4 2.4 0 1 1 4.2 1.6c-.8.7-1.4 1.1-1.4 2.2" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><circle cx="12" cy="16.8" r="1" fill="currentColor"/>',
}

const PRIMARY_NODE_CATEGORIES = new Set([
  'compute',
  'database',
  'storage',
  'integration',
  'serverless',
  'cdn',
  'container',
  'queue',
])

export type NodeProminence = 'primary' | 'secondary' | 'tertiary'

export function getNodeProminence(node: StackMapNode): NodeProminence {
  const weight = node.position_hint?.weight || 2
  if (weight >= 4 && PRIMARY_NODE_CATEGORIES.has(node.category)) return 'primary'
  if (weight >= 3) return 'secondary'
  return 'tertiary'
}

export function getNodeWidth(node: StackMapNode): number {
  const prominence = getNodeProminence(node)
  if (prominence === 'primary') {
    return Math.max(200, Math.min(280, node.name.length * 8.5 + 80))
  }
  if (prominence === 'secondary') {
    return Math.max(160, Math.min(220, node.name.length * 7.5 + 60))
  }
  return Math.max(130, Math.min(180, node.name.length * 6.5 + 50))
}

export function getNodeHeight(node: StackMapNode): number {
  const prominence = getNodeProminence(node)
  if (prominence === 'primary') return 58
  if (prominence === 'secondary') return 46
  return 36
}

export function truncate(str: string, maxLen: number = 22): string {
  if (str.length <= maxLen) return str
  return str.slice(0, maxLen - 1) + '…'
}

export function formatResourceType(resourceType: string): string {
  // CloudFormation / SAM types: "AWS::Lambda::Function" -> "lambda function"
  if (resourceType.startsWith('AWS::')) {
    const parts = resourceType.split('::')
    // Drop "AWS" prefix, join remaining parts lowercased
    return parts.slice(1).join(' ').toLowerCase()
  }
  // Terraform types: "aws_lambda_function" -> "lambda function"
  return resourceType.replace(/^aws_/, '').replace(/_/g, ' ')
}

export function useGraph() {
  return {
    CATEGORY_COLORS,
    EDGE_COLORS,
    CATEGORY_ICONS,
    truncate,
    formatResourceType,
    getNodeWidth,
    getNodeHeight,
    getNodeProminence,
  }
}
