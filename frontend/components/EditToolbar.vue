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

      <!-- Actions -->
      <template v-if="!store.connectingFromNodeId">
        <button
          class="edit-btn"
          title="Add a custom component"
          @click="showAddDialog = true"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="6.5" y1="2" x2="6.5" y2="11"/><line x1="2" y1="6.5" x2="11" y2="6.5"/></svg>
          <span>Add Node</span>
        </button>

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
          v-if="store.hiddenNodeIds.length > 0"
          class="edit-btn"
          @click="store.showAllNodes()"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M1 6.5s2.5-4 5.5-4 5.5 4 5.5 4-2.5 4-5.5 4-5.5-4-5.5-4z"/><circle cx="6.5" cy="6.5" r="1.5"/></svg>
          <span>Show All ({{ store.hiddenNodeIds.length }})</span>
        </button>

        <button
          v-if="hasAnyEdits"
          class="edit-btn text-red-400 hover:!bg-red-500/15"
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
          <div class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-300 font-mono">
            {{ selectedTemplate?.tier || 'backend' }} · {{ selectedTemplate?.category || 'other' }}
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
import { ref, computed } from 'vue'
import { USER_NODE_TEMPLATES } from '~/composables/useGraph'
import { useGraphStore } from '~/stores/graph'

const store = useGraphStore()

const showAddDialog = ref(false)
const newNodeName = ref('')
const newNodeTemplateId = ref('lambda')
const userNodeTemplates = USER_NODE_TEMPLATES

const selectedTemplate = computed(() =>
  userNodeTemplates.find(template => template.id === newNodeTemplateId.value) || userNodeTemplates[0]
)

const hasAnyEdits = computed(() =>
  store.hiddenNodeIds.length > 0 || store.userEdges.length > 0 || store.userNodes.length > 0
)

function addNode() {
  if (!newNodeName.value.trim()) return
  const template = selectedTemplate.value
  store.addUserNode(newNodeName.value.trim(), {
    resourceType: template.resourceType,
    category: template.category,
    tier: template.tier,
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
</script>

<style scoped>
.edit-btn {
  @apply flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-mono text-gray-300 transition;
  @apply hover:bg-white/5 hover:text-white;
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

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

select option {
  background: #12121a;
  color: #e5e7eb;
}
</style>
