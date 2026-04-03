<template>
  <Transition name="slide">
    <div
      v-if="node || edge"
      class="fixed right-0 top-0 h-full w-96 overflow-y-auto overflow-x-hidden z-50 detail-shell"
      style="backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); background: rgba(18, 18, 26, 0.95)"
      :style="{ '--panel-color': categoryColor }"
    >
      <div class="panel-accent" />

      <template v-if="node">
      <div class="p-4 border-b border-white/10">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3 min-w-0">
            <span
              class="inline-flex items-center justify-center w-9 h-9 rounded-lg flex-shrink-0"
              :style="{ backgroundColor: `${categoryColor}15`, color: categoryColor }"
            >
              <svg width="20" height="20" viewBox="0 0 24 24">
                <image
                  v-if="iconAsset"
                  :href="iconAsset"
                  x="0"
                  y="0"
                  width="24"
                  height="24"
                  preserveAspectRatio="xMidYMid meet"
                />
                <g v-else v-html="iconPath" />
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

        <div class="flex items-center gap-1.5 mt-3 flex-wrap">
          <span
            class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium tracking-wide"
            :style="{ backgroundColor: `${categoryColor}20`, color: categoryColor }"
          >{{ node.category }}</span>
          <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] text-gray-500 bg-white/5">{{ node.provider }}</span>
          <span v-if="node.position_hint?.tier" class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] text-gray-500 bg-white/5">{{ node.position_hint.tier }}</span>
          <span v-if="node.metadata?.account_id" class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] text-cyan-300 bg-cyan-500/10">{{ node.metadata.account_id }}</span>
          <span v-if="node.metadata?.region" class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] text-gray-500 bg-white/5">{{ node.metadata.region }}</span>
          <span
            v-if="diffStatus"
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold"
            :style="{ backgroundColor: `${diffStatusColor}20`, color: diffStatusColor }"
          >{{ diffBadgeLabel }}</span>
        </div>
        <div v-if="node.metadata?.org_path" class="mt-2 text-[11px] font-mono text-gray-500">
          {{ node.metadata.org_path }}
        </div>
      </div>

      <div v-if="diffChanges && Object.keys(diffChanges).length > 0" class="border-b border-amber-500/20 bg-amber-500/[0.03] p-4">
        <h3 class="mb-2 flex items-center gap-1.5 text-xs uppercase tracking-wider text-amber-500/70">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M5 1v4M5 7.5v.5"/></svg>
          Changes
        </h3>
        <dl>
          <div v-for="[key, change] in Object.entries(diffChanges)" :key="key" class="mb-1.5">
            <dt class="mb-0.5 text-[10px] font-mono text-gray-500">{{ key }}</dt>
            <div class="flex flex-col gap-0.5">
              <dd class="rounded bg-red-500/10 px-2 py-0.5 text-[11px] font-mono text-red-400 line-through opacity-70">
                {{ formatValue((change as any).old) }}
              </dd>
              <dd class="rounded bg-green-500/10 px-2 py-0.5 text-[11px] font-mono text-green-400">
                {{ formatValue((change as any).new) }}
              </dd>
            </div>
          </div>
        </dl>
      </div>

      <div class="p-4 border-b border-white/10">
        <!-- Edit mode actions for selected node -->
        <div v-if="store.editMode && node" class="mb-3 flex flex-wrap gap-1.5">
          <button
            class="rounded-md border border-red-400/20 bg-red-500/10 px-2.5 py-1 text-[10px] font-mono text-red-300 transition hover:bg-red-500/15"
            @click="store.hideNode(node.id)"
          >
            Hide
          </button>
          <button
            class="rounded-md border border-emerald-400/20 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-mono text-emerald-300 transition hover:bg-emerald-500/15"
            @click="store.startConnecting(node.id)"
          >
            Connect to...
          </button>
          <button
            v-if="!node.tags?._user_created"
            class="rounded-md border border-amber-400/20 bg-amber-500/10 px-2.5 py-1 text-[10px] font-mono text-amber-300 transition hover:bg-amber-500/15"
            @click="store.resetNodeEdits(node.id)"
          >
            Reset
          </button>
          <button
            v-if="node.tags?._user_created"
            class="rounded-md border border-red-400/30 bg-red-500/15 px-2.5 py-1 text-[10px] font-mono text-red-300 transition hover:bg-red-500/25"
            @click="store.removeUserNode(node.id)"
          >
            Delete
          </button>
        </div>

        <div v-if="store.editMode && node" class="mb-3 space-y-2">
          <label class="block">
            <span class="mb-1 block text-[10px] font-mono uppercase tracking-wider text-gray-500">Name</span>
            <input
              :value="node.name"
              class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white font-mono outline-none focus:border-emerald-400/40"
              @change="onNameChange"
            />
          </label>
          <label class="block">
            <span class="mb-1 block text-[10px] font-mono uppercase tracking-wider text-gray-500">Provider</span>
            <input
              :value="node.provider"
              class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white font-mono outline-none focus:border-emerald-400/40"
              @change="onProviderChange"
            />
          </label>
          <label v-if="node.tags?._user_created" class="block">
            <span class="mb-1 block text-[10px] font-mono uppercase tracking-wider text-gray-500">Service Type</span>
            <select
              :value="node.resource_type"
              class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white font-mono outline-none focus:border-emerald-400/40"
              @change="onResourceTypeChange"
            >
              <option v-for="template in userNodeTemplates" :key="template.id" :value="template.resourceType">{{ template.label }}</option>
            </select>
          </label>
          <label class="block">
            <span class="mb-1 block text-[10px] font-mono uppercase tracking-wider text-gray-500">Prominence</span>
            <select
              :value="String(node.position_hint?.weight || 2)"
              class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white font-mono outline-none focus:border-emerald-400/40"
              @change="onWeightChange"
            >
              <option value="2">Low</option>
              <option value="3">Medium</option>
              <option value="4">High</option>
              <option value="5">Critical</option>
            </select>
          </label>
          <label class="block">
            <span class="mb-1 block text-[10px] font-mono uppercase tracking-wider text-gray-500">Layer</span>
            <select
              :value="node.position_hint?.tier || 'compute'"
              class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white font-mono outline-none focus:border-emerald-400/40"
              @change="onLayerSelectChange"
            >
              <option
                v-for="layer in layerDefinitions"
                :key="layer.id"
                :value="layer.id"
              >
                {{ layer.label }}
              </option>
            </select>
          </label>
          <div class="flex gap-2">
            <input
              v-model="newLayerName"
              class="min-w-0 flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white font-mono placeholder-gray-600 outline-none focus:border-emerald-400/40"
              placeholder="Add new layer"
              @keydown.enter.prevent="addLayerAndMove"
            />
            <button
              class="rounded-lg border border-emerald-400/20 bg-emerald-500/10 px-3 py-2 text-[10px] font-mono text-emerald-300 transition hover:bg-emerald-500/15"
              @click="addLayerAndMove"
            >
              Add
            </button>
          </div>
        </div>

        <div v-if="componentLabel" class="mb-3 flex items-center justify-between rounded-lg border border-white/8 bg-white/[0.02] px-3 py-2">
          <div>
            <div class="text-[10px] uppercase tracking-widest text-gray-600">Component</div>
            <div class="mt-1 text-xs font-mono text-gray-300">{{ componentLabel }}</div>
          </div>
          <button
            class="rounded-md border border-cyan-400/20 bg-cyan-500/10 px-2.5 py-1 text-[10px] font-mono text-cyan-300 transition hover:bg-cyan-500/15"
            @click="store.focusSelectedNodeComponent()"
          >
            Focus component
          </button>
        </div>
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
              <svg width="11" height="11" viewBox="0 0 24 24">
                <image
                  v-if="nodeIconAssetById(e.target)"
                  :href="nodeIconAssetById(e.target) || undefined"
                  x="0"
                  y="0"
                  width="24"
                  height="24"
                  preserveAspectRatio="xMidYMid meet"
                />
                <g v-else v-html="nodeIconById(e.target)" />
              </svg>
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
              <svg width="11" height="11" viewBox="0 0 24 24">
                <image
                  v-if="nodeIconAssetById(e.source)"
                  :href="nodeIconAssetById(e.source) || undefined"
                  x="0"
                  y="0"
                  width="24"
                  height="24"
                  preserveAspectRatio="xMidYMid meet"
                />
                <g v-else v-html="nodeIconById(e.source)" />
              </svg>
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
      </template>

      <template v-else-if="edge">
        <div class="p-4 border-b border-white/10">
          <div class="flex items-center justify-between">
            <div class="min-w-0">
              <h2 class="text-sm font-semibold text-white font-mono leading-tight truncate">Manual Link</h2>
              <p class="text-xs text-gray-500 font-mono truncate">{{ edge.source }} → {{ edge.target }}</p>
            </div>
            <button
              class="text-gray-500 hover:text-gray-300 transition flex-shrink-0 w-6 h-6 flex items-center justify-center rounded hover:bg-white/5"
              @click="store.selectEdge(null)"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 2l8 8M10 2l-8 8"/></svg>
            </button>
          </div>
          <div class="mt-3 flex items-center gap-1.5 flex-wrap">
            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium tracking-wide" :style="{ backgroundColor: `${edgeColor}20`, color: edgeColor }">{{ edge.edge_type }}</span>
            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] text-gray-500 bg-white/5">{{ edge.label }}</span>
          </div>
        </div>

        <div class="p-4 border-b border-white/10 space-y-3">
          <label class="block">
            <span class="mb-1 block text-[10px] font-mono uppercase tracking-wider text-gray-500">Label</span>
            <input
              :value="edge.label"
              class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white font-mono outline-none focus:border-emerald-400/40"
              @change="onEdgeLabelChange"
            />
          </label>

          <label class="block">
            <span class="mb-1 block text-[10px] font-mono uppercase tracking-wider text-gray-500">Type</span>
            <select
              :value="edge.edge_type"
              class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white font-mono outline-none focus:border-emerald-400/40"
              @change="onEdgeTypeChange"
            >
              <option v-for="type in MANUAL_EDGE_TYPES" :key="type.id" :value="type.id">{{ type.label }}</option>
            </select>
          </label>

          <div>
            <span class="mb-1 block text-[10px] font-mono uppercase tracking-wider text-gray-500">Color</span>
            <div class="flex gap-2">
              <button
                v-for="color in userLinkColors"
                :key="color"
                class="h-7 w-7 rounded-full border"
                :style="{ backgroundColor: color, borderColor: edge.color === color ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.12)' }"
                @click="store.updateUserEdge(edge.id, { color })"
              />
            </div>
          </div>

          <button
            class="rounded-md border border-red-400/30 bg-red-500/15 px-3 py-1.5 text-[10px] font-mono text-red-300 transition hover:bg-red-500/25"
            @click="store.removeUserEdge(edge.id)"
          >
            Delete Link
          </button>
        </div>
      </template>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useGraphStore } from '~/stores/graph'
