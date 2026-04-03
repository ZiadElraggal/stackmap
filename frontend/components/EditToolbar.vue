<template>
  <!-- Floating edit toolbar -->
  <Transition name="slide-up">
    <div
      v-if="store.editMode"
      class="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 flex flex-col gap-2 rounded-2xl border border-emerald-400/20 bg-[#12121a]/95 px-4 py-3 shadow-[0_20px_60px_rgba(0,0,0,0.5)] backdrop-blur-md"
    >
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <PixelMascot :size="24" state="scanning" :animate="true" />
          <span class="text-[10px] font-mono uppercase tracking-widest text-emerald-400">Edit Mode</span>
          <span class="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-mono text-gray-300">{{ selectionLabel }}</span>
        </div>
        <div class="flex items-center gap-2 text-[10px] font-mono">
          <span class="text-gray-600">{{ store.lastEditAction || 'ready' }}</span>
          <span class="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-gray-400">{{ persistenceLabel }}</span>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <div class="flex items-center rounded-xl border border-white/[0.08] bg-white/[0.03] p-1">
          <button
            v-for="mode in editModes"
            :key="mode.id"
            class="rounded-lg px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.15em] transition-all"
            :class="store.editSubmode === mode.id ? 'bg-emerald-500/15 text-emerald-300' : 'text-gray-500 hover:text-white'"
            @click="store.setEditSubmode(mode.id)"
          >
            {{ mode.label }}
          </button>
        </div>
        <div class="hidden md:flex items-center gap-1.5 text-[10px] font-mono text-gray-600">
          <span class="rounded-full border border-white/[0.06] px-2 py-0.5">hidden {{ summary.hidden }}</span>
          <span class="rounded-full border border-white/[0.06] px-2 py-0.5">nodes {{ summary.customNodes }}</span>
          <span class="rounded-full border border-white/[0.06] px-2 py-0.5">links {{ summary.customLinks }}</span>
          <span class="rounded-full border border-white/[0.06] px-2 py-0.5">moved {{ summary.moved }}</span>
          <span class="rounded-full border border-white/[0.06] px-2 py-0.5">layers {{ summary.customLayers }}</span>
        </div>
      </div>

      <!-- Connecting indicator -->
      <div
        v-if="store.connectingFromNodeId"
        class="flex items-center gap-2 rounded-lg border border-amber-400/20 bg-amber-500/10 px-3 py-1.5"
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#fbbf24" stroke-width="1.5"><circle cx="3" cy="6" r="2"/><circle cx="9" cy="6" r="2"/><line x1="5" y1="6" x2="7" y2="6"/></svg>
        <span class="text-xs font-mono text-amber-300">Click target node</span>
        <button
          class="text-amber-400 hover:text-amber-200 transition"
          @click="store.cancelConnecting()"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 2l6 6M8 2l-6 6"/></svg>
        </button>
      </div>

      <!-- Actions — grouped by domain -->
      <template v-if="!store.connectingFromNodeId">
        <div class="hidden md:flex items-center rounded-md border border-white/[0.06] bg-white/[0.03] px-2.5 py-1 text-[9px] font-mono uppercase tracking-[0.15em] text-gray-600">
          {{ modeDescription }}
        </div>

        <!-- Node actions -->
        <span class="h-4 w-px bg-white/[0.08]" />
        <button
          v-if="store.editSubmode === 'structure'"
          class="edit-btn"
          title="Add a custom component"
          @click="showAddDialog = true"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="6.5" y1="2" x2="6.5" y2="11"/><line x1="2" y1="6.5" x2="11" y2="6.5"/></svg>
          <span>Add Node</span>
        </button>

        <button
          v-if="store.editSubmode === 'structure'"
          class="edit-btn"
          title="Create a new architecture layer"
          @click="showAddLayerDialog = true"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M2 4h9M2 6.5h9M2 9h9"/>
            <path d="M10 2.5v3M8.5 4h3"/>
          </svg>
          <span>Add Layer</span>
        </button>

        <!-- Layout actions -->
        <span class="h-4 w-px bg-white/[0.08]" />
        <button
          v-if="store.editSubmode === 'structure'"
          class="edit-btn"
          title="Re-arrange the graph after edits"
          @click="relayoutGraph"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M2 3.5h4M2 9.5h9M7 3.5l1.5-1.5M7 3.5L8.5 5M9 9.5l1.5-1.5M9 9.5l1.5 1.5"/>
          </svg>
          <span>Reflow</span>
        </button>

        <button
          v-if="store.editSubmode === 'structure'"
          class="edit-btn"
          title="Repack the graph more aggressively"
          @click="repackGraph"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <rect x="2" y="2" width="3" height="3"/><rect x="8" y="2" width="3" height="3"/><rect x="2" y="8" width="3" height="3"/><rect x="8" y="8" width="3" height="3"/>
          </svg>
          <span>Repack</span>
        </button>

        <!-- Global actions -->
        <span class="h-4 w-px bg-white/[0.08]" />
        <button
          class="edit-btn"
          :class="{ 'opacity-40 pointer-events-none': !store.canUndo }"
          title="Undo"
          @click="store.undoEdits()"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 3L2 6l3 3"/><path d="M2 6h5.5a3.5 3.5 0 1 1 0 7H6"/>
          </svg>
          <span>Undo</span>
        </button>

        <button
          class="edit-btn"
          :class="{ 'opacity-40 pointer-events-none': !store.canRedo }"
          title="Redo"
          @click="store.redoEdits()"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M8 3l3 3-3 3"/><path d="M11 6H5.5a3.5 3.5 0 1 0 0 7H7"/>
          </svg>
          <span>Redo</span>
        </button>

        <button
          v-if="store.hiddenNodeIds.length > 0"
          class="edit-btn"
          @click="store.showAllNodes()"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M1 6.5s2.5-4 5.5-4 5.5 4 5.5 4-2.5 4-5.5 4-5.5-4-5.5-4z"/><circle cx="6.5" cy="6.5" r="1.5"/></svg>
          <span>Show All ({{ store.hiddenNodeIds.length }})</span>
        </button>

        <button
          v-if="store.hiddenNodeIdsBackup?.length"
          class="edit-btn"
          @click="store.rehideShownNodes()"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M1 6.5s2.5-4 5.5-4 5.5 4 5.5 4-2.5 4-5.5 4-5.5-4-5.5-4z"/><path d="M2 11L11 2"/></svg>
          <span>Rehide ({{ store.hiddenNodeIdsBackup.length }})</span>
        </button>

        <button
          class="edit-btn"
          @click="togglePresentation"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1.5" y="2" width="10" height="7" rx="1.5"/><path d="M4 11h5"/></svg>
          <span>Present</span>
        </button>

        <button
          class="edit-btn"
          @click="downloadEdits"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6.5 2v6M4 6l2.5 2.5L9 6"/><path d="M2 10.5h9"/></svg>
          <span>Export Edits</span>
        </button>

        <button
          class="edit-btn"
          @click="triggerImport"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6.5 11V5M4 7.5L6.5 5 9 7.5"/><path d="M2 2.5h9"/></svg>
          <span>Import</span>
        </button>

        <button
          class="edit-btn"
          @click="downloadGraph"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 2.5h9v8H2z"/><path d="M4.5 5h4M4.5 7h3M4.5 9h4"/></svg>
          <span>Export Graph</span>
        </button>

        <button
          v-if="hasAnyEdits"
          class="edit-btn text-red-400/80 hover:!text-red-400 hover:!bg-red-500/10"
          @click="store.clearAllEdits()"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M2 4h9M4.5 4V3a1 1 0 011-1h2a1 1 0 011 1v1M5.5 6v4M7.5 6v4"/><path d="M3 4l.5 7a1 1 0 001 1h4a1 1 0 001-1L10 4"/></svg>
          <span>Clear Edits</span>
        </button>
      </template>

      <!-- Exit -->
      <button
        class="ml-1 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-mono text-gray-400 transition hover:bg-white/10 hover:text-white"
        @click="store.toggleEditMode()"
      >
        Done
      </button>
      <input ref="importInputRef" type="file" accept="application/json" class="hidden" @change="onImportFile" />
    </div>
  </Transition>

  <!-- Toggle button (when not in edit mode) -->
  <button
    v-if="!store.editMode"
    class="fixed bottom-6 right-6 z-40 flex items-center gap-2 rounded-xl border border-white/10 bg-[#12121a]/90 px-3 py-2 text-xs font-mono text-gray-400 shadow-[0_8px_30px_rgba(0,0,0,0.3)] backdrop-blur-sm transition hover:border-emerald-400/30 hover:text-emerald-400 hover:shadow-[0_8px_30px_rgba(74,222,128,0.08)]"
    @click="store.toggleEditMode()"
  >
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
      <path d="M8.5 2.5l3 3L4 13H1v-3L8.5 2.5z"/>
    </svg>
    Edit
  </button>

  <!-- Add Node Dialog -->
  <Transition name="fade">
    <div
      v-if="showAddDialog"
      class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      @click.self="showAddDialog = false"
    >
      <div class="w-[380px] rounded-2xl border border-white/10 bg-[#12121a] p-6 shadow-[0_30px_80px_rgba(0,0,0,0.5)]">
        <h3 class="text-sm font-semibold text-white mb-4">Add Custom Component</h3>

        <label class="block mb-3">
          <span class="text-[10px] font-mono uppercase tracking-wider text-gray-500 mb-1 block">Name</span>
          <input
            v-model="newNodeName"
            class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white font-mono placeholder-gray-600 outline-none focus:border-emerald-400/40"
            placeholder="e.g. Payment Service"
            @keydown.enter="addNode"
          />
        </label>

        <label class="block mb-3">
          <span class="text-[10px] font-mono uppercase tracking-wider text-gray-500 mb-1 block">Service Type</span>
          <select
            v-model="newNodeTemplateId"
            class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white font-mono outline-none focus:border-emerald-400/40 appearance-none"
          >
            <option
              v-for="template in userNodeTemplates"
              :key="template.id"
              :value="template.id"
            >
              {{ template.label }}
            </option>
          </select>
        </label>

        <label class="block mb-5">
          <span class="text-[10px] font-mono uppercase tracking-wider text-gray-500 mb-1 block">Placement</span>
          <select
            v-model="newNodeLayerId"
            class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white font-mono outline-none focus:border-emerald-400/40 appearance-none"
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

        <div class="flex justify-end gap-2">
          <button
            class="rounded-lg border border-white/10 px-4 py-2 text-xs font-mono text-gray-400 transition hover:bg-white/5"
            @click="showAddDialog = false"
          >
            Cancel
          </button>
          <button
            class="rounded-lg border border-emerald-400/30 bg-emerald-500/15 px-4 py-2 text-xs font-mono text-emerald-300 transition hover:bg-emerald-500/25"
            :disabled="!newNodeName.trim()"
            @click="addNode"
          >
            Add Component
          </button>
        </div>
      </div>
    </div>
  </Transition>

  <Transition name="fade">
    <div
      v-if="showAddLayerDialog"
      class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      @click.self="showAddLayerDialog = false"
    >
      <div class="w-[360px] rounded-2xl border border-white/10 bg-[#12121a] p-6 shadow-[0_30px_80px_rgba(0,0,0,0.5)]">
        <h3 class="mb-4 text-sm font-semibold text-white">Add Layer</h3>

        <label class="block mb-5">
          <span class="mb-1 block text-[10px] font-mono uppercase tracking-wider text-gray-500">Layer Name</span>
          <input
            v-model="newLayerName"
            class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white font-mono placeholder-gray-600 outline-none focus:border-emerald-400/40"
            placeholder="e.g. edge, authz, shared"
            @keydown.enter.prevent="addLayerFromDialog"
          />
        </label>

        <div class="flex justify-end gap-2">
          <button
            class="rounded-lg border border-white/10 px-4 py-2 text-xs font-mono text-gray-400 transition hover:bg-white/5"
            @click="showAddLayerDialog = false"
          >
            Cancel
          </button>
          <button
            class="rounded-lg border border-emerald-400/30 bg-emerald-500/15 px-4 py-2 text-xs font-mono text-emerald-300 transition hover:bg-emerald-500/25"
            :disabled="!newLayerName.trim()"
            @click="addLayerFromDialog"
          >
            Add Layer
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { DEFAULT_GRAPH_LAYERS, USER_NODE_TEMPLATES, buildLayerDefinitions } from '~/composables/useGraph'
import { useGraphStore } from '~/stores/graph'

