<template>
  <g
    :class="['graph-edge', { dimmed: isDimmed }]"
    :style="{
      '--edge-color': edgeColor,
      '--edge-delay': `${entryDelay}ms`,
    }"
  >
    <path
      :d="pathD"
      :stroke="edgeColor"
      :stroke-width="strokeWidth"
      :stroke-dasharray="dashPattern"
      fill="none"
      :opacity="computedOpacity"
      :marker-end="`url(#arrow-${edge.edge_type})`"
      class="edge-path"
    />

    <circle
      v-if="edge.edge_type === 'triggers' && !isDimmed"
      class="flow-dot"
      :fill="edgeColor"
      r="2.5"
      :opacity="computedOpacity"
    >
      <animateMotion dur="2s" repeatCount="indefinite" keySplines="0.42 0 0.58 1" keyTimes="0;1" calcMode="spline" :path="pathD" />
    </circle>

    <g v-if="showLabel">
      <rect
        :x="labelPosition.x - labelWidth / 2"
        :y="labelPosition.y - 8"
        :width="labelWidth"
        height="14"
        rx="3"
        ry="3"
        fill="rgba(10,10,15,0.8)"
      />
      <text
        :x="labelPosition.x"
        :y="labelPosition.y + 2"
        text-anchor="middle"
        fill="#6b7280"
        font-size="8"
        font-family="'JetBrains Mono', 'SF Mono', monospace"
      >{{ edge.edge_type }}</text>
    </g>

    <title>{{ edge.label || edge.edge_type }}</title>
  </g>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useGraphStore, type StackMapEdge } from '~/stores/graph'
import { EDGE_COLORS } from '~/composables/useGraph'

const props = withDefaults(
  defineProps<{
    edge: StackMapEdge
    x1: number
    y1: number
    x2: number
    y2: number
    zoomScale?: number
    entryDelay?: number
  }>(),
  {
    zoomScale: 1,
    entryDelay: 0,
  }
)

const store = useGraphStore()

const edgeDiffStatus = computed(() => store.edgeDiffStatus[props.edge.id] as string | undefined)

const edgeColor = computed(() => {
  if (store.diffMode && edgeDiffStatus.value === 'added') return '#22c55e'
  if (store.diffMode && edgeDiffStatus.value === 'removed') return '#ef4444'
  return EDGE_COLORS[props.edge.edge_type] || '#64748b'
})

const isConnectedToHovered = computed(() => {
  const hovered = store.hoveredNodeId
  if (!hovered) return false
  return props.edge.source === hovered || props.edge.target === hovered
})

const isConnectedToSelected = computed(() => {
  const selected = store.selectedNodeId
  if (!selected) return false
  return props.edge.source === selected || props.edge.target === selected
})

const isDimmed = computed(() => {
  const hovered = store.hoveredNodeId
  if (!hovered) return false
  return !isConnectedToHovered.value
})

const computedOpacity = computed(() => {
  if (store.hoveredNodeId) {
    return isConnectedToHovered.value ? 1 : 0.04
  }
  if (store.selectedNodeId) {
    return isConnectedToSelected.value ? 0.9 : 0.06
  }
  if (store.diffMode && edgeDiffStatus.value) {
    if (edgeDiffStatus.value === 'removed') {
      return Math.max(0.05, (0.5 - store.diffSlider) * 2 * 0.7)
    }
    if (edgeDiffStatus.value === 'added') {
      return Math.max(0.05, (store.diffSlider - 0.5) * 2 * 0.7)
    }
    if (edgeDiffStatus.value === 'unchanged') return 0.15
  }
  const type = props.edge.edge_type
  if (type === 'triggers') return 0.85
  if (type === 'writes_to' || type === 'reads_from') return 0.7
  if (type === 'routes_to') return 0.55
  return 0.2
})

const strokeWidth = computed(() => {
  const base: Record<string, number> = {
    triggers: 1.5,
    reads_from: 1.5,
    writes_to: 1.5,
    routes_to: 1.2,
    references: 1,
    contains: 0.8,
    authenticates: 1.2,
  }
  const lift = isConnectedToHovered.value ? 0.5 : 0
  return (base[props.edge.edge_type] ?? 1.2) + lift
})

const dashPattern = computed(() => {
  if (store.diffMode && edgeDiffStatus.value === 'added') return '6 3'
  if (store.diffMode && edgeDiffStatus.value === 'removed') return '3 4'
  if (props.edge.edge_type === 'references') return '4 3'
  if (props.edge.edge_type === 'contains') return '1 3'
  return 'none'
})

const pathD = computed(() => {
  const dx = props.x2 - props.x1
  const dy = props.y2 - props.y1
  const absDy = Math.abs(dy)
  const absDx = Math.abs(dx)

  if (absDy < 30 && absDx < 200) {
    return `M ${props.x1},${props.y1} L ${props.x2},${props.y2}`
  }

  if (absDy < 60) {
    const curve = dx >= 0 ? -60 : 60
    const cx = (props.x1 + props.x2) / 2
    const cy = (props.y1 + props.y2) / 2 + curve
    return `M ${props.x1},${props.y1} Q ${cx},${cy} ${props.x2},${props.y2}`
  }

  const midY = (props.y1 + props.y2) / 2
  const r = 12

  if (absDx < 20) {
    return `M ${props.x1},${props.y1} L ${props.x2},${props.y2}`
  }

  const signX = dx > 0 ? 1 : -1
  const signY = dy > 0 ? 1 : -1

  return [
    `M ${props.x1},${props.y1}`,
    `L ${props.x1},${midY - r * signY}`,
    `Q ${props.x1},${midY} ${props.x1 + r * signX},${midY}`,
    `L ${props.x2 - r * signX},${midY}`,
    `Q ${props.x2},${midY} ${props.x2},${midY + r * signY}`,
    `L ${props.x2},${props.y2}`,
  ].join(' ')
})

const labelPosition = computed(() => {
  const midY = (props.y1 + props.y2) / 2
  const midX = (props.x1 + props.x2) / 2
  return { x: midX, y: midY - 10 }
})

const labelWidth = computed(() => Math.max(36, props.edge.edge_type.length * 5.4 + 8))
const showLabel = computed(() => {
  if (props.zoomScale <= 0.6) return false
  return ['triggers', 'reads_from', 'writes_to'].includes(props.edge.edge_type)
})
</script>

<style scoped>
.graph-edge {
  animation: edge-enter 260ms ease-out both;
  animation-delay: var(--edge-delay);
}

@keyframes edge-enter {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.edge-path,
.flow-dot {
  transition: opacity 200ms ease-out, stroke-width 200ms ease-out;
  pointer-events: none;
}

.flow-dot {
  filter: drop-shadow(0 0 4px color-mix(in srgb, var(--edge-color) 70%, transparent));
}
</style>
