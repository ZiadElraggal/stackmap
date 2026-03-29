<template>
  <div
    :class="[
      'fixed left-0 top-0 h-full bg-[#12121a] border-r border-white/10 z-40 transition-all duration-200 flex flex-col',
      collapsed ? 'w-10' : 'w-60',
    ]"
  >
    <!-- Collapse toggle -->
    <button
      class="h-8 flex items-center justify-center text-gray-500 hover:text-gray-300 border-b border-white/10 text-xs"
      @click="collapsed = !collapsed"
    >
      {{ collapsed ? '▶' : '◀ Filters' }}
    </button>

    <div v-if="!collapsed" class="flex-1 overflow-y-auto p-3 space-y-4">
      <!-- View mode -->
      <div>
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">View</h3>
        <div class="inline-flex rounded border border-white/10 overflow-hidden text-xs">
          <button
            class="px-2 py-1 transition"
            :class="store.viewMode === 'architecture' ? 'bg-blue-500/20 text-blue-400' : 'bg-transparent text-gray-400 hover:bg-white/5'"
            @click="store.setViewMode('architecture')"
          >
            Architecture
          </button>
          <button
            class="px-2 py-1 transition border-l border-white/10"
            :class="store.viewMode === 'raw' ? 'bg-blue-500/20 text-blue-400' : 'bg-transparent text-gray-400 hover:bg-white/5'"
            @click="store.setViewMode('raw')"
          >
            Terraform raw
          </button>
        </div>
      </div>

      <!-- Category filters -->
      <div>
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">Categories</h3>
        <div class="space-y-1">
          <label
            v-for="cat in categories"
            :key="cat.name"
            class="flex items-center gap-2 text-xs cursor-pointer hover:bg-white/5 rounded px-1 py-0.5"
          >
            <input
              type="checkbox"
              :checked="store.categoryFilters[cat.name] !== false"
              class="rounded border-gray-600 bg-transparent accent-current"
              :style="{ accentColor: cat.color }"
              @change="store.toggleCategory(cat.name)"
            />
            <span
              class="w-2 h-2 rounded-full flex-shrink-0"
              :style="{ backgroundColor: cat.color }"
            />
            <span class="text-gray-300">{{ cat.name }}</span>
            <span class="text-gray-600 ml-auto">{{ cat.count }}</span>
          </label>
        </div>
      </div>

      <!-- Weight slider -->
      <div>
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">
          Min importance
        </h3>
        <input
          type="range"
          min="1"
          max="5"
          :value="minWeight"
          class="w-full accent-blue-500"
          @input="onWeightChange"
        />
        <div class="flex justify-between text-xs text-gray-600 mt-1">
          <span>All</span>
          <span>{{ minWeight }}</span>
          <span>Key only</span>
        </div>
      </div>

      <!-- Groups -->
      <div v-if="store.groups.length > 0">
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">Groups</h3>
        <div class="space-y-1">
          <div
            v-for="group in topGroups"
            :key="group.id"
            class="text-xs text-gray-400 px-1 py-0.5"
          >
            <span class="text-gray-500">{{ group.group_type }}:</span>
            {{ group.name }}
            <span class="text-gray-600">({{ group.children.length }})</span>
          </div>
        </div>
      </div>

      <!-- Reset -->
      <button
        class="w-full text-xs text-gray-500 hover:text-gray-300 border border-white/10 rounded px-2 py-1.5 transition"
        @click="resetFilters"
      >
        Reset all filters
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useGraphStore } from '~/stores/graph'
import { CATEGORY_COLORS } from '~/composables/useGraph'

const store = useGraphStore()
const collapsed = ref(false)
const minWeight = ref(1)

const categories = computed(() => {
  const counts: Record<string, number> = {}
  for (const n of store.nodes) {
    counts[n.category] = (counts[n.category] || 0) + 1
  }
  return Object.entries(counts)
    .map(([name, count]) => ({
      name,
      count,
      color: CATEGORY_COLORS[name] || '#9ca3af',
    }))
    .sort((a, b) => b.count - a.count)
})

const topGroups = computed(() =>
  store.groups.filter(g => g.parent === null)
)

function onWeightChange(e: Event) {
  const val = parseInt((e.target as HTMLInputElement).value)
  minWeight.value = val
  store.setMinWeight(val)
}

function resetFilters() {
  for (const cat of categories.value) {
    if (store.categoryFilters[cat.name] === false) {
      store.toggleCategory(cat.name)
    }
  }
  minWeight.value = 1
  store.setMinWeight(1)
  store.setSearch('')
}
</script>
