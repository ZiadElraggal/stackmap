<template>
  <div v-if="store.showLogs" class="log-viewer" :class="{ 'log-viewer--panel-open': panelOpen }">
    <div class="log-shell">
      <div class="log-header">
        <div>
          <div class="log-eyebrow">CloudWatch</div>
          <h3 class="log-title">Live logs</h3>
        </div>
        <div class="log-header-actions">
          <button v-if="store.logNodeId" class="log-scope-btn" @click="viewAllLogs">All</button>
          <button class="log-close" @click="store.toggleLogs()">Hide</button>
        </div>
      </div>

      <div v-if="store.logNodeId" class="log-scope-label">
        Showing logs for: <span class="log-scope-name">{{ store.logNodeId.split('.').pop() }}</span>
      </div>
      <div v-else class="log-scope-label">
        Showing logs for: <span class="log-scope-name">{{ store.logScope === 'visible' ? 'visible resources' : 'all resources' }}</span>
      </div>

      <div class="log-controls">
        <label class="log-range">
          <span>Range</span>
          <select :value="store.logMinutes" class="log-range-select" @change="setRange">
            <option :value="60">1 hour</option>
            <option :value="360">6 hours</option>
            <option :value="1440">24 hours</option>
            <option :value="10080">7 days</option>
          </select>
        </label>
        <button class="log-scope-btn" @click="viewVisibleLogs">Visible</button>
        <button class="log-scope-btn" @click="viewAllLogs">All graph</button>
      </div>

      <div class="log-search">
        <input
          v-model="searchQuery"
          type="text"
          class="log-search-input"
          placeholder="Search logs... (text or regex)"
          @keydown.enter="applyFilter"
        />
        <button class="log-search-btn" @click="applyFilter">Filter</button>
      </div>

      <div v-if="store.logLoading" class="log-status">
        <span class="log-spinner" />
        Fetching logs...
      </div>

      <div v-else-if="store.logError && filteredEvents.length === 0" class="log-status log-status--error">
        {{ store.logError }}
      </div>

      <div v-else-if="filteredEvents.length === 0" class="log-status">
        No log events found in the last {{ rangeLabel }}.
      </div>

      <div v-else class="log-events">
        <div class="log-meta">
          {{ filteredEvents.length }} events
          <span v-if="store.logGroups.length > 0" class="log-meta-groups">
            from {{ store.logGroups.length }} log group{{ store.logGroups.length !== 1 ? 's' : '' }}
          </span>
        </div>
        <div
          v-for="(event, idx) in displayedEvents"
          :key="idx"
          class="log-event"
          :class="{ 'log-event--error': isErrorLine(event.message) }"
        >
          <div class="log-event-time">{{ formatTimestamp(event.timestamp) }}</div>
          <div class="log-event-msg">{{ event.message }}</div>
        </div>
        <button
          v-if="filteredEvents.length > displayLimit"
          class="log-load-more"
          @click="displayLimit += 50"
        >
          Show more ({{ filteredEvents.length - displayLimit }} remaining)
        </button>
      </div>

      <div class="log-actions">
        <button class="log-refresh-btn" @click="refresh" :disabled="store.logLoading">
          Refresh
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useGraphStore } from '~/stores/graph'

const store = useGraphStore()

const searchQuery = ref('')
const displayLimit = ref(50)

const panelOpen = computed(() => !store.editorPanelCollapsed && (!!store.selectedNode || !!store.selectedEdge || store.editMode))

const filteredEvents = computed(() => {
  if (!searchQuery.value.trim()) return store.logEvents
  const q = searchQuery.value.toLowerCase()
  try {
    const re = new RegExp(searchQuery.value, 'i')
    return store.logEvents.filter(e => re.test(e.message))
  } catch {
    return store.logEvents.filter(e => e.message.toLowerCase().includes(q))
  }
})

const displayedEvents = computed(() => filteredEvents.value.slice(0, displayLimit.value))
const rangeLabel = computed(() => {
  if (store.logMinutes < 60) return `${store.logMinutes} minutes`
  if (store.logMinutes === 60) return 'hour'
  if (store.logMinutes < 1440) return `${Math.round(store.logMinutes / 60)} hours`
  if (store.logMinutes === 1440) return '24 hours'
  return `${Math.round(store.logMinutes / 1440)} days`
})

