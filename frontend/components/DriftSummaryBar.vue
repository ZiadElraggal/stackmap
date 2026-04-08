<template>
  <div v-if="store.driftMode && store.driftSummary" class="drift-summary-bar">
    <div class="drift-bar-inner">
      <span class="drift-label">Drift Analysis</span>
      <button
        class="drift-stat drift-stat--sync"
        :class="{ active: activeFilter === 'in_sync' }"
        @click="toggleFilter('in_sync')"
      >
        <span class="drift-dot drift-dot--sync" />
        {{ store.driftSummary.in_sync }} in sync
      </button>
      <button
        v-if="store.driftSummary.drifted > 0"
        class="drift-stat drift-stat--drifted"
        :class="{ active: activeFilter === 'drifted' }"
        @click="toggleFilter('drifted')"
      >
        <span class="drift-dot drift-dot--drifted" />
        {{ store.driftSummary.drifted }} drifted
      </button>
      <button
        v-if="store.driftSummary.missing > 0"
        class="drift-stat drift-stat--missing"
        :class="{ active: activeFilter === 'missing' }"
        @click="toggleFilter('missing')"
      >
        <span class="drift-dot drift-dot--missing" />
        {{ store.driftSummary.missing }} missing
      </button>
      <button
        v-if="store.driftSummary.extra > 0"
        class="drift-stat drift-stat--extra"
        :class="{ active: activeFilter === 'extra' }"
        @click="toggleFilter('extra')"
      >
        <span class="drift-dot drift-dot--extra" />
        {{ store.driftSummary.extra }} extra
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useGraphStore } from '~/stores/graph'

const store = useGraphStore()
const activeFilter = ref<string | null>(null)

function toggleFilter(status: string) {
  activeFilter.value = activeFilter.value === status ? null : status
}
</script>

<style scoped>
.drift-summary-bar {
  position: fixed;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000;
  background: var(--sm-surface, #12121a);
  border: 1px solid var(--sm-border, #2a2a3a);
  border-radius: var(--sm-radius-md, 10px);
  padding: 6px 16px;
  box-shadow: var(--sm-shadow-elevated, 0 8px 32px rgba(0, 0, 0, 0.4));
}

.drift-bar-inner {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
}

.drift-label {
  font-weight: 600;
  color: var(--sm-text, #e0e0e8);
  margin-right: 4px;
}

.drift-stat {
  display: flex;
  align-items: center;
  gap: 5px;
  background: none;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 3px 8px;
  cursor: pointer;
  color: var(--sm-text-secondary, #a0a0b0);
  font-size: 13px;
  transition: all 0.15s;
}

.drift-stat:hover,
.drift-stat.active {
  border-color: var(--sm-border, #2a2a3a);
  background: rgba(255, 255, 255, 0.04);
  color: var(--sm-text, #e0e0e8);
}

.drift-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.drift-dot--sync { background: #22c55e; }
.drift-dot--drifted { background: #f59e0b; }
.drift-dot--missing { background: #ef4444; }
.drift-dot--extra { background: #3b82f6; }
</style>
