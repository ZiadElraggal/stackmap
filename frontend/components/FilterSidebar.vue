<template>
  <div
    :class="[
      'fixed left-0 top-0 h-full border-r z-40 transition-all duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] flex flex-col',
      collapsed ? 'w-14' : 'w-[18rem]',
    ]"
    style="backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); background: linear-gradient(180deg, rgba(18, 18, 26, 0.97), rgba(10, 10, 15, 0.96)); border-color: var(--sm-border); box-shadow: 1px 0 14px rgba(0,0,0,0.28)"
  >
    <button
      class="sidebar-collapse-btn"
      @click="collapsed = !collapsed"
    >
      <svg
        width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"
        class="transition-transform duration-200" :class="collapsed ? '' : 'rotate-180'"
      ><path d="M5 3l4 4-4 4"/></svg>
      <span v-if="!collapsed" class="ml-2 tracking-wide font-medium">Workspace</span>
    </button>

    <div v-if="collapsed" class="flex flex-1 flex-col items-center gap-3 px-2 py-4">
      <div class="collapsed-mascot-shell">
        <PixelMascot :size="28" state="idle" :animate="true" />
      </div>
      <div class="collapsed-pill">{{ visibleResourceCount }}</div>
      <div class="collapsed-rail">
        <button class="collapsed-icon-btn" title="Architecture view" @click="store.setViewMode('architecture')">A</button>
        <button
          v-if="store.shouldUseComponentLanding || store.activeAccountId"
          class="collapsed-icon-btn"
          title="Components view"
          @click="store.setViewMode('components')"
        >C</button>
        <button class="collapsed-icon-btn" title="Raw view" @click="store.setViewMode('raw')">R</button>
      </div>
    </div>

    <div v-if="!collapsed" class="flex-1 overflow-y-auto p-4 transition-opacity duration-150 opacity-100">
      <section class="hero-card">
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="text-[10px] font-mono uppercase tracking-[0.18em] text-emerald-400">StackMap</div>
            <h2 class="mt-2 text-sm font-semibold text-white">Infrastructure workspace</h2>
            <p class="mt-2 text-xs leading-relaxed text-gray-400">
              Filter the live map, switch views, and trim noise before editing or presenting.
            </p>
          </div>
          <div class="mascot-shell">
            <PixelMascot :size="42" :state="store.editMode ? 'scanning' : 'idle'" :animate="true" />
          </div>
        </div>
        <div class="mt-4 grid grid-cols-3 gap-2">
          <div class="summary-chip">
            <span class="summary-chip__label">Visible</span>
            <span class="summary-chip__value">{{ visibleResourceCount }}</span>
          </div>
          <div class="summary-chip">
            <span class="summary-chip__label">Links</span>
            <span class="summary-chip__value">{{ visibleEdgeCount }}</span>
          </div>
          <div class="summary-chip">
            <span class="summary-chip__label">View</span>
            <span class="summary-chip__value">{{ activeViewLabel }}</span>
          </div>
        </div>
      </section>

      <section class="sidebar-section">
        <div class="section-heading">
          <span>View</span>
          <span class="section-heading__meta">{{ sourceLabel }}</span>
        </div>
        <div class="grid grid-cols-2 gap-2 text-xs">
          <button
            v-if="store.shouldUseComponentLanding || store.activeAccountId"
            class="view-btn"
            :class="store.viewMode === 'components' ? 'view-btn--active' : 'view-btn--inactive'"
            @click="store.setViewMode('components')"
          >
            Components
          </button>
          <button
            class="view-btn"
            :class="store.viewMode === 'architecture' ? 'view-btn--active' : 'view-btn--inactive'"
            @click="store.setViewMode('architecture')"
          >
            Architecture
          </button>
          <button
            class="view-btn"
            :class="store.viewMode === 'raw' ? 'view-btn--active' : 'view-btn--inactive'"
            @click="store.setViewMode('raw')"
          >
            Raw
          </button>
          <button
            v-if="store.hasOrganizationData"
            class="view-btn flex items-center gap-1"
            :class="store.viewMode === 'organization' ? 'view-btn--active' : 'view-btn--inactive'"
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

      <section class="sidebar-section">
        <div class="section-heading">
          <span>Categories</span>
          <span class="section-heading__meta">{{ categories.length }}</span>
        </div>
        <div class="space-y-0.5">
          <button
            v-for="cat in categories"
            :key="cat.name"
            class="filter-row"
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

      <section v-if="edgeTypes.length > 0" class="sidebar-section">
        <div class="section-heading">
          <span>Relationships</span>
          <span class="section-heading__meta">{{ edgeTypes.length }}</span>
        </div>
        <div class="mb-3 flex flex-wrap gap-2">
          <button
            v-for="preset in relationshipPresets"
            :key="preset.id"
            class="rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-1 text-[10px] font-mono text-gray-400 transition hover:bg-white/[0.06] hover:text-white"
            @click="store.setEdgeTypePreset(preset.id)"
          >
            {{ preset.label }}
          </button>
        </div>
        <div class="space-y-1">
          <button
            v-for="edgeType in edgeTypes"
            :key="edgeType.id"
            class="filter-row"
            @click="store.toggleEdgeType(edgeType.id)"
          >
            <span
              class="inline-flex h-3 w-5 rounded-full"
              :style="{ backgroundColor: EDGE_COLORS[edgeType.id] || '#64748b', opacity: 0.9 }"
            />
            <div class="min-w-0 flex-1 text-left">
              <div class="truncate text-xs text-gray-300">{{ edgeTypeLabel(edgeType.id) }}</div>
              <div class="text-[10px] font-mono uppercase tracking-wider text-gray-600">{{ edgeKindLabel(edgeType.kind) }}</div>
            </div>
            <span class="text-gray-600">{{ edgeType.count }}</span>
            <span class="toggle" :class="{ on: store.edgeTypeFilters[edgeType.id] !== false }" :style="{ '--toggle-color': EDGE_COLORS[edgeType.id] || '#64748b' }">
              <span class="knob" />
            </span>
          </button>
        </div>
      </section>

      <section class="sidebar-section">
        <div class="section-heading">
          <span>Min importance</span>
          <span class="section-heading__meta">{{ minWeight }}</span>
        </div>
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

      <section v-if="store.graphGroups.length > 0" class="sidebar-section">
        <div class="section-heading">
          <span>Groups</span>
          <span class="section-heading__meta">{{ topGroups.length }}</span>
        </div>
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

      <section v-if="store.hasOrganizationData" class="sidebar-section">
        <div class="section-heading mb-2">
          <div class="flex items-center gap-1.5">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.7">
              <path d="M4 21V8l8-5 8 5v13M9 21v-5h6v5"/>
            </svg>
            <span>Accounts</span>
          </div>
          <span class="section-heading__meta">{{ accountCount }}</span>
        </div>
        <div class="space-y-0.5">
          <button
            class="org-row"
            :class="store.activeAccountId === null && store.activeOrgGroupId === null ? 'org-row--active' : 'org-row--inactive'"
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
              class="w-full text-left text-xs rounded-xl py-1.5 transition flex items-center gap-1.5"
              :class="[
                item.account_id && store.activeAccountId === item.account_id
                  ? 'bg-cyan-500/10 text-cyan-300 border border-cyan-400/15'
                  : store.activeOrgGroupId === item.id
                    ? 'bg-amber-500/10 text-amber-300 border border-amber-400/15'
                    : 'text-gray-400 hover:bg-white/5 border border-transparent',
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

      <section v-if="store.hasOrganizationData" class="sidebar-section">
        <div class="section-heading">
          <span>Cross-account</span>
          <span class="section-heading__meta">{{ store.showCrossAccountEdges ? 'On' : 'Off' }}</span>
        </div>
        <button
          class="filter-row"
          @click="store.setShowCrossAccountEdges(!store.showCrossAccountEdges)"
        >
          <span class="text-gray-300">Show cross-account links</span>
          <span class="toggle" :class="{ on: store.showCrossAccountEdges }" style="--toggle-color: #f97316">
            <span class="knob" />
          </span>
        </button>
      </section>

      <section v-if="store.shouldUseComponentLanding || store.activeComponentId" class="sidebar-section">
        <div class="section-heading">
          <span>Components</span>
          <span class="section-heading__meta">Focus</span>
        </div>
        <div class="space-y-2">
          <button
            class="filter-row"
            @click="store.setShowUnlinkedResources(!store.showUnlinkedResources)"
          >
            <span class="text-gray-300">Show unlinked resources</span>
            <span class="toggle" :class="{ on: store.showUnlinkedResources }" style="--toggle-color: #38bdf8">
              <span class="knob" />
            </span>
          </button>
          <button
            class="filter-row"
            @click="store.setShowWeaklyLinkedComponents(!store.showWeaklyLinkedComponents)"
          >
            <span class="text-gray-300">Show weakly linked cards</span>
            <span class="toggle" :class="{ on: store.showWeaklyLinkedComponents }" style="--toggle-color: #f59e0b">
              <span class="knob" />
            </span>
          </button>
          <button
            class="filter-row"
            @click="store.setCollapseNetworkScaffolding(!store.collapseNetworkScaffolding)"
          >
            <span class="text-gray-300">Collapse network scaffolding</span>
            <span class="toggle" :class="{ on: store.collapseNetworkScaffolding }" style="--toggle-color: #818cf8">
              <span class="knob" />
            </span>
          </button>
        </div>
      </section>

      <section class="sidebar-section">
        <div class="section-heading">
          <span>Insights</span>
        </div>
        <div class="space-y-2">
          <button
            class="filter-row"
            @click="store.toggleCosts()"
          >
            <span class="text-gray-300">Cost estimate</span>
            <span class="toggle" :class="{ on: store.showCosts }" style="--toggle-color: #4ADE80">
              <span class="knob" />
            </span>
          </button>
          <button
            v-if="store.metadata?.drift_summary"
            class="filter-row"
            @click="store.setDriftMode(!store.driftMode)"
          >
            <span class="text-gray-300">Drift analysis</span>
            <span class="toggle" :class="{ on: store.driftMode }" style="--toggle-color: #f59e0b">
              <span class="knob" />
            </span>
          </button>
        </div>
      </section>
      <FindingsPanel />

      <section class="pt-2">
        <button
          class="w-full rounded-xl border border-white/[0.08] bg-white/[0.03] px-3 py-2.5 text-xs text-gray-400 transition-all duration-150 hover:border-white/[0.12] hover:bg-white/[0.06] hover:text-white active:scale-[0.98]"
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
import { CATEGORY_COLORS, CATEGORY_ICONS, EDGE_COLORS } from '~/composables/useGraph'