import { CATEGORY_COLORS, MANUAL_EDGE_TYPES, USER_NODE_TEMPLATES, buildLayerDefinitions, getNodeIconAsset, getNodeIconPath, getResourceIconAsset, getResourceIconPath } from '~/composables/useGraph'

const store = useGraphStore()
const showRaw = ref(false)
const newLayerName = ref('')
const userLinkColors = ['#4ADE80', '#38BDF8', '#C084FC', '#FB923C', '#F87171']

const node = computed(() => store.selectedNode)
const edge = computed(() => store.selectedEdge)
const diffStatus = computed(() => node.value?.position_hint?.diff_status as string | undefined)
const diffChanges = computed(() => node.value?.position_hint?.diff_changes as Record<string, unknown> | undefined)
const diffStatusColor = computed(() => {
  switch (diffStatus.value) {
    case 'added':
      return '#22c55e'
    case 'removed':
      return '#ef4444'
    case 'modified':
      return '#f59e0b'
    default:
      return '#9ca3af'
  }
})
const diffBadgeLabel = computed(() => {
  switch (diffStatus.value) {
    case 'added':
      return '+ added'
    case 'removed':
      return '− removed'
    case 'modified':
      return '~ modified'
    default:
      return ''
  }
})
const categoryColor = computed(() => CATEGORY_COLORS[node.value?.category || ''] || '#9ca3af')
const edgeColor = computed(() => edge.value?.color || CATEGORY_COLORS.integration)
const iconAsset = computed(() => node.value ? getNodeIconAsset(node.value) : getResourceIconAsset('user_defined'))
const iconPath = computed(() => node.value ? getNodeIconPath(node.value) : getResourceIconPath('user_defined', 'other'))
const layerDefinitions = computed(() => buildLayerDefinitions(store.layoutLayers, store.customLayers))
const userNodeTemplates = USER_NODE_TEMPLATES

