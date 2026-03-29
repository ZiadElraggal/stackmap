import { defineStore } from 'pinia'

export interface StackMapNode {
  id: string
  name: string
  resource_type: string
  provider: string
  category: string
  properties: Record<string, any>
  tags: Record<string, string>
  position_hint: {
    tier: string
    weight: number
    logical_parent?: string
    is_helper?: boolean
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
}

export interface NodePosition {
  x: number
  y: number
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
    viewMode: 'architecture' as 'architecture' | 'raw',
    loaded: false,
  }),

  getters: {
    selectedNode(state): StackMapNode | null {
      if (!state.selectedNodeId) return null
      return this.graphNodes.find((n: StackMapNode) => n.id === state.selectedNodeId)
        ?? state.nodes.find(n => n.id === state.selectedNodeId)
        ?? null
    },

    helperParentMap(state): Map<string, string> {
      if (state.viewMode === 'raw') return new Map()
      return buildHelperParentMap(state.nodes, state.edges)
    },

    graphNodes(state): StackMapNode[] {
      if (state.viewMode === 'raw') return state.nodes
      const parentMap = this.helperParentMap
      // Hide ALL helper nodes: those with parents (remapped) AND orphans (dropped)
      return state.nodes.filter(n => !parentMap.has(n.id) && !isHelperNode(n))
    },

    graphEdges(state): StackMapEdge[] {
      if (state.viewMode === 'raw') return state.edges

      const parentMap = this.helperParentMap
      const dedup = new Set<string>()
      let remapped: StackMapEdge[] = []

      for (const edge of state.edges) {
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
        remapped = remapped.filter(e => !['references', 'authenticates', 'contains'].includes(e.edge_type))
      }

      return remapped
    },

    connectedNodeIds(): (nodeId: string) => Set<string> {
      return (nodeId: string) => {
        const connected = new Set<string>()
        for (const edge of this.graphEdges) {
          if (edge.source === nodeId) connected.add(edge.target)
          if (edge.target === nodeId) connected.add(edge.source)
        }
        return connected
      }
    },

    nodesWithinHops(): (nodeId: string, hops: number) => Set<string> {
      return (nodeId: string, hops: number) => {
        const visited = new Set<string>([nodeId])
        let frontier = new Set<string>([nodeId])

        for (let i = 0; i < hops; i++) {
          const nextFrontier = new Set<string>()
          for (const nid of frontier) {
            for (const edge of this.graphEdges) {
              if (edge.source === nid && !visited.has(edge.target)) {
                visited.add(edge.target)
                nextFrontier.add(edge.target)
              }
              if (edge.target === nid && !visited.has(edge.source)) {
                visited.add(edge.source)
                nextFrontier.add(edge.source)
              }
            }
          }
          frontier = nextFrontier
        }

        return visited
      }
    },

    visibleNodes(state): StackMapNode[] {
      let hopSet: Set<string> | null = null
      if (state.hopLimit > 0 && state.selectedNodeId) {
        hopSet = this.nodesWithinHops(state.selectedNodeId, state.hopLimit)
      }

      return this.graphNodes.filter((n: StackMapNode) => {
        if (state.categoryFilters[n.category] === false) return false
        if (state.minWeight > 1 && (n.position_hint?.weight || 2) < state.minWeight) return false
        if (hopSet && !hopSet.has(n.id)) return false
        return true
      })
    },

    visibleEdges(): StackMapEdge[] {
      const visibleIds = new Set(this.visibleNodes.map((n: StackMapNode) => n.id))
      return this.graphEdges.filter((e: StackMapEdge) => visibleIds.has(e.source) && visibleIds.has(e.target))
    },

    nodeEdges(): (nodeId: string) => StackMapEdge[] {
      return (nodeId: string) => this.graphEdges.filter((e: StackMapEdge) => e.source === nodeId || e.target === nodeId)
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

      const cats = new Set(this.nodes.map(n => n.category))
      this.categoryFilters = Object.fromEntries([...cats].map(c => [c, true]))

      this.loaded = true
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

    setViewMode(mode: 'architecture' | 'raw') {
      this.viewMode = mode
      if (mode === 'architecture' && this.selectedNodeId) {
        const parent = this.helperParentMap.get(this.selectedNodeId)
        if (parent) this.selectedNodeId = parent
      }
    },

    resetFilters() {
      for (const cat of Object.keys(this.categoryFilters)) {
        this.categoryFilters[cat] = true
      }
      this.minWeight = 1
      this.hopLimit = 0
      this.searchQuery = ''
    },
  },
})
