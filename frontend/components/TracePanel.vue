<template>
  <div v-if="store.traceResult" class="trace-panel">
    <div class="trace-header">
      <h3 class="trace-title">Dependencies</h3>
      <button class="trace-close" @click="store.clearTrace()" title="Clear trace">&times;</button>
    </div>

    <div class="trace-origin">
      <span class="trace-origin-label">Tracing:</span>
      <span class="trace-origin-name">{{ originName }}</span>
    </div>

    <div class="trace-stats">
      <div class="trace-stat">
        <span class="trace-stat-value trace-stat--upstream">{{ store.traceResult.upstream.length }}</span>
        <span class="trace-stat-label">upstream</span>
      </div>
      <div class="trace-stat">
        <span class="trace-stat-value trace-stat--downstream">{{ store.traceResult.downstream.length }}</span>
        <span class="trace-stat-label">downstream</span>
      </div>
      <div class="trace-stat">
        <span class="trace-stat-value trace-stat--blast">{{ store.traceResult.blast_radius }}</span>
        <span class="trace-stat-label">blast radius</span>
      </div>
    </div>

    <div v-if="store.traceResult.upstream.length > 0" class="trace-section">
      <div class="trace-section-title trace-section--upstream">Upstream</div>
      <div
        v-for="hop in store.traceResult.upstream"
        :key="hop.node_id"
        class="trace-hop"
        :style="{ paddingLeft: `${12 + hop.depth * 12}px` }"
        @click="store.selectNode(hop.node_id)"
      >
        <span class="trace-hop-name">{{ nodeNames[hop.node_id] || hop.node_id }}</span>
        <span class="trace-hop-edge">{{ hop.edge_label || hop.edge_type }}</span>
      </div>
    </div>

    <div v-if="store.traceResult.downstream.length > 0" class="trace-section">
      <div class="trace-section-title trace-section--downstream">Downstream</div>
      <div
        v-for="hop in store.traceResult.downstream"
        :key="hop.node_id"
        class="trace-hop"
        :style="{ paddingLeft: `${12 + hop.depth * 12}px` }"
        @click="store.selectNode(hop.node_id)"
      >
        <span class="trace-hop-name">{{ nodeNames[hop.node_id] || hop.node_id }}</span>
        <span class="trace-hop-edge">{{ hop.edge_label || hop.edge_type }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useGraphStore } from '~/stores/graph'

const store = useGraphStore()

const nodeNames = computed(() => {
  const map: Record<string, string> = {}
  for (const node of store.nodes) {
    map[node.id] = node.name
  }
  return map
})

const originName = computed(() => {
  if (!store.traceResult) return ''
  return nodeNames.value[store.traceResult.origin_id] || store.traceResult.origin_id
})
</script>

<style scoped>
.trace-panel {
  padding: 12px 0;
  border-top: 1px solid var(--sm-border, #2a2a3a);
}

.trace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px 8px;
}

.trace-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--sm-text, #e0e0e8);
  margin: 0;
}

.trace-close {
  background: none;
  border: none;
  color: var(--sm-text-secondary, #a0a0b0);
  font-size: 18px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}

.trace-close:hover {
  color: var(--sm-text, #e0e0e8);
}

.trace-origin {
  padding: 0 16px 8px;
  font-size: 12px;
}

.trace-origin-label {
  color: var(--sm-text-secondary, #a0a0b0);
}

.trace-origin-name {
  color: var(--sm-text, #e0e0e8);
  font-weight: 500;
  margin-left: 4px;
}

.trace-stats {
  display: flex;
  gap: 12px;
  padding: 0 16px 12px;
}

.trace-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.trace-stat-value {
  font-size: 18px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.trace-stat--upstream { color: #3b82f6; }
.trace-stat--downstream { color: #f59e0b; }
.trace-stat--blast { color: #ef4444; }

.trace-stat-label {
  font-size: 10px;
  color: var(--sm-text-secondary, #a0a0b0);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.trace-section {
  margin-top: 4px;
}

.trace-section-title {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 16px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.trace-section--upstream { color: #3b82f6; }
.trace-section--downstream { color: #f59e0b; }

.trace-hop {
  padding: 4px 16px;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: background 0.1s;
}

.trace-hop:hover {
  background: rgba(255, 255, 255, 0.04);
}

.trace-hop-name {
  color: var(--sm-text, #e0e0e8);
  font-weight: 500;
}

.trace-hop-edge {
  font-size: 10px;
  color: var(--sm-text-secondary, #a0a0b0);
  opacity: 0.7;
}
</style>
