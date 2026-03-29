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
  function cloudfrontPreset(
    nodes: StackMapNode[],
    edges: StackMapEdge[]
  ): Record<string, NodePosition> {
    const byType = (t: string) => nodes.filter(n => n.resource_type === t)
    const distributions = byType('aws_cloudfront_distribution')
    const buckets = byType('aws_s3_bucket')
    const certs = byType('aws_acm_certificate')
    const oacs = byType('aws_cloudfront_origin_access_control')
    const roles = byType('aws_iam_role')
    const rolePolicies = byType('aws_iam_role_policy')

    if (distributions.length !== 1 || buckets.length < 1) return {}

    const cf = distributions[0]
    const s3 = buckets[0]
    const cert = certs[0]
    const oac = oacs[0]
    const role = roles[0]
    const rolePolicy = rolePolicies[0]

    const positions: Record<string, NodePosition> = {
      [cf.id]: { x: 900, y: 180 },
      [s3.id]: { x: 900, y: 720 },
    }

    if (oac) positions[oac.id] = { x: 1120, y: 420 }
    if (cert) positions[cert.id] = { x: 680, y: 420 }
    if (role) positions[role.id] = { x: 400, y: 420 }
    if (rolePolicy) positions[rolePolicy.id] = { x: 220, y: 420 }

    // Place remaining nodes near center lanes so force sim can settle faster
    for (const node of nodes) {
      if (positions[node.id]) continue
      const tier = node.position_hint?.tier || 'backend'
      positions[node.id] = {
        x: tier === 'frontend' ? 900 : tier === 'data' ? 900 : 600,
        y: TIER_Y[tier] ?? 600,
      }
    }

    // Guard: only use preset if CF routes toward S3 in this graph
    const hasCfToS3 = edges.some(e => e.source === cf.id && e.target === s3.id)
    return hasCfToS3 ? positions : {}
  }

  function computeLayout(
    nodes: StackMapNode[],
    edges: StackMapEdge[],
    groups: StackMapGroup[]
  ): Record<string, NodePosition> {
    if (nodes.length === 0) return {}

    const preset = cloudfrontPreset(nodes, edges)

    // Spread initial positions wider based on node count
    const spread = Math.max(1000, nodes.length * 20)

    const simNodes: SimNode[] = nodes.map(n => ({
      id: n.id,
      tier: n.position_hint?.tier || 'backend',
      weight: n.position_hint?.weight || 2,
      x: preset[n.id]?.x ?? Math.random() * spread,
      y: preset[n.id]?.y ?? (TIER_Y[n.position_hint?.tier || 'backend'] || 600),
    }))

    const nodeIdSet = new Set(nodes.map(n => n.id))
    const simLinks = edges
      .filter(e => nodeIdSet.has(e.source) && nodeIdSet.has(e.target))
      .map(e => ({ source: e.source, target: e.target }))

    const simulation = d3.forceSimulation<SimNode>(simNodes)
      .force('x', d3.forceX<SimNode>(d => preset[d.id]?.x ?? spread / 2).strength(0.08))
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
