import { defineStore } from 'pinia'

export interface StackMapNode {
  id: string
  name: string
  resource_type: string
  provider: string
  category: string
  properties: Record<string, any>
  tags: Record<string, string>
  metadata?: {
    account_id?: string
    account_name?: string
    region?: string
    org_path?: string
    view_kind?: string
    scanned?: boolean
  }
  position_hint: {
    tier: string
    weight: number
    manual_order?: number
    logical_parent?: string
    is_helper?: boolean
    diff_status?: string
    diff_changes?: Record<string, unknown>
    account_id?: string
    region?: string
    org_path?: string
    view_kind?: string
    // Drift detection
    drift_status?: 'in_sync' | 'missing' | 'extra' | 'drifted'
    drift_fields?: Record<string, { iac: any; live: any }>
    drift_severity?: 'info' | 'warning' | 'critical'
    // Cost overlay
    cost_monthly?: number
    cost_confidence?: 'high' | 'medium' | 'low' | 'unknown'
    cost_note?: string
  }
}

export interface StackMapEdge {
  id: string
  source: string
  target: string
  edge_type: string
  label: string
  color?: string
  metadata?: {
    source?: string
    inference_rule?: string
    confidence?: 'high' | 'medium' | 'low' | string
    evidence?: string
    api_calls?: string[]
    [key: string]: any
  }
}

export type EditSubmode = 'inspect' | 'structure' | 'connect'

export interface CustomLayerConfig {
  id: string
  label: string
  icon?: string
  accent?: string
}

export interface NodeOverrideMeta {
  name?: string
  provider?: string
  resource_type?: string
  category?: string
  weight?: number
  order?: number
}

interface OriginalNodeSnapshot {
  name: string
  provider: string
  resource_type: string
  category: string
  weight: number
  tier: string
}

export interface StackMapGroup {
  id: string
  name: string
  group_type: string
  children: string[]
  parent: string | null
  metadata?: {
    source_kind?: string
    account_id?: string
    account_name?: string
    ou_id?: string
    org_path?: string
    auto_strategy?: string
    evidence?: string
    confidence?: string
    [key: string]: any
  }
}

export interface NodePosition {
  x: number
  y: number
}

interface OrgTreeItem {
  id: string
  name: string
  group_type: string
  depth: number
  account_id?: string
}

export interface ComponentSummary {
  id: string
  name: string
  kind: 'service_component' | 'weakly_linked' | 'unlinked' | 'unlinked_bucket'
  nodeIds: string[]
  edgeIds: string[]
  resourceCount: number
  edgeCount: number
  dominantCategories: string[]
  entrypoints: string[]
  accountIds: string[]
  regions: string[]
  usefulnessScore: number
  helperRatio: number
  mostlyNetwork: boolean
  summary: string
}

export interface CostOverrideInput {
  memory_mb?: number
  invocations_per_month?: number
  avg_duration_ms?: number
  storage_gb?: number
  data_transfer_gb?: number
}

export interface CostNodeEstimate {
  resource_id: string
  resource_name: string
  resource_type: string
  monthly_estimate: number
  confidence: string
  pricing_model: string
  estimate_note: string
  breakdown?: Record<string, unknown> | null
}

export interface CostReportData {
  total_monthly: number
  by_node: Record<string, CostNodeEstimate>
  by_category: Record<string, number>
  by_tier: Record<string, number>
  by_group: Record<string, number>
  expensive_paths: Array<Record<string, unknown>>
  currency: string
}

interface EditHistorySnapshot {
  hiddenNodeIds: string[]
  hiddenNodeIdsBackup: string[] | null
  userEdges: StackMapEdge[]
  userNodes: StackMapNode[]
  customLayers: CustomLayerConfig[]
  nodeTierOverrides: Record<string, string>
  nodeOverrides: Record<string, NodeOverrideMeta>
  layoutLayers: string[]
}

const HELPER_RESOURCE_TYPES = new Set([
  'aws_iam_role',
  'aws_iam_policy',
  'aws_iam_role_policy',
  'aws_iam_role_policy_attachment',
  'aws_cloudwatch_log_group',
  'aws_lambda_permission',
  'aws_sns_topic_subscription',
  'aws_cloudfront_origin_access_control',
  'aws_api_gateway_deployment',
  'aws_api_gateway_stage',
  'aws_api_gateway_method',
  'aws_api_gateway_resource',
  'aws_api_gateway_integration',
  'aws_lb_listener',
  'aws_lb_listener_rule',
  'aws_lb_target_group',
  'aws_db_subnet_group',
  'aws_elasticache_subnet_group',
  'aws_s3_bucket_policy',
  'aws_s3_bucket_versioning',
  'aws_s3_bucket_server_side_encryption_configuration',
  'aws_route_table',
  'aws_route_table_association',
  'aws_eip',
  'aws_flow_log',
  'aws_security_group',
  'aws_acm_certificate',
  'aws_s3_bucket_public_access_block',
  'aws_s3_bucket_website_configuration',
  'aws_s3_bucket_cors_configuration',
  'aws_s3_bucket_lifecycle_configuration',
  'aws_s3_bucket_notification',
  'aws_nat_gateway',
  'aws_internet_gateway',
  'aws_cloudwatch_event_target',
  'aws_secretsmanager_secret_version',
  'aws_cognito_user_pool_client',
  'aws_cognito_identity_pool',
  'aws_wafv2_web_acl_association',
  'aws_acm_certificate_validation',
  'aws_ecr_lifecycle_policy',
  'aws_appsync_datasource',
  'aws_appsync_resolver',
  'AWS::ApiGateway::Deployment',
  'AWS::ApiGateway::Stage',
  'AWS::ApiGateway::Method',
  'AWS::ApiGateway::Resource',
  'AWS::ApiGateway::Integration',
  'AWS::ApiGatewayV2::Integration',
  'AWS::ApiGatewayV2::Route',
  'AWS::ApiGatewayV2::Stage',
  'AWS::ApiGatewayV2::Authorizer',
  'AWS::Lambda::Permission',
  'AWS::Lambda::LayerVersion',
  'AWS::Logs::LogGroup',
  'AWS::CloudWatch::Dashboard',
  'AWS::IAM::Policy',
  'AWS::IAM::ManagedPolicy',
  'AWS::S3::BucketPolicy',
  'AWS::ElasticLoadBalancingV2::Listener',
  'AWS::ElasticLoadBalancingV2::ListenerRule',
  'AWS::ElasticLoadBalancingV2::TargetGroup',
  'AWS::EC2::RouteTable',
  'AWS::EC2::SubnetRouteTableAssociation',
  'AWS::EC2::EIP',
  'AWS::EC2::NatGateway',
  'AWS::Serverless::LayerVersion',
  'AWS::WAFv2::WebACLAssociation',
  'AWS::CertificateManager::Certificate',
  'AWS::ElastiCache::SubnetGroup',
  'AWS::AppSync::DataSource',
  'AWS::AppSync::Resolver',
  'AWS::ECR::Repository',
])

const PRIMARY_CATEGORY_PRIORITY: Record<string, number> = {
  serverless: 0,
  compute: 1,
  container: 2,
  integration: 3,
  queue: 4,
  database: 5,
  storage: 6,
  network: 7,
  cdn: 8,
  dns: 9,
  monitoring: 10,
  other: 20,
  security: 30,
}

const ARCH_DROPPED_EDGE_TYPES = new Set(['authenticates', 'contains'])
const ORG_GROUP_TYPES = new Set(['organization_root', 'ou', 'account'])
const COMPONENT_ENTRY_CATEGORIES = new Set(['cdn', 'dns', 'integration', 'network'])
const COMPONENT_CORE_CATEGORIES = new Set(['serverless', 'compute', 'container', 'queue', 'database', 'storage'])
const NETWORK_HEAVY_RESOURCE_TYPES = new Set([
  'aws_vpc',
  'aws_subnet',
  'aws_security_group',
  'aws_route_table',
  'aws_route_table_association',
  'aws_nat_gateway',
  'aws_internet_gateway',
  'aws_eip',
])
const UNLINKED_COMPONENT_ID = '__unlinked_resources__'
const COMPONENT_VIEW_THRESHOLD_DEFAULT = 35
const DEFAULT_LAYOUT_LAYERS = ['frontend', 'api', 'serverless', 'compute', 'security', 'data']

function normalizeNodeTier(node: StackMapNode): string {
  const currentTier = node.position_hint?.tier
  if (currentTier && !['backend', 'frontend', 'api', 'data'].includes(currentTier)) {
    return currentTier
  }
  if (currentTier === 'frontend' || currentTier === 'api' || currentTier === 'data') {
    return currentTier
  }
  if (node.category === 'serverless' || node.resource_type.includes('lambda')) return 'serverless'
  if (
    node.category === 'security' ||
    node.resource_type.includes('cognito') ||
    node.resource_type.includes('iam') ||
    node.resource_type.includes('waf')
  ) return 'security'
  return 'compute'
}

const REFERENCE_TYPE_ALLOWLIST = new Set([
  'aws_ecs_service->aws_ecs_cluster',
  'aws_ecs_service->aws_ecs_task_definition',
  'aws_ecs_service->aws_lb_target_group',
  'aws_lb->aws_subnet',
  'aws_lb->aws_vpc',
  'aws_lb_listener->aws_lb_target_group',
  'aws_lb_listener_rule->aws_lb_target_group',
  'aws_lambda_function->aws_subnet',
  'aws_lambda_function->aws_vpc',
  'aws_nat_gateway->aws_eip',
  'aws_route_table_association->aws_route_table',
  'aws_route_table_association->aws_subnet',
  'aws_api_gateway_stage->aws_api_gateway_deployment',
  'aws_route53_record->aws_route53_zone',
  'aws_cognito_user_pool_client->aws_cognito_user_pool',
  'aws_wafv2_web_acl_association->aws_wafv2_web_acl',
  'aws_elasticache_replication_group->aws_elasticache_subnet_group',
  'aws_appsync_datasource->aws_appsync_graphql_api',
  'aws_kinesis_firehose_delivery_stream->aws_kinesis_stream',
  'aws_cloudwatch_event_target->aws_cloudwatch_event_rule',
])

function shouldKeepReferenceEdge(source: StackMapNode | undefined, target: StackMapNode | undefined): boolean {
  if (!source || !target) return false

  const pair = `${source.resource_type}->${target.resource_type}`
  if (REFERENCE_TYPE_ALLOWLIST.has(pair)) return true

  const sourceIsComputeLike = ['compute', 'container', 'integration', 'serverless'].includes(source.category)
  const targetIsDataLike = ['database', 'storage', 'queue'].includes(target.category)
  if (sourceIsComputeLike && targetIsDataLike) return true

  const sourceIsEntry = ['cdn', 'dns', 'network', 'integration'].includes(source.category)
  const targetIsCore = ['compute', 'container', 'integration', 'database', 'storage', 'queue'].includes(target.category)
  if (sourceIsEntry && targetIsCore) return true

  return false
}

function isHelperNode(node: StackMapNode): boolean {
  if (node.position_hint?.is_helper) return true
  return HELPER_RESOURCE_TYPES.has(node.resource_type)
}

function buildAdjacency(edges: StackMapEdge[]): Map<string, Set<string>> {
  const adjacency = new Map<string, Set<string>>()
  for (const edge of edges) {
    if (!adjacency.has(edge.source)) adjacency.set(edge.source, new Set())
    if (!adjacency.has(edge.target)) adjacency.set(edge.target, new Set())
    adjacency.get(edge.source)?.add(edge.target)
    adjacency.get(edge.target)?.add(edge.source)
  }
  return adjacency
}

