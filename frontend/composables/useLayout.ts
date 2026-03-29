import * as d3 from 'd3'
import type { StackMapNode, StackMapEdge, StackMapGroup, NodePosition } from '~/stores/graph'

const TIER_Y: Record<string, number> = {
  frontend: 0,
  api: 350,
  backend: 750,
  data: 1150,
}

const TIER_ORDER: Record<string, number> = {
  frontend: 0,
  api: 1,
  backend: 2,
  data: 3,
}

const PRIMARY_FLOW_EDGE_TYPES = new Set(['triggers', 'reads_from', 'writes_to', 'routes_to', 'contains'])

interface SimNode extends d3.SimulationNodeDatum {
  id: string
  tier: string
  weight: number
  category: string
}

export function useLayout() {
  function buildFlowClusters(nodes: StackMapNode[], edges: StackMapEdge[]): Map<string, number> {
    const nodeIds = new Set(nodes.map(n => n.id))
    const adjacency = new Map<string, Set<string>>()
    for (const node of nodes) adjacency.set(node.id, new Set())

    for (const edge of edges) {
      if (!PRIMARY_FLOW_EDGE_TYPES.has(edge.edge_type)) continue
      if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) continue
      adjacency.get(edge.source)?.add(edge.target)
      adjacency.get(edge.target)?.add(edge.source)
    }

    let clusterIdx = 0
    const clusterByNode = new Map<string, number>()

    for (const node of nodes) {
      if (clusterByNode.has(node.id)) continue
      const stack = [node.id]
      clusterByNode.set(node.id, clusterIdx)
      while (stack.length) {
        const cur = stack.pop()!
        for (const next of adjacency.get(cur) || []) {
          if (clusterByNode.has(next)) continue
          clusterByNode.set(next, clusterIdx)
          stack.push(next)
        }
      }
      clusterIdx += 1
    }

    return clusterByNode
  }
  function cloudfrontPreset(
    nodes: StackMapNode[],
    edges: StackMapEdge[]
  ): Record<string, NodePosition> {
    const byType = (t: string) => nodes.filter(n => n.resource_type === t)
    const distributions = byType('aws_cloudfront_distribution')
    const buckets = byType('aws_s3_bucket')
    if (distributions.length !== 1 || buckets.length < 1) return {}

    const cf = distributions[0]
    const s3 = buckets[0]
    const cert = byType('aws_acm_certificate')[0]
    const oac = byType('aws_cloudfront_origin_access_control')[0]
    const role = byType('aws_iam_role')[0]

    const hasCfToS3 = edges.some(e => e.source === cf.id && e.target === s3.id)
    if (!hasCfToS3) return {}

    const positions: Record<string, NodePosition> = {
      [cf.id]: { x: 900, y: 180 },
      [s3.id]: { x: 900, y: 1100 },
    }

    if (oac) positions[oac.id] = { x: 1120, y: 560 }
    if (cert) positions[cert.id] = { x: 680, y: 560 }
    if (role) positions[role.id] = { x: 360, y: 750 }

    return positions
  }

  function computeLayout(
    nodes: StackMapNode[],
    edges: StackMapEdge[],
    _groups: StackMapGroup[]
  ): Record<string, NodePosition> {
    if (nodes.length === 0) return {}

    const preset = cloudfrontPreset(nodes, edges)
    const spread = Math.max(1800, nodes.length * 34)
    const tierStartX = 180
    const tierWidth = Math.max(1400, spread)

    const byTier = new Map<string, StackMapNode[]>()
    for (const node of nodes) {
      const tier = node.position_hint?.tier || 'backend'
      if (!byTier.has(tier)) byTier.set(tier, [])
      byTier.get(tier)?.push(node)
    }

    const initial = new Map<string, NodePosition>()

    for (const [tier, tierNodes] of byTier.entries()) {
      const sorted = [...tierNodes].sort((a, b) => a.name.localeCompare(b.name))
      const spacing = sorted.length > 1 ? tierWidth / (sorted.length - 1) : tierWidth / 2
      sorted.forEach((node, idx) => {
        if (preset[node.id]) {
          initial.set(node.id, preset[node.id])
          return
        }
        initial.set(node.id, {
          x: tierStartX + idx * spacing,
          y: TIER_Y[tier] ?? 750,
        })
      })
    }

    const clusterByNode = buildFlowClusters(nodes, edges)
    const clustersByTier = new Map<string, number[]>()
    for (const node of nodes) {
      const tier = node.position_hint?.tier || 'backend'
      const cluster = clusterByNode.get(node.id) ?? 0
      if (!clustersByTier.has(tier)) clustersByTier.set(tier, [])
      const list = clustersByTier.get(tier)!
      if (!list.includes(cluster)) list.push(cluster)
    }
    for (const [tier, list] of clustersByTier.entries()) {
      list.sort((a, b) => a - b)
      clustersByTier.set(tier, list)
    }

    const simNodes: SimNode[] = nodes.map(n => {
      const p = initial.get(n.id) || { x: Math.random() * spread, y: TIER_Y.backend }
      return {
        id: n.id,
        tier: n.position_hint?.tier || 'backend',
        weight: n.position_hint?.weight || 2,
        category: n.category,
        x: p.x,
        y: p.y,
      }
    })

    const nodeIdSet = new Set(nodes.map(n => n.id))
    const simLinks = edges
      .filter(e => nodeIdSet.has(e.source) && nodeIdSet.has(e.target))
      .map(e => ({ source: e.source, target: e.target }))

    const simulation = d3.forceSimulation<SimNode>(simNodes)
      .force('x', d3.forceX<SimNode>(d => {
        if (preset[d.id]) return preset[d.id].x
        const clusterId = clusterByNode.get(d.id) ?? 0
        const tierClusters = clustersByTier.get(d.tier) || [0]
        const clusterIndex = Math.max(0, tierClusters.indexOf(clusterId))
        const segment = tierWidth / Math.max(1, tierClusters.length)
        return tierStartX + segment * clusterIndex + segment / 2
      }).strength(0.15))
      .force('y', d3.forceY<SimNode>(d => preset[d.id]?.y ?? (TIER_Y[d.tier] ?? 750)).strength(0.85))
      .force('charge', d3.forceManyBody<SimNode>().strength(-600).distanceMax(900))
      .force(
        'link',
        d3.forceLink<SimNode, d3.SimulationLinkDatum<SimNode>>(simLinks)
          .id(d => d.id)
          .distance(200)
          .strength(0.2)
      )
      .force('collide', d3.forceCollide<SimNode>(100))
      .stop()

    for (let i = 0; i < 400; i++) {
      simulation.tick()
    }

    const positions: Record<string, NodePosition> = {}
    for (const node of simNodes) {
      positions[node.id] = { x: node.x!, y: node.y! }
    }

    return positions
  }

  function computeGroupBounds(
    group: StackMapGroup,
    positions: Record<string, NodePosition>,
    padding: number = 60
  ): { x: number; y: number; width: number; height: number } | null {
    const childPositions = group.children
      .map(id => positions[id])
      .filter(Boolean)

    if (childPositions.length === 0) return null

    const minX = Math.min(...childPositions.map(p => p.x)) - padding
    const maxX = Math.max(...childPositions.map(p => p.x)) + padding
    const minY = Math.min(...childPositions.map(p => p.y)) - padding
    const maxY = Math.max(...childPositions.map(p => p.y)) + padding

    return {
      x: minX,
      y: minY,
      width: maxX - minX + 140,
      height: maxY - minY + 100,
    }
  }

  function sortByTier(nodes: StackMapNode[]): StackMapNode[] {
    return [...nodes].sort((a, b) => {
      const ta = TIER_ORDER[a.position_hint?.tier || 'backend'] ?? 99
      const tb = TIER_ORDER[b.position_hint?.tier || 'backend'] ?? 99
      if (ta !== tb) return ta - tb
      return a.name.localeCompare(b.name)
    })
  }

  return { computeLayout, computeGroupBounds, sortByTier, TIER_Y }
}
