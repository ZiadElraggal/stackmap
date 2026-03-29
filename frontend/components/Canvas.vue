<template>
  <div class="relative w-full h-full overflow-hidden" ref="containerRef">
    <svg
      ref="svgRef"
      class="w-full h-full"
      :style="{ background: '#0a0a0f' }"
    >
      <!-- Grid dots pattern -->
      <defs>
        <pattern id="grid-dots" x="0" y="0" width="30" height="30" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="0.5" fill="rgba(255,255,255,0.06)" />
        </pattern>
        <marker
          id="arrowhead"
          viewBox="0 0 10 7"
          refX="10"
          refY="3.5"
          markerWidth="8"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <polygon points="0 0, 10 3.5, 0 7" fill="#6b7280" />
        </marker>
      </defs>

      <rect width="100%" height="100%" fill="url(#grid-dots)" @click="store.selectNode(null)" />

      <!-- Zoomable group -->
      <g ref="zoomGroupRef">
        <!-- Groups (background) -->
        <GroupBoundary
          v-for="group in store.groups"
          :key="group.id"
          :group="group"
          :positions="store.positions"
        />

        <!-- Edges (middle layer) -->
        <GraphEdge
          v-for="edge in store.visibleEdges"
          :key="edge.id"
          :edge="edge"
          :x1="edgePos(edge.source).x"
          :y1="edgePos(edge.source).y"
          :x2="edgePos(edge.target).x"
          :y2="edgePos(edge.target).y"
        />

        <!-- Nodes (top layer) -->
        <GraphNode
          v-for="node in store.visibleNodes"
          :key="node.id"
          :node="node"
          :x="store.positions[node.id]?.x ?? 0"
          :y="store.positions[node.id]?.y ?? 0"
        />
      </g>
    </svg>

    <!-- Search bar (top center) -->
    <div class="absolute top-4 left-1/2 -translate-x-1/2 z-40">
      <SearchBar ref="searchBarRef" @pan-to="panToNode" />
    </div>

    <!-- Minimap -->
    <Minimap :viewport="viewportRect" />

    <!-- Keyboard help -->
    <div class="absolute top-4 right-4 z-30">
      <button
        class="w-6 h-6 rounded bg-white/5 border border-white/10 text-gray-500 hover:text-gray-300 text-xs flex items-center justify-center"
        @click="showHelp = !showHelp"
        title="Keyboard shortcuts (?)"
      >?</button>
    </div>

    <!-- Keyboard help overlay -->
    <Transition name="fade">
      <div
        v-if="showHelp"
        class="absolute top-12 right-4 w-56 bg-[#1a1a2e] border border-white/10 rounded-lg p-3 z-50 shadow-xl"
      >
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">Keyboard shortcuts</h3>
        <div class="space-y-1 text-xs">
          <div class="flex justify-between"><span class="text-gray-400">⌘K</span><span class="text-gray-600">Command palette</span></div>
          <div class="flex justify-between"><span class="text-gray-400">/</span><span class="text-gray-600">Search</span></div>
          <div class="flex justify-between"><span class="text-gray-400">Esc</span><span class="text-gray-600">Deselect / Close</span></div>
          <div class="flex justify-between"><span class="text-gray-400">0</span><span class="text-gray-600">Fit to screen</span></div>
          <div class="flex justify-between"><span class="text-gray-400">+ / -</span><span class="text-gray-600">Zoom in / out</span></div>
          <div class="flex justify-between"><span class="text-gray-400">?</span><span class="text-gray-600">Toggle help</span></div>
        </div>
      </div>
    </Transition>

    <!-- Status bar -->
    <div class="absolute bottom-0 left-0 right-0 h-7 bg-[#12121a]/90 border-t border-white/5 flex items-center px-4 text-xs text-gray-500 font-mono gap-4">
      <span>{{ store.visibleNodes.length }}/{{ store.nodes.length }} resources</span>
      <span>{{ store.visibleEdges.length }} connections</span>
      <span class="text-gray-600">{{ store.viewMode === 'architecture' ? 'architecture view' : 'terraform raw view' }}</span>
      <span v-if="store.groups.length > 0">{{ store.groups.length }} groups</span>
      <span v-if="store.metadata.terraform_version">Terraform v{{ store.metadata.terraform_version }}</span>
      <span class="ml-auto text-gray-600">scroll to zoom · drag to pan · ⌘K command palette</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, reactive, watch } from 'vue'
import * as d3 from 'd3'
import { useGraphStore } from '~/stores/graph'
import { useLayout } from '~/composables/useLayout'

