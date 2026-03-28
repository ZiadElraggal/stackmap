import * as d3 from 'd3'
import type { StackMapNode, StackMapEdge, StackMapGroup, NodePosition } from '~/stores/graph'

const TIER_Y: Record<string, number> = {
  frontend: 0,
  api: 300,
  backend: 600,
  data: 900,
}

interface SimNode extends d3.SimulationNodeDatum {
  id: string
  tier: string
  weight: number
}

export function useLayout() {
  function computeLayout(
    nodes: StackMapNode[],
    edges: StackMapEdge[],
    groups: StackMapGroup[]
  ): Record<string, NodePosition> {
    if (nodes.length === 0) return {}

    // Spread initial positions wider based on node count
    const spread = Math.max(1000, nodes.length * 20)

    const simNodes: SimNode[] = nodes.map(n => ({
      id: n.id,
      tier: n.position_hint?.tier || 'backend',
      weight: n.position_hint?.weight || 2,
      x: Math.random() * spread,
      y: TIER_Y[n.position_hint?.tier || 'backend'] || 600,
    }))

    const nodeIdSet = new Set(nodes.map(n => n.id))
    const simLinks = edges
      .filter(e => nodeIdSet.has(e.source) && nodeIdSet.has(e.target))
      .map(e => ({ source: e.source, target: e.target }))

    const simulation = d3.forceSimulation<SimNode>(simNodes)
      .force('x', d3.forceX<SimNode>(spread / 2).strength(0.03))
      .force('y', d3.forceY<SimNode>(d => TIER_Y[d.tier] ?? 600).strength(0.7))
      .force('charge', d3.forceManyBody<SimNode>().strength(-500).distanceMax(600))
      .force(
        'link',
        d3.forceLink<SimNode, d3.SimulationLinkDatum<SimNode>>(simLinks)
          .id(d => d.id)
          .distance(160)
          .strength(0.2)
      )
      .force('collide', d3.forceCollide<SimNode>(80))
      .stop()

    // Run iterations
    for (let i = 0; i < 300; i++) {
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
    padding: number = 40
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
      width: maxX - minX + 80,  // account for node width
      height: maxY - minY + 50, // account for node height
    }
  }

  return { computeLayout, computeGroupBounds }
}
