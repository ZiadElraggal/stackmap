<template>
  <div v-if="!asl || asl.error" class="rounded-xl border border-white/8 bg-white/[0.02] px-3 py-4 text-[11px] font-mono text-gray-400">
    <template v-if="!asl">No ASL graph available for this state machine.</template>
    <template v-else-if="asl.error === 'empty'">Definition was empty when the graph was built.</template>
    <template v-else-if="asl.error === 'unparseable'">ASL could not be parsed (invalid JSON/YAML).</template>
    <template v-else-if="asl.error === 'no_states'">Definition has no `States` block.</template>
    <template v-else>ASL parse error: {{ asl.error }}</template>
  </div>

  <div v-else class="space-y-3">
    <!-- Summary bar -->
    <div class="rounded-xl border border-white/8 bg-white/[0.02] px-3 py-2.5">
      <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[10px] font-mono uppercase tracking-[0.18em] text-gray-500">
        <span><span class="text-gray-300">{{ topLevelStateCount }}</span> states</span>
        <span v-if="branchCount"><span class="text-gray-300">{{ branchCount }}</span> branches</span>
        <span v-if="mapCount"><span class="text-gray-300">{{ mapCount }}</span> maps</span>
        <span v-if="taskCount"><span class="text-gray-300">{{ taskCount }}</span> tasks</span>
        <span v-if="asl.timeout_seconds"><span class="text-gray-300">{{ asl.timeout_seconds }}s</span> timeout</span>
      </div>
      <div v-if="asl.comment" class="mt-1.5 text-[11px] text-gray-400 italic leading-snug">{{ asl.comment }}</div>
      <div v-if="recentExecutionSummary" class="mt-2 rounded-lg border border-emerald-400/15 bg-emerald-500/[0.06] px-2 py-1.5 text-[11px] font-mono text-emerald-100/85">
        {{ recentExecutionSummary }}
      </div>
      <div class="mt-2 flex flex-wrap items-center gap-2">
        <button
          class="rounded-lg border border-cyan-400/20 bg-cyan-500/10 px-2.5 py-1.5 text-[10px] font-mono uppercase tracking-[0.16em] text-cyan-200 transition hover:border-cyan-300/35 hover:bg-cyan-500/15 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="executionLoading"
          @click="loadRecentExecutions"
        >
          {{ executionLoading ? 'Loading executions' : hasRecentExecutions ? 'Refresh executions' : 'Load recent executions' }}
        </button>
        <span v-if="executionProfile" class="text-[10px] font-mono text-gray-500">
          {{ executionProfile }}
        </span>
      </div>
      <div v-if="executionError" class="mt-2 rounded-lg border border-amber-400/20 bg-amber-500/[0.07] px-2 py-1.5 text-[11px] font-mono text-amber-100">
        {{ executionError }}
      </div>
    </div>

    <!-- Warnings banner -->
    <div v-if="(asl.warnings || []).length" class="rounded-xl border border-amber-400/25 bg-amber-500/[0.07] px-3 py-2.5">
      <div class="flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.18em] text-amber-300">
        <span>⚠ Warnings</span>
        <span class="text-amber-200/70">{{ warningSummary }}</span>
      </div>
      <ul class="mt-2 space-y-1 text-[11px] font-mono text-amber-100/90">
        <li v-for="(w, idx) in asl.warnings" :key="idx" class="leading-snug">
          <span class="text-amber-300">{{ w.code }}</span>
          <span v-if="w.state" class="text-amber-200/60"> · {{ w.state }}</span>
          <span class="text-amber-100/80"> — {{ w.message }}</span>
        </li>
      </ul>
    </div>

    <!-- Flow -->
    <div class="rounded-xl border border-white/8 bg-[#0e111a]/60 p-3">
      <div class="text-[10px] font-mono uppercase tracking-[0.2em] text-gray-500">
        Start → {{ asl.start_at || '—' }}
      </div>
      <div class="mt-3 space-y-2">
        <StateCard
          v-for="state in topLevelStates"
          :key="state.qualified_name"
          :state="state"
          :warnings-by-state="warningsByState"
          :all-states="statesByQualified"
          @focus-resource="focusResource"
        />
      </div>
    </div>

    <!-- Raw ASL toggle -->
    <div class="rounded-xl border border-white/8 bg-white/[0.02]">
      <button
        class="flex w-full items-center justify-between px-3 py-2 text-[10px] font-mono uppercase tracking-[0.18em] text-gray-400 transition hover:text-white"
        @click="showRaw = !showRaw"
      >
        <span>Raw graph JSON</span>
        <span>{{ showRaw ? 'Hide' : 'Show' }}</span>
      </button>
      <pre v-if="showRaw" class="max-h-80 overflow-auto border-t border-white/5 bg-[#0a0c13] px-3 py-2 text-[10px] leading-snug text-gray-300">{{ rawJson }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useGraphStore } from '~/stores/graph'
