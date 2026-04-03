import type { StackMapNode } from '~/stores/graph'

export interface GraphLayer {
  id: string
  label: string
  short: string
  fill: string
  stroke: string
  accent: string
  icon: string
}

export interface UserNodeTemplate {
  id: string
  label: string
  resourceType: string
  category: string
  tier: string
  provider?: string
  weight?: number
}

export const DEFAULT_GRAPH_LAYERS: GraphLayer[] = [
  { id: 'frontend', label: 'Frontend', short: 'FE', fill: 'rgba(34,211,238,0.09)', stroke: 'rgba(34,211,238,0.32)', accent: '#67e8f9', icon: '◈' },
  { id: 'api', label: 'API', short: 'API', fill: 'rgba(59,130,246,0.085)', stroke: 'rgba(59,130,246,0.30)', accent: '#60a5fa', icon: '◎' },
  { id: 'serverless', label: 'Serverless', short: 'SVL', fill: 'rgba(251,191,36,0.10)', stroke: 'rgba(251,191,36,0.30)', accent: '#fbbf24', icon: '⚡' },
  { id: 'compute', label: 'Compute', short: 'CMP', fill: 'rgba(129,140,248,0.09)', stroke: 'rgba(129,140,248,0.28)', accent: '#818cf8', icon: '▣' },
  { id: 'security', label: 'Security/Auth', short: 'SEC', fill: 'rgba(248,113,113,0.09)', stroke: 'rgba(248,113,113,0.28)', accent: '#f87171', icon: '⛨' },
  { id: 'data', label: 'Data', short: 'DATA', fill: 'rgba(16,185,129,0.09)', stroke: 'rgba(52,211,153,0.30)', accent: '#34d399', icon: '◉' },
]

export const USER_NODE_TEMPLATES: UserNodeTemplate[] = [
  { id: 'lambda', label: 'Lambda', resourceType: 'aws_lambda_function', category: 'serverless', tier: 'serverless', provider: 'aws', weight: 5 },
  { id: 'ec2', label: 'EC2', resourceType: 'aws_instance', category: 'compute', tier: 'compute', provider: 'aws', weight: 4 },
  { id: 'ecs-service', label: 'ECS Service', resourceType: 'aws_ecs_service', category: 'container', tier: 'compute', provider: 'aws', weight: 5 },
  { id: 'cognito', label: 'Cognito', resourceType: 'aws_cognito_user_pool', category: 'security', tier: 'security', provider: 'aws', weight: 4 },
  { id: 'api-gateway', label: 'API Gateway', resourceType: 'aws_api_gateway_rest_api', category: 'integration', tier: 'api', provider: 'aws', weight: 5 },
  { id: 'load-balancer', label: 'Load Balancer', resourceType: 'aws_lb', category: 'network', tier: 'api', provider: 'aws', weight: 5 },
  { id: 'cloudfront', label: 'CloudFront', resourceType: 'aws_cloudfront_distribution', category: 'cdn', tier: 'frontend', provider: 'aws', weight: 5 },
  { id: 'route53', label: 'Route53', resourceType: 'aws_route53_record', category: 'dns', tier: 'frontend', provider: 'aws', weight: 3 },
  { id: 'rds', label: 'RDS', resourceType: 'aws_db_instance', category: 'database', tier: 'data', provider: 'aws', weight: 5 },
  { id: 'dynamodb', label: 'DynamoDB', resourceType: 'aws_dynamodb_table', category: 'database', tier: 'data', provider: 'aws', weight: 5 },
  { id: 's3', label: 'S3 Bucket', resourceType: 'aws_s3_bucket', category: 'storage', tier: 'data', provider: 'aws', weight: 4 },
  { id: 'sqs', label: 'SQS Queue', resourceType: 'aws_sqs_queue', category: 'queue', tier: 'compute', provider: 'aws', weight: 4 },
  { id: 'sns', label: 'SNS Topic', resourceType: 'aws_sns_topic', category: 'integration', tier: 'api', provider: 'aws', weight: 4 },
  { id: 'custom', label: 'Custom Service', resourceType: 'user_defined', category: 'other', tier: 'compute', provider: 'user', weight: 4 },
]

export const CATEGORY_COLORS: Record<string, string> = {
  compute: '#f59e0b',
  storage: '#38BDF8',      // sky blue (aligned with landing page secondary)
  database: '#C084FC',     // soft purple (aligned with landing page tertiary)
  network: '#6b7280',
  security: '#ef4444',
  monitoring: '#4ADE80',   // StackMap green (primary brand color)
  integration: '#FB923C',  // warm orange (aligned with landing page warning)
  cdn: '#06b6d4',
  dns: '#14b8a6',
  container: '#ec4899',
  serverless: '#fbbf24',
  queue: '#a78bfa',
  other: '#9ca3af',
}

