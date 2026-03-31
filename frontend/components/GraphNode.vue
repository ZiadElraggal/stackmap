<template>
  <g
    :transform="`translate(${x}, ${y})`"
    :class="['graph-node', prominence, { dimmed: isDimmed, selected: isSelected, entering: !entered }]"
    :style="{
      '--node-color': categoryColor,
      '--entry-delay': `${entryDelay}ms`,
      '--diff-color': diffBorderColor,
    }"
    :opacity="nodeOpacity"
    @click.stop="onClick"
    @mouseenter="onHover"
    @mouseleave="onLeave"
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
      fill="#13131f"
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

    <text
      :x="-nodeWidth / 2 + 16 + iconSize"
      :y="typeFontSize > 0 ? -7 : 0"
      fill="#e5e7eb"
      :font-size="nameFontSize"
      font-weight="500"
      font-family="'JetBrains Mono', 'SF Mono', monospace"
      dominant-baseline="central"
      class="node-name"
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

    <title>{{ node.name }} ({{ node.resource_type }})</title>
  </g>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useGraphStore, type StackMapNode } from '~/stores/graph'
import {
  CATEGORY_COLORS,
  CATEGORY_ICONS,
  formatResourceType,
  getNodeHeight,
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

const store = useGraphStore()
const entered = ref(false)

const categoryColor = computed(() => CATEGORY_COLORS[props.node.category] || '#9ca3af')
const iconPath = computed(() => CATEGORY_ICONS[props.node.category] || CATEGORY_ICONS.other)
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

function onClick() {
  const accountId = props.node.metadata?.account_id || props.node.position_hint?.account_id
  if (store.viewMode === 'organization' && props.node.position_hint?.view_kind === 'account_summary' && accountId) {
    store.enterAccountArchitecture(accountId)
    return
  }
  store.selectNode(isSelected.value ? null : props.node.id)
}
function onHover() {
  store.hoverNode(props.node.id)
}
function onLeave() {
  store.hoverNode(null)
}

onMounted(() => {
  requestAnimationFrame(() => {
    entered.value = true
  })
})
</script>

<style scoped>
.graph-node {
  cursor: pointer;
  transition: opacity 200ms ease-out;
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
  stroke: color-mix(in srgb, var(--node-color) 40%, transparent);
  stroke-width: 2;
  filter: drop-shadow(0 0 16px color-mix(in srgb, var(--node-color) 25%, transparent));
}

.graph-node:hover .accent-bar {
  filter: drop-shadow(0 0 6px var(--node-color));
}

.graph-node.selected .outer-shell {
  stroke: color-mix(in srgb, var(--node-color) 80%, transparent);
  stroke-width: 2;
  filter: drop-shadow(0 0 20px color-mix(in srgb, var(--node-color) 30%, transparent));
}

.diff-glow {
  filter: drop-shadow(0 0 12px color-mix(in srgb, var(--diff-color) 35%, transparent));
}

.graph-node .node-name,
.graph-node .icon,
.graph-node .selection-ring {
  pointer-events: none;
}
</style>
