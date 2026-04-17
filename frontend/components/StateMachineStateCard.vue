<template>
  <div class="rounded-lg border px-3 py-2.5 transition" :class="cardClass">
    <!-- Header -->
    <div class="flex items-start justify-between gap-2">
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-1.5">
          <span class="rounded-md px-1.5 py-0.5 text-[9px] font-mono uppercase tracking-[0.16em]" :class="typeBadgeClass">
            {{ state.type }}
          </span>
          <span class="truncate text-[12px] font-mono font-semibold text-white">{{ state.name }}</span>
          <span v-if="state.pattern" class="rounded-md border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-[9px] font-mono text-gray-400">
            .{{ state.pattern }}
          </span>
          <span v-if="hasWarning" class="text-amber-400" title="This state has warnings">●</span>
        </div>
        <div v-if="state.comment" class="mt-1 text-[10px] italic text-gray-500 leading-snug">{{ state.comment }}</div>
      </div>
      <div v-if="state.end" class="flex-shrink-0 text-[9px] font-mono uppercase tracking-[0.16em] text-emerald-400">end</div>
    </div>

    <!-- Task-specific -->
    <div v-if="state.type === 'Task'" class="mt-2 space-y-1.5">
      <div v-if="state.integration" class="text-[10px] font-mono text-gray-400">
        <span class="text-gray-500">integration:</span> {{ state.integration }}
      </div>
      <div v-if="state.resource_arn" class="flex items-center gap-2">
        <span class="text-[10px] font-mono text-gray-500">→</span>
        <button
          v-if="state.resource_node_id"
          class="truncate rounded-md border border-cyan-400/25 bg-cyan-500/[0.08] px-2 py-0.5 text-[10px] font-mono text-cyan-200 transition hover:border-cyan-300/40 hover:bg-cyan-500/15"
          :title="`Jump to ${state.resource_node_id}`"
          @click="$emit('focusResource', state.resource_node_id!)"
        >
          {{ resourceLabel }}
        </button>
        <span
          v-else
          class="truncate rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] font-mono text-gray-400"
          :title="state.resource_arn"
        >
          {{ resourceLabel }}
        </span>
      </div>
      <div v-if="state.parameters_summary" class="text-[10px] font-mono text-gray-500 truncate">
        {{ state.parameters_summary }}
      </div>
      <div v-if="taskMeta.length" class="flex flex-wrap gap-1.5">
        <span
          v-for="m in taskMeta"
          :key="m"
          class="rounded-md border border-white/8 bg-white/[0.03] px-1.5 py-0.5 text-[9px] font-mono text-gray-400"
        >
          {{ m }}
        </span>
      </div>
    </div>

    <!-- Choice -->
    <div v-if="state.type === 'Choice' && state.choices?.length" class="mt-2 space-y-1">
      <div
        v-for="(choice, idx) in state.choices"
        :key="idx"
        class="flex items-start gap-2 text-[10px] font-mono"
      >
        <span class="mt-0.5 text-gray-500">if</span>
        <span class="flex-1 truncate text-gray-300">{{ choice.condition_summary || '(no condition)' }}</span>
        <span class="text-gray-500">→</span>
        <span class="text-cyan-300">{{ choice.next }}</span>
      </div>
      <div v-if="state.default" class="flex items-center gap-2 text-[10px] font-mono">
        <span class="text-gray-500">default →</span>
        <span class="text-cyan-300">{{ state.default }}</span>
      </div>
    </div>

    <!-- Wait -->
    <div v-if="state.type === 'Wait'" class="mt-2 text-[10px] font-mono text-gray-400">
      <span v-if="state.wait_seconds != null">wait {{ state.wait_seconds }}s</span>
      <span v-else-if="state.wait_seconds_path">wait for path {{ state.wait_seconds_path }}</span>
      <span v-else-if="state.wait_timestamp">wait until {{ state.wait_timestamp }}</span>
    </div>

    <!-- Fail -->
    <div v-if="state.type === 'Fail'" class="mt-2 text-[10px] font-mono text-red-300">
      <span v-if="state.error">{{ state.error }}</span>
      <span v-if="state.cause" class="ml-1 text-red-200/70">— {{ state.cause }}</span>
    </div>

    <!-- Retry / Catch pills -->
    <div v-if="retryLabels.length || catchLabels.length" class="mt-2 flex flex-wrap gap-1.5">
      <span
        v-for="(r, idx) in retryLabels"
        :key="'r' + idx"
        class="rounded-md border border-blue-400/20 bg-blue-500/[0.08] px-1.5 py-0.5 text-[9px] font-mono text-blue-200"
        title="Retry policy"
      >
        retry {{ r }}
      </span>
      <span
        v-for="(c, idx) in catchLabels"
        :key="'c' + idx"
        class="rounded-md border border-orange-400/20 bg-orange-500/[0.08] px-1.5 py-0.5 text-[9px] font-mono text-orange-200"
        title="Catch handler"
      >
        catch → {{ c }}
      </span>
    </div>

    <!-- Parallel branches -->
    <div v-if="state.type === 'Parallel' && state.branches?.length" class="mt-2 grid gap-2" :style="branchGridStyle">
      <div
        v-for="(branch, idx) in state.branches"
        :key="idx"
        class="rounded-md border border-white/8 bg-white/[0.02] p-2"
      >
        <div class="mb-1.5 text-[9px] font-mono uppercase tracking-[0.16em] text-gray-500">
          branch {{ idx + 1 }} · start {{ branch.start_at || '—' }}
        </div>
        <div class="space-y-1.5">
          <StateMachineStateCard
            v-for="qname in branch.states"
            :key="qname"
            :state="allStates[qname]"
            :warnings-by-state="warningsByState"
            :all-states="allStates"
            @focus-resource="(nid) => $emit('focusResource', nid)"
          />
        </div>
      </div>
    </div>

    <!-- Map iterator -->
    <div v-if="state.type === 'Map' && state.iterator" class="mt-2 rounded-md border border-white/8 bg-white/[0.02] p-2">
      <div class="mb-1.5 flex items-center justify-between text-[9px] font-mono uppercase tracking-[0.16em] text-gray-500">
        <span>iterator · start {{ state.iterator.start_at || '—' }}</span>
        <span class="rounded-md bg-white/[0.05] px-1.5 py-0.5 text-purple-300">
          ×{{ state.max_concurrency ?? 'N' }}
        </span>
      </div>
      <div v-if="state.items_path" class="mb-2 text-[10px] font-mono text-gray-500">items_path: {{ state.items_path }}</div>
      <div class="space-y-1.5">
        <StateMachineStateCard
          v-for="qname in state.iterator.states"
          :key="qname"
          :state="allStates[qname]"
          :warnings-by-state="warningsByState"
          :all-states="allStates"
          @focus-resource="(nid) => $emit('focusResource', nid)"
        />
      </div>
    </div>

    <!-- Next arrow -->
    <div v-if="state.next" class="mt-2 text-[10px] font-mono text-gray-500">
      ↓ <span class="text-cyan-300">{{ state.next }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface AslState {
  name: string
  qualified_name: string
  type: string
  path?: string[]
  next?: string
  end?: boolean
  comment?: string
  integration?: string
  pattern?: string
  resource_kind?: string
  resource_arn?: string | null
  resource_node_id?: string | null
  parameters_summary?: string
  result_summary?: string
  timeout_seconds?: number
  heartbeat_seconds?: number
  retry?: Array<{ error_equals: string[]; interval_seconds?: number; max_attempts?: number; backoff_rate?: number }>
  catch?: Array<{ error_equals: string[]; next?: string; result_path?: string }>
  choices?: Array<{ condition_summary: string; next?: string }>
  default?: string
  branches?: Array<{ start_at?: string; states: string[] }>
  iterator?: { start_at?: string; states: string[] } | null
  items_path?: string
  max_concurrency?: number
  wait_seconds?: number
  wait_seconds_path?: string
  wait_timestamp?: string
  error?: string
  cause?: string
}

const props = defineProps<{
  state: AslState
  warningsByState: Record<string, Array<{ code: string; message: string }>>
  allStates: Record<string, AslState>
}>()
defineEmits<{ (e: 'focusResource', nodeId: string): void }>()

const hasWarning = computed(() => (props.warningsByState[props.state.qualified_name] || []).length > 0)

const cardClass = computed(() => {
  if (hasWarning.value) return 'border-amber-400/25 bg-amber-500/[0.04]'
  if (props.state.type === 'Fail') return 'border-red-400/20 bg-red-500/[0.04]'
  if (props.state.type === 'Succeed') return 'border-emerald-400/20 bg-emerald-500/[0.04]'
  return 'border-white/8 bg-white/[0.02] hover:border-white/15'
})

const typeBadgeClass = computed(() => {
  switch (props.state.type) {
    case 'Task': return 'bg-cyan-500/15 text-cyan-300'
    case 'Choice': return 'bg-violet-500/15 text-violet-300'
    case 'Parallel': return 'bg-amber-500/15 text-amber-300'
    case 'Map': return 'bg-purple-500/15 text-purple-300'
    case 'Wait': return 'bg-gray-500/15 text-gray-300'
    case 'Pass': return 'bg-slate-500/15 text-slate-300'
    case 'Succeed': return 'bg-emerald-500/15 text-emerald-300'
    case 'Fail': return 'bg-red-500/15 text-red-300'
    default: return 'bg-white/8 text-gray-300'
  }
})

const resourceLabel = computed(() => {
  const arn = props.state.resource_arn
  if (!arn) return ''
  // Trim to the trailing :name or /name segment for readability.
  const tail = arn.split(/[:/]/).pop() || arn
  return tail.length > 40 ? tail.slice(0, 39) + '…' : tail
})

const taskMeta = computed(() => {
  const items: string[] = []
  if (props.state.timeout_seconds != null) items.push(`timeout ${props.state.timeout_seconds}s`)
  if (props.state.heartbeat_seconds != null) items.push(`heartbeat ${props.state.heartbeat_seconds}s`)
  return items
})

const retryLabels = computed(() =>
  (props.state.retry || []).map((r) => {
    const errs = (r.error_equals || []).join(',') || 'ALL'
    const attempts = r.max_attempts != null ? ` ×${r.max_attempts}` : ''
    return `${errs}${attempts}`
  }),
)

const catchLabels = computed(() =>
  (props.state.catch || []).map((c) => c.next || '?'),
)

const branchGridStyle = computed(() => {
  const n = props.state.branches?.length || 1
  // Up to 2 columns when narrow, 3 when wider — caller can override with CSS if needed.
  const cols = Math.min(n, 2)
  return { gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }
})
</script>
