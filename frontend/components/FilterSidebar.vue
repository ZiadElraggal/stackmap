<template>
  <div
    :class="[
      'fixed left-0 top-0 h-full bg-[#12121a] border-r border-white/10 z-40 transition-all duration-200 flex flex-col',
      collapsed ? 'w-10' : 'w-64',
    ]"
  >
    <button
      class="h-8 flex items-center justify-center text-gray-500 hover:text-gray-300 border-b border-white/10 text-xs"
      @click="collapsed = !collapsed"
    >
      {{ collapsed ? '▶' : '◀ Filters' }}
    </button>

    <div v-if="!collapsed" class="flex-1 overflow-y-auto p-3 transition-opacity duration-150 opacity-100">
      <section class="pb-4 border-b border-white/5">
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
      </section>

      <section class="py-4 border-b border-white/5">
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">Categories</h3>
        <div class="space-y-1">
          <button
            v-for="cat in categories"
            :key="cat.name"
            class="w-full flex items-center gap-2 text-xs cursor-pointer hover:bg-white/5 rounded px-1 py-1"
            @click="store.toggleCategory(cat.name)"
          >
            <span class="icon-wrap" :style="{ color: cat.color }">
              <svg width="13" height="13" viewBox="0 0 24 24">
                <g v-html="iconPath(cat.name)" />
              </svg>
            </span>
            <span class="text-gray-300 truncate">{{ cat.name }}</span>
            <span class="text-gray-600 ml-auto">{{ cat.count }}</span>
            <span class="toggle" :class="{ on: store.categoryFilters[cat.name] !== false }" :style="{ '--toggle-color': cat.color }">
              <span class="knob" />
            </span>
          </button>
        </div>
      </section>

      <section class="py-4 border-b border-white/5">
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">Min importance</h3>
        <svg
          ref="sliderRef"
          class="w-full h-7 cursor-pointer"
          viewBox="0 0 240 28"
          @mousedown="onSliderDown"
        >
          <defs>
            <linearGradient id="importance-track" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#475569" />
              <stop offset="100%" stop-color="#3b82f6" />
            </linearGradient>
          </defs>
          <rect x="8" y="12" width="224" height="4" rx="2" fill="rgba(255,255,255,0.1)" />
          <rect :x="8" y="12" :width="sliderFill" height="4" rx="2" fill="url(#importance-track)" />
          <circle :cx="sliderX" cy="14" r="7" fill="#0f172a" stroke="#60a5fa" stroke-width="2" />
        </svg>
        <div class="flex justify-between text-xs text-gray-600 mt-1">
          <span>All</span>
          <span>{{ minWeight }}</span>
          <span>Key only</span>
        </div>
      </section>

      <section v-if="store.groups.length > 0" class="py-4 border-b border-white/5">
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">Groups</h3>
        <div class="space-y-1">
          <div
            v-for="group in topGroups"
            :key="group.id"
            class="text-xs text-gray-400 px-1 py-1"
          >
            <span class="text-gray-500">{{ group.group_type }}:</span>
            {{ group.name }}
            <span class="text-gray-600">({{ group.children.length }})</span>
          </div>
        </div>
      </section>

      <section class="pt-4">
        <button
          class="w-full text-xs text-gray-500 hover:text-gray-300 border border-white/10 rounded px-2 py-1.5 transition"
          @click="resetFilters"
        >
          Reset all filters
        </button>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onUnmounted } from 'vue'
import { useGraphStore } from '~/stores/graph'
import { CATEGORY_COLORS, CATEGORY_ICONS } from '~/composables/useGraph'

const store = useGraphStore()
const collapsed = ref(false)
const minWeight = ref(1)
const sliderRef = ref<SVGElement>()

const categories = computed(() => {
  const counts: Record<string, number> = {}
  for (const n of store.graphNodes) {
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

const topGroups = computed(() => store.groups.filter(g => g.parent === null))

const sliderX = computed(() => 8 + ((minWeight.value - 1) / 4) * 224)
const sliderFill = computed(() => Math.max(0, sliderX.value - 8))

function iconPath(category: string): string {
  return CATEGORY_ICONS[category] || CATEGORY_ICONS.other
}

function setWeightFromClientX(clientX: number) {
  const rect = sliderRef.value?.getBoundingClientRect()
  if (!rect) return
  const ratio = Math.min(1, Math.max(0, (clientX - rect.left - 8) / 224))
  const val = 1 + Math.round(ratio * 4)
  minWeight.value = val
  store.setMinWeight(val)
}

function onSliderDown(e: MouseEvent) {
  setWeightFromClientX(e.clientX)
  const onMove = (ev: MouseEvent) => setWeightFromClientX(ev.clientX)
  const onUp = () => {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
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

onUnmounted(() => {
  // no-op cleanup guard for drag listeners in case component unmounts mid-drag
  window.onmouseup = null
})
</script>

<style scoped>
.toggle {
  width: 24px;
  height: 14px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.1);
  position: relative;
  transition: all 150ms ease;
}

.toggle .knob {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #cbd5e1;
  position: absolute;
  top: 1px;
  left: 1px;
  transition: all 150ms ease;
}

.toggle.on {
  background: color-mix(in srgb, var(--toggle-color) 40%, transparent);
}

.toggle.on .knob {
  left: 11px;
  background: var(--toggle-color);
}

.icon-wrap {
  width: 14px;
  height: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
</style>
