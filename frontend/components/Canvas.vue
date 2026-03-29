<template>
  <div class="relative h-full w-full overflow-hidden" ref="containerRef">
    <svg ref="svgRef" class="h-full w-full" :style="{ background: '#0a0a0f' }">
      <defs>
        <pattern id="grid-cross" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
          <line x1="18.5" y1="20" x2="21.5" y2="20" stroke="rgba(255,255,255,0.04)" stroke-width="1" />
          <line x1="20" y1="18.5" x2="20" y2="21.5" stroke="rgba(255,255,255,0.04)" stroke-width="1" />
        </pattern>

        <marker
          v-for="edgeType in edgeTypesInGraph"
          :id="`arrow-${edgeType}`"
          :key="`marker-${edgeType}`"
          viewBox="0 0 6 5"
          refX="5.6"
          refY="2.5"
          markerWidth="6"
          markerHeight="5"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 6 2.5 L 0 5 Z" :fill="edgeColor(edgeType)" />
        </marker>
      </defs>

      <rect width="100%" height="100%" fill="#0a0a0f" @click="store.selectNode(null)" />

      <g ref="zoomGroupRef">
        <rect
          :x="graphBounds.minX - 500"
          :y="graphBounds.minY - 500"
          :width="graphBounds.width + 1000"
          :height="graphBounds.height + 1000"
          fill="url(#grid-cross)"
          @click="store.selectNode(null)"
        />

        <g v-for="tier in tierLabels" :key="`tier-${tier.name}`" :transform="`translate(${tier.x}, ${tier.y}) rotate(-90)`">
          <text
            text-anchor="middle"
            fill="rgba(255,255,255,0.08)"
            font-size="10"
            letter-spacing="3"
            font-family="'JetBrains Mono', 'SF Mono', monospace"
          >
            {{ tier.name.toUpperCase() }}
          </text>
        </g>

        <GroupBoundary
          v-for="group in store.groups"
          :key="group.id"
          :group="group"
          :positions="store.positions"
        />

        <GraphEdge
          v-for="(edge, idx) in store.visibleEdges"
          :key="edge.id"
          :edge="edge"
          :x1="edgePos(edge.source).x"
          :y1="edgePos(edge.source).y"
          :x2="edgePos(edge.target).x"
          :y2="edgePos(edge.target).y"
          :zoom-scale="zoomScale"
          :entry-delay="edgeEntryBaseDelay + idx * 4"
        />

        <GraphNode
          v-for="(node, idx) in orderedVisibleNodes"
          :key="node.id"
          :node="node"
          :x="store.positions[node.id]?.x ?? 0"
          :y="store.positions[node.id]?.y ?? 0"
          :entry-delay="idx * 15"
        />
      </g>
    </svg>

    <div class="absolute left-1/2 top-4 z-40 -translate-x-1/2">
      <SearchBar ref="searchBarRef" @pan-to="panToNode" />
    </div>

    <Minimap :viewport="viewportRect" @pan-to-position="panToPosition" />

    <div class="absolute right-4 top-4 z-30">
      <button
        class="flex h-6 w-6 items-center justify-center rounded border border-white/10 bg-white/5 text-xs text-gray-500 hover:text-gray-300"
        @click="showHelp = !showHelp"
        title="Keyboard shortcuts (?)"
      >
        ?
      </button>
    </div>

    <Transition name="fade">
      <div
        v-if="showHelp"
        class="absolute right-4 top-12 z-50 w-56 rounded-lg border border-white/10 bg-[#1a1a2e] p-3 shadow-xl"
      >
        <h3 class="mb-2 text-xs uppercase tracking-wider text-gray-500">Keyboard shortcuts</h3>
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

    <div
      v-if="edgeTypesInGraph.length"
      class="absolute bottom-9 left-3 z-30 rounded-md border border-white/10 bg-[#12121a]/70 px-2 py-1 backdrop-blur-sm"
    >
      <div class="flex items-center gap-3">
        <div v-for="edgeType in edgeTypesInGraph" :key="`legend-${edgeType}`" class="flex items-center gap-1.5">
          <span class="h-px w-5" :style="{ backgroundColor: edgeColor(edgeType), opacity: 0.9 }" />
          <span class="text-[8px] uppercase tracking-wide text-gray-500">{{ edgeType }}</span>
        </div>
      </div>
    </div>

    <div class="status-glow absolute bottom-7 left-0 right-0 h-px" />

    <div
      class="absolute bottom-0 left-0 right-0 flex h-7 items-center gap-4 border-t border-white/5 bg-[#12121a]/90 px-4 font-mono text-xs text-gray-500"
    >
      <div class="flex items-center gap-2 text-gray-400">
        <span class="h-1.5 w-1.5 rounded-full bg-cyan-400" />
        <span class="text-[10px] font-semibold tracking-wide">StackMap</span>
      </div>
      <span>{{ store.visibleNodes.length }}/{{ store.nodes.length }} resources</span>
      <span>{{ store.visibleEdges.length }} connections</span>
      <span class="text-gray-600">{{ store.viewMode === 'architecture' ? 'architecture view' : 'terraform raw view' }}</span>
      <span v-if="store.groups.length > 0">{{ store.groups.length }} groups</span>
      <span v-if="store.metadata.terraform_version">Terraform v{{ store.metadata.terraform_version }}</span>
      <span>{{ Math.round(zoomScale * 100) }}%</span>
      <span class="ml-auto text-gray-600">scroll to zoom · drag to pan · ⌘K command palette</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, reactive, watch } from 'vue'
