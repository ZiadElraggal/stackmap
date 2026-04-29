<template>
  <div class="absolute inset-0 z-20 overflow-y-auto px-6 pb-16 pt-24 md:px-10 xl:px-16">
    <div class="pointer-events-none absolute inset-x-0 top-0 h-64 bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.12),transparent_52%),radial-gradient(circle_at_22%_18%,rgba(96,165,250,0.10),transparent_28%)]" />

    <div class="relative mx-auto max-w-5xl">
      <div class="mb-8 rounded-[28px] border border-white/[0.07] bg-[#0f131b]/88 px-6 py-6 shadow-[0_30px_100px_rgba(0,0,0,0.32)] backdrop-blur-md md:px-8">
        <div class="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div class="max-w-3xl">
            <p class="mb-3 text-[10px] font-mono uppercase tracking-[0.32em] text-emerald-300/75">Component View</p>
            <div class="flex items-start gap-4">
              <div class="hidden rounded-2xl border border-emerald-400/10 bg-emerald-500/[0.05] p-3 md:block">
                <PixelMascot :size="52" state="idle" :animate="true" />
              </div>
              <div>
                <h2 class="text-[28px] font-semibold leading-tight tracking-tight text-white md:text-[32px]">
                  Start with the systems, then open the details.
                </h2>
                <p class="mt-3 max-w-2xl text-sm leading-6 text-gray-400">
                  StackMap grouped the current architecture into cleaner service-sized slices so you can orient yourself quickly before diving into a single component.
                </p>
              </div>
            </div>
          </div>

          <div class="rounded-2xl border border-white/[0.06] bg-white/[0.03] px-4 py-3 text-left lg:min-w-[220px] lg:text-right">
            <div class="text-[10px] font-mono uppercase tracking-[0.24em] text-gray-600">Visible Scope</div>
            <div class="mt-2 text-sm font-medium text-white">{{ scopeLabel }}</div>
            <div class="mt-1 text-xs font-mono text-gray-500">{{ totalResources }} resources · {{ totalConnections }} connections</div>
            <button
              class="mt-3 rounded-lg border border-cyan-400/20 bg-cyan-500/10 px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.18em] text-cyan-200 transition hover:border-cyan-300/35 hover:bg-cyan-500/16"
              @click="store.viewAllComponents()"
            >
              View all
            </button>
          </div>
        </div>

        <div class="mt-6 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <div
            v-for="item in overviewItems"
            :key="item.label"
            class="rounded-2xl border border-white/[0.06] bg-white/[0.02] px-4 py-3"
          >
            <div class="text-[10px] font-mono uppercase tracking-[0.22em] text-gray-600">{{ item.label }}</div>
            <div class="mt-2 text-sm font-semibold text-white">{{ item.value }}</div>
            <div v-if="item.detail" class="mt-1 text-xs text-gray-500">{{ item.detail }}</div>
          </div>
        </div>
      </div>

      <section class="mb-10">
        <div class="mb-4 flex items-end justify-between gap-6">
          <div>
            <p class="text-[10px] font-mono uppercase tracking-[0.24em] text-gray-600">Smart Components</p>
            <h3 class="mt-2 text-xl font-semibold text-white">Open a group, or view everything together</h3>
          </div>
          <div class="text-right text-xs font-mono text-gray-500">
            {{ filteredPrimarySummaries.length }} of {{ primarySummaries.length }} service island{{ primarySummaries.length === 1 ? '' : 's' }}
          </div>
        </div>

        <div v-if="parentFilterOptions.length > 1" class="mb-4 flex flex-wrap gap-2">
          <button
            v-for="option in parentFilterOptions"
            :key="option.id"
            class="rounded-lg border px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.16em] transition"
            :class="selectedParentId === option.id
              ? 'border-emerald-300/30 bg-emerald-500/12 text-emerald-200'
              : 'border-white/[0.08] bg-white/[0.03] text-gray-400 hover:border-white/15 hover:text-white'"
            @click="selectedParentId = option.id"
          >
            {{ option.label }} · {{ option.count }}
          </button>
        </div>

        <button
          v-if="featuredSummary"
          class="group mb-4 w-full rounded-[28px] border border-emerald-400/14 bg-[linear-gradient(135deg,rgba(18,25,36,0.95),rgba(13,18,28,0.88))] px-6 py-5 text-left shadow-[0_28px_80px_rgba(0,0,0,0.28)] transition hover:border-emerald-300/28 hover:shadow-[0_36px_100px_rgba(0,0,0,0.34)]"
          @click="store.openComponent(featuredSummary.id)"
        >
          <div class="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div class="max-w-3xl">
              <div class="mb-3 flex items-center gap-2">
                <span class="rounded-full border border-emerald-400/15 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.22em] text-emerald-300">
                  Recommended
                </span>
                <span
                  v-if="featuredSummary.confidence !== undefined"
                  class="rounded-full border border-cyan-400/15 bg-cyan-500/10 px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.18em] text-cyan-200"
                >
                  {{ confidenceLabel(featuredSummary.confidence) }}
                </span>
                <span
                  v-if="featuredSummary.entrypoints.length"
                  class="rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.18em] text-gray-400"
                >
                  {{ featuredSummary.entrypoints[0] }}
                </span>
              </div>
              <h4 class="text-2xl font-semibold tracking-tight text-white transition group-hover:text-emerald-100">
                {{ displayName(featuredSummary.name) }}
              </h4>
              <p class="mt-3 max-w-2xl text-sm leading-6 text-gray-400">
                {{ featuredSummary.summary }}
              </p>
              <p v-if="featuredSummary.reason" class="mt-2 max-w-2xl text-xs leading-5 text-emerald-100/70">
                {{ featuredSummary.reason }}
              </p>
              <div class="mt-4 flex flex-wrap gap-1.5">
                <span
                  v-for="category in featuredSummary.dominantCategories.slice(0, 3)"
                  :key="`${featuredSummary.id}-${category}`"
                  class="rounded-full px-2.5 py-1 text-[10px] font-mono"
                  :style="{ backgroundColor: `${colorForCategory(category)}20`, color: colorForCategory(category) }"
                >
                  {{ displayCategory(category) }}
                </span>
              </div>
            </div>

            <div class="flex flex-col items-start gap-3 lg:min-w-[220px] lg:items-end">
              <div class="text-sm font-mono text-gray-300">
                {{ featuredSummary.resourceCount }} resources · {{ featuredSummary.edgeCount }} connections
              </div>
              <div class="text-xs text-gray-500">
                {{ metaLine(featuredSummary) }}
              </div>
              <div class="inline-flex items-center gap-2 rounded-full border border-emerald-400/15 bg-emerald-500/10 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.18em] text-emerald-300 transition group-hover:border-emerald-300/25 group-hover:text-emerald-200">
                Open component
              </div>
            </div>
          </div>
        </button>

        <div class="space-y-5">
          <div v-for="section in secondarySections" :key="section.id">
            <div v-if="secondarySections.length > 1" class="mb-2 flex items-center justify-between text-[10px] font-mono uppercase tracking-[0.18em] text-gray-500">
              <span>{{ section.label }}</span>
              <span>{{ section.items.length }} group{{ section.items.length === 1 ? '' : 's' }}</span>
            </div>
            <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <button
                v-for="component in section.items"
                :key="component.id"
                class="group rounded-[24px] border bg-[#11151d]/84 p-4 text-left shadow-[0_18px_60px_rgba(0,0,0,0.18)] transition hover:-translate-y-0.5 hover:shadow-[0_24px_70px_rgba(0,0,0,0.24)]"
                :class="component.kind === 'weakly_linked'
                  ? 'border-white/[0.06] hover:border-indigo-400/20'
                  : 'border-white/[0.08] hover:border-emerald-400/24'"
                @click="store.openComponent(component.id)"
              >
                <div class="mb-3 flex items-center justify-between gap-3">
                  <span
                    class="rounded-full px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.18em]"
                    :class="component.kind === 'weakly_linked'
                      ? 'bg-indigo-500/10 text-indigo-300'
                      : 'bg-emerald-500/10 text-emerald-300'"
                  >
                    {{ componentLabel(component) }}
                  </span>
                  <span class="text-[11px] font-mono text-gray-500">{{ component.resourceCount }} res</span>
                </div>

                <div class="mb-2 flex items-center gap-2">
                  <span v-if="component.confidence !== undefined" class="rounded-full bg-cyan-500/10 px-2 py-0.5 text-[10px] font-mono uppercase tracking-[0.14em] text-cyan-200">
                    {{ confidenceLabel(component.confidence) }}
                  </span>
                  <span v-if="component.parentGroupId" class="truncate text-[10px] font-mono uppercase tracking-[0.14em] text-gray-500">
                    {{ parentLabel(component.parentGroupId) }}
                  </span>
                </div>

                <h4 class="text-lg font-semibold tracking-tight text-white transition group-hover:text-emerald-100">
                  {{ displayName(component.name) }}
                </h4>
                <p class="mt-2 text-sm leading-6 text-gray-400">
                  {{ component.summary }}
                </p>
                <p v-if="component.reason" class="mt-2 text-xs leading-5 text-gray-500">
                  {{ component.reason }}
                </p>

                <div class="mt-4 flex flex-wrap gap-1.5">
                  <span
                    v-for="category in component.dominantCategories.slice(0, 3)"
                    :key="`${component.id}-${category}`"
                    class="rounded-full px-2 py-0.5 text-[10px] font-mono"
                    :style="{ backgroundColor: `${colorForCategory(category)}20`, color: colorForCategory(category) }"
                  >
                    {{ displayCategory(category) }}
                  </span>
                </div>

                <div v-if="component.entrypoints.length" class="mt-4 text-xs text-gray-300">
                  <span class="font-mono uppercase tracking-[0.18em] text-gray-600">Entrypoint</span>
                  <span class="ml-2">{{ component.entrypoints[0] }}</span>
                </div>

                <div class="mt-5 flex items-center justify-between border-t border-white/[0.06] pt-3 text-[11px] font-mono text-gray-500">
                  <span>{{ metaLine(component) }}</span>
                  <span class="rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-emerald-300 transition group-hover:border-emerald-300/20 group-hover:text-emerald-200">Open</span>
                </div>
              </button>
            </div>
          </div>
        </div>
      </section>

      <section
        v-if="unlinkedSummary"
        class="rounded-[28px] border border-white/[0.05] bg-white/[0.02] px-6 py-5 shadow-[0_18px_60px_rgba(0,0,0,0.16)]"
      >
        <div class="mb-4 flex items-end justify-between gap-6">
          <div>
            <p class="text-[10px] font-mono uppercase tracking-[0.24em] text-gray-600">Unlinked Resources</p>
            <h3 class="mt-2 text-lg font-semibold text-white">Resources that still need stronger grouping</h3>
            <p class="mt-2 max-w-3xl text-sm leading-6 text-gray-400">
              These resources were detected successfully, but no smart group claimed them yet.
            </p>
          </div>
          <div class="text-right text-xs font-mono text-gray-500">
            {{ unlinkedSummary.resourceCount }} resources
          </div>
        </div>

        <button
          class="group w-full rounded-[24px] border border-white/[0.06] bg-[#11141b]/72 p-4 text-left transition hover:border-amber-400/18 hover:bg-[#141923]"
          @click="store.openComponent(unlinkedSummary.id)"
        >
          <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div class="mb-2 flex items-center gap-2">
                <span class="rounded-full bg-amber-500/10 px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.18em] text-amber-300">
                  Unlinked bucket
                </span>
              </div>
              <h4 class="text-lg font-semibold text-white transition group-hover:text-amber-100">
                {{ displayName(unlinkedSummary.name) }}
              </h4>
              <p class="mt-2 text-sm leading-6 text-gray-400">
                {{ unlinkedSummary.summary }}
              </p>
            </div>

            <div class="flex flex-col items-start gap-3 lg:items-end">
              <div class="flex flex-wrap gap-1.5 lg:justify-end">
                <span
                  v-for="category in unlinkedSummary.dominantCategories.slice(0, 3)"
                  :key="`${unlinkedSummary.id}-${category}`"
                  class="rounded-full px-2 py-0.5 text-[10px] font-mono"
                  :style="{ backgroundColor: `${colorForCategory(category)}20`, color: colorForCategory(category) }"
                >
                  {{ displayCategory(category) }}
                </span>
              </div>
              <div class="text-[11px] font-mono text-gray-500">{{ metaLine(unlinkedSummary) }}</div>
              <div class="rounded-full border border-amber-400/15 bg-amber-500/10 px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.18em] text-amber-300 transition group-hover:border-amber-300/20 group-hover:text-amber-200">Inspect bucket</div>
            </div>
          </div>
        </button>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { CATEGORY_COLORS } from '~/composables/useGraph'
