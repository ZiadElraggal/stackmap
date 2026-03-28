import { defineStore } from 'pinia'

export interface StackMapNode {
  id: string
  name: string
  resource_type: string
  provider: string
  category: string
  properties: Record<string, any>
  tags: Record<string, string>
  position_hint: { tier: string; weight: number }
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
        for (const edge of state.edges) {
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
            for (const edge of state.edges) {
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
      // Compute hop-limited set if applicable
      let hopSet: Set<string> | null = null
      if (state.hopLimit > 0 && state.selectedNodeId) {
        hopSet = this.nodesWithinHops(state.selectedNodeId, state.hopLimit)
      }

      return state.nodes.filter(n => {
        if (state.categoryFilters[n.category] === false) return false
        if (state.minWeight > 1 && (n.position_hint?.weight || 2) < state.minWeight) return false
        if (hopSet && !hopSet.has(n.id)) return false
        return true
      })
    },

    visibleEdges(state): StackMapEdge[] {
      const visibleIds = new Set(this.visibleNodes.map((n: StackMapNode) => n.id))
      return state.edges.filter(
        e => visibleIds.has(e.source) && visibleIds.has(e.target)
      )
    },

    nodeEdges(state): (nodeId: string) => StackMapEdge[] {
      return (nodeId: string) => {
        return state.edges.filter(
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
