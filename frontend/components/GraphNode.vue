<template>
  <g
    :transform="`translate(${x}, ${y})`"
    :class="['graph-node', { dimmed: isDimmed, selected: isSelected }]"
    :opacity="isDimmed ? 0.15 : 1"
    @click.stop="onClick"
    @mouseenter="onHover"
    @mouseleave="onLeave"
    style="cursor: pointer"
  >
    <!-- Node background -->
    <rect
      :width="nodeWidth"
      :height="nodeHeight"
      :x="-nodeWidth / 2"
      :y="-nodeHeight / 2"
      :rx="8"
      :ry="8"
      :fill="bgColor"
      :stroke="isSelected ? categoryColor : 'rgba(255,255,255,0.08)'"
      :stroke-width="isSelected ? 2.5 : 1"
      class="node-rect"
    />

    <!-- Selection glow -->
    <rect
      v-if="isSelected"
      :width="nodeWidth + 6"
      :height="nodeHeight + 6"
      :x="-(nodeWidth + 6) / 2"
      :y="-(nodeHeight + 6) / 2"
      :rx="10"
      :ry="10"
      fill="none"
      :stroke="categoryColor"
      stroke-width="1"
      opacity="0.4"
    />

    <!-- Category icon -->
    <text
      :x="-nodeWidth / 2 + 14"
      y="1"
      :fill="categoryColor"
      font-size="14"
      text-anchor="middle"
      dominant-baseline="central"
    >{{ icon }}</text>

    <!-- Node name -->
    <text
      :x="-nodeWidth / 2 + 28"
      y="-3"
      fill="#e5e7eb"
      font-size="11"
      font-family="'JetBrains Mono', 'SF Mono', monospace"
      dominant-baseline="central"
    >{{ displayName }}</text>

    <!-- Resource type subtitle -->
    <text
      :x="-nodeWidth / 2 + 28"
      y="12"
      fill="#6b7280"
      font-size="9"
      font-family="'JetBrains Mono', 'SF Mono', monospace"
      dominant-baseline="central"
    >{{ shortType }}</text>

    <title>{{ node.name }} ({{ node.resource_type }})</title>
  </g>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useGraphStore, type StackMapNode } from '~/stores/graph'
import { CATEGORY_COLORS, CATEGORY_ICONS, truncate } from '~/composables/useGraph'

const props = defineProps<{
  node: StackMapNode
  x: number
  y: number
}>()

const store = useGraphStore()

const categoryColor = computed(() => CATEGORY_COLORS[props.node.category] || '#9ca3af')
const bgColor = computed(() => '#1a1a2e')
const icon = computed(() => CATEGORY_ICONS[props.node.category] || '○')
const displayName = computed(() => truncate(props.node.name, 20))
const shortType = computed(() => {
  const t = props.node.resource_type
  return t.replace('aws_', '').replace(/_/g, ' ')
})

const nodeWidth = computed(() => {
  const w = props.node.position_hint?.weight || 2
  return Math.max(140, 120 + w * 8)
})
const nodeHeight = computed(() => 36)

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
</script>

<style scoped>
.graph-node {
  transition: opacity 0.3s ease;
}
.node-rect {
  transition: stroke 0.2s ease, stroke-width 0.2s ease;
}
.graph-node:hover .node-rect {
  filter: brightness(1.2);
}
</style>
