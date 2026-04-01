<template>
  <div class="absolute inset-0 z-20 overflow-y-auto px-16 pb-16 pt-28">
    <div class="mx-auto max-w-6xl">
      <div class="mb-6 flex items-end justify-between gap-6">
        <div>
          <p class="mb-2 text-[10px] font-mono uppercase tracking-[0.28em] text-cyan-400/70">Large Architecture</p>
          <h2 class="text-2xl font-semibold text-white">Component Landing</h2>
          <p class="mt-2 max-w-3xl text-sm text-gray-400">
            Service-shaped islands are ranked first so large AWS scans open as architecture, not inventory soup.
          </p>
        </div>
        <div class="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-right">
          <div class="text-[10px] font-mono uppercase tracking-widest text-gray-600">Visible Scope</div>
          <div class="mt-1 text-sm font-mono text-white">{{ summaries.length }} component{{ summaries.length === 1 ? '' : 's' }}</div>
        </div>
      </div>

      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <button
          v-for="component in summaries"
          :key="component.id"
          class="group rounded-2xl border border-white/10 bg-[#11131c]/85 p-4 text-left transition hover:border-cyan-400/40 hover:bg-[#141826]"
          @click="store.openComponent(component.id)"
        >
          <div class="mb-3 flex items-start justify-between gap-4">
            <div>
              <div class="mb-1 flex items-center gap-2">
                <span
                  class="rounded-full px-2 py-0.5 text-[10px] font-mono uppercase tracking-widest"
                  :class="component.kind === 'unlinked_bucket' ? 'bg-amber-500/10 text-amber-300' : component.kind === 'weakly_linked' ? 'bg-indigo-500/10 text-indigo-300' : 'bg-cyan-500/10 text-cyan-300'"
                >
                  {{ component.kind === 'unlinked_bucket' ? 'Unlinked' : component.kind === 'weakly_linked' ? 'Weakly linked' : 'Service component' }}
                </span>
              </div>
              <h3 class="text-lg font-semibold text-white transition group-hover:text-cyan-200">{{ prettyName(component.name) }}</h3>
              <p class="mt-1 text-xs font-mono text-gray-500">{{ component.summary }}</p>
            </div>
            <div class="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-right">
              <div class="text-[10px] font-mono uppercase tracking-widest text-gray-600">Resources</div>
              <div class="mt-1 text-lg font-semibold text-white">{{ component.resourceCount }}</div>
            </div>
          </div>

          <div class="mb-3 flex flex-wrap gap-1.5">
            <span
              v-for="category in component.dominantCategories"
              :key="`${component.id}-${category}`"
              class="rounded-full px-2 py-0.5 text-[10px] font-mono"
              :style="{ backgroundColor: `${colorForCategory(category)}20`, color: colorForCategory(category) }"
            >
              {{ category }}
            </span>
          </div>

          <div class="grid gap-3 sm:grid-cols-2">
            <div>
              <div class="mb-1 text-[10px] font-mono uppercase tracking-widest text-gray-600">Entrypoints</div>
              <div class="text-xs text-gray-300">
                {{ component.entrypoints.length ? component.entrypoints.join(', ') : 'Internal / no clear front door' }}
              </div>
            </div>
            <div>
              <div class="mb-1 text-[10px] font-mono uppercase tracking-widest text-gray-600">Accounts / Regions</div>
              <div class="text-xs text-gray-300">
                {{ component.accountIds.length }} account{{ component.accountIds.length === 1 ? '' : 's' }} · {{ component.regions.length }} region{{ component.regions.length === 1 ? '' : 's' }}
              </div>
            </div>
          </div>

          <div class="mt-4 flex items-center justify-between border-t border-white/6 pt-3 text-[11px] font-mono text-gray-500">
            <span>{{ component.edgeCount }} connection{{ component.edgeCount === 1 ? '' : 's' }}</span>
            <span class="text-cyan-300 transition group-hover:text-cyan-200">Open component →</span>
          </div>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CATEGORY_COLORS } from '~/composables/useGraph'
import { useGraphStore } from '~/stores/graph'

const store = useGraphStore()
const summaries = computed(() => store.componentSummaries)

function prettyName(value: string): string {
  return value.replace(/-/g, ' ')
}

function colorForCategory(category: string): string {
  return CATEGORY_COLORS[category] || '#9ca3af'
}
</script>