function formatTimestamp(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function isErrorLine(msg: string): boolean {
  const lower = msg.toLowerCase()
  return lower.includes('error') || lower.includes('exception') || lower.includes('fatal') || lower.includes('traceback')
}

async function applyFilter() {
  if (store.logFilter !== searchQuery.value) {
    await store.setLogFilter(searchQuery.value)
  }
}

async function setRange(event: Event) {
  const value = Number((event.target as HTMLSelectElement).value)
  if (Number.isFinite(value)) {
    await store.setLogMinutes(value)
  }
}

async function viewVisibleLogs() {
  await store.fetchVisibleLogs()
}

async function viewAllLogs() {
  await store.fetchAllLogs()
}

async function refresh() {
  if (store.logNodeId) {
    await store.fetchLogs(store.logNodeId)
  } else if (store.logScope === 'visible') {
    await store.fetchVisibleLogs()
  } else {
    await store.fetchAllLogs()
  }
}

watch(() => store.showLogs, (val) => {
  if (val) displayLimit.value = 50
})
</script>

<style scoped>
.log-viewer {
  position: fixed;
  bottom: 16px;
  left: 16px;
  z-index: 994;
  width: min(600px, calc(100vw - 32px));
  max-height: 50vh;
  display: flex;
  flex-direction: column;
}

.log-viewer--panel-open {
  width: min(600px, calc(100vw - 24rem - 48px));
}

.log-shell {
  border: 1px solid var(--sm-border, #2a2a3a);
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(18, 18, 26, 0.97), rgba(10, 10, 15, 0.96)),
    radial-gradient(circle at bottom left, rgba(96, 165, 250, 0.12), transparent 42%);
  box-shadow: var(--sm-shadow-elevated, 0 8px 32px rgba(0, 0, 0, 0.4));
  backdrop-filter: blur(18px);
  padding: 14px;
  display: flex;
  flex-direction: column;
  max-height: 50vh;
}

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.log-header-actions {
  display: flex;
  gap: 6px;
}

.log-eyebrow {
  color: rgba(96, 165, 250, 0.8);
  font-size: 10px;
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.log-title {
  margin: 4px 0 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--sm-text, #e0e0e8);
}

.log-scope-label {
  margin-top: 8px;
  font-size: 11px;
  color: var(--sm-text-muted, rgba(245, 245, 247, 0.55));
}

.log-scope-name {
  color: #60a5fa;
  font-family: 'JetBrains Mono', monospace;
}

.log-search {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}

.log-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
}

.log-range {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--sm-text-muted, rgba(245, 245, 247, 0.55));
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.log-range-select {
  border: 1px solid var(--sm-border, #2a2a3a);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--sm-text, #e0e0e8);
  font-size: 11px;
  padding: 6px 8px;
  outline: none;
}

.log-search-input {
  flex: 1;
  border: 1px solid var(--sm-border, #2a2a3a);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--sm-text, #e0e0e8);
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  padding: 6px 10px;
  outline: none;
}

.log-search-input:focus {
  border-color: rgba(96, 165, 250, 0.4);
}

.log-search-input::placeholder {
  color: var(--sm-text-muted, rgba(245, 245, 247, 0.35));
}

.log-close,
.log-scope-btn,
.log-search-btn,
.log-refresh-btn,
.log-load-more {
  border: 1px solid var(--sm-border, #2a2a3a);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--sm-text-secondary, #a0a0b0);
  cursor: pointer;
  font-size: 11px;
  padding: 6px 10px;
  transition: all 0.15s;
}

.log-close:hover,
.log-scope-btn:hover,
.log-search-btn:hover,
.log-refresh-btn:hover,
.log-load-more:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--sm-text, #e0e0e8);
}

.log-status {
  margin-top: 12px;
  font-size: 12px;
  color: var(--sm-text-muted, rgba(245, 245, 247, 0.55));
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-status--error {
  color: #f87171;
}

.log-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(96, 165, 250, 0.3);
  border-top-color: #60a5fa;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.log-events {
  margin-top: 10px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.log-meta {
  font-size: 11px;
  color: var(--sm-text-muted, rgba(245, 245, 247, 0.55));
  margin-bottom: 8px;
  font-family: 'JetBrains Mono', monospace;
}

.log-event {
  display: flex;
  gap: 10px;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  line-height: 1.5;
}

.log-event:hover {
  background: rgba(255, 255, 255, 0.03);
}

.log-event--error {
  background: rgba(248, 113, 113, 0.06);
}

.log-event-time {
  flex-shrink: 0;
  color: var(--sm-text-muted, rgba(245, 245, 247, 0.4));
  white-space: nowrap;
}

.log-event-msg {
  color: var(--sm-text, #e0e0e8);
  word-break: break-all;
  white-space: pre-wrap;
}

.log-actions {
  margin-top: 10px;
  display: flex;
  gap: 8px;
}

.log-load-more {
  width: 100%;
  margin-top: 6px;
  text-align: center;
}

@media (max-width: 768px) {
  .log-viewer {
    left: 8px;
    right: 8px;
    width: auto;
  }
}
</style>
