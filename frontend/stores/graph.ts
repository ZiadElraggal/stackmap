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
    logical_parent?: string
    is_helper?: boolean
    diff_status?: string
    diff_changes?: Record<string, unknown>
    account_id?: string
    region?: string
    org_path?: string
    view_kind?: string
  }
}

export interface StackMapEdge {
  id: string
  source: string
  target: string
  edge_type: string
  label: string
  color?: string
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

interface EditHistorySnapshot {
  hiddenNodeIds: string[]
  hiddenNodeIdsBackup: string[] | null
  userEdges: StackMapEdge[]
  userNodes: StackMapNode[]
  customLayers: Array<{ id: string; label: string }>
  nodeTierOverrides: Record<string, string>
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

    // Edit mode state
    editMode: false as boolean,
    hiddenNodeIds: [] as string[],
    hiddenNodeIdsBackup: null as string[] | null,
    userEdges: [] as StackMapEdge[],
    userNodes: [] as StackMapNode[],
    connectingFromNodeId: null as string | null,
    layoutVersion: 0 as number,
    layoutLayers: [...DEFAULT_LAYOUT_LAYERS] as string[],
    customLayers: [] as Array<{ id: string; label: string }>,
    nodeTierOverrides: {} as Record<string, string>,
    draggingNodeId: null as string | null,
    dragTargetLayerId: null as string | null,
    editHistoryPast: [] as EditHistorySnapshot[],
    editHistoryFuture: [] as EditHistorySnapshot[],
  }),

  getters: {
    selectedNode(state): StackMapNode | null {
      if (!state.selectedNodeId) return null
      return this.graphNodes.find((n: StackMapNode) => n.id === state.selectedNodeId)
        ?? state.userNodes.find(n => n.id === state.selectedNodeId)
        ?? state.nodes.find(n => n.id === state.selectedNodeId)
        ?? null
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
      return [...baseEdges, ...userEdgesVisible]
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
      this.layoutLayers = [...snapshot.layoutLayers]

      for (const node of this.nodes) {
        const override = this.nodeTierOverrides[node.id]
        if (!node.position_hint) node.position_hint = { tier: 'compute', weight: 2 }
        node.position_hint.tier = override || normalizeNodeTier(node)
      }

      for (const node of this.userNodes) {
        if (!node.position_hint) node.position_hint = { tier: 'compute', weight: 4 }
        node.position_hint.tier = normalizeNodeTier(node)
      }

      this.requestRelayout()
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
      this.editHistoryPast = []
      this.editHistoryFuture = []
      this.loaded = true
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
      if (!nodeId) this.hopLimit = 0
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
    },

    // ── Edit mode actions ─────────────────────────────────────────
    toggleEditMode() {
      this.editMode = !this.editMode
      if (!this.editMode) {
        this.connectingFromNodeId = null
      }
    },

    hideNode(nodeId: string) {
      this._recordHistory()
      if (!this.hiddenNodeIds.includes(nodeId)) {
        this.hiddenNodeIds.push(nodeId)
      }
      if (this.selectedNodeId === nodeId) this.selectedNodeId = null
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
      this.requestRelayout()
      this._persistEdits()
    },

    showAllNodes() {
      if (this.hiddenNodeIds.length === 0) return
      this._recordHistory()
      this.hiddenNodeIdsBackup = [...this.hiddenNodeIds]
      this.hiddenNodeIds = []
      this.requestRelayout()
      this._persistEdits()
    },

    rehideShownNodes() {
      if (!this.hiddenNodeIdsBackup?.length) return
      this._recordHistory()
      this.hiddenNodeIds = [...new Set([...this.hiddenNodeIdsBackup, ...this.hiddenNodeIds])]
      this.hiddenNodeIdsBackup = null
      this.requestRelayout()
      this._persistEdits()
    },

    startConnecting(nodeId: string) {
      this.connectingFromNodeId = nodeId
    },

    cancelConnecting() {
      this.connectingFromNodeId = null
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
        edge_type: 'user_link',
        label: 'user link',
        color: '#4ADE80',
      })
      this.connectingFromNodeId = null
      this.requestRelayout()
      this._persistEdits()
    },

    removeUserEdge(edgeId: string) {
      this._recordHistory()
      this.userEdges = this.userEdges.filter(e => e.id !== edgeId)
      this.requestRelayout()
      this._persistEdits()
    },

    setUserEdgeColor(edgeId: string, color: string) {
      const edge = this.userEdges.find(candidate => candidate.id === edgeId)
      if (!edge || edge.color === color) return
      this._recordHistory()
      edge.color = color
      this._persistEdits()
    },

    requestRelayout() {
      this.layoutVersion += 1
    },

    startDraggingNode(nodeId: string) {
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
      this.requestRelayout()
      this._persistEdits()
      return true
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
      } else {
        const node = this.nodes.find(candidate => candidate.id === nodeId)
        if (!node) return
        if (!node.position_hint) node.position_hint = { tier: layerId, weight: 2 }
        node.position_hint.tier = layerId
        this.nodeTierOverrides[nodeId] = layerId
      }
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
      this.requestRelayout()
      this._persistEdits()
    },

    removeUserNode(nodeId: string) {
      this._recordHistory()
      this.userNodes = this.userNodes.filter(n => n.id !== nodeId)
      // Also remove any edges (user or auto) that reference this node
      this.userEdges = this.userEdges.filter(e => e.source !== nodeId && e.target !== nodeId)
      if (this.selectedNodeId === nodeId) this.selectedNodeId = null
      this.requestRelayout()
      this._persistEdits()
    },

    renameUserNode(nodeId: string, newName: string) {
      const node = this.userNodes.find(n => n.id === nodeId)
      if (node) {
        this._recordHistory()
        node.name = newName
        this._persistEdits()
      }
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
          layoutLayers: this.layoutLayers,
        }
        localStorage.setItem('stackmap-edits', JSON.stringify(data))
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
        if (Array.isArray(data.layoutLayers)) {
          const extras = this.layoutLayers.filter(layerId => !data.layoutLayers.includes(layerId))
          this.layoutLayers = [...data.layoutLayers, ...extras]
        }
      } catch { /* ignore parse errors */ }
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
      this.draggingNodeId = null
      this.dragTargetLayerId = null
      this.layoutLayers = [...DEFAULT_LAYOUT_LAYERS]
      for (const node of this.nodes) {
        if (!node.position_hint) node.position_hint = { tier: 'compute', weight: 2 }
        node.position_hint.tier = normalizeNodeTier(node)
      }
      this.requestRelayout()
      if (typeof window !== 'undefined') {
        localStorage.removeItem('stackmap-edits')
      }
    },
  },
})