const store = useGraphStore()

const showAddDialog = ref(false)
const showAddLayerDialog = ref(false)
const newNodeName = ref('')
const newNodeTemplateId = ref('lambda')
const newNodeLayerId = ref('serverless')
const newLayerName = ref('')
const importInputRef = ref<HTMLInputElement | null>(null)
const userNodeTemplates = USER_NODE_TEMPLATES
const editModes = [
  { id: 'inspect', label: 'Inspect' },
  { id: 'structure', label: 'Structure' },
  { id: 'connect', label: 'Connect' },
] as const

const selectedTemplate = computed(() =>
  userNodeTemplates.find(template => template.id === newNodeTemplateId.value) || userNodeTemplates[0]
)
const layerDefinitions = computed(() => buildLayerDefinitions(store.layoutLayers, store.customLayers))
const summary = computed(() => store.editChangeSummary)
const persistenceLabel = computed(() => {
  switch (store.editPersistenceStatus) {
    case 'saved': return 'saved locally'
    case 'restored': return 'restored'
    case 'imported': return 'imported'
    default: return 'idle'
  }
})
const selectionLabel = computed(() => {
  if (store.selectedNode) return store.selectedNode.name
  if (store.selectedEdge) return store.selectedEdge.label || 'manual link'
  return 'nothing selected'
})
const modeDescription = computed(() => {
  switch (store.editSubmode) {
    case 'inspect': return 'safe review mode'
    case 'structure': return 'drag to move · use layer rail'
    case 'connect': return store.connectingFromNodeId ? 'choose a target node' : 'select a node and connect it'
    default: return ''
  }
})

