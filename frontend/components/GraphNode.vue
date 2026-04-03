<template>
  <!-- ── Account summary card (org view) ─────────────────────────────── -->
  <g
    v-if="isAccountSummary"
    :transform="`translate(${x}, ${y})`"
    class="graph-node"
    :opacity="nodeOpacity"
    @click.stop="onClick"
    @mouseenter="onHover"
    @mouseleave="onLeave"
  >
      <!-- Selection / hover ring -->
      <rect
        :width="nodeWidth + 12" :height="nodeHeight + 12"
        :x="-(nodeWidth + 12) / 2" :y="-(nodeHeight + 12) / 2"
        rx="16" ry="16" fill="none" stroke="#22d3ee" stroke-width="1.5"
        :opacity="isSelected ? 0.35 : 0"
        class="outer-shell"
      />

      <!-- Card border -->
      <rect
        :width="nodeWidth" :height="nodeHeight"
        :x="-nodeWidth / 2" :y="-nodeHeight / 2"
        rx="12" ry="12"
        fill="rgba(34,211,238,0.05)"
        :stroke="isSelected ? 'rgba(34,211,238,0.55)' : (isScanned ? 'rgba(34,211,238,0.20)' : 'rgba(100,116,139,0.20)')"
        stroke-width="1.5"
        class="outer-shell"
      />

      <!-- Inner background -->
      <rect
        :width="nodeWidth - 8" :height="nodeHeight - 8"
        :x="-(nodeWidth - 8) / 2" :y="-(nodeHeight - 8) / 2"
        rx="10" ry="10"
        fill="#0c0c18"
      />

      <!-- Left accent bar -->
      <rect
        :x="-nodeWidth / 2 + 4"
        :y="-(nodeHeight - 16) / 2"
        width="4"
        :height="nodeHeight - 16"
        rx="2" ry="2"
        :fill="isScanned ? '#22d3ee' : '#475569'"
        opacity="0.65"
      />

      <!-- Account name -->
      <text
        :x="-nodeWidth / 2 + 16"
        y="-24"
        fill="#e2e8f0"
        font-size="11.5"
        font-weight="600"
        font-family="'JetBrains Mono', 'SF Mono', monospace"
        dominant-baseline="central"
        class="node-name"
      >{{ truncate(node.name, 20) }}</text>

      <!-- Resource count (top-right) -->
      <text
        :x="nodeWidth / 2 - 10"
        y="-24"
        fill="rgba(148,163,184,0.55)"
        font-size="8.5"
        font-family="'JetBrains Mono', 'SF Mono', monospace"
        dominant-baseline="central"
        text-anchor="end"
      >{{ resourceCount }} res</text>

      <!-- Account ID + region -->
      <text
        :x="-nodeWidth / 2 + 16"
        y="-12"
        fill="rgba(100,116,139,0.8)"
        font-size="8.5"
        font-family="'JetBrains Mono', 'SF Mono', monospace"
        dominant-baseline="central"
      >{{ accountId }}{{ regions ? '  ·  ' + regions : '' }}</text>

      <!-- Separator -->
      <line
        :x1="-nodeWidth / 2 + 16" y1="-5"
        :x2="nodeWidth / 2 - 10" y2="-5"
        stroke="rgba(255,255,255,0.04)" stroke-width="1"
      />

      <!-- Category dots row -->
      <g v-for="(cat, catIdx) in topCategories" :key="cat[0]">
        <circle
          :cx="-nodeWidth / 2 + 16 + catIdx * 32"
          cy="6"
          r="3.5"
          :fill="CATEGORY_COLORS[cat[0]] || '#6b7280'"
          opacity="0.85"
        />
        <text
          :x="-nodeWidth / 2 + 16 + catIdx * 32 + 8"
          y="6"
          fill="rgba(148,163,184,0.6)"
          font-size="8.5"
          font-family="'JetBrains Mono', 'SF Mono', monospace"
          dominant-baseline="central"
        >{{ cat[1] }}</text>
      </g>

      <!-- OU path (abbreviated) -->
      <text
        :x="-nodeWidth / 2 + 16"
        y="22"
        fill="rgba(71,85,105,0.9)"
        font-size="8"
        font-family="'JetBrains Mono', 'SF Mono', monospace"
        dominant-baseline="central"
      >{{ ouPathShort }}</text>

      <!-- Drill-in arrow -->
      <text
        :x="nodeWidth / 2 - 10"
        y="6"
        fill="rgba(100,116,139,0.5)"
        font-size="14"
        font-family="sans-serif"
        dominant-baseline="central"
        text-anchor="middle"
      >›</text>

      <!-- Unscanned badge -->
      <g v-if="!isScanned">
        <rect
          :x="nodeWidth / 2 - 72" :y="-nodeHeight / 2 + 8"
          width="62" height="12"
          rx="3" ry="3"
          fill="rgba(71,85,105,0.25)"
          stroke="rgba(71,85,105,0.3)" stroke-width="1"
        />
        <text
          :x="nodeWidth / 2 - 41" :y="-nodeHeight / 2 + 14"
          text-anchor="middle" dominant-baseline="central"
          fill="rgba(148,163,184,0.7)" font-size="7.5"
          font-family="'JetBrains Mono', monospace"
        >UNSCANNED</text>
      </g>

      <!-- Selection ring -->
      <rect
        v-if="isSelected"
        :width="nodeWidth + 8" :height="nodeHeight + 8"
        :x="-(nodeWidth + 8) / 2" :y="-(nodeHeight + 8) / 2"
        rx="16" ry="16" fill="none"
        stroke="#22d3ee" stroke-width="1.5" opacity="0.3"
        class="selection-ring"
      />

      <title>{{ node.name }} ({{ accountId }})</title>
  </g>
  <!-- ── END account summary card / Standard node ────────────────────── -->
  <g
    v-else
    :transform="`translate(${x}, ${y})`"
    :class="['graph-node', prominence, { dimmed: isDimmed, selected: isSelected, entering: !entered }]"
    :style="{
      '--node-color': categoryColor,
      '--entry-delay': `${entryDelay}ms`,
      '--diff-color': diffBorderColor,
    }"
    :opacity="nodeOpacity"
    :data-node-id="node.id"
    :data-drag-enabled="store.editMode && !isAccountSummary && !store.connectingFromNodeId ? 'true' : 'false'"
    @click.stop="onClick"
    @mouseenter="onHover"
    @mouseleave="onLeave"
    @pointerdown.prevent.stop="onPointerDown"
  >
    <rect
      v-if="diffStatus && diffStatus !== 'unchanged'"
      :width="nodeWidth + 16"
      :height="nodeHeight + 16"
      :x="-(nodeWidth + 16) / 2"
      :y="-(nodeHeight + 16) / 2"
      :rx="18"
      :ry="18"
      fill="none"
      :stroke="diffBorderColor"
      stroke-width="1.5"
      :opacity="0.45"
      class="diff-glow"
    />
    <rect
      :width="nodeWidth"
      :height="nodeHeight"
      :x="-nodeWidth / 2"
      :y="-nodeHeight / 2"
      :rx="12"
      :ry="12"
      :fill="`${categoryColor}0F`"
      :stroke="diffStatus && diffStatus !== 'unchanged' ? diffBorderColor : 'rgba(255,255,255,0.06)'"
      :stroke-width="diffStatus && diffStatus !== 'unchanged' ? 1.5 : 1"
      class="outer-shell"
    />

    <rect
      :width="nodeWidth - 8"
      :height="nodeHeight - 8"
      :x="-(nodeWidth - 8) / 2"
      :y="-(nodeHeight - 8) / 2"
      :rx="10"
      :ry="10"
      fill="#0d0d14"
      class="inner-shell"
    />

    <rect
      :width="accentBarWidth"
      :height="nodeHeight - 10"
      :x="-nodeWidth / 2 + 5"
      :y="-nodeHeight / 2 + 5"
      :rx="2"
      :ry="2"
      :fill="categoryColor"
      class="accent-bar"
    />

    <rect
      v-if="isSelected"
      :width="nodeWidth + 8"
      :height="nodeHeight + 8"
      :x="-(nodeWidth + 8) / 2"
      :y="-(nodeHeight + 8) / 2"
      :rx="16"
      :ry="16"
      fill="none"
      :stroke="categoryColor"
      stroke-width="1.5"
      opacity="0.25"
      class="selection-ring"
    />

    <svg
      :x="-nodeWidth / 2 + 10"
      :y="-iconSize / 2"
      :width="iconSize"
      :height="iconSize"
      viewBox="0 0 24 24"
      :style="{ color: categoryColor }"
      class="icon"
    >
      <g v-html="iconPath" />
    </svg>

    <!-- Editable label (inline edit on double-click for user nodes) -->
    <foreignObject
      v-if="isEditingLabel"
      :x="-nodeWidth / 2 + 14 + iconSize"
      :y="typeFontSize > 0 ? -18 : -11"
      :width="nodeWidth - 20 - iconSize"
      height="22"
    >
      <input
        ref="labelInputRef"
        :value="editLabelValue"
        class="inline-label-input"
        :style="{
          fontSize: `${nameFontSize}px`,
          fontFamily: `'JetBrains Mono', 'SF Mono', monospace`,
          fontWeight: 500,
        }"
        @input="editLabelValue = ($event.target as HTMLInputElement).value"
        @keydown.enter="confirmLabelEdit"
        @keydown.escape="cancelLabelEdit"
        @blur="confirmLabelEdit"
      />
    </foreignObject>
    <text
      v-else
      :x="-nodeWidth / 2 + 16 + iconSize"
      :y="typeFontSize > 0 ? -7 : 0"
      fill="#e5e7eb"
      :font-size="nameFontSize"
      font-weight="500"
      font-family="'JetBrains Mono', 'SF Mono', monospace"
      dominant-baseline="central"
      class="node-name"
      @dblclick.stop="onDoubleClickLabel"
    >{{ displayName }}</text>

    <text
      v-if="typeFontSize > 0"
      :x="-nodeWidth / 2 + 16 + iconSize"
      y="11"
      fill="#6b7280"
      :font-size="typeFontSize"
      font-weight="400"
      font-family="'JetBrains Mono', 'SF Mono', monospace"
      dominant-baseline="central"
    >{{ shortType }}</text>

    <g v-if="diffStatus && diffStatus !== 'unchanged'">
      <rect
        :x="nodeWidth / 2 - 16"
        :y="-nodeHeight / 2 - 2"
        width="14"
        height="14"
        rx="3"
        ry="3"
        :fill="diffBorderColor"
        fill-opacity="0.9"
      />
      <text
        :x="nodeWidth / 2 - 9"
        :y="-nodeHeight / 2 + 8"
        text-anchor="middle"
        fill="#fff"
        font-size="9"
        font-weight="700"
        font-family="'JetBrains Mono', monospace"
      >{{ diffBadge }}</text>
    </g>

    <!-- Edit mode action buttons -->
    <g v-if="store.editMode && !isAccountSummary" class="edit-actions" :opacity="isHovered || showDeleteConfirm ? 1 : 0">
      <!-- Hide button -->
      <g
        class="edit-action-btn"
        :transform="`translate(${nodeWidth / 2 - 8}, ${-nodeHeight / 2 - 14})`"
        @click.stop="store.hideNode(node.id)"
      >
        <rect x="-10" y="-8" width="20" height="16" rx="4" fill="rgba(239,68,68,0.2)" stroke="rgba(239,68,68,0.4)" stroke-width="1"/>
        <text x="0" y="1" text-anchor="middle" dominant-baseline="central" fill="#ef4444" font-size="9" font-family="'JetBrains Mono', monospace">H</text>
      </g>
      <!-- Connect button -->
      <g
        class="edit-action-btn"
        :transform="`translate(${nodeWidth / 2 - 32}, ${-nodeHeight / 2 - 14})`"
        @click.stop="onConnectClick"
      >
        <rect x="-10" y="-8" width="20" height="16" rx="4" fill="rgba(74,222,128,0.2)" stroke="rgba(74,222,128,0.4)" stroke-width="1"/>
        <text x="0" y="1" text-anchor="middle" dominant-baseline="central" fill="#4ADE80" font-size="9" font-family="'JetBrains Mono', monospace">C</text>
      </g>
      <!-- Duplicate button (user nodes only) -->
      <g
        v-if="node.tags?._user_created"
        class="edit-action-btn"
        :transform="`translate(${nodeWidth / 2 - 56}, ${-nodeHeight / 2 - 14})`"
        @click.stop="store.duplicateUserNode(node.id)"
      >
        <rect x="-10" y="-8" width="20" height="16" rx="4" fill="rgba(56,189,248,0.2)" stroke="rgba(56,189,248,0.4)" stroke-width="1"/>
        <text x="0" y="1" text-anchor="middle" dominant-baseline="central" fill="#38BDF8" font-size="9" font-family="'JetBrains Mono', monospace">D</text>
      </g>
      <!-- Delete button (user nodes only) — with inline confirmation -->
      <g
        v-if="node.tags?._user_created && !showDeleteConfirm"
        class="edit-action-btn"
        :transform="`translate(${nodeWidth / 2 + 16}, ${-nodeHeight / 2 - 14})`"
        @click.stop="requestDelete"
      >
        <rect x="-10" y="-8" width="20" height="16" rx="4" fill="rgba(239,68,68,0.3)" stroke="rgba(239,68,68,0.5)" stroke-width="1"/>
        <text x="0" y="1" text-anchor="middle" dominant-baseline="central" fill="#ef4444" font-size="10" font-weight="bold" font-family="'JetBrains Mono', monospace">×</text>
      </g>
    </g>

    <!-- Inline delete confirmation -->
    <g v-if="showDeleteConfirm" class="delete-confirm">
      <rect
        :x="-60"
        :y="nodeHeight / 2 + 6"
        width="120"
        height="24"
        rx="6"
        fill="rgba(239,68,68,0.15)"
        stroke="rgba(239,68,68,0.4)"
        stroke-width="1"
      />
      <text
        x="-30"
        :y="nodeHeight / 2 + 18"
        text-anchor="middle"
        dominant-baseline="central"
        fill="rgba(239,68,68,0.8)"
        font-size="8"
        font-family="'JetBrains Mono', monospace"
      >Delete?</text>
      <g class="edit-action-btn" @click.stop="confirmDelete">
        <rect :x="8" :y="nodeHeight / 2 + 10" width="22" height="16" rx="4" fill="rgba(239,68,68,0.3)" stroke="rgba(239,68,68,0.6)" stroke-width="1"/>
        <text :x="19" :y="nodeHeight / 2 + 18" text-anchor="middle" dominant-baseline="central" fill="#ef4444" font-size="9" font-weight="bold" font-family="'JetBrains Mono', monospace">✓</text>
      </g>
      <g class="edit-action-btn" @click.stop="cancelDelete">
        <rect :x="34" :y="nodeHeight / 2 + 10" width="22" height="16" rx="4" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.15)" stroke-width="1"/>
        <text :x="45" :y="nodeHeight / 2 + 18" text-anchor="middle" dominant-baseline="central" fill="#9ca3af" font-size="9" font-family="'JetBrains Mono', monospace">✗</text>
      </g>
    </g>

    <!-- Connecting-from indicator ring -->
    <rect
      v-if="store.connectingFromNodeId === node.id"
      :width="nodeWidth + 12"
      :height="nodeHeight + 12"
      :x="-(nodeWidth + 12) / 2"
      :y="-(nodeHeight + 12) / 2"
      rx="16" ry="16"
      fill="none"
      stroke="#4ADE80"
      stroke-width="2"
      stroke-dasharray="4 3"
      opacity="0.7"
      class="connecting-ring"
    />

    <!-- Connect-target pulse (when another node is connecting) -->
    <rect
      v-if="store.connectingFromNodeId && store.connectingFromNodeId !== node.id"
      :width="nodeWidth + 6"
      :height="nodeHeight + 6"
      :x="-(nodeWidth + 6) / 2"
      :y="-(nodeHeight + 6) / 2"
      rx="14" ry="14"
      fill="none"
      stroke="#4ADE80"
      stroke-width="1"
      opacity="0.25"
      class="connect-target-ring"
    />

    <title>{{ node.name }} ({{ node.resource_type }})</title>
  </g>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useGraphStore, type StackMapNode } from '~/stores/graph'
