<template>
  <!-- Floating edit toolbar -->
  <Transition name="slide-up">
    <div
      v-if="store.editMode"
      class="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 flex items-center gap-2 rounded-2xl border border-emerald-400/20 bg-[#12121a]/95 px-4 py-2.5 shadow-[0_20px_60px_rgba(0,0,0,0.5)] backdrop-blur-md"
    >
      <!-- Prism indicator -->
      <div class="flex items-center gap-2 border-r border-white/10 pr-3">
        <PixelMascot :size="24" state="scanning" :animate="true" />
        <span class="text-[10px] font-mono uppercase tracking-widest text-emerald-400">Edit Mode</span>
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
          Drag to reorder
        </div>

        <!-- Node actions -->
        <span class="h-4 w-px bg-white/[0.08]" />
        <button
          class="edit-btn"
          title="Add a custom component"
          @click="showAddDialog = true"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="6.5" y1="2" x2="6.5" y2="11"/><line x1="2" y1="6.5" x2="11" y2="6.5"/></svg>
          <span>Add Node</span>
        </button>

        <!-- Layout actions -->
        <span class="h-4 w-px bg-white/[0.08]" />
        <button
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
          class="edit-btn"
          title="Reorder architecture layers"
          @click="showLayersDialog = true"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
            <path d="M3 3.5h7M3 6.5h7M3 9.5h7"/>
            <path d="M1.5 3.5h.01M1.5 6.5h.01M1.5 9.5h.01"/>
          </svg>
          <span>Layers</span>
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
    </div>
  </Transition>

  <Transition name="fade">
    <div
      v-if="showLayersDialog"
      class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      @click.self="showLayersDialog = false"
    >
      <div class="w-[420px] rounded-2xl border border-white/10 bg-[#12121a] p-6 shadow-[0_30px_80px_rgba(0,0,0,0.5)]">
        <div class="mb-4 flex items-start justify-between gap-4">
          <div>
            <h3 class="text-sm font-semibold text-white">Reorder Layers</h3>
            <p class="mt-1 text-xs text-gray-500">Drag layers to change the architecture flow from top to bottom.</p>
          </div>
          <button
            class="rounded-lg border border-white/10 px-2 py-1 text-[10px] font-mono text-gray-400 transition hover:bg-white/5 hover:text-white"
            @click="showLayersDialog = false"
          >
            Close
          </button>
        </div>

        <div class="space-y-2">
          <div
            v-for="(layer, index) in layerDefinitions"
            :key="layer.id"
            draggable="true"
            class="layer-item"
            :class="{
              'layer-item--dragging': draggingLayerId === layer.id,
              'layer-item--target': layerDropTargetId === layer.id,
            }"
            @dragstart="onLayerDragStart($event, layer.id)"
            @dragover.prevent="onLayerDragOver(layer.id)"
            @drop.prevent="onLayerDrop(layer.id)"
            @dragend="onLayerDragEnd"
          >
            <div class="flex items-center gap-3">
              <span class="text-sm leading-none text-gray-500">⋮⋮</span>
              <span class="text-sm">{{ layer.icon }}</span>
              <div>
                <div class="text-sm font-medium text-white">{{ layer.label }}</div>
                <div class="text-[10px] font-mono uppercase tracking-wider text-gray-500">{{ layer.id }}</div>
              </div>
            </div>
            <span class="rounded-full border border-white/10 px-2 py-0.5 text-[10px] font-mono text-gray-400">
              {{ store.visibleNodes.filter(node => (node.position_hint?.tier || 'compute') === layer.id).length }}
            </span>
            <div class="flex items-center gap-1">
              <button
                class="layer-move-btn"
                :disabled="index === 0"
                title="Move layer up"
                @click="moveLayerByOffset(layer.id, -1)"
              >
                ↑
              </button>
              <button
                class="layer-move-btn"
                :disabled="index === layerDefinitions.length - 1"
                title="Move layer down"
                @click="moveLayerByOffset(layer.id, 1)"
              >
                ↓
              </button>
            </div>
          </div>
        </div>
      </div>
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

        <label class="block mb-5">
          <span class="text-[10px] font-mono uppercase tracking-wider text-gray-500 mb-1 block">New Layer</span>
          <div class="flex gap-2">
            <input
              v-model="newLayerName"
              class="min-w-0 flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white font-mono placeholder-gray-600 outline-none focus:border-emerald-400/40"
              placeholder="e.g. edge, authz, shared"
              @keydown.enter.prevent="addLayer"
            />
            <button
              class="rounded-lg border border-emerald-400/30 bg-emerald-500/15 px-3 py-2 text-xs font-mono text-emerald-300 transition hover:bg-emerald-500/25"
              @click="addLayer"
            >
              Add Layer
            </button>
          </div>
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
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { DEFAULT_GRAPH_LAYERS, USER_NODE_TEMPLATES, buildLayerDefinitions } from '~/composables/useGraph'
import { useGraphStore } from '~/stores/graph'

