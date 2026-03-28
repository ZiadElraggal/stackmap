<template>
  <g v-if="bounds" class="group-boundary">
    <rect
      :x="bounds.x"
      :y="bounds.y - 20"
      :width="bounds.width"
      :height="bounds.height + 20"
      :rx="12"
      :ry="12"
      fill="rgba(255,255,255,0.02)"
      stroke="rgba(255,255,255,0.08)"
      stroke-width="1"
      stroke-dasharray="8 4"
    />
    <text
      :x="bounds.x + 10"
      :y="bounds.y - 6"
      fill="#6b7280"
      font-size="10"
      font-family="'JetBrains Mono', 'SF Mono', monospace"
    >{{ group.group_type.toUpperCase() }}: {{ group.name }}</text>
  </g>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { StackMapGroup, NodePosition } from '~/stores/graph'
import { useLayout } from '~/composables/useLayout'

const props = defineProps<{
  group: StackMapGroup
  positions: Record<string, NodePosition>
}>()

const { computeGroupBounds } = useLayout()

const bounds = computed(() => computeGroupBounds(props.group, props.positions))
</script>
