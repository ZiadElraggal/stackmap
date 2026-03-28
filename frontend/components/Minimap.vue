<template>
  <div
    class="absolute bottom-10 right-4 w-48 h-36 bg-[#12121a]/90 border border-white/10 rounded-lg overflow-hidden z-30"
  >
    <svg class="w-full h-full" :viewBox="viewBox">
      <!-- Nodes as dots -->
      <circle
        v-for="node in store.visibleNodes"
        :key="node.id"
        :cx="store.positions[node.id]?.x ?? 0"
        :cy="store.positions[node.id]?.y ?? 0"
        :r="3"
        :fill="CATEGORY_COLORS[node.category] || '#9ca3af'"
        opacity="0.7"
      />

      <!-- Viewport rectangle -->
      <rect
        v-if="viewport"
        :x="viewport.x"
        :y="viewport.y"
        :width="viewport.width"
        :height="viewport.height"
        fill="none"
        stroke="rgba(255,255,255,0.3)"
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

const viewBox = computed(() => {
  const positions = Object.values(store.positions)
  if (positions.length === 0) return '0 0 100 100'

  const pad = 60
  const minX = Math.min(...positions.map(p => p.x)) - pad
  const maxX = Math.max(...positions.map(p => p.x)) + pad
  const minY = Math.min(...positions.map(p => p.y)) - pad
  const maxY = Math.max(...positions.map(p => p.y)) + pad

  return `${minX} ${minY} ${maxX - minX} ${maxY - minY}`
})
</script>