function slugifyName(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function pickSharedServiceTag(nodes: StackMapNode[]): string | null {
  const keys = ['service', 'Service', 'app', 'App', 'application', 'Application', 'project', 'Project']
  for (const key of keys) {
    const values = [...new Set(
      nodes
        .map(node => node.tags?.[key])
        .filter((value): value is string => Boolean(value && value.trim()))
        .map(value => value.trim())
    )]
    if (values.length === 1) return values[0]
  }
  return null
}

function serviceTagForNode(node: StackMapNode): string | null {
  const keys = ['service', 'Service', 'app', 'App', 'application', 'Application', 'project', 'Project']
  for (const key of keys) {
    const value = node.tags?.[key]
    if (value && value.trim()) return value.trim()
  }
  return null
}

function isMeaningfulServiceTag(tag: string | null): tag is string {
  if (!tag) return false
  const normalized = slugifyName(tag)
  return normalized.length >= 3 && !['default', 'main', 'primary', 'shared'].includes(normalized)
}

function topCategoriesForNodes(nodes: StackMapNode[]): string[] {
  const counts: Record<string, number> = {}
  for (const node of nodes) {
    counts[node.category] = (counts[node.category] || 0) + 1
  }
  return Object.entries(counts)
    .sort((a, b) => {
      if (b[1] !== a[1]) return b[1] - a[1]
      const pa = PRIMARY_CATEGORY_PRIORITY[a[0]] ?? 100
      const pb = PRIMARY_CATEGORY_PRIORITY[b[0]] ?? 100
      return pa - pb
    })
    .slice(0, 3)
    .map(([category]) => category)
}

function componentAnchorName(nodes: StackMapNode[], adjacency: Map<string, Set<string>>): string {
  const sharedTag = pickSharedServiceTag(nodes)
  if (sharedTag) return sharedTag

  const candidates = [...nodes].sort((a, b) => {
    const aIsEntry = COMPONENT_ENTRY_CATEGORIES.has(a.category) ? 1 : 0
    const bIsEntry = COMPONENT_ENTRY_CATEGORIES.has(b.category) ? 1 : 0
    if (aIsEntry !== bIsEntry) return bIsEntry - aIsEntry
    const aIsCore = COMPONENT_CORE_CATEGORIES.has(a.category) ? 1 : 0
    const bIsCore = COMPONENT_CORE_CATEGORIES.has(b.category) ? 1 : 0
    if (aIsCore !== bIsCore) return bIsCore - aIsCore
    const ad = adjacency.get(a.id)?.size || 0
    const bd = adjacency.get(b.id)?.size || 0
    if (ad !== bd) return bd - ad
    const pa = PRIMARY_CATEGORY_PRIORITY[a.category] ?? 100
    const pb = PRIMARY_CATEGORY_PRIORITY[b.category] ?? 100
    if (pa !== pb) return pa - pb
    return a.name.localeCompare(b.name)
  })
  return candidates[0]?.name || 'component'
}

function describeComponent(
  nodes: StackMapNode[],
  edges: StackMapEdge[],
  adjacency: Map<string, Set<string>>
): Omit<ComponentSummary, 'id'> {
  const resourceCount = nodes.length
  const edgeCount = edges.length
  const helperCount = nodes.filter(isHelperNode).length
  const helperRatio = resourceCount > 0 ? helperCount / resourceCount : 0
  const networkCount = nodes.filter(node => node.category === 'network' || NETWORK_HEAVY_RESOURCE_TYPES.has(node.resource_type)).length
  const entrypoints = nodes
    .filter(node => COMPONENT_ENTRY_CATEGORIES.has(node.category))
    .sort((a, b) => a.name.localeCompare(b.name))
    .slice(0, 3)
    .map(node => node.name)
  const coreCount = nodes.filter(node => COMPONENT_CORE_CATEGORIES.has(node.category)).length
  const accountIds = [...new Set(nodes.map(node => accountIdForNode(node)).filter((value): value is string => Boolean(value)))].sort()
  const regions = [...new Set(nodes.map(node => node.metadata?.region || node.position_hint?.region).filter((value): value is string => Boolean(value)))].sort()
  const dominantCategories = topCategoriesForNodes(nodes)
  const mostlyNetwork = resourceCount > 0 && networkCount / resourceCount >= 0.6
  const connectivityBonus = Math.max(0, edgeCount - resourceCount + 1)
  const usefulnessScore =
    entrypoints.length * 4 +
    coreCount * 3 +
    connectivityBonus * 2 +
    (mostlyNetwork ? -4 : 0) +
    Math.round((1 - helperRatio) * 4) -
    Math.max(0, 2 - resourceCount)

  let kind: ComponentSummary['kind'] = 'service_component'
  if (
    resourceCount <= 1 ||
    (mostlyNetwork && coreCount === 0) ||
    usefulnessScore < 4 ||
    (entrypoints.length === 0 && coreCount <= 1 && resourceCount <= 3)
  ) {
    kind = 'unlinked'
  } else if (usefulnessScore < 8 || (mostlyNetwork && coreCount <= 1) || resourceCount <= 3) {
    kind = 'weakly_linked'
  }

  const anchor = componentAnchorName(nodes, adjacency)
  const slug = slugifyName(anchor)
  const summaryBits = [
    dominantCategories.slice(0, 2).join(' + '),
    entrypoints.length ? `${entrypoints.length} entrypoint${entrypoints.length === 1 ? '' : 's'}` : 'internal',
    accountIds.length > 1 ? `${accountIds.length} accounts` : `${regions.length || 1} region${regions.length === 1 ? '' : 's'}`,
  ].filter(Boolean)

  return {
    name: slug || anchor || 'component',
    kind,
    nodeIds: nodes.map(node => node.id),
    edgeIds: edges.map(edge => edge.id),
    resourceCount,
    edgeCount,
    dominantCategories,
    entrypoints,
    accountIds,
    regions,
    usefulnessScore,
    helperRatio,
    mostlyNetwork,
    summary: summaryBits.join(' · '),
  }
}

function rankPrimary(nodesById: Map<string, StackMapNode>, id: string): number {
  const node = nodesById.get(id)
  if (!node) return 999
  return PRIMARY_CATEGORY_PRIORITY[node.category] ?? 100
}

function pickBestPrimary(nodesById: Map<string, StackMapNode>, candidates: string[]): string | null {
  if (!candidates.length) return null
  return [...candidates].sort((a, b) => {
    const ra = rankPrimary(nodesById, a)
    const rb = rankPrimary(nodesById, b)
    if (ra !== rb) return ra - rb
    const na = nodesById.get(a)?.name || a
    const nb = nodesById.get(b)?.name || b
    return na.localeCompare(nb)
  })[0]
}

function buildHelperParentMap(nodes: StackMapNode[], edges: StackMapEdge[]): Map<string, string> {
  const nodesById = new Map(nodes.map(n => [n.id, n]))
  const helpers = nodes.filter(isHelperNode)
  const helperIds = new Set(helpers.map(n => n.id))
  const adjacency = buildAdjacency(edges)

  const map = new Map<string, string>()

  for (const node of nodes) {
    const explicitParent = node.position_hint?.logical_parent
    if (explicitParent) map.set(node.id, explicitParent)
  }

  for (const helper of helpers) {
    if (map.has(helper.id)) continue

    const neighbors = [...(adjacency.get(helper.id) || [])]
    const directPrimary = neighbors.filter(id => !helperIds.has(id))
    const firstChoice = pickBestPrimary(nodesById, directPrimary)
    if (firstChoice) {
      map.set(helper.id, firstChoice)
      continue
    }

    const depthTwoPrimary = new Set<string>()
    for (const neighbor of neighbors) {
      for (const n2 of adjacency.get(neighbor) || []) {
        if (!helperIds.has(n2)) depthTwoPrimary.add(n2)
      }
    }

    const secondChoice = pickBestPrimary(nodesById, [...depthTwoPrimary])
    if (secondChoice) {
      map.set(helper.id, secondChoice)
    }
  }

  return map
}

function accountIdForNode(node: StackMapNode): string | undefined {
  return node.metadata?.account_id || node.position_hint?.account_id
}

function groupTouchesAccount(
  group: StackMapGroup,
  nodesById: Map<string, StackMapNode>,
  accountId: string
): boolean {
  if (group.metadata?.account_id === accountId) return true
  return group.children.some(childId => accountIdForNode(nodesById.get(childId) as StackMapNode) === accountId)
}

function dominantCategory(counts: Record<string, number>): string {
  const entries = Object.entries(counts)
  if (!entries.length) return 'other'
  entries.sort((a, b) => {
    if (b[1] !== a[1]) return b[1] - a[1]
    const pa = PRIMARY_CATEGORY_PRIORITY[a[0]] ?? 100
    const pb = PRIMARY_CATEGORY_PRIORITY[b[0]] ?? 100
    return pa - pb
  })
  return entries[0][0]
}

function buildOrganizationSummaryNodes(
  nodes: StackMapNode[],
  groups: StackMapGroup[],
  metadata: Record<string, any>
): StackMapNode[] {
  const countsByAccount: Record<string, Record<string, number>> = {}
  const regionByAccount: Record<string, Set<string>> = {}

  for (const node of nodes) {
    const accountId = accountIdForNode(node)
    if (!accountId) continue
    countsByAccount[accountId] ||= {}
    countsByAccount[accountId][node.category] = (countsByAccount[accountId][node.category] || 0) + 1
    regionByAccount[accountId] ||= new Set()
    const region = node.metadata?.region || node.position_hint?.region
    if (region) regionByAccount[accountId].add(region)
  }

  const accountGroups = groups.filter(group => group.group_type === 'account')
  const accountMeta = new Map<string, any>()
  for (const group of accountGroups) {
    const accountId = group.metadata?.account_id || group.id.replace(/^group:account:/, '')
    accountMeta.set(accountId, {
      id: accountId,
      name: group.metadata?.account_name || group.name || accountId,
      ou_path: group.metadata?.org_path,
      scanned: Boolean(group.children.length),
    })
  }

  const orgAccounts = Array.isArray(metadata.organization?.accounts) ? metadata.organization.accounts : []
  for (const account of orgAccounts) {
    accountMeta.set(account.id, {
      id: account.id,
      name: account.name || account.id,
      ou_path: account.ou_path,
      scanned: accountMeta.get(account.id)?.scanned ?? false,
    })
  }

  return [...accountMeta.values()]
    .sort((a, b) => String(a.ou_path || '').localeCompare(String(b.ou_path || '')) || String(a.name).localeCompare(String(b.name)))
    .map(account => {
      const categoryCounts = countsByAccount[account.id] || {}
      const resourceCount = Object.values(categoryCounts).reduce((sum, count) => sum + count, 0)
      const category = dominantCategory(categoryCounts)
      return {
        id: `account-summary:${account.id}`,
        name: account.name,
        resource_type: 'aws_account',
        provider: 'aws',
        category,
        properties: {
          account_id: account.id,
          resource_count: resourceCount,
          regions: [...(regionByAccount[account.id] || new Set())],
          categories: categoryCounts,
          scanned: resourceCount > 0 || Boolean(account.scanned),
          ou_path: account.ou_path,
        },
        tags: {},
        metadata: {
          account_id: account.id,
          account_name: account.name,
          org_path: account.ou_path,
          view_kind: 'account_summary',
          scanned: resourceCount > 0 || Boolean(account.scanned),
        },
        position_hint: {
          tier: 'backend',
          weight: resourceCount > 0 ? 4 : 2,
          account_id: account.id,
          org_path: account.ou_path,
          view_kind: 'account_summary',
        },
      } as StackMapNode
    })
}

function buildOrganizationGroups(
  rawGroups: StackMapGroup[],
  summaryNodes: StackMapNode[],
  rawNodes: StackMapNode[]
): StackMapGroup[] {
  const summaryIdByAccount = new Map(summaryNodes.map(node => [node.metadata?.account_id, node.id]))
  const nodesById = new Map(rawNodes.map(node => [node.id, node]))
  const orgGroups = rawGroups.filter(group => ORG_GROUP_TYPES.has(group.group_type))

  if (!orgGroups.length) {
    return rawGroups
      .filter(group => group.group_type === 'account')
      .map(group => {
        const accountId = group.metadata?.account_id || group.id.replace(/^group:account:/, '')
        const summaryId = summaryIdByAccount.get(accountId)
        return {
          ...group,
          children: summaryId ? [summaryId] : [],
        }
      })
  }

  return orgGroups.map(group => {
    const accountIds = new Set(
      group.children
        .map(childId => accountIdForNode(nodesById.get(childId) as StackMapNode))
        .filter((accountId): accountId is string => Boolean(accountId))
    )
    if (group.group_type === 'account') {
      const accountId = group.metadata?.account_id || group.id.replace(/^group:account:/, '')
      const summaryId = summaryIdByAccount.get(accountId)
      return {
        ...group,
        children: summaryId ? [summaryId] : [],
      }
    }
    return {
      ...group,
      children: [...accountIds]
        .map(accountId => summaryIdByAccount.get(accountId))
        .filter((id): id is string => Boolean(id)),
    }
  })
}

function buildOrganizationEdges(nodes: StackMapNode[], edges: StackMapEdge[], showCrossAccount: boolean): StackMapEdge[] {
  const nodeById = new Map(nodes.map(node => [node.id, node]))
  const dedup = new Map<string, number>()

  for (const edge of edges) {
    if (!showCrossAccount && edge.edge_type === 'cross_account_reference') continue
    const source = nodeById.get(edge.source)
    const target = nodeById.get(edge.target)
    const sourceAccount = source ? accountIdForNode(source) : undefined
    const targetAccount = target ? accountIdForNode(target) : undefined
    if (!sourceAccount || !targetAccount || sourceAccount === targetAccount) continue
    const key = `${sourceAccount}|${targetAccount}`
    dedup.set(key, (dedup.get(key) || 0) + 1)
  }

  return [...dedup.entries()].map(([key, count]) => {
    const [sourceAccount, targetAccount] = key.split('|')
    return {
      id: `account-summary:${sourceAccount}->account-summary:${targetAccount}:cross_account_reference`,
      source: `account-summary:${sourceAccount}`,
      target: `account-summary:${targetAccount}`,
      edge_type: 'cross_account_reference',
      label: `${count} cross-account link${count === 1 ? '' : 's'}`,
    }
  })
}

function flattenOrganizationTree(groups: StackMapGroup[]): OrgTreeItem[] {
  const byParent = new Map<string | null, StackMapGroup[]>()
  for (const group of groups) {
    const key = group.parent ?? null
    if (!byParent.has(key)) byParent.set(key, [])
    byParent.get(key)?.push(group)
  }

  const result: OrgTreeItem[] = []

  const walk = (parent: string | null, depth: number) => {
    const children = [...(byParent.get(parent) || [])].sort((a, b) => {
      const order = { organization_root: 0, ou: 1, account: 2 }
      const ao = order[a.group_type as keyof typeof order] ?? 99
      const bo = order[b.group_type as keyof typeof order] ?? 99
      if (ao !== bo) return ao - bo
      return a.name.localeCompare(b.name)
    })
    for (const group of children) {
      result.push({
        id: group.id,
        name: group.name,
        group_type: group.group_type,
        depth,
        account_id: group.metadata?.account_id,
      })
      walk(group.id, depth + 1)
    }
  }

  walk(null, 0)
  return result
}

function buildComponentSummaries(nodes: StackMapNode[], edges: StackMapEdge[]): ComponentSummary[] {
  const nodeById = new Map(nodes.map(node => [node.id, node]))
  const adjacency = buildAdjacency(edges)
  const seen = new Set<string>()
  const summaries: ComponentSummary[] = []

  for (const node of nodes) {
    if (seen.has(node.id)) continue
    const queue = [node.id]
    const componentNodeIds: string[] = []
    seen.add(node.id)

    while (queue.length > 0) {
      const current = queue.shift() as string
      componentNodeIds.push(current)
      for (const neighbor of adjacency.get(current) || []) {
        if (seen.has(neighbor)) continue
        seen.add(neighbor)
        queue.push(neighbor)
      }
    }

    const componentNodes = componentNodeIds
      .map(id => nodeById.get(id))
      .filter((value): value is StackMapNode => Boolean(value))
    const componentIdSet = new Set(componentNodeIds)
    const componentEdges = edges.filter(edge => componentIdSet.has(edge.source) && componentIdSet.has(edge.target))

    const tagSeeds = new Map<string, Set<string>>()
    for (const componentNode of componentNodes) {
      const tag = serviceTagForNode(componentNode)
      if (!isMeaningfulServiceTag(tag)) continue
      if (!tagSeeds.has(tag)) tagSeeds.set(tag, new Set())
      tagSeeds.get(tag)?.add(componentNode.id)
    }

    const strongTags = [...tagSeeds.entries()]
      .filter(([_, ids]) => ids.size >= 2)
      .map(([tag]) => tag)

    if (strongTags.length >= 2) {
      const nodeAssignments = new Map<string, string>()
      for (const tag of strongTags) {
        for (const nodeId of tagSeeds.get(tag) || []) {
          nodeAssignments.set(nodeId, tag)
        }
      }

      const orderedNodeIds = [...componentNodeIds].sort((a, b) => {
        const aNode = nodeById.get(a)
        const bNode = nodeById.get(b)
        const aHelper = aNode && isHelperNode(aNode) ? 1 : 0
        const bHelper = bNode && isHelperNode(bNode) ? 1 : 0
        if (aHelper !== bHelper) return aHelper - bHelper
        return (adjacency.get(b)?.size || 0) - (adjacency.get(a)?.size || 0)
      })

      for (let pass = 0; pass < 3; pass += 1) {
        let changed = false
        for (const nodeId of orderedNodeIds) {
          if (nodeAssignments.has(nodeId)) continue
          const node = nodeById.get(nodeId)
          if (!node) continue

          const neighborTags = [...new Set(
            [...(adjacency.get(nodeId) || [])]
              .map(neighborId => nodeAssignments.get(neighborId))
              .filter((value): value is string => Boolean(value))
          )]

          const logicalParent = node.position_hint?.logical_parent
          const parentTag = logicalParent ? nodeAssignments.get(logicalParent) : null

          if (parentTag && neighborTags.length <= 1) {
            nodeAssignments.set(nodeId, parentTag)
            changed = true
            continue
          }

          if (neighborTags.length === 1) {
            nodeAssignments.set(nodeId, neighborTags[0])
            changed = true
          }
        }
        if (!changed) break
      }

      const subcomponentNodeIds = new Map<string, Set<string>>()
      for (const tag of strongTags) subcomponentNodeIds.set(tag, new Set())
      const leftoverNodeIds = new Set<string>()

      for (const nodeId of componentNodeIds) {
        const assignedTag = nodeAssignments.get(nodeId)
        if (assignedTag && subcomponentNodeIds.has(assignedTag)) {
          subcomponentNodeIds.get(assignedTag)?.add(nodeId)
        } else {
          leftoverNodeIds.add(nodeId)
        }
      }

      for (const [tag, ids] of subcomponentNodeIds.entries()) {
        if (ids.size === 0) continue
        const subNodes = [...ids]
          .map(id => nodeById.get(id))
          .filter((value): value is StackMapNode => Boolean(value))
        const subIdSet = new Set(ids)
        const subEdges = componentEdges.filter(edge => subIdSet.has(edge.source) && subIdSet.has(edge.target))
        const described = describeComponent(subNodes, subEdges, adjacency)
        summaries.push({
          id: `component:${slugifyName(tag) || described.name || subNodes[0]?.id || summaries.length}`,
          ...described,
          name: slugifyName(tag) || described.name,
        })
      }

      if (leftoverNodeIds.size > 0) {
        const leftoverNodes = [...leftoverNodeIds]
          .map(id => nodeById.get(id))
          .filter((value): value is StackMapNode => Boolean(value))
        const leftoverIdSet = new Set(leftoverNodeIds)
        const leftoverEdges = componentEdges.filter(edge => leftoverIdSet.has(edge.source) && leftoverIdSet.has(edge.target))
        const described = describeComponent(leftoverNodes, leftoverEdges, adjacency)
        summaries.push({
          id: `component:${described.name || leftoverNodes[0]?.id || summaries.length}`,
          ...described,
        })
      }

      continue
    }

    const described = describeComponent(componentNodes, componentEdges, adjacency)
    summaries.push({
      id: `component:${described.name || componentNodes[0]?.id || summaries.length}`,
      ...described,
    })
  }

  const visibleSummaries: ComponentSummary[] = []
  const unlinkedNodeIds = new Set<string>()
  const unlinkedEdgeIds = new Set<string>()

  for (const summary of summaries) {
    if (summary.kind === 'service_component' || summary.kind === 'weakly_linked') {
      visibleSummaries.push(summary)
      continue
    }
    for (const nodeId of summary.nodeIds) unlinkedNodeIds.add(nodeId)
    for (const edgeId of summary.edgeIds) unlinkedEdgeIds.add(edgeId)
  }

  if (unlinkedNodeIds.size > 0) {
    const unlinkedNodes = [...unlinkedNodeIds]
      .map(id => nodeById.get(id))
      .filter((value): value is StackMapNode => Boolean(value))
    const unlinkedEdges = edges.filter(edge => unlinkedEdgeIds.has(edge.id))
    const categories = topCategoriesForNodes(unlinkedNodes)
    const accounts = [...new Set(unlinkedNodes.map(node => accountIdForNode(node)).filter((value): value is string => Boolean(value)))].sort()
    const regions = [...new Set(unlinkedNodes.map(node => node.metadata?.region || node.position_hint?.region).filter((value): value is string => Boolean(value)))].sort()
    visibleSummaries.push({
      id: UNLINKED_COMPONENT_ID,
      name: 'unlinked-resources',
      kind: 'unlinked_bucket',
      nodeIds: [...unlinkedNodeIds],
      edgeIds: [...unlinkedEdgeIds],
      resourceCount: unlinkedNodes.length,
      edgeCount: unlinkedEdges.length,
      dominantCategories: categories,
      entrypoints: [],
      accountIds: accounts,
      regions,
      usefulnessScore: 0,
      helperRatio: unlinkedNodes.length > 0 ? unlinkedNodes.filter(isHelperNode).length / unlinkedNodes.length : 0,
      mostlyNetwork: unlinkedNodes.length > 0 && unlinkedNodes.every(node => node.category === 'network' || NETWORK_HEAVY_RESOURCE_TYPES.has(node.resource_type)),
      summary: `${categories.slice(0, 2).join(' + ') || 'mixed'} · ${accounts.length || 1} account${accounts.length === 1 ? '' : 's'}`,
    })
  }

  return visibleSummaries.sort((a, b) => {
    if (a.kind === 'unlinked_bucket' && b.kind !== 'unlinked_bucket') return 1
    if (b.kind === 'unlinked_bucket' && a.kind !== 'unlinked_bucket') return -1
    if (b.usefulnessScore !== a.usefulnessScore) return b.usefulnessScore - a.usefulnessScore
    if (b.resourceCount !== a.resourceCount) return b.resourceCount - a.resourceCount
    return a.name.localeCompare(b.name)
  })
}

export const useGraphStore = defineStore('graph', {
  state: () => ({
    nodes: [] as StackMapNode[],
    edges: [] as StackMapEdge[],
    groups: [] as StackMapGroup[],
    metadata: {} as Record<string, any>,
    positions: {} as Record<string, NodePosition>,
    selectedNodeId: null as string | null,
    hoveredNodeId: null as string | null,
    categoryFilters: {} as Record<string, boolean>,
    edgeTypeFilters: {} as Record<string, boolean>,
    minWeight: 1,
    hopLimit: 0,
    searchQuery: '',
    viewMode: 'architecture' as 'architecture' | 'raw' | 'organization' | 'components',
    loaded: false,
    diffMode: false as boolean,
    diffSlider: 0.5 as number,
    showOnlyChanges: false as boolean,
    activeAccountId: null as string | null,
    activeOrgGroupId: null as string | null,
    activeComponentId: null as string | null,
    componentViewThreshold: COMPONENT_VIEW_THRESHOLD_DEFAULT,
    showUnlinkedResources: true as boolean,
    showWeaklyLinkedComponents: false as boolean,
    collapseNetworkScaffolding: true as boolean,
    showCrossAccountEdges: true as boolean,
    showLowConfidenceEdges: true as boolean,

    // Edit mode state
    editMode: false as boolean,
    editSubmode: 'inspect' as EditSubmode,
    hiddenNodeIds: [] as string[],
    hiddenNodeIdsBackup: null as string[] | null,
    userEdges: [] as StackMapEdge[],
    userNodes: [] as StackMapNode[],
    connectingFromNodeId: null as string | null,
    layoutVersion: 0 as number,
    relayoutMode: 'flow' as 'flow' | 'pack',
    layoutLayers: [...DEFAULT_LAYOUT_LAYERS] as string[],
    customLayers: [] as CustomLayerConfig[],
    nodeTierOverrides: {} as Record<string, string>,
    nodeOverrides: {} as Record<string, NodeOverrideMeta>,
    draggingNodeId: null as string | null,
    dragTargetLayerId: null as string | null,
    selectedEdgeId: null as string | null,
    editHistoryPast: [] as EditHistorySnapshot[],
    editHistoryFuture: [] as EditHistorySnapshot[],
    lastEditAction: '' as string,
    editPersistenceStatus: 'idle' as 'idle' | 'saved' | 'restored' | 'imported',
    presentationMode: false as boolean,
    editorPanelCollapsed: false as boolean,
    hasSeenEditWalkthrough: false as boolean,
    originalNodeSnapshots: {} as Record<string, OriginalNodeSnapshot>,

    // Feature: Drift Detection
    driftMode: false as boolean,
    driftSummary: null as { in_sync: number; drifted: number; missing: number; extra: number } | null,

    // Feature: Smart Groups
    smartGroups: [] as StackMapGroup[],
    collapsedGroups: new Set<string>() as Set<string>,

    // Feature: Dependency Tracing
    traceResult: null as {
      origin_id: string
      upstream: { node_id: string; depth: number; edge_type: string; edge_label: string; direction: string }[]
      downstream: { node_id: string; depth: number; edge_type: string; edge_label: string; direction: string }[]
      blast_radius: number
      critical_path: string[]
      critical_path_length: number
    } | null,
    traceOriginId: null as string | null,

    // Feature: Suspicious Pattern Detection
    findings: [] as {
      id: string
      pattern_id: string
      title: string
      description: string
      severity: string
      node_ids: string[]
      recommendation: string
      category: string
    }[],
    activeFindingFilter: null as string | null,

    // Feature: Cost Overlay
    costData: null as CostReportData | null,
    baseCostData: null as CostReportData | null,
    costOverrides: {} as Record<string, CostOverrideInput>,
    showCosts: false as boolean,
    costHeatmap: false as boolean,

    // Feature: Live Logs
    showLogs: false as boolean,
    logEvents: [] as Array<{ timestamp: number; message: string; log_group: string; log_stream: string }>,
    logGroups: [] as string[],
    logLoading: false as boolean,
    logError: null as string | null,
    logNodeId: null as string | null, // null = aggregated, string = per-resource
    logScope: 'visible' as 'visible' | 'all' | 'node',
    logFilter: '' as string,
    logMinutes: 60 as number,
    logsAvailable: false as boolean,

    // Feature: Billing
    billingData: null as { total_monthly: number; by_service: Record<string, number>; period_start: string; period_end: string } | null,
    billingAvailable: false as boolean,
    billingLoading: false as boolean,
    billingError: null as string | null,
  }),

  getters: {
    selectedNode(state): StackMapNode | null {
      if (!state.selectedNodeId) return null
      return this.graphNodes.find((n: StackMapNode) => n.id === state.selectedNodeId)
        ?? state.userNodes.find(n => n.id === state.selectedNodeId)
        ?? state.nodes.find(n => n.id === state.selectedNodeId)
        ?? null
    },

    selectedEdge(state): StackMapEdge | null {
      if (!state.selectedEdgeId) return null
      return state.userEdges.find(edge => edge.id === state.selectedEdgeId)
        ?? this.graphEdges.find(edge => edge.id === state.selectedEdgeId)
        ?? null
    },

    hasCostOverrides(state): boolean {
      return Object.keys(state.costOverrides).length > 0
    },

    hasOrganizationData(state): boolean {
      return state.groups.some(group => group.group_type === 'account')
    },

    isOrganizationOverview(state): boolean {
      return state.metadata?.scan_mode === 'organization' && this.hasOrganizationData && !state.activeAccountId
    },

    isLargeLiveScan(state): boolean {
      return state.metadata?.source_type === 'aws_live' && state.nodes.length > state.componentViewThreshold
    },

    shouldUseComponentLanding(): boolean {
      if (!this.isLargeLiveScan) return false
      if (this.isOrganizationOverview) return false
      return true
    },

    helperParentMap(state): Map<string, string> {
      if (state.viewMode === 'raw' || state.viewMode === 'organization') return new Map()
      return buildHelperParentMap(state.nodes, state.edges)
    },

    organizationNodes(state): StackMapNode[] {
      if (!this.hasOrganizationData) return []
      const nodes = buildOrganizationSummaryNodes(state.nodes, state.groups, state.metadata)
      if (!state.activeOrgGroupId) return nodes
      const scopedGroup = this.organizationGroupsRaw.find(group => group.id === state.activeOrgGroupId)
      if (!scopedGroup) return nodes
      const allowedNodeIds = new Set(scopedGroup.children)
      return nodes.filter(node => allowedNodeIds.has(node.id))
    },

    organizationGroupsRaw(state): StackMapGroup[] {
      return buildOrganizationGroups(state.groups, buildOrganizationSummaryNodes(state.nodes, state.groups, state.metadata), state.nodes)
    },

    organizationGroups(state): StackMapGroup[] {
      const groups = this.organizationGroupsRaw
      if (!state.activeOrgGroupId) return groups

      const groupById = new Map(groups.map(group => [group.id, group]))
      const keep = new Set<string>()

      const addAncestors = (groupId: string | null) => {
        let cursor = groupId
        while (cursor) {
          if (keep.has(cursor)) break
          keep.add(cursor)
          cursor = groupById.get(cursor)?.parent || null
        }
      }

      const addDescendants = (groupId: string) => {
        for (const group of groups) {
          if (group.parent === groupId && !keep.has(group.id)) {
            keep.add(group.id)
            addDescendants(group.id)
          }
        }
      }

      addAncestors(state.activeOrgGroupId)
      keep.add(state.activeOrgGroupId)
      addDescendants(state.activeOrgGroupId)
      return groups.filter(group => keep.has(group.id))
    },

    organizationEdges(state): StackMapEdge[] {
      return buildOrganizationEdges(state.nodes, state.edges, state.showCrossAccountEdges)
    },

    architectureSourceNodes(state): StackMapNode[] {
      const parentMap = this.helperParentMap
      let graphNodes = state.nodes.filter(n => !parentMap.has(n.id) && !isHelperNode(n))
      if (state.activeAccountId) {
        graphNodes = graphNodes.filter(node => accountIdForNode(node) === state.activeAccountId)
      }
      return graphNodes
    },

    architectureSourceEdges(state): StackMapEdge[] {
      let baseEdges = state.edges
      if (!state.showCrossAccountEdges) {
        baseEdges = baseEdges.filter(edge => edge.edge_type !== 'cross_account_reference')
      }
      if (!state.showLowConfidenceEdges) {
        baseEdges = baseEdges.filter(edge => edge.metadata?.confidence !== 'low')
      }

      const parentMap = this.helperParentMap
      const dedup = new Set<string>()
      let remapped: StackMapEdge[] = []

      for (const edge of baseEdges) {
        const source = parentMap.get(edge.source) || edge.source
        const target = parentMap.get(edge.target) || edge.target
        if (source === target) continue

        const key = `${source}|${target}|${edge.edge_type}`
        if (dedup.has(key)) continue
        dedup.add(key)

        remapped.push({
          ...edge,
          id: `${source}->${target}:${edge.edge_type}`,
          source,
          target,
        })
      }

      const nodeById = new Map(state.nodes.map(n => [n.id, n]))
      remapped = remapped.filter(edge => {
        if (ARCH_DROPPED_EDGE_TYPES.has(edge.edge_type)) return false
        if (edge.edge_type === 'cross_account_reference') return true
        if (edge.edge_type !== 'references') return true
        return shouldKeepReferenceEdge(nodeById.get(edge.source), nodeById.get(edge.target))
      })
      if (state.activeAccountId) {
        const visibleIds = new Set(this.architectureSourceNodes.map(node => node.id))
        remapped = remapped.filter(edge => visibleIds.has(edge.source) && visibleIds.has(edge.target))
      }

      return remapped
    },

    rawSourceNodes(state): StackMapNode[] {
      return state.activeAccountId
        ? state.nodes.filter(node => accountIdForNode(node) === state.activeAccountId)
        : state.nodes
    },

    rawSourceEdges(state): StackMapEdge[] {
      let baseEdges = state.edges
      if (!state.showCrossAccountEdges) {
        baseEdges = baseEdges.filter(edge => edge.edge_type !== 'cross_account_reference')
      }
      if (!state.showLowConfidenceEdges) {
        baseEdges = baseEdges.filter(edge => edge.metadata?.confidence !== 'low')
      }
      if (!state.activeAccountId) return baseEdges
      const visibleIds = new Set(this.rawSourceNodes.map(node => node.id))
      return baseEdges.filter(edge => visibleIds.has(edge.source) && visibleIds.has(edge.target))
    },

    componentSummaries(state): ComponentSummary[] {
      const summaries = buildComponentSummaries(this.architectureSourceNodes, this.architectureSourceEdges)
      if (state.showWeaklyLinkedComponents) return summaries
      const explicit = summaries.filter(summary => summary.kind !== 'weakly_linked' && summary.kind !== 'unlinked_bucket')
      const hiddenWeakly = summaries.filter(summary => summary.kind === 'weakly_linked')
      const bucket = summaries.find(summary => summary.kind === 'unlinked_bucket')
      if (!hiddenWeakly.length) return summaries

      const nodeIds = new Set<string>(bucket?.nodeIds || [])
      const edgeIds = new Set<string>(bucket?.edgeIds || [])
      for (const summary of hiddenWeakly) {
        for (const nodeId of summary.nodeIds) nodeIds.add(nodeId)
        for (const edgeId of summary.edgeIds) edgeIds.add(edgeId)
      }

      const mergedBucket: ComponentSummary = {
        id: UNLINKED_COMPONENT_ID,
        name: 'unlinked-resources',
        kind: 'unlinked_bucket',
        nodeIds: [...nodeIds],
        edgeIds: [...edgeIds],
        resourceCount: [...nodeIds].length,
        edgeCount: [...edgeIds].length,
        dominantCategories: bucket?.dominantCategories || ['other'],
        entrypoints: [],
        accountIds: bucket?.accountIds || [],
        regions: bucket?.regions || [],
        usefulnessScore: 0,
        helperRatio: bucket?.helperRatio || 0,
        mostlyNetwork: bucket?.mostlyNetwork || false,
        summary: bucket?.summary || 'mixed',
      }

      return [...explicit, mergedBucket].sort((a, b) => {
        if (a.kind === 'unlinked_bucket' && b.kind !== 'unlinked_bucket') return 1
        if (b.kind === 'unlinked_bucket' && a.kind !== 'unlinked_bucket') return -1
        if (b.usefulnessScore !== a.usefulnessScore) return b.usefulnessScore - a.usefulnessScore
        if (b.resourceCount !== a.resourceCount) return b.resourceCount - a.resourceCount
        return a.name.localeCompare(b.name)
      })
    },

    activeComponentSummary(state): ComponentSummary | null {
      if (!state.activeComponentId) return null
      return this.componentSummaries.find(component => component.id === state.activeComponentId) || null
    },

    activeComponentNodeIds(state): Set<string> | null {
      if (!state.activeComponentId) return null
      const component = this.activeComponentSummary
      if (!component) return null
      return new Set(component.nodeIds)
    },

    graphNodes(state): StackMapNode[] {
      if (state.viewMode === 'organization') return this.organizationNodes
      if (state.viewMode === 'components') return []
      if (state.viewMode === 'raw') {
        return this.rawSourceNodes
      }

      let nodes = this.architectureSourceNodes
      if (state.activeComponentId) {
        const activeIds = this.activeComponentNodeIds
        if (activeIds) nodes = nodes.filter(node => activeIds.has(node.id))
      } else if (this.shouldUseComponentLanding && !state.showUnlinkedResources) {
        const unlinked = this.componentSummaries.find(component => component.id === UNLINKED_COMPONENT_ID)
        if (unlinked) {
          const unlinkedIds = new Set(unlinked.nodeIds)
          nodes = nodes.filter(node => !unlinkedIds.has(node.id))
        }
      }
      return nodes
    },

    graphEdges(state): StackMapEdge[] {
      if (state.viewMode === 'organization') return this.organizationEdges
      if (state.viewMode === 'components') return []
      if (state.viewMode === 'raw') return this.rawSourceEdges

      let edges = this.architectureSourceEdges
      if (state.activeComponentId) {
        const activeIds = this.activeComponentNodeIds
        if (activeIds) edges = edges.filter(edge => activeIds.has(edge.source) && activeIds.has(edge.target))
      } else if (this.shouldUseComponentLanding && !state.showUnlinkedResources) {
        const unlinked = this.componentSummaries.find(component => component.id === UNLINKED_COMPONENT_ID)
        if (unlinked) {
          const unlinkedIds = new Set(unlinked.nodeIds)
          edges = edges.filter(edge => !unlinkedIds.has(edge.source) && !unlinkedIds.has(edge.target))
        }
      }
      return edges
    },

    graphGroups(state): StackMapGroup[] {
      if (state.viewMode === 'organization') return this.organizationGroups
      const nodesById = new Map(state.nodes.map(node => [node.id, node]))
      const visibleNodeIds = new Set(this.graphNodes.map(node => node.id))
      let groups = !state.activeAccountId
        ? state.groups
        : state.groups.filter(group => groupTouchesAccount(group, nodesById, state.activeAccountId as string))

      groups = groups
        .map(group => ({
          ...group,
          children: group.children.filter(child => visibleNodeIds.has(child)),
        }))
        .filter(group => group.children.length > 0)

      if (state.viewMode === 'architecture' && state.collapseNetworkScaffolding) {
        groups = groups.filter(group => {
          if (!['vpc', 'subnet'].includes(group.group_type)) return true
          return group.children.some(childId => {
            const node = nodesById.get(childId)
            if (!node) return false
            if (isHelperNode(node)) return false
            return node.category !== 'network' && !NETWORK_HEAVY_RESOURCE_TYPES.has(node.resource_type)
          })
        })
      }

      return groups
    },

    organizationTree(): OrgTreeItem[] {
      return flattenOrganizationTree(this.organizationGroups)
    },

    connectedNodeIds(): (nodeId: string) => Set<string> {
      const adj = this.graphAdjacency
      return (nodeId: string) => adj.get(nodeId) ?? new Set()
    },

    graphAdjacency(): Map<string, Set<string>> {
      const adj = new Map<string, Set<string>>()
      for (const edge of [...this.graphEdges, ...this.userEdges]) {
        if (!adj.has(edge.source)) adj.set(edge.source, new Set())
        if (!adj.has(edge.target)) adj.set(edge.target, new Set())
        adj.get(edge.source)!.add(edge.target)
        adj.get(edge.target)!.add(edge.source)
      }
      return adj
    },

    nodesWithinHops(): (nodeId: string, hops: number) => Set<string> {
      const adj = this.graphAdjacency
      return (nodeId: string, hops: number) => {
        const visited = new Set<string>([nodeId])
        let frontier = new Set<string>([nodeId])

        for (let i = 0; i < hops; i++) {
          const nextFrontier = new Set<string>()
          for (const nid of frontier) {
            const neighbors = adj.get(nid)
            if (!neighbors) continue
            for (const neighbor of neighbors) {
              if (!visited.has(neighbor)) {
                visited.add(neighbor)
                nextFrontier.add(neighbor)
              }
            }
          }
          frontier = nextFrontier
        }

        return visited
      }
    },

    diffSummary(state): { added: number; removed: number; modified: number; unchanged: number } | null {
      if (!state.diffMode) return null
      return (state.metadata?.diff_summary as { added: number; removed: number; modified: number; unchanged: number }) ?? null
    },

    nodeDiffStatus(): Record<string, string> {
      return Object.fromEntries(
        this.nodes
          .map(n => [n.id, n.position_hint?.diff_status])
          .filter((entry): entry is [string, string] => typeof entry[1] === 'string')
      )
    },

    edgeDiffStatus(state): Record<string, string> {
      if (!state.diffMode) return {}
      return (state.metadata?.edge_diff_status as Record<string, string>) ?? {}
    },

    activeBreadcrumb(state): string[] {
      if (state.viewMode === 'organization' && state.activeOrgGroupId) {
        const groupById = new Map(this.organizationGroupsRaw.map(group => [group.id, group]))
        const path: string[] = []
        let cursor = state.activeOrgGroupId
        while (cursor) {
          const group = groupById.get(cursor)
          if (!group) break
          path.unshift(group.name)
          cursor = group.parent
        }
        return path
      }
      if (!state.activeAccountId) return []
      const accountNode = this.organizationNodes.find(node => node.metadata?.account_id === state.activeAccountId)
      const path = String(accountNode?.metadata?.org_path || '').trim()
      const breadcrumb = !path ? [accountNode?.name || state.activeAccountId] : path.split('/').filter(Boolean).concat(accountNode?.name || [])
      if (state.activeComponentId) {
        const component = this.activeComponentSummary
        if (component) breadcrumb.push(component.name)
      }
      return breadcrumb
    },

    visibleNodes(state): StackMapNode[] {
      let hopSet: Set<string> | null = null
      if (state.hopLimit > 0 && state.selectedNodeId) {
        hopSet = this.nodesWithinHops(state.selectedNodeId, state.hopLimit)
      }

      // Include user-created nodes
      const allNodes = [...this.graphNodes, ...state.userNodes]

      return allNodes.filter((node: StackMapNode) => {
        if (state.hiddenNodeIds.includes(node.id)) return false
        if (state.categoryFilters[node.category] === false) return false
        if (state.minWeight > 1 && (node.position_hint?.weight || 2) < state.minWeight) return false
        if (hopSet && !hopSet.has(node.id)) return false
        if (state.diffMode) {
          const diffStatus = node.position_hint?.diff_status
          if (state.showOnlyChanges && diffStatus === 'unchanged') return false
          if (diffStatus === 'added' && state.diffSlider <= 0) return false
          if (diffStatus === 'removed' && state.diffSlider >= 1) return false
        }
        return true
      })
    },

    visibleEdges(): StackMapEdge[] {
      const visibleIds = new Set(this.visibleNodes.map((node: StackMapNode) => node.id))
      const baseEdges = this.graphEdges.filter((edge: StackMapEdge) => visibleIds.has(edge.source) && visibleIds.has(edge.target))
      const userEdgesVisible = this.userEdges.filter((edge: StackMapEdge) => visibleIds.has(edge.source) && visibleIds.has(edge.target))
      return [...baseEdges, ...userEdgesVisible].filter(edge => this.edgeTypeFilters[edge.edge_type] !== false)
    },

    availableEdgeTypes(state): Array<{ id: string; count: number; kind: 'manual' | 'cross-account' | 'inferred' }> {
      const visibleIds = new Set(this.visibleNodes.map((node: StackMapNode) => node.id))
      const allVisible = [...this.graphEdges, ...state.userEdges].filter(
        edge => visibleIds.has(edge.source) && visibleIds.has(edge.target)
      )
      const counts = new Map<string, number>()
      for (const edge of allVisible) {
        counts.set(edge.edge_type, (counts.get(edge.edge_type) || 0) + 1)
      }
      return [...counts.entries()]
        .map(([id, count]) => ({
          id,
          count,
          kind: id.startsWith('manual_') || id === 'user_link'
            ? 'manual'
            : id === 'cross_account_reference'
              ? 'cross-account'
              : 'inferred' as const,
        }))
        .sort((a, b) => b.count - a.count || a.id.localeCompare(b.id))
    },

    nodeEdges(): (nodeId: string) => StackMapEdge[] {
      return (nodeId: string) =>
        [...this.graphEdges, ...this.userEdges].filter(
          (edge: StackMapEdge) => edge.source === nodeId || edge.target === nodeId
        )
    },

    canUndo(state): boolean {
      return state.editHistoryPast.length > 0
    },

    canRedo(state): boolean {
      return state.editHistoryFuture.length > 0
    },

    editChangeSummary(state): { hidden: number; customNodes: number; customLinks: number; moved: number; customLayers: number } {
      return {
        hidden: state.hiddenNodeIds.length,
        customNodes: state.userNodes.length,
        customLinks: state.userEdges.length,
        moved: Object.keys(state.nodeTierOverrides).length,
        customLayers: state.customLayers.length,
      }
    },
  },

  actions: {
    _createEditSnapshot(): EditHistorySnapshot {
      return JSON.parse(JSON.stringify({
        hiddenNodeIds: this.hiddenNodeIds,
        hiddenNodeIdsBackup: this.hiddenNodeIdsBackup,
        userEdges: this.userEdges,
        userNodes: this.userNodes,
        customLayers: this.customLayers,
        nodeTierOverrides: this.nodeTierOverrides,
        nodeOverrides: this.nodeOverrides,
        layoutLayers: this.layoutLayers,
      }))
    },

    _applyEditSnapshot(snapshot: EditHistorySnapshot) {
      this.hiddenNodeIds = [...snapshot.hiddenNodeIds]
      this.hiddenNodeIdsBackup = snapshot.hiddenNodeIdsBackup ? [...snapshot.hiddenNodeIdsBackup] : null
      this.userEdges = JSON.parse(JSON.stringify(snapshot.userEdges))
      this.userNodes = JSON.parse(JSON.stringify(snapshot.userNodes))
      this.customLayers = JSON.parse(JSON.stringify(snapshot.customLayers))
      this.nodeTierOverrides = { ...snapshot.nodeTierOverrides }
      this.nodeOverrides = { ...snapshot.nodeOverrides }
      this.layoutLayers = [...snapshot.layoutLayers]

      for (const node of this.nodes) {
        const original = this.originalNodeSnapshots[node.id]
        if (original) {
          node.name = original.name
          node.provider = original.provider
          node.resource_type = original.resource_type
          node.category = original.category
          if (!node.position_hint) node.position_hint = { tier: original.tier, weight: original.weight }
          node.position_hint.weight = original.weight
        }
        const override = this.nodeTierOverrides[node.id]
        const meta = this.nodeOverrides[node.id]
        if (!node.position_hint) node.position_hint = { tier: 'compute', weight: 2 }
        node.position_hint.tier = override || normalizeNodeTier(node)
        if (meta?.name) node.name = meta.name
        if (meta?.provider) node.provider = meta.provider
        if (meta?.resource_type) node.resource_type = meta.resource_type
        if (meta?.category) node.category = meta.category
        if (typeof meta?.weight === 'number') node.position_hint.weight = meta.weight
      }

      for (const node of this.userNodes) {
        if (!node.position_hint) node.position_hint = { tier: 'compute', weight: 4 }
        node.position_hint.tier = normalizeNodeTier(node)
      }

      this.requestRelayout()
    },

    _setLastEditAction(message: string) {
      this.lastEditAction = message
    },

    _recordHistory() {
      this.editHistoryPast.push(this._createEditSnapshot())
      if (this.editHistoryPast.length > 80) {
        this.editHistoryPast.shift()
      }
      this.editHistoryFuture = []
    },

    undoEdits() {
      const previous = this.editHistoryPast.pop()
      if (!previous) return
      this.editHistoryFuture.push(this._createEditSnapshot())
      this._applyEditSnapshot(previous)
      this._persistEdits()
    },

    redoEdits() {
      const next = this.editHistoryFuture.pop()
      if (!next) return
      this.editHistoryPast.push(this._createEditSnapshot())
      this._applyEditSnapshot(next)
      this._persistEdits()
    },

    async loadFromJSON(path: string) {
      const data =
        typeof window !== 'undefined' && (window as any).__STACKMAP_DATA__
          ? (window as any).__STACKMAP_DATA__
          : await fetch(path).then(r => r.json())

      this.metadata = data.metadata || {}
      this.nodes = data.nodes || []
      this.edges = data.edges || []
      this.groups = data.groups || []
      this.layoutLayers = [...DEFAULT_LAYOUT_LAYERS]

      for (const node of this.nodes) {
        if (!node.position_hint) {
          node.position_hint = { tier: 'compute', weight: 2 }
        }
        node.position_hint.tier = normalizeNodeTier(node)
        if (!this.layoutLayers.includes(node.position_hint.tier)) {
          this.layoutLayers.push(node.position_hint.tier)
        }
      }
      this.originalNodeSnapshots = Object.fromEntries(
        this.nodes.map(node => [
          node.id,
          {
            name: node.name,
            provider: node.provider,
            resource_type: node.resource_type,
            category: node.category,
            weight: node.position_hint?.weight || 2,
            tier: node.position_hint?.tier || 'compute',
          },
        ])
      )
      if (typeof window !== 'undefined') {
        this.hasSeenEditWalkthrough = localStorage.getItem('stackmap-edit-walkthrough-seen') === 'true'
        this.editorPanelCollapsed = localStorage.getItem('stackmap-editor-panel-collapsed') === 'true'
      }

      const cats = new Set(this.graphNodes.map(node => node.category))
      this.categoryFilters = Object.fromEntries([...cats].map(category => [category, true]))

      if (this.metadata.diff_mode) {
        this.diffMode = true
        this.diffSlider = 0.5
      }

      this.activeComponentId = null
      if (this.metadata?.source_type === 'aws_live' && this.metadata?.scan_mode === 'organization' && this.hasOrganizationData) {
        this.viewMode = 'organization'
      } else if (this.shouldUseComponentLanding) {
        this.viewMode = 'components'
      } else {
        this.viewMode = 'architecture'
      }

      this.loadPersistedEdits()
      const edgeTypes = new Set([...this.graphEdges, ...this.userEdges].map(edge => edge.edge_type))
      this.edgeTypeFilters = Object.fromEntries([...edgeTypes].map(edgeType => [edgeType, true]))
      this.editHistoryPast = []
      this.editHistoryFuture = []
      this.loaded = true

      // Auto-load findings, drift data, and check live features (non-blocking)
      this.loadFindings()
      this.checkLogsAvailable()
      if (this.metadata?.drift_summary) {
        this.driftSummary = this.metadata.drift_summary
      }
    },

    setDiffMode(enabled: boolean) {
      this.diffMode = enabled
      if (!enabled) {
        this.diffSlider = 0.5
        this.showOnlyChanges = false
      }
    },

    setDiffSlider(value: number) {
      this.diffSlider = Math.max(0, Math.min(1, value))
    },

    setShowOnlyChanges(show: boolean) {
      this.showOnlyChanges = show
    },

    selectNode(nodeId: string | null) {
      this.selectedNodeId = nodeId
      if (nodeId) this.selectedEdgeId = null
      if (nodeId) this.editorPanelCollapsed = false
      if (!nodeId) this.hopLimit = 0
    },

    selectEdge(edgeId: string | null) {
      this.selectedEdgeId = edgeId
      if (edgeId) this.selectedNodeId = null
      if (edgeId) this.editorPanelCollapsed = false
    },

    hoverNode(nodeId: string | null) {
      this.hoveredNodeId = nodeId
    },

    setPositions(positions: Record<string, NodePosition>) {
      this.positions = positions
    },

    toggleCategory(category: string) {
      this.categoryFilters[category] = !this.categoryFilters[category]
    },

    toggleEdgeType(edgeType: string) {
      this.edgeTypeFilters[edgeType] = this.edgeTypeFilters[edgeType] === false
    },

    setEdgeTypePreset(preset: 'all' | 'manual' | 'inferred' | 'presentation') {
      const edgeTypes = new Set([...this.graphEdges, ...this.userEdges].map(edge => edge.edge_type))
      const shouldEnable = (edgeType: string) => {
        if (preset === 'all') return true
        if (preset === 'manual') return edgeType.startsWith('manual_') || edgeType === 'user_link'
        if (preset === 'inferred') return !edgeType.startsWith('manual_') && edgeType !== 'user_link'
        return edgeType.startsWith('manual_')
          || edgeType === 'user_link'
          || edgeType === 'triggers'
          || edgeType === 'writes_to'
          || edgeType === 'reads_from'
          || edgeType === 'routes_to'
      }

      for (const edgeType of edgeTypes) {
        this.edgeTypeFilters[edgeType] = shouldEnable(edgeType)
      }
    },

    setMinWeight(weight: number) {
      this.minWeight = weight
    },

    setHopLimit(hops: number) {
      this.hopLimit = hops
    },

    setSearch(query: string) {
      this.searchQuery = query
    },

    setViewMode(mode: 'architecture' | 'raw' | 'organization' | 'components') {
      this.viewMode = mode
      if (mode === 'architecture' && this.selectedNodeId) {
        const parent = this.helperParentMap.get(this.selectedNodeId)
        if (parent) this.selectedNodeId = parent
      }
      if (mode === 'organization' || mode === 'components') {
        this.selectedNodeId = null
        this.selectedEdgeId = null
      }
      if (mode !== 'architecture') {
        this.activeComponentId = null
      }
    },

    setActiveAccount(accountId: string | null) {
      this.activeAccountId = accountId
      this.activeOrgGroupId = null
      this.activeComponentId = null
      this.selectedNodeId = null
      this.hopLimit = 0
    },

    enterAccountArchitecture(accountId: string) {
      this.activeAccountId = accountId
      this.activeOrgGroupId = null
      this.activeComponentId = null
      this.viewMode = this.shouldUseComponentLanding ? 'components' : 'architecture'
      this.selectedNodeId = null
      this.hopLimit = 0
    },

    setActiveOrgGroup(groupId: string | null) {
      this.activeOrgGroupId = groupId
      this.selectedNodeId = null
    },

    setShowCrossAccountEdges(show: boolean) {
      this.showCrossAccountEdges = show
    },

    setShowLowConfidenceEdges(show: boolean) {
      this.showLowConfidenceEdges = show
    },

    openComponent(componentId: string) {
      this.activeComponentId = componentId
      this.viewMode = 'architecture'
      this.selectedNodeId = null
      this.hopLimit = 0
    },

    returnToComponents() {
      this.activeComponentId = null
      this.selectedNodeId = null
      this.hopLimit = 0
      this.viewMode = 'components'
    },

    focusSelectedNodeComponent() {
      if (!this.selectedNodeId) return
      const component = this.componentSummaries.find(summary => summary.nodeIds.includes(this.selectedNodeId as string))
      if (!component) return
      this.openComponent(component.id)
    },

    setShowUnlinkedResources(show: boolean) {
      this.showUnlinkedResources = show
    },

    setShowWeaklyLinkedComponents(show: boolean) {
      this.showWeaklyLinkedComponents = show
    },

    setCollapseNetworkScaffolding(show: boolean) {
      this.collapseNetworkScaffolding = show
    },

    resetFilters() {
      for (const category of Object.keys(this.categoryFilters)) {
        this.categoryFilters[category] = true
      }
      this.minWeight = 1
      this.hopLimit = 0
      this.searchQuery = ''
      this.activeAccountId = null
      this.activeOrgGroupId = null
      this.activeComponentId = null
      this.showUnlinkedResources = true
      this.showWeaklyLinkedComponents = false
      this.collapseNetworkScaffolding = true
      this.showCrossAccountEdges = true
      for (const edgeType of Object.keys(this.edgeTypeFilters)) {
        this.edgeTypeFilters[edgeType] = true
      }
    },

    // ── Edit mode actions ─────────────────────────────────────────
    toggleEditMode() {
      this.editMode = !this.editMode
      if (!this.editMode) {
        this.connectingFromNodeId = null
        this.editSubmode = 'inspect'
      } else {
        this.editSubmode = 'inspect'
      }
    },

    setEditSubmode(mode: EditSubmode) {
      this.editSubmode = mode
      if (mode !== 'connect') {
        this.connectingFromNodeId = null
      }
      this._setLastEditAction(`mode: ${mode}`)
    },

    setPresentationMode(enabled: boolean) {
      this.presentationMode = enabled
    },

    setEditorPanelCollapsed(collapsed: boolean) {
      this.editorPanelCollapsed = collapsed
      if (typeof window !== 'undefined') {
        localStorage.setItem('stackmap-editor-panel-collapsed', String(collapsed))
      }
    },

    dismissEditWalkthrough() {
      this.hasSeenEditWalkthrough = true
      if (typeof window !== 'undefined') {
        localStorage.setItem('stackmap-edit-walkthrough-seen', 'true')
      }
    },

    hideNode(nodeId: string) {
      this._recordHistory()
      if (!this.hiddenNodeIds.includes(nodeId)) {
        this.hiddenNodeIds.push(nodeId)
      }
      if (this.selectedNodeId === nodeId) this.selectedNodeId = null
      this._setLastEditAction('hid resource')
      this.requestRelayout()
      this._persistEdits()
    },

    showNode(nodeId: string) {
      this._recordHistory()
      this.hiddenNodeIds = this.hiddenNodeIds.filter(id => id !== nodeId)
      if (this.hiddenNodeIdsBackup) {
        this.hiddenNodeIdsBackup = this.hiddenNodeIdsBackup.filter(id => id !== nodeId)
        if (this.hiddenNodeIdsBackup.length === 0) this.hiddenNodeIdsBackup = null
      }
      this._setLastEditAction('restored resource')
      this.requestRelayout()
      this._persistEdits()
    },

    showAllNodes() {
      if (this.hiddenNodeIds.length === 0) return
      this._recordHistory()
      this.hiddenNodeIdsBackup = [...this.hiddenNodeIds]
      this.hiddenNodeIds = []
      this._setLastEditAction('showed all hidden resources')
      this.requestRelayout()
      this._persistEdits()
    },

    rehideShownNodes() {
      if (!this.hiddenNodeIdsBackup?.length) return
      this._recordHistory()
      this.hiddenNodeIds = [...new Set([...this.hiddenNodeIdsBackup, ...this.hiddenNodeIds])]
      this.hiddenNodeIdsBackup = null
      this._setLastEditAction('rehid shown resources')
      this.requestRelayout()
      this._persistEdits()
    },

    isolateNodeSet(nodeIds: string[], label: string) {
      const keep = new Set(nodeIds)
      if (keep.size === 0) return
      const visibleIds = this.visibleNodes.map(node => node.id)
      const nextHidden = new Set(this.hiddenNodeIds)
      for (const nodeId of visibleIds) {
        if (!keep.has(nodeId)) nextHidden.add(nodeId)
      }
      if (nextHidden.size === this.hiddenNodeIds.length) return
      this._recordHistory()
      this.hiddenNodeIds = [...nextHidden]
      this._setLastEditAction(label)
      this.requestRelayout()
      this._persistEdits()
    },

    isolateSelectedNeighborhood(hops: number = 1) {
      if (!this.selectedNodeId) return
      const nodeSet = this.nodesWithinHops(this.selectedNodeId, hops)
      nodeSet.add(this.selectedNodeId)
      this.isolateNodeSet([...nodeSet], `isolated ${hops}-hop neighborhood`)
    },

    isolateSelectedLayer() {
      if (!this.selectedNode) return
      const tier = this.selectedNode.position_hint?.tier || 'compute'
      const tierNodeIds = this.visibleNodes
        .filter(node => (node.position_hint?.tier || 'compute') === tier)
        .map(node => node.id)
      this.isolateNodeSet(tierNodeIds, `isolated layer: ${tier}`)
    },

    isolateSelectedComponent() {
      if (!this.selectedNodeId) return
      const component = this.componentSummaries.find(summary => summary.nodeIds.includes(this.selectedNodeId as string))
      if (!component) return
      this.isolateNodeSet(component.nodeIds, `isolated component: ${component.name}`)
    },

    startConnecting(nodeId: string) {
      this.editSubmode = 'connect'
      this.connectingFromNodeId = nodeId
      this._setLastEditAction('connect mode')
    },

    cancelConnecting() {
      this.connectingFromNodeId = null
      if (this.editSubmode === 'connect') this.editSubmode = 'inspect'
    },

    completeConnection(targetNodeId: string) {
      if (!this.connectingFromNodeId || this.connectingFromNodeId === targetNodeId) {
        this.connectingFromNodeId = null
        return
      }
      const edgeId = `user:${this.connectingFromNodeId}->${targetNodeId}`
      // Don't add duplicate edges
      if (this.userEdges.some(e => e.id === edgeId)) {
        this.connectingFromNodeId = null
        return
      }
      this._recordHistory()
      this.userEdges.push({
        id: edgeId,
        source: this.connectingFromNodeId,
        target: targetNodeId,
        edge_type: 'manual_generic',
        label: 'Manual link',
        color: '#4ADE80',
      })
      this.edgeTypeFilters.manual_generic = true
      this.connectingFromNodeId = null
      this.selectedEdgeId = edgeId
      this._setLastEditAction('created manual link')
      this.requestRelayout()
      this._persistEdits()
    },

    removeUserEdge(edgeId: string) {
      this._recordHistory()
      this.userEdges = this.userEdges.filter(e => e.id !== edgeId)
      if (this.selectedEdgeId === edgeId) this.selectedEdgeId = null
      this._setLastEditAction('deleted manual link')
      this.requestRelayout()
      this._persistEdits()
    },

    setUserEdgeColor(edgeId: string, color: string) {
      const edge = this.userEdges.find(candidate => candidate.id === edgeId)
      if (!edge || edge.color === color) return
      this._recordHistory()
      edge.color = color
      this._setLastEditAction('changed link color')
      this._persistEdits()
    },

    updateUserEdge(edgeId: string, updates: Partial<Pick<StackMapEdge, 'label' | 'edge_type' | 'color'>>) {
      const edge = this.userEdges.find(candidate => candidate.id === edgeId)
      if (!edge) return
      const next = {
        label: updates.label ?? edge.label,
        edge_type: updates.edge_type ?? edge.edge_type,
        color: updates.color ?? edge.color,
      }
      if (next.label === edge.label && next.edge_type === edge.edge_type && next.color === edge.color) return
      this._recordHistory()
      edge.label = next.label
      if (edge.edge_type !== next.edge_type) {
        this.edgeTypeFilters[next.edge_type] = true
      }
      edge.edge_type = next.edge_type
      edge.color = next.color
      this._setLastEditAction('updated manual link')
      this._persistEdits()
    },

    requestRelayout(mode: 'flow' | 'pack' = 'flow') {
      this.relayoutMode = mode
      this.layoutVersion += 1
    },

    startDraggingNode(nodeId: string) {
      if (this.editSubmode !== 'structure') return
      this.draggingNodeId = nodeId
      const node =
        this.userNodes.find(candidate => candidate.id === nodeId)
        || this.nodes.find(candidate => candidate.id === nodeId)
        || this.graphNodes.find(candidate => candidate.id === nodeId)
      this.dragTargetLayerId = node?.position_hint?.tier || null
    },

    setDragTargetLayer(layerId: string | null) {
      this.dragTargetLayerId = layerId
    },

    finishDraggingNode(layerId: string | null) {
      const nodeId = this.draggingNodeId
      this.draggingNodeId = null
      this.dragTargetLayerId = null
      if (!nodeId || !layerId) return
      this.moveNodeToLayer(nodeId, layerId)
    },

    cancelDraggingNode() {
      this.draggingNodeId = null
      this.dragTargetLayerId = null
    },

    addCustomLayer(label: string): string | null {
      const trimmed = label.trim()
      if (!trimmed) return null
      const id = trimmed
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
      if (!id) return null
      if (this.layoutLayers.includes(id) || this.customLayers.some(layer => layer.id === id)) {
        return id
      }
      this._recordHistory()
      if (!this.layoutLayers.includes(id)) {
        this.layoutLayers.push(id)
      }
      if (!this.customLayers.some(layer => layer.id === id) && !DEFAULT_LAYOUT_LAYERS.includes(id)) {
        this.customLayers.push({ id, label: trimmed })
      }
      this._setLastEditAction('added layer')
      this.requestRelayout()
      this._persistEdits()
      return id
    },

    removeCustomLayer(layerId: string) {
      if (DEFAULT_LAYOUT_LAYERS.includes(layerId)) return false
      if (!this.customLayers.some(layer => layer.id === layerId)) return false

      const hasAssignedNodes = [...this.nodes, ...this.userNodes].some(
        node => (node.position_hint?.tier || 'compute') === layerId
      )
      if (hasAssignedNodes) return false

      this._recordHistory()
      this.customLayers = this.customLayers.filter(layer => layer.id !== layerId)
      this.layoutLayers = this.layoutLayers.filter(id => id !== layerId)
      if (this.dragTargetLayerId === layerId) {
        this.dragTargetLayerId = null
      }
      this._setLastEditAction('deleted custom layer')
      this.requestRelayout()
      this._persistEdits()
      return true
    },

    updateCustomLayer(layerId: string, updates: Partial<CustomLayerConfig>) {
      const layer = this.customLayers.find(candidate => candidate.id === layerId)
      if (!layer) return
      const nextLabel = updates.label?.trim() || layer.label
      const nextIcon = updates.icon ?? layer.icon
      const nextAccent = updates.accent ?? layer.accent
      if (nextLabel === layer.label && nextIcon === layer.icon && nextAccent === layer.accent) return
      this._recordHistory()
      layer.label = nextLabel
      layer.icon = nextIcon
      layer.accent = nextAccent
      this._setLastEditAction('updated layer')
      this.requestRelayout()
      this._persistEdits()
    },

    reorderLayers(draggedLayerId: string, targetLayerId: string) {
      if (draggedLayerId === targetLayerId) return
      const fromIndex = this.layoutLayers.indexOf(draggedLayerId)
      const toIndex = this.layoutLayers.indexOf(targetLayerId)
      if (fromIndex === -1 || toIndex === -1) return

      this._recordHistory()
      const updated = [...this.layoutLayers]
      const [moved] = updated.splice(fromIndex, 1)
      updated.splice(toIndex, 0, moved)
      this.layoutLayers = updated
      this._setLastEditAction('reordered layers')
      this.requestRelayout()
      this._persistEdits()
    },

    moveNodeToLayer(nodeId: string, layerId: string) {
      const currentNode =
        this.userNodes.find(candidate => candidate.id === nodeId)
        || this.nodes.find(candidate => candidate.id === nodeId)
      if (currentNode?.position_hint?.tier === layerId) return
      this._recordHistory()
      if (!this.layoutLayers.includes(layerId)) {
        this.layoutLayers.push(layerId)
      }
      const userNode = this.userNodes.find(node => node.id === nodeId)
      if (userNode) {
        if (!userNode.position_hint) userNode.position_hint = { tier: layerId, weight: 4 }
        userNode.position_hint.tier = layerId
        const peerOrders = this.userNodes
          .filter(node => node.id !== nodeId && (node.position_hint?.tier || 'compute') === layerId)
          .map(node => node.position_hint?.manual_order)
          .filter((value): value is number => typeof value === 'number')
        userNode.position_hint.manual_order = peerOrders.length ? Math.max(...peerOrders) + 100 : 100
      } else {
        const node = this.nodes.find(candidate => candidate.id === nodeId)
        if (!node) return
        if (!node.position_hint) node.position_hint = { tier: layerId, weight: 2 }
        node.position_hint.tier = layerId
        this.nodeTierOverrides[nodeId] = layerId
        const peerOrders = this.nodes
          .filter(candidate => candidate.id !== nodeId && (candidate.position_hint?.tier || 'compute') === layerId)
          .map(candidate => candidate.position_hint?.manual_order)
          .filter((value): value is number => typeof value === 'number')
        node.position_hint.manual_order = peerOrders.length ? Math.max(...peerOrders) + 100 : 100
        this.nodeOverrides[nodeId] = {
          ...this.nodeOverrides[nodeId],
          order: node.position_hint.manual_order,
        }
      }
      this._setLastEditAction('moved resource to layer')
      this.requestRelayout()
      this._persistEdits()
    },

    reorderNodesWithinLayer(nodeIdsInOrder: string[], layerId: string) {
      if (!nodeIdsInOrder.length) return
      this._recordHistory()
      nodeIdsInOrder.forEach((nodeId, index) => {
        const order = (index + 1) * 100
        const userNode = this.userNodes.find(node => node.id === nodeId)
        if (userNode) {
          if (!userNode.position_hint) userNode.position_hint = { tier: layerId, weight: 4 }
          userNode.position_hint.tier = layerId
          userNode.position_hint.manual_order = order
          return
        }
        const node = this.nodes.find(candidate => candidate.id === nodeId)
        if (!node) return
        if (!node.position_hint) node.position_hint = { tier: layerId, weight: 2 }
        node.position_hint.tier = layerId
        node.position_hint.manual_order = order
        this.nodeTierOverrides[nodeId] = layerId
        this.nodeOverrides[nodeId] = {
          ...this.nodeOverrides[nodeId],
          order,
        }
      })
      this._setLastEditAction('reordered resources in layer')
      this.requestRelayout()
      this._persistEdits()
    },

    addUserNode(
      name: string,
      options: {
        resourceType: string
        category: string
        tier: string
        provider?: string
        weight?: number
      }
    ) {
      this._recordHistory()
      const id = `user:${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      this.userNodes.push({
        id,
        name,
        resource_type: options.resourceType,
        provider: options.provider || 'user',
        category: options.category,
        properties: {},
        tags: { _user_created: 'true' },
        position_hint: {
          tier: options.tier,
          weight: options.weight ?? 4,
        },
      })
      if (!this.layoutLayers.includes(options.tier)) {
        this.layoutLayers.push(options.tier)
      }
      this.selectedNodeId = id
      this._setLastEditAction('added custom node')
      this.requestRelayout()
      this._persistEdits()
    },

    removeUserNode(nodeId: string) {
      this._recordHistory()
      this.userNodes = this.userNodes.filter(n => n.id !== nodeId)
      // Also remove any edges (user or auto) that reference this node
      this.userEdges = this.userEdges.filter(e => e.source !== nodeId && e.target !== nodeId)
      if (this.selectedNodeId === nodeId) this.selectedNodeId = null
      this._setLastEditAction('deleted custom node')
      this.requestRelayout()
      this._persistEdits()
    },

    renameNode(nodeId: string, newName: string) {
      const trimmed = newName.trim()
      if (!trimmed) return
      const userNode = this.userNodes.find(n => n.id === nodeId)
      if (userNode) {
        if (userNode.name === trimmed) return
        this._recordHistory()
        userNode.name = trimmed
        this._setLastEditAction('renamed custom node')
        this._persistEdits()
        return
      }
      const node = this.nodes.find(n => n.id === nodeId)
      if (!node || node.name === trimmed) return
      this._recordHistory()
      node.name = trimmed
      this.nodeOverrides[nodeId] = { ...this.nodeOverrides[nodeId], name: trimmed }
      this._setLastEditAction('renamed resource')
      this._persistEdits()
    },

    updateNodeDetails(
      nodeId: string,
      updates: Partial<Pick<StackMapNode, 'provider' | 'resource_type' | 'category'>> & { weight?: number }
    ) {
      const userNode = this.userNodes.find(node => node.id === nodeId)
      if (userNode) {
        const changed =
          (updates.provider !== undefined && updates.provider !== userNode.provider)
          || (updates.resource_type !== undefined && updates.resource_type !== userNode.resource_type)
          || (updates.category !== undefined && updates.category !== userNode.category)
          || (typeof updates.weight === 'number' && updates.weight !== (userNode.position_hint?.weight || 4))
        if (!changed) return
        this._recordHistory()
        if (updates.provider !== undefined) userNode.provider = updates.provider
        if (updates.resource_type !== undefined) userNode.resource_type = updates.resource_type
        if (updates.category !== undefined) userNode.category = updates.category
        if (!userNode.position_hint) userNode.position_hint = { tier: 'compute', weight: 4 }
        if (typeof updates.weight === 'number') userNode.position_hint.weight = updates.weight
        this._setLastEditAction('updated custom node')
        this.requestRelayout()
        this._persistEdits()
        return
      }

      const node = this.nodes.find(candidate => candidate.id === nodeId)
      if (!node) return
      const original = this.originalNodeSnapshots[nodeId]
      const nextProvider = updates.provider ?? node.provider
      const nextResourceType = updates.resource_type ?? node.resource_type
      const nextCategory = updates.category ?? node.category
      const nextWeight = typeof updates.weight === 'number' ? updates.weight : (node.position_hint?.weight || 2)
      if (
        nextProvider === node.provider
        && nextResourceType === node.resource_type
        && nextCategory === node.category
        && nextWeight === (node.position_hint?.weight || 2)
      ) return
      this._recordHistory()
      node.provider = nextProvider
      node.resource_type = nextResourceType
      node.category = nextCategory
      if (!node.position_hint) node.position_hint = { tier: original?.tier || 'compute', weight: original?.weight || 2 }
      node.position_hint.weight = nextWeight
      this.nodeOverrides[nodeId] = {
        ...this.nodeOverrides[nodeId],
        provider: nextProvider !== original?.provider ? nextProvider : undefined,
        resource_type: nextResourceType !== original?.resource_type ? nextResourceType : undefined,
        category: nextCategory !== original?.category ? nextCategory : undefined,
        weight: nextWeight !== original?.weight ? nextWeight : undefined,
        name: this.nodeOverrides[nodeId]?.name,
      }
      if (Object.values(this.nodeOverrides[nodeId]).every(value => value === undefined)) {
        delete this.nodeOverrides[nodeId]
      }
      this._setLastEditAction('updated resource details')
      this.requestRelayout()
      this._persistEdits()
    },

    duplicateUserNode(nodeId: string) {
      const original = this.userNodes.find(n => n.id === nodeId)
      if (!original) return
      this._recordHistory()
      const id = `user:${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      this.userNodes.push({
        id,
        name: `${original.name} (copy)`,
        resource_type: original.resource_type,
        provider: original.provider,
        category: original.category,
        properties: { ...original.properties },
        tags: { ...original.tags, _user_created: 'true' },
        position_hint: {
          tier: original.position_hint?.tier || 'compute',
          weight: original.position_hint?.weight || 4,
        },
      })
      this._setLastEditAction('duplicated custom node')
      this.requestRelayout()
      this._persistEdits()
    },

    resetNodeEdits(nodeId: string) {
      const node = this.nodes.find(candidate => candidate.id === nodeId)
      const original = this.originalNodeSnapshots[nodeId]
      if (!node || !original) return
      this._recordHistory()
      node.name = original.name
      node.provider = original.provider
      node.resource_type = original.resource_type
      node.category = original.category
      if (!node.position_hint) node.position_hint = { tier: original.tier, weight: original.weight }
      node.position_hint.weight = original.weight
      node.position_hint.tier = original.tier
      delete this.nodeTierOverrides[nodeId]
      delete this.nodeOverrides[nodeId]
      this.hiddenNodeIds = this.hiddenNodeIds.filter(id => id !== nodeId)
      delete node.position_hint.manual_order
      this._setLastEditAction('reset resource edits')
      this.requestRelayout()
      this._persistEdits()
    },

    _persistEdits() {
      if (typeof window === 'undefined') return
      try {
        const data = {
          hiddenNodeIds: this.hiddenNodeIds,
          hiddenNodeIdsBackup: this.hiddenNodeIdsBackup,
          userEdges: this.userEdges,
          userNodes: this.userNodes,
          customLayers: this.customLayers,
          nodeTierOverrides: this.nodeTierOverrides,
          nodeOverrides: this.nodeOverrides,
          layoutLayers: this.layoutLayers,
        }
        localStorage.setItem('stackmap-edits', JSON.stringify(data))
        this.editPersistenceStatus = 'saved'
      } catch { /* ignore quota errors */ }
    },

    loadPersistedEdits() {
      if (typeof window === 'undefined') return
      try {
        const raw = localStorage.getItem('stackmap-edits')
        if (!raw) return
        const data = JSON.parse(raw)
        if (Array.isArray(data.hiddenNodeIds)) {
          this.hiddenNodeIds = data.hiddenNodeIds
        }
        if (Array.isArray(data.hiddenNodeIdsBackup)) {
          this.hiddenNodeIdsBackup = data.hiddenNodeIdsBackup
        }
        if (Array.isArray(data.userEdges)) {
          this.userEdges = data.userEdges.map((edge: StackMapEdge) => (
            edge.label === 'user link' && edge.edge_type === 'references'
              ? { ...edge, edge_type: 'user_link', color: edge.color || '#4ADE80' }
              : (edge.edge_type === 'user_link' ? { ...edge, color: edge.color || '#4ADE80' } : edge)
          ))
        }
        if (Array.isArray(data.userNodes)) {
          this.userNodes = data.userNodes
          for (const node of this.userNodes) {
          if (!node.position_hint) {
              node.position_hint = { tier: 'compute', weight: 4 }
            }
            node.position_hint.tier = normalizeNodeTier(node)
            if (!this.layoutLayers.includes(node.position_hint.tier)) {
              this.layoutLayers.push(node.position_hint.tier)
            }
          }
        }
        if (Array.isArray(data.customLayers)) {
          this.customLayers = data.customLayers
          for (const layer of this.customLayers) {
            if (!this.layoutLayers.includes(layer.id)) {
              this.layoutLayers.push(layer.id)
            }
          }
        }
        if (data.nodeOverrides && typeof data.nodeOverrides === 'object') {
          this.nodeOverrides = data.nodeOverrides
        }
        if (data.nodeTierOverrides && typeof data.nodeTierOverrides === 'object') {
          this.nodeTierOverrides = data.nodeTierOverrides
          for (const node of this.nodes) {
            const override = this.nodeTierOverrides[node.id]
            if (override) {
              if (!node.position_hint) node.position_hint = { tier: override, weight: 2 }
              node.position_hint.tier = override
              if (!this.layoutLayers.includes(override)) {
                this.layoutLayers.push(override)
              }
            }
          }
        }
        for (const node of this.nodes) {
          const meta = this.nodeOverrides[node.id]
          if (!meta) continue
          if (meta.name) node.name = meta.name
          if (meta.provider) node.provider = meta.provider
          if (meta.resource_type) node.resource_type = meta.resource_type
          if (meta.category) node.category = meta.category
          if (!node.position_hint) node.position_hint = { tier: normalizeNodeTier(node), weight: 2 }
          if (typeof meta.weight === 'number') node.position_hint.weight = meta.weight
          if (typeof meta.order === 'number') node.position_hint.manual_order = meta.order
        }
        if (Array.isArray(data.layoutLayers)) {
          const extras = this.layoutLayers.filter(layerId => !data.layoutLayers.includes(layerId))
          this.layoutLayers = [...data.layoutLayers, ...extras]
        }
        this.editPersistenceStatus = 'restored'
        if (typeof window !== 'undefined') {
          this.hasSeenEditWalkthrough = localStorage.getItem('stackmap-edit-walkthrough-seen') === 'true'
        }
      } catch { /* ignore parse errors */ }
    },

    exportEditsPayload(): string {
      return JSON.stringify({
        hiddenNodeIds: this.hiddenNodeIds,
        hiddenNodeIdsBackup: this.hiddenNodeIdsBackup,
        userEdges: this.userEdges,
        userNodes: this.userNodes,
        customLayers: this.customLayers,
        nodeTierOverrides: this.nodeTierOverrides,
        nodeOverrides: this.nodeOverrides,
        layoutLayers: this.layoutLayers,
        exportedAt: new Date().toISOString(),
      }, null, 2)
    },

    importEditsPayload(raw: string) {
      const data = JSON.parse(raw)
      this._recordHistory()
      if (Array.isArray(data.hiddenNodeIds)) this.hiddenNodeIds = data.hiddenNodeIds
      this.hiddenNodeIdsBackup = Array.isArray(data.hiddenNodeIdsBackup) ? data.hiddenNodeIdsBackup : null
      if (Array.isArray(data.userEdges)) this.userEdges = data.userEdges
      if (Array.isArray(data.userNodes)) this.userNodes = data.userNodes
      if (Array.isArray(data.customLayers)) this.customLayers = data.customLayers
      if (data.nodeTierOverrides && typeof data.nodeTierOverrides === 'object') this.nodeTierOverrides = data.nodeTierOverrides
      if (data.nodeOverrides && typeof data.nodeOverrides === 'object') this.nodeOverrides = data.nodeOverrides
      if (Array.isArray(data.layoutLayers)) this.layoutLayers = data.layoutLayers
      this._applyEditSnapshot(this._createEditSnapshot())
      this._setLastEditAction('imported edit overlay')
      this.editPersistenceStatus = 'imported'
      this._persistEdits()
    },

    exportCurrentGraphPayload(mode: 'raw' | 'corrected' | 'presentation' = 'corrected'): string {
      const useVisible = mode !== 'raw'
      const payload = {
        metadata: {
          ...this.metadata,
          export_mode: mode,
          exported_at: new Date().toISOString(),
        },
        nodes: useVisible ? this.visibleNodes : [...this.graphNodes, ...this.userNodes],
        edges: useVisible ? this.visibleEdges : [...this.graphEdges, ...this.userEdges],
        groups: this.graphGroups,
      }
      return JSON.stringify(payload, null, 2)
    },

    clearAllEdits() {
      this._recordHistory()
      this.hiddenNodeIds = []
      this.hiddenNodeIdsBackup = null
      this.userEdges = []
      this.userNodes = []
      this.connectingFromNodeId = null
      this.customLayers = []
      this.nodeTierOverrides = {}
      this.nodeOverrides = {}
      this.draggingNodeId = null
      this.dragTargetLayerId = null
      this.selectedEdgeId = null
      this.layoutLayers = [...DEFAULT_LAYOUT_LAYERS]
      for (const node of this.nodes) {
        if (!node.position_hint) node.position_hint = { tier: 'compute', weight: 2 }
        const original = this.originalNodeSnapshots[node.id]
        node.name = original?.name || node.name
        node.provider = original?.provider || node.provider
        node.resource_type = original?.resource_type || node.resource_type
        node.category = original?.category || node.category
        node.position_hint.tier = normalizeNodeTier(node)
        node.position_hint.weight = original?.weight || node.position_hint.weight || 2
        delete node.position_hint.manual_order
      }
      this._setLastEditAction('cleared all edits')
      this.requestRelayout()
      if (typeof window !== 'undefined') {
        localStorage.removeItem('stackmap-edits')
      }
    },

    // --- Feature: Dependency Tracing ---
    async traceNode(nodeId: string) {
      this.traceOriginId = nodeId
      try {
        const res = await fetch(`/api/trace?node=${encodeURIComponent(nodeId)}&depth=5&direction=both`)
        if (res.ok) {
          this.traceResult = await res.json()
        }
      } catch {
        // Client-side BFS fallback
        this.traceResult = this._clientSideTrace(nodeId)
      }
    },

    clearTrace() {
      this.traceResult = null
      this.traceOriginId = null
    },

    _clientSideTrace(originId: string) {
      const forward: Record<string, { target: string; edge_type: string; label: string }[]> = {}
      const reverse: Record<string, { source: string; edge_type: string; label: string }[]> = {}
      for (const edge of this.edges) {
        if (edge.edge_type === 'contains') continue
        if (!forward[edge.source]) forward[edge.source] = []
        forward[edge.source].push({ target: edge.target, edge_type: edge.edge_type, label: edge.label })
        if (!reverse[edge.target]) reverse[edge.target] = []
        reverse[edge.target].push({ source: edge.source, edge_type: edge.edge_type, label: edge.label })
      }

      const bfs = (adj: Record<string, any[]>, direction: string, keyField: string) => {
        const visited = new Set([originId])
        const queue = [{ id: originId, depth: 0 }]
        const hops: any[] = []
        while (queue.length > 0) {
          const { id, depth } = queue.shift()!
          if (depth >= 5) continue
          for (const neighbor of (adj[id] || [])) {
            const neighborId = neighbor[keyField]
            if (visited.has(neighborId)) continue
            visited.add(neighborId)
            hops.push({ node_id: neighborId, depth: depth + 1, edge_type: neighbor.edge_type, edge_label: neighbor.label || '', direction })
            queue.push({ id: neighborId, depth: depth + 1 })
          }
        }
        return hops
      }

      const upstream = bfs(reverse, 'upstream', 'source')
      const downstream = bfs(forward, 'downstream', 'target')

      return {
        origin_id: originId,
        upstream,
        downstream,
        blast_radius: new Set(downstream.map((h: any) => h.node_id)).size,
        critical_path: [originId],
        critical_path_length: 0,
      }
    },

    // --- Feature: Findings ---
    async loadFindings() {
      try {
        const res = await fetch('/api/findings')
        if (res.ok) {
          this.findings = await res.json()
        }
      } catch { /* ignore */ }
    },

    setFindingFilter(patternId: string | null) {
      this.activeFindingFilter = patternId
    },

    // --- Feature: Cost ---
    _sanitizeCostOverrides(overrides: Record<string, CostOverrideInput>): Record<string, CostOverrideInput> {
      const cleanedEntries = Object.entries(overrides)
        .map(([nodeId, values]) => {
          const cleanedValues = Object.fromEntries(
            Object.entries(values).filter(([, raw]) => typeof raw === 'number' && Number.isFinite(raw) && raw >= 0)
          ) as CostOverrideInput
          return [nodeId, cleanedValues] as const
        })
        .filter(([, values]) => Object.keys(values).length > 0)
      return Object.fromEntries(cleanedEntries)
    },

    _applyCostDataToNodes(report: CostReportData | null) {
      const byNode = report?.by_node || {}
      for (const node of this.nodes) {
        if (!node.position_hint) node.position_hint = { tier: 'compute', weight: 2 }
        const estimate = byNode[node.id]
        if (estimate) {
          node.position_hint.cost_monthly = estimate.monthly_estimate
          node.position_hint.cost_confidence = estimate.confidence as StackMapNode['position_hint']['cost_confidence']
          node.position_hint.cost_note = estimate.estimate_note
        } else {
          delete node.position_hint.cost_monthly
          delete node.position_hint.cost_confidence
          delete node.position_hint.cost_note
        }
      }
    },

    async ensureBaseCostData() {
      try {
        const res = await fetch('/api/cost')
        if (res.ok) {
          const report = await res.json() as CostReportData
          this.baseCostData = report
          if (!this.hasCostOverrides) {
            this.costData = report
            this._applyCostDataToNodes(report)
          }
        }
      } catch { /* ignore */ }
    },

    async refreshCostData(): Promise<{ ok: boolean; error?: string }> {
      if (!this.baseCostData) {
        await this.ensureBaseCostData()
      }

      const overrides = this._sanitizeCostOverrides(this.costOverrides)
      this.costOverrides = overrides

      if (Object.keys(overrides).length === 0) {
        this.costData = this.baseCostData
        this._applyCostDataToNodes(this.costData)
        return { ok: true }
      }

      try {
        const res = await fetch('/api/cost', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ overrides }),
        })
        if (res.ok) {
          const report = await res.json() as CostReportData
          this.costData = report
          this._applyCostDataToNodes(report)
          return { ok: true }
        }
        const body = await res.json().catch(() => ({}))
        return { ok: false, error: body?.error || `Server returned ${res.status}` }
      } catch (err) {
        return { ok: false, error: String(err) }
      }
    },

    async setNodeCostOverrides(nodeId: string, overrides: CostOverrideInput): Promise<{ ok: boolean; error?: string }> {
      const current = this.costOverrides[nodeId] || {}
      // Only merge keys that are explicitly provided (not undefined)
      const merged = { ...current }
      for (const [key, value] of Object.entries(overrides)) {
        if (value !== undefined) {
          (merged as Record<string, unknown>)[key] = value
        }
      }
      const cleaned = Object.fromEntries(
        Object.entries(merged).filter(([, value]) => typeof value === 'number' && Number.isFinite(value) && value >= 0)
      ) as CostOverrideInput

      if (Object.keys(cleaned).length > 0) {
        this.costOverrides = {
          ...this.costOverrides,
          [nodeId]: cleaned,
        }
      } else {
        const { [nodeId]: _removed, ...rest } = this.costOverrides
        this.costOverrides = rest
      }

      return this.refreshCostData()
    },

    async clearNodeCostOverrides(nodeId: string) {
      if (!(nodeId in this.costOverrides)) return
      const { [nodeId]: _removed, ...rest } = this.costOverrides
      this.costOverrides = rest
      await this.refreshCostData()
    },

    async loadCostData() {
      await this.refreshCostData()
    },

    async toggleCosts() {
      this.showCosts = !this.showCosts
      if (this.showCosts) {
        await this.refreshCostData()
      }
    },

    toggleCostHeatmap() {
      this.costHeatmap = !this.costHeatmap
    },

    // --- Feature: Drift ---
    setDriftMode(enabled: boolean) {
      this.driftMode = enabled
      if (enabled && this.metadata?.drift_summary) {
        this.driftSummary = this.metadata.drift_summary
      }
    },

    // --- Feature: Smart Groups ---
    toggleGroupCollapse(groupId: string) {
      if (this.collapsedGroups.has(groupId)) {
        this.collapsedGroups.delete(groupId)
      } else {
        this.collapsedGroups.add(groupId)
      }
    },

    // --- Feature: Live Logs ---
    async checkLogsAvailable() {
      try {
        const res = await fetch('/api/live-features')
        if (res.ok) {
          const data = await res.json()
          this.logsAvailable = !!data.logs
          this.billingAvailable = !!data.billing
        }
      } catch { /* ignore */ }
    },

    async toggleLogs() {
      this.showLogs = !this.showLogs
      if (this.showLogs && this.logEvents.length === 0) {
        await this.fetchVisibleLogs()
      }
    },

    async fetchLogs(nodeId?: string, options: { nodeIds?: string[]; scope?: 'visible' | 'all' | 'node' } = {}) {
      this.logLoading = true
      this.logError = null
      this.logNodeId = nodeId || null
      this.logScope = nodeId ? 'node' : (options.scope || (options.nodeIds?.length ? 'visible' : 'all'))

      try {
        const params = new URLSearchParams()
        if (nodeId) params.set('node', nodeId)
        if (!nodeId && options.nodeIds?.length) params.set('nodes', options.nodeIds.join(','))
        if (this.logFilter) params.set('filter', this.logFilter)
        params.set('minutes', String(this.logMinutes))
        params.set('limit', '200')

        const res = await fetch(`/api/logs?${params}`)
        if (res.ok) {
          const data = await res.json()
          this.logEvents = data.events || []
          this.logGroups = data.log_groups || []
          this.logError = data.error || null
        } else {
          const body = await res.json().catch(() => ({}))
          this.logError = body?.error || `Server returned ${res.status}`
        }
      } catch (err) {
        this.logError = String(err)
      } finally {
        this.logLoading = false
      }
    },

    async fetchVisibleLogs() {
      const nodeIds = this.visibleNodes.map(node => node.id)
      await this.fetchLogs(undefined, { nodeIds, scope: 'visible' })
    },

    async fetchAllLogs() {
      await this.fetchLogs(undefined, { scope: 'all' })
    },

    async setLogMinutes(minutes: number) {
      this.logMinutes = minutes
      if (this.logNodeId) {
        await this.fetchLogs(this.logNodeId)
      } else if (this.logScope === 'visible') {
        await this.fetchVisibleLogs()
      } else {
        await this.fetchAllLogs()
      }
    },

    async setLogFilter(filter: string) {
      this.logFilter = filter
      if (this.logNodeId) {
        await this.fetchLogs(this.logNodeId)
      } else if (this.logScope === 'visible') {
        await this.fetchVisibleLogs()
      } else {
        await this.fetchAllLogs()
      }
    },

    // --- Feature: Billing ---
    async fetchBillingData() {
      this.billingLoading = true
      this.billingError = null
      try {
        const res = await fetch('/api/billing')
        if (res.ok) {
          this.billingData = await res.json()
        } else {
          const body = await res.json().catch(() => ({}))
          this.billingError = body?.error || `Server returned ${res.status}`
        }
      } catch (err) {
        this.billingError = String(err)
      } finally {
        this.billingLoading = false
      }
    },

    async fetchUsageMetrics(nodeId: string) {
      try {
        const res = await fetch(`/api/billing/usage?node=${encodeURIComponent(nodeId)}`)
        if (res.ok) {
          const data = await res.json()
          if (data.usage && Object.keys(data.usage).length > 0) {
            await this.setNodeCostOverrides(nodeId, data.usage)
            return { ok: true, usage: data.usage }
          }
          return { ok: true, usage: {} }
        }
        const body = await res.json().catch(() => ({}))
        return { ok: false, error: body?.error || `Server returned ${res.status}` }
      } catch (err) {
        return { ok: false, error: String(err) }
      }
    },

    async fetchAllUsageMetrics(): Promise<{ ok: boolean; count?: number; error?: string }> {
      this.billingLoading = true
      this.billingError = null
      try {
        const res = await fetch('/api/billing/usage')
        if (res.ok) {
          const data = await res.json()
          const overrides = this._sanitizeCostOverrides(data.overrides || {})
          this.costOverrides = {
            ...this.costOverrides,
            ...overrides,
          }
          await this.refreshCostData()
          return { ok: true, count: Object.keys(overrides).length }
        }
        const body = await res.json().catch(() => ({}))
        const error = body?.error || `Server returned ${res.status}`
        this.billingError = error
        return { ok: false, error }
      } catch (err) {
        const error = String(err)
        this.billingError = error
        return { ok: false, error }
      } finally {
        this.billingLoading = false
      }
    },
  },
})
