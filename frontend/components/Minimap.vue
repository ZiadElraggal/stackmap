<template>
  <div
    class="absolute bottom-10 right-4 w-48 h-36 bg-[#0e0e18]/90 border border-white/[0.06] rounded-xl overflow-hidden z-30 minimap-shell backdrop-blur-sm"
    @mousedown="onMouseDown"
  >
    <svg class="w-full h-full" :viewBox="viewBox">
      <line
        v-for="edge in minimapEdges"
        :key="edge.id"
        :x1="edge.sourcePosition.x"
        :y1="edge.sourcePosition.y"
        :x2="edge.targetPosition.x"
        :y2="edge.targetPosition.y"
        stroke="rgba(255,255,255,0.1)"
        :stroke-width="Math.min(2, 0.35 + edge.count * 0.08)"
      />

      <circle
        v-for="node in minimapNodes"
        :key="node.id"
        :cx="node.position.x"
        :cy="node.position.y"
        :r="node.radius"
        :fill="CATEGORY_COLORS[node.category] || '#9ca3af'"
        stroke="rgba(0,0,0,0.45)"
        stroke-width="1"
        :opacity="node.opacity"
      />

      <rect
        v-if="viewport"
        :x="viewport.x"
        :y="viewport.y"
        :width="viewport.width"
        :height="viewport.height"
        fill="rgba(59,130,246,0.08)"
        stroke="rgba(148,163,184,0.45)"
        stroke-width="2"
        rx="2"
      />
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useGraphStore } from '~/stores/graph'
import { CATEGORY_COLORS } from '~/composables/useGraph'

const store = useGraphStore()

const props = defineProps<{
  viewport: { x: number; y: number; width: number; height: number } | null
}>()

const emit = defineEmits<{
  panToPosition: [{ x: number; y: number }]
}>()

type MinimapNode = {
  id: string
  category: string
  position: { x: number; y: number }
  radius: number
  opacity: number
}

type MinimapEdge = {
  id: string
  sourcePosition: { x: number; y: number }
  targetPosition: { x: number; y: number }
  count: number
}

const shouldUseOverview = computed(() => {
  return store.viewMode === 'architecture' && store.componentSummaries.length > 1 && !store.activeComponentId
})

const componentByNodeId = computed(() => {
  const byNode = new Map<string, string>()
  for (const component of store.componentSummaries) {
    for (const nodeId of component.nodeIds) byNode.set(nodeId, component.id)
  }
  return byNode
})

function fallbackPosition(index: number): { x: number; y: number } {
  const columns = Math.max(1, Math.ceil(Math.sqrt(store.componentSummaries.length || 1)))
  return {
    x: (index % columns) * 180,
    y: Math.floor(index / columns) * 140,
  }
}

function centroid(nodeIds: string[], fallback: { x: number; y: number }): { x: number; y: number } {
  const points = nodeIds
    .map(nodeId => store.positions[nodeId])
    .filter((point): point is { x: number; y: number } => Boolean(point))
  if (points.length === 0) return fallback
  return {
    x: points.reduce((sum, point) => sum + point.x, 0) / points.length,
    y: points.reduce((sum, point) => sum + point.y, 0) / points.length,
  }
}

const overviewPositions = computed(() => {
  const positions = new Map<string, { x: number; y: number }>()
  store.componentSummaries.forEach((component, index) => {
    positions.set(component.id, centroid(component.nodeIds, fallbackPosition(index)))
  })
  return positions
})

const minimapNodes = computed<MinimapNode[]>(() => {
  if (shouldUseOverview.value) {
    return store.componentSummaries.map((component, index) => ({
      id: `overview:${component.id}`,
      category: component.dominantCategories[0] || 'other',
      position: overviewPositions.value.get(component.id) || fallbackPosition(index),
      radius: Math.min(10, Math.max(4, Math.sqrt(component.resourceCount) + 2)),
      opacity: 0.9,
    }))
  }

  return store.visibleNodes.map(node => ({
    id: node.id,
    category: node.category,
    position: store.positions[node.id] || { x: 0, y: 0 },
    radius: 4,
    opacity: 0.82,
  }))
})

const minimapEdges = computed<MinimapEdge[]>(() => {
  if (!shouldUseOverview.value) {
    return store.visibleEdges.map(edge => ({
      id: edge.id,
      sourcePosition: store.positions[edge.source] || { x: 0, y: 0 },
      targetPosition: store.positions[edge.target] || { x: 0, y: 0 },
      count: 1,
    }))
  }

  const counts = new Map<string, { source: string; target: string; count: number }>()
  for (const edge of store.graphEdges) {
    const source = componentByNodeId.value.get(edge.source)
    const target = componentByNodeId.value.get(edge.target)
    if (!source || !target || source === target) continue
    const key = `${source}->${target}`
    const current = counts.get(key)
    if (current) {
      current.count += 1
    } else {
      counts.set(key, { source, target, count: 1 })
    }
  }

  return [...counts.entries()].map(([id, edge]) => ({
    id: `overview-edge:${id}`,
    sourcePosition: overviewPositions.value.get(edge.source) || { x: 0, y: 0 },
    targetPosition: overviewPositions.value.get(edge.target) || { x: 0, y: 0 },
    count: edge.count,
  }))
})

const viewBox = computed(() => {
  const positions = minimapNodes.value.map(node => node.position)
  if (positions.length === 0) return '0 0 100 100'

  const pad = 80
  const minX = Math.min(...positions.map(p => p.x)) - pad
  const maxX = Math.max(...positions.map(p => p.x)) + pad
  const minY = Math.min(...positions.map(p => p.y)) - pad
  const maxY = Math.max(...positions.map(p => p.y)) + pad

  return `${minX} ${minY} ${maxX - minX} ${maxY - minY}`
})

function pointFromMouse(event: MouseEvent): { x: number; y: number } | null {
  const svg = (event.currentTarget as HTMLElement).querySelector('svg') as SVGSVGElement | null
  if (!svg) return null
  const pt = svg.createSVGPoint()
  pt.x = event.clientX
  pt.y = event.clientY
  const ctm = svg.getScreenCTM()
  if (!ctm) return null
  const transformed = pt.matrixTransform(ctm.inverse())
  return { x: transformed.x, y: transformed.y }
}

function onMouseDown(e: MouseEvent) {
  const first = pointFromMouse(e)
  if (!first) return
  emit('panToPosition', first)

  const onMove = (ev: MouseEvent) => {
    const p = pointFromMouse(ev)
    if (!p) return
    emit('panToPosition', p)
  }

  const onUp = () => {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }

  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}
</script>

<style scoped>
.minimap-shell {
  box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.4), 0 4px 20px rgba(0, 0, 0, 0.3);
}
</style>
