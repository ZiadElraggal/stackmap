<template>
  <g
    :transform="`translate(${x}, ${y})`"
    :class="['graph-node', { dimmed: isDimmed, selected: isSelected, entering: !entered }]"
    :style="{
      '--node-color': categoryColor,
      '--entry-delay': `${entryDelay}ms`,
    }"
    :opacity="isDimmed ? 0.12 : 1"
    @click.stop="onClick"
    @mouseenter="onHover"
    @mouseleave="onLeave"
  >
    <rect
      :width="nodeWidth"
      :height="nodeHeight"
      :x="-nodeWidth / 2"
      :y="-nodeHeight / 2"
      :rx="12"
      :ry="12"
      :fill="`${categoryColor}0F`"
      stroke="rgba(255,255,255,0.06)"
      stroke-width="1"
      class="outer-shell"
    />

    <rect
      :width="nodeWidth - 8"
      :height="nodeHeight - 8"
      :x="-(nodeWidth - 8) / 2 + 4"
      :y="-(nodeHeight - 8) / 2 + 4"
      :rx="10"
      :ry="10"
      fill="#13131f"
      class="inner-shell"
    />

    <rect
      :width="3"
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
      :x="-nodeWidth / 2 + 13"
      :y="-9"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      :style="{ color: categoryColor }"
      class="icon"
    >
      <g v-html="iconPath" />
    </svg>

    <text
      :x="-nodeWidth / 2 + 40"
      y="-4"
      fill="#e5e7eb"
      font-size="12"
      font-weight="500"
      font-family="'JetBrains Mono', 'SF Mono', monospace"
      dominant-baseline="central"
      class="node-name"
    >{{ displayName }}</text>

    <text
      :x="-nodeWidth / 2 + 40"
      y="13"
      fill="#6b7280"
      font-size="10"
      font-weight="400"
      font-family="'JetBrains Mono', 'SF Mono', monospace"
      dominant-baseline="central"
    >{{ shortType }}</text>

    <title>{{ node.name }} ({{ node.resource_type }})</title>
  </g>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useGraphStore, type StackMapNode } from '~/stores/graph'
import { CATEGORY_COLORS, CATEGORY_ICONS, formatResourceType, truncate } from '~/composables/useGraph'

const props = withDefaults(
  defineProps<{
    node: StackMapNode
    x: number
    y: number
    entryDelay?: number
  }>(),
  {
    entryDelay: 0,
  }
)

const store = useGraphStore()
const entered = ref(false)

const categoryColor = computed(() => CATEGORY_COLORS[props.node.category] || '#9ca3af')
const iconPath = computed(() => CATEGORY_ICONS[props.node.category] || CATEGORY_ICONS.other)
const displayName = computed(() => truncate(props.node.name, 24))
const shortType = computed(() => formatResourceType(props.node.resource_type))

const nodeWidth = computed(() => Math.max(180, Math.min(260, props.node.name.length * 8 + 70)))
const nodeHeight = computed(() => 52)

const isSelected = computed(() => store.selectedNodeId === props.node.id)
const isDimmed = computed(() => {
  const hovered = store.hoveredNodeId
  if (!hovered) return false
  if (hovered === props.node.id) return false
  const connected = store.connectedNodeIds(hovered)
  return !connected.has(props.node.id)
})

function onClick() {
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
  stroke: color-mix(in srgb, var(--node-color) 30%, transparent);
  filter: drop-shadow(0 0 12px color-mix(in srgb, var(--node-color) 20%, transparent));
}

.graph-node.selected .outer-shell {
  stroke: color-mix(in srgb, var(--node-color) 80%, transparent);
  stroke-width: 2;
}

.graph-node .node-name,
.graph-node .icon,
.graph-node .selection-ring {
  pointer-events: none;
}
</style>