const store = useGraphStore()
const collapsed = ref(false)
const minWeight = ref(1)
const sliderRef = ref<SVGElement>()

const categories = computed(() => {
  const counts: Record<string, number> = {}
  const sourceNodes = store.viewMode === 'components' ? store.architectureSourceNodes : store.graphNodes
  for (const n of sourceNodes) {
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
const visibleResourceCount = computed(() => store.visibleNodes.length)
const visibleEdgeCount = computed(() => store.visibleEdges.length)
const edgeTypes = computed(() => store.availableEdgeTypes)
const activeViewLabel = computed(() => {
  if (store.viewMode === 'architecture') return 'Arch'
  if (store.viewMode === 'components') return 'Comp'
  if (store.viewMode === 'organization') return 'Org'
  return 'Raw'
})
const sourceLabel = computed(() => {
  const sourceType = String(store.metadata?.source_type || '').replace(/_/g, ' ')
  return sourceType || 'workspace'
})
const relationshipPresets = [
  { id: 'all', label: 'All' },
  { id: 'manual', label: 'Manual Only' },
  { id: 'inferred', label: 'Inferred Only' },
  { id: 'presentation', label: 'Presentation' },
] as const

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

function edgeTypeLabel(edgeType: string): string {
  return edgeType
    .replace(/^manual_/, '')
    .replace(/cross_account_reference/g, 'cross-account')
    .replace(/_/g, ' ')
}

function edgeKindLabel(kind: 'manual' | 'cross-account' | 'inferred'): string {
  if (kind === 'manual') return 'manual'
  if (kind === 'cross-account') return 'cross-account'
  return 'inferred'
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
  store.activeComponentId = null
  store.setActiveOrgGroup(null)
  store.setActiveAccount(null)
  if (store.hasOrganizationData && store.metadata?.scan_mode === 'organization') {
    store.setViewMode('organization')
    return
  }
  if (store.shouldUseComponentLanding) {
    store.setViewMode('components')
    return
  }
  store.setViewMode('architecture')
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
.sidebar-collapse-btn {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(156, 163, 175, 0.9);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  font-size: 12px;
  transition: background-color 150ms ease, color 150ms ease;
}

.sidebar-collapse-btn:hover {
  background: rgba(255,255,255,0.03);
  color: rgba(229, 231, 235, 0.95);
}

.hero-card,
.sidebar-section {
  border: 1px solid rgba(255,255,255,0.06);
  background: rgba(255,255,255,0.025);
  border-radius: 18px;
  padding: 14px;
  margin-bottom: 12px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.02);
}

.mascot-shell,
.collapsed-mascot-shell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  border: 1px solid rgba(74, 222, 128, 0.14);
  background: radial-gradient(circle at 50% 35%, rgba(74,222,128,0.12), rgba(255,255,255,0.02));
}

.mascot-shell {
  padding: 10px;
}

.collapsed-mascot-shell {
  padding: 6px;
}

.summary-chip {
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.05);
  background: rgba(0,0,0,0.22);
  padding: 8px 10px;
}

.summary-chip__label {
  font-size: 9px;
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(107, 114, 128, 0.95);
}

.summary-chip__value {
  font-size: 12px;
  color: rgba(255,255,255,0.95);
}

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(156, 163, 175, 0.92);
}

