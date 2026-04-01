<template>
  <div
    :class="[
      'fixed left-0 top-0 h-full bg-[#12121a]/95 backdrop-blur-md border-r border-white/[0.06] z-40 transition-all duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] flex flex-col',
      collapsed ? 'w-10' : 'w-64',
    ]"
  >
    <button
      class="h-9 flex items-center justify-center text-gray-500 hover:text-gray-300 border-b border-white/[0.06] text-xs transition-colors"
      @click="collapsed = !collapsed"
    >
      <svg
        width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"
        class="transition-transform duration-200" :class="collapsed ? '' : 'rotate-180'"
      ><path d="M5 3l4 4-4 4"/></svg>
      <span v-if="!collapsed" class="ml-1.5 tracking-wide">Filters</span>
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
            Raw
          </button>
          <button
            v-if="store.hasOrganizationData"
            class="px-2 py-1 transition border-l border-white/10 flex items-center gap-1"
            :class="store.viewMode === 'organization' ? 'bg-blue-500/20 text-blue-400' : 'bg-transparent text-gray-400 hover:bg-white/5'"
            @click="store.setViewMode('organization')"
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
              <rect x="9" y="2" width="6" height="4" rx="1.5"/><rect x="2" y="11" width="6" height="4" rx="1.5"/><rect x="16" y="11" width="6" height="4" rx="1.5"/>
              <path d="M12 6v3M5 11V9h14v2"/>
            </svg>
            Org
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

      <section v-if="store.graphGroups.length > 0" class="py-4 border-b border-white/5">
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">Groups</h3>
        <div class="space-y-1">
          <div
            v-for="group in topGroups"
            :key="group.id"
            class="flex items-center gap-2 text-xs text-gray-400 px-1 py-1"
          >
            <span class="h-1.5 w-1.5 rounded-full shrink-0" :style="{ backgroundColor: groupDotColor(group.group_type) }" />
            <span class="text-gray-500 shrink-0 capitalize">{{ group.group_type }}</span>
            <span class="truncate flex-1">{{ group.name }}</span>
            <span class="text-gray-600 shrink-0">{{ group.children.length }}</span>
          </div>
        </div>
      </section>

      <section v-if="store.hasOrganizationData" class="py-4 border-b border-white/5">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-1.5">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.7">
              <path d="M4 21V8l8-5 8 5v13M9 21v-5h6v5"/>
            </svg>
            <h3 class="text-xs uppercase tracking-wider text-gray-500">Accounts</h3>
          </div>
          <span class="text-[10px] font-mono text-gray-600">{{ accountCount }}</span>
        </div>
        <div class="space-y-0.5">
          <button
            class="w-full text-left text-xs rounded px-2 py-1 transition flex items-center gap-2"
            :class="store.activeAccountId === null && store.activeOrgGroupId === null ? 'bg-white/5 text-white' : 'text-gray-400 hover:bg-white/5'"
            @click="clearOrganizationScope"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.5">
              <circle cx="12" cy="12" r="9"/>
              <path d="M3 12h18M12 3C8 7 8 17 12 21M12 3c4 4 4 14 0 18"/>
            </svg>
            <span class="flex-1">All accounts</span>
            <span class="text-[10px] font-mono text-gray-600">{{ accountCount }}</span>
          </button>
          <div
            v-for="(item, idx) in orgTree"
            :key="item.id"
            class="relative"
          >
            <!-- Vertical tree line: connects to siblings below -->
            <span
              v-if="item.depth > 0"
              class="pointer-events-none absolute"
              :style="{
                left: `${8 + (item.depth - 1) * 14 + 5}px`,
                top: '-2px',
                bottom: hasNextSibling(idx, item.depth) ? '-2px' : '50%',
                width: '1px',
                background: item.depth === 1 ? 'rgba(245,158,11,0.18)' : 'rgba(34,211,238,0.14)',
              }"
            />
            <!-- Horizontal connector nub -->
            <span
              v-if="item.depth > 0"
              class="pointer-events-none absolute"
              :style="{
                left: `${8 + (item.depth - 1) * 14 + 5}px`,
                top: '50%',
                transform: 'translateY(-50%)',
                width: '9px',
                height: '1px',
                background: item.depth === 1 ? 'rgba(245,158,11,0.18)' : 'rgba(34,211,238,0.14)',
              }"
            />
            <button
              class="w-full text-left text-xs rounded py-1 transition flex items-center gap-1.5"
              :class="[
                item.account_id && store.activeAccountId === item.account_id
                  ? 'bg-cyan-500/10 text-cyan-300'
                  : store.activeOrgGroupId === item.id
                    ? 'bg-amber-500/10 text-amber-300'
                    : 'text-gray-400 hover:bg-white/5',
              ]"
              :style="{ paddingLeft: `${8 + item.depth * 14}px`, paddingRight: '8px' }"
              @click="onOrgTreeClick(item)"
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" :style="{ color: orgTypeColor(item.group_type) }" class="shrink-0">
                <g v-html="orgTypeIcon(item.group_type)" />
              </svg>
              <span class="truncate flex-1">{{ item.name }}</span>
              <span v-if="item.account_id" class="text-[9px] font-mono text-gray-600 shrink-0">·{{ item.account_id.slice(-6) }}</span>
            </button>
          </div>
        </div>
      </section>

      <section v-if="store.hasOrganizationData" class="py-4 border-b border-white/5">
        <h3 class="text-xs uppercase tracking-wider text-gray-500 mb-2">Cross-account</h3>
        <button
          class="w-full flex items-center justify-between text-xs rounded px-2 py-1 transition hover:bg-white/5"
          @click="store.setShowCrossAccountEdges(!store.showCrossAccountEdges)"
        >
          <span class="text-gray-300">Show cross-account links</span>
          <span class="toggle" :class="{ on: store.showCrossAccountEdges }" style="--toggle-color: #f97316">
            <span class="knob" />
          </span>
        </button>
      </section>

      <section class="pt-4">
        <button
          class="w-full text-xs text-gray-500 hover:text-gray-300 border border-white/[0.08] rounded-md px-2 py-1.5 transition-all hover:bg-white/[0.03] active:scale-[0.98]"
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