const hasAnyEdits = computed(() =>
  store.hiddenNodeIds.length > 0
  || store.userEdges.length > 0
  || store.userNodes.length > 0
  || store.customLayers.length > 0
  || Object.keys(store.nodeTierOverrides).length > 0
  || store.layoutLayers.join('|') !== [...DEFAULT_GRAPH_LAYERS.map(layer => layer.id), ...store.customLayers.map(layer => layer.id)].join('|')
)

function addLayerFromDialog() {
  if (!newLayerName.value.trim()) return
  const layerId = store.addCustomLayer(newLayerName.value)
  if (!layerId) return
  newNodeLayerId.value = layerId
  newLayerName.value = ''
  showAddLayerDialog.value = false
  relayoutGraph()
}

function addNode() {
  if (!newNodeName.value.trim()) return
  const template = selectedTemplate.value
  store.addUserNode(newNodeName.value.trim(), {
    resourceType: template.resourceType,
    category: template.category,
    tier: newNodeLayerId.value,
    provider: template.provider,
    weight: template.weight,
  })
  newNodeName.value = ''
  showAddDialog.value = false
  relayoutGraph()
}

function relayoutGraph() {
  store.requestRelayout()
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event('stackmap-fit-view'))
  }
}

function repackGraph() {
  store.requestRelayout()
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('stackmap-fit-view'))
  }
}

