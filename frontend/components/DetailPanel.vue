<template>
  <Transition name="slide">
    <div
      v-if="node"
      class="fixed right-0 top-0 h-full w-96 bg-[#12121a] overflow-y-auto overflow-x-hidden z-50 detail-shell"
      :style="{ '--panel-color': categoryColor }"
    >
      <div class="panel-accent" />

      <div class="p-4 border-b border-white/10">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3 min-w-0">
            <span
              class="inline-flex items-center justify-center w-9 h-9 rounded-lg flex-shrink-0"
              :style="{ backgroundColor: `${categoryColor}15`, color: categoryColor }"
            >
              <svg width="20" height="20" viewBox="0 0 24 24">
                <g v-html="iconPath" />
              </svg>
            </span>
            <div class="min-w-0">
              <h2 class="text-sm font-semibold text-white font-mono leading-tight truncate">{{ node.name }}</h2>
              <p class="text-xs text-gray-500 font-mono truncate">{{ node.resource_type }}</p>
            </div>
          </div>
          <button
            class="text-gray-500 hover:text-gray-300 transition flex-shrink-0 w-6 h-6 flex items-center justify-center rounded hover:bg-white/5"
            @click="store.selectNode(null)"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 2l8 8M10 2l-8 8"/></svg>
          </button>
        </div>

        <div class="flex items-center gap-1.5 mt-3">
          <span
            class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium tracking-wide"
            :style="{ backgroundColor: `${categoryColor}20`, color: categoryColor }"
          >{{ node.category }}</span>
          <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] text-gray-500 bg-white/5">{{ node.provider }}</span>
          <span v-if="node.position_hint?.tier" class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] text-gray-500 bg-white/5">{{ node.position_hint.tier }}</span>
        </div>
      </div>

      <div class="p-4 border-b border-white/10">
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">Properties</h3>
        <dl>
          <div
            v-for="([key, val], idx) in topProperties"
            :key="key"
            class="flex justify-between text-xs px-2 py-1"
            :class="idx % 2 === 0 ? 'bg-transparent' : 'bg-white/[0.02]'"
          >
            <dt class="text-gray-500 font-mono mr-3">{{ key }}</dt>
            <dd class="text-gray-300 font-mono truncate max-w-[200px]">
              {{ formatValue(val) }}
            </dd>
          </div>
        </dl>
      </div>

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

      <div class="p-4 border-b border-white/10">
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">
          Connections
          <span class="text-gray-600 ml-1 normal-case tracking-normal">({{ edges.length }})</span>
        </h3>

        <div v-if="outgoing.length > 0" class="mb-3">
          <p class="text-[10px] text-gray-600 mb-1.5 uppercase tracking-wider flex items-center gap-1">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 5h6M6 3l2 2-2 2"/></svg>
            Outgoing
          </p>
          <div
            v-for="e in outgoing"
            :key="e.id"
            class="flex items-center gap-2 text-xs py-1.5 px-2 rounded-md hover:bg-white/5 cursor-pointer transition-colors group"
            @click="store.selectNode(e.target)"
          >
            <span
              class="w-5 h-5 rounded flex-shrink-0 flex items-center justify-center"
              :style="{ backgroundColor: `${nodeColorById(e.target)}15`, color: nodeColorById(e.target) }"
            >
              <svg width="11" height="11" viewBox="0 0 24 24"><g v-html="nodeIconById(e.target)" /></svg>
            </span>
            <span class="text-gray-300 font-mono truncate group-hover:text-white transition-colors">{{ nodeNameById(e.target) }}</span>
            <span class="text-[10px] text-gray-600 ml-auto flex-shrink-0 font-mono">{{ e.label || e.edge_type }}</span>
          </div>
        </div>

        <div v-if="incoming.length > 0">
          <p class="text-[10px] text-gray-600 mb-1.5 uppercase tracking-wider flex items-center gap-1">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 5H2M4 3L2 5l2 2"/></svg>
            Incoming
          </p>
          <div
            v-for="e in incoming"
            :key="e.id"
            class="flex items-center gap-2 text-xs py-1.5 px-2 rounded-md hover:bg-white/5 cursor-pointer transition-colors group"
            @click="store.selectNode(e.source)"
          >
            <span
              class="w-5 h-5 rounded flex-shrink-0 flex items-center justify-center"
              :style="{ backgroundColor: `${nodeColorById(e.source)}15`, color: nodeColorById(e.source) }"
            >
              <svg width="11" height="11" viewBox="0 0 24 24"><g v-html="nodeIconById(e.source)" /></svg>
            </span>
            <span class="text-gray-300 font-mono truncate group-hover:text-white transition-colors">{{ nodeNameById(e.source) }}</span>
            <span class="text-[10px] text-gray-600 ml-auto flex-shrink-0 font-mono">{{ e.label || e.edge_type }}</span>
          </div>
        </div>

        <div v-if="edges.length === 0" class="text-xs text-gray-600 italic py-2">No connections</div>
      </div>

      <div class="p-4 border-b border-white/10">
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">Neighborhood</h3>
        <div class="flex gap-1.5">
          <button
            v-for="h in [0, 1, 2, 3]"
            :key="h"
            :class="[
              'px-2.5 py-1 rounded-md text-xs font-mono transition-all',
              store.hopLimit === h
                ? 'text-white active-hop shadow-sm'
                : 'text-gray-500 hover:text-gray-300 bg-white/[0.03] hover:bg-white/[0.06]',
            ]"
            @click="store.setHopLimit(h)"
          >
            {{ h === 0 ? 'All' : h + ' hop' + (h > 1 ? 's' : '') }}
          </button>
        </div>
      </div>

      <div class="p-4">
        <button
          class="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition group"
          @click="showRaw = !showRaw"
        >
          <svg
            width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5"
            class="transition-transform" :class="showRaw ? 'rotate-90' : ''"
          ><path d="M3 2l4 3-4 3"/></svg>
          <span>{{ showRaw ? 'Hide' : 'View' }} raw properties</span>
        </button>
        <Transition name="expand">
          <div v-if="showRaw" class="mt-2 max-w-full overflow-hidden">
            <pre
              class="p-3 bg-black/30 rounded-lg text-[11px] text-gray-400 font-mono max-h-80 overflow-y-auto whitespace-pre-wrap break-words leading-relaxed"
            >{{ rawJsonText }}</pre>
          </div>
        </Transition>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useGraphStore } from '~/stores/graph'
