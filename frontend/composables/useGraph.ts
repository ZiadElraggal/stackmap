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
  { id: 'step-functions', label: 'Step Functions', resourceType: 'aws_sfn_state_machine', category: 'serverless', tier: 'serverless', provider: 'aws', weight: 5 },
  { id: 'eventbridge', label: 'EventBridge', resourceType: 'aws_cloudwatch_event_rule', category: 'integration', tier: 'api', provider: 'aws', weight: 4 },
  { id: 'cloudwatch', label: 'CloudWatch', resourceType: 'aws_cloudwatch_metric_alarm', category: 'monitoring', tier: 'compute', provider: 'aws', weight: 3 },
  { id: 'vpc', label: 'VPC', resourceType: 'aws_vpc', category: 'network', tier: 'compute', provider: 'aws', weight: 3 },
  { id: 'cloudformation', label: 'CloudFormation', resourceType: 'aws_cloudformation_stack', category: 'other', tier: 'compute', provider: 'aws', weight: 3 },
  { id: 'secrets-manager', label: 'Secrets Manager', resourceType: 'aws_secretsmanager_secret', category: 'security', tier: 'security', provider: 'aws', weight: 3 },
  { id: 'kms', label: 'KMS', resourceType: 'aws_kms_key', category: 'security', tier: 'security', provider: 'aws', weight: 3 },
  { id: 'kinesis', label: 'Kinesis', resourceType: 'aws_kinesis_stream', category: 'queue', tier: 'compute', provider: 'aws', weight: 4 },
  { id: 'elastic-beanstalk', label: 'Elastic Beanstalk', resourceType: 'aws_elastic_beanstalk_environment', category: 'compute', tier: 'compute', provider: 'aws', weight: 4 },
  { id: 'ecr', label: 'ECR', resourceType: 'aws_ecr_repository', category: 'container', tier: 'compute', provider: 'aws', weight: 3 },
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