import {
  CATEGORY_COLORS,
  formatResourceType,
  getNodeHeight,
  getNodeIconPath,
  getNodeProminence,
  getNodeWidth,
  truncate,
} from '~/composables/useGraph'

const props = withDefaults(
  defineProps<{
    node: StackMapNode
    x: number
    y: number
    entryDelay?: number
    zoomScale?: number
  }>(),
  {
    entryDelay: 0,
    zoomScale: 1,
  }
)

const emit = defineEmits<{
  dragNodeStart: [payload: { nodeId: string; clientX: number; clientY: number }]
  dragNodeMove: [payload: { nodeId: string; clientX: number; clientY: number }]
  dragNodeEnd: [payload: { nodeId: string; clientX: number; clientY: number }]
}>()

const store = useGraphStore()
const entered = ref(false)
const activePointerId = ref<number | null>(null)
const pointerStart = ref<{ x: number; y: number } | null>(null)
const dragStarted = ref(false)
const suppressClickOnce = ref(false)
const pointerOwner = ref<Element | null>(null)

// Inline label editing state
const isEditingLabel = ref(false)
const editLabelValue = ref('')
const labelInputRef = ref<HTMLInputElement | null>(null)

// Delete confirmation state
const showDeleteConfirm = ref(false)
let deleteConfirmTimer: ReturnType<typeof setTimeout> | null = null