.section-heading__meta {
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: normal;
  text-transform: none;
  color: rgba(107, 114, 128, 0.95);
}

.view-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.03);
  padding: 7px 10px;
  transition: background-color 150ms ease, color 150ms ease;
}

.view-btn--active {
  background: rgba(74, 222, 128, 0.12);
  color: rgba(167, 243, 208, 0.96);
}

.view-btn--inactive {
  background: transparent;
  color: rgba(156, 163, 175, 0.95);
}

.view-btn--inactive:hover {
  background: rgba(255,255,255,0.05);
  color: rgba(255,255,255,0.92);
}

.filter-row,
.org-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  border-radius: 12px;
  padding: 8px 10px;
  transition: background-color 150ms ease, color 150ms ease, border-color 150ms ease;
  border: 1px solid transparent;
}

.filter-row:hover,
.org-row--inactive:hover {
  background: rgba(255,255,255,0.04);
}

.org-row--active {
  background: rgba(255,255,255,0.05);
  color: rgba(255,255,255,0.95);
  border-color: rgba(255,255,255,0.06);
}

.org-row--inactive {
  color: rgba(156,163,175,0.95);
}

.collapsed-pill {
  min-width: 28px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  padding: 4px 6px;
  text-align: center;
  font-size: 10px;
  font-family: 'JetBrains Mono', monospace;
  color: rgba(229,231,235,0.95);
}

.collapsed-rail {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.collapsed-icon-btn {
  display: inline-flex;
  height: 28px;
  width: 28px;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.03);
  color: rgba(156,163,175,0.95);
  font-size: 10px;
  font-family: 'JetBrains Mono', monospace;
  transition: background-color 150ms ease, color 150ms ease;
}

.collapsed-icon-btn:hover {
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.95);
}

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
