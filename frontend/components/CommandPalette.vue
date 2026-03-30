<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 bg-black/60 z-[100] flex items-start justify-center pt-[20vh]"
        @click.self="close"
        @keydown.escape="close"
      >
        <div class="w-[520px] bg-[#1a1a2e]/95 backdrop-blur-xl border border-white/[0.08] rounded-2xl shadow-2xl shadow-black/50 overflow-hidden">
          <!-- Input -->
          <div class="flex items-center gap-3 px-4 py-3.5 border-b border-white/[0.06]">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" class="text-gray-500 flex-shrink-0">
              <circle cx="7" cy="7" r="5" /><path d="M11 11l4 4" />
            </svg>
            <input
              ref="inputRef"
              v-model="query"
              type="text"
              placeholder="Search resources or run a command..."
              class="bg-transparent text-gray-200 placeholder-gray-600 outline-none flex-1 text-sm"
              @keydown.enter="executeSelected"
              @keydown.down.prevent="moveSelection(1)"
              @keydown.up.prevent="moveSelection(-1)"
            />
            <span class="text-[10px] text-gray-600 font-mono flex-shrink-0 px-1.5 py-0.5 rounded bg-white/[0.04] border border-white/[0.06]">esc</span>
          </div>

          <!-- Results -->
          <div class="max-h-72 overflow-y-auto">
            <!-- Commands -->
            <div v-if="filteredCommands.length > 0">
              <div class="px-3 py-1.5 text-xs text-gray-600 uppercase tracking-wider">Commands</div>
              <div
                v-for="(cmd, i) in filteredCommands"
                :key="cmd.id"
                :class="[
                  'flex items-center gap-3 px-4 py-2 cursor-pointer text-sm',
                  selectedIndex === i ? 'bg-white/10' : 'hover:bg-white/5',
                ]"
                @click="executeCommand(cmd)"
              >
                <span class="text-gray-500">{{ cmd.icon }}</span>
                <span class="text-gray-300">{{ cmd.label }}</span>
                <span v-if="cmd.shortcut" class="text-gray-600 text-xs ml-auto font-mono">{{ cmd.shortcut }}</span>
              </div>
            </div>

            <!-- Nodes -->
            <div v-if="filteredNodes.length > 0">
              <div class="px-3 py-1.5 text-xs text-gray-600 uppercase tracking-wider">Resources</div>
              <div
                v-for="(result, i) in filteredNodes"
                :key="result.item.id"
                :class="[
                  'flex items-center gap-3 px-4 py-2 cursor-pointer text-sm',
                  selectedIndex === filteredCommands.length + i ? 'bg-white/10' : 'hover:bg-white/5',
                ]"
                @click="selectNode(result.item)"
              >
                <span
                  class="w-2 h-2 rounded-full flex-shrink-0"
                  :style="{ backgroundColor: CATEGORY_COLORS[result.item.category] || '#9ca3af' }"
                />
                <span class="text-gray-300 font-mono">{{ result.item.name }}</span>
                <span class="text-gray-600 text-xs ml-auto">{{ shortType(result.item.resource_type) }}</span>
              </div>
            </div>

            <div v-if="filteredCommands.length === 0 && filteredNodes.length === 0" class="px-4 py-6 text-center text-gray-600 text-sm">
              No results found
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import Fuse from 'fuse.js'
import { useGraphStore, type StackMapNode } from '~/stores/graph'
import { CATEGORY_COLORS } from '~/composables/useGraph'

const store = useGraphStore()
const open = ref(false)
const query = ref('')
const selectedIndex = ref(0)
const inputRef = ref<HTMLInputElement>()

interface Command {
  id: string
  label: string
  icon: string
  shortcut?: string
  action: () => void
}

const commands: Command[] = [
  { id: 'reset', label: 'Reset all filters', icon: '↺', action: () => store.resetFilters() },
  { id: 'fit', label: 'Fit to screen', icon: '⊡', shortcut: '0', action: () => emit('fitToScreen') },
  { id: 'compute', label: 'Show only compute', icon: 'λ', action: () => filterOnly('compute') },
  { id: 'database', label: 'Show only database', icon: '⊡', action: () => filterOnly('database') },
  { id: 'storage', label: 'Show only storage', icon: '⬡', action: () => filterOnly('storage') },
  { id: 'network', label: 'Show only network', icon: '◈', action: () => filterOnly('network') },
  { id: 'deselect', label: 'Deselect node', icon: '✕', shortcut: 'Esc', action: () => store.selectNode(null) },
]

const fuse = computed(() => {
  return new Fuse(store.nodes, {
    keys: ['name', 'resource_type'],
    threshold: 0.4,
  })
})

const filteredCommands = computed(() => {
  if (!query.value) return commands
  const q = query.value.toLowerCase()
  return commands.filter(c => c.label.toLowerCase().includes(q))
})

const filteredNodes = computed(() => {
  if (!query.value) return []
  return fuse.value.search(query.value).slice(0, 8)
})

const totalItems = computed(() => filteredCommands.value.length + filteredNodes.value.length)

function moveSelection(delta: number) {
  if (totalItems.value === 0) return
  selectedIndex.value = (selectedIndex.value + delta + totalItems.value) % totalItems.value
}

function executeSelected() {
  if (selectedIndex.value < filteredCommands.value.length) {
    executeCommand(filteredCommands.value[selectedIndex.value])
  } else {
    const nodeIdx = selectedIndex.value - filteredCommands.value.length
    if (nodeIdx < filteredNodes.value.length) {
      selectNode(filteredNodes.value[nodeIdx].item)
    }
  }
}

function executeCommand(cmd: Command) {
  cmd.action()
  close()
}

function selectNode(node: StackMapNode) {
  store.selectNode(node.id)
  emit('panTo', node.id)
  close()
}

function filterOnly(category: string) {
  for (const cat of Object.keys(store.categoryFilters)) {
    store.categoryFilters[cat] = cat === category
  }
}

function shortType(type: string) {
  return type.replace('aws_', '').replace(/_/g, ' ')
}

function toggle() {
  open.value = !open.value
  if (open.value) {
    query.value = ''
    selectedIndex.value = 0
    nextTick(() => inputRef.value?.focus())
  }
}

function close() {
  open.value = false
  query.value = ''
}

watch(query, () => { selectedIndex.value = 0 })

const emit = defineEmits<{
  panTo: [nodeId: string]
  fitToScreen: []
}>()

defineExpose({ toggle })
</script>

<style scoped>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
