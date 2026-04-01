<template>
  <g v-if="bounds" class="group-boundary" :style="{ '--group-color': groupColor }">
    <rect
      :x="bounds.x"
      :y="bounds.y - 28"
      :width="bounds.width"
      :height="bounds.height + 28"
      :rx="16"
      :ry="16"
      :fill="fillColor"
      :stroke="strokeColor"
      stroke-width="1.5"
      :stroke-dasharray="dashPattern"
    />

    <rect
      :x="bounds.x + 1"
      :y="bounds.y - 27"
      :width="bounds.width - 2"
      height="28"
      rx="12"
      ry="12"
      fill="rgba(18,18,26,0.6)"
    />

    <svg
      :x="bounds.x + 10"
      :y="bounds.y - 20"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      :style="{ color: groupColor }"
    >
      <g v-html="iconPath" />
    </svg>

    <text
      :x="bounds.x + 30"
      :y="group.group_type === 'account' && group.metadata?.account_id ? bounds.y - 15 : bounds.y - 10"
      fill="#94a3b8"
      font-size="10"
      font-family="'JetBrains Mono', 'SF Mono', monospace"
    >{{ group.group_type.toUpperCase() }} · {{ group.name }}</text>

    <text
      v-if="group.group_type === 'account' && group.metadata?.account_id"
      :x="bounds.x + 30"
      :y="bounds.y - 4"
      fill="#475569"
      font-size="8"
      font-family="'JetBrains Mono', 'SF Mono', monospace"
    >{{ group.metadata.account_id }}</text>
  </g>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { StackMapGroup, NodePosition } from '~/stores/graph'
import { CATEGORY_COLORS, CATEGORY_ICONS } from '~/composables/useGraph'
import { useLayout } from '~/composables/useLayout'

const props = defineProps<{
  group: StackMapGroup
  positions: Record<string, NodePosition>
}>()

const { computeGroupBounds } = useLayout()

const bounds = computed(() => computeGroupBounds(props.group, props.positions, 60))

const isNested = computed(() => Boolean(props.group.parent))
const groupColor = computed(() => {
  if (props.group.group_type === 'vpc' || props.group.group_type === 'subnet') {
    return CATEGORY_COLORS.network
  }
  if (props.group.group_type === 'account') return '#22d3ee'
  if (props.group.group_type === 'ou') return '#f59e0b'
  if (props.group.group_type === 'organization_root') return '#38bdf8'
  return CATEGORY_COLORS.other
})

const fillColor = computed(() => {
  return isNested.value
    ? 'color-mix(in srgb, var(--group-color) 2%, transparent)'
    : 'color-mix(in srgb, var(--group-color) 3%, transparent)'
})
const strokeColor = computed(() => 'color-mix(in srgb, var(--group-color) 12%, transparent)')
const dashPattern = computed(() => {
  if (props.group.group_type === 'organization_root') return '16 8'
  if (props.group.group_type === 'ou') return '10 6'
  if (props.group.group_type === 'account') return '6 4'
  return isNested.value ? '8 5' : '12 6'
})

// Dedicated icons for each org group type
const ORG_BOUNDARY_ICONS: Record<string, string> = {
  account:
    '<path d="M4 21V8l8-5 8 5v13M9 21v-5h6v5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  ou:
    '<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" stroke="currentColor" stroke-width="1.5" fill="none"/>',
  organization_root:
    '<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M3 12h18M12 3C8 7 8 17 12 21M12 3c4 4 4 14 0 18" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>',
}

const iconPath = computed(() => {
  return ORG_BOUNDARY_ICONS[props.group.group_type] ?? CATEGORY_ICONS.network
})
</script>