const categoryColor = computed(() => CATEGORY_COLORS[props.node.category] || '#9ca3af')
const iconPath = computed(() => getNodeIconPath(props.node))
const displayName = computed(() => truncate(props.node.name, 28))
const shortType = computed(() => formatResourceType(props.node.resource_type))

const prominence = computed(() => getNodeProminence(props.node))
const nodeWidth = computed(() => getNodeWidth(props.node))
const nodeHeight = computed(() => getNodeHeight(props.node))
const diffStatus = computed(() => props.node.position_hint?.diff_status as string | undefined)

const diffBorderColor = computed(() => {
  switch (diffStatus.value) {
    case 'added':
      return '#22c55e'
    case 'removed':
      return '#ef4444'
    case 'modified':
      return '#f59e0b'
    default:
      return 'transparent'
  }
})

const diffBadge = computed(() => {
  switch (diffStatus.value) {
    case 'added':
      return '+'
    case 'removed':
      return '−'
    case 'modified':
      return '~'
    default:
      return ''
  }
})

const nameFontSize = computed(() => {
  if (prominence.value === 'primary') return 13
  if (prominence.value === 'secondary') return 11
  return 9.5
})

const typeFontSize = computed(() => {
  if (prominence.value === 'primary') return 10
  if (prominence.value === 'secondary') return 8.5
  return 0
})