const edges = computed(() => (node.value ? store.nodeEdges(node.value.id) : []))
const outgoing = computed(() => edges.value.filter(e => e.source === node.value?.id))
const incoming = computed(() => edges.value.filter(e => e.target === node.value?.id))
const rawJsonText = computed(() => {
  if (!node.value) return ''
  const pretty = JSON.stringify(normalizeEmbeddedJson(node.value.properties), null, 2)
  // Keep raw viewer human-readable even when upstream stores escaped newline text.
  return pretty.replace(/\\n/g, '\n')
})
const componentLabel = computed(() => {
  if (!node.value) return null
  const component = store.componentSummaries.find(summary => summary.nodeIds.includes(node.value!.id))
  return component ? component.name.replace(/-/g, ' ') : null
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
  return store.nodes.find(n => n.id === id)?.name || store.userNodes.find(n => n.id === id)?.name || id
}

function nodeColorById(id: string): string {
  const category = store.nodes.find(n => n.id === id)?.category || store.userNodes.find(n => n.id === id)?.category || 'other'
  return CATEGORY_COLORS[category] || '#9ca3af'
}

function nodeIconById(id: string): string {
  const targetNode = store.nodes.find(n => n.id === id) || store.userNodes.find(n => n.id === id)
  return targetNode ? getNodeIconPath(targetNode) : getResourceIconPath('user_defined', 'other')
}

function nodeIconAssetById(id: string): string | null {
  const targetNode = store.nodes.find(n => n.id === id) || store.userNodes.find(n => n.id === id)
  return targetNode ? getNodeIconAsset(targetNode) : null
}

function onLayerChange(layerId: string) {
  if (!node.value) return
  store.moveNodeToLayer(node.value.id, layerId)
}

function onNameChange(event: Event) {
  if (!node.value) return
  const target = event.target as HTMLInputElement | null
  if (!target) return
  store.renameNode(node.value.id, target.value)
}

function onProviderChange(event: Event) {
  if (!node.value) return
  const target = event.target as HTMLInputElement | null
  if (!target) return
  store.updateNodeDetails(node.value.id, { provider: target.value })
}

function onResourceTypeChange(event: Event) {
  if (!node.value) return
  const target = event.target as HTMLSelectElement | null
  if (!target) return
  const template = userNodeTemplates.find(candidate => candidate.resourceType === target.value)
  store.updateNodeDetails(node.value.id, {
    resource_type: target.value,
    category: template?.category ?? node.value.category,
    provider: template?.provider ?? node.value.provider,
  })
}

function onWeightChange(event: Event) {
  if (!node.value) return
  const target = event.target as HTMLSelectElement | null
  if (!target) return
  store.updateNodeDetails(node.value.id, { weight: Number(target.value) })
}

function onEdgeLabelChange(event: Event) {
  if (!edge.value) return
  const target = event.target as HTMLInputElement | null
  if (!target) return
  store.updateUserEdge(edge.value.id, { label: target.value.trim() || 'Manual link' })
}

function onEdgeTypeChange(event: Event) {
  if (!edge.value) return
  const target = event.target as HTMLSelectElement | null
  if (!target) return
  const manualType = MANUAL_EDGE_TYPES.find(type => type.id === target.value)
  store.updateUserEdge(edge.value.id, { edge_type: target.value, label: edge.value.label || manualType?.label || 'Manual link' })
}

function onLayerSelectChange(event: Event) {
  const target = event.target as HTMLSelectElement | null
  if (!target) return
  onLayerChange(target.value)
}

function addLayerAndMove() {
  if (!node.value || !newLayerName.value.trim()) return
  const layerId = store.addCustomLayer(newLayerName.value)
  if (layerId) {
    store.moveNodeToLayer(node.value.id, layerId)
    newLayerName.value = ''
  }
}
</script>

<style scoped>
.detail-shell {
  box-shadow: -12px 0 40px rgba(0, 0, 0, 0.4), -1px 0 0 rgba(255, 255, 255, 0.05);
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

.slide-enter-active {
  transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.18s ease;
}
.slide-leave-active {
  transition: transform 0.18s ease, opacity 0.15s ease;
}

.slide-enter-from {
  transform: translateX(100%);
  opacity: 0.6;
}
.slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
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