const topGroups = computed(() => store.graphGroups.filter(g => g.parent === null))
const orgTree = computed(() => store.organizationTree)
const accountCount = computed(() => orgTree.value.filter(i => i.group_type === 'account').length)

const ORG_ICONS: Record<string, string> = {
  account:
    '<path d="M4 21V8l8-5 8 5v13M9 21v-5h6v5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  ou:
    '<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" stroke="currentColor" stroke-width="1.5" fill="none"/>',
  organization_root:
    '<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M3 12h18M12 3C8 7 8 17 12 21M12 3c4 4 4 14 0 18" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>',
}

const ORG_TYPE_COLORS: Record<string, string> = {
  account: '#22d3ee',
  ou: '#f59e0b',
  organization_root: '#38bdf8',
}

function orgTypeIcon(groupType: string): string {
  return ORG_ICONS[groupType] ?? ORG_ICONS.account
}

function orgTypeColor(groupType: string): string {
  return ORG_TYPE_COLORS[groupType] ?? '#9ca3af'
}

function hasNextSibling(idx: number, depth: number): boolean {
  for (let i = idx + 1; i < orgTree.value.length; i++) {
    if (orgTree.value[i].depth === depth) return true
    if (orgTree.value[i].depth < depth) return false
  }
  return false
}

function groupDotColor(groupType: string): string {
  if (groupType === 'vpc') return CATEGORY_COLORS.network
  if (groupType === 'subnet') return '#4b5563'
  if (groupType === 'account') return '#22d3ee'
  if (groupType === 'ou') return '#f59e0b'
  if (groupType === 'organization_root') return '#38bdf8'
  return '#6b7280'
}

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

function clearOrganizationScope() {
  store.setActiveOrgGroup(null)
  store.setActiveAccount(null)
}

function onOrgTreeClick(item: { id: string; account_id?: string }) {
  if (item.account_id) {
    if (store.viewMode === 'organization') {
      store.enterAccountArchitecture(item.account_id)
      return
    }
    store.setActiveAccount(item.account_id)
    return
  }
  if (store.viewMode === 'organization') {
    store.setActiveOrgGroup(item.id)
  }
}

// Drag listeners are cleaned up via their own mouseup handlers.
// No global onmouseup clobbering needed.
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