export const EDGE_COLORS: Record<string, string> = {
  triggers: '#FB923C',       // warm orange (landing page warning)
  reads_from: '#38BDF8',     // sky blue (landing page secondary)
  writes_to: '#4ADE80',      // StackMap green (landing page primary)
  user_link: '#4ADE80',
  routes_to: '#94a3b8',
  references: '#64748b',
  contains: '#475569',
  authenticates: '#ef4444',
  cross_account_reference: '#C084FC', // purple (landing page tertiary)
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

const RESOURCE_TYPE_ICONS: Array<{ match: (resourceType: string) => boolean; icon: string }> = [
  {
    match: resourceType => resourceType.includes('lambda'),
    icon: '<path d="M13.8 3.5L6.5 13.2h4.3l-1 7.3 7.7-10h-4.4l.7-7z" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round"/>',
  },
  {
    match: resourceType => resourceType === 'aws_s3_bucket' || resourceType.includes('s3_bucket'),
    icon: '<path d="M5 9.5h14v8H5z" stroke="currentColor" stroke-width="2" fill="none"/><path d="M7 9.5V7.8A2.8 2.8 0 0 1 9.8 5h4.4A2.8 2.8 0 0 1 17 7.8v1.7" stroke="currentColor" stroke-width="2" fill="none"/><path d="M8 13.5h8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  },
  {
    match: resourceType => resourceType.includes('dynamodb'),
    icon: '<ellipse cx="12" cy="6" rx="5.8" ry="2.6" stroke="currentColor" stroke-width="2" fill="none"/><path d="M6.2 6v7.8c0 1.5 2.6 2.7 5.8 2.7s5.8-1.2 5.8-2.7V6" stroke="currentColor" stroke-width="2" fill="none"/><path d="M8 10.2h8M8 13.6h8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  },
  {
    match: resourceType => resourceType === 'aws_instance' || resourceType.includes('ec2'),
    icon: '<rect x="4" y="6" width="16" height="10" rx="2" stroke="currentColor" stroke-width="2" fill="none"/><path d="M8 18h8M9 10h1M12 10h1M15 10h1" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  },
  {
    match: resourceType => resourceType.includes('ecs'),
    icon: '<rect x="4" y="6" width="16" height="12" rx="2.5" stroke="currentColor" stroke-width="2" fill="none"/><path d="M8 6v12M16 6v12M4 10h16M4 14h16" stroke="currentColor" stroke-width="2"/>',
  },
  {
    match: resourceType => resourceType.includes('cognito'),
    icon: '<path d="M12 4l6 3v5c0 3.5-2.3 6.4-6 7.6-3.7-1.2-6-4.1-6-7.6V7l6-3z" stroke="currentColor" stroke-width="2" fill="none"/><circle cx="12" cy="10" r="1.8" fill="currentColor"/><path d="M9.5 14.5c.8-.9 1.7-1.3 2.5-1.3s1.7.4 2.5 1.3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  },
  {
    match: resourceType => resourceType.includes('api_gateway') || resourceType.includes('apigateway'),
    icon: '<path d="M4 8h8M9 5l3 3-3 3" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/><path d="M20 16h-8M15 13l-3 3 3 3" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  },
  {
    match: resourceType => resourceType === 'aws_lb' || resourceType.includes('load_balancer'),
    icon: '<circle cx="7" cy="8" r="2.2" stroke="currentColor" stroke-width="2" fill="none"/><circle cx="17" cy="8" r="2.2" stroke="currentColor" stroke-width="2" fill="none"/><circle cx="12" cy="16" r="2.4" stroke="currentColor" stroke-width="2" fill="none"/><path d="M9 8h6M8 9.5l2.5 4M16 9.5l-2.5 4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  },
  {
    match: resourceType => resourceType.includes('cloudfront'),
    icon: '<circle cx="12" cy="12" r="7" stroke="currentColor" stroke-width="2" fill="none"/><path d="M5 12h14M12 5c-2.2 2-2.2 12 0 14M12 5c2.2 2 2.2 12 0 14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>',
  },
  {
    match: resourceType => resourceType.includes('route53'),
    icon: '<path d="M6 6h6v6H6zM12 12h6v6h-6z" stroke="currentColor" stroke-width="2" fill="none"/><path d="M12 9h4M9 12v4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  },
  {
    match: resourceType => resourceType.includes('db_instance') || resourceType.includes('rds_cluster') || resourceType.includes('redshift'),
    icon: '<ellipse cx="12" cy="6" rx="6.5" ry="2.8" stroke="currentColor" stroke-width="2" fill="none"/><path d="M5.5 6v10c0 1.6 2.9 2.8 6.5 2.8s6.5-1.2 6.5-2.8V6" stroke="currentColor" stroke-width="2" fill="none"/><path d="M7 10.5h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  },
  {
    match: resourceType => resourceType.includes('sqs'),
    icon: '<rect x="4" y="6" width="14" height="3" rx="1.5" stroke="currentColor" stroke-width="2" fill="none"/><rect x="4" y="11" width="14" height="3" rx="1.5" stroke="currentColor" stroke-width="2" fill="none"/><rect x="4" y="16" width="14" height="3" rx="1.5" stroke="currentColor" stroke-width="2" fill="none"/><path d="M18 12h3M19.8 10.2l1.8 1.8-1.8 1.8" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  },
  {
    match: resourceType => resourceType.includes('sns'),
    icon: '<path d="M5 15V9l6-3v12l-6-3z" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round"/><path d="M14 9c1 .6 1.5 1.5 1.5 3S15 14.4 14 15M16.5 7.2C18.1 8.2 19 9.8 19 12s-.9 3.8-2.5 4.8" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>',
  },
  {
    match: resourceType => resourceType.includes('iam') || resourceType.includes('waf') || resourceType.includes('security_group'),
    icon: '<path d="M12 3.2l7 2.8v5.8c0 4.1-2.8 7.7-7 8.9-4.2-1.2-7-4.8-7-8.9V6l7-2.8z" stroke="currentColor" stroke-width="2" fill="none"/><path d="M8.6 12.2l2.2 2.2 4.6-4.6" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  },
]

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
  if (node.position_hint?.view_kind === 'account_summary') return 220
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
  if (node.position_hint?.view_kind === 'account_summary') return 84
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

export function slugifyLayerId(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export function labelForLayerId(layerId: string): string {
  return layerId
    .split('-')
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

export function buildLayerDefinitions(
  layerIds: string[],
  customLayers: Array<{ id: string; label: string }> = []
): GraphLayer[] {
  const customMap = new Map(customLayers.map(layer => [layer.id, layer.label]))
  const defaults = new Map(DEFAULT_GRAPH_LAYERS.map(layer => [layer.id, layer]))
  return layerIds.map((layerId, index) => {
    const defaultLayer = defaults.get(layerId)
    if (defaultLayer) return defaultLayer
    const hue = (index * 57 + 180) % 360
    return {
      id: layerId,
      label: customMap.get(layerId) || labelForLayerId(layerId),
      short: (customMap.get(layerId) || labelForLayerId(layerId)).slice(0, 4).toUpperCase(),
      fill: `hsla(${hue}, 70%, 55%, 0.08)`,
      stroke: `hsla(${hue}, 75%, 68%, 0.28)`,
      accent: `hsl(${hue}, 80%, 72%)`,
      icon: '◌',
    }
  })
}

export function normalizeLayerId(
  currentTier: string | undefined,
  category: string,
  resourceType: string
): string {
  if (currentTier && !['backend', 'frontend', 'api', 'data'].includes(currentTier)) {
    return currentTier
  }
  if (currentTier === 'frontend' || currentTier === 'api' || currentTier === 'data') {
    return currentTier
  }
  if (category === 'serverless' || resourceType.includes('lambda')) return 'serverless'
  if (category === 'security' || resourceType.includes('cognito') || resourceType.includes('iam') || resourceType.includes('waf')) return 'security'
  return 'compute'
}

export function getResourceIconPath(resourceType: string, category: string = 'other'): string {
  const normalized = resourceType.toLowerCase()
  const match = RESOURCE_TYPE_ICONS.find(entry => entry.match(normalized))
  if (match) return match.icon
  return CATEGORY_ICONS[category] || CATEGORY_ICONS.other
}

export function getNodeIconPath(node: Pick<StackMapNode, 'resource_type' | 'category'>): string {
  return getResourceIconPath(node.resource_type, node.category)
}

export function useGraph() {
  return {
    CATEGORY_COLORS,
    EDGE_COLORS,
    CATEGORY_ICONS,
    DEFAULT_GRAPH_LAYERS,
    truncate,
    formatResourceType,
    getNodeWidth,
    getNodeHeight,
    getNodeProminence,
    buildLayerDefinitions,
    normalizeLayerId,
    getResourceIconPath,
    getNodeIconPath,
  }
}
