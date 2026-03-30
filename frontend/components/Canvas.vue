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
          refX="8"
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
        <g>
          <rect
            v-for="band in tierBands"
            :key="`tier-band-${band.name}`"
            :x="graphBounds.minX - 260"
            :y="band.yStart"
            :width="graphBounds.width + 520"
            :height="band.yEnd - band.yStart"
            :fill="band.fill"
            :fill-opacity="tierBandOpacity(band.name)"
            :stroke="band.stroke"
            :stroke-opacity="tierBorderOpacity(band.name)"
            stroke-width="1.2"
          />
        </g>

        <g>
          <line
            v-for="divider in tierDividers"
            :key="`tier-divider-${divider.name}`"
            :x1="graphBounds.minX - 250"
            :x2="graphBounds.minX + graphBounds.width + 250"
            :y1="divider.y"
            :y2="divider.y"
            :stroke="divider.stroke"
            :stroke-opacity="tierDividerOpacity(divider.name)"
            stroke-width="1"
          />
        </g>

        <rect
          :x="graphBounds.minX - 500"
          :y="graphBounds.minY - 500"
          :width="graphBounds.width + 1000"
          :height="graphBounds.height + 1000"
          fill="url(#grid-cross)"
          @click="store.selectNode(null)"
        />

        <g v-for="band in tierBands" :key="`tier-${band.name}`">
          <rect
            :x="graphBounds.minX - 226"
            :y="band.yStart + 12"
            rx="8"
            ry="8"
            width="118"
            height="24"
            :fill="band.chipFill"
            :fill-opacity="tierChipOpacity(band.name)"
            :stroke="band.chipStroke"
            :stroke-opacity="tierChipOpacity(band.name)"
            stroke-width="1"
          />
          <text
            :x="graphBounds.minX - 216"
            :y="band.yStart + 28"
            :fill="band.chipAccent"
            font-size="10"
            text-anchor="start"
            font-weight="700"
            letter-spacing="1.5"
            font-family="'JetBrains Mono', monospace"
          >{{ band.icon }}</text>
          <text
            :x="graphBounds.minX - 200"
            :y="band.yStart + 28"
            fill="rgba(229,231,235,0.95)"
            font-size="10"
            text-anchor="start"
            font-weight="600"
            letter-spacing="1.3"
            font-family="'JetBrains Mono', monospace"
          >{{ band.name.toUpperCase() }}</text>
          <text
            :x="graphBounds.minX - 60"
            :y="band.labelY"
            fill="rgba(255,255,255,0.1)"
            font-size="11"
            font-weight="600"
            letter-spacing="3"
            text-anchor="end"
            dominant-baseline="central"
            font-family="'JetBrains Mono', monospace"
          >{{ band.name.toUpperCase() }}</text>
        </g>

        <g v-for="(band, idx) in tierBands" :key="`flow-arrow-${band.name}`">
          <text
            v-if="idx < tierBands.length - 1"
            :x="graphBounds.minX + graphBounds.width / 2"
            :y="band.yEnd + 10"
            fill="rgba(255,255,255,0.06)"
            font-size="16"
            text-anchor="middle"
            dominant-baseline="central"
          >↓</text>
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
          :x1="edgeSourcePos(edge).x"
          :y1="edgeSourcePos(edge).y"
          :x2="edgeTargetPos(edge).x"
          :y2="edgeTargetPos(edge).y"
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
      <span class="text-gray-600">{{ viewModeLabel }}</span>
      <span v-if="store.groups.length > 0">{{ store.groups.length }} groups</span>
      <span v-if="store.metadata.terraform_version">Terraform v{{ store.metadata.terraform_version }}</span>
      <span>{{ Math.round(zoomScale * 100) }}%</span>
      <div class="flex items-center gap-1 rounded border border-white/10 bg-white/[0.03] px-1.5 py-0.5">
        <div
          v-for="lane in architectureStrip"
          :key="`strip-${lane.name}`"
          class="flex items-center gap-1 rounded px-1 py-[1px]"
          :style="{ backgroundColor: lane.bg }"
        >
          <span class="text-[8px] uppercase tracking-wide" :style="{ color: lane.accent }">{{ lane.short }}</span>
          <span class="text-[9px] text-gray-300">{{ lane.count }}</span>
        </div>
      </div>
      <span class="ml-auto text-gray-600">scroll to zoom · drag to pan · ⌘K command palette</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import * as d3 from 'd3'