import { useGraphStore, type ComponentSummary } from '~/stores/graph'

const store = useGraphStore()

const allSummaries = computed(() => store.componentSummaries)
const primarySummaries = computed(() => allSummaries.value.filter(summary => summary.kind !== 'unlinked_bucket'))
const selectedParentId = ref('all')
const filteredPrimarySummaries = computed(() => {
  if (selectedParentId.value === 'all') return primarySummaries.value
  return primarySummaries.value.filter(summary => (summary.parentGroupId || 'unscoped') === selectedParentId.value)
})
const featuredSummary = computed(() => filteredPrimarySummaries.value[0] || null)
const secondarySummaries = computed(() => filteredPrimarySummaries.value.slice(1))
const unlinkedSummary = computed(() => allSummaries.value.find(summary => summary.kind === 'unlinked_bucket') || null)
const totalResources = computed(() => store.architectureSourceNodes.length)
const totalConnections = computed(() => store.architectureSourceEdges.length)

const accountScopeName = computed(() => {
  if (!store.activeAccountId) return null
  const accountGroup = store.groups.find(group => group.group_type === 'account' && group.metadata?.account_id === store.activeAccountId)
  return accountGroup?.metadata?.account_name || accountGroup?.name || store.activeAccountId
})

const scopeLabel = computed(() => {
  if (accountScopeName.value) return accountScopeName.value
  if (store.metadata?.scan_mode === 'organization') return 'Organization slice'
  return 'Current scan'
})

