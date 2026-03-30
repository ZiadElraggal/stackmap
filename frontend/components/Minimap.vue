<template>
  <div
    class="absolute bottom-10 right-4 w-48 h-36 bg-[#0e0e18]/90 border border-white/[0.06] rounded-xl overflow-hidden z-30 minimap-shell backdrop-blur-sm"
    @mousedown="onMouseDown"
  >
    <svg class="w-full h-full" :viewBox="viewBox">
      <line
        v-for="edge in store.visibleEdges"
        :key="edge.id"
        :x1="store.positions[edge.source]?.x ?? 0"
        :y1="store.positions[edge.source]?.y ?? 0"
        :x2="store.positions[edge.target]?.x ?? 0"
        :y2="store.positions[edge.target]?.y ?? 0"
        stroke="rgba(255,255,255,0.1)"
        stroke-width="0.5"
      />

      <circle
        v-for="node in store.visibleNodes"
        :key="node.id"
        :cx="store.positions[node.id]?.x ?? 0"
        :cy="store.positions[node.id]?.y ?? 0"
        :r="4"
        :fill="CATEGORY_COLORS[node.category] || '#9ca3af'"
        stroke="rgba(0,0,0,0.45)"
        stroke-width="1"
        opacity="0.82"
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

const viewBox = computed(() => {
  const positions = Object.values(store.positions)
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