import { useGraphStore, type StackMapEdge, type StackMapNode } from '~/stores/graph'
import { useLayout } from '~/composables/useLayout'
import { EDGE_COLORS, getNodeHeight } from '~/composables/useGraph'

const store = useGraphStore()
const { computeLayout, sortByTier } = useLayout()

const svgRef = ref<SVGSVGElement>()
const zoomGroupRef = ref<SVGGElement>()
const containerRef = ref<HTMLDivElement>()
const searchBarRef = ref<{ focus: () => void }>()
const showHelp = ref(false)

const viewportRect = ref<{ x: number; y: number; width: number; height: number } | null>(null)
const zoomScale = ref(1)

let zoomBehavior: d3.ZoomBehavior<SVGSVGElement, unknown> | null = null
let svgSelection: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null

const orderedVisibleNodes = computed(() => sortByTier(store.visibleNodes))
const visibleNodeMap = computed(() => new Map(store.visibleNodes.map(n => [n.id, n])))
const edgeEntryBaseDelay = computed(() => orderedVisibleNodes.value.length * 15 + 200)
const edgeTypesInGraph = computed(() => [...new Set(store.visibleEdges.map(edge => edge.edge_type))])

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

const tierBands = computed(() => {
  const tierNodes: Record<string, number[]> = {}
  for (const node of store.visibleNodes) {
    const tier = node.position_hint?.tier || 'backend'
    const pos = store.positions[node.id]
    if (!pos) continue
    if (!tierNodes[tier]) tierNodes[tier] = []
    tierNodes[tier].push(pos.y)
  }

  const bands: Array<{
    name: string
    yStart: number
    yEnd: number
    fill: string
    stroke: string
    chipFill: string
    chipStroke: string
    chipAccent: string
    labelY: number
    icon: string
  }> = []
  const tierOrder = ['frontend', 'api', 'backend', 'data']
  const tierColors: Record<string, { fill: string; stroke: string; icon: string }> = {
    frontend: { fill: 'rgba(34,211,238,0.09)', stroke: 'rgba(34,211,238,0.32)', icon: '◈' },
    api: { fill: 'rgba(59,130,246,0.085)', stroke: 'rgba(59,130,246,0.3)', icon: '◎' },
    backend: { fill: 'rgba(99,102,241,0.08)', stroke: 'rgba(129,140,248,0.28)', icon: '▣' },
    data: { fill: 'rgba(16,185,129,0.09)', stroke: 'rgba(52,211,153,0.3)', icon: '◉' },
  }

  for (const tier of tierOrder) {
    const ys = tierNodes[tier]
    if (!ys || ys.length === 0) continue
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)
    const padding = 80
    const c = tierColors[tier] || { fill: 'rgba(255,255,255,0.05)', stroke: 'rgba(255,255,255,0.2)', icon: '•' }
    bands.push({
      name: tier,
      yStart: minY - padding,
      yEnd: maxY + padding,
      fill: c.fill,
      stroke: c.stroke,
      chipFill: c.fill,
      chipStroke: c.stroke,
      chipAccent: c.stroke,
      labelY: (minY + maxY) / 2,
      icon: c.icon,
    })
  }

  return bands
})

const tierDividers = computed(() => {
  const dividers: Array<{ name: string; y: number; stroke: string }> = []
  for (let i = 0; i < tierBands.value.length - 1; i++) {
    const current = tierBands.value[i]
    const next = tierBands.value[i + 1]
    dividers.push({
      name: `${current.name}-${next.name}`,
      y: (current.yEnd + next.yStart) / 2,
      stroke: 'rgba(255,255,255,0.18)',
    })
  }
  return dividers
})

const hoveredTier = computed(() => {
  if (!store.hoveredNodeId) return null
  const node = store.graphNodes.find(n => n.id === store.hoveredNodeId) || store.nodes.find(n => n.id === store.hoveredNodeId)
  return node?.position_hint?.tier || null
})