const store = useGraphStore()
const { computeLayout } = useLayout()

const svgRef = ref<SVGSVGElement>()
const zoomGroupRef = ref<SVGGElement>()
const containerRef = ref<HTMLDivElement>()
const searchBarRef = ref<{ focus: () => void }>()
const showHelp = ref(false)

const viewportRect = reactive<{ x: number; y: number; width: number; height: number } | null>(null)

let zoomBehavior: d3.ZoomBehavior<SVGSVGElement, unknown> | null = null
let svgSelection: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null

function edgePos(nodeId: string) {
  return store.positions[nodeId] ?? { x: 0, y: 0 }
}

onMounted(async () => {
  await store.loadFromJSON('/sample-data.json')

  recomputeLayout()

  if (svgRef.value && zoomGroupRef.value) {
    svgSelection = d3.select(svgRef.value)
    const g = d3.select(zoomGroupRef.value)

    zoomBehavior = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform.toString())
        updateViewport(event.transform)
      })

    svgSelection.call(zoomBehavior)
    fitToViewport()
  }

  // Keyboard shortcuts
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})

watch(
  () => [store.viewMode, store.nodes.length, store.edges.length],
  () => {
    if (!store.loaded) return
    recomputeLayout()
  }
)

function onKeydown(e: KeyboardEvent) {
  // Don't capture when typing in inputs
  const tag = (e.target as HTMLElement)?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA') {
    if (e.key === 'Escape') {
      (e.target as HTMLElement).blur()
      store.selectNode(null)
    }
    return
  }

  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault()
    emit('toggleCommandPalette')
    return
  }

  switch (e.key) {
    case '/':
      e.preventDefault()
      searchBarRef.value?.focus()
      break
    case 'Escape':
      store.selectNode(null)
      showHelp.value = false
      break
    case '0':
    case ' ':
      e.preventDefault()
      fitToViewport()
      break
    case '=':
    case '+':
      e.preventDefault()
      zoomBy(1.3)
      break
    case '-':
      e.preventDefault()
      zoomBy(0.7)
      break
    case '?':
      showHelp.value = !showHelp.value
      break
  }
}

function fitToViewport() {
  if (!svgSelection || !zoomBehavior) return

  const positions = Object.values(store.positions)
  if (positions.length === 0) return

  const padding = 100
  const minX = Math.min(...positions.map(p => p.x)) - padding
  const maxX = Math.max(...positions.map(p => p.x)) + padding
  const minY = Math.min(...positions.map(p => p.y)) - padding
  const maxY = Math.max(...positions.map(p => p.y)) + padding

  const width = svgRef.value?.clientWidth || 1000
  const height = svgRef.value?.clientHeight || 800

  const graphWidth = maxX - minX
  const graphHeight = maxY - minY
  const scale = Math.min(width / graphWidth, height / graphHeight, 1.5)
  const tx = width / 2 - (minX + graphWidth / 2) * scale
  const ty = height / 2 - (minY + graphHeight / 2) * scale

  svgSelection
    .transition()
    .duration(500)
    .call(
      zoomBehavior.transform,
      d3.zoomIdentity.translate(tx, ty).scale(scale)
    )
}

function recomputeLayout() {
  const positions = computeLayout(store.graphNodes, store.graphEdges, store.groups)
  store.setPositions(positions)
}

function zoomBy(factor: number) {
  if (!svgSelection || !zoomBehavior) return
  svgSelection
    .transition()
    .duration(300)
    .call(zoomBehavior.scaleBy, factor)
}

function panToNode(nodeId: string) {
  if (!svgSelection || !zoomBehavior) return
  const pos = store.positions[nodeId]
  if (!pos) return

  const width = svgRef.value?.clientWidth || 1000
  const height = svgRef.value?.clientHeight || 800
  const scale = 1.2

  svgSelection
    .transition()
    .duration(500)
    .call(
      zoomBehavior.transform,
      d3.zoomIdentity
        .translate(width / 2 - pos.x * scale, height / 2 - pos.y * scale)
        .scale(scale)
    )
}

function updateViewport(transform: d3.ZoomTransform) {
  if (!svgRef.value) return
  const w = svgRef.value.clientWidth
  const h = svgRef.value.clientHeight

  Object.assign(viewportRect ?? {}, {
    x: -transform.x / transform.k,
    y: -transform.y / transform.k,
    width: w / transform.k,
    height: h / transform.k,
  })
}

const emit = defineEmits<{
  toggleCommandPalette: []
}>()

defineExpose({ fitToViewport, panToNode })
</script>

<style scoped>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
