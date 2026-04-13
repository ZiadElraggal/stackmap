/**
 * Client-side dependency tracing composable.
 * Provides BFS-based upstream/downstream traversal for use in exported HTML.
 */

import { computed, ref } from 'vue'
import type { StackMapEdge, StackMapNode } from '~/stores/graph'

export interface TraceHop {
  node_id: string
  depth: number
  edge_type: string
  edge_label: string
  direction: 'upstream' | 'downstream'
}

export interface TraceResult {
  origin_id: string
  upstream: TraceHop[]
  downstream: TraceHop[]
  blast_radius: number
  critical_path: string[]
  critical_path_length: number
}

const STRUCTURAL_EDGE_TYPES = new Set(['contains'])

export function useTrace(
  nodes: () => StackMapNode[],
  edges: () => StackMapEdge[],
) {
  const traceResult = ref<TraceResult | null>(null)
  const traceOriginId = ref<string | null>(null)

  const tracedNodeIds = computed<Set<string>>(() => {
    if (!traceResult.value) return new Set()
    const ids = new Set<string>()
    ids.add(traceResult.value.origin_id)
    for (const hop of traceResult.value.upstream) ids.add(hop.node_id)
    for (const hop of traceResult.value.downstream) ids.add(hop.node_id)
    return ids
  })

  const tracedEdgeIds = computed<Set<string>>(() => {
    if (!traceResult.value) return new Set()
    const traced = tracedNodeIds.value
    const ids = new Set<string>()
    for (const edge of edges()) {
      if (traced.has(edge.source) && traced.has(edge.target)) {
        ids.add(edge.id)
      }
    }
    return ids
  })

  function buildAdjacency() {
    const forward: Record<string, { target: string; edge_type: string; label: string }[]> = {}
    const reverse: Record<string, { source: string; edge_type: string; label: string }[]> = {}

    for (const edge of edges()) {
      if (STRUCTURAL_EDGE_TYPES.has(edge.edge_type)) continue
      if (!forward[edge.source]) forward[edge.source] = []
      forward[edge.source].push({ target: edge.target, edge_type: edge.edge_type, label: edge.label })
      if (!reverse[edge.target]) reverse[edge.target] = []
      reverse[edge.target].push({ source: edge.source, edge_type: edge.edge_type, label: edge.label })
    }

    return { forward, reverse }
  }

  function bfs(
    adj: Record<string, any[]>,
    originId: string,
    direction: 'upstream' | 'downstream',
    keyField: 'source' | 'target',
    maxDepth: number = 5,
  ): TraceHop[] {
    const visited = new Set([originId])
    const queue: { id: string; depth: number }[] = [{ id: originId, depth: 0 }]
    const hops: TraceHop[] = []

    while (queue.length > 0) {
      const { id, depth } = queue.shift()!
      if (depth >= maxDepth) continue
      for (const neighbor of (adj[id] || [])) {
        const neighborId = neighbor[keyField]
        if (visited.has(neighborId)) continue
        visited.add(neighborId)
        hops.push({
          node_id: neighborId,
          depth: depth + 1,
          edge_type: neighbor.edge_type,
          edge_label: neighbor.label || '',
          direction,
        })
        queue.push({ id: neighborId, depth: depth + 1 })
      }
    }

    return hops
  }

  function trace(nodeId: string, maxDepth: number = 5): TraceResult {
    const { forward, reverse } = buildAdjacency()

    const upstream = bfs(reverse, nodeId, 'upstream', 'source', maxDepth)
    const downstream = bfs(forward, nodeId, 'downstream', 'target', maxDepth)

    const downstreamIds = new Set(downstream.map(h => h.node_id))

    return {
      origin_id: nodeId,
      upstream,
      downstream,
      blast_radius: downstreamIds.size,
      critical_path: [nodeId],
      critical_path_length: 0,
    }
  }

  function startTrace(nodeId: string) {
    traceOriginId.value = nodeId
    traceResult.value = trace(nodeId)
  }

  function clearTrace() {
    traceResult.value = null
    traceOriginId.value = null
  }

  return {
    traceResult,
    traceOriginId,
    tracedNodeIds,
    tracedEdgeIds,
    startTrace,
    clearTrace,
    trace,
  }
}