import StateCard from '~/components/StateMachineStateCard.vue'

interface AslTransition {
  from: string
  to: string
  kind: string
  label?: string
  error_equals?: string[]
}

interface AslWarning {
  state?: string
  code: string
  message: string
}

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

export interface AslGraph {
  start_at?: string
  timeout_seconds?: number
  version?: string
  comment?: string
  states?: AslState[]
  transitions?: AslTransition[]
  resources?: Array<{ arn: string; kind: string; integration?: string; pattern?: string; node_id?: string | null }>
  warnings?: AslWarning[]
  recent_executions?: Array<{ status?: string; start?: string; duration_ms?: number | null; failed_state?: string | null }>
  error?: string
}

const props = defineProps<{ node: { id: string; properties?: Record<string, any> } }>()
const store = useGraphStore()
const showRaw = ref(false)
const executionLoading = ref(false)
const executionError = ref('')
const executionProfile = ref('')

const asl = computed<AslGraph | null>(() => {
  const raw = props.node?.properties?.asl_graph
  return raw && typeof raw === 'object' ? (raw as AslGraph) : null
})

const allStates = computed<AslState[]>(() => asl.value?.states || [])
const topLevelStates = computed(() => allStates.value.filter((s) => !s.path || s.path.length === 0))
const topLevelStateCount = computed(() => topLevelStates.value.length)
const taskCount = computed(() => allStates.value.filter((s) => s.type === 'Task').length)
const branchCount = computed(() =>
  allStates.value.reduce((acc, s) => acc + (s.type === 'Parallel' ? (s.branches?.length || 0) : 0), 0),
)
const mapCount = computed(() => allStates.value.filter((s) => s.type === 'Map').length)

const statesByQualified = computed(() => {
  const map: Record<string, AslState> = {}
  for (const state of allStates.value) map[state.qualified_name] = state
  return map
})

const warningsByState = computed(() => {
  const map: Record<string, AslWarning[]> = {}
  for (const w of asl.value?.warnings || []) {
    if (!w.state) continue
    if (!map[w.state]) map[w.state] = []
    map[w.state].push(w)
  }
  return map
})

const warningSummary = computed(() => {
  const counts: Record<string, number> = {}
  for (const w of asl.value?.warnings || []) counts[w.code] = (counts[w.code] || 0) + 1
  return Object.entries(counts).map(([code, n]) => `${n} ${code.replace(/_/g, ' ')}`).join(' · ')
})

const recentExecutionSummary = computed(() => {
  const executions = asl.value?.recent_executions || []
  if (!executions.length) return ''
  const succeeded = executions.filter(item => item.status === 'SUCCEEDED').length
  const failed = executions.filter(item => item.status === 'FAILED' || item.status === 'TIMED_OUT' || item.status === 'ABORTED').length
  const durations = executions
    .map(item => item.duration_ms)
    .filter((value): value is number => typeof value === 'number')
  const avg = durations.length
    ? `${Math.round(durations.reduce((sum, value) => sum + value, 0) / durations.length)}ms avg`
    : 'duration pending'
  return `${succeeded}/${executions.length} succeeded · ${failed} failed · ${avg}`
})
const hasRecentExecutions = computed(() => Boolean(asl.value?.recent_executions?.length))

const rawJson = computed(() => JSON.stringify(asl.value, null, 2))

function focusResource(nodeId: string) {
  if (!nodeId) return
  store.selectNode(nodeId)
  window.dispatchEvent(new CustomEvent('stackmap-pan-to-node', { detail: { nodeId } }))
}

async function loadRecentExecutions() {
  executionLoading.value = true
  executionError.value = ''
  try {
    const response = await fetch('/api/sfn-executions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_id: props.node.id }),
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(payload.error || 'Could not load recent executions.')
    }
    if (asl.value) {
      asl.value.recent_executions = Array.isArray(payload.executions) ? payload.executions : []
    }
    executionProfile.value = payload.active_profile ? `profile ${payload.active_profile}` : ''
  } catch (error) {
    executionError.value = error instanceof Error ? error.message : 'Could not load recent executions.'
  } finally {
    executionLoading.value = false
  }
}
</script>
