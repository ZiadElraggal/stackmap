<template>
  <div class="relative" ref="searchRef">
    <div
      class="flex items-center gap-2 bg-[#1a1a2e]/90 backdrop-blur-lg border rounded-xl px-3 py-1.5 text-sm shadow-lg shadow-black/20 transition-all duration-150"
      :class="focused ? 'border-blue-500/40 w-72' : 'border-white/[0.08] w-56'"
    >
      <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.5" class="text-gray-500 flex-shrink-0">
        <circle cx="5.5" cy="5.5" r="4" /><path d="M8.5 8.5L12 12" />
      </svg>
      <input
        ref="inputRef"
        v-model="query"
        type="text"
        placeholder="Search resources..."
        class="bg-transparent text-gray-300 placeholder-gray-600 outline-none flex-1 font-mono text-xs min-w-0"
        @focus="focused = true"
        @blur="onBlur"
        @input="onSearch"
        @keydown.enter="selectTopResult"
        @keydown.escape="clearSearch"
        @keydown.down.prevent="moveSelection(1)"
        @keydown.up.prevent="moveSelection(-1)"
      />
      <span v-if="!query && !focused" class="text-gray-600 text-[10px] flex-shrink-0 font-mono">/</span>
      <span v-if="query" class="text-gray-600 cursor-pointer text-xs flex-shrink-0 hover:text-gray-400 transition-colors" @click="clearSearch">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 2l6 6M8 2l-6 6"/></svg>
      </span>
    </div>

    <!-- Results dropdown -->
    <Transition name="dropdown">
      <div
        v-if="focused && results.length > 0"
        class="absolute top-full left-0 right-0 mt-1.5 bg-[#1a1a2e]/95 backdrop-blur-lg border border-white/[0.08] rounded-xl shadow-2xl shadow-black/40 z-50 max-h-64 overflow-y-auto py-1"
      >
        <div
          v-for="(result, i) in results"
          :key="result.item.id"
          :class="[
            'flex items-center gap-2.5 px-3 py-2 cursor-pointer text-xs mx-1 rounded-lg transition-colors',
            i === selectedIndex ? 'bg-white/10' : 'hover:bg-white/5',
          ]"
          @mousedown.prevent="selectResult(result.item)"
        >
          <span
            class="w-5 h-5 rounded flex-shrink-0 flex items-center justify-center text-[10px]"
            :style="{ backgroundColor: `${CATEGORY_COLORS[result.item.category] || '#9ca3af'}15`, color: CATEGORY_COLORS[result.item.category] || '#9ca3af' }"
          >
            <svg width="11" height="11" viewBox="0 0 24 24"><g v-html="CATEGORY_ICONS[result.item.category] || CATEGORY_ICONS.other" /></svg>
          </span>
          <span class="text-gray-300 font-mono truncate">{{ result.item.name }}</span>
          <span class="text-gray-600 ml-auto flex-shrink-0 text-[10px]">{{ shortType(result.item.resource_type) }}</span>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import Fuse from 'fuse.js'
import { useGraphStore, type StackMapNode } from '~/stores/graph'
import { CATEGORY_COLORS, CATEGORY_ICONS } from '~/composables/useGraph'

const store = useGraphStore()
const query = ref('')
const focused = ref(false)
const selectedIndex = ref(0)
const inputRef = ref<HTMLInputElement>()
const searchRef = ref<HTMLDivElement>()

const fuse = computed(() => {
  return new Fuse(store.nodes, {
    keys: ['name', 'resource_type', 'tags.Name', 'tags.Environment'],
    threshold: 0.4,
    includeScore: true,
  })
})

const results = computed(() => {
  if (!query.value) return []
  return fuse.value.search(query.value).slice(0, 10)
})

function onSearch() {
  selectedIndex.value = 0
  store.setSearch(query.value)
}

function selectTopResult() {
  if (results.value.length > 0) {
    selectResult(results.value[selectedIndex.value].item)
  }
}

function selectResult(node: StackMapNode) {
  store.selectNode(node.id)
  query.value = ''
  focused.value = false
  inputRef.value?.blur()

  // Pan to node
  emit('panTo', node.id)
}

function clearSearch() {
  query.value = ''
  store.setSearch('')
  selectedIndex.value = 0
  inputRef.value?.blur()
  focused.value = false
}

function moveSelection(delta: number) {
  const len = results.value.length
  if (len === 0) return
  selectedIndex.value = (selectedIndex.value + delta + len) % len
}

function onBlur() {
  // Delay to allow click on results
  setTimeout(() => { focused.value = false }, 150)
}

function shortType(type: string) {
  return type.replace('aws_', '').replace(/_/g, ' ')
}

const emit = defineEmits<{
  panTo: [nodeId: string]
}>()

// Expose focus method for keyboard shortcut
defineExpose({
  focus: () => inputRef.value?.focus(),
})
</script>

<style scoped>
.dropdown-enter-active { transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1); }
.dropdown-leave-active { transition: all 0.1s ease; }
.dropdown-enter-from { opacity: 0; transform: translateY(-4px) scale(0.98); }
.dropdown-leave-to { opacity: 0; transform: translateY(-2px); }
</style>