const totalAccounts = computed(() => {
  const ids = new Set<string>()
  for (const summary of allSummaries.value) {
    for (const accountId of summary.accountIds) ids.add(accountId)
  }
  return ids.size || 1
})

const totalRegions = computed(() => {
  const regions = new Set<string>()
  for (const summary of allSummaries.value) {
    for (const region of summary.regions) regions.add(region)
  }
  return regions.size || 1
})

const topEntrypoints = computed(() => {
  const names = new Set<string>()
  for (const summary of primarySummaries.value) {
    for (const entrypoint of summary.entrypoints.slice(0, 2)) names.add(entrypoint)
  }
  return [...names].slice(0, 3)
})

const parentFilterOptions = computed(() => {
  const counts = new Map<string, number>()
  for (const summary of primarySummaries.value) {
    const id = summary.parentGroupId || 'unscoped'
    counts.set(id, (counts.get(id) || 0) + 1)
  }
  const options = [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([id, count]) => ({ id, label: parentLabel(id), count }))
  return [{ id: 'all', label: 'All', count: primarySummaries.value.length }, ...options]
})

const secondarySections = computed(() => {
  if (selectedParentId.value !== 'all') {
    return [{ id: selectedParentId.value, label: parentLabel(selectedParentId.value), items: secondarySummaries.value }]
  }
  const sections = new Map<string, ComponentSummary[]>()
  for (const summary of secondarySummaries.value) {
    const id = summary.parentGroupId || 'unscoped'
    if (!sections.has(id)) sections.set(id, [])
    sections.get(id)!.push(summary)
  }
  return [...sections.entries()].map(([id, items]) => ({ id, label: parentLabel(id), items }))
})