import { CATEGORY_COLORS, CATEGORY_ICONS } from '~/composables/useGraph'

const store = useGraphStore()
const showRaw = ref(false)

const node = computed(() => store.selectedNode)
const categoryColor = computed(() => CATEGORY_COLORS[node.value?.category || ''] || '#9ca3af')
const iconPath = computed(() => CATEGORY_ICONS[node.value?.category || 'other'] || CATEGORY_ICONS.other)

const edges = computed(() => (node.value ? store.nodeEdges(node.value.id) : []))
const outgoing = computed(() => edges.value.filter(e => e.source === node.value?.id))
const incoming = computed(() => edges.value.filter(e => e.target === node.value?.id))
const rawJsonText = computed(() => {
  if (!node.value) return ''
  const pretty = JSON.stringify(normalizeEmbeddedJson(node.value.properties), null, 2)
  // Keep raw viewer human-readable even when upstream stores escaped newline text.
  return pretty.replace(/\\n/g, '\n')
})

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

function normalizeEmbeddedJson(value: any): any {
  if (Array.isArray(value)) {
    return value.map(v => normalizeEmbeddedJson(v))
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([k, v]) => [k, normalizeEmbeddedJson(v)])
    )
  }
  if (typeof value !== 'string') return value

  const trimmed = value.trim()
  const looksLikeJson =
    (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
    (trimmed.startsWith('[') && trimmed.endsWith(']'))

  if (looksLikeJson) {
    try {
      return normalizeEmbeddedJson(JSON.parse(trimmed))
    } catch {
      // Keep original string if it's not valid JSON.
    }
  }

  // Convert escaped line breaks in stored strings into readable multi-line text.
  return value.replace(/\\n/g, '\n')
}

function nodeNameById(id: string): string {
  return store.nodes.find(n => n.id === id)?.name || id
}

function nodeColorById(id: string): string {
  const category = store.nodes.find(n => n.id === id)?.category || 'other'
  return CATEGORY_COLORS[category] || '#9ca3af'
}

function nodeIconById(id: string): string {
  const category = store.nodes.find(n => n.id === id)?.category || 'other'
  return CATEGORY_ICONS[category] || CATEGORY_ICONS.other
}
</script>

<style scoped>
.detail-shell {
  box-shadow: -20px 0 60px rgba(0, 0, 0, 0.5);
  border-left: 1px solid rgba(255,255,255,0.06);
}

.panel-accent {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: linear-gradient(
    180deg,
    var(--panel-color),
    color-mix(in srgb, var(--panel-color) 30%, transparent)
  );
}

.active-hop {
  background: color-mix(in srgb, var(--panel-color) 18%, transparent);
  color: var(--panel-color);
}

.slide-enter-active,
.slide-leave-active {
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}

.expand-enter-active,
.expand-leave-active {
  transition: all 0.15s ease;
  overflow: hidden;
}
.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