function togglePresentation() {
  store.setPresentationMode(true)
}

function downloadBlob(filename: string, content: string) {
  if (typeof window === 'undefined') return
  const blob = new Blob([content], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function downloadEdits() {
  downloadBlob('stackmap-edits.json', store.exportEditsPayload())
}

function downloadGraph() {
  downloadBlob('stackmap-corrected-graph.json', store.exportCurrentGraphPayload(store.presentationMode ? 'presentation' : 'corrected'))
}

function triggerImport() {
  importInputRef.value?.click()
}

async function onImportFile(event: Event) {
  const target = event.target as HTMLInputElement | null
  const file = target?.files?.[0]
  if (!file) return
  const text = await file.text()
  store.importEditsPayload(text)
  relayoutGraph()
  if (target) target.value = ''
}

watch(selectedTemplate, template => {
  if (template && store.layoutLayers.includes(template.tier)) {
    newNodeLayerId.value = template.tier
  }
}, { immediate: true })
</script>

<style scoped>
.edit-btn {
  @apply flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-mono text-gray-400 transition-all duration-150;
  @apply hover:bg-white/[0.06] hover:text-white active:scale-[0.97];
}

.edit-btn svg {
  opacity: 0.7;
  transition: opacity 150ms ease;
}

.edit-btn:hover svg {
  opacity: 1;
}

.slide-up-enter-active {
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.slide-up-leave-active {
  transition: all 0.15s ease;
}
.slide-up-enter-from {
  opacity: 0;
  transform: translate(-50%, 20px);
}
.slide-up-leave-to {
  opacity: 0;
  transform: translate(-50%, 10px);
}

.fade-enter-active {
  transition: opacity 0.18s ease, transform 0.18s cubic-bezier(0.16, 1, 0.3, 1);
}
.fade-leave-active {
  transition: opacity 0.12s ease, transform 0.12s ease;
}
.fade-enter-from {
  opacity: 0;
  transform: scale(0.97) translateY(4px);
}
.fade-leave-to {
  opacity: 0;
  transform: scale(0.98);
}

select option {
  background: #12121a;
  color: #e5e7eb;
}
</style>
