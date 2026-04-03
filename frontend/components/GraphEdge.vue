<template>
  <g
    :class="['graph-edge', { dimmed: isDimmed, 'user-link-hover': isUserLink && (isHovered || isControlHovering) && store.editMode }]"
    :style="{
      '--edge-color': edgeColor,
      '--edge-delay': `${entryDelay}ms`,
      opacity: fadingOut ? 0 : undefined,
      transition: fadingOut ? 'opacity 300ms ease-out' : undefined,
    }"
    @mouseenter="onEdgeEnter"
    @mouseleave="onEdgeLeave"
  >
    <!-- Invisible wider hit area for hover detection on edges -->
    <path
      v-if="isUserLink && store.editMode"
      :d="pathD"
      stroke="transparent"
      :stroke-width="Math.max(strokeWidth * 3, 12)"
      fill="none"
      class="edge-hit-area"
    />

    <path
      :d="pathD"
      :stroke="edgeColor"
      :stroke-width="strokeWidth"
      :stroke-dasharray="dashPattern"
      fill="none"
      :opacity="computedOpacity"
      :marker-end="`url(#${markerId})`"
      class="edge-path"
    />

    <circle
      v-if="(edge.edge_type === 'triggers' || isUserLink) && !isDimmed"
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

    <g
      v-if="isUserLink && store.editMode && (isHovered || isControlHovering) && !fadingOut"
      class="edge-color-palette"
      :transform="`translate(${midpoint.x - 34}, ${midpoint.y - 22})`"
      @mouseenter="onControlHoverEnter"
      @mouseleave="onControlHoverLeave"
    >
      <rect x="-10" y="-12" width="92" height="24" fill="rgba(0,0,0,0.001)" />
      <g
        v-for="(color, idx) in userLinkColors"
        :key="color"
        class="edge-color-chip"
        :transform="`translate(${idx * 18}, 0)`"
        @click.stop="onSetEdgeColor(color)"
      >
        <circle r="6" :fill="color" :stroke="edge.color === color ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.22)'" stroke-width="1.5" />
      </g>
    </g>

    <!-- Delete button at midpoint for user_link edges in edit mode -->
    <g
      v-if="isUserLink && store.editMode && (isHovered || isControlHovering) && !fadingOut"
      class="edge-delete-btn"
      :transform="`translate(${midpoint.x}, ${midpoint.y - 46})`"
      @mouseenter="onControlHoverEnter"
      @mouseleave="onControlHoverLeave"
      @click.stop="onDeleteEdge"
    >
      <circle r="10" fill="rgba(239,68,68,0.3)" stroke="rgba(239,68,68,0.75)" stroke-width="1" />
      <path d="M-3.5,-3.5 L3.5,3.5 M3.5,-3.5 L-3.5,3.5" stroke="#ef4444" stroke-width="1.8" stroke-linecap="round" />
    </g>

    <title>{{ edge.label || edge.edge_type }}</title>
  </g>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
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

const isUserLink = computed(() =>
  props.edge.edge_type === 'user_link'
  || props.edge.label === 'user link'
  || props.edge.id.startsWith('user:')
)

const edgeDiffStatus = computed(() => store.edgeDiffStatus[props.edge.id] as string | undefined)
const userLinkColors = ['#4ADE80', '#38BDF8', '#C084FC', '#FB923C', '#F87171']

const edgeColor = computed(() => {
  if (store.diffMode && edgeDiffStatus.value === 'added') return '#22c55e'
  if (store.diffMode && edgeDiffStatus.value === 'removed') return '#ef4444'
  if (isUserLink.value) return props.edge.color || EDGE_COLORS.user_link
  return EDGE_COLORS[props.edge.edge_type] || '#64748b'
})

const markerId = computed(() => {
  if (!isUserLink.value) return `arrow-${props.edge.edge_type}`
  return `arrow-user-${props.edge.id.replace(/[^a-zA-Z0-9_-]/g, '-')}`
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
  if (isUserLink.value) return 0.82
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
    user_link: 1.6,
    routes_to: 1.2,
    references: 1,
    contains: 0.8,
    authenticates: 1.2,
    cross_account_reference: 2.2,
  }
  const lift = isConnectedToHovered.value ? 0.5 : 0
  return (base[props.edge.edge_type] ?? 1.2) + lift
})

const dashPattern = computed(() => {
  if (store.diffMode && edgeDiffStatus.value === 'added') return '6 3'
  if (store.diffMode && edgeDiffStatus.value === 'removed') return '3 4'
  if (isUserLink.value) return 'none'
  if (props.edge.edge_type === 'cross_account_reference') return '8 4'
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
  return ['triggers', 'reads_from', 'writes_to', 'cross_account_reference', 'user_link'].includes(props.edge.edge_type)
})

const midpoint = computed(() => {
  return {
    x: (props.x1 + props.x2) / 2,
    y: (props.y1 + props.y2) / 2,
  }
})

const isHovered = ref(false)
const isControlHovering = ref(false)
const fadingOut = ref(false)
let hoverLeaveTimer: ReturnType<typeof setTimeout> | null = null

function onEdgeEnter() {
  if (isUserLink.value && store.editMode) {
    if (hoverLeaveTimer) {
      clearTimeout(hoverLeaveTimer)
      hoverLeaveTimer = null
    }
    isHovered.value = true
  }
}

function onEdgeLeave() {
  if (hoverLeaveTimer) clearTimeout(hoverLeaveTimer)
  hoverLeaveTimer = setTimeout(() => {
    if (!isControlHovering.value) {
      isHovered.value = false
    }
    hoverLeaveTimer = null
  }, 90)
}

function onControlHoverEnter() {
  if (hoverLeaveTimer) {
    clearTimeout(hoverLeaveTimer)
    hoverLeaveTimer = null
  }
  isControlHovering.value = true
  isHovered.value = true
}

function onControlHoverLeave() {
  isControlHovering.value = false
  if (hoverLeaveTimer) clearTimeout(hoverLeaveTimer)
  hoverLeaveTimer = setTimeout(() => {
    if (!isControlHovering.value) {
      isHovered.value = false
    }
    hoverLeaveTimer = null
  }, 90)
}

function onDeleteEdge() {
  fadingOut.value = true
  setTimeout(() => {
    store.removeUserEdge(props.edge.id)
  }, 300)
}

function onSetEdgeColor(color: string) {
  store.setUserEdgeColor(props.edge.id, color)
}
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
  transition: opacity 200ms ease-out, stroke-width 200ms ease-out, filter 200ms ease-out;
  pointer-events: none;
}

.edge-hit-area {
  pointer-events: stroke;
  cursor: pointer;
}

.user-link-hover .edge-path {
  filter: drop-shadow(0 0 6px color-mix(in srgb, var(--edge-color) 60%, transparent));
  stroke-width: 2.4;
}

.flow-dot {
  filter: drop-shadow(0 0 4px color-mix(in srgb, var(--edge-color) 70%, transparent));
}

.edge-delete-btn,
.edge-color-chip {
  cursor: pointer;
}

.edge-delete-btn {
  cursor: pointer;
  pointer-events: auto;
  animation: edge-delete-appear 150ms ease-out;
}

.edge-delete-btn:hover circle {
  fill: rgba(239, 68, 68, 0.45);
  stroke: rgba(239, 68, 68, 0.9);
}

@keyframes edge-delete-appear {
  from { opacity: 0; transform: scale(0.6); }
  to { opacity: 1; transform: scale(1); }
}
</style>