const iconSize = computed(() => {
  if (prominence.value === 'primary') return 20
  if (prominence.value === 'secondary') return 16
  return 13
})

const accentBarWidth = computed(() => {
  if (prominence.value === 'primary') return 4
  if (prominence.value === 'secondary') return 3
  return 2
})

// ── Account summary card (org view) ───────────────────────────────────────
const isAccountSummary = computed(() => props.node.position_hint?.view_kind === 'account_summary')
const accountId = computed(() => String(props.node.properties?.account_id || props.node.metadata?.account_id || ''))
const resourceCount = computed(() => Number(props.node.properties?.resource_count || 0))
const isScanned = computed(() => props.node.properties?.scanned !== false)
const topCategories = computed(() => {
  const counts = (props.node.properties?.category_counts as Record<string, number>) || {}
  return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 5)
})
const regions = computed(() => {
  const r = (props.node.properties?.regions as string[]) || []
  return r.slice(0, 1).join(', ')
})
const ouPathShort = computed(() => {
  const raw = String(props.node.properties?.ou_path || props.node.position_hint?.org_path || '')
  const parts = raw.split('/').filter(Boolean)
  return parts.length > 1 ? parts.slice(1).join(' / ') : raw
})
// ─────────────────────────────────────────────────────────────────────────