import * as d3 from 'd3'
import { useGraphStore } from '~/stores/graph'
import { useLayout } from '~/composables/useLayout'
import { EDGE_COLORS } from '~/composables/useGraph'

const store = useGraphStore()
const { computeLayout, sortByTier, TIER_Y } = useLayout()

const svgRef = ref<SVGSVGElement>()
const zoomGroupRef = ref<SVGGElement>()
const containerRef = ref<HTMLDivElement>()
const searchBarRef = ref<{ focus: () => void }>()
const showHelp = ref(false)

const viewportRect = ref<{ x: number; y: number; width: number; height: number } | null>(null)
const zoomScale = ref(1)

let zoomBehavior: d3.ZoomBehavior<SVGSVGElement, unknown> | null = null
let svgSelection: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null

const orderedVisibleNodes = computed(() => {
  const nodes = sortByTier(store.visibleNodes)
  return nodes
})

const edgeEntryBaseDelay = computed(() => orderedVisibleNodes.value.length * 15 + 200)

const edgeTypesInGraph = computed(() => {
  return [...new Set(store.visibleEdges.map(edge => edge.edge_type))]
})

const graphBounds = computed(() => {
  const points = Object.values(store.positions)
  if (!points.length) {
    return { minX: -800, minY: -400, width: 2200, height: 1900 }
  }
  const minX = Math.min(...points.map(p => p.x))
  const maxX = Math.max(...points.map(p => p.x))
  const minY = Math.min(...points.map(p => p.y))
  const maxY = Math.max(...points.map(p => p.y))
  return {
    minX,
    minY,
    width: Math.max(600, maxX - minX),
    height: Math.max(600, maxY - minY),
  }
})

const tierLabels = computed(() => {
  const minX = graphBounds.value.minX - 120
  return [
    { name: 'frontend', x: minX, y: TIER_Y.frontend },
    { name: 'api', x: minX, y: TIER_Y.api },
    { name: 'backend', x: minX, y: TIER_Y.backend },
    { name: 'data', x: minX, y: TIER_Y.data },
  ]
})

function edgeColor(edgeType: string): string {
  return EDGE_COLORS[edgeType] || '#64748b'
}

function edgePos(nodeId: string) {
  return store.positions[nodeId] ?? { x: 0, y: 0 }
}

onMounted(async () => {
  await store.loadFromJSON('/sample-data.json')

  recomputeLayout()

  if (svgRef.value && zoomGroupRef.value) {
    svgSelection = d3.select(svgRef.value)
    const g = d3.select(zoomGroupRef.value)

    zoomBehavior = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', event => {
        g.attr('transform', event.transform.toString())
        zoomScale.value = event.transform.k
        updateViewport(event.transform)
      })

    svgSelection.call(zoomBehavior)
    fitToViewport()
  }

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
  const tag = (e.target as HTMLElement)?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA') {
    if (e.key === 'Escape') {
      ;(e.target as HTMLElement).blur()
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
  if (!positions.length) return

  const padding = 140
  const minX = Math.min(...positions.map(p => p.x)) - padding
  const maxX = Math.max(...positions.map(p => p.x)) + padding
  const minY = Math.min(...positions.map(p => p.y)) - padding
  const maxY = Math.max(...positions.map(p => p.y)) + padding

  const width = svgRef.value?.clientWidth || 1000
  const height = svgRef.value?.clientHeight || 800

  const graphWidth = Math.max(1, maxX - minX)
  const graphHeight = Math.max(1, maxY - minY)
  const scale = Math.min(width / graphWidth, height / graphHeight, 1.45)
  const tx = width / 2 - (minX + graphWidth / 2) * scale
  const ty = height / 2 - (minY + graphHeight / 2) * scale

  svgSelection.transition().duration(500).call(zoomBehavior.transform, d3.zoomIdentity.translate(tx, ty).scale(scale))
}

function recomputeLayout() {
  const positions = computeLayout(store.graphNodes, store.graphEdges, store.groups)
  store.setPositions(positions)
}

function zoomBy(factor: number) {
  if (!svgSelection || !zoomBehavior) return
  svgSelection.transition().duration(300).call(zoomBehavior.scaleBy, factor)
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
    .call(zoomBehavior.transform, d3.zoomIdentity.translate(width / 2 - pos.x * scale, height / 2 - pos.y * scale).scale(scale))
}

function panToPosition(position: { x: number; y: number }) {
  if (!svgSelection || !zoomBehavior) return
  const width = svgRef.value?.clientWidth || 1000
  const height = svgRef.value?.clientHeight || 800
  const scale = zoomScale.value || 1
  svgSelection.call(
    zoomBehavior.transform,
    d3.zoomIdentity.translate(width / 2 - position.x * scale, height / 2 - position.y * scale).scale(scale)
  )
}

function updateViewport(transform: d3.ZoomTransform) {
  if (!svgRef.value) return
  const w = svgRef.value.clientWidth
  const h = svgRef.value.clientHeight

  viewportRect.value = {
    x: -transform.x / transform.k,
    y: -transform.y / transform.k,
    width: w / transform.k,
    height: h / transform.k,
  }
}

const emit = defineEmits<{
  toggleCommandPalette: []
}>()

defineExpose({ fitToViewport, panToNode })
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.status-glow {
  background: linear-gradient(90deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0));
}
</style>
