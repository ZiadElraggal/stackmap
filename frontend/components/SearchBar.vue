<template>
  <div class="relative" ref="searchRef">
    <div
      class="flex items-center gap-2 bg-[#1a1a2e] border border-white/10 rounded-lg px-3 py-1.5 text-sm"
      :class="{ 'border-blue-500/50': focused }"
    >
      <span class="text-gray-500 text-xs">⌘K</span>
      <input
        ref="inputRef"
        v-model="query"
        type="text"
        placeholder="Search resources..."
        class="bg-transparent text-gray-300 placeholder-gray-600 outline-none flex-1 font-mono text-xs w-40"
        @focus="focused = true"
        @blur="onBlur"
        @input="onSearch"
        @keydown.enter="selectTopResult"
        @keydown.escape="clearSearch"
        @keydown.down.prevent="moveSelection(1)"
        @keydown.up.prevent="moveSelection(-1)"
      />
      <span v-if="query" class="text-gray-600 cursor-pointer text-xs" @click="clearSearch">✕</span>
    </div>

    <!-- Results dropdown -->
    <div
      v-if="focused && results.length > 0"
      class="absolute top-full left-0 right-0 mt-1 bg-[#1a1a2e] border border-white/10 rounded-lg shadow-xl z-50 max-h-64 overflow-y-auto"
    >
      <div
        v-for="(result, i) in results"
        :key="result.item.id"
        :class="[
          'flex items-center gap-2 px-3 py-2 cursor-pointer text-xs',
          i === selectedIndex ? 'bg-white/10' : 'hover:bg-white/5',
        ]"
        @mousedown.prevent="selectResult(result.item)"
      >
        <span
          class="w-2 h-2 rounded-full flex-shrink-0"
          :style="{ backgroundColor: CATEGORY_COLORS[result.item.category] || '#9ca3af' }"
        />
        <span class="text-gray-300 font-mono truncate">{{ result.item.name }}</span>
        <span class="text-gray-600 ml-auto flex-shrink-0">{{ shortType(result.item.resource_type) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import Fuse from 'fuse.js'
import { useGraphStore, type StackMapNode } from '~/stores/graph'
import { CATEGORY_COLORS } from '~/composables/useGraph'

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