const isSelected = computed(() => store.selectedNodeId === props.node.id)
const isDimmed = computed(() => {
  const hovered = store.hoveredNodeId
  if (!hovered) return false
  if (hovered === props.node.id) return false
  const connected = store.connectedNodeIds(hovered)
  return !connected.has(props.node.id)
})

const nodeOpacity = computed(() => {
  if (store.diffMode && diffStatus.value) {
    if (diffStatus.value === 'removed') {
      const base = Math.max(0, (0.5 - store.diffSlider) * 2)
      return isDimmed.value ? base * 0.12 : Math.max(0.2, base)
    }
    if (diffStatus.value === 'added') {
      const base = Math.max(0, (store.diffSlider - 0.5) * 2)
      return isDimmed.value ? base * 0.12 : Math.max(0.2, base)
    }
    if (diffStatus.value === 'unchanged' && store.showOnlyChanges) {
      return isDimmed.value ? 0.06 : 0.2
    }
  }
  return isDimmed.value ? 0.12 : 1
})

const isHovered = computed(() => store.hoveredNodeId === props.node.id)

function onClick() {
  if (suppressClickOnce.value) {
    suppressClickOnce.value = false
    return
  }
  // Edit mode: handle connecting
  if (store.editMode && store.connectingFromNodeId) {
    store.completeConnection(props.node.id)
    return
  }

  const accountId = props.node.metadata?.account_id || props.node.position_hint?.account_id
  if (store.viewMode === 'organization' && props.node.position_hint?.view_kind === 'account_summary' && accountId) {
    store.enterAccountArchitecture(accountId)
    return
  }
  store.selectNode(isSelected.value ? null : props.node.id)
}

