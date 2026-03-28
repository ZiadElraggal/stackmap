<template>
  <g :class="['graph-edge', { dimmed: isDimmed }]" :opacity="isDimmed ? 0.06 : opacity">
    <line
      :x1="x1"
      :y1="y1"
      :x2="x2"
      :y2="y2"
      :stroke="edgeColor"
      :stroke-width="1.5"
      :stroke-dasharray="isDashed ? '6 4' : 'none'"
      marker-end="url(#arrowhead)"
    />
    <title>{{ edge.label }} ({{ edge.edge_type }})</title>
  </g>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useGraphStore, type StackMapEdge } from '~/stores/graph'
import { EDGE_COLORS } from '~/composables/useGraph'

const props = defineProps<{
  edge: StackMapEdge
  x1: number
  y1: number
  x2: number
  y2: number
}>()

const store = useGraphStore()

const edgeColor = computed(() => EDGE_COLORS[props.edge.edge_type] || '#4b5563')
const isDashed = computed(() => props.edge.edge_type === 'references')
const opacity = computed(() => {
  const sel = store.selectedNodeId
  const hov = store.hoveredNodeId
  const active = sel || hov
  if (!active) return 0.5
  if (props.edge.source === active || props.edge.target === active) return 1
  return 0.08
})

const isDimmed = computed(() => {
  const hov = store.hoveredNodeId
  if (!hov) return false
  return props.edge.source !== hov && props.edge.target !== hov
})
</script>

<style scoped>
.graph-edge {
  transition: opacity 0.3s ease;
}
</style>