const overviewItems = computed(() => [
  {
    label: 'Service islands',
    value: `${primarySummaries.value.length}`,
    detail: primarySummaries.value.length === 1 ? 'One mapped system in scope' : 'Ranked by architectural value',
  },
  {
    label: 'Resources in scope',
    value: `${totalResources.value}`,
    detail: `${totalConnections.value} visible connections`,
  },
  {
    label: 'Accounts / regions',
    value: `${totalAccounts.value} / ${totalRegions.value}`,
    detail: accountScopeName.value ? 'Scoped to the selected account' : 'Landscape view across the current scope',
  },
  {
    label: 'Top signal',
    value: featuredSummary.value ? displayName(featuredSummary.value.name) : 'No dominant component',
    detail: topEntrypoints.value.length ? topEntrypoints.value.join(' · ') : 'Internal architecture',
  },
])

function displayName(value: string): string {
  return value
    .split(/[-_]/g)
    .filter(Boolean)
    .map(part => {
      const lower = part.toLowerCase()
      if (['api', 'aws', 'vpc', 'ecs', 'rds', 's3', 'sns', 'sqs', 'cdn', 'dns', 'alb'].includes(lower)) {
        return lower.toUpperCase()
      }
      return lower.charAt(0).toUpperCase() + lower.slice(1)
    })
    .join(' ')
}

function displayCategory(category: string): string {
  return category.replace(/_/g, ' ')
}

function metaLine(component: ComponentSummary): string {
  return `${component.accountIds.length} account${component.accountIds.length === 1 ? '' : 's'} · ${component.regions.length} region${component.regions.length === 1 ? '' : 's'} · ${component.edgeCount} connection${component.edgeCount === 1 ? '' : 's'}`
}

function parentLabel(parentGroupId: string): string {
  if (parentGroupId === 'all') return 'All'
  if (parentGroupId === 'unscoped') return 'Landscape'
  const group = store.groups.find(item => item.id === parentGroupId)
  return group?.name ? displayName(group.name) : 'Landscape'
}

function confidenceLabel(value: number): string {
  return `${Math.round(value * 100)}% match`
}

function componentLabel(component: ComponentSummary): string {
  if (component.source === 'smart_group') return 'Smart group'
  if (component.kind === 'weakly_linked') return 'Weakly linked'
  return 'Service component'
}

function colorForCategory(category: string): string {
  return CATEGORY_COLORS[category] || '#9ca3af'
}
</script>