const store = useGraphStore()

const showAddDialog = ref(false)
const showLayersDialog = ref(false)
const newNodeName = ref('')
const newNodeTemplateId = ref('lambda')
const newNodeLayerId = ref('serverless')
const newLayerName = ref('')
const draggingLayerId = ref<string | null>(null)
const layerDropTargetId = ref<string | null>(null)
const userNodeTemplates = USER_NODE_TEMPLATES

const selectedTemplate = computed(() =>
  userNodeTemplates.find(template => template.id === newNodeTemplateId.value) || userNodeTemplates[0]
)
const layerDefinitions = computed(() => buildLayerDefinitions(store.layoutLayers, store.customLayers))

const hasAnyEdits = computed(() =>
  store.hiddenNodeIds.length > 0
  || store.userEdges.length > 0
  || store.userNodes.length > 0
  || store.customLayers.length > 0
  || Object.keys(store.nodeTierOverrides).length > 0
  || store.layoutLayers.join('|') !== [...DEFAULT_GRAPH_LAYERS.map(layer => layer.id), ...store.customLayers.map(layer => layer.id)].join('|')
)

function addLayer() {
  if (!newLayerName.value.trim()) return
  const layerId = store.addCustomLayer(newLayerName.value)
  if (layerId) {
    newNodeLayerId.value = layerId
    newLayerName.value = ''
  }
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

function onLayerDragStart(event: DragEvent, layerId: string) {
  event.dataTransfer?.setData('text/plain', layerId)
  event.dataTransfer!.effectAllowed = 'move'
  draggingLayerId.value = layerId
  layerDropTargetId.value = layerId
}

function onLayerDragOver(layerId: string) {
  layerDropTargetId.value = layerId
}

function onLayerDrop(layerId: string) {
  if (!draggingLayerId.value) return
  store.reorderLayers(draggingLayerId.value, layerId)
  relayoutGraph()
  draggingLayerId.value = null
  layerDropTargetId.value = null
}

function onLayerDragEnd() {
  draggingLayerId.value = null
  layerDropTargetId.value = null
}

function moveLayerByOffset(layerId: string, offset: number) {
  const index = store.layoutLayers.indexOf(layerId)
  const targetIndex = index + offset
  if (index === -1 || targetIndex < 0 || targetIndex >= store.layoutLayers.length) return
  const targetLayerId = store.layoutLayers[targetIndex]
  store.reorderLayers(layerId, targetLayerId)
  relayoutGraph()
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

.layer-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  border-radius: 0.875rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  padding: 0.875rem 0.95rem;
  transition: border-color 160ms ease, background-color 160ms ease, transform 160ms ease;
  cursor: grab;
}

.layer-item--dragging {
  opacity: 0.5;
}

.layer-item--target {
  border-color: rgba(74, 222, 128, 0.35);
  background: rgba(74, 222, 128, 0.08);
  transform: translateY(-1px);
}

.layer-move-btn {
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #9ca3af;
  border-radius: 0.5rem;
  padding: 0.15rem 0.45rem;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  transition: background-color 160ms ease, color 160ms ease, border-color 160ms ease;
}

.layer-move-btn:hover:not(:disabled) {
  background: rgba(74, 222, 128, 0.12);
  border-color: rgba(74, 222, 128, 0.28);
  color: #d1fae5;
}

.layer-move-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
</style>