// AWS Architecture Icon-inspired SVG icons — designed for light-on-dark rendering.
// Each icon uses stroke-based rendering at 24x24 viewBox to match the official style.
const RESOURCE_TYPE_ICONS: Array<{ match: (resourceType: string) => boolean; icon: string }> = [
  // ── Serverless / Lambda ─────────────────────────────────────────
  {
    match: rt => rt.includes('lambda') || rt.includes('Lambda'),
    icon: '<path d="M4.5 19.5L9.2 4.5h2.2l3.2 10.5h2.9l2 4.5H4.5z" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linejoin="round"/><path d="M9.8 4.5l5 15" stroke="currentColor" stroke-width="1.8" fill="none"/>',
  },
  // ── S3 ──────────────────────────────────────────────────────────
  {
    match: rt => rt === 'aws_s3_bucket' || rt.includes('s3_bucket') || rt.includes('S3::Bucket'),
    icon: '<path d="M5.5 7c0-1.1 2.9-2 6.5-2s6.5.9 6.5 2v10c0 1.1-2.9 2-6.5 2s-6.5-.9-6.5-2V7z" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M5.5 7c0 1.1 2.9 2 6.5 2s6.5-.9 6.5-2" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M5.5 12c0 1.1 2.9 2 6.5 2s6.5-.9 6.5-2" stroke="currentColor" stroke-width="1.8" fill="none"/>',
  },
  // ── DynamoDB ────────────────────────────────────────────────────
  {
    match: rt => rt.includes('dynamodb') || rt.includes('DynamoDB'),
    icon: '<path d="M6 6.5c0-1.4 2.7-2.5 6-2.5s6 1.1 6 2.5" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M6 6.5v11c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5v-11" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M18 12c0 1.4-2.7 2.5-6 2.5S6 13.4 6 12" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M9 9l6 2M9 11l6-2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
  },
  // ── EC2 ─────────────────────────────────────────────────────────
  {
    match: rt => rt === 'aws_instance' || rt.includes('ec2') || rt.includes('EC2::Instance'),
    icon: '<rect x="4" y="5" width="16" height="14" rx="2" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M4 9h16" stroke="currentColor" stroke-width="1.8"/><circle cx="7" cy="7" r="1" fill="currentColor"/><path d="M9 13h6M9 16h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
  },
  // ── ECS ─────────────────────────────────────────────────────────
  {
    match: rt => rt.includes('ecs') || rt.includes('ECS'),
    icon: '<rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" stroke-width="1.8" fill="none"/><rect x="6" y="6" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.5" fill="none"/><rect x="13" y="6" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.5" fill="none"/><rect x="6" y="13" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.5" fill="none"/><rect x="13" y="13" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.5" fill="none"/>',
  },
  // ── ECR ─────────────────────────────────────────────────────────
  {
    match: rt => rt.includes('ecr') || rt.includes('ECR'),
    icon: '<rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M8 9l-3 3 3 3M16 9l3 3-3 3M13 8l-2 8" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  },
  // ── Cognito ─────────────────────────────────────────────────────
  {
    match: rt => rt.includes('cognito') || rt.includes('Cognito'),
    icon: '<circle cx="12" cy="8" r="3" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M6 19v-1c0-2.2 2.7-4 6-4s6 1.8 6 4v1" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round"/><path d="M12 3v2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M17.5 5.5l-1.4 1.4M6.5 5.5l1.4 1.4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
  },
  // ── API Gateway ─────────────────────────────────────────────────
  {
    match: rt => rt.includes('api_gateway') || rt.includes('apigateway') || rt.includes('ApiGateway'),
    icon: '<rect x="9" y="3" width="6" height="18" rx="1.5" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M9 8H4.5M9 12H4.5M9 16H4.5M15 8h4.5M15 12h4.5M15 16h4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
  },
  // ── Load Balancer (ELB) ─────────────────────────────────────────
  {
    match: rt => rt === 'aws_lb' || rt.includes('load_balancer') || rt.includes('ElasticLoadBalancing'),
    icon: '<circle cx="6" cy="7" r="2.5" stroke="currentColor" stroke-width="1.8" fill="none"/><circle cx="6" cy="17" r="2.5" stroke="currentColor" stroke-width="1.8" fill="none"/><circle cx="18" cy="12" r="2.5" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M8.3 8L15.5 11M8.3 16L15.5 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
  },
  // ── CloudFront ──────────────────────────────────────────────────
  {
    match: rt => rt.includes('cloudfront') || rt.includes('CloudFront'),
    icon: '<circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="1.8" fill="none"/><ellipse cx="12" cy="12" rx="3.5" ry="8" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M4 12h16" stroke="currentColor" stroke-width="1.5"/><path d="M5.5 7.5h13M5.5 16.5h13" stroke="currentColor" stroke-width="1" stroke-opacity="0.5"/>',
  },
  // ── Route 53 ────────────────────────────────────────────────────
  {
    match: rt => rt.includes('route53') || rt.includes('Route53'),
    icon: '<circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="1.8" fill="none"/><text x="12" y="16" text-anchor="middle" fill="currentColor" font-size="11" font-weight="700" font-family="sans-serif">53</text>',
  },
  // ── RDS ─────────────────────────────────────────────────────────
  {
    match: rt => rt.includes('db_instance') || rt.includes('rds_cluster') || rt.includes('rds') || rt.includes('RDS') || rt.includes('redshift'),
    icon: '<path d="M6 5.5c0-1.4 2.7-2.5 6-2.5s6 1.1 6 2.5" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M6 5.5v13c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5v-13" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M6 10c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M6 14.5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5" stroke="currentColor" stroke-width="1.8" fill="none"/>',
  },
  // ── SQS ─────────────────────────────────────────────────────────
  {
    match: rt => rt.includes('sqs') || rt.includes('SQS'),
    icon: '<path d="M4 6h12v4H4zM4 14h12v4H4z" stroke="currentColor" stroke-width="1.8" fill="none" rx="1"/><path d="M16 8h3M16 16h3M19 6l2 2-2 2M19 14l2 2-2 2" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/><path d="M4 12h12" stroke="currentColor" stroke-width="1" stroke-dasharray="2 2" stroke-opacity="0.4"/>',
  },
  // ── SNS ─────────────────────────────────────────────────────────
  {
    match: rt => rt.includes('sns') || rt.includes('SNS'),
    icon: '<circle cx="8" cy="12" r="4" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M12 12l5-5M12 12l5 0M12 12l5 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="17" cy="7" r="1.5" fill="currentColor" opacity="0.7"/><circle cx="17" cy="12" r="1.5" fill="currentColor" opacity="0.7"/><circle cx="17" cy="17" r="1.5" fill="currentColor" opacity="0.7"/>',
  },
  // ── Step Functions ──────────────────────────────────────────────
  {
    match: rt => rt.includes('sfn') || rt.includes('step_function') || rt.includes('StepFunctions'),
    icon: '<circle cx="12" cy="4.5" r="2" stroke="currentColor" stroke-width="1.8" fill="none"/><circle cx="12" cy="12" r="2" stroke="currentColor" stroke-width="1.8" fill="none"/><circle cx="12" cy="19.5" r="2" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M12 6.5v3.5M12 14v3.5" stroke="currentColor" stroke-width="1.8"/><path d="M14 4.5h4v7.5h-4M10 12h-4v7.5h4" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linejoin="round"/>',
  },
  // ── EventBridge ─────────────────────────────────────────────────
  {
    match: rt => rt.includes('eventbridge') || rt.includes('cloudwatch_event') || rt.includes('Events'),
    icon: '<rect x="4" y="4" width="16" height="16" rx="2" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M12 8v4l3 2" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="12" r="1" fill="currentColor"/><path d="M4 9h2M4 15h2M18 9h2M18 15h2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
  },
  // ── CloudWatch ──────────────────────────────────────────────────
  {
    match: rt => rt.includes('cloudwatch') || rt.includes('CloudWatch'),
    icon: '<circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M7 14l2.5-4 2 2.5 3-5L17 12" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  },
  // ── IAM ─────────────────────────────────────────────────────────
  {
    match: rt => rt.includes('iam') || rt.includes('IAM'),
    icon: '<circle cx="12" cy="8" r="3.5" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M5.5 20v-1.5c0-2.5 2.9-4.5 6.5-4.5s6.5 2 6.5 4.5V20" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round"/><path d="M15 7l2 1M15 9l2-1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
  },
  // ── VPC ─────────────────────────────────────────────────────────
  {
    match: rt => rt.includes('vpc') || rt.includes('VPC') || rt.includes('subnet'),
    icon: '<rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M3 10h18M10 3v18" stroke="currentColor" stroke-width="1" stroke-dasharray="3 2" stroke-opacity="0.4"/><circle cx="7" cy="7" r="1.5" fill="currentColor" opacity="0.6"/><circle cx="15" cy="15" r="1.5" fill="currentColor" opacity="0.6"/>',
  },
  // ── CloudFormation ──────────────────────────────────────────────
  {
    match: rt => rt.includes('cloudformation') || rt.includes('CloudFormation'),
    icon: '<path d="M12 3L4 7v10l8 4 8-4V7l-8-4z" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linejoin="round"/><path d="M4 7l8 4 8-4M12 11v10" stroke="currentColor" stroke-width="1.5" fill="none"/>',
  },
  // ── Secrets Manager ─────────────────────────────────────────────
  {
    match: rt => rt.includes('secretsmanager') || rt.includes('SecretsManager'),
    icon: '<rect x="5" y="10" width="14" height="10" rx="2" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M8 10V7a4 4 0 0 1 8 0v3" stroke="currentColor" stroke-width="1.8" fill="none"/><circle cx="12" cy="15" r="1.5" fill="currentColor"/><path d="M12 16.5V18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
  },
  // ── KMS ─────────────────────────────────────────────────────────
  {
    match: rt => rt.includes('kms') || rt.includes('KMS'),
    icon: '<circle cx="10" cy="12" r="5" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M14 12h6M17 10v4M19 10v4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="10" cy="12" r="1.5" fill="currentColor"/>',
  },
  // ── Kinesis ─────────────────────────────────────────────────────
  {
    match: rt => rt.includes('kinesis') || rt.includes('Kinesis'),
    icon: '<path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M14 3l3 3-3 3M10 9l-3 3 3 3M14 15l3 3-3 3" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  },
  // ── Elastic Beanstalk ───────────────────────────────────────────
  {
    match: rt => rt.includes('elastic_beanstalk') || rt.includes('ElasticBeanstalk'),
    icon: '<path d="M12 3c-3 4-5 6-5 9a5 5 0 0 0 10 0c0-3-2-5-5-9z" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M12 13v5M9 16h6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
  },
  // ── WAF / Security Group ────────────────────────────────────────
  {
    match: rt => rt.includes('waf') || rt.includes('WAF') || rt.includes('security_group'),
    icon: '<path d="M12 3.2l7 2.8v5.8c0 4.1-2.8 7.7-7 8.9-4.2-1.2-7-4.8-7-8.9V6l7-2.8z" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M8.6 12.2l2.2 2.2 4.6-4.6" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  },
  // ── AppSync ─────────────────────────────────────────────────────
  {
    match: rt => rt.includes('appsync') || rt.includes('AppSync'),
    icon: '<circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.8" fill="none"/><circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="1.5" fill="none" stroke-dasharray="4 2"/><path d="M12 4v4M12 16v4M4 12h4M16 12h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
  },
  // ── ElastiCache ─────────────────────────────────────────────────
  {
    match: rt => rt.includes('elasticache') || rt.includes('ElastiCache'),
    icon: '<rect x="4" y="7" width="16" height="10" rx="2" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M8 10v4M12 9v6M16 10v4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M4 12h16" stroke="currentColor" stroke-width="1" stroke-opacity="0.3"/>',
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