const architectureStrip = computed(() => {
  const order = ['frontend', 'api', 'backend', 'data']
  const names: Record<string, string> = { frontend: 'FE', api: 'API', backend: 'BE', data: 'DATA' }
  const accents: Record<string, string> = {
    frontend: '#67e8f9',
    api: '#60a5fa',
    backend: '#818cf8',
    data: '#34d399',
  }
  const backgrounds: Record<string, string> = {
    frontend: 'rgba(34,211,238,0.16)',
    api: 'rgba(59,130,246,0.16)',
    backend: 'rgba(99,102,241,0.16)',
    data: 'rgba(16,185,129,0.16)',
  }
  const counts: Record<string, number> = { frontend: 0, api: 0, backend: 0, data: 0 }
  for (const node of store.visibleNodes) {
    const tier = node.position_hint?.tier || 'backend'
    if (tier in counts) counts[tier] += 1
  }
  return order.map(name => ({
    name,
    short: names[name],
    count: counts[name] || 0,
    accent: accents[name],
    bg: backgrounds[name],
  }))
})

const viewModeLabel = computed(() => {
  if (store.viewMode === 'architecture') return 'architecture view'
  const sourceType = String(store.metadata?.source_type || '').toLowerCase()
  if (sourceType === 'cloudformation') return 'cloudformation raw view'
  if (sourceType === 'terraform') return 'terraform raw view'
  return 'raw view'
})

function tierBandOpacity(bandName: string): number {
  if (!hoveredTier.value) return 0.65
  return hoveredTier.value === bandName ? 0.95 : 0.28
}

function tierBorderOpacity(bandName: string): number {
  if (!hoveredTier.value) return 0.45
  return hoveredTier.value === bandName ? 0.9 : 0.2
}

function tierDividerOpacity(dividerName: string): number {
  if (!hoveredTier.value) return 0.22
  return dividerName.includes(hoveredTier.value) ? 0.45 : 0.15
}

function tierChipOpacity(bandName: string): number {
  if (!hoveredTier.value) return 0.9
  return hoveredTier.value === bandName ? 1 : 0.45
}

function edgeColor(edgeType: string): string {
  return EDGE_COLORS[edgeType] || '#64748b'
}

function edgeSourcePos(edge: StackMapEdge) {
  const pos = store.positions[edge.source]
  if (!pos) return { x: 0, y: 0 }
  const node = visibleNodeMap.value.get(edge.source)
  if (!node) return pos
  const h = getNodeHeight(node)
  const targetPos = store.positions[edge.target]
  if (!targetPos) return pos
  const dy = targetPos.y - pos.y
  return { x: pos.x, y: pos.y + (dy > 0 ? h / 2 : -h / 2) }
}

function edgeTargetPos(edge: StackMapEdge) {
  const pos = store.positions[edge.target]
  if (!pos) return { x: 0, y: 0 }
  const node = visibleNodeMap.value.get(edge.target)
  if (!node) return pos
  const h = getNodeHeight(node)
  const sourcePos = store.positions[edge.source]
  if (!sourcePos) return pos
  const dy = sourcePos.y - pos.y
  return { x: pos.x, y: pos.y + (dy > 0 ? h / 2 : -h / 2) }
}

onMounted(async () => {
  try {
    await store.loadFromJSON('/api/graph')
  } catch {
    // Fallback for static/offline exports that only ship sample-data.json.
    await store.loadFromJSON('/sample-data.json')
  }

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
  () => [
    store.viewMode,
    store.visibleNodes.map(n => n.id).join('|'),
    store.visibleEdges.map(e => e.id).join('|'),
  ],
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

const SIDEBAR_WIDTH = 256
const DETAIL_PANEL_WIDTH = 0 // Detail panel overlaps, accounted only when open

function fitToViewport() {
  if (!svgSelection || !zoomBehavior) return

  const positions = Object.values(store.positions)
  if (!positions.length) return

  const padding = 120
  const minX = Math.min(...positions.map(p => p.x)) - padding
  const maxX = Math.max(...positions.map(p => p.x)) + padding
  const minY = Math.min(...positions.map(p => p.y)) - padding
  const maxY = Math.max(...positions.map(p => p.y)) + padding

  const totalWidth = svgRef.value?.clientWidth || 1000
  const height = (svgRef.value?.clientHeight || 800) - 40 // subtract status bar
  // Account for sidebar taking space on the left
  const availableWidth = totalWidth - SIDEBAR_WIDTH
  const offsetX = SIDEBAR_WIDTH

  const graphWidth = Math.max(1, maxX - minX)
  const graphHeight = Math.max(1, maxY - minY)
  const scale = Math.min(availableWidth / graphWidth, height / graphHeight, 1.45)
  const tx = offsetX + availableWidth / 2 - (minX + graphWidth / 2) * scale
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