function onConnectClick() {
  store.startConnecting(props.node.id)
}

function onHover() {
  store.hoverNode(props.node.id)
}
function onLeave() {
  store.hoverNode(null)
}

// ── Label editing ─────────────────────────────────────────────────
function onDoubleClickLabel() {
  if (!store.editMode || !props.node.tags?._user_created) return
  isEditingLabel.value = true
  editLabelValue.value = props.node.name
  nextTick(() => {
    labelInputRef.value?.focus()
    labelInputRef.value?.select()
  })
}

function confirmLabelEdit() {
  if (!isEditingLabel.value) return
  const trimmed = editLabelValue.value.trim()
  if (trimmed && trimmed !== props.node.name) {
    store.renameUserNode(props.node.id, trimmed)
  }
  isEditingLabel.value = false
}

function cancelLabelEdit() {
  isEditingLabel.value = false
}

// ── Delete confirmation ───────────────────────────────────────────
function requestDelete() {
  showDeleteConfirm.value = true
  // Auto-dismiss after 3 seconds
  if (deleteConfirmTimer) clearTimeout(deleteConfirmTimer)
  deleteConfirmTimer = setTimeout(() => {
    showDeleteConfirm.value = false
  }, 3000)
}

function confirmDelete() {
  if (deleteConfirmTimer) clearTimeout(deleteConfirmTimer)
  showDeleteConfirm.value = false
  store.removeUserNode(props.node.id)
}

function cancelDelete() {
  if (deleteConfirmTimer) clearTimeout(deleteConfirmTimer)
  showDeleteConfirm.value = false
}

function onPointerDown(event: PointerEvent) {
  if (!store.editMode || isAccountSummary.value || store.connectingFromNodeId) return
  if (event.button !== 0) return
  activePointerId.value = event.pointerId
  pointerStart.value = { x: event.clientX, y: event.clientY }
  dragStarted.value = false
  pointerOwner.value = event.currentTarget as Element | null
  pointerOwner.value?.setPointerCapture?.(event.pointerId)
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('pointercancel', onPointerCancel)
}

function onPointerMove(event: PointerEvent) {
  if (activePointerId.value !== event.pointerId) return
  const start = pointerStart.value
  if (!start) return
  const dx = event.clientX - start.x
  const dy = event.clientY - start.y
  if (!dragStarted.value && Math.hypot(dx, dy) < 6) return
  if (!dragStarted.value) {
    dragStarted.value = true
    emit('dragNodeStart', {
      nodeId: props.node.id,
      clientX: start.x,
      clientY: start.y,
    })
  }
  emit('dragNodeMove', {
    nodeId: props.node.id,
    clientX: event.clientX,
    clientY: event.clientY,
  })
}

