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
    hopLimit: 0, // 0 = show all, 1-3 = N hops from selected node
    searchQuery: '',
    viewMode: 'architecture' as 'architecture' | 'raw',
    loaded: false,
  }),

  getters: {
    selectedNode(state): StackMapNode | null {
      if (!state.selectedNodeId) return null
      return state.nodes.find(n => n.id === state.selectedNodeId) ?? null
    },

    connectedNodeIds(state): (nodeId: string) => Set<string> {
      return (nodeId: string) => {
        const connected = new Set<string>()
        for (const edge of this.graphEdges) {
          if (edge.source === nodeId) connected.add(edge.target)
          if (edge.target === nodeId) connected.add(edge.source)
        }
        return connected
      }
    },

    // BFS to find nodes within N hops
    nodesWithinHops(state): (nodeId: string, hops: number) => Set<string> {
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

    graphNodes(state): StackMapNode[] {
      if (state.viewMode === 'raw') return state.nodes
      return state.nodes.filter(n => !n.position_hint?.logical_parent)
    },

    graphEdges(state): StackMapEdge[] {
      if (state.viewMode === 'raw') return state.edges

      const helperToParent = new Map<string, string>()
      for (const n of state.nodes) {
        const parent = n.position_hint?.logical_parent
        if (parent && typeof parent === 'string') {
          helperToParent.set(n.id, parent)
        }
      }

      const dedup = new Set<string>()
      const remapped: StackMapEdge[] = []
      for (const edge of state.edges) {
        const source = helperToParent.get(edge.source) || edge.source
        const target = helperToParent.get(edge.target) || edge.target
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
      return remapped
    },

    visibleNodes(state): StackMapNode[] {
      // Compute hop-limited set if applicable
      let hopSet: Set<string> | null = null
      if (state.hopLimit > 0 && state.selectedNodeId) {
        hopSet = this.nodesWithinHops(state.selectedNodeId, state.hopLimit)
      }

      return this.graphNodes.filter(n => {
        if (state.categoryFilters[n.category] === false) return false
        if (state.minWeight > 1 && (n.position_hint?.weight || 2) < state.minWeight) return false
        if (hopSet && !hopSet.has(n.id)) return false
        return true
      })
    },

    visibleEdges(): StackMapEdge[] {
      const visibleIds = new Set(this.visibleNodes.map((n: StackMapNode) => n.id))
      return this.graphEdges.filter(
        e => visibleIds.has(e.source) && visibleIds.has(e.target)
      )
    },

    nodeEdges(): (nodeId: string) => StackMapEdge[] {
      return (nodeId: string) => {
        return this.graphEdges.filter(
          e => e.source === nodeId || e.target === nodeId
        )
      }
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
      this.categoryFilters = Object.fromEntries(
        [...cats].map(c => [c, true])
      )

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
        const selected = this.nodes.find(n => n.id === this.selectedNodeId)
        if (selected?.position_hint?.logical_parent) {
          this.selectedNodeId = selected.position_hint.logical_parent
        }
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
