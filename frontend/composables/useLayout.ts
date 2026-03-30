import dagre from '@dagrejs/dagre'
import { getNodeHeight, getNodeWidth } from '~/composables/useGraph'
import type { StackMapNode, StackMapEdge, StackMapGroup, NodePosition } from '~/stores/graph'

const BASE_TIER_Y: Record<string, number> = {
  frontend: 0,
  api: 250,
  backend: 500,
  data: 750,
}

function getTierY(nodeCount: number): Record<string, number> {
  if (nodeCount > 60) {
    return { frontend: 0, api: 320, backend: 640, data: 960 }
  }
  return BASE_TIER_Y
}

const TIER_ORDER: Record<string, number> = {
  frontend: 0,
  api: 1,
  backend: 2,
  data: 3,
}

const LAYOUT_EDGE_TYPES = new Set(['triggers', 'writes_to', 'reads_from', 'routes_to'])
const TIER_LIST = ['frontend', 'api', 'backend', 'data']

// For large graphs, increase spacing to prevent visual clutter
function getLayoutParams(nodeCount: number) {
  if (nodeCount > 80) {
    return { nodesep: 100, ranksep: 220, edgesep: 35, marginx: 60, marginy: 60, minGap: 50 }
  }
  if (nodeCount > 40) {
    return { nodesep: 85, ranksep: 200, edgesep: 30, marginx: 50, marginy: 50, minGap: 40 }
  }
  return { nodesep: 70, ranksep: 180, edgesep: 25, marginx: 40, marginy: 40, minGap: 30 }
}

export function useLayout() {
  /**
   * Hybrid layout: dagre computes optimal X positions (minimizing edge crossings),
   * then we override Y positions with our fixed tier system.
   */
  function computeLayout(
    nodes: StackMapNode[],
    edges: StackMapEdge[],
    _groups: StackMapGroup[]
  ): Record<string, NodePosition> {
    if (nodes.length === 0) return {}

    const TIER_Y = getTierY(nodes.length)

    // Group nodes by tier for fallback
    const byTier = new Map<string, StackMapNode[]>()
    for (const node of nodes) {
      const tier = node.position_hint?.tier || 'backend'
      if (!byTier.has(tier)) byTier.set(tier, [])
      byTier.get(tier)!.push(node)
    }

    // Build dagre graph with just real nodes and edges
    const params = getLayoutParams(nodes.length)
    const g = new dagre.graphlib.Graph()
    g.setGraph({
      rankdir: 'TB',
      nodesep: params.nodesep,
      ranksep: params.ranksep,
      edgesep: params.edgesep,
      marginx: params.marginx,
      marginy: params.marginy,
      ranker: 'network-simplex',
    })
    g.setDefaultEdgeLabel(() => ({}))

    const nodeIdSet = new Set<string>()
    for (const node of nodes) {
      nodeIdSet.add(node.id)
      g.setNode(node.id, {
        width: getNodeWidth(node),
        height: getNodeHeight(node),
      })
    }

    let edgeCount = 0
    for (const edge of edges) {
      if (!LAYOUT_EDGE_TYPES.has(edge.edge_type)) continue
      if (!nodeIdSet.has(edge.source) || !nodeIdSet.has(edge.target)) continue
      g.setEdge(edge.source, edge.target, {
        weight: edge.edge_type === 'triggers' ? 3 : 2,
        minlen: 1,
      })
      edgeCount++
    }

    let positions: Record<string, NodePosition> = {}

    if (edgeCount > 0) {
      try {
        dagre.layout(g)

        // Take X from dagre, Y from our tier system
        for (const node of nodes) {
          const dagreNode = g.node(node.id)
          if (dagreNode && Number.isFinite(dagreNode.x)) {
            const tier = node.position_hint?.tier || 'backend'
            positions[node.id] = {
              x: dagreNode.x,
              y: TIER_Y[tier] ?? TIER_Y.backend,
            }
          }
        }
      } catch (_e) {
        // dagre failed, fall through to fallback
        positions = {}
      }
    }

    // Fallback: simple horizontal spacing per tier
    if (Object.keys(positions).length < nodes.length) {
      const startX = 200
      const rowGap = nodes.length > 60 ? 200 : 160
      for (const tier of TIER_LIST) {
        const tierNodes = (byTier.get(tier) || []).sort((a, b) => a.name.localeCompare(b.name))
        const tierWidth = tierNodes.length * rowGap
        tierNodes.forEach((node, idx) => {
          if (!positions[node.id]) {
            positions[node.id] = {
              x: startX + idx * rowGap - tierWidth / 2 + rowGap / 2,
              y: TIER_Y[tier] ?? TIER_Y.backend,
            }
          }
        })
      }
    }

    // De-overlap pass: since we override Y, nodes dagre put on different ranks
    // may now share the same Y. Spread them out if they overlap.
    const MIN_GAP = params.minGap

    for (const tier of TIER_LIST) {
      const tierNodes = (byTier.get(tier) || [])
        .filter(n => positions[n.id])
        .sort((a, b) => positions[a.id].x - positions[b.id].x)

      for (let i = 1; i < tierNodes.length; i++) {
        const prev = tierNodes[i - 1]
        const curr = tierNodes[i]
        const prevRight = positions[prev.id].x + getNodeWidth(prev) / 2
        const currLeft = positions[curr.id].x - getNodeWidth(curr) / 2
        const overlap = prevRight + MIN_GAP - currLeft
        if (overlap > 0) {
          // Push current node right
          positions[curr.id].x += overlap
        }
      }
    }

    // Center-align tiers: shift each tier so its center aligns with the overall center
    const allX = Object.values(positions).map(p => p.x)
    if (allX.length > 0) {
      const globalCenterX = (Math.min(...allX) + Math.max(...allX)) / 2

      for (const tier of TIER_LIST) {
        const tierNodeIds = (byTier.get(tier) || []).map(n => n.id).filter(id => positions[id])
        if (tierNodeIds.length === 0) continue

        const tierXs = tierNodeIds.map(id => positions[id].x)
        const tierCenterX = (Math.min(...tierXs) + Math.max(...tierXs)) / 2
        const shift = globalCenterX - tierCenterX

        for (const id of tierNodeIds) {
          positions[id].x += shift
        }
      }
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

  return { computeLayout, computeGroupBounds, sortByTier, TIER_Y: BASE_TIER_Y }
}
