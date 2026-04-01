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
    viewMode: 'architecture' as 'architecture' | 'raw' | 'organization',
    loaded: false,
    diffMode: false as boolean,
    diffSlider: 0.5 as number,
    showOnlyChanges: false as boolean,
    activeAccountId: null as string | null,
    activeOrgGroupId: null as string | null,
    showCrossAccountEdges: true as boolean,
  }),

  getters: {
    selectedNode(state): StackMapNode | null {
      if (!state.selectedNodeId) return null
      return this.graphNodes.find((n: StackMapNode) => n.id === state.selectedNodeId)
        ?? state.nodes.find(n => n.id === state.selectedNodeId)
        ?? null
    },

    hasOrganizationData(state): boolean {
      return state.groups.some(group => group.group_type === 'account')
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

    graphNodes(state): StackMapNode[] {
      if (state.viewMode === 'organization') return this.organizationNodes
      if (state.viewMode === 'raw') {
        return state.activeAccountId
          ? state.nodes.filter(node => accountIdForNode(node) === state.activeAccountId)
          : state.nodes
      }

      const parentMap = this.helperParentMap
      let graphNodes = state.nodes.filter(n => !parentMap.has(n.id) && !isHelperNode(n))
      if (state.activeAccountId) {
        graphNodes = graphNodes.filter(node => accountIdForNode(node) === state.activeAccountId)
      }
      return graphNodes
    },

    graphEdges(state): StackMapEdge[] {
      if (state.viewMode === 'organization') {
        return this.organizationEdges
      }

      let baseEdges = state.edges
      if (!state.showCrossAccountEdges) {
        baseEdges = baseEdges.filter(edge => edge.edge_type !== 'cross_account_reference')
      }

      if (state.viewMode === 'raw') {
        if (!state.activeAccountId) return baseEdges
        const visibleIds = new Set(
          state.nodes
            .filter(node => accountIdForNode(node) === state.activeAccountId)
            .map(node => node.id)
        )
        return baseEdges.filter(edge => visibleIds.has(edge.source) && visibleIds.has(edge.target))
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

      if (state.viewMode === 'architecture') {
        const nodeById = new Map(state.nodes.map(n => [n.id, n]))
        remapped = remapped.filter(edge => {
          if (ARCH_DROPPED_EDGE_TYPES.has(edge.edge_type)) return false
          if (edge.edge_type === 'cross_account_reference') return true
          if (edge.edge_type !== 'references') return true
          return shouldKeepReferenceEdge(nodeById.get(edge.source), nodeById.get(edge.target))
        })
      }

      if (state.activeAccountId) {
        const visibleIds = new Set(this.graphNodes.map(node => node.id))
        remapped = remapped.filter(edge => visibleIds.has(edge.source) && visibleIds.has(edge.target))
      }

      return remapped
    },

    graphGroups(state): StackMapGroup[] {
      if (state.viewMode === 'organization') return this.organizationGroups
      if (!state.activeAccountId) return state.groups

      const nodesById = new Map(state.nodes.map(node => [node.id, node]))
      return state.groups.filter(group => groupTouchesAccount(group, nodesById, state.activeAccountId as string))
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
      for (const edge of this.graphEdges) {
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
      if (!path) return [accountNode?.name || state.activeAccountId]
      return path.split('/').filter(Boolean).concat(accountNode?.name || [])
    },

    visibleNodes(state): StackMapNode[] {
      let hopSet: Set<string> | null = null
      if (state.hopLimit > 0 && state.selectedNodeId) {
        hopSet = this.nodesWithinHops(state.selectedNodeId, state.hopLimit)
      }

      return this.graphNodes.filter((node: StackMapNode) => {
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
      return this.graphEdges.filter((edge: StackMapEdge) => visibleIds.has(edge.source) && visibleIds.has(edge.target))
    },

    nodeEdges(): (nodeId: string) => StackMapEdge[] {
      return (nodeId: string) => this.graphEdges.filter((edge: StackMapEdge) => edge.source === nodeId || edge.target === nodeId)
    },
  },

  actions: {
    async loadFromJSON(path: string) {
      const data =
        typeof window !== 'undefined' && (window as any).__STACKMAP_DATA__
          ? (window as any).__STACKMAP_DATA__
          : await fetch(path).then(r => r.json())

      this.metadata = data.metadata || {}
      this.nodes = data.nodes || []
      this.edges = data.edges || []
      this.groups = data.groups || []

      const cats = new Set(this.graphNodes.map(node => node.category))
      this.categoryFilters = Object.fromEntries([...cats].map(category => [category, true]))

      if (this.metadata.diff_mode) {
        this.diffMode = true
        this.diffSlider = 0.5
      }

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

    setViewMode(mode: 'architecture' | 'raw' | 'organization') {
      this.viewMode = mode
      if (mode === 'architecture' && this.selectedNodeId) {
        const parent = this.helperParentMap.get(this.selectedNodeId)
        if (parent) this.selectedNodeId = parent
      }
      if (mode === 'organization') {
        this.selectedNodeId = null
      }
    },

    setActiveAccount(accountId: string | null) {
      this.activeAccountId = accountId
      this.activeOrgGroupId = null
      this.selectedNodeId = null
      this.hopLimit = 0
    },

    enterAccountArchitecture(accountId: string) {
      this.activeAccountId = accountId
      this.activeOrgGroupId = null
      this.viewMode = 'architecture'
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

    resetFilters() {
      for (const category of Object.keys(this.categoryFilters)) {
        this.categoryFilters[category] = true
      }
      this.minWeight = 1
      this.hopLimit = 0
      this.searchQuery = ''
      this.activeAccountId = null
      this.activeOrgGroupId = null
      this.showCrossAccountEdges = true
    },
  },
})
