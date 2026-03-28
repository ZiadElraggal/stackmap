<template>
  <Transition name="slide">
    <div
      v-if="node"
      class="fixed right-0 top-0 h-full w-96 bg-[#12121a] border-l border-white/10 overflow-y-auto z-50 shadow-2xl"
    >
      <!-- Header -->
      <div class="p-4 border-b border-white/10">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span
              class="inline-block w-3 h-3 rounded-full"
              :style="{ backgroundColor: categoryColor }"
            />
            <span class="text-xs uppercase tracking-wider text-gray-400">{{
              node.category
            }}</span>
          </div>
          <button
            class="text-gray-500 hover:text-gray-300 transition"
            @click="store.selectNode(null)"
          >
            ✕
          </button>
        </div>
        <h2 class="text-lg font-semibold text-white mt-2 font-mono">
          {{ node.name }}
        </h2>
        <p class="text-sm text-gray-500 font-mono">{{ node.resource_type }}</p>
      </div>

      <!-- Properties -->
      <div class="p-4 border-b border-white/10">
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">
          Properties
        </h3>
        <dl class="space-y-1">
          <div
            v-for="[key, val] in topProperties"
            :key="key"
            class="flex justify-between text-xs"
          >
            <dt class="text-gray-500 font-mono">{{ key }}</dt>
            <dd class="text-gray-300 font-mono truncate max-w-[200px]">
              {{ formatValue(val) }}
            </dd>
          </div>
        </dl>
      </div>

      <!-- Tags -->
      <div v-if="Object.keys(node.tags || {}).length > 0" class="p-4 border-b border-white/10">
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">Tags</h3>
        <div class="flex flex-wrap gap-1">
          <span
            v-for="[key, val] in Object.entries(node.tags)"
            :key="key"
            class="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono bg-white/5 text-gray-400"
          >
            {{ key }}={{ val }}
          </span>
        </div>
      </div>

      <!-- Connections -->
      <div class="p-4">
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">
          Connections ({{ edges.length }})
        </h3>

        <!-- Outgoing -->
        <div v-if="outgoing.length > 0" class="mb-3">
          <p class="text-xs text-gray-600 mb-1">Outgoing →</p>
          <div
            v-for="e in outgoing"
            :key="e.id"
            class="flex items-center gap-2 text-xs py-1 px-2 rounded hover:bg-white/5 cursor-pointer"
            @click="store.selectNode(e.target)"
          >
            <span
              class="w-2 h-2 rounded-full"
              :style="{ backgroundColor: edgeColor(e.edge_type) }"
            />
            <span class="text-gray-300 font-mono">{{
              nodeNameById(e.target)
            }}</span>
            <span class="text-gray-600 ml-auto">{{ e.label }}</span>
          </div>
        </div>

        <!-- Incoming -->
        <div v-if="incoming.length > 0">
          <p class="text-xs text-gray-600 mb-1">← Incoming</p>
          <div
            v-for="e in incoming"
            :key="e.id"
            class="flex items-center gap-2 text-xs py-1 px-2 rounded hover:bg-white/5 cursor-pointer"
            @click="store.selectNode(e.source)"
          >
            <span
              class="w-2 h-2 rounded-full"
              :style="{ backgroundColor: edgeColor(e.edge_type) }"
            />
            <span class="text-gray-300 font-mono">{{
              nodeNameById(e.source)
            }}</span>
            <span class="text-gray-600 ml-auto">{{ e.label }}</span>
          </div>
        </div>
      </div>

      <!-- Hop filter -->
      <div class="p-4 border-b border-white/10">
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">
          Show connections
        </h3>
        <div class="flex gap-1">
          <button
            v-for="h in [0, 1, 2, 3]"
            :key="h"
            :class="[
              'px-2 py-1 rounded text-xs font-mono transition',
              store.hopLimit === h
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                : 'text-gray-500 hover:text-gray-300 border border-white/10',
            ]"
            @click="store.setHopLimit(h)"
          >
            {{ h === 0 ? 'All' : h + ' hop' + (h > 1 ? 's' : '') }}
          </button>
        </div>
      </div>

      <!-- Raw JSON toggle -->
      <div class="p-4 border-t border-white/10">
        <button
          class="text-xs text-gray-500 hover:text-gray-300 transition"
          @click="showRaw = !showRaw"
        >
          {{ showRaw ? 'Hide' : 'View' }} Raw JSON
        </button>
        <pre
          v-if="showRaw"
          class="mt-2 p-2 bg-black/30 rounded text-xs text-gray-400 overflow-x-auto font-mono max-h-64 overflow-y-auto"
        >{{ JSON.stringify(node.properties, null, 2) }}</pre>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useGraphStore } from '~/stores/graph'
import { CATEGORY_COLORS, EDGE_COLORS } from '~/composables/useGraph'

const store = useGraphStore()
const showRaw = ref(false)

const node = computed(() => store.selectedNode)
const categoryColor = computed(
  () => CATEGORY_COLORS[node.value?.category || ''] || '#9ca3af'
)

const edges = computed(() =>
  node.value ? store.nodeEdges(node.value.id) : []
)
const outgoing = computed(() =>
  edges.value.filter(e => e.source === node.value?.id)
)
const incoming = computed(() =>
  edges.value.filter(e => e.target === node.value?.id)
)

// Show most relevant properties (filter out massive blobs)
const SKIP_KEYS = new Set([
  'tags', 'tags_all', 'arn', 'id', 'definition', 'policy',
  'assume_role_policy', 'inline_policy', 'vpc_config',
  'network_configuration', 'origin', 'default_cache_behavior',
  'ordered_cache_behavior', 'viewer_certificate', 'restrictions',
])

const topProperties = computed(() => {
  if (!node.value) return []
  return Object.entries(node.value.properties)
    .filter(([key, val]) => {
      if (SKIP_KEYS.has(key)) return false
      if (val === null || val === '' || val === undefined) return false
      if (typeof val === 'object') return false
      return true
    })
    .slice(0, 12)
})

function formatValue(val: any): string {
  if (typeof val === 'boolean') return val ? 'true' : 'false'
  if (typeof val === 'number') return String(val)
  return String(val)
}

function edgeColor(type: string): string {
  return EDGE_COLORS[type] || '#4b5563'
}

function nodeNameById(id: string): string {
  return store.nodes.find(n => n.id === id)?.name || id
}
</script>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.25s ease;
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}
</style>