function onPointerUp(event: PointerEvent) {
  if (activePointerId.value !== event.pointerId) return
  if (dragStarted.value) {
    suppressClickOnce.value = true
    emit('dragNodeEnd', {
      nodeId: props.node.id,
      clientX: event.clientX,
      clientY: event.clientY,
    })
  }
  cleanupPointerListeners()
}

function onPointerCancel() {
  cleanupPointerListeners()
}

function cleanupPointerListeners() {
  if (pointerOwner.value && activePointerId.value !== null) {
    pointerOwner.value.releasePointerCapture?.(activePointerId.value)
  }
  pointerOwner.value = null
  activePointerId.value = null
  pointerStart.value = null
  dragStarted.value = false
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerCancel)
}

onMounted(() => {
  requestAnimationFrame(() => {
    entered.value = true
  })
})

onUnmounted(() => {
  cleanupPointerListeners()
  if (deleteConfirmTimer) clearTimeout(deleteConfirmTimer)
})
</script>

<style scoped>
.graph-node {
  cursor: pointer;
  transition: opacity 200ms ease-out;
}

.graph-node[data-drag-enabled='true'] {
  touch-action: none;
}

.graph-node.entering {
  opacity: 0;
  animation: node-enter 300ms ease-out forwards;
  animation-delay: var(--entry-delay);
}

@keyframes node-enter {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.outer-shell,
.inner-shell,
.accent-bar,
.selection-ring {
  transition: all 200ms ease-out;
}

.graph-node:hover .outer-shell {
  stroke: color-mix(in srgb, var(--node-color) 35%, transparent);
  stroke-width: 1.5;
  filter: drop-shadow(0 0 12px color-mix(in srgb, var(--node-color) 18%, transparent));
}

.graph-node:hover .inner-shell {
  fill: #0e0e16;
}

.graph-node:hover .accent-bar {
  filter: drop-shadow(0 0 5px color-mix(in srgb, var(--node-color) 50%, transparent));
}

.graph-node.selected .outer-shell {
  stroke: color-mix(in srgb, var(--node-color) 60%, transparent);
  stroke-width: 1.8;
  filter: drop-shadow(0 0 16px color-mix(in srgb, var(--node-color) 22%, transparent));
}

.graph-node.selected .inner-shell {
  fill: #0f0f18;
}

.diff-glow {
  filter: drop-shadow(0 0 12px color-mix(in srgb, var(--diff-color) 35%, transparent));
}

.graph-node .node-name,
.graph-node .icon,
.graph-node .selection-ring {
  pointer-events: none;
}

.edit-actions {
  transition: opacity 150ms ease;
  pointer-events: auto;
}

.edit-action-btn {
  cursor: pointer;
  transition: transform 120ms ease;
}

.edit-action-btn:hover {
  transform: scale(1.15);
}

@keyframes connecting-dash {
  to { stroke-dashoffset: -14; }
}

.connecting-ring {
  animation: connecting-dash 0.6s linear infinite;
}

@keyframes connect-pulse {
  0%, 100% { opacity: 0.15; }
  50% { opacity: 0.4; }
}

.connect-target-ring {
  animation: connect-pulse 1.2s ease-in-out infinite;
}

.inline-label-input {
  width: 100%;
  background: rgba(13, 13, 20, 0.95);
  border: 1px solid rgba(74, 222, 128, 0.4);
  border-radius: 4px;
  color: #e5e7eb;
  padding: 1px 4px;
  outline: none;
  line-height: 1.4;
  box-sizing: border-box;
}

.inline-label-input:focus {
  border-color: rgba(74, 222, 128, 0.7);
  box-shadow: 0 0 8px rgba(74, 222, 128, 0.15);
}

.delete-confirm {
  animation: confirm-appear 150ms ease-out;
  pointer-events: auto;
}

@keyframes confirm-appear {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
